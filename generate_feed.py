import datetime
import os
import json
import requests
from pathlib import Path
from xml.sax.saxutils import escape

# Constants
OUTPUT_DIR = Path("docs")
IMG_DIR = OUTPUT_DIR / "img"
FEED_FILE = OUTPUT_DIR / "dilbert-clean.xml"
INDEX_FILE = OUTPUT_DIR / "index.html"
USED_FILE = Path("used_comics.json")
BASE_URL = "https://djz2k.github.io/dilbert-rss"

IMG_DIR.mkdir(parents=True, exist_ok=True)

# Get today's date
today = datetime.date.today()
date_str = today.strftime("%Y-%m-%d")
short_date = today.strftime("%y%m%d")

# Construct original image URL
original_img_url = f"https://web.archive.org/web/2023{short_date}im_/https://assets.amuniversal.com/{short_date}d8ab06cc901301d50001dd8b71c47"

# Save image locally to proxy through GitHub Pages
proxied_img_path = IMG_DIR / f"{date_str}.jpg"
proxied_img_url = f"{BASE_URL}/img/{date_str}.jpg"

if not proxied_img_path.exists():
    try:
        response = requests.get(original_img_url, timeout=10)
        response.raise_for_status()
        with open(proxied_img_path, "wb") as f:
            f.write(response.content)
        print(f"✅ Downloaded and saved image to {proxied_img_path}")
    except Exception as e:
        print(f"❌ Failed to download image: {e}")
        exit(1)
else:
    print(f"⏭️ Image already exists at {proxied_img_path}, skipping download.")

# Generate HTML page
def generate_html(date_str, img_url):
    filename = f"dilbert-{date_str}.html"
    page_url = f"{BASE_URL}/{filename}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta property="og:title" content="Dilbert - {date_str}" />
  <meta property="og:description" content="Today's Dilbert comic" />
  <meta property="og:image" content="{img_url}" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="{page_url}" />
  <title>Dilbert - {date_str}</title>
  <style>body {{ font-family: sans-serif; text-align: center; padding: 2em; }}</style>
</head>
<body>
  <h1>Dilbert - {date_str}</h1>
  <img src="{img_url}" alt="Dilbert comic for {date_str}" style="max-width: 100%; height: auto;" />
  <p><a href="{img_url}" target="_blank">View full-size image</a></p>
</body>
</html>"""
    with open(OUTPUT_DIR / filename, "w", encoding="utf-8") as f:
        f.write(html)
    return filename, page_url

filename, page_url = generate_html(date_str, proxied_img_url)

# Load or create used_comics.json
if USED_FILE.exists():
    with open(USED_FILE, "r") as f:
        used = json.load(f)
else:
    used = []

# Check if already added
if any(comic["date"] == date_str for comic in used):
    print(f"⏭️ Already generated for {date_str}, exiting.")
    exit(0)

# Prepend new entry
used.insert(0, {
    "date": date_str,
    "title": f"Dilbert - {date_str}",
    "link": page_url
})
used = used[:30]
with open(USED_FILE, "w") as f:
    json.dump(used, f, indent=2)

# Update RSS
def update_feed(entries):
    feed_items = ""
    for entry in entries:
        feed_items += f"""
  <item>
    <title>{escape(entry['title'])}</title>
    <link>{entry['link']}</link>
    <guid>{entry['link']}</guid>
    <description>{escape(entry['title'])}</description>
  </item>"""

    rss = f"""<?xml version='1.0' encoding='utf-8'?>
<rss xmlns:atom="http://www.w3.org/2005/Atom" version="2.0">
<channel>
  <title>Daily Dilbert</title>
  <link>{BASE_URL}/dilbert-clean.xml</link>
  <description>Unofficial Dilbert RSS Feed</description>
  <atom:link href="{BASE_URL}/dilbert-clean.xml" rel="self" type="application/rss+xml" />
  <lastBuildDate>{datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')}</lastBuildDate>
  {feed_items}
</channel>
</rss>"""

    with open(FEED_FILE, "w", encoding="utf-8") as f:
        f.write(rss)

update_feed(used)

# Update index.html
def update_index(latest_filename):
    redirect_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta http-equiv="refresh" content="0; url={latest_filename}" />
  <title>Redirecting…</title>
</head>
<body>
  <p>Redirecting to <a href="{latest_filename}">{latest_filename}</a></p>
</body>
</html>"""
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(redirect_html)

update_index(filename)
print(f"✅ Done generating {filename} and RSS.")
