r"""Stage 2 of the deal hunt: Hermes (DeepSeek, zero tools) reads the whole stage-1 shortlist in batches and says which rows deserve
a real price check. It never sees the internet and never invents prices: it judges only what the rows say (title coherence, brand,
mislabeled or no-name items, variant or bundle traps) and picks the ones worth verifying.

    .venv\Scripts\python.exe scripts\hermes_review.py [--batch 40] [--max-batches 0]

Money rules are the project's (D-004): balance read before EVERY call, hard stop at balance 1.85, job cap US$2, key never printed.
Output: data\deal_scan\hermes_verdicts.jsonl (one JSON per row: verdict look|ok|skip|unsure, model, flags, reason). Resumable.
"""
import argparse
import json
import os
import sys
import time

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, 'scripts'))
import store_payments as sp  # noqa: E402

OUT_DIR = os.path.join(root, 'data', 'deal_scan')
sp.HDIR = os.path.join(OUT_DIR, '_hermes')
sp.WSL_HDIR = '/mnt/c/PROJECTS/tech_monitor/data/deal_scan/_hermes'
VERDICTS = os.path.join(OUT_DIR, 'hermes_verdicts.jsonl')

PROMPT = """You are screening tech price listings for a buyer in Egypt. Each line below is a listing already flagged by a price rule
(the rule and its numbers are in the line). You have NO internet. Judge ONLY from the text on the line. Do not quote outside prices.

For every line return a verdict:
  "look"   = AT MOST 5 lines in the whole batch: the ones most likely to be a genuinely good deal worth a real price check. Needs a
             coherent, recognisable product from a known brand (or a clear used item with specs), a price signal that is not explained by
             pack size, colour, bundle or variant differences, and a product people actually want (storage, monitors, networking, power,
             audio, input devices, cooling, parts). Prefer bigger savings on higher-priced items over 100 EGP differences on cheap ones.
  "ok"     = coherent product, price plausible, but not one of the 5 best.
  "skip"   = junk: no-name or "compatible"/replica item, accessory or part for something else, bundle, multi-pack or variant that
             explains the low price (1-pack vs 3-pack, different capacity or colour), wrong category, contradictory title, typo price.
  "unsure" = cannot tell.
Also give "model" (clean product name, max 8 words) and "flags" (any of: noname, compatible_part, variant_mismatch, bundle, used_unclear,
typo_price, wrong_category, accessory_of_other_item, none) and "why" (max 12 words).

Reply with ONE JSON object only, no prose: {"rows":[{"n":<line number>,"verdict":"look|ok|skip|unsure","model":"...","flags":["..."],"why":"..."}]}
Every line number must appear exactly once.

LINES:
"""


def line(n, d):
    return (f"{n}|{d['zone']}|{d['store']}|{d['category']}|{d['condition']}|{d['price_egp']} EGP"
            f"{'' if d['currency']=='EGP' else ' (' + str(round(d['price_local'] or 0)) + ' ' + d['currency'] + ')'}|"
            f"{'; '.join(d['signals'])[:150]}|{d['title']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--batch', type=int, default=40)
    ap.add_argument('--max-batches', type=int, default=0)
    ap.add_argument('--shortlist', default=os.path.join(OUT_DIR, 'shortlist.jsonl'))
    a = ap.parse_args()
    rows = [json.loads(x) for x in open(a.shortlist, encoding='utf-8')]
    done = set()
    if os.path.exists(VERDICTS):
        done = {json.loads(x)['id'] for x in open(VERDICTS, encoding='utf-8') if x.strip()}
    todo = [r for r in rows if r['id'] not in done]
    print(f'{len(rows)} shortlisted, {len(todo)} not yet read', flush=True)
    start = sp.read_balance()
    if start is None: sys.exit('balance unreadable; stop')
    print(f'[money] balance before: {start:.2f} at {sp.now()}', flush=True)
    sp.GLOBAL_HARD_STOP = 1.85
    with open(os.path.join(root, 'data', 'store_payments_balance.txt'), 'a') as f: f.write(f'{sp.now()} deal-review start {start:.2f}\n')
    batches = [todo[i:i + a.batch] for i in range(0, len(todo), a.batch)]
    if a.max_batches: batches = batches[:a.max_batches]
    for bi, batch in enumerate(batches, 1):
        prompt = PROMPT + '\n'.join(line(i, d) for i, d in enumerate(batch, 1))
        obj = None
        for model, tag in ((sp.FLASH, 'f1'), (sp.FLASH, 'f2'), (sp.PRO, 'p1')):
            try: sp.check_money(start)
            except sp.BudgetStop as e:
                print('[money] STOP:', e, flush=True); return
            out, usage = sp.run_hermes(f'b{bi:03d}', tag, prompt, model)
            obj = sp.repair_json(out)
            if isinstance(obj, dict) and isinstance(obj.get('rows'), list) and 'deepseek' in str(usage.get('provider', 'deepseek')).lower(): break
            obj = None
            print(f'[batch {bi}] {tag} unusable reply', flush=True)
        if obj is None: print(f'[batch {bi}] gave up'); continue
        got = {r.get('n'): r for r in obj['rows'] if isinstance(r, dict)}
        with open(VERDICTS, 'a', encoding='utf-8', newline='\n') as f:
            for i, d in enumerate(batch, 1):
                v = got.get(i)
                if not v: continue
                f.write(json.dumps({**d, 'verdict': v.get('verdict'), 'model': v.get('model'), 'flags': v.get('flags'), 'why': v.get('why'),
                                    'reviewer': model}, ensure_ascii=False) + '\n')
        print(f'[batch {bi}/{len(batches)}] {len(got)}/{len(batch)} rows judged by {model} at {sp.now()}', flush=True)
    end = sp.read_balance()
    print(f'[money] balance after: {end}', flush=True)
    with open(os.path.join(root, 'data', 'store_payments_balance.txt'), 'a') as f: f.write(f'{sp.now()} deal-review end {end}\n')


if __name__ == '__main__':
    main()
