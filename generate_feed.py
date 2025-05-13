import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from feedgen.feed import FeedGenerator
from xml.etree.ElementTree import Element

# Constants
COMIC_URL = 'https://dilbert-viewer.herokuapp.com/random'
RSS_FILE = 'docs/dilbert-clean.xml'

# Ensure the docs directory exists
os.makedirs('docs', exist_ok=True)

# Fetch the random comic
res = requests.get(COMIC_URL)
soup = BeautifulSoup(res.text, 'html.parser')
img = soup.find('img')
img_url = img['src'] if img else None

if img_url:
    fg = FeedGenerator()
    fg.load_extension('media')
    fg.title('Daily Dilbert')
    fg.link(href='https://djz2k.github.io/dilbert-rss/dilbert-clean.xml', rel='self')
    fg.description('A new Dilbert comic every day.')
    fg.language('en')

    fe = fg.add_entry()
    now = datetime.now(timezone.utc)
    fe.title(f'Dilbert - {now.strftime("%Y-%m-%d")}')
    fe.pubDate(now)
    fe.link(href=img_url)
    fe.guid(img_url, permalink=True)

    # Embed comic in body
    fe.description(f'<p><img src="{img_url}" alt="Dilbert comic for {now.strftime("%Y-%m-%d")}" /></p>')

    # Inject <media:content> manually without <media:group>
    media_content = Element("media:content", {
        "url": img_url,
        "type": "image/jpeg",
        "medium": "image"
    })
    fe._feed_entry.append(media_content)

    # Output the feed
    fg.rss_file(RSS_FILE)
    print(f"✅ RSS updated with comic: {img_url}")
else:
    print("⚠️ No image found.")
