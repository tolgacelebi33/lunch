#!/usr/bin/env python3
"""
Updater for Dagens lunch.

Safe design:
- Never converts stale menus into today's menu.
- Existing verified values remain until a new verified value is available.
- Instagram/Glasets Hus is deliberately adapter-based. Put an official API
  implementation in fetch_glassets_hus() when credentials are available.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "lunch.json"
TZ = ZoneInfo("Europe/Stockholm")

def fetch_glassets_hus():
    # Production hook:
    # 1. Instagram Graph API for @glasetshuslimmared if account/API access is granted.
    # 2. Find latest weekly-menu media.
    # 3. Extract caption/image menu.
    # 4. Accept only current ISO week.
    #
    # Returning None is intentional: never fabricate data when source access fails.
    return None

def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    now = datetime.now(TZ)
    data["updated_at"] = now.strftime("%Y-%m-%d %H:%M")

    gh = fetch_glassets_hus()
    if gh:
        for r in data["restaurants"]:
            if r["name"] == "Glasets Hus":
                r["menu"].update(gh)

    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
