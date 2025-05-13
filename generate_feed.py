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

# Fetch the random comic
res = requests.get(COMIC_URL)
soup = BeautifulSoup(res.text, 'html.parser')
img = soup.find('img')
img_url = img['src'] if img else None

if img_url:
    fg = FeedGenerator()
    fg.load_extension('media')
    fg.title('Daily Dilbert')
    fg.link(href='https://djz2k.github.io/dilbert-rss/', rel='alternate')
    fg.link(href='https://djz2k.github.io/dilbert-rss/dilbert-clean.xml', rel='self')
    fg.description('A new Dilbert comic every day.')
    fg.language('en')

    fe = fg.add_entry()
    now = datetime.now(timezone.utc)
    fe.title(f'Dilbert - {now.strftime("%Y-%m-%d")}')
    fe.pubDate(now)

    # Point to the HTML page as canonical entry link
    html_url = f"https://djz2k.github.io/dilbert-rss/dilbert-{now.strftime('%Y-%m-%d')}.html"
    fe.link(href=html_url)
    fe.guid(html_url, permalink=True)

    # Inline image in the description
    fe.description(f'<p><img src="{img_url}" alt="Dilbert comic for {now.strftime("%Y-%m-%d")}" /></p>')

    # Write initial RSS file
    fg.rss_file(RSS_FILE)

    # Modify RSS file manually with ElementTree
    tree = ET.parse(RSS_FILE)
    root = tree.getroot()
    ET.register_namespace('media', "http://search.yahoo.com/mrss/")
    ET.register_namespace('atom', "http://www.w3.org/2005/Atom")

    channel = root.find('channel')
    item = channel.find('item')

    # Insert <media:content> into <item>
    media_content = ET.Element('{http://search.yahoo.com/mrss/}content', {
        'url': img_url,
        'type': 'image/jpeg',
        'medium': 'image'
    })
    item.append(media_content)

    # Insert <image> BEFORE <item>
    image_tag = ET.Element('image')
    ET.SubElement(image_tag, 'url').text = img_url
    ET.SubElement(image_tag, 'title').text = 'Daily Dilbert'
    ET.SubElement(image_tag, 'link').text = 'https://djz2k.github.io/dilbert-rss/'
    channel.insert(list(channel).index(item), image_tag)

    # Save updated XML
    tree.write(RSS_FILE, encoding='utf-8', xml_declaration=True)

    # Generate the daily HTML page for rich previews
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta property="og:title" content="Dilbert - {now.strftime('%Y-%m-%d')}" />
  <meta property="og:description" content="Today's Dilbert comic" />
  <meta property="og:image" content="{img_url}" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="{html_url}" />
  <title>Dilbert - {now.strftime('%Y-%m-%d')}</title>
  <style>body {{ font-family: sans-serif; text-align: center; padding: 2em; }}</style>
</head>
<body>
  <h1>Dilbert - {now.strftime('%Y-%m-%d')}</h1>
  <img src="{img_url}" alt="Dilbert comic for {now.strftime('%Y-%m-%d')}" style="max-width: 100%; height: auto;" />
  <p><a href="{img_url}" target="_blank">View original image</a></p>
</body>
</html>
"""
    html_path = f'docs/dilbert-{now.strftime("%Y-%m-%d")}.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_template)

    # Generate index.html pointing to the latest
    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta property="og:title" content="Today's Dilbert Comic" />
  <meta property="og:description" content="The latest Dilbert comic" />
  <meta property="og:image" content="{img_url}" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://djz2k.github.io/dilbert-rss/index.html" />
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

    print(f"✅ RSS + HTML + index updated for {now.strftime('%Y-%m-%d')}")
else:
    print("⚠️ No image found.")
