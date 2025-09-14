import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from feedgen.feed import FeedGenerator
from xml.etree import ElementTree as ET

# Constants
COMIC_URL = 'https://dilbert-viewer.herokuapp.com/random'
RSS_FILE = 'docs/dilbert-clean.xml'
HTML_TEMPLATE = 'docs/dilbert-{date}.html'
HOMEPAGE = 'https://djz2k.github.io/dilbert-rss/'

# Ensure output folder exists
os.makedirs('docs', exist_ok=True)

# Fetch the comic
res = requests.get(COMIC_URL)
soup = BeautifulSoup(res.text, 'html.parser')
img = soup.find('img')
img_url = img['src'] if img else None

if img_url:
    fg = FeedGenerator()
    fg.load_extension('media')
    fg.title('Daily Dilbert')
    fg.link(href=HOMEPAGE, rel='alternate')
    fg.link(href=HOMEPAGE + 'dilbert-clean.xml', rel='self')
    fg.id(HOMEPAGE)
    fg.description('A new Dilbert comic every day.')
    fg.language('en')

    fe = fg.add_entry()
    now = datetime.now(timezone.utc)
    today_str = now.strftime('%Y-%m-%d')
    html_url = f"{HOMEPAGE}dilbert-{today_str}.html"

    fe.title(f'Dilbert - {today_str}')
    fe.pubDate(now)
    fe.link(href=html_url)
    fe.guid(html_url, permalink=True)
    fe.description(f'<p><img src="{img_url}" alt="Dilbert comic for {today_str}" /></p>')

    # Generate RSS feed
    fg.rss_file(RSS_FILE)

    # Enhance with media content
    tree = ET.parse(RSS_FILE)
    root = tree.getroot()
    ET.register_namespace('media', "http://search.yahoo.com/mrss/")
    ET.register_namespace('atom', "http://www.w3.org/2005/Atom")

    channel = root.find('channel')
    item = channel.find('item')

    # <media:content>
    media_content = ET.Element('{http://search.yahoo.com/mrss/}content', {
        'url': img_url,
        'type': 'image/jpeg',
        'medium': 'image'
    })
    item.append(media_content)

    # <image> block for feed
    image_tag = ET.Element('image')
    ET.SubElement(image_tag, 'url').text = img_url
    ET.SubElement(image_tag, 'title').text = 'Daily Dilbert'
    ET.SubElement(image_tag, 'link').text = HOMEPAGE
    channel.insert(0, image_tag)

    tree.write(RSS_FILE, encoding='utf-8', xml_declaration=True)

    # Generate per-day HTML page with Open Graph meta tags
    html_output = HTML_TEMPLATE.format(date=today_str)
    with open(html_output, 'w') as f:
        f.write(f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dilbert Comic - {today_str}</title>
  <meta property="og:title" content="Dilbert Comic - {today_str}" />
  <meta property="og:image" content="{img_url}" />
  <meta property="og:description" content="Daily Dilbert comic for {today_str}" />
  <meta property="og:url" content="{html_url}" />
  <meta property="og:type" content="article" />
</head>
<body>
  <h1>Dilbert - {today_str}</h1>
  <img src="{img_url}" alt="Dilbert comic for {today_str}" />
</body>
</html>''')
