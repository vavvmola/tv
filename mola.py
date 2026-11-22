import os
import sys
import warnings
from typing import Dict, List, Tuple

import requests
from urllib3.exceptions import InsecureRequestWarning

OUTPUT_FILE = os.getenv("OUTPUT_FILE", "mola.m3u")

warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# (İngilizce grup adı, Türkçe karşılığı)
COUNTRIES: Dict[int, Tuple[str, str]] = {
    1: ("Turkey", "Türkiye"),
    2: ("Spain", "İspanya"),
    3: ("Balkans", "Balkanlar"),
    4: ("France", "Fransa"),
    5: ("Romania", "Romanya"),
    6: ("Italy", "İtalya"),
    7: ("Portugal", "Portekiz"),
    8: ("Poland", "Polonya"),
    9: ("Netherlands", "Hollanda"),
    10: ("Russia", "Rusya"),
    11: ("United Kingdom", "Birleşik Krallık"),
    12: ("Albania", "Arnavutluk"),
    13: ("Bulgaria", "Bulgaristan"),
    14: ("Germany", "Almanya"),
    15: ("Arabia", "Arabistan"),
}

CURSORS = [0, 300, 600, 900, 1200]


def fetch_group(group_name: str, tr_name: str, use_tr_group_title: bool = False) -> List[Dict]:
    channels: List[Dict] = []
    seen_ids = set()
    headers = {
        "Accept": "application/json",
        "Referer": "https://geil.to/",
        "User-Agent": "AirTV-STB/1.0.0",
    }

    group_label = tr_name if use_tr_group_title else group_name

    for cursor in CURSORS:
        url = (
            "https://geil.to/live/catalog/live/channels.json"
            f"?region=TR&language=tr&sort=name&filter[group]={group_name}&cursor={cursor}"
        )
        try:
            response = requests.get(url, timeout=15, verify=False, headers=headers)
            response.raise_for_status()
            payload = response.json()
            items = payload.get("items", []) if isinstance(payload, dict) else []
            if not items:
                break

            for item in items:
                ch_id = item.get("id")
                if not ch_id or ch_id in seen_ids:
                    continue
                seen_ids.add(ch_id)
                channels.append({
                    "id": str(ch_id).strip(),
                    "name": str(item.get("name", ch_id)).strip(),
                    "group": group_label,
                    "tvg_id": str(item.get("tvg_id") or "").strip(),
                })
        except Exception as exc:
            print(f"[Uyarı] {group_name} (cursor={cursor}) alınırken hata: {exc}", file=sys.stderr)
            break

    return channels


def build_m3u_content(channels: List[Dict]) -> str:
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
    all_channels: List[Dict] = []
    use_tr_groups = os.getenv("USE_TR_GROUPS", "false").lower() in ("1", "true", "yes")

    for _, (eng_name, tr_name) in COUNTRIES.items():
        group_channels = fetch_group(eng_name, tr_name, use_tr_group_title=use_tr_groups)
        print(f"{tr_name} ({eng_name}): {len(group_channels)} kanal bulundu.")
        all_channels.extend(group_channels)

    m3u_content = build_m3u_content(all_channels)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print(f"Tamamlandı: {OUTPUT_FILE} (Toplam {len(all_channels)} kanal)")
    return 0


if _name_ == "_main_":
    raise SystemExit(main())
