"""Hardware offers, comparable memory prices, and explicit collection gaps."""
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from .hardware import HARDWARE_CATEGORIES,GEAR_CATEGORIES
from .model import now
from .crawl_state import read,inventory

def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temporary.replace(path)

def write_csv(path,records,columns):
    temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
        for record in records:
            row={k:record.get(k) for k in columns}
            for key,value in row.items():
                if isinstance(value,(list,dict)):row[key]=json.dumps(value,ensure_ascii=False)
                elif isinstance(value,str) and value.startswith(('=','+','-','@')):row[key]="'"+value
            writer.writerow(row)
    temporary.replace(path)

def product_key(record):
    p=urlsplit(record['url'])
    return record['store'],parse_qs(p.query).get('id',[p.path])[0]

def gap_kind(error):
    e=error.lower()
    if 'robots' in e:return 'robots_policy_or_unavailable'
    if any(x in e for x in ['401','403','429','access challenge','paused']):return 'access_or_rate_limit'
    if '404' in e:return 'endpoint_not_found'
    if 'region' in e:return 'wrong_region'
    if any(x in e for x in ['extract','json','sitemap','adapter']):return 'adapter_or_markup'
    return 'network_or_parser_failure'

def export_hardware(listings,root,statuses=None):
    folder=root/'data/hardware';folder.mkdir(parents=True,exist_ok=True)
    records=[]
    for listing in listings:
        if listing.category not in HARDWARE_CATEGORIES:continue
        record=listing.dict();record.update(record['specs'])
        record['under_budget']=bool(listing.price_egp is not None and listing.price_egp<=70000)
        records.append(record)
    records.sort(key=lambda r:(r['category'],not r['alert_eligible'],r['price_egp'] or float('inf')))
    columns=['store','category','accessory_type','brand','raw_title','parent_title','variant_title','mpn','sku','price_egp','old_price_egp','currency','stock','condition','alert_eligible','under_budget','build_complete','cpu_model','cpu_socket','gpu_model','gpu_vram_gb','ram_gb','ram_type','ram_form_factor','ram_modules','ram_module_gb','ram_speed_mt_s','ram_cas_latency','ram_ecc','ram_registered','storage_gb','storage_type','storage_pcie_gen','psu_w','psu_80plus','warranty_months','warranty_type','observed_at','verified_at','quality_issues','url']
    write_csv(folder/'all-hardware.csv',records,columns)
    write_csv(folder/'ram-offers.csv',[r for r in records if r['category']=='ram'],columns)
    write_csv(folder/'pc-builds-and-bundles.csv',[r for r in records if r['category'] in {'pc','bundle'}],columns)
    write_csv(folder/'separate-components.csv',[r for r in records if r['category'] not in {'laptop','pc','bundle'}],columns)
    gear=[r for r in records if r['category'] in GEAR_CATEGORIES]
    write_csv(folder/'accessories-and-tech.csv',gear,columns)
    gear_groups=defaultdict(list)
    for r in gear:gear_groups[(r['category'],r['accessory_type'],r['brand'])].append(r)
    gear_summary=[]
    for (category,kind,brand),offers in gear_groups.items():
        verified=[r for r in offers if r['alert_eligible'] and r['source_kind']=='retailer']
        cheapest=min(verified,key=lambda r:r['price_egp']) if verified else None
        gear_summary.append({'category':category,'accessory_type':kind,'brand':brand,'offer_rows':len(offers),'verified_in_stock_offer_rows':len(verified),'from_egp':cheapest['price_egp'] if cheapest else None,'cheapest_title':cheapest['raw_title'] if cheapest else None,'cheapest_url':cheapest['url'] if cheapest else None})
    write_csv(folder/'accessories-by-type-and-brand.csv',gear_summary,['category','accessory_type','brand','offer_rows','verified_in_stock_offer_rows','from_egp','cheapest_title','cheapest_url'])
    category_counts=Counter(r['category'] for r in gear)
    write_json(folder/'accessories-summary.json',{'generated_at':now(),'offer_rows':len(gear),'verified_in_stock_retailer_rows':sum(r['alert_eligible'] and r['source_kind']=='retailer' for r in gear),'by_category':{name:category_counts[name] for name in sorted(GEAR_CATEGORIES)},'categories_not_yet_observed':[name for name in sorted(GEAR_CATEGORIES) if not category_counts[name]],'by_type':dict(Counter(r['accessory_type'] or 'unspecified' for r in gear)),'limits':'Coverage is limited to configured public sources. From-prices span different models; compare exact specifications. Missing accessories, price, stock and compatibility remain unknown.'})
    write_csv(folder/'unpriced-or-unverified.csv',[r for r in records if not r['alert_eligible']],columns)
    write_csv(root/'data/all-products-under-70000.csv',[r for r in records if r['under_budget'] and r['price_egp'] is not None and r['price_egp']>=100 and r['currency']=='EGP' and not r['placeholder']],columns)
    eligible=[r for r in records if r['alert_eligible'] and r['source_kind']=='retailer']
    memory=defaultdict(list)
    for r in eligible:
        if r['category']!='ram' or r.get('ram_gb') is None or r.get('ram_type') is None:continue
        key=tuple(r.get(k) for k in ['brand','ram_type','ram_gb','ram_form_factor','ram_modules','ram_speed_mt_s','ram_cas_latency','ram_ecc','ram_registered','condition'])
        memory[key].append(r)
    ram_prices=[]
    for key,offers in memory.items():
        cheapest=min(offers,key=lambda r:r['price_egp'])
        keys=['brand','ram_type','capacity_gb','form_factor','modules','speed_mt_s','cas_latency','ecc','registered','condition']
        ram_prices.append({**dict(zip(keys,key)),'min_egp':cheapest['price_egp'],'max_egp':max(r['price_egp'] for r in offers),'offer_rows':len(offers),'stores':sorted({r['store'] for r in offers}),'cheapest_store':cheapest['store'],'cheapest_title':cheapest['raw_title'],'cheapest_url':cheapest['url'],'observed_at':cheapest['observed_at']})
    ram_prices.sort(key=lambda r:(r['ram_type'],r['capacity_gb'],r['form_factor'] or '',r['min_egp']))
    write_json(folder/'ram-prices-by-brand.json',ram_prices)
    write_csv(folder/'ram-prices-by-brand.csv',ram_prices,['brand','ram_type','capacity_gb','form_factor','modules','speed_mt_s','cas_latency','ecc','registered','condition','min_egp','max_egp','offer_rows','stores','cheapest_store','cheapest_title','cheapest_url','observed_at'])
    floor=[]
    for generation in ['DDR2','DDR3','DDR4','DDR5']:
        for capacity in [8,16,32,64]:
            for form in ['DIMM','SODIMM','RDIMM']:
                offers=[r for r in eligible if r['category']=='ram' and r.get('ram_gb')==capacity and r.get('ram_type')==generation and r.get('ram_form_factor')==form and r['condition']=='new']
                chosen=min(offers,key=lambda r:r['price_egp']) if offers else None
                floor.append({'ram_type':generation,'capacity_gb':capacity,'form_factor':form,'min_egp':chosen['price_egp'] if chosen else None,'brand':chosen['brand'] if chosen else None,'modules':chosen['ram_modules'] if chosen else None,'store':chosen['store'] if chosen else None,'url':chosen['url'] if chosen else None,'status':'observed_in_stock' if chosen else 'no_verified_matching_offer'})
    write_csv(folder/'ram-capacity-overview.csv',floor,['ram_type','capacity_gb','form_factor','min_egp','brand','modules','store','status','url'])
    summary={'generated_at':now(),'price_collection_ceiling':None,'deal_budget_egp':70000,'hardware_offer_rows_all_stock_states':len(records),'unique_store_product_urls':len({product_key(r) for r in records}),'eligible_in_stock_retailer_offer_rows':len(eligible),'offer_rows_by_category':dict(Counter(r['category'] for r in records)),'eligible_offer_rows_by_category':dict(Counter(r['category'] for r in eligible)),'ram_brands_observed':sorted({r['brand'] for r in records if r['category']=='ram' and r['brand']}),'ram_offers_missing_capacity':sum(r['category']=='ram' and r.get('ram_gb') is None for r in records),'ram_offers_missing_generation':sum(r['category']=='ram' and r.get('ram_type') is None for r in records),'ram_offers_missing_form_factor':sum(r['category']=='ram' and r.get('ram_form_factor') is None for r in records),'ram_offers_missing_module_count':sum(r['category']=='ram' and r.get('ram_modules') is None for r in records),'limits':'Collected and classified public listings, not every store in Egypt. Variants and unavailable offers remain in exports. Price floors span brands and speeds; use the detailed groups for comparisons. Missing RAM type, form factor or stick count stays unknown.'}
    write_json(folder/'summary.json',summary)
    registry=json.loads((root/'sources.json').read_text());current={s['source']:s for s in statuses or []};discovery_path=root/'data/source-discovery.json';probes={r['source']:r for r in json.loads(discovery_path.read_text())} if discovery_path.exists() else {}
    coverage=[]
    for source in registry:
        status=current.get(source['id'],{});progress_path=root/'data/harvest-progress'/(source['id']+'.json')
        if progress_path.exists():
            progress=json.loads(progress_path.read_text())
            if progress.get('status')=='running':status={**status,**progress}
        state_path=root/'data/harvest-state'/(source['id']+'.json');state=read(state_path);detail=inventory(state) if state.get('active_urls') else {}
        rows=[r for r in records if r['source']==source['id']]
        gaps=[{'kind':gap_kind(e),'reason':e} for e in status.get('errors',[])]
        if status.get('page_limit_reached'):gaps.append({'kind':'discovery_or_feed_limit','reason':'Configured page/document limit was reached'})
        if detail.get('never_attempted_product_urls',0):gaps.append({'kind':'queued_not_yet_harvested','reason':f"{detail['never_attempted_product_urls']} discovered product URLs have not yet been attempted"})
        if detail.get('failed_or_empty_product_urls',0):gaps.append({'kind':'failed_or_empty_product_pages','reason':f"{detail['failed_or_empty_product_urls']} product URLs failed or yielded no listing; see crawl state"})
        if not status:gaps.append({'kind':'not_yet_collected','reason':'No collection result recorded yet'})
        if status.get('filtered_sitemap_urls') and source.get('harvest_scope','hardware')=='hardware':gaps.append({'kind':'hardware_url_filter','reason':f"{status['filtered_sitemap_urls']} sitemap URLs excluded by the hardware/product URL filters; opaque product slugs may be missed"})
        if not rows and status:gaps.append({'kind':'no_hardware_extracted','reason':'No hardware listing extracted so far; this does not prove the store has none'})
        missing_prices=sum(r['price_egp'] is None for r in rows)
        unknown_stock=sum(r['stock']=='unknown' for r in rows)
        flagged=sum(bool(r['quality_issues']) for r in rows)
        if missing_prices:gaps.append({'kind':'missing_prices','reason':f'{missing_prices} hardware offers have no extracted price'})
        if unknown_stock:gaps.append({'kind':'unknown_stock','reason':f'{unknown_stock} hardware offers have no confirmed stock status'})
        if flagged:gaps.append({'kind':'listing_quality','reason':f'{flagged} hardware offers require verification; see unpriced-or-unverified.csv'})
        if source.get('kind')=='aggregator':gaps.append({'kind':'search_sample','reason':'Configured searches are sampled; prices need primary retailer verification'})
        if status.get('scope')=='laptops':gaps.append({'kind':'previous_scope_laptops','reason':'Latest completed collection retained laptops; broader hardware collection is pending'})
        if not status.get('feed_exhausted') and not detail and status:gaps.append({'kind':'coverage_not_proven','reason':'Previous collection did not record an exhausted feed or complete URL inventory'})
        coverage.append({'source':source['id'],'store':source['name'],'base':source['base'],'adapter':source['adapter'],'status':status.get('status','not_yet_collected'),'last_saved_at':status.get('last_saved_at'),'feed_exhausted':status.get('feed_exhausted',False),'discovery_exhausted':status.get('discovery_exhausted',False),'collected_hardware_offer_rows':len(rows),'eligible_in_stock_hardware_rows':sum(r['alert_eligible'] for r in rows),'missing_price_rows':sum(r['price_egp'] is None for r in rows),'unknown_stock_rows':sum(r['stock']=='unknown' for r in rows),'quality_issue_rows':sum(bool(r['quality_issues']) for r in rows),'scope':status.get('scope'),'comparison_only':source.get('comparison_only',False),**detail,'gaps':gaps,'probe':probes.get(source['id'])})
    deferred=json.loads((root/'coverage.json').read_text()) if (root/'coverage.json').exists() else {}
    value={'generated_at':now(),'sources':coverage,'deferred_and_excluded':deferred,'limits':'Coverage measures configured sources and discovered inventories, not the whole Egyptian market. An accessible homepage is not a harvested catalogue.'}
    write_json(folder/'coverage-and-gaps.json',value)
    write_csv(folder/'coverage-and-gaps.csv',coverage,['source','store','base','adapter','status','last_saved_at','scope','feed_exhausted','discovery_exhausted','collected_hardware_offer_rows','eligible_in_stock_hardware_rows','missing_price_rows','unknown_stock_rows','quality_issue_rows','discovered_product_urls','never_attempted_product_urls','successfully_extracted_product_urls','failed_or_empty_product_urls','comparison_only','gaps'])
    text=['# Egyptian hardware harvest','',f'Generated: {now()}. Hardware collection has no price ceiling; buying alerts use the 70,000 EGP ceiling.','',f"{len(records):,} hardware offer rows across all stock states; {len(eligible):,} eligible in-stock retailer offers. Variants remain separate.",'','## Categories','','| Category | Collected offers | Eligible in-stock offers |','|---|---:|---:|']
    for name,count in sorted(summary['offer_rows_by_category'].items()):text.append(f"| {name} | {count:,} | {summary['eligible_offer_rows_by_category'].get(name,0):,} |")
    text+=['','## RAM prices','','Lowest observed new prices across brands/speeds. A 32GB total may be a kit; check modules in the detailed CSV. Unknown form factors are excluded from these floors.','','| Type | Capacity | Form | EGP | Brand | Store |','|---|---:|---|---:|---|---|']
    for r in floor:
        if r['capacity_gb'] in {8,16,32} and r['ram_type'] in {'DDR3','DDR4','DDR5'} and r['form_factor'] in {'DIMM','SODIMM'}:
            text.append(f"| {r['ram_type']} | {r['capacity_gb']}GB | {r['form_factor']} | {r['min_egp']:,.0f} | {r['brand'] or 'unknown'} | {r['store']} |" if r['min_egp'] is not None else f"| {r['ram_type']} | {r['capacity_gb']}GB | {r['form_factor']} | Unknown | — | No verified matching offer |")
    text+=['','## Coverage and gaps','','| Source | Status | Hardware rows | Remaining discovered URLs | Gaps |','|---|---|---:|---:|---|']
    for r in coverage:text.append(f"| {r['store']} | {r['status']} | {r['collected_hardware_offer_rows']:,} | {r.get('never_attempted_product_urls',0):,} | "+'; '.join(g['reason'].replace('|','/') for g in r['gaps'])+' |')
    text+=['','## Not collected or excluded','',*[f'- **{k}:** {v}' for k,v in deferred.items()],'','## Data limits','',summary['limits'],f"RAM fields missing: capacity {summary['ram_offers_missing_capacity']}, DDR generation {summary['ram_offers_missing_generation']}, form factor {summary['ram_offers_missing_form_factor']}, module count {summary['ram_offers_missing_module_count']}.",'A retailer feed marked in stock is not a final checkout guarantee. Missing benchmarks, warranty type, delivery cost and exact component compatibility stay unknown.']
    (folder/'report.md').write_text('\n'.join(text)+'\n')
    return summary
