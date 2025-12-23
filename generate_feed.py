#!/usr/bin/env python3
import os
import re
import json
import hashlib
import datetime
import requests
import sys
from bs4 import BeautifulSoup
from feedgenerator import Rss201rev2Feed

BASE_URL = "https://djz2k.github.io/dilbert-rss"
OUTPUT_DIR = "docs"
USED_COMICS_FILE = "used_comics.json"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_today_date():
    return datetime.date.today().isoformat()

def load_used_comics():
    if os.path.exists(USED_COMICS_FILE):
        with open(USED_COMICS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_used_comics(used):
    with open(USED_COMICS_FILE, "w") as f:
        json.dump(sorted(list(used)), f, indent=2)

def download_comic_image():
    try:
        response = requests.get("https://dilbert-viewer.herokuapp.com/random", headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        img_tag = soup.find("img", {"src": re.compile(r"amuniversal\.com")})
        if not img_tag:
            return None, None, None

        img_url = img_tag["src"]
        image_filename = hashlib.md5(img_url.encode()).hexdigest() + ".jpg"
        local_path = os.path.join(OUTPUT_DIR, "images", image_filename)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        if not os.path.exists(local_path):
            img_data = requests.get(img_url, headers=HEADERS, timeout=10)
            img_data.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(img_data.content)
            print(f"✅ Downloaded image: {local_path}")
        else:
            print(f"ℹ️ Image already exists: {local_path}")

        return local_path, image_filename, img_url
    except Exception as e:
        print(f"❌ Failed to fetch comic: {e}")
        return None, None, None

def generate_html(date_str, image_filename, comic_url):
    html_path = os.path.join(OUTPUT_DIR, f"dilbert-{date_str}.html")
    page_url = f"{BASE_URL}/dilbert-{date_str}.html"
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
</head>
<body>
  <h1>Dilbert for {date_str}</h1>
  <a href="{comic_url}" target="_blank"><img src="{image_url}" alt="Dilbert comic for {date_str}"></a>
</body>
</html>"""
    with open(html_path, "w") as f:
        f.write(html)
    return page_url, image_url

def generate_feed(today, page_url, image_url, file_size):
    feed = Rss201rev2Feed(
        title="Daily Dilbert",
        link=f"{BASE_URL}/dilbert-clean.xml",
        description="Unofficial Dilbert feed with full comic previews.",
        language="en",
    )
    feed.add_item(
        title=f"Dilbert for {today}",
        link=page_url,
        description=f"""<p>Dilbert comic for {today}.</p><img src="{image_url}" alt="Dilbert comic" />""",
        unique_id=hashlib.md5(page_url.encode()).hexdigest(),
        pubdate=datetime.datetime.now(datetime.timezone.utc),
        enclosures=[type('Enclosure', (object,), {
            'url': image_url,
            'length': str(file_size),
            'mime_type': "image/jpeg"
        })()]
    )
    with open(os.path.join(OUTPUT_DIR, "dilbert-clean.xml"), "w", encoding="utf-8") as f:
        feed.write(f, "utf-8")

def write_index_html(page_url):
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w") as f:
        f.write(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Daily Dilbert</title></head>
<body>
<h1>Daily Dilbert RSS Feed</h1>
<p>Latest comic: <a href="{page_url}">{page_url}</a></p>
<p><a href="dilbert-clean.xml">RSS Feed</a></p>
</body></html>""")

def main():
    today = get_today_date()
    used_comics = load_used_comics()

    local_path, filename, original_url = download_comic_image()
    if not local_path or not filename:
        print("❌ No comic downloaded. Exiting.")
        sys.exit(1)

    page_url, image_url = generate_html(today, filename, original_url)
    file_size = os.path.getsize(local_path)

    generate_feed(today, page_url, image_url, file_size)
    write_index_html(page_url)

    used_comics.add(today)
    save_used_comics(used_comics)

    print(f"✅ Comic for {today} successfully published.")

if __name__ == "__main__":
    main()
