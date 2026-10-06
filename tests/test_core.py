import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from egypt_deals.adapters import jsonld, shopify, verify_qarenly, woo
from egypt_deals.alerts import detect, matches, send_pending
from egypt_deals.http import Client, FetchError, Robots
from egypt_deals.metrics import comparisons, cost_to_32
from egypt_deals.model import Listing, money, now, redact
from egypt_deals.storage import Database

ROOT=Path(__file__).resolve().parents[1]
RULES=json.loads((ROOT/'rules.json').read_text())

def listing(title='Lenovo LOQ 15IRX10 i7-14700HX RTX 5060 8GB 16GB RAM 83JE00WVED',price=57500,**kwargs):
    return Listing(store='store',url='https://example.com/product',raw_title=title,price_egp=price,stock='in_stock',verified_at=now(),**kwargs).finish()

def test_arabic_money_and_placeholder():
    assert money('٥٧٬٥٠٠٫٠٠ جنيه')==57500
    assert not listing(price=1).eligible()
    assert not listing(title='Coming soon LOQ 15IRX10').eligible()

def test_wrong_laptop_and_motherboard_do_not_match():
    rule=RULES['thresholds'][0]
    assert matches(listing(),rule)
    assert not matches(listing(title='LOQ 15IRX10 i7-13650HX RTX 5060 8GB laptop'),rule)
    assert not matches(listing(title='LOQ 15IRX10 i7-14700HX RTX 5050 8GB laptop'),rule)
    assert not matches(listing(title='Lenovo Legion 5 15IRX10 i7-14700HX RTX 5060 8GB laptop'),rule)
    assert not matches(listing(title='Gigabyte B760 Gaming DDR5 ATX Motherboard'),RULES['thresholds'][3])

def test_ram_requires_form_and_kit_configuration():
    laptop=listing(title='Kingston 16GB (1×16GB) DDR5 SO-DIMM laptop memory')
    assert matches(laptop,RULES['thresholds'][2])
    assert matches(listing(title='Corsair DDR5 32GB (2x16GB) desktop memory kit'),RULES['thresholds'][3])
    assert not matches(listing(title='Corsair DDR5 32GB (1x32GB) desktop memory'),RULES['thresholds'][3])
    assert not matches(listing(title='Unknown DDR5 32GB memory kit'),RULES['thresholds'][3])
    assert not matches(listing(title='RYZEN 5 7600X + ASUS B650 + 32GB DDR5 memory'),RULES['thresholds'][3])

def test_used_gpu_does_not_match_a_pc_or_8gb_variant():
    assert matches(listing(title='Used RTX 3060 12GB graphics card'),RULES['thresholds'][1])
    assert not matches(listing(title='Used RTX 3060 8GB graphics card'),RULES['thresholds'][1])
    assert not matches(listing(title='Used gaming PC 5600X RTX 3060 12GB'),RULES['thresholds'][1])
    assert matches(listing(title='Used gaming PC 5600X RTX 3060 12GB'),RULES['thresholds'][4])
    fresh=listing(title='RTX 3060 12GB graphics card',condition='new',description='Can be used for gaming and design')
    assert fresh.condition=='new'
    assert not matches(fresh,RULES['thresholds'][1])

def test_freshness_currency_stock_and_aggregator_verification():
    old=(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()
    l=listing(); l.verified_at=old; assert not l.eligible()
    l=listing(); l.stock='unknown'; assert not l.eligible()
    l=listing(); l.currency='AED'; assert not l.eligible()
    l=listing(source_kind='aggregator'); assert not l.eligible()
    l.page_updated_at=now(); assert l.eligible()
    l.page_updated_at=old; assert not l.eligible()
    l=listing(); l.comparison_only=True; assert not l.eligible()

def test_robots_wildcards_anchor_longest_and_repeated_groups():
    rules=Robots('User-agent: *\nDisallow: /api/\nAllow: /api/public/\nDisallow: /*.json$\n\nUser-agent: *\nDisallow: /profile/\nDisallow: /search\n')
    assert not rules.allows('https://example.com/api/private')
    assert rules.allows('https://example.com/api/public/product')
    assert not rules.allows('https://example.com/file.json')
    assert rules.allows('https://example.com/file.json?page=1')
    assert not rules.allows('https://example.com/profile/foo')
    assert not rules.allows('https://example.com/search?q=loq')

def test_cache_preserves_observation_time_and_private_not_saved(tmp_path):
    c=Client(tmp_path,delay=0)
    calls=[]
    def respond(request):
        calls.append(request.url.path)
        return httpx.Response(200,text='User-agent: *\nAllow: /' if request.url.path=='/robots.txt' else 'product')
    c.http.close(); c.http=httpx.Client(transport=httpx.MockTransport(respond))
    first=c.get('https://example.com/product')
    assert c.get('https://example.com/product')[2]==first[2]
    assert calls.count('/product')==1
    c.get('https://example.com/used',private=True)
    assert len(list(tmp_path.glob('*.json')))==1
    c.close()

def test_redirect_checks_destination_robots(tmp_path):
    c=Client(tmp_path,delay=0)
    def respond(request):
        if request.url.path=='/robots.txt': return httpx.Response(200,text='User-agent: *\nDisallow: /private')
        if request.url.path=='/public': return httpx.Response(302,headers={'location':'/private'})
        pytest.fail('Disallowed redirect was fetched')
    c.http.close(); c.http=httpx.Client(transport=httpx.MockTransport(respond))
    with pytest.raises(FetchError,match='disallows'): c.get('https://example.com/public')
    c.close()

def test_feed_units_variants_and_wrong_currency():
    source={'id':'x','name':'x','base':'https://example.com'}
    products=shopify({'products':[{'title':'DDR5 16GB laptop RAM','handle':'ram','variants':[{'id':1,'price':'9500.00','available':True,'sku':'A'},{'id':2,'title':'32GB','price':'19000','available':False,'sku':'B'}]}]},source,now())
    assert len(products)==2
    assert products[0].identity!=products[1].identity
    assert products[0].price_egp==9500
    assert products[1].stock=='out_of_stock'
    ram=woo([{'name':'DDR5 memory 16GB','permalink':'https://example.com/ram','prices':{'currency_minor_unit':2,'price':'950000','currency_code':'EGP'},'is_in_stock':True}],source,now())[0]
    assert ram.price_egp==9500
    html='<script type="application/ld+json">'+json.dumps({'@type':'Product','name':'LOQ 15IRX10 i7-14700HX RTX 5060','offers':{'price':'57500','priceCurrency':'AED','availability':'https://schema.org/InStock'}})+'</script>'
    assert not jsonld(html,source,'https://example.com/item',now())[0].eligible()

def test_numeric_retailer_sku_does_not_stop_product_collection():
    source={'id':'retailer','name':'Retailer','base':'https://example.com','_scope':'catalog'}
    html='<script type="application/ld+json">'+json.dumps({'@type':'Product','name':'Intel Core i5-14400F PC bundle','sku':14400,'offers':{'price':44200,'priceCurrency':'EGP','availability':'https://schema.org/InStock'}})+'</script>'
    items=jsonld(html,source,'https://example.com/product',now())
    assert len(items)==1 and items[0].sku=='14400'
    assert items[0].price_egp==44200 and items[0].eligible()

def test_aggregate_offer_never_inherits_cheapest_alternative_specs():
    source={'id':'q','name':'Qarenly','base':'https://qarenly.com','kind':'aggregator'}
    html='<script type="application/ld+json">'+json.dumps({'@type':'Product','name':'LOQ 15IRX10 i7-14700HX RTX 5060','offers':{'@type':'AggregateOffer','lowPrice':54000,'priceCurrency':'EGP','offers':[{'price':54000,'priceCurrency':'EGP','url':'https://example.com/different-cpu'}]}})+'</script>'
    assert jsonld(html,source,'https://example.com/item',now())==[]

def test_aggregator_verification_fetches_only_main_known_retailer():
    candidate=listing();candidate.url='https://qarenly.com/en/store/product'
    calls=[]
    body='<script type="application/ld+json">'+json.dumps({'@type':'Product','name':candidate.raw_title,'offers':{'price':'57500','priceCurrency':'EGP','availability':'https://schema.org/InStock'}})+'</script>'
    class FakeClient:
        def get(self,url):
            calls.append(url)
            if 'qarenly' in url: return '<a href="https://example.com/product?utm_source=qarenly">Go to site</a><a href="https://other.com/product">Go to site</a>',url,now()
            assert url=='https://example.com/product'
            return body,url,now()
    registry=[{'id':'store','name':'store','base':'https://example.com','adapter':'html'}]
    verified,errors=verify_qarenly([candidate],FakeClient(),registry,1,RULES['thresholds'])
    assert len(verified)==1 and verified[0].eligible()
    assert not errors and len(calls)==2

def test_stale_pending_telegram_alert_is_not_sent(tmp_path,monkeypatch):
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','test-token')
    monkeypatch.setenv('TELEGRAM_CHAT_ID','test-chat')
    monkeypatch.setattr(httpx,'post',lambda *a,**k:pytest.fail('Stale alert must not send'))
    db=Database(tmp_path/'db.sqlite')
    l=listing();db.save([l],{'source':'x'});detect([l],RULES,db)
    l.stock='out_of_stock';db.save([l],{'source':'x'})
    result=send_pending(db)
    assert result['sent']==0 and result['expired']==1 and not db.pending()
    db.close()

def test_used_contact_redaction_and_signs():
    l=listing(title='Used RTX 3060 12GB',source_kind='used',seller='PRIVATE NAME',description='فاتورة ضمان بالكرتونة تعدين mining +20 010 1234 5678 test@example.com')
    assert l.seller is None
    assert 'test@example.com' not in l.description
    assert '1234' not in l.description
    assert 'تعدين' in l.used['warning_signs']
    assert 'فاتورة' in l.used['good_signs']

def test_conflicting_kit_part_number_suppresses_alert():
    l=listing(title='Kingston DDR5 16GB (1x16GB) laptop memory SO-DIMM',sku='KF556S40IBK2-32')
    assert l.quality_issues
    assert not l.eligible()
    assert listing(title='Kingston DDR5 32GB (2x16GB) laptop memory SO-DIMM',sku='KF556S40IBK2-32').eligible()
    joined=listing(title='Kingston DDR5 16GB (1x16GB) laptop memory SO-DIMM',description='Part Number: KF556S40IBK2-32PerformanceSpeed: 5600 MT/s')
    assert joined.quality_issues and not joined.eligible()

def test_history_drop_alert_dedup_and_24h_window(tmp_path):
    db=Database(tmp_path/'db.sqlite')
    status={'source':'x'}
    l=listing(price=60000)
    l.observed_at=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
    db.save([l],status)
    current=listing(price=55200)
    db.save([current],status)
    alerts=detect([current],RULES,db)
    assert {a['rule'] for a in alerts}=={'loq-14700hx-5060','drop-24h'}
    assert all(a['new'] for a in alerts)
    assert not any(a['new'] for a in detect([current],RULES,db))
    assert db.history(current,30)['low_egp']==55200
    old=listing(price=70000);old.url='https://example.com/other';old.observed_at=(datetime.now(timezone.utc)-timedelta(hours=25)).isoformat();db.save([old],status)
    current.url=old.url
    assert db.previous(current) is None
    db.close()

def test_cross_store_only_exact_known_variant():
    a=listing();b=listing();b.store='other';b.price_egp=56000
    assert len(comparisons([a,b]))==1
    b.mpn='83JE0000AX';assert comparisons([a,b])==[]
    b.mpn=a.mpn;b.specs['ram_gb']=32;assert comparisons([a,b])==[]

def test_ram_cost_requires_layout_and_compatibility():
    l=listing();prices={('DDR5','SODIMM',16):9000}
    assert cost_to_32(l,prices) is None
    l.specs.update(ram_gb=16,ram_type='DDR5',ram_slots=2,ram_modules=1,ram_soldered=False,ram_max_gb=32)
    assert cost_to_32(l,prices)==66500
    l.specs['ram_modules']=2;assert cost_to_32(l,prices)==75500
    l.specs['ram_soldered']=True;assert cost_to_32(l,prices) is None
    l.specs['ram_soldered']=False;l.specs['ram_max_gb']=16;assert cost_to_32(l,prices) is None

def test_telegram_missing_credentials_never_sends(tmp_path,monkeypatch):
    monkeypatch.delenv('TELEGRAM_BOT_TOKEN',raising=False)
    monkeypatch.delenv('TELEGRAM_CHAT_ID',raising=False)
    db=Database(tmp_path/'db.sqlite')
    assert send_pending(db)['status']=='credentials_missing'
    db.close()
