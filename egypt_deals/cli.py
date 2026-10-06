import argparse
import csv
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .adapters import collect
from .baseline import update_fx
from .alerts import detect, matches, send_pending, verify_pending_stock
from .http import Client
from .metrics import apply_references, comparisons, cost_to_32, evaluate
from .model import date_value, now
from .storage import Database
from .telegram_setup import load_settings, setup as setup_telegram, TelegramSetupError
from .import_cost import landed_egp

def write_json(path,value):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2))
    temp.replace(path)

def export(db, root, statuses=None):
    listings=db.listings()
    baseline=json.loads((root/'references.json').read_text())
    rules=json.loads((root/'rules.json').read_text())
    prices={}
    for l in listings:
        if l.category=='ram' and l.eligible() and l.specs.get('ram_modules')==1:
            key=(l.specs.get('ram_type'),l.specs.get('ram_form_factor'),l.specs.get('ram_gb'))
            prices[key]=min(prices.get(key,float('inf')),l.price_egp)
    records=[]
    for l in listings:
        record=l.dict()
        record['metrics']=evaluate(l,db,baseline)
        record['metrics']['true_cost_to_32gb_egp']=cost_to_32(l,prices) if l.category=='laptop' else None
        record['matched_rules']=[r['id'] for r in rules['thresholds'] if matches(l,r)]
        records.append(record)
    records.sort(key=lambda r:(not r['alert_eligible'],r['price_egp'] or float('inf')))
    from .laptop_review import export_under_budget
    export_under_budget(listings,root)
    data=root/'data'
    statuses=db.statuses()
    from .catalog_report import export_hardware
    export_hardware(listings,root,statuses)
    write_json(data/'listings.json',records)
    write_json(data/'comparisons.json',comparisons(listings))
    write_json(data/'source-status.json',statuses)
    columns=['store','source','url','observed_at','raw_title','price_egp','old_price_egp','currency','stock','condition','mpn','sku','alert_eligible','matched_rules']
    spec_columns=['cpu_model','gpu_model','gpu_vram_gb','ram_gb','ram_type','ram_form_factor','ram_modules']
    with (data/'listings.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns+spec_columns+['specs_json','used_json','metrics_json'])
        writer.writeheader()
        for r in records:
            row={c:r.get(c) for c in columns}
            row['matched_rules']=','.join(r['matched_rules'])
            row.update({k:r['specs'].get(k) for k in spec_columns})
            row.update({name+'_json':json.dumps(r[name],ensure_ascii=False) for name in ['specs','used','metrics']})
            # Spreadsheet imports must not interpret scraped text as formulas.
            row={k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for k,v in row.items()}
            writer.writerow(row)
    report=['# Egyptian computer price collection','',f'Generated: {now()}','',f'{len(records)} extracted listings; {sum(r["alert_eligible"] for r in records)} eligible for price alerts.','',
            'Results are a bounded sample, not a claim to the lowest price in Egypt. An alert needs an explicit in-stock price, matching product facts and a fresh retailer observation. Aggregator entries also need a recent source update and retailer verification.','',
            '## Target candidates','']
    for rule in rules['thresholds']:
        candidates=[r for r in records if rule['id'] in r['matched_rules']]
        eligible=[r for r in candidates if r['alert_eligible']]
        report.append(f'- **{rule["label"]}** (target {rule["max_egp"]:,} EGP): '+(f'best verified {eligible[0]["price_egp"]:,.0f} EGP at {eligible[0]["store"]}; {eligible[0]["url"]}' if eligible else 'no verified eligible listing in this run')+f'. {len(candidates)} matching candidates including unverified/out-of-stock.')
    report+=['','## Source coverage','']
    for s in statuses or []:
        report.append(f'- {s["source"]}: {s.get("status") or s.get("verdict") or "n/a"}; {s.get("listings", s.get("kept", 0))} listings, {s.get("pages", s.get("requests", 0))} pages'+(' — '+', '.join(map(str, s['errors'])) if s.get('errors') else ''))
    flagged=[r for r in records if r['quality_issues']]
    if flagged:
        report+=['','## Listings requiring verification','']
        for r in flagged[:20]: report.append(f'- {r["store"]}: {r["raw_title"]} — '+ '; '.join(r['quality_issues'])+f'. {r["url"]}')
    fx=baseline.get('fx',{})
    if fx.get('usd_egp'): report+=['','## Exchange-rate baseline','',f'1 USD = {fx["usd_egp"]} EGP; provider quote: {fx["checked_at"]}; {fx["source_url"]}. This is a reference rate, not a guaranteed bank execution rate.']
    report+=['','## Limits','', 'Price history begins with the first collection. The 30/90-day values are observed lows, with observation counts and dates, not reconstructed historical lows. Missing RAM layouts, TGP, benchmarks and reputation evidence stay unknown. Disappearance of a used listing does not prove a sale or a selling price. Telegram and continuous scheduling require configuration described in README.md.']
    (data/'report.md').write_text('\n'.join(report)+'\n')
    return records

def run(args, db, root):
    started=now()
    sources=json.loads((root/'sources.json').read_text())
    verification_sources=[dict(s) for s in sources]
    rules=json.loads((root/'rules.json').read_text())
    if args.sources:
        selected=set(args.sources.split(','))
        unknown=selected-{s['id'] for s in sources}
        if unknown: raise SystemExit('Unknown sources: '+','.join(sorted(unknown)))
        sources=[s for s in sources if s['id'] in selected]
    if args.due: sources=[s for s in sources if db.due(s)]
    if args.due and not sources:
        if args.send: verify_pending_stock(db, root, getattr(args, 'delay', 4))
        telegram=send_pending(db) if args.send else {'status':'disabled','pending':len(db.pending())}
        print(json.dumps({'status':'idle','checked_at':now(),'reason':'no_sources_due','telegram':telegram}),flush=True)
        return
    known={s['id']:{} for s in sources}
    for listing in db.listings():
        if listing.source in known and listing.verified_at:known[listing.source][listing.url]=listing.verified_at
    progress_dir=root/'data/harvest-progress';progress_dir.mkdir(exist_ok=True)
    def work(source):
        source={**source,'_crawl_state_path':str(root/'data/harvest-state'/(source['id']+'.json')),'_known_products':known[source['id']]}
        client=Client(root/'data'/'cache'/source['id'],delay=args.delay,ttl=args.cache_ttl)
        source_scope=source.get('catalog_scope',args.scope) if args.scope=='catalog' else args.scope
        if args.scope=='hardware':source_scope=source.get('harvest_scope','hardware')
        def progress(details):
            write_json(progress_dir/(source['id']+'.json'),{'status':'running','checked_at':now(),**details})
            print(json.dumps({'progress':details}),flush=True)
        def checkpoint(listings,details):
            apply_references(listings,root/'references.json')
            partial=Database(root/'data/deals.sqlite3')
            try:partial.save(listings,{'source':source['id'],'status':'running','listings':len(listings),'pages':details.get('pages',0),'errors':[],'scope':source_scope,'source_configuration_revision':source.get('revision',0),**details})
            finally:partial.close()
        try:
            result=collect(source,client,source.get('max_pages',args.max_pages),source.get('max_details',args.max_details),verification_sources,rules['thresholds'],source_scope,progress,checkpoint)
            result[1]['source_configuration_revision']=source.get('revision',0)
            write_json(progress_dir/(source['id']+'.json'),{'checked_at':now(),**result[1]})
            return source,result
        except Exception as error:
            # One site's unexpected markup must not take down other sources or
            # the watcher. Record its error type without dumping response data.
            status={'source':source['id'],'status':'blocked_or_failed','listings':0,'pages':0,'errors':['Unexpected '+type(error).__name__+'; adapter needs review'],'scope':source_scope,'source_configuration_revision':source.get('revision',0)}
            write_json(progress_dir/(source['id']+'.json'),{'checked_at':now(),**status})
            return source,([],status)
        finally: client.close()
    statuses=[]
    run_ids=set()
    saved_statuses={s['source']:s for s in db.statuses()}
    def source_order(source):
        previous=saved_statuses.get(source['id'])
        revised=previous and source.get('revision',0)>previous.get('source_configuration_revision',0)
        return (not bool(revised),bool(previous),(previous or {}).get('started_at') or (previous or {}).get('last_saved_at') or '')
    # Aggregators first; independent stores may run concurrently. A single client is never shared.
    for group in [[s for s in sources if s.get('kind')=='aggregator'],[s for s in sources if s.get('kind')!='aggregator']]:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            jobs=[pool.submit(work,s) for s in sorted(group,key=source_order)]
            for job in as_completed(jobs):
                source,(listings,status)=job.result()
                apply_references(listings,root/'references.json')
                db.save(listings,status)
                run_ids.update(l.identity for l in listings)
                statuses.append(status)
                print(json.dumps(status),flush=True)
                if len(statuses)%3==0:
                    from .catalog_report import export_hardware
                    export_hardware(db.listings(),root,db.statuses())
    listings=db.listings()
    rules=json.loads((root/'rules.json').read_text())
    alerts=detect(listings,rules,db)
    db.expire_invalid()
    write_json(root/'data'/'alerts.json',alerts)
    if args.send:
        print(json.dumps({'alert_stock_verification':verify_pending_stock(db, root, args.delay)}), flush=True)
    telegram=send_pending(db) if args.send else {'status':'disabled','pending':len(db.pending())}
    records=export(db,root,statuses)
    fresh=[r for r in records if r['id'] in run_ids and date_value(r['observed_at'])>=date_value(started)]
    priced=[r for r in fresh if r['currency']=='EGP' and r['price_egp'] is not None and r['price_egp']>=100 and not r['placeholder']]
    from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
    def product_key(r):
        p=urlsplit(r['url'])
        return r['store'],urlunsplit((p.scheme,p.netloc,p.path,urlencode([(k,v) for k,v in parse_qsl(p.query) if k!='variant']),''))
    manifest={'started_at':started,'finished_at':now(),'scope':args.scope,'cache_ttl_seconds':args.cache_ttl,
              'selected_sources':[s['id'] for s in sources],'fresh_listing_rows':len(fresh),'fresh_priced_egp_rows':len(priced),
              'fresh_unique_priced_store_products':len({product_key(r) for r in priced}),
              'fresh_in_stock_priced_rows':sum(r['stock']=='in_stock' for r in priced),
              'old_or_cached_rows_excluded_from_fresh_count':len(records)-len(fresh)}
    write_json(root/'data'/'run-manifest.json',manifest)
    write_json(root/'data'/'fresh-listings.json',fresh)
    print(json.dumps({'run_manifest':manifest}),flush=True)
    print(json.dumps({'listings':len(records),'eligible':sum(r['alert_eligible'] for r in records),'alerts':len(alerts),'telegram':telegram,'report':str(root/'data'/'report.md')}),flush=True)

def main():
    parser=argparse.ArgumentParser(description='Egyptian PC/laptop price scraper')
    parser.add_argument('command',choices=['run','watch','export','notify','fx','telegram-setup','import-check'],nargs='?',default='run')
    parser.add_argument('--quote-file',type=Path,help='JSON file of item, shipping, import charges and payment-rate costs')
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--sources',help='comma-separated source IDs')
    parser.add_argument('--scope',choices=['tracked','catalog','laptops','hardware'],default='tracked',help='retain tracked targets, broader catalog, laptops, or all hardware')
    parser.add_argument('--max-pages',type=int,default=4)
    parser.add_argument('--max-details',type=int,default=8)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--delay',type=float,default=4)
    parser.add_argument('--cache-ttl',type=int,default=1800)
    parser.add_argument('--due',action='store_true',help='only sources whose scheduled interval elapsed')
    parser.add_argument('--send',action='store_true',help='send pending Telegram alerts using environment variables')
    parser.add_argument('--days',type=int,default=21,help='watch stopping horizon; anchored to first watch invocation')
    parser.add_argument('--bootstrap',action='store_true',help='watch: harvest all configured sources immediately before interval-gated cycles')
    parser.add_argument('--poll-seconds',type=int,default=60,help='watch scheduling interval')
    args=parser.parse_args()
    if args.delay<3: parser.error('request delay must be at least 3 seconds')
    if not 1<=args.workers<=8 or not 1<=args.max_pages<=1000 or not 0<=args.max_details<=10000 or args.days<1 or args.poll_seconds<15: parser.error('invalid limits')
    root=args.root.resolve()
    load_settings(root)
    db=Database(root/'data'/'deals.sqlite3')
    try:
        if args.command=='import-check':
            if not args.quote_file: parser.error('--quote-file is required for import-check')
            quote=json.loads(args.quote_file.read_text())
            total=landed_egp(*(quote.get(k) for k in ['item_usd','shipping_usd','import_charges_usd','usd_egp']),card_fee_pct=quote.get('card_fee_pct',0),extra_egp=quote.get('extra_egp',0))
            local=quote.get('local_comparable_price_egp')
            print(json.dumps({'landed_egp':total,'saving_egp':round(local-total,2) if local and total is not None else None,'status':'incomplete_quote' if total is None else 'calculated','source_url':quote.get('source_url')}))
        elif args.command=='telegram-setup': print(json.dumps(setup_telegram(root)))
        elif args.command=='fx': print(json.dumps(update_fx(root)))
        elif args.command=='export': export(db,root)
        elif args.command=='notify':
            print(json.dumps({'alert_stock_verification':verify_pending_stock(db, root, args.delay)}), flush=True)
            print(json.dumps(send_pending(db)))
        elif args.command=='run': run(args,db,root)
        else:
            state=root/'data'/'watch.json'
            if not state.exists(): write_json(state,{'started_at':now(),'stop_at':(datetime.now(timezone.utc)+timedelta(days=args.days)).isoformat()})
            end=date_value(json.loads(state.read_text())['stop_at'])
            args.due=True
            bootstrap=args.bootstrap
            while datetime.now(timezone.utc)<end:
                write_json(root/'data'/'watch-status.json',{'status':'running','checked_at':now(),'stop_at':end.isoformat(),'scope':args.scope})
                args.due=not bootstrap
                run(args,db,root)
                bootstrap=False
                # Short sleeps allow prompt shutdown; collection is interval-gated by source.
                for _ in range(max(1,args.poll_seconds//15)):
                    if datetime.now(timezone.utc)>=end: break
                    time.sleep(15)
            write_json(root/'data'/'watch-status.json',{'status':'stopped_at_deadline','checked_at':now(),'stop_at':end.isoformat()})
            print('Monitoring horizon reached. Review data/report.md for the best observed verified price.')
    except KeyboardInterrupt:
        print('Stopped; collected data preserved.')
    except TelegramSetupError as e:
        raise SystemExit(str(e)) from None
    finally: db.close()

if __name__=='__main__': main()
