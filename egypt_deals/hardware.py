"""Explicit hardware classification and manufacturer names for catalog exports."""
import re

HARDWARE_CATEGORIES = {'laptop','pc','bundle','cpu','motherboard','ram','gpu','ssd','hdd','psu','case','cooler','ups','monitor','network','peripheral','accessory'}
GEAR_CATEGORIES={'accessory','peripheral','network','monitor','audio','gaming','creator','maker','smart_home','wearable','tablet','ereader'}
HARDWARE_CATEGORIES.update(GEAR_CATEGORIES)

GEAR_PATTERNS=[
    ('accessory','monitor_arm',r'monitor (?:arm|mount|stand)|vesa (?:arm|mount)'),
    ('accessory','hub_dock_kvm',r'\bkvm\b|docking station|usb[ -]?(?:c )?hub|thunderbolt dock'),
    ('accessory','enclosure_reader',r'(?:ssd|hdd|nvme|m\.2|hard drive) (?:enclosure|caddy)|card reader'),
    ('accessory','charging',r'power bank|wall charger|gan charger|usb[ -]?c charger|(?:laptop|notebook) charger'),
    ('accessory','laptop_support',r'laptop (?:stand|riser|kickstand|cooling)|cooling pad'),
    ('accessory','carry_protection',r'laptop (?:bag|sleeve)|backpack|(?:protective|hard shell) case'),
    ('accessory','cable_adapter',r'\b(?:cable|hdmi splitter|displayport adapter|usb adapter)\b'),
    ('accessory','maintenance',r'thermal (?:paste|pad)|screwdriver|compressed air|electric duster|cleaning kit|anti[ -]?static'),
    ('accessory','desk_setup',r'mouse[ -]?pad|desk[ -]?mat|wrist rest|gaming chair\b|gaming desk\b|rgb strip|led strip'),
    ('accessory','keyboard_customization',r'keycaps?|keyboard switches|switch puller|keycap puller'),
    ('accessory','portable_storage',r'usb flash|flash drive|pendrive|micro[ -]?sd|sdxc|sdhc|memory card'),
    ('creator','drawing_tablet',r'drawing tablet|graphics tablet|pen tablet|\bwacom\b|\bhuion\b|xp[ -]?pen'),
    ('creator','streaming_capture',r'stream deck|capture card|video capture|audio interface|condenser microphone|usb microphone|ring light'),
    ('maker','development_tools',r'raspberry pi|\barduino\b|\besp32\b|\besp8266\b|breadboard|soldering (?:iron|station)|digital multimeter|3d printer'),
    ('gaming','vr',r'vr headset|virtual reality headset|meta quest|oculus quest'),
    ('gaming','handheld',r'steam deck|legion go|rog ally|gaming handheld'),
    ('gaming','console_controller',r'\b(?:game console|playstation|ps5|xbox|nintendo switch|dualsense|dualshock|joystick|racing wheel|flight stick)\b'),
    ('audio','personal_audio',r'\b(?:earbuds?|airpods|iem|in[ -]ear monitor)\b'),
    ('audio','speakers_dac',r'\b(?:speakers?|soundbar|subwoofer|dac|headphone amplifier)\b'),
    ('smart_home','connected_devices',r'smart (?:plug|bulb|light|hub|switch)|ip camera|security camera|\bimou\b|video doorbell'),
    ('wearable','watch_tracker',r'smart[ -]?watch|apple watch|fitness tracker|smart band'),
    ('ereader','reader',r'\bkindle\b|\bkobo\b|e[ -]?reader'),
    ('tablet','tablet',r'\b(?:ipad|tablet)\b|\blenovo tab\b|detachable tab'),
    ('peripheral','keyboard',r'\bkeyboard\b'),
    ('peripheral','mouse',r'\bmouse\b'),
    ('peripheral','headset',r'\b(?:headset|headphone|earphone)\b'),
    ('peripheral','webcam',r'\bwebcam\b'),
    ('peripheral','gamepad',r'\bgamepad\b'),
    ('network','networking',r'\b(?:router|modem|network switch|access point|mesh wifi|nas)\b'),
]

def gear_type(title):
    return next((kind for _,kind,pattern in GEAR_PATTERNS if re.search(pattern,title,re.I)),None)

def gear_category(title):
    # Compatibility text on a full computer or component is not its product type.
    if re.search(r'\b(?:i[3579][\s-]*\d{4,5}|ryzen\s+(?:ai\s+)?[3579]|xeon|celeron|pentium|core\s+(?:ultra\s+)?[3579])',title,re.I):return None
    if re.search(r'\b(?:motherboard|mainboard|b[45678][456]0[a-z]*|z[678]90[a-z]*)\b',title,re.I):return None
    if re.search(r'\b(?:internal speaker|replacement keyboard|spare keyboard)\b',title,re.I):return 'accessory'
    for category,_,pattern in GEAR_PATTERNS:
        if re.search(pattern,title,re.I):
            if category=='gaming' and re.search(r'\b(?:ssd|nvme|hard drive|ram|memory)\b',title,re.I):continue
            if category=='tablet' and re.search(r'\b(?:case|cover|charger|stand|holder)\b',title,re.I):return 'accessory'
            return category
    return None
BRANDS = [
    ('G.SKILL',r'g[.\s-]*skill'),('TEAMGROUP',r'team\s*group|t[ -]?force'),
    ('Silicon Power',r'silicon\s*power'),('Western Digital',r'western digital|\bwd\b'),
    ('be quiet!',r'be\s*quiet'),('Cooler Master',r'cooler master'),('DeepCool',r'deep\s*cool'),
    ('Kingston',r'kingston'),('Crucial',r'crucial'),('Corsair',r'corsair'),('Lexar',r'lexar'),
    ('ADATA',r'adata'),('XPG',r'xpg'),('HIKSEMI',r'hiksemi'),('Hikvision',r'hikvision'),
    ('KLEVV',r'klevv'),('Patriot',r'patriot'),('PNY',r'pny'),('Samsung',r'samsung'),
    ('Micron',r'micron'),('Apacer',r'apacer'),('Transcend',r'transcend'),('GeIL',r'geil'),
    ('Netac',r'netac'),('OCPC',r'ocpc'),('V-Color',r'v[ -]?color'),('SanDisk',r'sandisk'),
    ('OSCOO',r'oscoo'),('Dahua',r'dahua'),('DATO',r'dato'),('Addlink',r'addlink'),
    ('TwinMOS',r'twinmos'),('GoodRAM',r'goodram'),('ZION',r'zion'),('PLUZZ',r'pluzz'),
    ('KingSpec',r'kingspec'),('Kingmax',r'kingmax'),('Neo Forza',r'neo\s*forza'),
    ('OLOy',r'oloy'),('Asgard',r'asgard'),('JUHOR',r'juhor'),('Vaseky',r'vaseky'),
    ('Seagate',r'seagate'),('Toshiba',r'toshiba'),('HGST',r'hgst'),('SK hynix',r'sk\s*hynix|hynix'),
    ('Lenovo',r'lenovo'),('Dell',r'dell'),('HP',r'hp'),('ASUS',r'asus'),('Acer',r'acer'),
    ('MSI',r'msi'),('Gigabyte',r'gigabyte'),('ASRock',r'asrock'),('AMD',r'amd'),('Intel',r'intel'),
    ('NVIDIA',r'nvidia'),('EVGA',r'evga'),('ZOTAC',r'zotac'),('GALAX',r'galax'),('Palit',r'palit'),
    ('Sapphire',r'sapphire'),('PowerColor',r'power\s*color'),('Gainward',r'gainward'),
    ('Xigmatek',r'xigmatek'),('Antec',r'antec'),('AeroCool',r'aero\s*cool'),('Lian Li',r'lian[ -]?li'),
    ('FSP',r'fsp'),('Seasonic',r'sea\s*sonic'),('Thermaltake',r'thermaltake'),('Gamdias',r'gamdias'),
    ('NZXT',r'nzxt'),('Fractal Design',r'fractal'),('DarkFlash',r'dark\s*flash'),('Redragon',r'redragon'),
    ('BenQ',r'benq'),('AOC',r'aoc'),('ViewSonic',r'view\s*sonic'),('LG',r'lg'),('Philips',r'philips'),
    ('APC',r'apc'),('Eaton',r'eaton'),('CyberPower',r'cyber\s*power'),('Mercury',r'mercury'),
    ('TP-Link',r'tp[ -]?link'),('D-Link',r'd[ -]?link'),('Tenda',r'tenda'),('Ubiquiti',r'ubiquiti'),
    ('Logitech',r'logitech'),('Razer',r'razer'),('SteelSeries',r'steel\s*series'),('HyperX',r'hyper\s*x'),
    ('Apple',r'apple'),('Xander',r'xander'),('Fantech',r'fantech'),('UGREEN',r'ugreen'),
]

def manufacturer(title):
    matches=[]
    for name, pattern in BRANDS:
        match=re.search(r'(?<!\w)(?:'+pattern+r')(?!\w)',title,re.I)
        if match:matches.append((match.start(),name))
    return min(matches)[1] if matches else None

def classify(t):
    t=t.lower()
    gear=gear_category(t)
    if gear:return gear
    if re.search(r'\b(?:smartphone|mobile phone|nothing phone|galaxy|iphone|redmi|poco|oppo|realme|honor|infinix|tecno|ipad|tablet|smartwatch|pixel|oneplus|vivo|zte|micromax|hmd|nokia|dual sim|smart tv|tv box|television|washing machine|refrigerator|dishwasher|air fryer|trimmer|oven|stove|microwave)\b|\bhuawei\s+(?:mate\s*\d|p\s*\d|nova)|\blenovo\s+tab\b|detachable tab',t): return 'other'
    if re.search(r'\b(?:android|4g|5g|lte)\b',t) and not re.search(r'\b(?:router|modem|laptop|notebook|chromebook|workstation|graphics? card|gpu|rtx|gtx|radeon|geforce|ddr[2345]|ssd|nvme)\b',t): return 'other'
    if re.search(r'\b(?:cctv|nvr|dvr|ip camera|security camera|imou|dashcam)\b',t):return 'other'
    if re.search(r'\b(?:usb flash|flash drive|pendrive|micro[ -]?sd|sdxc|sdhc|flash memory|memory card)\b',t):return 'accessory'
    cpu=bool(re.search(r'\b(?:i[3579][\s-]*\d{4,5}[a-z]{0,3}|ryzen\s*(?:ai\s*)?[3579]|threadripper|core\s+(?:ultra\s+)?[3579]|snapdragon\s+x|xeon|celeron|pentium)\b',t))
    family=bool(re.search(r'\b(?:loq|legion|ideapad|thinkpad|thinkbook|yoga|vivobook|zenbook|expertbook|macbook|chromebook|probook|elitebook|zbook|victus|omen|pavilion|spectre|envy|inspiron|latitude|vostro|xps|alienware|aspire|cyborg|katana|raider|prestige)\b|\btuf(?:\s+gaming)?\s+[af]\d{2}\b|\bacer\s+(?:swift|nitro\s+(?:v|[57]))\b|\bmsi\s+(?:thin|sword|modern|vector|crosshair|pulse|titan|summit|creator|stealth)\b|\bgigabyte\s+(?:gaming\s+)?a(?:16|17)\b|\blenovo\s+v(?:14|15|17)\b|\bdell\s+(?:precision|g(?:15|16)|pro\s+(?:14|15|16))\b|\bhp\s+(?:240|245|250|255)\b',t))
    # A physical component or accessory must not become a computer because its
    # compatibility text mentions "gaming PC", "all in one" or a laptop family.
    if re.search(r'\b(?:phone|iphone|airpods|galaxy|tablet)\b',t) and re.search(r'\b(?:case|cover|screen|charger)\b',t): return 'other'
    if re.search(r'\b(?:pc case|computer case|atx case|mid[ -]?tower (?:pc )?case|panoramic stealth|full tower.*case)\b',t): return 'case'
    if re.search(r'\b(?:cpu|processor|liquid|air) cooler\b|\b(?:aio|all[ -]in[ -]one).*cooler\b|\bmasterliquid\b',t): return 'cooler'
    if re.search(r'\b(?:motherboard|mainboard)\b',t) and not (cpu and family) and not re.search(r'\b(?:bundle|bundel|buindle)\b',t) and t.count('+')<2:return 'motherboard'
    if re.search(r'\b(?:external lan card|kvm switcher|usb[ -]?c hub|toploader|protective case|brush heads|laptop cooling table|laptop kickstand|briefcase|daypack|changing liquid metal|cooler laptop|laptop (?:stand|bag|sleeve|battery|charger)|cooling pad|(?:replacement|spare) (?:keyboard|battery|screen)|lcd panel|wall charger|power bank)\b',t): return 'accessory'
    if re.search(r'\b(?:hinges?|housing|flat|internal fan|internal speaker|socket|connector|cable|screwdriver|cleaning|protector|safety lock|storage upgrade|hard shell case|hdd cover|dvd drive)\b',t) and not cpu: return 'accessory'
    if re.search(r'\b(?:monitor|projector)\b|\bmsi\s+modern\s+md\d|\blegion\s+(?:24|25|27|32|34)-\d',t) or ('benq' in t and not cpu): return 'monitor'
    if re.search(r'\blegion\s+go\b',t): return 'other'
    if re.search(r'\b(?:router|network switch|access point|mesh wifi|ethernet card|network adapter|usb[ -]?hub|docking|dock|nas)\b',t): return 'network'
    if re.search(r'\b(?:keyboard|mouse|headset|headphone|earphone|webcam|gamepad)\b',t) and not cpu: return 'peripheral'
    if re.search(r'\b(?:backpack|bag|sleeve|adapter|charger)\b',t) and not cpu: return 'accessory'
    # Camera/CCTV/LED/router DC supplies and mini DC UPS units are not PC power gear.
    if re.search(r'\b(?:camera|cctv|led|router|poe|dc)\s+(?:power\s+supply|ups)\b|\bmini\s+(?:dc\s+)?ups\b|\b(?:power supply|ups)\b.*\b12\s*v\b|\b12\s*v\b.*\b(?:power supply|ups)\b',t) and not re.search(r'\b(?:atx|80\s*(?:\+|plus)|\d{3,4}\s*va)\b',t): return 'accessory'
    if re.search(r'\b(?:power supply|psu)\b|\b\d{3,4}\s*w\b.*\b80\s*(?:\+|plus)',t) and not cpu:return 'psu'
    if re.search(r'\b(?:full pc|used pc|gaming pc|desktop pc|mini pc|mini computer|intel nuc|deskmini|tower workstation|tower pc|كمبيوتر كامل|تجميعة)\b',t) or re.search(r'\b(?:precision\s+(?:58\d0|36\d0|t[357]\d{3})|prodesk|elitedesk|optiplex|thinkcentre)\b',t): return 'pc'
    if re.search(r'\bmsi\s+modern\s+am\d|\ball[ -]in[ -]one\s+(?:pc|computer|desktop)\b',t): return 'pc'
    if not family and ((cpu and (t.count('+')>=2 or t.count('|')>=2)) or re.search(r'\b(?:bundle|bundel|buindle)\b',t)):
        complete=bool(re.search(r'\b(?:rtx|gtx|rx\s*\d{4})\b',t) and re.search(r'\b(?:ssd|nvme)\b',t) and re.search(r'\b(?:ddr[2345]|ram)\b',t) and re.search(r'\b(?:case|psu|power supply|bronze)\b',t))
        return 'pc' if complete else 'bundle'
    if re.search(r'\b(?:motherboard|mainboard|لوحة ام)\b',t) or (re.search(r'\b(?:b[45678][456]0e?|a[356]20|z[678]90|x[5678]70e?|h[4567]10)[a-z-]*\b',t) and not (cpu and (family or 'laptop' in t))): return 'motherboard'
    if re.search(r'\b(?:power supply|psu)\b|\b\d{3,4}\s*w\b.*\b80\s*(?:\+|plus)',t) and not cpu: return 'psu'
    if re.search(r'\bups\b|uninterruptible power',t): return 'ups'
    if re.search(r'\b(?:ram laptop|laptop ram|sodimm|so-dimm|laptop memory|notebook memory|ram for (?:laptop|notebook|pc))\b',t) and not re.search(r'\b(?:ssd|nvme|solid state|hard drive|hdd)\b',t) and not (cpu and (family or re.search(r'\b(?:laptop|notebook)\b',t))): return 'ram'
    if re.search(r'\b(?:hard drive|hard disk|hdd)\b',t) and not (cpu and family): return 'hdd'
    if re.search(r'\b(?:ssd|nvme|solid state)\b',t) and not (cpu and (family or re.search(r'\b(?:laptop|notebook)\b',t))):
        if not family or manufacturer(t) in {'Crucial','HIKSEMI','Hikvision','KLEVV','Seagate','Kingston','Western Digital','SanDisk','Lexar','Samsung','ADATA','XPG','Silicon Power'}: return 'ssd'
    if family or re.search(r'\b(?:laptop|notebook|لابتوب|لاب توب)\b',t): return 'laptop'
    if cpu:return 'cpu'
    if re.search(r'\b(?:rtx|gtx|gt\s*\d{3,4}|quadro|firepro|radeon|graphics card|graphic card|geforce|rx\s*\d{4}|arc\s+[ab]\d{3})\b',t): return 'gpu'
    if re.search(r'\b(?:ram|memory|sodimm|so-dimm|[ru]?dimm|ddr[2345])\b',t): return 'ram'
    if cpu or re.search(r'\b(?:processor|cpu)\b',t): return 'cpu'
    if re.search(r'\b(?:bundle|bundel)\b',t): return 'bundle'
    if re.search(r'\bcase\b|\b(?:chassis|(?:mid|full|mini)[ -]?tower)\b',t): return 'case'
    if re.search(r'\b(?:unmanaged|managed|poe\+?|gigabit|sfp\+?|patch panel|transceiver)\b',t) and re.search(r'\b(?:switch|ports?|sfp\+?|panel|transceiver|router)\b',t): return 'network'
    if re.search(r'\b\d{2,3}\s*mm\b.*\bfans?\b|\bfans?\b.*\b(?:argb|pwm|rgb)\b|\bcase fans?\b|\bargb\b.*\bfans?\b',t): return 'cooler'
    return 'other'
