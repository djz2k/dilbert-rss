"""Daily Dilbert RSS feed generator.

Architecture notes:
- The comic image is DOWNLOADED at build time and self-hosted under docs/images/.
  Hotlinking the upstream archive host is not viable: every URL is a cross-domain
  302 to a different capture, latency is seconds, and the host refuses connections
  at the TCP layer once an IP makes more than a handful of requests. Unfurl bots
  run from shared, high-volume IPs, so they get blocked and render an empty card.
  Serving the image from GitHub Pages is same-origin, redirect-free and unmetered.
- Every comic is re-encoded onto a fixed 1200x630 JPEG canvas. Upstream strips
  arrive at 900 and 1200 px wide, as GIF or JPEG, with aspect ratios from 1.5:1
  to 3.3:1, and unfurlers disagree about which of those they will render.
  Normalising removes the variation instead of guessing at each client's limits.
  It also makes the extension honest, so Pages serves a matching Content-Type.
- RSS generation uses ElementTree (no feed library dependency).
- The run fails loudly (non-zero exit) rather than skipping a day.
"""

import io
import json
import random
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from PIL import Image

# === Config ===
SOURCE_URL = "https://dilbert-viewer.herokuapp.com/random"
USED_FILE = "used_comics.json"
RSS_FILE = "docs/dilbert-clean.xml"
INDEX_FILE = "docs/index.html"
IMAGES_DIR = "docs/images"
SITE_URL = "https://djz2k.github.io/dilbert-rss"
FEED_TITLE = "Daily Dilbert"
FEED_DESC = "A daily classic Dilbert comic strip"
ITEM_DESC = "View today's Dilbert comic."
MAX_ITEMS = 50
MAX_RETRIES = 10
MAX_FALLBACK_RETRIES = 5
MAX_IMAGE_RETRIES = 5
IMAGE_RETRY_BACKOFF = 6  # seconds, multiplied by attempt number
MIN_IMAGE_BYTES = 1024
POOL_EXTS = {".gif", ".jpg", ".jpeg", ".png"}
# Standard Open Graph canvas. Every served image is exactly this.
OG_WIDTH = 1200
OG_HEIGHT = 630
OG_BACKGROUND = (255, 255, 255)
JPEG_QUALITY = 90
HEADERS = {"User-Agent": "Mozilla/5.0"}
MEDIA_NS = "http://search.yahoo.com/mrss/"

ET.register_namespace("media", MEDIA_NS)


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


def find_any_comic():
    """Last resort: accept a repeat rather than let the day go unfilled."""
    for attempt in range(1, MAX_FALLBACK_RETRIES + 1):
        print(f"Fallback attempt {attempt}/{MAX_FALLBACK_RETRIES}...")
        image_hash, image_url = fetch_random_comic()
        if image_hash:
            return image_hash, image_url
    return None, None


def normalize_image(data, date_str):
    """Letterbox the comic onto the standard Open Graph canvas as baseline JPEG.

    Pillow decodes by content rather than by filename, so this also rescues the
    older stored comics that carry a .jpg name over GIF bytes.

    Returns (image_url, mime_type, width, height, byte_count) or None.
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            frame = img.convert("RGB")
    except Exception as e:
        print(f"  [ERR] Could not decode image: {e}")
        return None

    if frame.width < 1 or frame.height < 1:
        print("  [ERR] Decoded image has no pixels")
        return None

    scale = min(OG_WIDTH / frame.width, OG_HEIGHT / frame.height)
    new_w = max(1, round(frame.width * scale))
    new_h = max(1, round(frame.height * scale))
    resized = frame.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), OG_BACKGROUND)
    canvas.paste(resized, ((OG_WIDTH - new_w) // 2, (OG_HEIGHT - new_h) // 2))

    Path(IMAGES_DIR).mkdir(parents=True, exist_ok=True)
    # Drop any stale copy for today that used a different extension
    for old in Path(IMAGES_DIR).glob(f"{date_str}.*"):
        if old.suffix != ".jpg":
            old.unlink()
            print(f"  [OK] Removed stale {old.name}")

    dest = Path(IMAGES_DIR) / f"{date_str}.jpg"
    # Baseline, not progressive: some unfurlers mishandle progressive JPEG.
    canvas.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=False)
    byte_count = dest.stat().st_size
    image_url = f"{SITE_URL}/images/{date_str}.jpg"
    print(f"  [OK] Normalised {frame.width}x{frame.height} -> {OG_WIDTH}x{OG_HEIGHT} "
          f"JPEG: {dest.name} ({byte_count} bytes)")
    return image_url, "image/jpeg", OG_WIDTH, OG_HEIGHT, byte_count


def download_image(source_url, date_str):
    """Download the comic and store it under docs/images/.

    Returns (image_url, mime_type, width, height, byte_count) or None.
    """
    Path(IMAGES_DIR).mkdir(parents=True, exist_ok=True)

    for attempt in range(1, MAX_IMAGE_RETRIES + 1):
        print(f"Downloading image, attempt {attempt}/{MAX_IMAGE_RETRIES}...")
        try:
            r = requests.get(source_url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            data = r.content
        except Exception as e:
            print(f"  [ERR] Image download failed: {e}")
            if attempt < MAX_IMAGE_RETRIES:
                delay = IMAGE_RETRY_BACKOFF * attempt
                print(f"  [WAIT] Backing off {delay}s before retry")
                time.sleep(delay)
            continue

        if len(data) < MIN_IMAGE_BYTES:
            print(f"  [ERR] Image too small ({len(data)} bytes), treating as failure")
            if attempt < MAX_IMAGE_RETRIES:
                time.sleep(IMAGE_RETRY_BACKOFF * attempt)
            continue

        normalized = normalize_image(data, date_str)
        if not normalized:
            print("  [ERR] Downloaded payload could not be normalised")
            if attempt < MAX_IMAGE_RETRIES:
                time.sleep(IMAGE_RETRY_BACKOFF * attempt)
            continue

        return normalized

    return None


def recently_used_images():
    """Basenames of images referenced by the current feed, to avoid an obvious repeat."""
    names = set()
    if not Path(RSS_FILE).exists():
        return names
    try:
        tree = ET.parse(RSS_FILE)
        for enc in tree.getroot().iter("enclosure"):
            url = enc.get("url", "")
            if url:
                names.add(url.rstrip("/").split("/")[-1].split("?")[0])
    except ET.ParseError:
        print("  [WARN] Could not parse existing feed while reading recent images")
    return names


def use_local_pool(date_str):
    """Last resort: re-post an image we already host.

    Every upstream in this pipeline is a third party that can disappear. The
    images under docs/images/ are served from our own Pages site, so they cannot
    fail the way a remote host can. Falling back to them keeps the promise that a
    day is never skipped. The pick is seeded by the date, so re-running the same
    day is idempotent, and the file is referenced in place rather than copied so
    the emergency path does not bloat the repo.

    Returns (image_url, mime_type, width, height, byte_count) or None.
    """
    if not Path(IMAGES_DIR).is_dir():
        print("  [ERR] No local image pool directory")
        return None

    candidates = sorted(
        p for p in Path(IMAGES_DIR).iterdir()
        if p.is_file() and p.suffix.lower() in POOL_EXTS and p.stem != date_str
    )
    if not candidates:
        print("  [ERR] Local image pool is empty")
        return None

    recent = recently_used_images()
    fresh = [p for p in candidates if p.name not in recent]
    if fresh:
        pool = fresh
    else:
        pool = candidates
        print("  [WARN] Every pooled image is already in the feed; allowing a repeat")

    print(f"Selecting from local pool ({len(pool)} candidates)...")
    order = list(pool)
    random.Random(date_str).shuffle(order)

    for candidate in order:
        try:
            data = candidate.read_bytes()
        except OSError as e:
            print(f"  [SKIP] Could not read {candidate.name}: {e}")
            continue

        if len(data) < MIN_IMAGE_BYTES:
            print(f"  [SKIP] {candidate.name} is too small ({len(data)} bytes)")
            continue

        # Normalising re-encodes from the decoded pixels, so a stored file whose
        # extension lies about its bytes is still perfectly usable here.
        normalized = normalize_image(data, date_str)
        if not normalized:
            print(f"  [SKIP] {candidate.name} could not be normalised")
            continue

        print(f"  [OK] Reusing {candidate.name}")
        return normalized

    print("  [ERR] No usable image in the local pool")
    return None


def render_html(date_str, page_url, image_url, mime, width, height):
    """Minimal page carrying a complete, self-consistent set of unfurl tags."""
    feed_url = f"{SITE_URL}/dilbert-clean.xml"
    size_tags = ""
    if width and height:
        size_tags = (
            f'\n  <meta property="og:image:width" content="{width}" />'
            f'\n  <meta property="og:image:height" content="{height}" />'
        )
    dimensions = f' width="{width}" height="{height}"' if width and height else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dilbert for {date_str}</title>
  <link rel="canonical" href="{page_url}" />
  <link rel="alternate" type="application/rss+xml" title="{FEED_TITLE}" href="{feed_url}" />
  <meta property="og:type" content="article" />
  <meta property="og:site_name" content="{FEED_TITLE}" />
  <meta property="og:url" content="{page_url}" />
  <meta property="og:title" content="Dilbert for {date_str}" />
  <meta property="og:description" content="{ITEM_DESC}" />
  <meta property="og:image" content="{image_url}" />
  <meta property="og:image:secure_url" content="{image_url}" />
  <meta property="og:image:type" content="{mime}" />
  <meta property="og:image:alt" content="Dilbert comic for {date_str}" />{size_tags}
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="Dilbert for {date_str}" />
  <meta name="twitter:description" content="{ITEM_DESC}" />
  <meta name="twitter:image" content="{image_url}" />
</head>
<body>
  <h1>Dilbert for {date_str}</h1>
  <img src="{image_url}" alt="Dilbert comic for {date_str}"{dimensions} style="max-width:100%;height:auto" />
  <p><a href="{feed_url}">RSS feed</a></p>
</body>
</html>"""


def write_html(date_str, image_url, mime, width, height):
    """Write the dated page and index.html, each declaring its own canonical URL."""
    page_url = f"{SITE_URL}/dilbert-{date_str}.html"

    Path("docs").mkdir(exist_ok=True)
    Path(f"docs/dilbert-{date_str}.html").write_text(
        render_html(date_str, page_url, image_url, mime, width, height)
    )
    Path(INDEX_FILE).write_text(
        render_html(date_str, f"{SITE_URL}/", image_url, mime, width, height)
    )
    print(f"  [OK] Wrote dilbert-{date_str}.html + index.html")


def normalize_description(item):
    """Unwrap literal CDATA markers left in carried-forward items.

    ElementTree escapes whatever it is handed, so a '<![CDATA[...]]>' string
    previously landed in the feed as visible text instead of markup. Strip the
    wrapper so the payload escapes once, the way RSS expects.
    """
    desc = item.find("description")
    if desc is None or not desc.text:
        return
    text = desc.text.strip()
    if text.startswith("<![CDATA[") and text.endswith("]]>"):
        desc.text = text[len("<![CDATA["):-len("]]>")]


def build_rss_items(date_str, image_url, mime, width, height, byte_count):
    """Build the new item and append existing items from the feed file."""
    items = []

    # New item
    pub_date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
    link_url = f"{SITE_URL}/dilbert-{date_str}.html"

    item = ET.Element("item")
    ET.SubElement(item, "title").text = f"Dilbert for {date_str}"
    ET.SubElement(item, "link").text = link_url
    ET.SubElement(item, "guid", attrib={"isPermaLink": "true"}).text = link_url
    ET.SubElement(item, "pubDate").text = pub_date
    # Escaped HTML, not a literal CDATA string: ElementTree escapes this once.
    ET.SubElement(item, "description").text = (
        f'<img src="{image_url}" alt="Dilbert comic for {date_str}" /><p>{ITEM_DESC}</p>'
    )
    ET.SubElement(item, "enclosure", attrib={
        "url": image_url,
        "type": mime,
        "length": str(byte_count),
    })
    media_attrib = {"url": image_url, "type": mime, "medium": "image"}
    if width and height:
        media_attrib["width"] = str(width)
        media_attrib["height"] = str(height)
    ET.SubElement(item, f"{{{MEDIA_NS}}}content", attrib=media_attrib)
    ET.SubElement(item, f"{{{MEDIA_NS}}}thumbnail", attrib={"url": image_url})
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
                    if old_item.findtext("guid", "") == link_url:
                        continue
                    normalize_description(old_item)
                    items.append(old_item)
        except ET.ParseError:
            print("  [WARN] Could not parse existing feed, starting fresh")

    return items, pub_date


def write_rss(items, pub_date):
    """Write the RSS feed."""
    # The media namespace declaration comes from ET.register_namespace above;
    # declaring it here as well would emit a duplicate attribute and break the XML.
    rss = ET.Element("rss", attrib={"version": "2.0"})
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

    image_hash, source_url = find_unique_comic(used)
    if not image_hash:
        print("[WARN] No unused comic after all retries; allowing a repeat so the day is not skipped.")
        image_hash, source_url = find_any_comic()

    downloaded = None
    if image_hash:
        downloaded = download_image(source_url, today)
        if not downloaded:
            print("[WARN] Could not download the comic image; falling back to the local pool.")
    else:
        print("[WARN] No comic available upstream; falling back to the local pool.")

    from_pool = False
    if not downloaded:
        downloaded = use_local_pool(today)
        from_pool = downloaded is not None

    if not downloaded:
        print("[FAIL] Upstream unavailable and no usable image in the local pool. "
              "Failing the run rather than skipping the day.")
        sys.exit(1)

    image_url, mime, width, height, byte_count = downloaded

    write_html(today, image_url, mime, width, height)
    items, pub_date = build_rss_items(today, image_url, mime, width, height, byte_count)
    write_rss(items, pub_date)

    if from_pool:
        # No upstream hash to record: the comic came from images we already host.
        print(f"[SUCCESS] Posted Dilbert for {today} from the local pool: "
              f"{image_url.rstrip('/').split('/')[-1]}")
    else:
        used.add(image_hash)
        save_used(used)
        print(f"[SUCCESS] Posted Dilbert for {today}: {image_hash}")


if __name__ == "__main__":
    main()
