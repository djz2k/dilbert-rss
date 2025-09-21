#!/usr/bin/env python3
import os
import re
import json
import time
import hashlib
import requests
import datetime
from bs4 import BeautifulSoup
from feedgenerator import Rss201rev2Feed

BASE_URL = "https://djz2k.github.io/dilbert-rss"
OUTPUT_DIR = "docs"
USED_COMICS_FILE = "used_comics.json"
SOURCE_URL = "https://dilbert-viewer.herokuapp.com/random"
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

def fetch_random_comic():
    try:
        response = requests.get(SOURCE_URL, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        img_tag = soup.find("img")
        if not img_tag or not img_tag.get("src"):
            print("❌ No image found on Dilbert viewer.")
            return None, None
        img_url = img_tag["src"]
        return img_url, SOURCE_URL
    except Exception as e:
        print(f"❌ Error fetching comic: {e}")
        return None, None

def download_and_save_image(image_url, save_path):
    try:
        response = requests.get(image_url, headers=HEADERS)
        response.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(response.content)
        print(f"✅ Downloaded image: {save_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to download image: {e}")
        return False

def generate_html(date_str, image_filename, comic_url):
    html_path = os.path.join(OUTPUT_DIR, f"dilbert-{date_str}.html")
    page_url = f"{BASE_URL}/dilbert-{date_str}.html"
    image_url = f"{BASE_URL}/images/{image_filename}" if image_filename else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dilbert for {date_str}</title>
    <meta property="og:title" content="Dilbert for {date_str}" />
    <meta property="og:type" content="article" />
    <meta property="og:url" content="{page_url}" />
    {"<meta property='og:image' content='" + image_url + "' />" if image_url else ""}
    <meta property="og:description" content='Today&apos;s Dilbert comic.' />
</head>
<body>
    <h1>Dilbert for {date_str}</h1>
    {f'<a href="{comic_url}" target="_blank"><img src="{image_url}" alt="Dilbert comic for {date_str}"></a>' if image_url else '<p>Comic not available.</p>'}
</body>
</html>
"""
    with open(html_path, "w") as f:
        f.write(html)

    return page_url

def generate_debug_html(all_logs):
    path = os.path.join(OUTPUT_DIR, "debug.html")
    with open(path, "w") as f:
        f.write("<html><body><h1>Debug Output</h1><pre>\n")
        f.write("\n".join(all_logs))
        f.write("\n</pre></body></html>")

def main():
    today = get_today_date()
    used_comics = load_used_comics()
    logs = [f"🕒 Running at {datetime.datetime.utcnow().isoformat()} UTC"]
    feed = Rss201rev2Feed(
        title="Daily Dilbert",
        link=f"{BASE_URL}/dilbert-clean.xml",
        description="Unofficial Dilbert feed with direct image and link preview support.",
        language="en",
    )

    image_url, source_link = fetch_random_comic()
    if not image_url:
        logs.append("❌ Could not fetch image.")
        generate_debug_html(logs)
        return

    comic_hash = hashlib.sha256(image_url.encode()).hexdigest()
    if comic_hash in used_comics:
        logs.append("⚠️ Duplicate image. Already used. Skipping.")
        generate_debug_html(logs)
        return

    image_filename = os.path.basename(image_url.split("?")[0])
    local_image_path = os.path.join(OUTPUT_DIR, "images", image_filename)
    os.makedirs(os.path.dirname(local_image_path), exist_ok=True)

    success = download_and_save_image(image_url, local_image_path)
    if not success:
        logs.append("❌ Failed to save image.")
        generate_debug_html(logs)
        return

    page_url = generate_html(today, image_filename, source_link)
    feed.add_item(
        title=f"Dilbert for {today}",
        link=page_url,
        description=f"View the Dilbert comic for {today}.",
        unique_id=comic_hash,
        pubdate=datetime.datetime.utcnow(),
        enclosures=[{
            "url": f"{BASE_URL}/images/{image_filename}",
            "length": str(os.path.getsize(local_image_path)),
            "mime_type": "image/jpeg"
        }]
    )

    with open(os.path.join(OUTPUT_DIR, "dilbert-clean.xml"), "w", encoding="utf-8") as f:
        feed.write(f, "utf-8")

    with open(os.path.join(OUTPUT_DIR, "index.html"), "w") as f:
        f.write(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Daily Dilbert</title></head>
<body>
<h1>Daily Dilbert RSS Feed</h1>
<p>Latest comic: <a href="{page_url}">{page_url}</a></p>
<p><a href="dilbert-clean.xml">RSS Feed</a></p>
</body></html>""")

    used_comics.add(comic_hash)
    save_used_comics(used_comics)
    logs.append(f"✅ Added {today} → {page_url}")
    generate_debug_html(logs)
    print("\n".join(logs))

if __name__ == "__main__":
    main()
