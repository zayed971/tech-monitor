"""Create a dated, reviewable shortlist from the collected retailer offers."""
import json
from contextlib import closing
from pathlib import Path

from egypt_deals.cli import export
from egypt_deals.metrics import apply_references
from egypt_deals.model import now, category
from egypt_deals.storage import Database


root = Path(__file__).resolve().parents[1]
data = root / 'data/laptop-review'
references = json.loads((root / 'references.json').read_text())
references['products']['83JC00H1ED'] = {
    'source_url': 'https://psref.lenovo.com/syspool/Sys/PDF/LOQ/LOQ_15ARP9/LOQ_15ARP9_Spec.PDF',
    'checked_at': now(),
    'specs': {'cpu_cores': 8, 'cpu_threads': 16, 'cpu_boost_ghz': 4.5,
              'ram_slots': 2, 'ram_max_gb': 32},
    'notes': 'Platform facts matching the listed CPU. Factory 12GB module layout remains unknown. GPU power depends on charger: 105W with 170W adapter, up to 115W with 230W adapter.'
}
(root / 'references.json').write_text(json.dumps(references, ensure_ascii=False, indent=2) + '\n')

with closing(Database(root / 'data/deals.sqlite3')) as db:
    listings = db.listings()
    for listing in listings:
        classified = category(listing.raw_title)
        if listing.category != classified:
            listing.category = classified
            db.db.execute('UPDATE listings SET payload=? WHERE id=?',
                          (json.dumps(listing.dict(), ensure_ascii=False), listing.identity))
        if listing.raw_title.lower().startswith('as new '):
            listing.condition = 'used'
            db.db.execute('UPDATE listings SET payload=? WHERE id=?',
                          (json.dumps(listing.dict(), ensure_ascii=False), listing.identity))
    affected = [l for l in listings if l.mpn in references['products']]
    apply_references(affected, root / 'references.json')
    # Enrichment preserves the source observation date and price.
    for l in affected:
        db.db.execute('UPDATE listings SET payload=? WHERE id=?',
                        (json.dumps(l.dict(), ensure_ascii=False), l.identity))
    db.db.commit()
    export(db, root)
    listings = db.listings()

choices = [
    ('Best lower-price new gaming option', 'Sigma Computer', '83LK00C9US',
     'RTX 4050 6GB, 8GB RAM, 512GB SSD. Only one RAM slot: upgrade by replacing the module. Advertised 144Hz 100% sRGB display, Windows 11, one-year warranty. Budget for RAM; not comparable to a higher-power RTX 4050 on model name alone.'),
    ('Best value for plugged-in 3D work', 'Sigma Computer', '83JC00H1ED',
     'RTX 4060 8GB, Ryzen 7 7435HS, 12GB RAM, 512GB SSD. Advertised 144Hz 100% sRGB display and two-year warranty. Two RAM slots, but installed module layout is unconfirmed. CPU has no integrated GPU, which limits battery efficiency. Retailer lists 105W GPU; manufacturer says power varies with charger.'),
    ('Mid-price option with 16GB RAM', 'Compumarts', 'Gigabyte Gaming A16 CTH Gaming',
     'i7-13620H, RTX 5050 8GB, 16GB DDR5, 512GB SSD, 16-inch WUXGA 165Hz. Exact factory RAM layout and panel color coverage need confirmation. A conditional 1x16GB + 9,500 EGP stick upgrade totals 67,999 EGP; do not assume 1x16 is installed.'),
    ('RTX 5060 with 1TB storage', 'Compumarts', 'GIGABYTE Gaming A16 Laptop Intel',
     'i7-13620H, RTX 5060 8GB, 16GB DDR5, 1TB SSD, 16-inch WUXGA 165Hz and Windows 11. Useful storage advantage. Manufacturer publishes multiple panel variants; local 100% sRGB claim is not independently confirmed for WUXGA.'),
    ('Alternative RTX 5060', 'Compumarts', 'ANV15-52-9703',
     'i9-13900H, RTX 5060 8GB, 16GB RAM, 512GB SSD, 165Hz and Windows 11. Acer lists maximum GPU power of 75W. Memory-generation information conflicts across sources. The i9 badge alone does not establish better value or rendering performance.'),
    ('Lower-cost 100W RTX 5060 option', 'Compumarts', 'Cyborg 15 Max C13WF',
     'i7-13620H, RTX 5060 8GB, 16GB DDR5, 512GB SSD; two-year advertised warranty. MSI Max platform specifies 100W GPU and 144Hz 100% sRGB panel. Confirm Egypt SKU C13WF-020EG. This is a different platform from the older 45W Cyborg A13VE.'),
    ('Highest-priority CPU-heavy option near the ceiling', 'Sigma Computer', '83JE00U1AX',
     'i7-14700HX (20 cores / 28 threads), RTX 5060 8GB at platform 100W, 16GB DDR5, 512GB SSD, 144Hz 100% sRGB. Two RAM slots; layout unconfirmed. DOS means no Windows license included. One-year advertised warranty. Only 501 EGP remains within the 70k base-price budget.'),
    ('Lower-cost used CAD option', 'Kimo Store', 'Precision 3581',
     'Used i7-13800H, RTX A500 4GB, 16GB DDR5, 512GB SSD, FHD touch. Primary description gives one-month warranty and Windows Test, so a paid Windows license is not established. CPU-focused CAD option; 4GB VRAM limits larger rendering scenes. Battery health and condition require inspection.'),
]
shortlist = []
for purpose, store, match, note in choices:
    candidates = [l for l in listings if l.store == store and l.category == 'laptop'
                  and l.eligible() and l.price_egp <= 70000
                  and match.casefold() in (l.raw_title + ' ' + str(l.mpn)).casefold()]
    if not candidates:
        continue
    listing = min(candidates, key=lambda l: l.price_egp)
    shortlist.append({'purpose': purpose, 'notes': note, 'listing': listing.dict()})
(data / 'shortlist.json').write_text(json.dumps(shortlist, ensure_ascii=False, indent=2) + '\n')

summary = json.loads((data / 'summary.json').read_text())
lines = [
    '# Laptop review: Egypt, advertised prices up to 70,000 EGP', '',
    f'Generated: {now()}. Destination: Mansoura. Prices exclude delivery and upgrades.', '',
    '**Recommendation:** start with the 54,499 EGP Lenovo LOQ 15ARP9 RTX 4060 for value when working plugged in. Compare the 65,499 EGP MSI Cyborg 15 Max and 69,499 EGP LOQ i7-14700HX RTX 5060 if more CPU/GPU headroom justifies the cost. No matched Blender or Rhino benchmark results were collected, so these are specification-based candidates rather than measured performance rankings.', '',
    f"Reviewed {summary['eligible_in_stock_unique_products']} distinct eligible, in-stock retailer products ({summary['in_stock_unique_products_by_condition'].get('new', 0)} new and {summary['in_stock_unique_products_by_condition'].get('used', 0)} used). The full export preserves {summary['under_budget_retailer_variant_rows_all_stock_states']:,} variant offers / {summary['under_budget_unique_retailer_products_all_stock_states']:,} distinct retailer products across all stock states.", '',
    '## Shortlist', '',
    '| Laptop | CPU / GPU | RAM / SSD | EGP | Retailer |',
    '|---|---|---|---:|---|',
]
for item in shortlist:
    l = item['listing']; s = l['specs']
    title = l['raw_title'].replace('|', '\\|')
    lines.append(f"| [{title}]({l['url']}) | {s.get('cpu_model')} / {s.get('gpu_model')} | {s.get('ram_gb')}GB / {s.get('storage_gb')}GB | {l['price_egp']:,.0f} | {l['store']} |")
lines += ['', '## What the prices mean', '']
for item in shortlist:
    lines += [f"- **{item['purpose']} — {item['listing']['price_egp']:,.0f} EGP:** {item['notes']}"]
lines += [
    '', '## RAM and the budget', '',
    'The ceiling currently applies to the advertised laptop price. RAM upgrades, installation, shipping to Mansoura and any Windows license are separate. Current collected 16GB DDR5 laptop sticks start at 9,500 EGP. Adding one to a verified 1x16GB system costs about 9,500 EGP; replacing smaller modules with two costs about 19,000 EGP before fitting and delivery. Installed layouts and memory compatibility must be checked first.', '',
    'The 69,499 EGP LOQ would become 78,999 EGP in the conditional add-one-stick scenario. The 54,499 EGP 12GB LOQ becomes 73,499 EGP if both modules must be replaced with two 16GB sticks. Neither is a verified 32GB purchase within 70k. The cheaper LOQ Essential has one slot, so a two-stick kit will not fit.', '',
    '## New GPU coverage', '',
    '| Parsed GPU | Distinct in-stock new laptops |', '|---|---:|',
]
for gpu, count in summary['in_stock_new_products_by_gpu'].items():
    lines.append(f'| {gpu} | {count} |')
lines += [
    '', '## Coverage and limits', '',
    'Eight complete discovered retailer feeds were refreshed, including all 87 Alfrensia pages, plus 137 distinct Sigma laptop product pages from the discovered sitemap. The resumed scrape reused feed responses downloaded minutes earlier, retaining their original timestamps. Leading offers were also checked on their product pages. Some retained offers were observed earlier the same evening; their dates are explicit in the CSV.', '',
    'All recognized retailer laptop prices up to 70k are retained, including unavailable products. Recommendations use fresh, explicit in-stock offers with a matching retailer URL. Accessories, placeholder prices, foreign structured-offer URLs and Sigma language duplicates are excluded from the eligible counts. This covers the collected sources, not every seller or laptop in Egypt; the discovered Sigma sitemap itself was bounded. Dubizzle was inaccessible in this environment.', '',
    'Used listings indicate asking prices, not proven sale prices. Retailer warranty lengths are advertised claims; official warranty status is not inferred from an ED suffix. Missing GPU power, factory memory layouts, batteries and benchmark scores remain unknown unless cited in manufacturer-evidence.json or the verification records.', '',
    'Amazon US delivery and final import cost to Mansoura remain unverified: no destination-specific checkout quote was obtained. Compare a confirmed landed price, including shipping, import fees and payment conversion, against the matching local configuration. A US sticker price alone does not establish a saving.', '',
    'Budget monitoring: every eligible collected laptop at or below 70k is included in the 8% within 24 hours drop rule. The i7-14700HX/RTX5060 LOQ threshold was raised to 70k. Monitoring ends on 26 October 2026 and depends on the cloud workspace remaining active.', '',
    'Manufacturer sources:', '',
    '- LOQ 15ARP9: https://psref.lenovo.com/syspool/Sys/PDF/LOQ/LOQ_15ARP9/LOQ_15ARP9_Spec.PDF',
    '- AMD Ryzen 7435HS without integrated graphics: https://www.amd.com/en/blogs/2024/new-amd-ryzen-notebook-dgpu-paired-offerings-.html',
    '- LOQ 15IRX10: https://psref.lenovo.com/syspool/Sys/PDF/LOQ/LOQ_15IRX10/LOQ_15IRX10_Spec.PDF',
    '- MSI Cyborg 15 Max: https://www.msi.com/Laptop/Cyborg-15-MAX-C13WX/Specification',
    '- Acer exact model: https://www.acer.com/ae-en/laptops/nitro/nitro-v-15/pdp/NH.QZAEM.004',
    '- Gigabyte A16: https://www.gigabyte.com/us/Laptop/GIGABYTE-GAMING-A16-GA6H/sp',
]
(data / 'review.md').write_text('\n'.join(lines) + '\n')
print(json.dumps({'shortlisted_offers': len(shortlist), 'summary': summary}, ensure_ascii=False))
