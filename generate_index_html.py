import os
from datetime import datetime
from pathlib import Path

DOCS_DIR = "docs"
IMAGES_DIR = f"{DOCS_DIR}/images"
INDEX_FILE = f"{DOCS_DIR}/index.html"
SITE_URL = "https://djz2k.github.io/dilbert-rss"

def find_latest_existing_date():
    html_files = sorted([
        f for f in os.listdir(DOCS_DIR)
        if f.endswith(".html") and f != "index.html"
    ], reverse=True)
    
    for html_file in html_files:
        date_str = html_file.replace(".html", "")
        image_path = os.path.join(IMAGES_DIR, f"{date_str}.jpg")
        if os.path.exists(image_path):
            return date_str
    raise FileNotFoundError("No valid Dilbert HTML+image pair found")

# Start with today's date
today_str = datetime.utcnow().strftime("%Y-%m-%d")
today_image_path = os.path.join(IMAGES_DIR, f"{today_str}.jpg")

# Use today's date only if image exists
final_date = today_str if os.path.exists(today_image_path) else find_latest_existing_date()

# Construct URLs
image_url = f"{SITE_URL}/images/{final_date}.jpg"
comic_page_url = f"{SITE_URL}/{final_date}.html"
feed_url = f"{SITE_URL}/feed.xml"

# Build HTML content
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Dilbert for {final_date}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta property="og:title" content="Dilbert for {final_date}">
  <meta property="og:description" content="View today's Dilbert comic.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{comic_page_url}">
  <meta property="og:image" content="{image_url}">
  <meta property="og:image:type" content="image/jpeg">
  <meta property="og:image:width" content="800">
  <meta property="og:image:height" content="300">
  <meta name="twitter:card" content="summary_large_image">
</head>
<body>
  <h1>Dilbert for {final_date}</h1>
  <p><a href="{comic_page_url}">View today's comic</a></p>
  <img src="{image_url}" alt="Dilbert comic for {final_date}" style="max-width: 100%;">
  <p><a href="{feed_url}">RSS Feed</a></p>
</body>
</html>
"""

# Write index.html
Path(INDEX_FILE).write_text(html, encoding="utf-8")
print(f"Wrote {INDEX_FILE} with fallback date {final_date}")
