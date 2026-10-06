import json
import math
from datetime import datetime, timezone

from .model import date_value

def apply_references(listings, path):
    if not path.exists(): return
    references = json.loads(path.read_text()).get('products',{})
    for l in listings:
        reference = references.get(l.mpn) if l.mpn else None
        if not reference: continue
        checked = date_value(reference.get('checked_at'))
        if not checked or not reference.get('source_url') or (datetime.now(timezone.utc)-checked).days > 35: continue
        for key, value in reference.get('specs',{}).items():
            if key in l.specs:
                l.specs[key] = value
                l.spec_sources[key] = reference['source_url']

def cost_to_32(listing, ram_prices):
    s = listing.specs
    base, installed, slots, occupied = listing.price_egp, s.get('ram_gb'), s.get('ram_slots'), s.get('ram_modules')
    if base is None or installed is None: return None
    if installed >= 32: return base
    maximum = s.get('ram_max_gb')
    if maximum is None or maximum < 32: return None
    if slots is None or occupied is None or s.get('ram_soldered') is None: return None
    if s.get('ram_soldered'): return None  # mixed soldered layouts need an explicit upgrade plan
    single16 = ram_prices.get((s.get('ram_type'),'SODIMM',16))
    if not single16 or slots < 2: return None
    if installed == 16 and occupied == 1 and slots > occupied: return base+single16
    if installed in {8,16} and occupied <= slots: return base+2*single16
    return None

def evaluate(listing, db, baseline):
    result = {'history_30d':db.history(listing,30),'history_90d':db.history(listing,90),
              'true_cost_to_32gb_egp':None,'egp_per_blender_point':None,'egp_per_cpu_multi_point':None,
              'egp_per_cpu_single_point':None,'import_premium_pct':None}
    if listing.mpn:
        ref = baseline.get('products',{}).get(listing.mpn,{})
        for score, metric in [('blender_score','egp_per_blender_point'),('cpu_multi_score','egp_per_cpu_multi_point'),('cpu_single_score','egp_per_cpu_single_point')]:
            value=ref.get(score)
            checked=date_value(ref.get('checked_at'))
            if value and value>0 and listing.price_egp and checked and ref.get('source_url') and (datetime.now(timezone.utc)-checked).days <= 35:
                result[metric]=round(listing.price_egp/value,4)
        fx=baseline.get('fx',{})
        fx_date=date_value(fx.get('checked_at'))
        ref_date=date_value(ref.get('checked_at'))
        if fx.get('usd_egp') and fx.get('source_url') and fx_date and ref_date and ref.get('source_url') and (datetime.now(timezone.utc)-fx_date).days<=7 and (datetime.now(timezone.utc)-ref_date).days<=7 and ref.get('us_price_usd') and listing.price_egp:
            result['import_premium_pct']=round((listing.price_egp/(ref['us_price_usd']*fx['usd_egp'])-1)*100,2)
    return result

def comparisons(listings):
    groups={}
    for l in listings:
        if not l.mpn or not l.eligible(): continue
        # Keep RAM/storage/condition variants separate even if a store reused an MPN.
        key=(l.mpn,l.condition,l.specs.get('ram_gb'),l.specs.get('storage_gb'),l.specs.get('gpu_model'),l.specs.get('cpu_model'))
        groups.setdefault(key,[]).append(l)
    result=[]
    for key, values in groups.items():
        by_store={}
        for l in values:
            if l.store not in by_store or l.price_egp<by_store[l.store].price_egp: by_store[l.store]=l
        values=sorted(by_store.values(),key=lambda l:l.price_egp)
        if len(values)<2: continue
        result.append({'mpn':key[0],'condition':key[1],'min_egp':values[0].price_egp,'max_egp':values[-1].price_egp,
                       'spread_egp':values[-1].price_egp-values[0].price_egp,
                       'offers':[{'store':l.store,'price_egp':l.price_egp,'url':l.url} for l in values]})
    return result
