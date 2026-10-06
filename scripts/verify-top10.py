"""Read selected public product pages/variant JSON without altering the monitor."""
import json
import argparse
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,urlunsplit
from concurrent.futures import ThreadPoolExecutor
from egypt_deals.http import Client,FetchError
from egypt_deals.adapters import shopify,product_html

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--source');args=parser.parse_args()
selected=json.loads((root/'data/top10-selected.json').read_text())
registry={s['id']:s for s in json.loads((root/'sources.json').read_text())}
groups={}
for row in selected:
 if not args.source or row['source']==args.source:groups.setdefault(row['source'],[]).append(row)

def verify(group):
 source_id,rows=group;source={**registry[source_id],'_scope':'catalog'}
 client=Client(root/'data/cache/top10-verification'/source_id,delay=4,ttl=0);results=[]
 try:
  for row in rows:
   record={'id':row['id'],'store':row['store'],'title':row['raw_title'],'url':row['url'],'collected_price_egp':row['price_egp'],'collected_stock':row['stock'],'collected_at':row['observed_at']}
   try:
    request=row['url']
    if source['adapter']=='shopify':
     parts=urlsplit(request);request=urlunsplit((parts.scheme,parts.netloc,parts.path+'.json','',''))
     body,final,stamp=client.get(request);data=json.loads(body)
     parsed=shopify({'products':[data['product']]},source,stamp)
     variant=parse_qs(parts.query).get('variant',[None])[0]
     matched=[item for item in parsed if parse_qs(urlsplit(item.url).query).get('variant',[None])[0]==variant]
    else:
     body,final,stamp=client.get(request);parsed=product_html(body,source,final,stamp)
     matched=[item for item in parsed if item.price_egp==row['price_egp']] or parsed[:1]
    record.update(checked_at=stamp,requested_url=request)
    if matched:
     item=matched[0];record.update(status='price_and_stock_confirmed' if item.price_egp==row['price_egp'] and item.stock=='in_stock' else 'changed_or_stock_unconfirmed',page_title=item.raw_title,page_price_egp=item.price_egp,page_stock=item.stock,page_quality_issues=item.quality_issues)
     if source['adapter']=='shopify' and item.stock=='unknown':
      # Shopify's product JSON can omit availability. Its documented public
      # Ajax product endpoint includes it; prices there are in minor units.
      request=urlunsplit((parts.scheme,parts.netloc,parts.path+'.js','',''))
      body,final,stamp=client.get(request);ajax=json.loads(body)
      current=next(v for v in ajax['variants'] if str(v['id'])==variant)
      price=float(current['price'])/100;available=current.get('available')
      state='in_stock' if available is True else 'out_of_stock' if available is False else 'unknown'
      record.update(checked_at=stamp,requested_url=request,page_price_egp=price,page_stock=state,status='price_and_stock_confirmed' if price==row['price_egp'] and state=='in_stock' else 'changed_or_stock_unconfirmed')
    else:record.update(status='no_primary_listing_extracted')
   except (FetchError,ValueError,KeyError,TypeError) as error:record.update(status='verification_failed',reason=str(error))
   results.append(record);print(json.dumps({k:record.get(k) for k in ['id','store','status','page_price_egp','page_stock','reason']}),flush=True)
 finally:client.close()
 return results

with ThreadPoolExecutor(max_workers=4) as pool:results=[item for group in pool.map(verify,groups.items()) for item in group]
if args.source:
 previous=json.loads((root/'data/top10-page-verifications.json').read_text())
 changed={r['id'] for r in results};results=[r for r in previous if r['id'] not in changed]+results
(root/'data/top10-page-verifications.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
