import os
import json
import datetime
import requests
from bs4 import BeautifulSoup
from feedgenerator import Rss201rev2Feed

BASE_URL = "https://dilbert.com/"
OUTPUT_DIR = "docs"
USED_JSON_PATH = "used_comics.json"

today = datetime.date.today()
today_str = today.strftime("%Y-%m-%d")
html_path = f"{OUTPUT_DIR}/dilbert-{today_str}.html"
rss_path = f"{OUTPUT_DIR}/feed.xml"
image_output_path = f"{OUTPUT_DIR}/images/dilbert-{today_str}.jpg"

# Load used comics
if os.path.exists(USED_JSON_PATH):
    with open(USED_JSON_PATH, "r") as f:
        used_comics = json.load(f)
else:
    used_comics = {}

# Skip if already fetched AND image exists
if today_str in used_comics and os.path.exists(image_output_path):
    print(f"✅ Comic already processed for {today_str}")
    exit(0)

# Fetch Dilbert homepage
response = requests.get(BASE_URL)
soup = BeautifulSoup(response.text, "html.parser")
img_tag = soup.select_one("img.img-comic")

if not img_tag or not img_tag.get("src"):
    print("❌ Comic image not found.")
    exit(1)

img_url = img_tag["src"]
if img_url.startswith("//"):
    img_url = "https:" + img_url

# Download image
img_data = requests.get(img_url).content
os.makedirs(os.path.dirname(image_output_path), exist_ok=True)
with open(image_output_path, "wb") as f:
    f.write(img_data)
print(f"📥 Downloaded image: {img_url}")

# Save HTML page
title = f"Dilbert for {today_str}"
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <meta property="og:title" content="{title}">
  <meta property="og:image" content="https://djz2k.github.io/dilbert-rss/images/dilbert-{today_str}.jpg">
  <meta property="og:type" content="article">
</head>
<body>
  <h1>{title}</h1>
  <img src="images/dilbert-{today_str}.jpg" alt="Dilbert comic for {today_str}">
</body>
</html>
"""
with open(html_path, "w") as f:
    f.write(html_content)
print(f"📝 Saved HTML to {html_path}")

# Update RSS feed
feed = Rss201rev2Feed(
    title="Daily Dilbert",
    link="https://djz2k.github.io/dilbert-rss/",
    description="View today’s Dilbert comic.",
    language="en"
)

feed.add_item(
    title=title,
    link=f"https://djz2k.github.io/dilbert-rss/dilbert-{today_str}.html",
    description=title,
    pubdate=datetime.datetime.utcnow()
)

with open(rss_path, "w") as f:
    feed.write(f, "utf-8")
print(f"📡 Updated RSS feed at {rss_path}")

# Mark comic as used
used_comics[today_str] = img_url
with open(USED_JSON_PATH, "w") as f:
    json.dump(used_comics, f, indent=2)
print(f"✅ Marked {today_str} as used")
