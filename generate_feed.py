import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from feedgen.feed import FeedGenerator
from xml.etree import ElementTree as ET

# Constants
COMIC_URL = 'https://dilbert-viewer.herokuapp.com/random'
RSS_FILE = 'docs/dilbert-clean.xml'
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
    fg.link(href=HOMEPAGE, rel='alternate')  # Homepage for human readers
    fg.link(href=HOMEPAGE + 'dilbert-clean.xml', rel='self')  # Feed URL
    fg.id(HOMEPAGE)  # Set channel ID to homepage
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

    # Generate initial feed XML
    fg.rss_file(RSS_FILE)

    # Clean up the feed with ElementTree
    tree = ET.parse(RSS_FILE)
    root = tree.getroot()
    ET.register_namespace('media', "http://search.yahoo.com/mrss/")
    ET.register_namespace('atom', "http://www.w3.org/2005/Atom")

    channel = root.find('channel')
    item = channel.find('item')

    # Add <media:content>
    media_content = ET.Element('{http://search.yahoo.com/mrss/}content', {
        'url': img_url,
        'type': 'image/jpeg',
        'medium': 'image'
    })
    item.append(media_content)

    # Add <image> block at top of <channel>
    image_tag = ET.Element('image')
    ET.SubElement(image_tag, 'url').text = img_url
    ET.SubElement(image_tag, 'title').text = 'Daily Dilbert'
    ET.SubElement(image_tag, 'link').text = HOMEPAGE
    channel.insert(list(channel).index(item), image_tag)

    tree.write(RSS_FILE, encoding='utf-8', xml_declaration=True)

    # Generate daily HTML page with OG metadata
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta property="og:title" content="Dilbert - {today_str}" />
  <meta property="og:description" content="Today's Dilbert comic" />
  <meta property="og:image" content="{img_url}" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="{html_url}" />
  <title>Dilbert - {today_str}</title>
  <style>body {{ font-family: sans-serif; text-align: center; padding: 2em; }}</style>
</head>
<body>
  <h1>Dilbert - {today_str}</h1>
  <img src="{img_url}" alt="Dilbert comic for {today_str}" style="max-width: 100%; height: auto;" />
  <p><a href="{img_url}" target="_blank">View original image</a></p>
</body>
</html>
"""
    with open(f'docs/dilbert-{today_str}.html', 'w', encoding='utf-8') as f:
        f.write(html_template)

    # Generate index.html that always points to latest
    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta property="og:title" content="Today's Dilbert Comic" />
  <meta property="og:description" content="The latest Dilbert comic" />
  <meta property="og:image" content="{img_url}" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="{HOMEPAGE}" />
  <title>Today's Dilbert</title>
  <style>body {{ font-family: sans-serif; text-align: center; padding: 2em; }}</style>
</head>
<body>
  <h1>Today's Dilbert</h1>
  <a href="{html_url}">
    <img src="{img_url}" alt="Latest Dilbert comic" style="max-width: 100%; height: auto;" />
  </a>
  <p><a href="{html_url}">View permanent link</a></p>
</body>
</html>
"""
    with open('docs/index.html', 'w', encoding='utf-8') as f:
        f.write(index_html)

    print(f"✅ RSS, HTML, and index updated for {today_str}")
else:
    print("⚠️ No image found.")
