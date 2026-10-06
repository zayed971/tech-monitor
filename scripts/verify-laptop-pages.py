"""Recheck the primary product pages for selected laptop candidates."""
import json,re
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from egypt_deals.http import Client,FetchError
from egypt_deals.adapters import product_html
from egypt_deals.model import normalized,now

root=Path(__file__).resolve().parents[1]
rows=json.loads((root/'data/laptops-working.json').read_text())
needles=['acer-nitro-v-i9-rtx5060','laptops-gaming-gigabyte-a16-cvh','gigabyte-gaming-a16-cth-intel','hp-victu-gaming-laptop-intel-core-i5','msi-cyborg-15-black-edition','msi-cyborg-15-max-c2wf','lenovo-loq-15ahp10-ryzen-7-250','lenovo-loq-15irx9-i7-14700hx','lenovo-loq-15-6-gaming-laptop-fhd-amd-ryzen-5','hp-zbook-power-15-g9','dell-precision-3581']
selected=[r for r in rows if any(n in r['url'] for n in needles)]
selected=list({r['url']:r for r in selected}.values())
registry={s['id']:s for s in json.loads((root/'sources.json').read_text())}
groups={}
for row in selected:groups.setdefault(row['source'],[]).append(row)

def work(source_id,candidates):
 client=Client(root/'data/cache'/(source_id+'-laptop-verification'),delay=4,ttl=0); results=[]
 try:
  for row in candidates:
   result={'requested_url':row['url'],'store':row['store'],'feed_title':row['raw_title'],'feed_price_egp':row['price_egp'],'checked_at':now()}
   try:
    body,url,stamp=client.get(row['url']); soup=BeautifulSoup(body,'html.parser')
    header=soup.select_one('h1'); header=normalized(header.get_text()) if header else ''
    parsed=product_html(body,{**registry[source_id],'_scope':'catalog'},url,stamp)
    primary=[l for l in parsed if urlsplit(l.url).path.rstrip('/')==urlsplit(url).path.rstrip('/')]
    exact=[l for l in primary if normalized(l.raw_title).casefold()==header.casefold()]
    primary=exact or primary
    section=soup.select_one('.product__info-container,.product__info-wrapper,.summary')
    prices=[normalized(e.get_text()) for e in section.select('.price')][:3] if section else []
    text=normalized(section.get_text()) if section else ''
    result.update({'observed_at':stamp,'final_url':url,'page_h1':header,'primary_offers':[{'title':l.raw_title,'price_egp':l.price_egp,'stock':l.stock,'mpn':l.mpn,'sku':l.sku,'specs':{k:v for k,v in l.specs.items() if v is not None}} for l in primary],'visible_price_blocks':prices,'main_text_excerpt':text[:3200],'primary_description_excerpt':primary[0].description[:10000] if primary else None,'status':'checked'})
   except FetchError as e:result.update(status='failed',error=str(e))
   results.append(result)
   print(json.dumps({'store':row['store'],'price':row['price_egp'],'page_checked':result['status'],'url':row['url']},ensure_ascii=False),flush=True)
 finally:client.close()
 return results
results=[]
with ThreadPoolExecutor(max_workers=3) as pool:
 for job in as_completed([pool.submit(work,k,v) for k,v in groups.items()]): results+=job.result()
(root/'data/laptop-review/page-verifications.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'verified_candidates':len(results),'output':'data/laptop-review/page-verifications.json'}),flush=True)
