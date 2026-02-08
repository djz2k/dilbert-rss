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
MAX_RETRIES = 5


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


def try_fetch_comic():
    try:
        response = requests.get("https://dilbert-viewer.herokuapp.com/random", headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        img_tag = soup.find("img", {"src": re.compile(r"amuniversal\\.com")})
        return img_tag["src"] if img_tag else None
    except Exception as e:
        print(f"❌ Error during comic fetch: {e}")
        return None


def download_unique_comic(date_str, used_comics):
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"🔁 Attempt {attempt} to fetch unique comic...")
        image_url = try_fetch_comic()
        if not image_url:
            continue

        base_filename = os.path.basename(image_url).split("?")[0]
        base_filename = os.path.splitext(base_filename)[0]
        if base_filename in used_comics:
            print(f"⚠️ Comic {base_filename} already used. Trying again...")
            continue

        image_filename = f"{base_filename}-{date_str}.jpg"
        local_path = os.path.join(OUTPUT_DIR, "images", image_filename)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        try:
            img_data = requests.get(image_url, headers=HEADERS, timeout=15)
            img_data.raise_for_status()
            with open(local_path, "wb") as f:
                f.write(img_data.content)
            print(f"✅ Downloaded image: {local_path}")
            return base_filename, image_filename, local_path, image_url
        except Exception as e:
            print(f"❌ Error saving comic image: {e}")

    print("❌ Failed to fetch a unique comic after multiple attempts.")
    return None, None, None, None


def generate_html(date_str, image_filename, comic_url):
    html_path = os.path.join(OUTPUT_DIR, f"dilbert-{date_str}.html")
    page_url = f"{BASE_URL}/dilbert-{date_str}.html"
    image_url = f"{BASE_URL}/images/{image_filename}"

    html = f"""<!DOCTYPE html>
<html lang=\"en\" prefix=\"og: http://ogp.me/ns#\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Dilbert for {date_str}</title>
  <meta property=\"og:title\" content=\"Dilbert for {date_str}\" />
  <meta property=\"og:type\" content=\"article\" />
  <meta property=\"og:url\" content=\"{page_url}\" />
  <meta property=\"og:image\" content=\"{image_url}\" />
  <meta property=\"og:image:type\" content=\"image/jpeg\" />
  <meta property=\"og:image:width\" content=\"1200\" />
  <meta property=\"og:image:height\" content=\"630\" />
  <meta property=\"og:description\" content=\"View today's Dilbert comic.\" />
  <meta name=\"twitter:card\" content=\"summary_large_image\" />
  <meta name=\"twitter:title\" content=\"Dilbert for {date_str}\" />
  <meta name=\"twitter:description\" content=\"View today's Dilbert comic.\" />
  <meta name=\"twitter:image\" content=\"{image_url}\" />
</head>
<body>
  <h1>Dilbert for {date_str}</h1>
  <a href=\"{comic_url}\" target=\"_blank\">
    <img src=\"{image_url}\" alt=\"Dilbert comic for {date_str}\">
  </a>
</body>
</html>"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    return page_url


def main():
    today = get_today_date()
    used_comics = load_used_comics()

    base_filename, image_filename, local_path, image_url = download_unique_comic(today, used_comics)
    if not image_filename:
        print("❌ Exiting: No unique comic available.")
        return

    page_url = generate_html(today, image_filename, image_url)

    feed = Rss201rev2Feed(
        title="Daily Dilbert",
        link=f"{BASE_URL}/dilbert-clean.xml",
        description="Unofficial Dilbert feed with full comic previews.",
        language="en",
    )

    feed.add_item(
        title=f"Dilbert for {today}",
        link=page_url,
        description=f'<p>Dilbert comic for {today}.</p><img src="{BASE_URL}/images/{image_filename}" alt="Dilbert comic" />',
        unique_id=hashlib.md5(page_url.encode()).hexdigest(),
        pubdate=datetime.datetime.now(datetime.UTC),
        enclosures=[type(
            "Enclosure",
            (object,),
            {
                "url": f"{BASE_URL}/images/{image_filename}",
                "length": str(os.path.getsize(local_path)),
                "mime_type": "image/jpeg",
            },
        )()],
    )

    with open(os.path.join(OUTPUT_DIR, "dilbert-clean.xml"), "w", encoding="utf-8") as f:
        feed.write(f, "utf-8")

    used_comics.add(base_filename)
    save_used_comics(used_comics)
    print(f"✅ Comic {base_filename} saved and feed updated.")


if __name__ == "__main__":
    main()
