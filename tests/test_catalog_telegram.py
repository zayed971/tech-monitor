import json
import os
from pathlib import Path

from egypt_deals.adapters import collect, shopify, interested, sitemap_targets
from egypt_deals.model import now
from egypt_deals.telegram_setup import load_settings, private_chat_ids
from egypt_deals.import_cost import landed_egp,maximum_delivered_usd
from egypt_deals.model import category,extract_specs

def test_complete_laptops_are_distinct_from_parts_and_accessories():
    machines=[
        'ASUS Vivobook 15 X1504MA Core 5 320 DDR5 8GB 512GB SSD',
        'HP ProBook 4 G1i ULTRA 7 255U 16G 512 SSD 16 inch',
        'HP Victus 16 i7-14650HX 16GB DDR5 512GB SSD RTX 3050 6GB',
        'Lenovo LOQ i5-12450HX 12G DDR5 512 SSD RTX 2050 +WIN 11 +2 YEARS',
        'MSI Thin 15 B13VE i7-13620H 16GB DDR5 RTX 4050',
    ]
    assert all(category(title)=='laptop' for title in machines)
    assert category('Lenovo Legion Pro 34 OLED Gaming Monitor')=='monitor'
    assert category('ASUS TUF Gaming K3 Gen II Keyboard')=='peripheral'
    assert category('Laptop bag for Lenovo ThinkPad')=='accessory'
    assert category('UGREEN wall charger for MacBook Pro')=='accessory'
    assert category('Kingston 16GB DDR5 SO-DIMM Laptop Memory')=='ram'
    assert category('ASUS TUF GeForce RTX 5060 graphics card')=='gpu'
    assert category('Dell Precision 5820 Tower Workstation')=='pc'
    assert category('Dell Precision 3620 Tower PC Xeon E3-1220 V5 8GB DDR4')=='pc'
    assert category('Dell Precision 5810 Workstation Xeon E5-1603 V4 16GB DDR4')=='pc'
    assert category('Dell Precision 3581 Workstation Laptop i7-13800H 16GB DDR5')=='laptop'
    assert category('HP ProBook 4510S Laptop Hinges')=='accessory'
    assert category('Dell Latitude 5400 Laptop Internal Fan')=='accessory'
    assert category('ROG Swift PG27AQN 360Hz')=='other'
    assert category('Cooler Master MasterLiquid 360 ATMOS STEALTH Liquid CPU Cooler')=='cooler'
    assert category('Patriot RAM For Laptop 4GB DDR3 1600MHz')=='ram'
    assert category('Hikvision e100 2.5 ssd 128gb, internal solid state drive disk storage for laptop desktop')=='ssd'
    assert category('Crucial P3 NVMe SSD High-Speed Storage for PC & Laptop')=='ssd'
    assert category('RAM LAPTOP LEXAR 16G 4800HZ')=='ram'
    assert category('Lenovo Legion 24-10 23.8 IPS FHD 240HZ')=='monitor'
    assert category('MSI Modern MD2412P 1920 x 1080 IPS 100Hz')=='monitor'
    assert category('MSI Modern AM242 12M')=='pc'
    assert category('Oral-B Precision Clean Replacement Brush Heads')=='accessory'
    assert category('LENOVO Laptop Casual Toploader T210')=='accessory'
    assert category('USB External Lan Card for PC Laptop Receiver')=='accessory'
    assert interested('https://example.com/en/item?id=acer-nitro-v-15-i7-rtx-5060',{'_scope':'laptops'})
    assert not interested('https://example.com/product/laptop-ram-ddr5-16gb',{'_scope':'laptops'})

def test_laptop_capacity_cpu_and_professional_gpu_extraction():
    specs=extract_specs('Lenovo LOQ i7- 13650HX 16GB 512 SSD RTX 5060 8GB')
    assert specs['cpu_model']=='I7-13650HX' and specs['ram_gb']==16
    assert specs['storage_gb']==512 and specs['gpu_vram_gb']==8
    specs=extract_specs('HP ZBook i7-13850HX 32GB DDR5 M.2 1TB SSD RTX A1000 6GB')
    assert specs['gpu_model']=='RTX A1000' and specs['ram_gb']==32
    assert extract_specs('Lenovo LOQ Ryzen 7 250 16GB RTX 5060 8GB')['cpu_model']=='Ryzen 7 250'
    assert extract_specs('ASUS Vivobook Core 7 240H RAM 16G DDR5')['cpu_model']=='Core 7 240H'
    assert extract_specs('DELL Pro laptop Core Ultra 7 265U RAM 16G')['ram_gb']==16
    assert extract_specs('Gigabyte laptop i7-13620H 16GB RAM M.2 NVMe 1TB RTX 5060 8GB')['storage_gb']==1000
    assert extract_specs('HP laptop i5-13420H 8GB RAM M.2 NVMe 512GB RTX 3050 6GB')['storage_gb']==512

def test_sigma_language_pages_are_one_product_request():
    pages=['https://sigma-computer.com/ar/item?id=lenovo-loq-15irx10',
           'https://sigma-computer.com/en/item?id=lenovo-loq-15irx10',
           'https://sigma-computer.com/en/item?id=acer-nitro-v-15',
           'https://sigma-computer.com/en/item?id=ddr5-laptop-ram']
    selected=sitemap_targets(pages,{'id':'sigma','_scope':'laptops'})
    assert selected==pages[1:3]

def test_retailer_cannot_verify_another_sites_offer():
    from egypt_deals.adapters import jsonld
    source={'id':'store','name':'Store','base':'https://store.example','_scope':'catalog'}
    product={'@type':'Product','name':'Lenovo LOQ 15IRX10 i7-14700HX RTX 5060 16GB RAM','offers':{'@type':'Offer','url':'https://aggregator.example/item','price':65000,'priceCurrency':'EGP','availability':'https://schema.org/InStock'}}
    html='<script type="application/ld+json">'+json.dumps(product)+'</script>'
    result=jsonld(html,source,'https://store.example/product',now())[0]
    assert result.quality_issues and not result.eligible()

def test_price_drop_watch_includes_other_under_budget_laptops(tmp_path):
    from datetime import datetime,timedelta,timezone
    from egypt_deals.model import Listing
    from egypt_deals.storage import Database
    from egypt_deals.alerts import detect
    previous=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()
    title='HP Victus laptop i5-13420H RTX 4050 6GB 16GB RAM'
    old=Listing('store','https://example.com/victus',title,59000,stock='in_stock',observed_at=previous,verified_at=previous).finish()
    current=Listing('store','https://example.com/victus',title,53000,stock='in_stock',verified_at=now()).finish()
    rules={'thresholds':[],'laptop_watch':{'max_egp':70000},'drop':{'id':'drop-24h','hours':24,'min_pct':8}}
    db=Database(tmp_path/'deals.sqlite3')
    try:
        db.save([old],{'source':'store'});db.save([current],{'source':'store'})
        alerts=detect([current],rules,db)
        assert len(alerts)==1 and alerts[0]['rule']=='drop-24h'
    finally:db.close()

def test_catalog_scope_keeps_non_target_real_products():
    p={'id':1,'title':'Logitech wireless keyboard','handle':'keyboard','variants':[{'id':11,'price':'2000','available':True}]}
    source={'id':'store','name':'store','base':'https://example.com'}
    assert shopify({'products':[p]},source,now())==[]
    assert len(shopify({'products':[p]},{**source,'_scope':'catalog'},now()))==1

def test_repeating_catalog_page_cannot_pad_counts():
    products=[{'id':n,'title':f'Keyboard {n}','handle':f'keyboard-{n}','variants':[{'id':n,'price':'2000','available':True}]} for n in range(250)]
    class FakeClient:
        requests=0
        def get(self,url,private=False): return json.dumps({'products':products}),url,now()
    source={'id':'store','name':'store','base':'https://example.com','adapter':'shopify'}
    listings,status=collect(source,FakeClient(),max_pages=3,scope='catalog')
    assert len(listings)==250 and status['pages']==2
    assert status['status']=='partial' and 'repeated' in status['errors'][0]

def test_telegram_only_discovers_private_chat_ids():
    updates=[{'message':{'chat':{'id':10,'type':'private','first_name':'never saved'},'text':'private text'}},
             {'message':{'chat':{'id':-20,'type':'group'},'text':'group text'}},
             {'message':{'chat':{'id':10,'type':'private'}}}]
    assert private_chat_ids(updates)==['10']

def test_env_loader_parses_data_without_executing_shell(tmp_path,monkeypatch):
    monkeypatch.delenv('TELEGRAM_BOT_TOKEN',raising=False)
    monkeypatch.delenv('TELEGRAM_CHAT_ID',raising=False)
    (tmp_path/'.env').write_text("TELEGRAM_BOT_TOKEN='$(touch /tmp/should-never-execute)'\nTELEGRAM_CHAT_ID='123'\nUNRELATED=ignore\n")
    load_settings(tmp_path)
    assert os.environ['TELEGRAM_BOT_TOKEN']=='$(touch /tmp/should-never-execute)'
    assert os.environ['TELEGRAM_CHAT_ID']=='123'

def test_import_total_requires_shipping_and_taxes():
    assert landed_egp(100,None,None,50) is None
    assert landed_egp(100,20,15,50,card_fee_pct=3)==6952.5
    assert maximum_delivered_usd(10000,50,card_fee_pct=3,saving_pct=10)==174.76

def test_idle_scheduler_preserves_collected_snapshot_and_notifies(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from egypt_deals import cli
    from egypt_deals.storage import Database
    (tmp_path/'sources.json').write_text(json.dumps([{'id':'store','interval_hours':24}]))
    (tmp_path/'rules.json').write_text(json.dumps({'thresholds':[]}))
    data=tmp_path/'data'; data.mkdir()
    paths=[data/'run-manifest.json',data/'fresh-listings.json',data/'report.md']
    for path in paths: path.write_text('preserve last successful collection')
    db=Database(data/'deals.sqlite3')
    try:
        db.save([],{'source':'store'})
        notified=[]
        monkeypatch.setattr(cli,'send_pending',lambda database:notified.append(database) or {'sent':2})
        cli.run(SimpleNamespace(sources=None,due=True,send=True),db,tmp_path)
        assert notified==[db]
        assert all(path.read_text()=='preserve last successful collection' for path in paths)
    finally: db.close()

def test_start_message_connects_and_enters_bounded_monitor(tmp_path,monkeypatch,capsys):
    import runpy
    import pytest
    from egypt_deals import telegram_setup
    calls=[]
    def fake_api(token,method,payload=None):
        calls.append((method,payload))
        if method=='getMe': return {'username':'fixture_bot'}
        if method=='getUpdates': return [{'message':{'chat':{'id':123,'type':'private'},'text':'/start'}}]
        if method=='sendMessage': return {'message_id':1}
        raise AssertionError(method)
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','test-token')
    monkeypatch.delenv('TELEGRAM_CHAT_ID',raising=False)
    monkeypatch.setattr(telegram_setup,'api',fake_api)
    script=Path(__file__).resolve().parents[1]/'scripts/connect-and-watch.py'
    main=runpy.run_path(str(script))['main']
    main.__globals__['__file__']=str(tmp_path/'scripts/connect-and-watch.py')
    launched=[]
    def replace_process(executable,arguments):
        launched.append(arguments)
        raise SystemExit(0)
    monkeypatch.setattr(os,'execv',replace_process)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit): main()
    status=json.loads((tmp_path/'data/telegram-status.json').read_text())
    assert status['status']=='connected' and status['test_sent']
    assert sum(method=='sendMessage' for method,_ in calls)==1
    assert 'watch' in launched[0] and '--send' in launched[0]
    assert (tmp_path/'data/watch.json').exists()
    if os.name!='nt':  # Windows ignores POSIX chmod bits, so 0600 cannot be checked there
        assert (tmp_path/'.env').stat().st_mode & 0o777==0o600
    output=capsys.readouterr().out
    assert 'test-token' not in output and '/start' not in output
