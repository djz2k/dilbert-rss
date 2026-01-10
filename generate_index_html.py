import os
import datetime
from pathlib import Path

# === CONFIG ===
DOCS_DIR = "docs"
IMAGES_DIR = f"{DOCS_DIR}/images"
INDEX_FILE = f"{DOCS_DIR}/index.html"
FEED_FILE = f"{DOCS_DIR}/feed.xml"
SITE_URL = "https://djz2k.github.io/dilbert-rss"

# === Determine today's date string ===
today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
image_filename = f"{today_str}.jpg"
image_path = f"{SITE_URL}/images/{image_filename}"
comic_page_url = f"{SITE_URL}/{today_str}.html"

# === Build HTML content with proper OG tags ===
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Dilbert for {today_str}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta property="og:title" content="Dilbert for {today_str}">
  <meta property="og:description" content="View today's Dilbert comic.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{comic_page_url}">
  <meta property="og:image" content="{image_path}">
  <meta property="og:image:type" content="image/jpeg">
  <meta property="og:image:width" content="800">
  <meta property="og:image:height" content="300">
  <meta name="twitter:card" content="summary_large_image">
</head>
<body>
  <h1>Dilbert for {today_str}</h1>
  <p><a href="{comic_page_url}">View today's comic</a></p>
  <img src="{image_path}" alt="Dilbert comic for {today_str}" style="max-width: 100%;">
  <p><a href="{FEED_FILE}">RSS Feed</a></p>
</body>
</html>
"""

# === Write to index.html ===
Path(INDEX_FILE).write_text(html, encoding="utf-8")
print(f"Wrote {INDEX_FILE}")
