import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from feedgen.feed import FeedGenerator
from xml.etree import ElementTree as ET

# Constants
COMIC_URL = 'https://dilbert-viewer.herokuapp.com/random'
RSS_FILE = 'docs/dilbert-clean.xml'

# Ensure output folder exists
os.makedirs('docs', exist_ok=True)

# Fetch a random Dilbert comic
res = requests.get(COMIC_URL)
soup = BeautifulSoup(res.text, 'html.parser')
img = soup.find('img')
img_url = img['src'] if img else None

if img_url:
    fg = FeedGenerator()
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
    fe.description(f'<p><img src="{img_url}" alt="Dilbert comic for {now.strftime("%Y-%m-%d")}" /></p>')

    # Generate the feed and manually inject media:content
    fg.rss_file(RSS_FILE)
    # Parse the RSS XML
    tree = ET.parse(RSS_FILE)
    root = tree.getroot()

    # Locate the <channel> tag
    channel = root.find('channel')

    # Inject <image> block if not already present
    image_tag = ET.SubElement(channel, 'image')
    ET.SubElement(image_tag, 'url').text = img_url
    ET.SubElement(image_tag, 'title').text = 'Daily Dilbert'
    ET.SubElement(image_tag, 'link').text = 'https://djz2k.github.io/dilbert-rss/'

    # Re-save the updated XML with channel image included
    tree.write(RSS_FILE, encoding='utf-8', xml_declaration=True)

    # Inject <media:content> using ElementTree
    tree = ET.parse(RSS_FILE)
    root = tree.getroot()

    # Register the media namespace
    media_ns = "http://search.yahoo.com/mrss/"
    ET.register_namespace('media', media_ns)

    # Add <media:content> to the first <item>
    channel = root.find('channel')
    item = channel.find('item')
    media_content = ET.SubElement(item, f'{{{media_ns}}}content', {
        'url': img_url,
        'type': 'image/jpeg',
        'medium': 'image'
    })

    # Write it back
    tree.write(RSS_FILE, encoding='utf-8', xml_declaration=True)

    print(f"✅ RSS updated with comic and media:content: {img_url}")
else:
    print("⚠️ No image found.")
