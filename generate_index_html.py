import os
import datetime
from pathlib import Path
from glob import glob

# === CONFIG ===
DOCS_DIR = "docs"
IMAGES_DIR = f"{DOCS_DIR}/images"
INDEX_FILE = f"{DOCS_DIR}/index.html"
FEED_FILE = f"{DOCS_DIR}/feed.xml"
SITE_URL = "https://djz2k.github.io/dilbert-rss"

# === Determine today's expected image ===
today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
expected_image = f"{IMAGES_DIR}/{today_str}.jpg"

# === Find latest available image if today’s is missing ===
if os.path.exists(expected_image):
    image_filename = f"{today_str}.jpg"
    image_date = today_str
else:
    print(f"[fallback] No image for {today_str}. Looking for most recent available image.")
    image_files = sorted(glob(f"{IMAGES_DIR}/*.jpg"), reverse=True)
    if not image_files:
        raise FileNotFoundError("No comic images found in docs/images/")
    image_filename = os.path.basename(image_files[0])
    image_date = image_filename.replace(".jpg", "")

# === Final URLs ===
image_url = f"{SITE_URL}/images/{image_filename}"
comic_page_url = f"{SITE_URL}/{image_date}.html"

# === Build HTML content ===
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Dilbert for {image_date}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta property="og:title" content="Dilbert for {image_date}">
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
  <h1>Dilbert for {image_date}</h1>
  <p><a href="{comic_page_url}">View today's comic</a></p>
  <img src="{image_url}" alt="Dilbert comic for {image_date}" style="max-width: 100%;">
  <p><a href="{FEED_FILE}">RSS Feed</a></p>
</body>
</html>
"""

# === Write index.html ===
Path(INDEX_FILE).write_text(html, encoding="utf-8")
print(f"[done] Wrote {INDEX_FILE} based on image {image_filename}")
