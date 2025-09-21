import os
import requests
import datetime
from bs4 import BeautifulSoup

BASE_URL = "https://dilbert.com"
ARCHIVE_URL_TEMPLATE = "https://web.archive.org/web/{timestamp}im_/https://assets.amuniversal.com/{image_id}"
FALLBACK_TIMESTAMP = "20230303045303"
FEED_PATH = "docs/dilbert-clean.xml"
IMG_DIR = "docs/img"
HTML_DIR = "docs"

def get_today():
    return datetime.datetime.utcnow().date()

def fetch_comic_page(date):
    url = f"{BASE_URL}/strip/{date}"
    res = requests.get(url)
    res.raise_for_status()
    return res.text

def extract_image_id(page_html):
    soup = BeautifulSoup(page_html, "html.parser")
    meta = soup.find("meta", property="og:image")
    if not meta:
        raise ValueError("No og:image meta tag found")
    image_url = meta["content"]
    return image_url.strip().split("/")[-1]

def try_download_image(image_id, save_path):
    for timestamp in [get_today().strftime("%Y%m%d000000"), FALLBACK_TIMESTAMP]:
        url = ARCHIVE_URL_TEMPLATE.format(timestamp=timestamp, image_id=image_id)
        try:
            print(f"Trying to download image from {url}")
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(res.content)
            return url, True
        except Exception as e:
            print(f"Failed to download with timestamp {timestamp}: {e}")
    return None, False

def write_html_page(date_str, image_filename):
    local_image_path = f"img/{image_filename}"
    full_page_path = os.path.join(HTML_DIR, f"dilbert-{date_str}.html")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta property="og:title" content="Dilbert - {date_str}" />
  <meta property="og:description" content="Dilbert comic for {date_str}" />
  <meta property="og:image" content="https://djz2k.github.io/dilbert-rss/{local_image_path}" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://djz2k.github.io/dilbert-rss/dilbert-{date_str}.html" />
  <title>Dilbert - {date_str}</title>
  <style>body {{ font-family: sans-serif; text-align: center; padding: 2em; }}</style>
</head>
<body>
  <h1>Dilbert - {date_str}</h1>
  <img src="{local_image_path}" alt="Dilbert comic for {date_str}" style="max-width: 100%; height: auto;" />
  <p><a href="{local_image_path}" target="_blank">View original image</a></p>
</body>
</html>
"""
    with open(full_page_path, "w", encoding="utf-8") as f:
        f.write(html)

def write_debug_page(date_str, original_page_html):
    path = os.path.join(HTML_DIR, "debug.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>DEBUG - Dilbert {date_str}</title></head>
<body><h1>DEBUG: Dilbert page for {date_str}</h1>
<pre>{original_page_html}</pre>
</body></html>
""")

def update_rss_feed(date_str, image_filename):
    local_image_url = f"https://djz2k.github.io/dilbert-rss/img/{image_filename}"
    item = f"""<item>
  <title>Dilbert for {date_str}</title>
  <link>https://djz2k.github.io/dilbert-rss/dilbert-{date_str}.html</link>
  <guid>https://djz2k.github.io/dilbert-rss/dilbert-{date_str}.html</guid>
  <pubDate>{datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate>
  <description><![CDATA[<img src="{local_image_url}" alt="Dilbert for {date_str}" />]]></description>
</item>"""

    if not os.path.exists(FEED_PATH):
        print("Creating new feed file")
        with open(FEED_PATH, "w", encoding="utf-8") as f:
            f.write(f"""<?xml version="1.0" encoding="utf-8"?>
<rss xmlns:atom="http://www.w3.org/2005/Atom" version="2.0">
<channel>
  <title>Daily Dilbert</title>
  <link>https://djz2k.github.io/dilbert-rss/</link>
  <description>Unofficial daily Dilbert RSS feed</description>
  <atom:link href="https://djz2k.github.io/dilbert-rss/dilbert-clean.xml" rel="self" type="application/rss+xml" />
{item}
</channel>
</rss>""")
    else:
        with open(FEED_PATH, "r+", encoding="utf-8") as f:
            rss = f.read()
            updated = rss.replace("</channel></rss>", f"{item}\n</channel></rss>")
            f.seek(0)
            f.write(updated)
            f.truncate()

def main():
    today = get_today()
    date_str = today.strftime("%Y-%m-%d")
    try:
        print(f"Fetching comic for {date_str}")
        page = fetch_comic_page(date_str)
        write_debug_page(date_str, page)
        image_id = extract_image_id(page)
        filename = f"{image_id}.jpg"
        os.makedirs(IMG_DIR, exist_ok=True)
        image_path = os.path.join(IMG_DIR, filename)
        _, success = try_download_image(image_id, image_path)
        if not success:
            print(f"⚠️ Skipping {date_str} due to image download failure")
            return
        write_html_page(date_str, filename)
        update_rss_feed(date_str, filename)
        print(f"✅ Done for {date_str}")
    except Exception as e:
        print(f"❌ Failed to process {date_str}: {e}")

if __name__ == "__main__":
    main()
