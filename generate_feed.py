import os
import datetime
import feedparser
from bs4 import BeautifulSoup
import requests
import json

FEED_PATH = "docs/feed.xml"
USED_COMICS_PATH = "used_comics.json"
HTML_FOLDER = "docs"
INDEX_PATH = os.path.join(HTML_FOLDER, "index.html")

BASE_URL = "https://dilbert-viewer.herokuapp.com/random"

def get_today_date():
    return datetime.date.today().isoformat()

def get_used_comics():
    if os.path.exists(USED_COMICS_PATH):
        with open(USED_COMICS_PATH, "r") as f:
            return set(json.load(f))
    return set()

def save_used_comics(comics):
    with open(USED_COMICS_PATH, "w") as f:
        json.dump(sorted(comics), f)

def fetch_comic_image_url():
    try:
        response = requests.get(BASE_URL, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        img = soup.select_one("div[class*='ComicImage'] img")
        return img["src"] if img else None
    except Exception as e:
        print(f"Error fetching comic image: {e}")
        return None

def generate_html(date_str, image_url):
    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Dilbert for {date_str}</title>
  <meta property="og:title" content="Dilbert for {date_str}" />
  <meta property="og:image" content="{image_url}" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="https://djz2k.github.io/dilbert-rss/dilbert-{date_str}.html" />
</head>
<body>
  <h1>Dilbert for {date_str}</h1>
  <img src="{image_url}" alt="Dilbert comic for {date_str}" />
</body>
</html>
"""
    html_path = os.path.join(HTML_FOLDER, f"dilbert-{date_str}.html")
    with open(html_path, "w") as f:
        f.write(html_content)

def update_index(date_str):
    with open(INDEX_PATH, "w") as f:
        f.write(f"""<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="Refresh" content="0; url=dilbert-{date_str}.html" />
</head>
<body>
  <p>Redirecting to <a href="dilbert-{date_str}.html">today's comic</a>.</p>
</body>
</html>
""")

def update_rss(date_str, image_url):
    if os.path.exists(FEED_PATH):
        feed = feedparser.parse(FEED_PATH)
    else:
        feed = {"entries": []}

    new_entry = f"""<item>
  <title>Dilbert for {date_str}</title>
  <link>https://djz2k.github.io/dilbert-rss/dilbert-{date_str}.html</link>
  <description>&lt;img src="{image_url}" /&gt;</description>
  <guid isPermaLink="false">{date_str}</guid>
  <pubDate>{datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")}</pubDate>
</item>"""

    items = [new_entry]
    for entry in feed.get("entries", [])[:29]:  # keep 30 max
        items.append(entry.get("raw", ""))

    rss = f"""<?xml version="1.0"?>
<rss version="2.0">
<channel>
  <title>Daily Dilbert</title>
  <link>https://djz2k.github.io/dilbert-rss/</link>
  <description>Unofficial Dilbert RSS feed</description>
  {''.join(items)}
</channel>
</rss>"""

    with open(FEED_PATH, "w") as f:
        f.write(rss)

def main():
    today = get_today_date()
    used_comics = get_used_comics()

    if today in used_comics:
        print(f"✔️ Comic for {today} already processed.")
        update_index(today)
        return

    print(f"🚀 Starting Daily Dilbert feed generation for {today}...")

    image_url = fetch_comic_image_url()
    if not image_url:
        print(f"⚠️ Comic image not found for {today}. Skipping HTML + RSS.")
        return

    generate_html(today, image_url)
    update_index(today)
    update_rss(today, image_url)

    used_comics.add(today)
    save_used_comics(used_comics)
    print(f"✅ Comic for {today} processed successfully.")

if __name__ == "__main__":
    main()
