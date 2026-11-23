import os
import re
import sys
import warnings
from typing import Dict, List, Set, Tuple

import requests
from urllib3.exceptions import InsecureRequestWarning

OUTPUT_FILE = os.getenv("OUTPUT_FILE", "mola.m3u")
INITIAL_CURSORS = list(range(0, 15000, 100))

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

COUNTRIES: Dict[int, Tuple[str, str]] = {
    1: ("Turkey", "Türkiye"),
    2: ("Germany", "Almanya"),
    3: ("France", "Fransa"),
    4: ("France Sport", "Fransa Sport"),
    5: ("Spain", "İspanya"),
    6: ("Italy", "İtalya"),
    7: ("Netherlands", "Hollanda"),
    8: ("United Kingdom", "Birleşik Krallık"),
    9: ("Portugal", "Portekiz"),
    10: ("Russia", "Rusya"),
    11: ("Poland", "Polonya"),
    12: ("Romania", "Romanya"),
    13: ("Balkans", "Balkanlar"),
    14: ("Albania", "Arnavutluk"),
    15: ("Bulgaria", "Bulgaristan"),
    16: ("Arabia", "Arabistan"),
}

CATEGORY_PRIORITY: Dict[str, int] = {
    "TR Spor": 1,
    "TR Ulusal": 2,
    "TR Haber": 3,
    "TR Film": 4,
    "TR Belgesel": 5,
    "TR Çocuk": 6,
    "TR Müzik": 7,
    "TR Dini": 8,
    "TR Yaşam": 9,
    "TR Yerel": 10,
    "TR Radyo": 11,
    "TR Diğer": 12,
}


def clean_channel_name(name):
    if not name:
        return "Bilinmeyen Kanal"

    s = str(name)
    s = re.sub(r"^\s*(?:4K\s*)?TR\s*:\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*\.[bcs]\b", "", s, flags=re.IGNORECASE)
    s = re.sub(
        r"\s+(?:4K|UHD|FHD|HD\+|HD|SD|HEVC|RAW|H265|H\.265|FEED)(?=\s|$)",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"S\s*[\x00-\x1F\x7F-\xFF?\s]*NEMA", "SINEMA", s, flags=re.IGNORECASE)
    s = re.sub(r"DREAM\s*T\s*R\s*K", "DREAM TURK", s, flags=re.IGNORECASE)
    s = re.sub(r"MINICA", "MINIKA", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)

    return s.strip()


def normalize_for_category(name):
    s = clean_channel_name(name)

    char_map = {
        "Ç": "C", "ç": "c",
        "Ğ": "G", "ğ": "g",
        "İ": "I", "I": "I", "ı": "i",
        "Ö": "O", "ö": "o",
        "Ş": "S", "ş": "s",
        "Ü": "U", "ü": "u",
        "Â": "A", "â": "a",
        "Î": "I", "î": "i",
        "Û": "U", "û": "u",
    }
    for k, v in char_map.items():
        s = s.replace(k, v)

    search_patterns = [
        r"\bT RK\b", r"\bT RKIYEM\b", r"\bBENG\b", r"\bBENGT\b", r"\bAK T\b",
        r"\bS\s*NEMA\b", r"\bM N KA\b", r"\bOCUK\b", r"\bM\s*Z\s*K\b", r"\bS ZC\b",
        r"\bSZC\b", r"\bLKE\b", r"\bYE IL AM\b", r"\bYE IL[ ]?CAM\b", r"\bT[ÜU]RK\b",
        r"\bCI\s*EVERSE\b", r"\bBARIS\s*MANCO\b", r"\bRUMEL\b", r"\bLALEGUL\b",
    ]
    replace_values = [
        "TURK", "TURKIYEM", "BENGU", "BENGUT", "AKIT", "SINEMA", "MINIKA",
        "COCUK", "MUZIK", "SOZCU", "SOZCU", "ULKE", "YESILCAM", "YESILCAM", "TURK",
        "CINEVERSE", "BARIS MANCO", "RUMELI", "LALEGUL",
    ]

    for pat, rep in zip(search_patterns, replace_values):
        s = re.sub(pat, rep, s, flags=re.IGNORECASE)

    return s


def has_sport_keyword(name: str) -> bool:
    s = normalize_for_category(name)
    sport_pattern = (
        r"BEIN SPO[RT]{0,3}S?|BEIN\s*1|S[- ]?SPORTS?|\bS SPORT\b|SPOR SMART|"
        r"EUROSPORT|\bNBA\b|TJK TV|TIVIBU ?SPOR|TIVIBUSPOR|TRT SPOR|TABII SPOR|"
        r"EXXEN SPO[RT]?|\bHT SPOR\b|EKOL SPOR|SPORTS TV|IDMAN TV|GALATASARAY TV|"
        r"\bFB TV\b|\bGS TV\b|SARAN SPORT|SMART SPOR|SPOR|SPORT"
    )
    return bool(re.search(sport_pattern, s, flags=re.IGNORECASE))


def categorize_channel(name):
    s = normalize_for_category(name)

    if re.search(r"KARADENIZ\s*BRT", s, flags=re.IGNORECASE):
        return "TR Diğer"

    rules = {
        "TR Spor": r"BEIN SPO[RT]{0,3}S?|BEIN\s*1|S[- ]?SPORTS?|\bS SPORT\b|SPOR SMART|EUROSPORT|\bNBA\b|TJK TV|TIVIBU ?SPOR|TIVIBUSPOR|TRT SPOR|TABII SPOR|EXXEN SPO[RT]?|\bHT SPOR\b|EKOL SPOR|SPORTS TV|IDMAN TV|GALATASARAY TV|\bFB TV\b|\bGS TV\b|SARAN SPORT|SMART SPOR|SPOR|SPORT",
        "TR Radyo": r"\b(RADIO|RADYO)\b|\b(FM|MBAT FM|EFKAR FM|FMTV|F ?M)\b(?!\s*TV)|POWERTURK|POWER FM|SHOW RADYO|ALEM (?:FM|RADYO)|BABA RADYO|KRAL POP RADYO|PAL STATION|X NOSTALJI|RADIO ROCK|STANBUL FM",
        "TR Çocuk": r"CARTOON|BOOMERANG|DISNEY|NICK(?:ELODEON|TOONS|JR|JUNIOR|\b)|BABY ?TV|BABYTV|MINIKA|MINICA|POKEMON|ANIMATION|ANIMASYON|TRT ?COCUK|COCUK HD|\bCOCUK\b|ANKA|BEN ?10|ANGRY BIRDS|CAILLOU|PEPPA|PEPE|HEIDI|SIRINLER|TOM & JERRY|SUNGER|SUNGER\s*BOB|SPIDERMAN|BARBIE|PIJAMA|PIRIL|RAFADAN|KELOGLAN|KUKULI|KUKILI|KOSTEBEK|CHICKY|BOOBA|WAKFU|GABBY|TAYO|NILOYA|PISI|LEYLEK|MASAL|CANIM KARDESIM|ADIBESA|MOMO|ALVIN|VIKINGLER|TRANSFORMERS|TROL AVCILARI|SMART\s*COCUK|COCUK\s*SMART|ILAHI COCUK|CILGIN ORMAN|KRAL SAKIR|SERCE KUS|ITFAYECI SAM|MUFFETIS|MAYMUNLAR|ELIF VE|ELIFIN|MIMOCAN|HAPSUU|RUYA TRENI|MASA KOCAAYI|PAK PIRPIR|LIMON ZEYTIN|GONCA TV|NASREDDIN|SEKER HOCA|SEVIMLI DOSTLAR|PAW PETROL|OSCAR COLLERDE|SL NILOYA|CBEEBIES|DUCK TV|JIM ?JAM|ENGLISH CLUB TV|EBA TV|TAVSAN|PATRON BEBEK|DIYARI|BAHA\b|SEF ROKKA|BULMACA KULESI|AKILLI TAVSAN|AKLILI|DA VINC KIDS|DA VINCI KIDS|DINAMIK ANIMASYON|BEST ANIMASYON|YILDIZ KIZ|KONUSAN TOM|JURASSIC WORLD|MONTAG|64\s*KARE",
        "TR Belgesel": r"DISCOVERY|NATIONAL GEOGRAPHIC|NAT ?GEO|\bHISTORY\b|ANIMAL PLANET|DA VINCI(?! KIDS)|VIASAT|BBC EARTH|LOVE NATURE|TRT BELGESEL|EPIC DRAMA|TARIH TV|TARIM TV|TGRT BELGESEL|INVESTIGATION|DMAX|DOCUBOX|DOCU SCREEN|SCIENCE|\bIZ TV\b|YABAN|OUTDOOR|CHASSE|ANIMAUX|AGRO TV|CIFTCI TV|REDBULL TV|\bTLC\b",
        "TR Yaşam": r"24 KITCHEN|GURME|BEIN GURME|LIFESTYLE|\bLIFE TV\b|FASHION|WM TV|EGE ILE GAGA|24 RAW|\bTVEM\b|\bTV EM\b|AUTOMOTO|LINE TV|BILGILENDIRME|WOMAN|TELEGRAM",
        "TR Haber": r"(?:^|\b)24(?:\s*TV|\s*HABER)?(?:\b|$)|\bTV\s*24\b|HABER|\bNEWS\b|BLOOMBERG|\bCNN\b|EKOTURK|\bEKO ?TURK\b|\bEKOL\b|A ?PARA|APARA|PARANIN|HALK TV|TELE ?1|SOZCU|\bSZC\b|BENGU|BENGUTURK|TRT WORLD|TRT HABER|\bDHA\b|LIDER HABER|FLASH|FLASH HABER|MEDYA HABER|GLOBAL HABER|TRABZON HABER|BEIN SPORTS HABER|TURKHABER|HABERTURK|\bARTI TV\b|\bAKIT\b|TVNET|TV NET|MELTEM|A HABER|ULKE|A NEWS|KRT|ULUSAL",
        "TR Film": r"CINEVERSE|CI\s*EVERSE|DREAM|DINAMIK\s*TURK|SINEMA|CINEMA|CINEMALAR|GLOBALLER|SINEMAX|SINEVIZYON|\bMOVIES?\b|MOVIEMAX|MOVIESMART|BEIN MOVIES|BEIN BOX|BOX OFFICE|\bFX\b|FX HD|YESILCAM|GLOBAL BOX|PROTURK|FIX CINEMA|KINGBOX|ARENA BOX|SHOWMAX|SHOW MAX|REAL BOX|SMART BOX|BEST (?:AKSIYON|BILIMKURGU|DRAM|HABABAM|IMBD|KOMEDI|KORKU|LOCA|NETFLIX|SALON|SAVAS|TURK|WESTERN|YESILCAM)|MAX|\bLOCA\b|\bSALON\b|\bVIZYON\b|AKSIYON|KOMEDI|\bKORKU\b|\bDRAM\b|WESTERN|BILIM ?KURGU|\bSAVAS\b|\bIMBD\b|\bIMDB\b|\bFILM\b|FILMBOX|HORROR|OSCAR|KEMAL SUNAL|KEMAL SUNA|\b007\b|\bCINE ?1\b|SIFIR TV|SON C BOOM|\bYERLI\b|SPIDERMAN(?! TV)|ARENA BOX|MOVIE SMART|\bMTURK TV\b|SERIES|\bDIZI\b|BEIN SERIES|DIZISMART",
        "TR Ulusal": r"\bTRT\b|\bTRT 1\b|\bTRT ?2\b|TRT2|\bTRT 3\b|TRT AVAZ|TRT TURK|TRT KURDI|TRT 4K|TRT EBA|\bKANAL D\b|\bATV\b|ATV AVRUPA|ATV EUROPA|STAR TV|\bSTAR\b|STAR HD|SHOW TV|SHOW TURK|\bSHOW\b|\bFOX\b|NOW ?TV|\bNOW\b|TV ?8|TV8[.,]5|BEYAZ TV|BEYAZ HD|\bBEYAZ\b|\b360\b|\bA2\b|TV ?100|TV ?4|TEVE ?2|TEVE2|CNN TURK|\bBRT ?[0-9]|\bBRTV\b|EURO ?D|EURO ?STAR|\bNTV\b|EXXEN TV|TIVITURK|TABII|OLAY TURK|KANAL AVRUPA|\bKANAL 7\b|KANAL 7 (?:AVRUPA|EUROPA)|EURO D|EURO STAR|SHOW TV EUROPA|TGRT EU|DUGUN TV|\bTBMM\b|\bTV 1\b|TVO TV|BEIN IZ",
        "TR Müzik": r"TRT\s*MZK|TRT\s*MUZIK|90LAR|90\s*LAR|BARIS\s*MANCO|ROCK|TEMPO|RUMEL|POP|MUZIK|M\s*Z\s*K|POWER TURK|POWER ?TV|POWERTURK|POWER (?:DANCE|LOVE|HD)|\bPOWER\b|KRAL POP|KRAL ?TV|\bKRAL\b|NR ?1|NUMBER ?1|NUMBER ONE|DAMAR|ARABESK|AKUSTIK|AHMET KAYA|IBRAHIM ERKAL|IBRAHIM TATLISES|\bTATLISES\b|ZERRIN OZER|SEZEN AKSU|TARKAN|SELDA BAGCAN|CENGIZ KURTOGLU|MAHSUN KIRMIZIGUL|MUSLUM GURSES|YILDIZ TILBE|FERDI TAYFUR|\bFERDI\b|DURSUN AL|MTV LIVE|VINTAGE MUSIC|RETRO TURK|TURKCE POP|TURKCE KLASIK|SLOW KARADENIZ|\bSLOW\b|\bZARA\b|\bSONER ARICA\b|\bFM TV\b|\bFMTV\b|REDBOX",
        "TR Dini": r"LALEGUL|DIYANET|MEHTAP|HILAL|KUDUS|SEMERKAND|MERCAN TV|VUSLAT|KARDELEN|DIYAR TV|\bDOST TV\b|\bYOL TV\b|HAYAT|HAYIRLI|HZ MERYEM|HZ OMER|HZ YUSUF|MAM EBU|ASHABI KEHF|HASAN VE HUSEYIN|SAT ?7 TURK|TRT DIYANET|\bTV ?5\b|\bTV5\b|REHBER|ILAHI|ILKE TV|MESAJ TV|SURELER|TURKCE MEAL|DURSUN AL ERZINCANLI|YUNUS EMRE|CEM TV|BARBAROS TV|ASLAN TV|TYT TURK|SATRANC|FASIL",
        "TR Yerel": r"TVDEN|TV DEN|ADANA|ADIYAMAN|AFYON|AKSARAY|ALANYA|ANAKKALE|\bANKARA\b|ANKA TV|ANKARA TURKIYEM|SANLIURFA|ANTALYA|\bBURSA\b|ELAZIG|ERCIS|ERZURUM|ESKISEHIR|\bES TV\b|\bER TV\b|ETV KAYSERI|ETV MANISA|GAZIANTEP|\bICEL\b|KAHRAMANMARAS|KAYSERI|KOCAELI|KON TV|KONYA|MALATYA|MERSIN|ORDU|ALTAS TV|SIVAS|TRABZON|TUNCELI|DERSIM|\bURFA\b|IZMIR TV|TON TV|KIBRIS|EDIRNE|DENIZLI|\bKAY TV\b|KENT TURK|HUNAT|\bOBB\b|KANAL 12|KANAL 15|KANAL 23|KANAL 24|KANAL 26|KANAL 3\b|KANAL 32|KANAL 33|KANAL 34|KANAL 360|KANAL 42|KANAL 58|KANAL 68|KANAL FIRAT|KANAL URFA|KANAL V\b|\bKANAL Z\b|KANAL T\b|KANAL HAYAT|GUNEYDOGU|\bEGE\b|TEK RUMELI|YENI KOCAELI|OLAY TV|\bGRT\b|SUN RTV|SUN TV|\bKOY TV\b|IZMIR|TIVI 6|TV 41|TV 42|TV 52|TV 264|KOZA TV|MC EU|MERCAN|KADIRGA|\bFANATIK\b|AS TV|ISVI|GURBET24|T.A.Y|TAY TV|\bTAY\b|\bTMB\b|AV TV|MAVI KARADENIZ|EGE ILE GAGA|GAZIANTEP GRT|VIYANA TV|LUYS|EDESSA|BIR TV|ANADOLU|DIYAR|ERTV|HRT|VIZYON 58|ADA TV|CAN TV|DEHA|SIFIR|EKIN TURK|AFROTURK|ARAS|ARKADAG|VATAN|DORU|AKSU TV|KARE TV|ON 4|ON 6|PAMUKKALE|UCANKUS|DENIZ POSTASI",
    }

    for cat, pattern in rules.items():
        if re.search(pattern, s, flags=re.IGNORECASE):
            return cat

    return "TR Diğer"


def get_sort_key(ch: Dict[str, str], country_order: int) -> Tuple[int, str, str]:
    group = ch["group"]
    if group in CATEGORY_PRIORITY:
        return (CATEGORY_PRIORITY[group], group.lower(), ch["name"].lower())
    return (100 + country_order, group.lower(), ch["name"].lower())


def fetch_group(
    session: requests.Session,
    eng_name: str,
    tr_name: str,
    use_tr_group_title: bool = False,
) -> List[Dict[str, str]]:
    channels: List[Dict[str, str]] = []
    seen_entries: Set[Tuple[str, str]] = set()
    visited_cursors: Set[int] = set()
    cursor_queue: List[int] = list(INITIAL_CURSORS)
    idx = 0
    consecutive_empty = 0

    while idx < len(cursor_queue):
        cursor = cursor_queue[idx]
        idx += 1
        if cursor in visited_cursors:
            continue
        visited_cursors.add(cursor)

        url = (
            "https://geil.to/live/catalog/live/channels.json"
            f"?region=TR&language=tr&sort=name&filter[group]={eng_name}&cursor={cursor}"
        )
        try:
            response = session.get(url, timeout=15, verify=False)
            response.raise_for_status()
            payload = response.json()

            if isinstance(payload, dict):
                items = payload.get("items", [])
                next_cursor = payload.get("next_cursor") or payload.get("cursor_next")
                if isinstance(next_cursor, int) and next_cursor > cursor and next_cursor not in visited_cursors:
                    cursor_queue.append(next_cursor)
            elif isinstance(payload, list):
                items = payload
            else:
                items = []

            if not items:
                consecutive_empty += 1
                if consecutive_empty >= 3 and cursor > 1000:
                    break
                continue

            consecutive_empty = 0
            new_added_in_page = 0

            for item in items:
                if not isinstance(item, dict):
                    continue
                ch_id = str(item.get("id") or "").strip()
                raw_name = str(item.get("name") or "").strip()
                tvg_id = str(item.get("tvg_id") or "").strip()

                if not ch_id or not raw_name:
                    continue

                cleaned_name = clean_channel_name(raw_name)

                if eng_name == "Turkey":
                    primary_group = categorize_channel(raw_name)
                    target_groups = [primary_group]
                    if has_sport_keyword(raw_name) and "TR Spor" not in target_groups:
                        target_groups.append("TR Spor")
                else:
                    target_groups = [tr_name if use_tr_group_title else eng_name]

                for group_label in target_groups:
                    entry_key = (ch_id, group_label)
                    if entry_key in seen_entries:
                        continue
                    seen_entries.add(entry_key)
                    channels.append({
                        "id": ch_id,
                        "name": cleaned_name,
                        "group": group_label,
                        "tvg_id": tvg_id,
                    })
                    new_added_in_page += 1

            if len(items) >= 50 and new_added_in_page > 0:
                next_guess = cursor + len(items)
                if next_guess not in visited_cursors and next_guess not in cursor_queue:
                    cursor_queue.append(next_guess)

        except Exception:
            continue

    return channels


def build_m3u_content(channels: List[Dict[str, str]]) -> str:
    lines = ["#EXTM3U"]
    for ch in channels:
        ch_id = ch["id"]
        name = ch["name"].replace("\n", " ").replace("\r", " ")
        group = ch["group"]
        tvg_id = ch["tvg_id"]
        lines.append(f'#EXTINF:-1 tvg-id="{tvg_id}" group-title="{group}",{name}')
        lines.append(f"http://vavoo.net/live2/play3/{ch_id}.m3u8")
    return "\n".join(lines) + "\n"


def main() -> int:
    all_channels: List[Tuple[int, Dict[str, str]]] = []
    use_tr_groups = os.getenv("USE_TR_GROUPS", "false").lower() in ("1", "true", "yes")

    headers = {
        "Accept": "application/json",
        "Referer": "https://geil.to/",
        "User-Agent": "AirTV-STB/1.0.0",
    }

    with requests.Session() as session:
        session.headers.update(headers)
        for country_order, (eng_name, tr_name) in COUNTRIES.items():
            group_channels = fetch_group(session, eng_name, tr_name, use_tr_group_title=use_tr_groups)
            for ch in group_channels:
                all_channels.append((country_order, ch))

    all_channels.sort(key=lambda item: get_sort_key(item[1], item[0]))
    sorted_channels = [ch for _, ch in all_channels]

    m3u_content = build_m3u_content(sorted_channels)

    out_dir = os.path.dirname(OUTPUT_FILE)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(m3u_content)

    return 0


if __name__ == "__main__":
    sys.exit(main())
