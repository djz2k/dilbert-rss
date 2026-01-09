import os
from datetime import datetime
from bs4 import BeautifulSoup

DOCS_DIR = "docs"
today_str = datetime.today().strftime("%Y-%m-%d")
daily_filename = f"{today_str}.html"
daily_path = os.path.join(DOCS_DIR, daily_filename)
index_path = os.path.join(DOCS_DIR, "index.html")

# Fallback to most recent file if today's missing
if not os.path.exists(daily_path):
    print(f"{daily_filename} not found. Falling back to latest .html page.")
    html_files = sorted([
        f for f in os.listdir(DOCS_DIR)
        if f.endswith(".html") and f != "index.html"
    ], reverse=True)
    if not html_files:
        raise FileNotFoundError("No HTML pages found in docs/")
    daily_path = os.path.join(DOCS_DIR, html_files[0])

# Read daily page and parse for OG tags
with open(daily_path, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

# Extract or fallback image for og:image
img_tag = soup.find("meta", property="og:image")
img_url = img_tag["content"] if img_tag else soup.find("img")["src"]
if img_url.startswith("/"):
    img_url = f"https://djz2k.github.io/dilbert-rss{img_url}"
elif img_url.startswith("images/"):
    img_url = f"https://djz2k.github.io/dilbert-rss/{img_url}"

# Update OG tags (even if missing in source)
og_title = soup.find("meta", property="og:title")
if not og_title:
    og_title = soup.new_tag("meta", property="og:title", content=f"Dilbert for {today_str}")
    soup.head.append(og_title)
else:
    og_title["content"] = f"Dilbert for {today_str}"

og_desc = soup.find("meta", property="og:description")
if not og_desc:
    og_desc = soup.new_tag("meta", property="og:description", content="View today’s Dilbert comic.")
    soup.head.append(og_desc)
else:
    og_desc["content"] = "View today’s Dilbert comic."

og_img = soup.find("meta", property="og:image")
if not og_img:
    og_img = soup.new_tag("meta", property="og:image", content=img_url)
    soup.head.append(og_img)
else:
    og_img["content"] = img_url

# Write to index.html
with open(index_path, "w", encoding="utf-8") as f:
    f.write(str(soup))

print(f"Updated index.html with OG tags from {daily_path}")
