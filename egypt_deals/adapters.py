import json
import re
from datetime import timedelta
from urllib.parse import quote, urljoin, urlsplit,unquote
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

from .http import FetchError
from .model import Listing, category, date_value, money, normalized,now

def clean(html):
    s = BeautifulSoup(str(html or ""), "html.parser")
    for tag in s.select("script, style, noscript"): tag.decompose()
    return s.get_text(" ", strip=True)

def wanted(title):
    return bool(re.search(r"15irx10|\b3060\b|ddr[\s-]*5|5600x", normalized(title), re.I))

def interested(title, source):
    if source.get('_scope')=='hardware':
        from .hardware import HARDWARE_CATEGORIES
        return category(normalized(unquote(title)).replace('-',' ')) in HARDWARE_CATEGORIES
    if source.get('_scope')=='laptops':
        return category(normalized(title).replace('-',' '))=='laptop'
    return source.get('_scope') == 'catalog' or wanted(title)

def stock(value):
    text = re.sub(r"[\s_-]+", "", normalized(value).lower())
    if "outofstock" in text or "soldout" in text: return "out_of_stock"
    if any(word in text for word in ["غيرمتوفر", "غيرمتاح", "نفذ", "نفدت"]): return "out_of_stock"
    if "instock" in text or "limitedavailability" in text: return "in_stock"
    if text in {"متوفر", "متاح"}: return "in_stock"
    if "preorder" in text or "backorder" in text: return "preorder"
    return "unknown"

def schema_type(value, expected):
    values = value if isinstance(value, list) else [value]
    return any(isinstance(v, str) and v.rstrip('/').rsplit('/', 1)[-1].rsplit('#', 1)[-1] == expected for v in values)

def shopify(data, source, observed):
    output = []
    for p in data.get("products", []):
        if not interested(p.get("title", ""), source): continue
        description = clean(p.get("body_html"))
        for v in p.get("variants", []):
            suffix = "" if v.get("title") in {None, "Default Title"} else " — " + v["title"]
            item=Listing(
                store=source["name"], source=source["id"], url=source["base"] + "/products/" + p["handle"] + "?variant=" + str(v["id"]),
                raw_title=p["title"] + suffix, price_egp=money(v.get("price")), old_price_egp=money(v.get("compare_at_price")),
                stock="in_stock" if v.get("available") is True else "out_of_stock" if v.get("available") is False else "unknown",
                observed_at=observed, verified_at=observed, page_updated_at=p.get("updated_at"),
                brand=p.get("vendor"), sku=v.get("sku"), images=[i["src"] for i in p.get("images", []) if "src" in i],
                description=description, condition="new",
                parent_title=p['title'],variant_title=v.get('title') if suffix else None,
            ).finish()
            output.append(item)
    return output

def woo(data, source, observed):
    output = []
    for p in data:
        if not interested(p.get("name", ""), source): continue
        prices = p.get("prices", {})
        scale = 10 ** int(prices.get("currency_minor_unit", 2))
        convert = lambda value: money(value)/scale if money(value) is not None else None
        output.append(Listing(
            store=source["name"], source=source["id"], url=p["permalink"], raw_title=clean(p["name"]),
            price_egp=convert(prices.get("price")), old_price_egp=convert(prices.get("regular_price")),
            currency=prices.get("currency_code", "unknown"), sku=p.get("sku"),
            stock="in_stock" if p.get("is_in_stock") is True else "out_of_stock" if p.get("is_in_stock") is False else "unknown",
            observed_at=observed, verified_at=observed, condition="new", images=[i.get("src") for i in p.get("images", [])],
            description=clean(p.get("description", "") + " " + p.get("short_description", "")),
        ).finish())
    return output

def nodes(value):
    if isinstance(value, dict):
        yield value
        for v in value.values(): yield from nodes(v)
    elif isinstance(value, list):
        for v in value: yield from nodes(v)

def jsonld(html, source, url, observed):
    soup = BeautifulSoup(html, "html.parser")
    output = []
    for tag in soup.select('script[type="application/ld+json"]'):
        try: data = json.loads(tag.get_text())
        except (ValueError, TypeError): continue
        for p in nodes(data):
            if not schema_type(p.get("@type"), "Product") or not p.get("name"): continue
            if not interested(p["name"], source): continue
            offers = p.get("offers") or {}
            if isinstance(offers, dict): offers = [offers]
            if not isinstance(offers, list): continue
            for o in offers:
                if not isinstance(o, dict): continue
                if schema_type(o.get('@type'), 'AggregateOffer'): continue
                # AggregateOffer has a low price, not an individual listing that can be bought.
                price = money(o.get("price", o.get("lowPrice")))
                seller = o.get("seller", {})
                seller = seller.get("name") if isinstance(seller, dict) else str(seller)
                brand = p.get("brand", {})
                brand = brand.get("name") if isinstance(brand, dict) else str(brand)
                images = p.get("image", [])
                if isinstance(images, str): images = [images]
                used = source.get("kind") == "used"
                listing = Listing(
                    store=(seller or source["name"]) if source.get('kind')=='aggregator' else source['name'], source=source["id"], source_kind=source.get("kind", "retailer"),
                    url=urljoin(url, o.get("url") or p.get("url") or url), raw_title=p["name"], price_egp=price,
                    currency=o.get("priceCurrency", "unknown"), stock=stock(o.get("availability")),
                    observed_at=observed, verified_at=observed if source.get("kind") != "aggregator" else None,
                    page_updated_at=p.get("dateModified"), mpn=p.get("mpn"), sku=p.get("sku"), brand=brand,
                    seller=None if used else seller, images=images, description=clean(p.get("description", "")),
                    condition='used' if 'usedcondition' in str(o.get('itemCondition','')).lower() else 'refurbished' if 'refurbishedcondition' in str(o.get('itemCondition','')).lower() else "new" if "newcondition" in str(o.get("itemCondition", "")).lower() else "unknown",
                    comparison_only=source.get("comparison_only", False),
                ).finish()
                if listing.source_kind=='retailer':
                    actual=urlsplit(listing.url).hostname
                    observed_host=urlsplit(url).hostname
                    if actual and observed_host and actual.removeprefix('www.')!=observed_host.removeprefix('www.'):
                        listing.quality_issues.append('Structured-data offer points to another site; retailer price needs primary-page verification')
                if used:
                    listing.store = source["name"]
                    listing.used.update(date_posted=p.get("datePosted"), photo_count=len(images), negotiable=None, area=None, seller_type=None)
                output.append(listing)
    return output

def qarenly(html, source, url, observed):
    result = jsonld(html, source, url, observed)
    soup = BeautifulSoup(html, "html.parser")
    by_url = {p.url: p for p in result}
    for card in soup.select("article"):
        link = card.select_one('a[href^="/en/"][aria-hidden="true"]')
        title, price = card.select_one("h2"), None
        if not link or not title or not interested(title.get_text(), source): continue
        for p in card.select("p"):
            if "EGP" in p.get_text(): price = money(p.get_text()); break
        target = urljoin(url, link["href"])
        listing = by_url.get(target)
        if listing is None:
            listing = Listing(store=target.split("/")[4], source=source["id"], source_kind="aggregator", url=target,
                              raw_title=title.get_text(), price_egp=price, observed_at=observed).finish()
            result.append(listing)
        stamp = card.select_one('[title^="Last seen:"]')
        if stamp:
            relative = normalized(stamp.get("title"))
            m = re.search(r"(\d+)\s*(minute|hour|day|week)s? ago", relative)
            if m:
                listing.page_updated_at = (date_value(observed) - timedelta(seconds=int(m.group(1))*{"minute":60,"hour":3600,"day":86400,"week":604800}[m.group(2)])).isoformat()
    return result

def egprices(html, source, url, observed):
    result = jsonld(html, source, url, observed)
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.select('script[type="application/json"]'):
        try:
            payload = json.loads(script.get_text())
            payload = json.loads(payload["body"]) if "body" in payload else payload
        except (ValueError, TypeError, KeyError): continue
        for p in nodes(payload):
            if "prod_name" not in p or not interested(p["prod_name"], source): continue
            # Some category payloads expose products but load their prices
            # separately. Keep their metadata and report the missing price.
            for price in p.get("prices") or [{}]:
                retailer = price.get("store", {}).get("store_name", source["name"])
                result.append(Listing(store=retailer, source=source["id"], source_kind="aggregator",
                    url=urljoin(url, "/en/product/" + p["prod_url"]), raw_title=p["prod_name"],brand=(p.get('brand') or {}).get('brand_name'),
                    price_egp=money(price.get("price_value")), observed_at=observed,
                    page_updated_at=price.get("updated_at"), stock="unknown").finish())
    return result

def product_html(html, source, url, observed):
    result = jsonld(html, source, url, observed)
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one('h1.product_title, h1.product-title, h1[itemprop="name"]') or soup.select_one("h1")
    # Product controls must belong to the main product, never a recommended
    # item's card elsewhere on the page. CS-Cart uses ty-product-block.
    root = None
    if title:
        root = next((p for p in title.parents if any(c in p.get('class', []) for c in ['ty-product-block', 'product-detail', 'product-details', 'single-product', 'product-info-main'])), None)
    root = root or soup
    stock_elements = root.select('.product-stock, .stock, .ty-qty-in-stock, .ty-qty-out-of-stock, [itemprop="availability"]')
    stock_elements = [t for t in stock_elements if not t.find_parent(class_=re.compile(r'(?:product-thumb|product-card|product-item|product-grid-item|product-small|product-miniature|ty-product-list|related|recommend|upsell)'))]
    signals = {stock(t.get("content") or t.get("href") or t.get_text()) for t in stock_elements} - {'unknown'}
    availability = 'out_of_stock' if 'out_of_stock' in signals else 'preorder' if 'preorder' in signals else 'in_stock' if signals == {'in_stock'} else 'unknown'
    if result:
        # Visible negative stock takes precedence over stale structured data.
        for item in result:
            if availability in {'out_of_stock', 'preorder'}:
                item.stock = availability
            elif item.stock == 'unknown':
                item.stock = availability
        return result
    if source.get('id') == 'amazon-eg' and soup.select_one('#productTitle'):
        # Amazon product pages carry no JSON-LD: read the visible buy-box price and availability.
        amazon_title = soup.select_one('#productTitle').get_text(' ', strip=True)
        amazon_price = soup.select_one('#corePrice_feature_div .a-offscreen, #corePriceDisplay_desktop_feature_div .a-offscreen')
        amount = money(amazon_price.get_text()) if amazon_price else None
        note = soup.select_one('#availability')
        note_text = normalized(note.get_text(' ', strip=True)).lower() if note else ''
        amazon_stock = 'out_of_stock' if 'unavailable' in note_text else stock(note_text)
        if amount is None or not interested(amazon_title, source): return []
        return [Listing(store=source["name"], source=source["id"], url=url, raw_title=amazon_title,
            price_egp=amount, stock=amazon_stock, observed_at=observed, verified_at=observed,
            condition="new", comparison_only=source.get("comparison_only", False)).finish()]
    price = root.select_one('[itemprop="price"], .product-price-new, .product-price, .price-new, .ty-price-num')
    if not title or not price or not interested(title.get_text(), source): return []
    description = soup.select_one('#tab-description, .product-description, .woocommerce-product-details__short-description')
    return [Listing(store=source["name"], source=source["id"], url=url, raw_title=title.get_text(),
        price_egp=money(price.get("content") or price.get_text()), stock=availability,
        observed_at=observed, verified_at=observed, description=clean(description),
        condition="new", comparison_only=source.get("comparison_only", False)).finish()]

def links(html, base, scope='tracked',source=None):
    soup = BeautifulSoup(html, "html.parser")
    output = []
    pattern=(source or {}).get('product_url_regex')
    for card in soup.select('.product-thumb, .product, .product-layout, .product-item, .prd, .ty-product-list, article'):
        if not interested(card.get_text(),{'_scope':scope}): continue
        a=next((a for a in card.select('a[href]') if re.search(pattern,urljoin(base,a['href']))),None) if pattern else card.select_one('.name a[href], h2 a[href], h3 a[href], a[href]')
        if a: output.append(urljoin(base, a['href']))
    for a in soup.select('a[href]'):
        target = urljoin(base, a['href'])
        valid=bool(re.search(pattern,target)) if pattern else any(x in target for x in ['/products/', '/product/', '/item/', '/item?'])
        if interested(target + " " + a.get_text(),{'_scope':scope}) and valid: output.append(target)
    return list(dict.fromkeys(output))

def sitemap_targets(locations,source):
    pattern=source.get('product_url_regex')
    targets=[u for u in locations if interested(unquote(u),source) and (not pattern or re.search(pattern,u))]
    if source.get('id')=='sigma':
        # Sigma publishes both language URLs for the same product ID.
        from urllib.parse import parse_qs
        unique={}
        for url in targets:
            parts=urlsplit(url)
            product_id=parse_qs(parts.query).get('id')
            key=(parts.hostname,product_id[0]) if product_id else url
            if key not in unique or parts.path.startswith('/en/'):
                unique[key]=url
        targets=list(unique.values())
    return targets

def verify_qarenly(candidates, client, registry, limit, rules):
    from .alerts import matches
    # Only fetch outbound retailer hosts already configured for this monitor.
    allowed={urlsplit(s['base']).hostname.removeprefix('www.'):s for s in registry if s.get('kind') not in {'aggregator','used'}}
    prioritized=[]
    for rule in rules:
        group=sorted([l for l in candidates if matches(l,rule)],key=lambda l:l.price_egp or float('inf'))
        prioritized.append(group)
    chosen=[]
    seen=set()
    while len(chosen)<limit and any(prioritized):
        for group in prioritized:
            if not group: continue
            candidate=group.pop(0)
            if candidate.url in seen: continue
            seen.add(candidate.url);chosen.append(candidate)
            if len(chosen)>=limit: break
    result,errors=[],[]
    for candidate in chosen:
        try:
            body,url,stamp=client.get(candidate.url)
            soup=BeautifulSoup(body,'html.parser')
            outbound=next((a.get('href') for a in soup.select('a[href]') if normalized(a.get_text()).lower()=='go to site'),None)
            if not outbound: continue
            host=urlsplit(outbound).hostname
            retailer=allowed.get(host.removeprefix('www.')) if host else None
            if not retailer: continue
            # Remove aggregator tracking parameters and fragments, retaining variant IDs.
            from urllib.parse import parse_qsl, urlencode, urlunsplit
            parts=urlsplit(outbound)
            query=urlencode([(k,v) for k,v in parse_qsl(parts.query) if not k.startswith('utm_')])
            outbound=urlunsplit((parts.scheme,parts.netloc,parts.path,query,''))
            body,url,stamp=client.get(outbound)
            if urlsplit(url).hostname.removeprefix('www.') not in allowed: continue
            result.extend(product_html(body,retailer,url,stamp))
        except FetchError as e: errors.append(str(e))
    return list({l.identity:l for l in result}.values()),list(dict.fromkeys(errors))

def collect(source, client, max_pages=3, max_details=8, verification_sources=None, rules=None, scope='tracked', progress=None,checkpoint=None):
    source={**source, '_scope':scope}
    adapter = source["adapter"]
    all_listings, failures = [], []
    pages = 0
    from .crawl_state import plan,observe,write,inventory
    metadata={'adapter':adapter,'started_at':now(),
              'feed_exhausted':False,'page_limit_reached':False,'detail_limit_reached':False,
              'discovery_exhausted':False,'discovered_product_urls':0,'detail_attempted_this_run':0,
              'failed_product_pages':[],'empty_product_pages':[]}
    state=None
    def emit(details):
        if progress:progress({'source':source['id'],**metadata,**details})
    def detail(targets):
        nonlocal state
        chosen,state=plan(targets,source,max_details)
        metadata.update(inventory(state),detail_limit_reached=len(targets)>len(chosen))
        emit({'stage':'product_details','pages':pages,'extracted_rows':len(all_listings)})
        pending=[];consecutive_empty=0
        for target in chosen:
            stamp=None;parsed=[];error=None
            try:
                body,url,stamp=fetch(target)
                parse=jsonld if adapter=='used' else product_html
                parsed=parse(body,source,url,stamp)
                all_listings.extend(parsed);pending.extend(parsed)
                if not parsed:metadata['empty_product_pages'].append(target)
                consecutive_empty=0 if parsed else consecutive_empty+1
            except (FetchError,KeyError,TypeError,ValueError,httpx.InvalidURL) as exc:
                error=str(exc);failures.append(error);metadata['failed_product_pages'].append({'url':target,'reason':error})
            metadata['detail_attempted_this_run']+=1
            observe(state,target,stamp,len(parsed),error)
            metadata.update(inventory(state))
            if metadata['detail_attempted_this_run']%25==0 or metadata['detail_attempted_this_run']==1:
                emit({'stage':'product_details','pages':pages,'extracted_rows':len(all_listings)})
                if checkpoint and pending:checkpoint(pending,dict(metadata));pending=[]
                # Commit the inventory after its corresponding rows. An
                # interrupted batch can safely re-fetch its uncommitted tail.
                write(source.get('_crawl_state_path'),state)
            if error and any(x in error for x in ['HTTP 401','HTTP 403','HTTP 429','host paused']):break
            if consecutive_empty>=10:
                failures.append('No listings extracted from 10 consecutive product pages; adapter needs review');break
        if checkpoint and pending:checkpoint(pending,dict(metadata))
        write(source.get('_crawl_state_path'),state)
    def fetch(url):
        nonlocal pages
        body, final, stamp = client.get(url, private=source.get("kind") == "used")
        if source.get('expected_path_prefix') and not urlsplit(final).path.startswith(source['expected_path_prefix']):raise FetchError('Site redirected outside its configured Egypt region')
        pages += 1
        return body, final, stamp
    try:
        if adapter in {"shopify", "woo"}:
            seen_feed_ids=set()
            for page in range(1, max_pages+1):
                path = f"/products.json?limit=250&page={page}" if adapter == "shopify" else f"/wp-json/wc/store/v1/products?per_page=100&page={page}"
                body, _, stamp = fetch(source["base"] + path)
                try: data = json.loads(body)
                except ValueError: raise FetchError("product endpoint returned non-JSON")
                if adapter == "shopify":
                    if not isinstance(data, dict) or "products" not in data: raise FetchError("invalid Shopify feed")
                    feed=data['products']
                    ids={str(p.get('id')) for p in feed}
                    if ids and ids <= seen_feed_ids: raise FetchError('pagination repeated previous products; stopped')
                    seen_feed_ids.update(ids)
                    all_listings.extend(shopify(data, source, stamp))
                else:
                    if not isinstance(data, list): raise FetchError("invalid WooCommerce feed")
                    feed=data
                    ids={str(p.get('id')) for p in feed}
                    if ids and ids <= seen_feed_ids: raise FetchError('pagination repeated previous products; stopped')
                    seen_feed_ids.update(ids)
                    all_listings.extend(woo(data, source, stamp))
                if page==1 or page%5==0:emit({'stage':'feed','page':page,'unique_products_seen':len(seen_feed_ids),'extracted_rows':len(all_listings)})
                if len(feed) < (250 if adapter=='shopify' else 100):metadata['feed_exhausted']=True;break
            metadata.update(feed_unique_products_seen=len(seen_feed_ids),page_limit_reached=not metadata['feed_exhausted'])
        elif adapter in {"qarenly", "pricena", "egprices"}:
            queries=source.get('queries',['15irx10','ddr5','3060','5600x'])
            metadata.update(planned_queries=len(queries),attempted_queries=0,failed_queries=[],query_limit_reached=len(queries)>max_pages)
            for query in queries[:max_pages]:
                path = source['search'].format(query=quote(query))
                metadata['attempted_queries']+=1
                try:
                    body,url,stamp=fetch(source['base']+path)
                    parse=qarenly if adapter=='qarenly' else egprices if adapter=='egprices' else jsonld
                    all_listings.extend(parse(body,source,url,stamp))
                except (FetchError,KeyError,TypeError,ValueError) as error:
                    failures.append(str(error));metadata['failed_queries'].append({'query':query,'reason':str(error)})
                    if any(code in str(error) for code in ['HTTP 401','HTTP 403','HTTP 429','host paused']):break
                emit({'stage':'aggregator_queries','extracted_rows':len(all_listings)})
        elif adapter == 'facebook-public':
            from .marketplace_local import card_listing
            paths=source.get('paths',[])
            limit=min(max_pages,source.get('public_page_limit',4))
            metadata.update(planned_discovery_paths=len(paths),attempted_discovery_paths=0,
                            failed_discovery_paths=[],authenticated=False,
                            requested_region=source.get('region'),availability='unconfirmed')
            for path in paths[:limit]:
                metadata['attempted_discovery_paths']+=1
                try:
                    body,url,stamp=fetch(source['base']+path)
                    if re.search(r'/login|/checkpoint|/challenge',urlsplit(url).path):
                        raise FetchError('Facebook login/challenge requires owner attention')
                    soup=BeautifulSoup(body,'html.parser')
                    count=0
                    for anchor in soup.select('a[href*="/marketplace/item/"]'):
                        text=anchor.get_text('\n',strip=True)
                        # Unlike owner-configured local Chrome, an anonymous
                        # page cannot establish that the £ symbol means EGP.
                        if not re.search(r'\bEGP\b|جنيه|ج\.\s*م',text,re.I):continue
                        item=card_listing(urljoin(url,anchor.get('href','')),text,stamp)
                        if item and interested(item.raw_title,source):
                            item.store=source['name'];item.source=source['id']
                            all_listings.append(item);count+=1
                    if not count:failures.append('No explicit-EGP public hardware cards; login or rendered-page layout may be required')
                except (FetchError,KeyError,TypeError,ValueError) as error:
                    failures.append(str(error));metadata['failed_discovery_paths'].append({'path':path,'reason':str(error)})
                    # A single robots/access failure ends this bounded probe.
                    break
            metadata['page_limit_reached']=len(paths)>limit
        elif adapter == 'sitemap':
            queue=[source['base']+source['sitemap']];seen=set();locations=[]
            while queue and len(seen)<max_pages:
                address=queue.pop(0)
                if address in seen:continue
                seen.add(address)
                previous_ttl=client.ttl if hasattr(client,'ttl') else None
                if previous_ttl is not None:client.ttl=source.get('sitemap_cache_seconds',86400)
                try:body,url,stamp=fetch(address)
                finally:
                    if previous_ttl is not None:client.ttl=previous_ttl
                try:root=ElementTree.fromstring(body)
                except ElementTree.ParseError:raise FetchError('invalid sitemap')
                entries=[]
                for node in root:
                    loc=next((e.text for e in node if e.tag.split('}')[-1]=='loc'),None)
                    if source.get('prefer_english'):
                        alternative=next((e.get('href') for e in node if e.get('hreflang')=='en'),None)
                        if alternative:loc=alternative.strip()
                    if loc:entries.append(loc.strip())
                if root.tag.split('}')[-1]=='sitemapindex':
                    pattern=source.get('sitemap_include')
                    queue.extend(u for u in entries if not pattern or re.search(pattern,u))
                else:locations.extend(entries)
                emit({'stage':'sitemap_discovery','sitemap_documents':len(seen),'urls_seen':len(locations)})
            metadata.update(discovery_exhausted=not queue,page_limit_reached=bool(queue),sitemap_documents=len(seen),sitemap_url_count=len(locations))
            targets=sitemap_targets(list(dict.fromkeys(locations)),source)
            metadata['filtered_sitemap_urls']=len(locations)-len(targets)
            detail(targets)
        elif adapter in {'html','used'}:
            targets = []
            metadata.update(planned_discovery_paths=len(source.get('paths',['/'])),attempted_discovery_paths=0,failed_discovery_paths=[])
            for path in source.get('paths',['/'])[:max_pages]:
                metadata['attempted_discovery_paths']+=1
                try:
                    body, url, stamp = fetch(source['base']+path)
                    all_listings.extend(jsonld(body,source,url,stamp))
                    targets.extend(links(body,url,scope,source))
                except (FetchError,KeyError,TypeError,ValueError) as error:
                    failures.append(str(error));metadata['failed_discovery_paths'].append({'path':path,'reason':str(error)})
                    if any(code in str(error) for code in ['HTTP 401','HTTP 403','HTTP 429','HTTP 503','host paused']):break
            metadata['discovery_exhausted']=False
            detail(list(dict.fromkeys(targets)))
        else: raise FetchError('unsupported adapter')
    except (FetchError, KeyError, TypeError, ValueError) as e:
        failures.append(str(e))
    verified=[]
    if adapter=='qarenly' and verification_sources and all_listings:
        verified,verification_errors=verify_qarenly(all_listings,client,verification_sources,max_details,rules or [])
        all_listings.extend(verified)
        failures.extend(verification_errors)
    dedup = {x.identity:x for x in all_listings}
    return list(dedup.values()), {'source':source['id'], 'status':'partial' if failures and dedup else 'blocked_or_failed' if failures else 'ok' if dedup else 'no_extracted_matches',
        'listings':len(dedup), 'pages':pages, 'errors':list(dict.fromkeys(failures)), 'page_limit':max_pages, 'detail_limit':max_details,
        'retailer_verifications':len(verified), 'scope':scope, 'network_requests':client.requests,
        'coverage':'Available product feed reached its end' if metadata['feed_exhausted'] else 'Discovered URL inventory; see remaining and failed counts. Not a claim of full-market coverage',
        **metadata }
