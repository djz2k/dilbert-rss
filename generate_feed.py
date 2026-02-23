import os
import re
import json
import hashlib
import datetime
import requests
from bs4 import BeautifulSoup
from feedgenerator import Rss201rev2Feed

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


def download_image(image_url, image_filename):
    """Download an image and return the local path, or None on failure."""
    local_path = os.path.join(IMAGES_DIR, image_filename)
    os.makedirs(IMAGES_DIR, exist_ok=True)

    try:
        img_response = requests.get(image_url, headers=HEADERS, timeout=15)
        img_response.raise_for_status()

        content_type = img_response.headers.get("Content-Type", "image/jpeg")
        size = len(img_response.content)

        if size < 1000:
            print(f"  ⚠️ Image too small ({size} bytes), likely broken")
            return None, None, None

        with open(local_path, "wb") as f:
            f.write(img_response.content)

        print(f"  ✅ Downloaded image: {local_path} ({size} bytes, {content_type})")
        return local_path, content_type, size
    except Exception as e:
        print(f"  ❌ Error downloading image: {e}")
        return None, None, None


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

        image_filename = f"{image_hash}.jpg"
        local_path, content_type, size = download_image(image_url, image_filename)
        if not local_path:
            continue

        return {
            "image_hash": image_hash,
            "image_filename": image_filename,
            "local_path": local_path,
            "image_url": image_url,
            "mime_type": "image/jpeg",
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
<html lang="en" prefix="og: http://ogp.me/ns#">
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
  <meta name="twitter:title" content="Daily Dilbert" />
  <meta name="twitter:image" content="{image_url}" />
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
    """Build the RSS feed from the accumulated feed items list."""
    feed = Rss201rev2Feed(
        title="Daily Dilbert",
        link=f"{BASE_URL}/dilbert-clean.xml",
        description="Unofficial Dilbert feed with full comic previews.",
        language="en",
    )

    for item in reversed(feed_items[-FEED_MAX_ITEMS:]):
        image_full_url = f"{BASE_URL}/images/{item['image_filename']}"
        page_url = f"{BASE_URL}/dilbert-{item['date']}.html"

        feed.add_item(
            title=f"Dilbert for {item['date']}",
            link=page_url,
            description=(
                f'<p>Dilbert comic for {item["date"]}.</p>'
                f'<img src="{image_full_url}" alt="Dilbert comic" '
                f'style="max-width:100%;" />'
            ),
            unique_id=hashlib.md5(
                f"{page_url}-{item['image_hash']}".encode()
            ).hexdigest(),
            pubdate=datetime.datetime.fromisoformat(item["pubdate"]),
            enclosures=[
                type(
                    "Enclosure",
                    (object,),
                    {
                        "url": image_full_url,
                        "length": str(item.get("size", 0)),
                        "mime_type": item.get("mime_type", "image/jpeg"),
                    },
                )()
            ],
        )

    feed_path = os.path.join(OUTPUT_DIR, "dilbert-clean.xml")
    with open(feed_path, "w", encoding="utf-8") as f:
        feed.write(f, "utf-8")
    print(f"  ✅ RSS feed written with {min(len(feed_items), FEED_MAX_ITEMS)} items")


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
    """Fix image filenames and regenerate HTML pages for proper OG unfurling."""
    migrated = 0
    for item in feed_items:
        old_filename = item["image_filename"]
        new_filename = f"{item['image_hash']}.jpg"
        # Fix mime_type to match .jpg extension (avoids enclosure type mismatch)
        item["mime_type"] = "image/jpeg"
        if old_filename == new_filename:
            pass
        else:
            # Rename image file from old name to new name
            old_path = os.path.join(IMAGES_DIR, old_filename)
            new_path = os.path.join(IMAGES_DIR, new_filename)
            if os.path.exists(old_path):
                os.rename(old_path, new_path)
                print(f"  🔄 Renamed {old_filename} → {new_filename}")
            item["image_filename"] = new_filename

        # Regenerate the HTML page with the canonical minimal template
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

    # Migrate image filenames and regenerate HTML pages for proper OG unfurling
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
        page_url = generate_comic_html(today, comic["image_filename"], comic["image_url"])

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
