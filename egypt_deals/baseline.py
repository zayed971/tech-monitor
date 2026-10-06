import json
from datetime import datetime, timezone

from .http import Client, FetchError
from .model import date_value

def update_fx(root):
    url='https://open.er-api.com/v6/latest/USD'
    c=Client(root/'data'/'cache'/'fx',delay=4,ttl=86400)
    try:
        body,final,observed=c.get(url)
        data=json.loads(body)
        rate=data.get('rates',{}).get('EGP')
        timestamp=data.get('time_last_update_unix')
        if data.get('result')!='success' or not isinstance(rate,(int,float)) or rate<=0 or not isinstance(timestamp,int):
            raise FetchError('exchange provider returned invalid data')
        checked=datetime.fromtimestamp(timestamp,timezone.utc)
        if not 0 <= (datetime.now(timezone.utc)-checked).total_seconds() <= 7*86400:
            raise FetchError('exchange-provider quote is stale or future-dated')
        path=root/'references.json'
        refs=json.loads(path.read_text())
        refs['fx']={'usd_egp':rate,'source_url':final,'checked_at':checked.isoformat(),'observed_at':observed,'provider':'ExchangeRate-API open access'}
        temp=path.with_suffix('.json.tmp');temp.write_text(json.dumps(refs,ensure_ascii=False,indent=2));temp.replace(path)
        return refs['fx']
    finally:c.close()
