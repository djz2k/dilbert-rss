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
ARCHIVE_BASE = "https://web.archive.org/web/"
DILBERT_ARCHIVE = "https://dilbert.com/strip/"

HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_today_date():
    return datetime.date.today().isoformat()

def get_yesterday_date():
    return (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

def load_used_comics():
    if os.path.exists(USED_COMICS_FILE):
        with open(USED_COMICS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_used_comics(used):
    with open(USED_COMICS_FILE, "w") as f:
        json.dump(sorted(list(used)), f, indent=2)

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

def fetch_comic(date_str):
    comic_url = f"{DILBERT_ARCHIVE}{date_str}"
    try:
        response = requests.get(comic_url, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        img_tag = soup.find("img", attrs={"src": re.compile(r"assets\.amuniversal\.com")})
        if not img_tag:
            print(f"❌ Comic image not found on page for {date_str}")
            return None, None, comic_url

        img_url = img_tag["src"]
        # Proxy via Wayback Machine
        wayback_url = f"{ARCHIVE_BASE}{date_str.replace('-', '')}im_/{img_url}"
        image_filename = os.path.basename(img_url).split("?")[0]
        local_image_path = os.path.join(OUTPUT_DIR, "images", image_filename)
        os.makedirs(os.path.dirname(local_image_path), exist_ok=True)

        if not os.path.exists(local_image_path):
            success = download_and_save_image(wayback_url, local_image_path)
            if not success:
                return None, None, comic_url

        return local_image_path, image_filename, comic_url
    except Exception as e:
        print(f"❌ Error fetching comic for {date_str}: {e}")
        return None, None, comic_url

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
    <meta property="og:description" content="View today's Dilbert comic." />
</head>
<body>
    <h1>Dilbert for {date_str}</h1>
    {f'<a href="{comic_url}" target="_blank"><img src="{image_url}" alt="Dilbert comic for {date_str}"></a>' if image_url else '<p>Comic not available yet.</p>'}
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
    feed = Rss201rev2Feed(
        title="Daily Dilbert",
        link=f"{BASE_URL}/dilbert-clean.xml",
        description="Unofficial Dilbert feed with direct image and link preview support.",
        language="en",
    )

    logs = [f"🕒 Running at {datetime.datetime.utcnow().isoformat()} UTC"]
    generated_count = 0

    for i in range(10):
        date = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
        if date in used_comics:
            continue

        local_image_path, image_filename, comic_url = fetch_comic(date)
        if local_image_path:
            page_url = generate_html(date, image_filename, comic_url)
            feed.add_item(
                title=f"Dilbert for {date}",
                link=page_url,
                description=f"See the Dilbert comic for {date}.",
                unique_id=hashlib.md5(page_url.encode()).hexdigest(),
                pubdate=datetime.datetime.strptime(date, "%Y-%m-%d"),
                enclosures=[{
                    "url": f"{BASE_URL}/images/{image_filename}",
                    "length": str(os.path.getsize(local_image_path)),
                    "mime_type": "image/jpeg"
                }]
            )
            used_comics.add(date)
            logs.append(f"✅ Added {date} → {page_url}")
            generated_count += 1
        else:
            page_url = generate_html(date, None, comic_url)
            logs.append(f"⚠️ Skipped {date} (missing image): {comic_url}")
            continue

    if generated_count == 0:
        logs.append("⚠️ No new comics were added.")

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

    save_used_comics(used_comics)
    generate_debug_html(logs)
    print("\n".join(logs))

if __name__ == "__main__":
    main()
