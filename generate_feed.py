#!/usr/bin/env python3
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
        response = requests.get(
            "https://dilbert-viewer.herokuapp.com/random",
            headers=HEADERS,
            timeout=15,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        img_tag = soup.find("img", {"src": re.compile(r"amuniversal\.com")})
        if not img_tag:
            return None, None, None

        img_url = img_tag["src"]
        image_filename = os.path.basename(img_url).split("?")[0]
        if not image_filename.endswith(".jpg"):
            image_filename += ".jpg"

        local_path = os.path.join(OUTPUT_DIR, "images", image_filename)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        if not os.path.exists(local_path):
            img_data = requests.get(img_url, headers=HEADERS, timeout=15)
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

    # 🔑 CRITICAL FIX:
    # Cache-bust OG image so social platforms re-fetch it
    og_image_url = f"{image_url}?v={date_str.replace('-', '')}"

    html = f"""<!DOCTYPE html>
<html lang="en" prefix="og: http://ogp.me/ns#">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">

  <title>Dilbert for {date_str}</title>

  <!-- Open Graph -->
  <meta property="og:title" content="Dilbert for {date_str}" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="{page_url}" />
  <meta property="og:image" content="{og_image_url}" />
  <meta property="og:image:type" content="image/jpeg" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:description" content="View today's Dilbert comic." />

  <!-- Twitter / Slack / Discord fallback -->
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="Dilbert for {date_str}" />
  <meta name="twitter:description" content="View today's Dilbert comic." />
  <meta name="twitter:image" content="{og_image_url}" />
</head>
<body>
  <h1>Dilbert for {date_str}</h1>
  <a href="{comic_url}" target="_blank">
    <img src="{image_url}" alt="Dilbert comic for {date_str}">
  </a>
</body>
</html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    return page_url


def generate_debug_html(logs):
    path = os.path.join(OUTPUT_DIR, "debug.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write("<html><body><h1>Debug Output</h1><pre>\n")
        f.write("\n".join(logs))
        f.write("\n</pre></body></html>")


def main():
    today = get_today_date()
    used_comics = load_used_comics()
    logs = [f"🕒 Running for {today}"]

    if today in used_comics:
        logs.append("⚠️ Comic already used, skipping.")
        generate_debug_html(logs)
        return

    local_path, filename, original_url = download_comic_image()
    if not local_path:
        logs.append("❌ Could not get new comic.")
        generate_debug_html(logs)
        return

    page_url = generate_html(today, filename, original_url)
    image_url = f"{BASE_URL}/images/{filename}"
    file_size = os.path.getsize(local_path)

    feed = Rss201rev2Feed(
        title="Daily Dilbert",
        link=f"{BASE_URL}/dilbert-clean.xml",
        description="Unofficial Dilbert feed with full comic previews.",
        language="en",
    )

    feed.add_item(
        title=f"Dilbert for {today}",
        link=page_url,
        description=f'<p>Dilbert comic for {today}.</p><img src="{image_url}" alt="Dilbert comic" />',
        unique_id=hashlib.md5(page_url.encode()).hexdigest(),
        pubdate=datetime.datetime.now(datetime.UTC),
        enclosures=[type(
            "Enclosure",
            (object,),
            {
                "url": image_url,
                "length": str(file_size),
                "mime_type": "image/jpeg",
            },
        )()],
    )

    with open(os.path.join(OUTPUT_DIR, "dilbert-clean.xml"), "w", encoding="utf-8") as f:
        feed.write(f, "utf-8")

    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(
            f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Daily Dilbert</title>
</head>
<body>
  <h1>Daily Dilbert RSS Feed</h1>
  <p>Latest comic: <a href="{page_url}">{page_url}</a></p>
  <p><a href="dilbert-clean.xml">RSS Feed</a></p>
</body>
</html>"""
        )

    used_comics.add(today)
    save_used_comics(used_comics)

    logs.append(f"✅ Comic generated: {filename}")
    generate_debug_html(logs)
    print("\n".join(logs))


if __name__ == "__main__":
    main()
