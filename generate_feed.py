"""Daily Dilbert RSS feed generator.

Mirrors the proven calvin-rss architecture:
- External image URLs (no self-hosted images)
- ElementTree RSS generation
- Minimal OG tags for reliable unfurling
"""

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# === Config ===
SOURCE_URL = "https://dilbert-viewer.herokuapp.com/random"
USED_FILE = "used_comics.json"
RSS_FILE = "docs/dilbert-clean.xml"
INDEX_FILE = "docs/index.html"
SITE_URL = "https://djz2k.github.io/dilbert-rss"
FEED_TITLE = "Daily Dilbert"
FEED_DESC = "A daily classic Dilbert comic strip"
MAX_ITEMS = 50
MAX_RETRIES = 10
HEADERS = {"User-Agent": "Mozilla/5.0"}


def load_used():
    if Path(USED_FILE).exists():
        with open(USED_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_used(used):
    with open(USED_FILE, "w") as f:
        json.dump(sorted(used), f, indent=2)


def fetch_random_comic():
    """Fetch a random comic page and return (image_hash, image_url) or (None, None)."""
    try:
        r = requests.get(SOURCE_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        img = soup.find("img", {"src": re.compile(r"amuniversal\.com")})
        if not img:
            print("  [WARN] No amuniversal image found")
            return None, None
        url = img["src"]
        # The hash is the last path segment before any query params
        image_hash = url.rstrip("/").split("/")[-1].split("?")[0]
        print(f"  [OK] Found comic: {image_hash}")
        return image_hash, url
    except Exception as e:
        print(f"  [ERR] Fetch failed: {e}")
        return None, None


def find_unique_comic(used):
    """Try up to MAX_RETRIES to get a comic we haven't posted before."""
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"Attempt {attempt}/{MAX_RETRIES}...")
        image_hash, image_url = fetch_random_comic()
        if not image_hash:
            continue
        if image_hash in used:
            print(f"  [SKIP] Already used {image_hash}")
            continue
        return image_hash, image_url
    return None, None


def write_html(image_url, date_str):
    """Write both the dated page and index.html — mirrors Calvin exactly."""
    page_url = f"{SITE_URL}/dilbert-{date_str}.html"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta property="og:title" content="Dilbert for {date_str}" />
  <meta property="og:image" content="{image_url}" />
  <meta property="og:description" content="View today's Dilbert comic." />
  <meta name="twitter:card" content="summary_large_image" />
  <title>Dilbert for {date_str}</title>
</head>
<body>
  <h1>Dilbert for {date_str}</h1>
  <img src="{image_url}" alt="Dilbert comic"/>
</body>
</html>"""

    Path(f"docs/dilbert-{date_str}.html").write_text(html)
    Path(INDEX_FILE).write_text(html)
    print(f"  [OK] Wrote dilbert-{date_str}.html + index.html")


def build_rss_items(date_str, image_url):
    """Build the new item and append existing items from the feed file."""
    items = []

    # New item
    pub_date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
    link_url = f"{SITE_URL}/dilbert-{date_str}.html"

    item = ET.Element("item")
    ET.SubElement(item, "title").text = f"Dilbert for {date_str}"
    ET.SubElement(item, "link").text = link_url
    ET.SubElement(item, "guid").text = link_url
    ET.SubElement(item, "pubDate").text = pub_date
    ET.SubElement(item, "description").text = (
        f'<![CDATA[<img src="{image_url}" alt="Dilbert comic" />]]>'
    )
    ET.SubElement(item, "enclosure", attrib={
        "url": image_url,
        "type": "image/gif",
    })
    items.append(item)

    # Carry forward existing items
    if Path(RSS_FILE).exists():
        try:
            tree = ET.parse(RSS_FILE)
            channel = tree.getroot().find("channel")
            if channel is not None:
                for old_item in channel.findall("item"):
                    if len(items) >= MAX_ITEMS:
                        break
                    items.append(old_item)
        except ET.ParseError:
            print("  [WARN] Could not parse existing feed, starting fresh")

    return items, pub_date


def write_rss(items, pub_date):
    """Write the RSS feed — mirrors Calvin exactly."""
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = FEED_TITLE
    ET.SubElement(channel, "link").text = f"{SITE_URL}/dilbert-clean.xml"
    ET.SubElement(channel, "description").text = FEED_DESC
    ET.SubElement(channel, "language").text = "en-us"
    ET.SubElement(channel, "pubDate").text = pub_date
    ET.SubElement(channel, "lastBuildDate").text = pub_date

    for item in items:
        channel.append(item)

    Path("docs").mkdir(exist_ok=True)
    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ", level=0)
    tree.write(RSS_FILE, encoding="utf-8", xml_declaration=True)
    print(f"  [OK] Wrote RSS feed with {len(items)} items")


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"=== Daily Dilbert — {today} ===")

    # Check if we already ran today
    if Path(RSS_FILE).exists():
        try:
            tree = ET.parse(RSS_FILE)
            channel = tree.getroot().find("channel")
            if channel is not None:
                first_item = channel.find("item")
                if first_item is not None:
                    title = first_item.findtext("title", "")
                    if today in title:
                        print(f"Already posted for {today}, skipping.")
                        return
        except ET.ParseError:
            pass

    used = load_used()
    print(f"Loaded {len(used)} used comics")

    image_hash, image_url = find_unique_comic(used)
    if not image_hash:
        print("[FAIL] Could not find a unique comic after all retries.")
        return

    write_html(image_url, today)
    items, pub_date = build_rss_items(today, image_url)
    write_rss(items, pub_date)

    used.add(image_hash)
    save_used(used)
    print(f"[SUCCESS] Posted Dilbert for {today}: {image_hash}")


if __name__ == "__main__":
    main()
