import json
from datetime import datetime,timedelta,timezone
from pathlib import Path

from egypt_deals.adapters import collect,shopify
from egypt_deals.catalog_report import export_hardware
from egypt_deals.crawl_state import plan,observe,write,inventory
from egypt_deals.model import category,extract_specs,Listing,now
from egypt_deals.storage import Database
from egypt_deals.alerts import detect


def test_components_do_not_become_pcs_or_ram_from_compatibility_words():
    assert category('DEEPCOOL PF650 650 Watt 80 Plus Power Supply for Gaming PC')=='psu'
    assert category('Havit CF923 RGB Gaming PC Case Mid Tower')=='case'
    assert category('ASUS GT 1030 Graphics Card 2GB DDR4')=='gpu'
    assert category('Crucial P3 1TB NVMe SSD with DRAM cache')=='ssd'
    assert category('Seagate 1TB Internal Laptop Hard Drive')=='hdd'
    assert category('Core i5-14600K + ASUS PRIME B760M-K + RTX 4060 Ti Bundle')=='bundle'
    assert category('Samsung Galaxy A07 8GB RAM 256GB')=='other'
    assert category('Lenovo LOQ i7-14700HX 16GB SODIMM DDR5 RAM RTX 5060 Laptop')=='laptop'
    assert category('GIGABYTE B760M DS3H WIFI6E DDR4 GEN5')=='motherboard'
    assert category('MSI GT 730 4GB DDR3')=='gpu'
    assert category('Bundle | MSI B840 GAMING PLUS WIFI | 16GB DDR5 5600MHz')=='bundle'
    assert category('HUAWEI Mate 50 Pro 8GB RAM 512GB')=='other'


def test_ram_capacity_generation_kit_and_server_memory_are_distinct():
    specs=extract_specs('RAM LAPTOP LEXAR 16G DDR5 4800HZ')
    assert (specs['ram_gb'],specs['ram_type'],specs['ram_form_factor'],specs['ram_speed_mt_s'])==(16,'DDR5','SODIMM',4800)
    kit=extract_specs('Corsair DDR4 Desktop 32GB (2x16GB) 3200MHz CL16')
    assert kit['ram_gb']==32 and kit['ram_modules']==2 and kit['ram_module_gb']==16
    server=extract_specs('Samsung 32GB DDR4 ECC Registered RDIMM 3200MHz')
    assert server['ram_form_factor']=='RDIMM' and server['ram_ecc'] and server['ram_registered']
    assert extract_specs('Kingston 8GB DDR3 SO-DIMM')['ram_type']=='DDR3'
    assert extract_specs('Kingston 2GB DDR2 Desktop RAM')['ram_type']=='DDR2'


def test_variant_storage_capacity_does_not_take_first_parent_size():
    source={'id':'s','name':'Store','base':'https://example.com','_scope':'catalog'}
    rows=shopify({'products':[{'title':'HIKSEMI SSD 128GB / 256GB / 512GB / 1TB','handle':'ssd','variants':[{'id':1,'title':'128GB','price':1000,'available':True},{'id':2,'title':'1TB','price':7000,'available':True}]}]},source,now())
    assert [r.specs['storage_gb'] for r in rows]==[128,1000]


def test_url_queue_rotates_and_exposes_failures(tmp_path):
    source={'_crawl_state_path':str(tmp_path/'state.json')}
    first,state=plan(['a','b','c'],source,2)
    observe(state,'a',now(),1);observe(state,'b',None,0,'HTTP 404');write(source['_crawl_state_path'],state)
    second,state=plan(['a','b','c'],source,1)
    assert second==['c']
    assert inventory(state)['never_attempted_product_urls']==1
    assert inventory(state)['failed_or_empty_product_urls']==1


def test_sitemap_index_reports_backlog_and_ignores_image_locations(tmp_path):
    class Fake:
        requests=0
        def get(self,url,private=False):
            self.requests+=1
            if url.endswith('sitemap.xml'):return '<sitemapindex><sitemap><loc>https://example.com/products.xml</loc></sitemap></sitemapindex>',url,now()
            if url.endswith('products.xml'):return '<urlset xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"><url><loc>https://example.com/product/ram-a</loc><image:image><image:loc>https://example.com/a.jpg</image:loc></image:image></url><url><loc>https://example.com/product/ram-b</loc></url></urlset>',url,now()
            html='<script type="application/ld+json">'+json.dumps({'@type':'Product','name':'Kingston 16GB DDR4 Desktop RAM','offers':{'price':5000,'priceCurrency':'EGP','availability':'https://schema.org/InStock'}})+'</script>'
            return html,url,now()
    source={'id':'s','name':'Store','base':'https://example.com','adapter':'sitemap','sitemap':'/sitemap.xml','_crawl_state_path':str(tmp_path/'state.json')}
    rows,status=collect(source,Fake(),max_pages=4,max_details=1,scope='catalog')
    assert len(rows)==1 and status['discovered_product_urls']==2
    assert status['never_attempted_product_urls']==1 and status['detail_limit_reached']
    assert status['discovery_exhausted'] and status['sitemap_documents']==2


def test_ram_export_keeps_unknowns_and_server_memory_out_of_desktop_floor(tmp_path):
    (tmp_path/'sources.json').write_text(json.dumps([{'id':'s','name':'Store','base':'https://example.com','adapter':'shopify'}]));(tmp_path/'data').mkdir()
    specs={'store':'Store','source':'s','price_egp':2000,'stock':'in_stock','condition':'new','verified_at':now()}
    server=Listing(url='https://example.com/server',raw_title='Samsung 32GB DDR4 ECC RDIMM',**specs).finish()
    unknown=Listing(url='https://example.com/unknown',raw_title='Memory module DDR4',**specs).finish()
    desktop=Listing(url='https://example.com/desktop',raw_title='Corsair 32GB (2x16GB) DDR4 3200MHz Desktop Memory',**{**specs,'price_egp':11000}).finish()
    summary=export_hardware([server,unknown,desktop],tmp_path)
    assert summary['hardware_offer_rows_all_stock_states']==3 and summary['ram_offers_missing_capacity']==1
    import csv
    rows=list(csv.DictReader((tmp_path/'data/hardware/ram-capacity-overview.csv').open()))
    floor=next(r for r in rows if r['ram_type']=='DDR4' and r['capacity_gb']=='32' and r['form_factor']=='DIMM')
    assert float(floor['min_egp'])==11000


def test_backlog_scheduled_soon_but_blocked_source_keeps_interval(tmp_path):
    db=Database(tmp_path/'data.db');old=(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
    source={'id':'s','interval_hours':24}
    status={'source':'s','status':'partial','started_at':old,'errors':[],'discovered_product_urls':1000,'never_attempted_product_urls':500,'detail_limit':100}
    db.save([],status);assert db.due(source)
    db.save([],{**status,'status':'blocked_or_failed','errors':['HTTP 403']});assert not db.due(source)
    assert db.due({**source,'revision':1})
    db.save([],{**status,'status':'ok'});assert not db.due({**source,'rotate_inventory':False})
    db.close()


def test_desktop_component_price_drops_are_monitored(tmp_path):
    db=Database(tmp_path/'data.db');current=datetime.now(timezone.utc)
    before=Listing(store='Store',source='s',url='https://example.com/cpu',raw_title='AMD Ryzen 5 5600 CPU',price_egp=6000,stock='in_stock',verified_at=(current-timedelta(hours=2)).isoformat(),observed_at=(current-timedelta(hours=2)).isoformat()).finish()
    after=Listing(store='Store',source='s',url=before.url,raw_title=before.raw_title,price_egp=5400,stock='in_stock',verified_at=current.isoformat(),observed_at=current.isoformat()).finish()
    db.save([before,after],{'source':'s'})
    rules={'thresholds':[],'drop':{'id':'drop','hours':24,'min_pct':8},'hardware_watch':{'categories':['cpu'],'max_egp':70000}}
    assert detect([after],rules,db)[0]['rule']=='drop'
    db.close()


def test_build_only_component_price_cannot_be_a_standalone_deal():
    offer=Listing(store='Store',url='https://example.com/ram',raw_title='Corsair 16GB DDR4 Desktop RAM — داخل تجميعه فقط',price_egp=4000,stock='in_stock',verified_at=now()).finish()
    assert offer.category=='ram' and not offer.eligible()
    assert any('standalone price' in reason for reason in offer.quality_issues)
    pc=Listing(store='Store',url='https://example.com/pc',raw_title='Gaming PC Ryzen 5 5600 RTX 5060',price_egp=40000,stock='in_stock',verified_at=now()).finish()
    assert pc.eligible()


def test_ram_variant_conflict_accepts_g_abbreviation_and_multisize_parents():
    base={'store':'Store','url':'https://example.com/ram','price_egp':6500,'stock':'in_stock','verified_at':now()}
    wrong=Listing(raw_title='RAM LAP CRUCIAL 16G DDR5 — 32GB',parent_title='RAM LAP CRUCIAL 16G DDR5',variant_title='32GB',**base).finish()
    assert not wrong.eligible() and wrong.quality_issues
    valid=Listing(raw_title='Crucial DDR5 16GB / 32GB Laptop Memory — 32GB',parent_title='Crucial DDR5 16GB / 32GB Laptop Memory',variant_title='32GB',**base).finish()
    assert valid.eligible() and valid.specs['ram_gb']==32


def test_marketplace_product_discovery_excludes_login_links():
    from egypt_deals.adapters import links
    html='<article class="prd"><a href="/customer/account/login/">Wishlist</a><a href="/acer-laptop-12345678.html">Acer Laptop</a></article>'
    source={'product_url_regex':r'-\d{6,}\.html(?:\?|$)'}
    assert links(html,'https://example.com/','hardware',source)==['https://example.com/acer-laptop-12345678.html']


def test_geek_gear_and_accessories_keep_component_compatibility_separate():
    expected={'UGREEN NVMe SSD Enclosure':'accessory','Wacom Intuos Drawing Tablet':'creator','Elgato Stream Deck':'creator','Raspberry Pi 5 Development Board':'maker','Meta Quest 3 VR Headset':'gaming','Valve Steam Deck 512GB':'gaming','TP-Link Smart Plug':'smart_home','Apple Watch Series 10 Smartwatch':'wearable','Amazon Kindle Paperwhite':'ereader','Anker USB-C GaN Charger':'accessory','Logitech Wireless Mouse':'peripheral','Samsung 1TB NVMe SSD for PS5':'ssd','ASUS B760M Motherboard with Headphone Amplifier':'motherboard','Lenovo LOQ i7-14700HX Laptop with Webcam':'laptop'}
    for title,kind in expected.items():assert category(title)==kind,title
    offer=Listing(store='Store',url='https://example.com/arm',raw_title='VESA Monitor Arm',price_egp=1200,stock='in_stock',verified_at=now()).finish()
    assert offer.accessory_type=='monitor_arm' and offer.eligible()
    assert category('KLEVV 16GB DDR4 Gaming Desktop RAM')=='ram'
    assert category('ASUS TUF A14 Gaming Laptop Ryzen AI 9 HX 370 16GB RAM with Backpack')=='laptop'
    assert category('Lenovo ThinkPad P50 Xeon E3-1505M Workstation Laptop English Keyboard')=='laptop'
    assert category('Intel Core i5-14400F + ASUS B760M Motherboard + RTX 5060 Bundle')=='bundle'
