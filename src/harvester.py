import os
import re
import json
import time
import random
import sqlite3
from dataclasses import dataclass
from typing import List, Dict, Optional

import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright


def env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    pinterest_email: str
    pinterest_password: str
    pinterest_headless: bool
    pinterest_locale: str
    keywords: List[str]
    max_pins_per_keyword: int
    scroll_rounds: int
    sleep_min: float
    sleep_max: float
    eagle_api_base: str
    eagle_token: str
    eagle_folder_id: str
    eagle_tags: List[str]
    db_path: str


class StateDB:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_pins (
                pin_id TEXT PRIMARY KEY,
                image_url TEXT,
                keyword TEXT,
                imported_at INTEGER
            )
            """
        )
        self.conn.commit()

    def seen(self, pin_id: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM seen_pins WHERE pin_id = ?", (pin_id,)).fetchone()
        return row is not None

    def mark_seen(self, pin_id: str, image_url: str, keyword: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO seen_pins(pin_id, image_url, keyword, imported_at) VALUES (?, ?, ?, ?)",
            (pin_id, image_url, keyword, int(time.time())),
        )
        self.conn.commit()


class EagleClient:
    def __init__(self, base_url: str, token: str, folder_id: str, tags: List[str]):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.folder_id = folder_id
        self.tags = tags

    def add_from_url(self, image_url: str, name: str, website: str, tags: Optional[List[str]] = None) -> bool:
        payload = {
            "url": image_url,
            "name": name,
            "website": website,
            "tags": (tags or []) + self.tags,
            "folderId": self.folder_id or None,
            "token": self.token or None,
        }
        payload = {k: v for k, v in payload.items() if v not in (None, "")}
        r = requests.post(f"{self.base_url}/api/item/addFromURL", json=payload, timeout=20)
        if r.status_code != 200:
            print(f"[Eagle] HTTP {r.status_code}: {r.text[:200]}")
            return False
        try:
            data = r.json()
        except Exception:
            print(f"[Eagle] Non-JSON response: {r.text[:200]}")
            return False
        if data.get("status") != "success":
            print(f"[Eagle] Failed: {json.dumps(data, ensure_ascii=False)}")
            return False
        return True


def load_config() -> Config:
    load_dotenv()
    keywords = [k.strip() for k in os.getenv("PINTEREST_KEYWORDS", "").split(",") if k.strip()]
    tags = [t.strip() for t in os.getenv("EAGLE_TAGS", "").split(",") if t.strip()]
    return Config(
        pinterest_email=os.getenv("PINTEREST_EMAIL", ""),
        pinterest_password=os.getenv("PINTEREST_PASSWORD", ""),
        pinterest_headless=env_bool("PINTEREST_HEADLESS", True),
        pinterest_locale=os.getenv("PINTEREST_LOCALE", "ko-KR"),
        keywords=keywords,
        max_pins_per_keyword=int(os.getenv("MAX_PINS_PER_KEYWORD", "30")),
        scroll_rounds=int(os.getenv("SCROLL_ROUNDS", "8")),
        sleep_min=float(os.getenv("RANDOM_SLEEP_MIN", "0.8")),
        sleep_max=float(os.getenv("RANDOM_SLEEP_MAX", "1.8")),
        eagle_api_base=os.getenv("EAGLE_API_BASE", "http://127.0.0.1:41595"),
        eagle_token=os.getenv("EAGLE_TOKEN", ""),
        eagle_folder_id=os.getenv("EAGLE_FOLDER_ID", ""),
        eagle_tags=tags,
        db_path=os.getenv("DB_PATH", "./data/state.db"),
    )


def jitter(cfg: Config):
    time.sleep(random.uniform(cfg.sleep_min, cfg.sleep_max))


def pinterest_login(page, cfg: Config):
    if not cfg.pinterest_email or not cfg.pinterest_password:
        print("[WARN] PINTEREST_EMAIL/PASSWORD not set. Trying without login.")
        return

    page.goto("https://www.pinterest.com/login/", wait_until="domcontentloaded", timeout=45000)
    jitter(cfg)

    try:
        page.fill("input[name='id']", cfg.pinterest_email)
        page.fill("input[name='password']", cfg.pinterest_password)
        page.click("button[type='submit']")
        page.wait_for_timeout(4000)
        print("[INFO] Pinterest login attempted")
    except Exception as e:
        print(f"[WARN] Login flow not completed: {e}")


def extract_pin_id(url: str) -> Optional[str]:
    m = re.search(r"/pin/(\d+)", url)
    if m:
        return m.group(1)
    return None


def collect_for_keyword(page, cfg: Config, keyword: str) -> List[Dict[str, str]]:
    q = keyword.replace(" ", "%20")
    url = f"https://www.pinterest.com/search/pins/?q={q}"
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    jitter(cfg)

    for _ in range(cfg.scroll_rounds):
        page.mouse.wheel(0, random.randint(1800, 2600))
        jitter(cfg)

    pins = []
    anchors = page.query_selector_all("a[href*='/pin/']")

    for a in anchors:
        href = a.get_attribute("href") or ""
        if not href:
            continue
        if href.startswith("/"):
            href = "https://www.pinterest.com" + href
        pin_id = extract_pin_id(href)
        if not pin_id:
            continue

        img_url = ""
        try:
            img = a.query_selector("img")
            if img:
                img_url = img.get_attribute("src") or ""
        except Exception:
            pass

        if not img_url:
            continue

        pins.append({"pin_id": pin_id, "pin_url": href, "image_url": img_url, "keyword": keyword})

    uniq = {}
    for p in pins:
        uniq[p["pin_id"]] = p
    result = list(uniq.values())[: cfg.max_pins_per_keyword]
    return result


def run():
    cfg = load_config()
    if not cfg.keywords:
        raise SystemExit("PINTEREST_KEYWORDS is empty. Set keywords in .env")

    state = StateDB(cfg.db_path)
    eagle = EagleClient(cfg.eagle_api_base, cfg.eagle_token, cfg.eagle_folder_id, cfg.eagle_tags)

    total_new = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=cfg.pinterest_headless)
        context = browser.new_context(locale=cfg.pinterest_locale)
        page = context.new_page()

        pinterest_login(page, cfg)

        for kw in cfg.keywords:
            print(f"\n[INFO] Collect keyword: {kw}")
            pins = collect_for_keyword(page, cfg, kw)
            print(f"[INFO] Candidate pins: {len(pins)}")

            for pin in pins:
                pin_id = pin["pin_id"]
                if state.seen(pin_id):
                    continue

                title = f"pinterest_{kw}_{pin_id}"
                ok = eagle.add_from_url(
                    image_url=pin["image_url"],
                    name=title,
                    website=pin["pin_url"],
                    tags=[kw],
                )
                if ok:
                    state.mark_seen(pin_id, pin["image_url"], kw)
                    total_new += 1
                    print(f"[OK] Imported {pin_id}")
                else:
                    print(f"[FAIL] Import {pin_id}")

                jitter(cfg)

        browser.close()

    print(f"\n[DONE] Imported new items: {total_new}")


if __name__ == "__main__":
    run()
