import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

def now():
    return datetime.now(timezone.utc).isoformat()

def normalized(text):
    return re.sub(r"\s+", " ", str(text or "").translate(DIGITS)).strip()

def money(value):
    if value is None or isinstance(value, bool):
        return None
    text = normalized(value).replace("٬", ",").replace("٫", ".")
    found = re.search(r"\d[\d,]*(?:\.\d+)?", text)
    if not found:
        return None
    try:
        return float(Decimal(found.group().replace(",", "")))
    except InvalidOperation:
        return None

def redact(text):
    text = normalized(text)
    text = re.sub(r"(?:\+?20[\s-]*)?0?1[0125](?:[\s-]*\d){8}\b", "[phone removed]", text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email removed]", text)
    text = re.sub(r"(?:https?://)?(?:wa\.me|api\.whatsapp\.com)/\S+", "[contact removed]", text)
    # Explicit contact lines may contain a person's name as well as a number.
    text = re.sub(r"(?:seller name|contact name|اسم البائع|للتواصل مع)\s*[:：].*?(?:[.!]|$)", "[contact removed]", text, flags=re.I)
    return text

def date_value(value):
    if not value:
        return None
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return d.replace(tzinfo=d.tzinfo or timezone.utc)
    except (ValueError, TypeError):
        return None

def category(title):
    from .hardware import classify
    return classify(normalized(title))


def extract_specs(title, description=""):
    # Parse only explicit facts. Detailed specs belong in a part-number reference join.
    title = normalized(title)
    text = normalized(title + " " + description).replace('™','').replace('®','')
    specs = {}
    intel = re.search(r'\b(i[3579])[\s-]*(\d{4,5}[A-Z]{0,3})\b',text,re.I)
    modern = re.search(r'\bCore\s+(Ultra\s+)?([3579])[\s-]+(\d{3}[A-Z]{0,3})\b',text,re.I)
    ryzen = re.search(r'\bRyzen\s*([3579])[\s-]+(\d{3,4}[A-Z0-9]{0,3})\b',text,re.I)
    if intel: specs['cpu_model']=intel.group(1).upper()+'-'+intel.group(2).upper()
    elif modern: specs['cpu_model']='Core '+('Ultra ' if modern.group(1) else '')+modern.group(2)+' '+modern.group(3).upper()
    elif ryzen: specs['cpu_model']='Ryzen '+ryzen.group(1)+' '+ryzen.group(2).upper()
    elif re.search(r'\b5600X\b',text,re.I): specs['cpu_model']='5600X'
    gpu = re.search(r"\b(?:RTX|GTX)\s*(A?\d{3,4})(?:\s*(Ti|SUPER|Ada))?\b", text, re.I)
    if gpu:
        specs["gpu_model"] = "RTX " + gpu.group(1) + (" " + gpu.group(2).upper() if gpu.group(2) else "") if gpu.group().lower().startswith("rtx") else gpu.group().upper()
        vram = re.search(r"(?:RTX|GTX)\s*A?\d{3,4}(?:\s*(?:Ti|SUPER|Ada))?\s*(\d+)\s*G(?:B)?\b", text, re.I)
        if not vram: vram = re.search(r'(\d+)\s*GB\s*(?:RTX|GTX)\s*A?\d{3,4}',text,re.I)
        if vram:
            following=text[vram.end():]
            if not re.match(r'\s*(?:DDR[2345]|RAM)\b',following,re.I):specs["gpu_vram_gb"] = int(vram.group(1))
    else:
        amd=re.search(r'\bRX\s*(\d{4})(?:\s*(XTX|XT))?\b',text,re.I)
        arc=re.search(r'\bArc\s*([AB]\d{3})\b',text,re.I)
        if amd or arc:
            match=amd or arc
            specs['gpu_model']='RX '+amd.group(1)+(' '+amd.group(2).upper() if amd.group(2) else '') if amd else 'Arc '+arc.group(1).upper()
            vram=re.search(r'\b(\d+)\s*GB\s*(?:GDDR[567]|VRAM)?\b',text[match.end():match.end()+100],re.I)
            if vram and not re.match(r'\s*(?:DDR[2345]|RAM)\b',text[match.end()+vram.end():],re.I):specs['gpu_vram_gb']=int(vram.group(1))
    kind = category(title)
    ddr = re.search(r"\b(?:LP)?DDR\s*([2345])(?:X)?\b", title, re.I)
    if not ddr: ddr=re.search(r"\b(?:LP)?DDR\s*([2345])(?:X)?\b", text, re.I)
    if ddr:
        specs["ram_type"] = "DDR" + ddr.group(1)
    if kind == "ram":
        kit = re.search(r"(\d+)\s*[x×*]\s*(\d+)\s*G(?:B)?\b", title, re.I)
        reverse_kit=re.search(r'(\d+)\s*GB\s*[x×*]\s*(\d+)\b',title,re.I)
        capacity = re.search(r"\b(\d+)\s*G(?:B)?\b", title, re.I)
        if kit:
            specs.update(ram_modules=int(kit.group(1)), ram_module_gb=int(kit.group(2)), ram_gb=int(kit.group(1))*int(kit.group(2)))
        elif reverse_kit:
            specs.update(ram_modules=int(reverse_kit.group(2)),ram_module_gb=int(reverse_kit.group(1)),ram_gb=int(reverse_kit.group(1))*int(reverse_kit.group(2)))
        elif capacity:
            specs["ram_gb"] = int(capacity.group(1))
            if re.search(r"\b(?:single|1x|stick|module|sodimm|so-dimm)\b", title, re.I) and "kit" not in title.lower():
                specs.update(ram_modules=1, ram_module_gb=int(capacity.group(1)))
        if re.search(r"sodimm|so-dimm|laptop|notebook", title, re.I):
            specs["ram_form_factor"] = "SODIMM"
        elif re.search(r'\brdimm\b|registered',title,re.I):
            specs['ram_form_factor']='RDIMM'
        elif re.search(r"udimm|desktop|\bdimm\b|ram for pc", title, re.I):
            specs["ram_form_factor"] = "DIMM"
        if not specs.get('ram_form_factor'):
            sodimm=bool(re.search(r'\b(?:sodimm|so-dimm)\b',description,re.I))
            dimm=bool(re.search(r'\b(?:udimm|desktop memory|desktop ram)\b',description,re.I))
            if sodimm and not dimm:specs['ram_form_factor']='SODIMM'
            elif dimm and not sodimm:specs['ram_form_factor']='DIMM'
        speed = re.search(r"\b(\d{3,5})\s*(?:MHz|MT/s|MT|HZ)\b", title, re.I)
        if not speed: speed=re.search(r'\bDDR[2345][\s-]+(\d{4,5})\b',title,re.I)
        if not speed: speed=re.search(r"\b(\d{3,5})\s*(?:MHz|MT/s|MT)\b", text, re.I)
        cas = re.search(r"\bCL\s*(\d{2})\b", text, re.I)
        if speed: specs["ram_speed_mt_s"] = int(speed.group(1))
        if cas: specs["ram_cas_latency"] = int(cas.group(1))
        if re.search(r'\bnon[ -]?ecc\b',title,re.I):specs['ram_ecc']=False
        elif re.search(r'\becc\b',title,re.I):specs['ram_ecc']=True
        if re.search(r'\bunbuffered\b|\budimm\b',title,re.I):specs['ram_registered']=False
        elif re.search(r'\bregistered\b|\brdimm\b',title,re.I):specs['ram_registered']=True
    else:
        ram = re.search(r"(\d+)\s*G(?:B)?\s*(?:RAM|DDR[345])\b|(?:RAM|DDR[345])\s*[:\-]?\s*(\d+)\s*G(?:B)?\b", title, re.I)
        if ram: specs["ram_gb"] = int(ram.group(1) or ram.group(2))
        elif kind=='laptop':
            without_gpu=re.sub(r'(?:RTX|GTX)\s*A?\d{3,4}(?:\s*(?:Ti|SUPER|Ada))?\s*\d+\s*G(?:B)?\b|\d+\s*GB\s*(?:RTX|GTX)\s*A?\d{3,4}', '', title,re.I)
            capacities={int(x) for x in re.findall(r'\b(8|12|16|24|32|48|64|96|128)\s*GB\b',without_gpu,re.I)}
            if len(capacities)==1: specs['ram_gb']=capacities.pop()
    storage = re.search(r'(?<![\w.])(\d+(?:\.\d+)?)\s*(GB|TB)?\s*(?:NVMe|SSD)\b', title, re.I)
    if not storage: storage=re.search(r'(?:NVMe|SSD|M\.2)\s*(\d+(?:\.\d+)?)\s*(GB|TB)\b',title,re.I)
    if storage: specs['storage_gb'] = int(float(storage.group(1))*(1000 if (storage.group(2) or '').upper()=='TB' else 1))
    if kind in {'ssd','hdd'}:
        capacity=re.search(r'\b(\d+(?:\.\d+)?)\s*(GB|TB)\b',title,re.I)
        if capacity:specs['storage_gb']=int(float(capacity.group(1))*(1000 if capacity.group(2).upper()=='TB' else 1))
        specs['storage_type']=kind.upper()
        generation=re.search(r'\b(?:gen\s*|pcie\s*)([345])(?:\.0)?\b',title,re.I)
        if generation:specs['storage_pcie_gen']=int(generation.group(1))
        tbw=re.search(r'\b(\d+)\s*TBW\b',text,re.I)
        if tbw:specs['ssd_tbw']=int(tbw.group(1))
        if re.search(r'\b(?:dram[ -]?less|no dram|without dram)\b',text,re.I):specs['ssd_dram']=False
        elif re.search(r'\bwith dram\b|\bdram cache\b',text,re.I):specs['ssd_dram']=True
    if kind=='cpu':
        socket=re.search(r'\b(?:AM[345]|LGA\s*\d{4})\b',text,re.I)
        if socket:specs['cpu_socket']=socket.group().upper().replace(' ','')
        if re.search(r'\btray\b',title,re.I):specs['cpu_package']='tray'
        elif re.search(r'\b(?:boxed|box)\b',title,re.I):specs['cpu_package']='boxed'
        if re.search(r'\b(?:without (?:fan|cooler)|no cooler)\b',text,re.I):specs['cooler_included']=False
        elif re.search(r'\b(?:cooler included|with (?:a )?(?:stock )?cooler)\b',text,re.I):specs['cooler_included']=True
        if specs.get('cpu_model','').startswith('I') and re.search(r'\dF$|\dKF$',specs['cpu_model']):specs['cpu_integrated_graphics']=False
    if kind=='motherboard':
        chipset=re.search(r'\b([BHZX]\d{3}[E]?)(?:M)?\b',title,re.I)
        if chipset:specs['motherboard_chipset']=chipset.group(1).upper()
        form=re.search(r'\b(?:micro[ -]?atx|m[ -]?atx|mini[ -]?itx|e[ -]?atx|atx)\b',text,re.I)
        if form:specs['motherboard_form_factor']=form.group().upper()
        slots=re.search(r'\b([248])\s*(?:x\s*)?(?:DDR[345]\s*)?(?:DIMM|RAM)\s*slots?',text,re.I)
        if slots:specs['motherboard_ram_slots']=int(slots.group(1))
        if re.search(r'\bwi[ -]?fi\b',title,re.I):specs['motherboard_wifi']=True
    if kind=='psu':
        watts=re.search(r'\b(\d{3,4})\s*(?:W|watts?)\b',title,re.I)
        if watts:specs['psu_w']=int(watts.group(1))
        rating=re.search(r'80\s*(?:\+|plus)\s*(bronze|silver|gold|platinum|titanium|standard)?',title,re.I)
        if rating:specs['psu_80plus']=(rating.group(1) or 'standard').lower()
        specs['psu_model']=title
    if kind=='ups':
        va=re.search(r'\b(\d{3,5})\s*VA\b',title,re.I)
        watts=re.search(r'\b(\d{2,5})\s*W\b',title,re.I)
        if va:specs['ups_va']=int(va.group(1))
        if watts:specs['ups_w']=int(watts.group(1))
    if kind == 'laptop':
        resolution = re.search(r'\b(\d{3,4})\s*[x×]\s*(\d{3,4})\b',title,re.I)
        if resolution: specs['display_resolution'] = resolution.group(1)+'x'+resolution.group(2)
        refresh = re.search(r'\b(\d{2,3})\s*Hz\b',title,re.I)
        if refresh: specs['display_hz'] = int(refresh.group(1))
        panel = re.search(r'\b(?:IPS|OLED|TN|VA)\b',title,re.I)
        if panel: specs['display_panel'] = panel.group().upper()
        brightness = re.search(r'\b(\d{3,4})\s*nits\b',title,re.I)
        if brightness: specs['display_nits'] = int(brightness.group(1))
        srgb = re.search(r'\b(\d{2,3})\s*%\s*sRGB',title,re.I)
        if srgb: specs['display_srgb_pct'] = int(srgb.group(1))
        size=re.search(r'\b(1[2-8](?:\.\d)?)\s*(?:-?inch|inches|["″])',title,re.I)
        if size: specs['display_inches']=float(size.group(1))
        if not resolution:
            if re.search(r'\b(?:WUXGA|FHD\+)',title,re.I): specs['display_resolution']='1920x1200'
            elif re.search(r'\bFHD\b',title,re.I): specs['display_resolution']='1920x1080'
        memory_speed=re.search(r'\bDDR[345][\s-]*(\d{4,5})\s*(?:MHz|MT/s)?',title,re.I)
        if memory_speed: specs['ram_speed_mt_s']=int(memory_speed.group(1))
    if re.search(r"\b(?:DOS|FreeDOS)\b", text, re.I):
        specs["os"] = "DOS"
        specs["windows_license_included"] = False
    elif re.search(r'\b(?:Win(?:dows)?\s*11|Win11)\b',text,re.I):
        specs['os']='Windows 11'
        specs['windows_license_included']=True
    return specs

SPEC_FIELDS = "cpu_model cpu_cores cpu_threads cpu_boost_ghz cpu_socket cpu_integrated_graphics cpu_package cooler_included gpu_model gpu_vram_gb gpu_tgp_w gpu_mux gpu_length_mm gpu_power_connector gpu_recommended_psu_w ram_gb ram_type ram_speed_mt_s ram_modules ram_module_gb ram_slots ram_soldered ram_max_gb ram_form_factor ram_cas_latency ram_ecc ram_registered storage_gb storage_type storage_pcie_gen storage_free_m2 motherboard_chipset motherboard_form_factor motherboard_ram_slots motherboard_m2_slots motherboard_wifi display_inches display_resolution display_hz display_panel display_nits display_srgb_pct battery_wh charger_w weight_kg ports wifi_version keyboard_layout os windows_license_included region_suffix psu_w psu_80plus psu_model psu_tier ssd_dram ssd_tbw case_gpu_clearance_mm ups_va ups_w ups_runtime_400w_minutes".split()

@dataclass
class Listing:
    store: str
    url: str
    raw_title: str
    price_egp: float | None
    observed_at: str = field(default_factory=now)
    source: str = ""
    source_kind: str = "retailer"
    currency: str = "EGP"
    old_price_egp: float | None = None
    stock: str = "unknown"
    quantity: int | None = None
    placeholder: bool = False
    condition: str = "unknown"
    brand: str | None = None
    model: str | None = None
    mpn: str | None = None
    sku: str | None = None
    parent_title: str | None = None
    variant_title: str | None = None
    build_complete: bool | None = None
    category: str = "other"
    accessory_type: str | None = None
    warranty_months: int | None = None
    warranty_type: str | None = None
    seller: str | None = None
    fulfilled_by: str | None = None
    shipping_egp: float | None = None
    delivery_time: str | None = None
    installments: str | None = None
    bundle_contents: str | None = None
    images: list = field(default_factory=list)
    page_updated_at: str | None = None
    verified_at: str | None = None
    comparison_only: bool = False
    description: str = ""
    used: dict = field(default_factory=dict)
    specs: dict = field(default_factory=dict)
    spec_sources: dict = field(default_factory=dict)
    quality_issues: list = field(default_factory=list)
    # Zone layer (tech_monitor, 2026-10-07). Old rows have none of these and read back as Egypt.
    zone: str = "EG"                      # EG, UAE, KSA or US: where the item is bought
    country: str | None = None
    price_local: float | None = None      # price in `currency` as shown; price_egp is the converted item price only
    payments: list = field(default_factory=list)   # paypal, cod, card, installments, bank_transfer, instapay ...
    route: str | None = None              # how it reaches Mansoura
    landed_egp: float | None = None       # only when a real quote exists; never a guess, never zero for "unknown"
    landed_status: str = "domestic"       # domestic | unconfirmed (reason in `route`) | quoted

    def finish(self):
        self.raw_title = normalized(self.raw_title)
        if self.sku is not None: self.sku = str(self.sku)
        if self.mpn is not None: self.mpn = str(self.mpn)
        self.category = category(self.raw_title)
        from .hardware import GEAR_CATEGORIES,gear_type
        self.accessory_type=gear_type(self.raw_title) if self.category in GEAR_CATEGORIES else None
        t = (self.raw_title + " " + self.description).lower()
        condition_text=self.raw_title.lower()
        if re.search(r"\b(?:used|as new|like new)\b|مستعمل|كسر زيرو", condition_text):
            self.condition = "used"
        elif "refurbished" in condition_text:
            self.condition = "refurbished"
        elif "open box" in condition_text:
            self.condition = "open_box"
        self.placeholder = self.placeholder or self.price_egp is None or self.price_egp < 100 or any(x in t for x in ["coming soon", "قريبا", "قريباً"])
        explicit = extract_specs(self.raw_title, self.description)
        self.specs = {**{k: None for k in SPEC_FIELDS}, **explicit, **self.specs}
        for k in explicit: self.spec_sources.setdefault(k, self.url)
        if self.variant_title:
            variant=normalized(self.variant_title)
            if self.category=='ram':
                capacity=re.search(r'\b(\d+)\s*G(?:B)?\b',variant,re.I)
                kit=re.search(r'(\d+)\s*[x×*]\s*(\d+)\s*G(?:B)?\b',variant,re.I)
                if kit:self.specs.update(ram_modules=int(kit.group(1)),ram_module_gb=int(kit.group(2)),ram_gb=int(kit.group(1))*int(kit.group(2)))
                elif capacity:self.specs['ram_gb']=int(capacity.group(1))
                generation=re.search(r'\bDDR\s*([2345])\b',variant,re.I)
                if generation:self.specs['ram_type']='DDR'+generation.group(1)
            elif self.category in {'ssd','hdd'}:
                capacity=re.search(r'\b(\d+(?:\.\d+)?)\s*(GB|TB)\b',variant,re.I)
                if capacity:self.specs['storage_gb']=int(float(capacity.group(1))*(1000 if capacity.group(2).upper()=='TB' else 1))
        mpn = re.search(r"\b(?:83|82)[A-Z0-9]{8}\b", (self.raw_title + " " + self.description + " " + (self.sku or "")).upper())
        if not self.mpn and mpn: self.mpn = mpn.group()
        from .hardware import manufacturer
        explicit_brand=manufacturer(self.raw_title)
        if explicit_brand:self.brand=explicit_brand
        elif self.brand:
            canonical=manufacturer(self.brand)
            if canonical:self.brand=canonical
            elif self.brand.casefold()==self.store.casefold():self.brand=None
            elif self.brand.casefold()=='generic':self.brand='Generic'
        if self.category=='bundle':
            parts=self.description.lower()
            if re.search(r'\b(?:ram|memory)\b',parts) and re.search(r'\b(?:rtx|geforce|radeon)\b',parts) and re.search(r'\b(?:ssd|nvme)\b',parts) and re.search(r'\b(?:case|psu|power supply)\b',parts):self.category='pc'
        if self.category in {'pc','bundle'}:
            self.build_complete=False if self.category=='bundle' or re.search(r'\b(?:no hard|no graphics card|without gpu)\b',t) else None
        if not self.model:
            model = re.search(r'\b(?:LOQ|Legion|IdeaPad)\s+(?:\d\s+)?[A-Z0-9]+\b',self.raw_title,re.I)
            if model: self.model = model.group()
        if self.warranty_months is None:
            warranty = re.search(r'(\d+)\s*[- ]?\s*(years?|months?)\s*warranty',t)
            if warranty: self.warranty_months=int(warranty.group(1))*(12 if warranty.group(2).startswith('year') else 1)
        if not self.warranty_type:
            for label,value in [('official warranty','official'),('store warranty','store'),('international warranty','international')]:
                if label in t: self.warranty_type=value;break
        if self.category=='pc': self.bundle_contents=self.bundle_contents or self.raw_title
        if self.category=='laptop':
            title_memory=re.search(r'\bDDR\s*([345])\b',self.raw_title,re.I)
            description_memory=re.search(r'\b(?:RAM|Memory)\s*[:\-]?\s*\d+\s*GB\s*DDR\s*([345])\b',self.description,re.I)
            if title_memory and description_memory and title_memory.group(1)!=description_memory.group(1):
                self.quality_issues.append('Laptop title and memory description disagree on DDR generation; verify installed RAM')
        if self.category == 'ram':
            if self.parent_title and self.variant_title:
                parent_sizes={int(v) for v in re.findall(r'\b(\d+)\s*G(?:B)?\b',self.parent_title,re.I)}
                variant_sizes={int(v) for v in re.findall(r'\b(\d+)\s*G(?:B)?\b',self.variant_title,re.I)}
                if parent_sizes and variant_sizes and not variant_sizes.issubset(parent_sizes):
                    self.quality_issues.append('RAM variant capacity conflicts with parent title; verify exact variant')
            kingston_kit = re.search(r'\b(KF\d{3}[SU]\d{2}[A-Z0-9]*K(\d)-(\d+))(?!\d)', (self.raw_title+' '+self.description+' '+(self.sku or '')+' '+(self.mpn or '')).upper())
            if kingston_kit:
                self.mpn = self.mpn or kingston_kit.group(1)
                if self.specs.get('ram_gb') != int(kingston_kit.group(3)) or (self.specs.get('ram_modules') is not None and self.specs['ram_modules'] != int(kingston_kit.group(2))):
                    self.quality_issues.append('RAM title conflicts with Kingston kit part-number capacity/configuration; verify with retailer')
        if self.category not in {'pc','bundle','laptop','other'} and re.search(r'داخل\s+(?:تجميع[هة]|التجميع[هة])|\b(?:bundle only|build only|only (?:bundle|build)|only (?:in|with) (?:a )?(?:bundle|build))\b',self.raw_title,re.I):
            self.quality_issues.append('Price requires a PC build or bundle; standalone price not verified')
        if self.source_kind == "used" or self.condition == "used":
            self.seller = None
            self.description = redact(self.description)
            self.raw_title = redact(self.raw_title)
            self.used["good_signs"] = [x for x in ["فاتورة", "ضمان", "بالكرتونة", "متبرشم", "كسر زيرو"] if x in t]
            self.used["warning_signs"] = [x for x in ["تعدين", "دخل صيانة", "استيراد", "mining", "lhr"] if x in t]
        self.quality_issues=list(dict.fromkeys(self.quality_issues))
        return self

    @property
    def identity(self):
        # Shopify variant URLs remain distinct; duplicate JSON-LD descriptions of one URL collapse.
        return hashlib.sha256((self.store + "|" + self.url).encode()).hexdigest()[:24]

    def eligible(self, at=None):
        at = at or datetime.now(timezone.utc)
        verified = date_value(self.verified_at)
        updated = date_value(self.page_updated_at)
        if self.source_kind == "aggregator":
            fresh = verified is not None and updated is not None and 0 <= (at - updated).total_seconds() <= 7*86400
        else:
            fresh = verified is not None and -300 <= (at - verified).total_seconds() <= 7*86400
        return bool(fresh and self.stock == "in_stock" and not self.placeholder and not self.quality_issues and not self.comparison_only and self.currency == "EGP")

    def dict(self):
        result = asdict(self)
        result["id"] = self.identity
        result["discount_pct"] = round((1-self.price_egp/self.old_price_egp)*100,2) if self.price_egp and self.old_price_egp and self.old_price_egp > self.price_egp else None
        result["alert_eligible"] = self.eligible()
        return result
