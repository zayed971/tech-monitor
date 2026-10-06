"""Resume a public product URL inventory without revisiting the first batch."""
import json
from pathlib import Path
from .model import now

def read(path):
    if not path:return {'urls':{}}
    path=Path(path)
    return json.loads(path.read_text()) if path.exists() else {'urls':{}}

def write(path,state):
    if not path:return
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.json.tmp');temp.write_text(json.dumps(state,ensure_ascii=False));temp.replace(path)

def plan(urls,source,limit):
    state=read(source.get('_crawl_state_path'))
    known=source.get('_known_products',{})
    for url in urls:
        item=state['urls'].setdefault(url,{})
        if not item and url in known:item.update(last_success_at=known[url],last_attempt_at=known[url])
    # Failed pages also move to the back, allowing collection to progress.
    chosen=sorted(urls,key=lambda url:(bool(state['urls'][url].get('last_attempt_at')),state['urls'][url].get('last_attempt_at','')))[:limit]
    state.update(discovered_at=now(),discovered_urls=len(urls),active_urls=urls)
    write(source.get('_crawl_state_path'),state)
    return chosen,state

def observe(state,url,stamp,count,error=None):
    item=state['urls'].setdefault(url,{})
    item.update(last_attempt_at=now(),extracted_rows=count)
    if error:item['error']=error
    elif count:item.update(last_success_at=stamp,error=None)
    else:item['error']='No product listing extracted from this page'

def inventory(state):
    active=[state['urls'][url] for url in state.get('active_urls',[])]
    return {'discovered_product_urls':len(active),
            'never_attempted_product_urls':sum(not item.get('last_attempt_at') for item in active),
            'successfully_extracted_product_urls':sum(bool(item.get('last_success_at')) for item in active),
            'failed_or_empty_product_urls':sum(bool(item.get('error')) for item in active)}
