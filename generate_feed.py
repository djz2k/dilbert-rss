import os
import re
import json
import hashlib
import datetime
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

BASE_URL = "https://djz2k.github.io/dilbert-rss"
OUTPUT_DIR = "docs"
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
USED_COMICS_FILE = "used_comics.json"
FEED_STATE_FILE = os.path.join(OUTPUT_DIR, "feed_state.json")
HEADERS = {"User-Agent": "Mozilla/5.0"}
MAX_RETRIES = 10
FEED_MAX_ITEMS = 20


def get_today_date():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def detect_image_type(data):
    """Detect actual image type from file magic bytes.

    Returns (extension, mime_type) based on the first few bytes.
    """
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif", "image/gif"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg", "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png", "image/png"
    # Default to gif since that's what the source overwhelmingly provides
    return ".gif", "image/gif"


def load_used_comics():
    """Load the set of image hashes that have already been used."""
    if os.path.exists(USED_COMICS_FILE):
        with open(USED_COMICS_FILE, "r") as f:
            data = json.load(f)
            # Migration: filter out any old date-format entries (YYYY-MM-DD)
            # and keep only image hash entries
            hashes = [e for e in data if not re.match(r"^\d{4}-\d{2}-\d{2}$", e)]
            return set(hashes)
    return set()


def save_used_comics(used):
    with open(USED_COMICS_FILE, "w") as f:
        json.dump(sorted(list(used)), f, indent=2)


def load_feed_state():
    """Load previous feed items so the RSS feed accumulates entries."""
    if os.path.exists(FEED_STATE_FILE):
        with open(FEED_STATE_FILE, "r") as f:
            return json.load(f)
    return []


def save_feed_state(items):
    """Persist the last N feed items for next run."""
    with open(FEED_STATE_FILE, "w") as f:
        json.dump(items[-FEED_MAX_ITEMS:], f, indent=2)


def try_fetch_comic():
    """Fetch a random comic page and extract the image URL and comic date."""
    try:
        response = requests.get(
            "https://dilbert-viewer.herokuapp.com/random",
            headers=HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        img_tag = soup.find("img", {"src": re.compile(r"amuniversal\.com")})
        if not img_tag:
            print("  ⚠️ No amuniversal image tag found in response")
            return None, None

        image_url = img_tag["src"]

        # Try to extract the original comic date from the page
        comic_date = None
        title_tag = soup.find("title")
        if title_tag:
            print(f"  📄 Page title: {title_tag.text.strip()}")

        return image_url, soup
    except Exception as e:
        print(f"  ❌ Error during comic fetch: {e}")
        return None, None


def get_image_hash(image_url):
    """Extract the unique image hash from the URL (the basename)."""
    return os.path.basename(image_url).split("?")[0]


def download_image(image_url, image_hash):
    """Download an image, detect its type, save with correct extension.

    Returns (local_path, image_filename, mime_type, size) or Nones on failure.
    """
    os.makedirs(IMAGES_DIR, exist_ok=True)

    try:
        img_response = requests.get(image_url, headers=HEADERS, timeout=15)
        img_response.raise_for_status()

        data = img_response.content
        size = len(data)

        if size < 1000:
            print(f"  ⚠️ Image too small ({size} bytes), likely broken")
            return None, None, None, None

        # Detect actual image type from file content
        ext, mime_type = detect_image_type(data)
        image_filename = f"{image_hash}{ext}"
        local_path = os.path.join(IMAGES_DIR, image_filename)

        with open(local_path, "wb") as f:
            f.write(data)

        print(f"  ✅ Downloaded image: {local_path} ({size} bytes, {mime_type})")
        return local_path, image_filename, mime_type, size
    except Exception as e:
        print(f"  ❌ Error downloading image: {e}")
        return None, None, None, None


def download_unique_comic(date_str, used_comics):
    """Try up to MAX_RETRIES times to get a comic we haven't used before."""
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"🔁 Attempt {attempt}/{MAX_RETRIES} to fetch unique comic...")

        image_url, soup = try_fetch_comic()
        if not image_url:
            continue

        image_hash = get_image_hash(image_url)

        if image_hash in used_comics:
            print(f"  ⚠️ Comic {image_hash} already used, trying again...")
            continue

        local_path, image_filename, mime_type, size = download_image(
            image_url, image_hash
        )
        if not local_path:
            continue

        return {
            "image_hash": image_hash,
            "image_filename": image_filename,
            "local_path": local_path,
            "image_url": image_url,
            "mime_type": mime_type,
            "size": size,
        }

    print(f"❌ Failed to fetch a unique comic after {MAX_RETRIES} attempts.")
    return None


def generate_comic_html(date_str, image_filename, original_url):
    """Generate a standalone HTML page for the comic with OG metadata."""
    html_filename = f"dilbert-{date_str}.html"
    html_path = os.path.join(OUTPUT_DIR, html_filename)
    page_url = f"{BASE_URL}/{html_filename}"
    image_url = f"{BASE_URL}/images/{image_filename}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Dilbert for {date_str}</title>
  <meta property="og:title" content="Dilbert for {date_str}" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="{page_url}" />
  <meta property="og:image" content="{image_url}" />
  <meta property="og:description" content="View today's Dilbert comic." />
  <meta name="twitter:card" content="summary_large_image" />
</head>
<body>
  <h1>Dilbert for {date_str}</h1>
  <a href="{original_url}" target="_blank"><img src="{image_url}" alt="Dilbert comic for {date_str}"></a>
</body>
</html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✅ Generated HTML: {html_path}")
    return page_url


def generate_index_html(date_str, image_filename):
    """Update the landing page to point to the latest comic."""
    page_url = f"{BASE_URL}/dilbert-{date_str}.html"
    image_url = f"{BASE_URL}/images/{image_filename}"
    index_path = os.path.join(OUTPUT_DIR, "index.html")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Daily Dilbert</title>
  <meta property="og:title" content="Daily Dilbert" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="{BASE_URL}/" />
  <meta property="og:image" content="{image_url}" />
  <meta property="og:description" content="A daily-updating feed of Dilbert comics." />
  <meta name="twitter:card" content="summary_large_image" />
</head>
<body>
  <h1>Daily Dilbert RSS Feed</h1>
  <p>Latest comic: <a href="{page_url}">Dilbert for {date_str}</a></p>
  <p><a href="dilbert-clean.xml">Subscribe via RSS</a></p>
  <img src="{image_url}" alt="Latest Dilbert comic" style="max-width:100%;">
</body>
</html>"""

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✅ Updated index.html")


def generate_rss_feed(feed_items):
    """Build the RSS feed from the accumulated feed items list using ElementTree.

    Produces clean RSS 2.0 XML with no extra namespaces, matching the
    structure used by the working calvin-rss and cnh-rss projects.
    """
    items_to_write = feed_items[-FEED_MAX_ITEMS:]

    # Determine lastBuildDate from the newest item
    if items_to_write:
        last_pub = datetime.datetime.fromisoformat(items_to_write[-1]["pubdate"])
    else:
        last_pub = datetime.datetime.now(datetime.timezone.utc)
    last_build_str = last_pub.strftime("%a, %d %b %Y %H:%M:%S %z")

    # Build the RSS tree
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = "Daily Dilbert"
    ET.SubElement(channel, "link").text = f"{BASE_URL}/dilbert-clean.xml"
    ET.SubElement(channel, "description").text = (
        "Unofficial Dilbert feed with full comic previews."
    )
    ET.SubElement(channel, "language").text = "en-us"
    ET.SubElement(channel, "pubDate").text = last_build_str
    ET.SubElement(channel, "lastBuildDate").text = last_build_str

    # Add items newest-first (reversed) like calvin-rss
    for item_data in reversed(items_to_write):
        image_full_url = f"{BASE_URL}/images/{item_data['image_filename']}"
        page_url = f"{BASE_URL}/dilbert-{item_data['date']}.html"
        pub_dt = datetime.datetime.fromisoformat(item_data["pubdate"])
        pub_date_str = pub_dt.strftime("%a, %d %b %Y %H:%M:%S %z")

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = f"Dilbert for {item_data['date']}"
        ET.SubElement(item, "link").text = page_url
        # Use the page URL as GUID (isPermaLink defaults to true, which is correct)
        ET.SubElement(item, "guid").text = page_url
        ET.SubElement(item, "pubDate").text = pub_date_str
        ET.SubElement(item, "description").text = (
            f'<![CDATA[<p>Dilbert comic for {item_data["date"]}.</p>'
            f'<img src="{image_full_url}" alt="Dilbert comic" />]]>'
        )
        ET.SubElement(
            item,
            "enclosure",
            attrib={
                "url": image_full_url,
                "type": item_data.get("mime_type", "image/gif"),
            },
        )

    feed_path = os.path.join(OUTPUT_DIR, "dilbert-clean.xml")
    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ", level=0)
    tree.write(feed_path, encoding="utf-8", xml_declaration=True)
    print(f"  ✅ RSS feed written with {len(items_to_write)} items")


def generate_debug_html(date_str, log_lines):
    """Write a debug page showing what happened during this run."""
    debug_path = os.path.join(OUTPUT_DIR, "debug.html")
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    log_html = "\n".join(f"<li>{line}</li>" for line in log_lines)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Dilbert Feed - Debug Log</title>
  <style>body {{ font-family: monospace; padding: 1em; }} li {{ margin: 0.3em 0; }}</style>
</head>
<body>
  <h1>Debug Log</h1>
  <p><strong>Run date:</strong> {date_str}</p>
  <p><strong>Timestamp:</strong> {timestamp}</p>
  <ul>{log_html}</ul>
</body>
</html>"""

    with open(debug_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ✅ Debug page written: {debug_path}")


def migrate_feed_items(feed_items):
    """Fix image filenames to match actual content type and regenerate HTML pages."""
    migrated = 0
    for item in feed_items:
        old_filename = item["image_filename"]
        image_hash = item["image_hash"]

        # Detect actual image type from file content
        old_path = os.path.join(IMAGES_DIR, old_filename)
        if os.path.exists(old_path):
            with open(old_path, "rb") as f:
                magic = f.read(8)
            ext, mime_type = detect_image_type(magic)
        else:
            # File missing — try alternative extensions
            for try_ext in (".gif", ".jpg", ".png"):
                alt_path = os.path.join(IMAGES_DIR, f"{image_hash}{try_ext}")
                if os.path.exists(alt_path):
                    with open(alt_path, "rb") as f:
                        magic = f.read(8)
                    ext, mime_type = detect_image_type(magic)
                    old_path = alt_path
                    old_filename = f"{image_hash}{try_ext}"
                    break
            else:
                print(f"  ⚠️ Image file missing for {image_hash}, skipping")
                continue

        new_filename = f"{image_hash}{ext}"
        item["mime_type"] = mime_type
        item["image_filename"] = new_filename

        # Rename file if extension changed
        if old_filename != new_filename:
            new_path = os.path.join(IMAGES_DIR, new_filename)
            os.rename(old_path, new_path)
            print(f"  🔄 Renamed {old_filename} → {new_filename} ({mime_type})")

        # Regenerate the HTML page with the correct image URL
        date_str = item["date"]
        page_url = f"{BASE_URL}/dilbert-{date_str}.html"
        image_url = f"{BASE_URL}/images/{new_filename}"
        html_path = os.path.join(OUTPUT_DIR, f"dilbert-{date_str}.html")
        if os.path.exists(html_path):
            # Read existing page to extract the original comic link
            with open(html_path, "r") as f:
                old_html = f.read()
            # Extract original_url from existing href
            m = re.search(r'<a href="([^"]+)" target="_blank">', old_html)
            original_url = m.group(1) if m else "#"

            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Dilbert for {date_str}</title>
  <meta property="og:title" content="Dilbert for {date_str}" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="{page_url}" />
  <meta property="og:image" content="{image_url}" />
  <meta property="og:description" content="View today's Dilbert comic." />
  <meta name="twitter:card" content="summary_large_image" />
</head>
<body>
  <h1>Dilbert for {date_str}</h1>
  <a href="{original_url}" target="_blank"><img src="{image_url}" alt="Dilbert comic for {date_str}"></a>
</body>
</html>"""
            with open(html_path, "w") as f:
                f.write(html)
            print(f"  🔄 Regenerated HTML: dilbert-{date_str}.html")
        migrated += 1
    return migrated


def main():
    today = get_today_date()
    log = []
    log.append(f"Run started for {today}")

    print(f"📅 Date: {today}")
    print(f"🔧 Output dir: {OUTPUT_DIR}")

    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Load state
    used_comics = load_used_comics()
    feed_items = load_feed_state()
    log.append(f"Loaded {len(used_comics)} used comic hashes")
    log.append(f"Loaded {len(feed_items)} existing feed items")

    # Migrate image filenames to match actual content type
    migrated = migrate_feed_items(feed_items)
    if migrated:
        save_feed_state(feed_items)
        log.append(f"Migrated {migrated} feed item(s)")

    # Check if we already ran today
    if feed_items and feed_items[-1].get("date") == today:
        print(f"⚠️ Already have an entry for {today}, skipping fetch")
        log.append(f"Already ran today ({today}), regenerating feed only")
        generate_rss_feed(feed_items)
        latest = feed_items[-1]
        generate_index_html(today, latest["image_filename"])
        generate_debug_html(today, log)
        return

    # Fetch a new unique comic
    comic = download_unique_comic(today, used_comics)

    if comic:
        log.append(f"Fetched comic: {comic['image_hash']}")
        log.append(f"Image file: {comic['image_filename']}")
        log.append(f"MIME type: {comic['mime_type']}, Size: {comic['size']} bytes")

        # Generate the dated HTML page
        page_url = generate_comic_html(
            today, comic["image_filename"], comic["image_url"]
        )

        # Add to feed items
        new_item = {
            "date": today,
            "image_hash": comic["image_hash"],
            "image_filename": comic["image_filename"],
            "mime_type": comic["mime_type"],
            "size": comic["size"],
            "pubdate": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        feed_items.append(new_item)

        # Update dedup tracking
        used_comics.add(comic["image_hash"])
        save_used_comics(used_comics)
        log.append("Saved used_comics.json")

        # Generate RSS feed with all accumulated items
        generate_rss_feed(feed_items)

        # Save feed state for next run
        save_feed_state(feed_items)
        log.append("Saved feed_state.json")

        # Update index.html
        generate_index_html(today, comic["image_filename"])

        log.append("✅ Run completed successfully")
        print(f"\n🎉 Done! Comic {comic['image_hash']} saved for {today}")
    else:
        # FALLBACK: All retries failed. Still generate output so the day is not silent.
        log.append("❌ All fetch attempts failed")
        log.append("Using fallback: regenerating feed with existing items")

        if feed_items:
            # Regenerate feed with existing items (lastBuildDate will update)
            generate_rss_feed(feed_items)
            latest = feed_items[-1]
            generate_index_html(today, latest["image_filename"])
            log.append(f"Fallback: kept latest comic from {latest['date']}")
        else:
            log.append("No existing feed items available for fallback")

        log.append("⚠️ Run completed with fallback (no new comic)")
        print("\n⚠️ No new comic today, but feed and index are still valid")

    # Always write debug page
    generate_debug_html(today, log)


if __name__ == "__main__":
    main()
