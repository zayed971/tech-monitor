"""Export every collected retailer laptop under the user's price ceiling."""
import csv
import json
from collections import Counter
from urllib.parse import urlsplit,parse_qs
from .model import now


def product_key(listing):
    parts=urlsplit(listing.url)
    if parts.hostname and parts.hostname.removeprefix('www.')=='sigma-computer.com':
        return listing.store,parse_qs(parts.query).get('id',[parts.path])[0]
    return listing.store,parts.path.rstrip('/')


def export_under_budget(listings,root):
    settings=root/'data/laptop-search.json'
    if not settings.exists(): return None
    budget=json.loads(settings.read_text())['budget_egp']
    registry={s['id']:s for s in json.loads((root/'sources.json').read_text())}
    under=[l for l in listings if l.category=='laptop' and l.source_kind=='retailer'
           and l.price_egp is not None and 100<=l.price_egp<=budget and l.currency=='EGP' and not l.placeholder]
    under.sort(key=lambda l:(not l.eligible(),l.price_egp,l.store))
    records=[]
    for l in under:
        record=l.dict()
        expected=urlsplit(registry.get(l.source,{}).get('base','')).hostname
        actual=urlsplit(l.url).hostname
        valid_host=bool(expected and actual and expected.removeprefix('www.')==actual.removeprefix('www.'))
        if not valid_host:
            record['quality_issues']=record['quality_issues']+['Listing URL does not belong to its configured retailer; needs verification']
        record['eligible_for_review']=l.eligible() and valid_host
        record['product_key']=product_key(l)[1]
        records.append(record)
    data=root/'data/laptop-review'; data.mkdir(exist_ok=True)
    def write_json(name,value):
        path=data/name; temporary=path.with_suffix(path.suffix+'.tmp')
        temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n'); temporary.replace(path)
    write_json('all-under-70000.json',records)
    columns=['store','price_egp','stock','condition','raw_title','mpn','sku','cpu_model','gpu_model','gpu_vram_gb','gpu_tgp_w','ram_gb','ram_type','ram_modules','ram_slots','ram_max_gb','storage_gb','display_resolution','display_hz','display_srgb_pct','os','warranty_months','warranty_type','observed_at','verified_at','eligible_for_review','quality_issues','url']
    path=data/'all-under-70000.csv'; temporary=path.with_suffix('.csv.tmp')
    with temporary.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
        for record in records:
            row={k:record.get(k,record['specs'].get(k)) for k in columns}
            row['quality_issues']='; '.join(row['quality_issues'])
            row={k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for k,v in row.items()}
            writer.writerow(row)
    temporary.replace(path)
    eligible=[r for r in records if r['eligible_for_review']]
    unique={}
    for r in eligible: unique.setdefault((r['store'],r['product_key']),r)
    unique=list(unique.values())
    gpu_counts=Counter(r['specs'].get('gpu_model') or 'unknown/integrated' for r in unique if r['condition']=='new')
    summary={'generated_at':now(),'budget_egp':budget,'budget_basis':'advertised laptop price; shipping and RAM upgrades excluded',
             'under_budget_retailer_variant_rows_all_stock_states':len(records),
             'under_budget_unique_retailer_products_all_stock_states':len({(r['store'],r['product_key']) for r in records}),
             'eligible_in_stock_variant_rows':len(eligible),'eligible_in_stock_unique_products':len(unique),
             'in_stock_unique_products_by_condition':dict(Counter(r['condition'] for r in unique)),
             'in_stock_unique_products_by_store':dict(Counter(r['store'] for r in unique)),
             'in_stock_new_products_by_gpu':dict(gpu_counts),
             'observed_at_range':[min((r['observed_at'] for r in records),default=None),max((r['observed_at'] for r in records),default=None)],
             'limits':'Every recognized under-budget retailer laptop in the collected dataset; not every laptop in Egypt. Product counts collapse variants and Sigma language duplicates; variant offers remain explicit in the export. A feed marked in stock is not a final checkout guarantee. Missing specs stay unknown.'}
    write_json('summary.json',summary)
    return summary
