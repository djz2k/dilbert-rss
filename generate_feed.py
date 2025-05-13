import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from feedgen.feed import FeedGenerator

# Constants
COMIC_URL = 'https://dilbert-viewer.herokuapp.com/random'
RSS_FILE = 'docs/dilbert.xml'

# Ensure the docs directory exists
os.makedirs('docs', exist_ok=True)

# Fetch the random comic
res = requests.get(COMIC_URL)
soup = BeautifulSoup(res.text, 'html.parser')
img = soup.find('img')
img_url = img['src'] if img else None

# Generate RSS feed
if img_url:
    fg = FeedGenerator()
    fg.load_extension('media')  # Enables <media:content>
    fg.title('Daily Dilbert')
    fg.link(href='https://djz2k.github.io/dilbert-rss/dilbert.xml', rel='self')
    fg.description('A new Dilbert comic every day.')

    fe = fg.add_entry()
    now = datetime.now(timezone.utc)
    fe.title(f'Dilbert - {now.strftime("%Y-%m-%d")}')
    fe.pubDate(now)
    fe.link(href=img_url)

    # Embed image in the description
    fe.description(f'<p><img src="{img_url}" alt="Dilbert comic for {now.strftime("%Y-%m-%d")}" /></p>')

    # Add media:content for better RSS support
    fe.media.content({
        'url': img_url,
        'type': 'image/jpeg',  # You could use 'image/png' if needed
        'medium': 'image',
    })

    fg.rss_file(RSS_FILE)
    print(f"✅ RSS updated with comic: {img_url}")
else:
    print("⚠️ No image found.")
