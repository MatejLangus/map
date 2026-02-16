"""
/**
 * @file blog_generator.py
 * @brief Script for fetching, processing, and rendering blog posts into a static site.
 *
 * This script handles:
 *  - Fetching all blog entries from a local JSON feed or remote URL.
 *  - Parsing post metadata, dates, categories, and generating unique slugs.
 *  - Modifying HTML content for images, lightbox support, and WebP optimization.
 *  - Rendering individual post HTML with author, date, thumbnail, labels, and summary.
 *  - Replacing placeholder <script> blocks in templates with rendered post HTML.
 *  - Building archive sidebar HTML and label navigation for the site.
 *  - Managing last-modified tracking and sitemap generation.
 *
 * @author Metod Langus
 * @date 2025-12-08
 * @last-modified 2026-02-16
 */
"""

import re
import requests
from pathlib import Path
from slugify import slugify
from collections import defaultdict
from datetime import datetime, timezone
from babel.dates import format_datetime
from xml.etree.ElementTree import Element, SubElement, ElementTree
from zoneinfo import ZoneInfo  # Python 3.9+
from dateutil import parser  # pip install python-dateutil
from bs4 import BeautifulSoup
from collections import defaultdict
from urllib.parse import urlparse, urlunparse, urljoin
import os
import json
import hashlib
import time

# Settings - Change this one line when switching local <-> GitHub Pages
BASE_SITE_URL = "https://matejlangus.github.io/map"    # GitHub Pages
# BASE_SITE_URL = f"http://127.0.0.1:5500"               # Live server

GITHUB_USER_NAME = "matejlangus"
GITHUB_REPO_NAME = "map"
LOCAL_REPO_PATH  = os.path.dirname(os.path.abspath(__file__))

BLOG_AUTHOR = "Matej Langus"
BLOG_TITLE = "Matej lezel je taM"

# Constants
entries_per_page = 12 # Set pagination on home and label pages
NO_IMAGE = "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEih6RhkrzOOLNxaVeJR-PiYl4gL_LCvnt8_mQJMJ1QLqVoKAovrkocbpwT5Pf7Zc7jLFnKH2F4MdWZR7Fqq4ZDd1T5FqVB4Wn6uxoP1_JcGEprf-tt_7HqeHhLjKnaFHs3xrkitzcqQNmNaiVT-MrgmJgxjARcUDGpEVYdpif-J2gJF72h_xB9qnLkKfUH4/s1600/no-image-icon.jpg"
DEFAULT_OG_IMAGE = "https://img.relive.com/-/w:1000/aHR0cHM6Ly91YS5yZWxpdmUuY2MvMTcyNzE0NjQvMjAyMjA3MTdfMDk1ODM4LmpwZ18xNjU4MDQ0NzE2MDAwLmpwZw=="
SLIDESHOW_COVER_IMAGE = "https://img.relive.com/-/w:1000/aHR0cHM6Ly91YS5yZWxpdmUuY2MvMTcyNzE0NjQvMjAyMjA3MTdfMDk1ODM4LmpwZ18xNjU4MDQ0NzE2MDAwLmpwZw=="
SLIDESHOW_COVER_UPPER_TEXT = "Cristallo di Mezzo"
SLIDESHOW_COVER_TEXT = ""

BLOG_TITLE_SVG = """<svg class='logo-svg' height='160' version='1.0' viewBox="0 0 3400 168" width="1188" xmlns="http://www.w3.org/2000/svg" aria-labelledby="logoTitle logoDesc" role="img">
  <desc id="logoDesc">Site title rendered as SVG text using Rubik Doodle Shadow font</desc>
  <rect width="100%" height="100%" fill="transparent"/>
  <g fill="#666">
    <text x="50%" y="50%" text-anchor="middle" dominant-baseline="central"
          font-family="'Rubik Doodle Shadow', cursive, sans-serif"
          font-weight="800"
          font-size="360"
          letter-spacing="3">
      Matej lezel je taM
    </text>
  </g>
</svg>"""


OUTPUT_DIR = Path.cwd() # Current path
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SITEMAP_FILE = "sitemap.xml"
LASTMOD_DB = Path("build/lastmod.json")

BASE_FEED_PATH = f"{LOCAL_REPO_PATH }/data/all-posts.json"
REMOTE_DB_URL = f"{BASE_SITE_URL}/.build/lastmod.json"

def load_lastmod_db():
    if LASTMOD_DB.exists():
        with open(LASTMOD_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_lastmod_db(db):
    LASTMOD_DB.parent.mkdir(parents=True, exist_ok=True)
    with open(LASTMOD_DB, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)  

def compute_md5(file_path: Path) -> str:
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def override_domain(url, base_site_url):
    """
    Overrides the domain from base_site_url, preserving the full path, query, and fragment
    from the original URL. Prevents duplication of base paths.
    """
    parsed_original = urlparse(url)
    parsed_base = urlparse(base_site_url)

    # Keep the original path, query, and fragment
    new_url = urlunparse((
        parsed_base.scheme,   # scheme from base
        parsed_base.netloc,   # domain from base
        parsed_original.path, # full path from original
        parsed_original.params,
        parsed_original.query,
        parsed_original.fragment
    ))
    return new_url

def parse_entry_date(entry, index=None):
    published = entry.get("published", {}).get("$t", "")
    local_tz = ZoneInfo("Europe/Ljubljana")

    try:
        parsed_date = parser.isoparse(published).astimezone(local_tz)
        formatted_date = parsed_date.isoformat()
        year = str(parsed_date.year)
        month = f"{parsed_date.month:02d}"
    except Exception as e:
        if index is not None:
            print(f"Date parse error at index {index}: {e}")
        formatted_date, year, month = published, "unknown", "unknown"

    return formatted_date, year, month

def generate_unique_slugs(entries, return_type="slugs"):
    slugs = []
    archive_dict = defaultdict(lambda: defaultdict(list))

    for i, entry in enumerate(entries):

        links = entry.get("link", [])
        href = next(
            (l.get("href") for l in links if l.get("rel") == "alternate"),
            None
        )

        # Fallback slug
        unique_slug = f"post-{i}"
        year = month = "unknown"

        if href:
            path_parts = [p for p in urlparse(href).path.split("/") if p]

            # Try to detect pattern: .../posts/yyyy/mm/slug/ or .../posts/yyyy/mm/
            if "posts" in path_parts:
                try:
                    idx = path_parts.index("posts")
                    year = path_parts[idx + 1]
                    month = path_parts[idx + 2]

                    # slug may exist or not
                    # if missing, build one from title
                    if len(path_parts) > idx + 3:
                        unique_slug = path_parts[idx + 3]
                    else:
                        title = entry.get("title", {}).get("$t", f"untitled-{i}")
                        unique_slug = slugify(title)

                except Exception:
                    pass

        # Title
        title = entry.get("title", {}).get("$t", f"untitled-{i}")

        archive_dict[year][month].append((unique_slug, title))
        slugs.append(unique_slug)

    return archive_dict if return_type == "archive" else slugs

def fetch_all_entries():
    print("Fetching all paginated posts...")
    all_entries = []

    url = BASE_FEED_PATH
    print(f"Fetching: {url}")
    
    # Load JSON directly from local file
    with open(url, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("feed", {}).get("entry", [])
    all_entries.extend(entries)

    print(f"Total entries fetched: {len(all_entries)}")
    return all_entries

def fix_images_for_lightbox(html_content, post_title):
    """
    Modify image links in HTML content for lightbox compatibility.
    Keeps first image high resolution (/s1600/), others at /s1000/.
    Uses WebP, adds alt tags, <picture> elements, and loading attributes.
    Adds 'cover-photo' class to the first image.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    image_index = 0  # Track image count for loading priority

    for a_tag in soup.find_all("a"):
        img = a_tag.find("img")
        if not img:
            continue

        # Step 1: Determine <img> alt text
        data_skip = img.get("data-skip", "").lower()
        skip_keywords = [k.strip() for k in data_skip.split(";") if k.strip()]
        alt_text = ""

        # Find possible caption
        table = img.find_parent("table", class_="tr-caption-container")
        caption_td = None
        if table:
            caption_td = table.find("td", class_="tr-caption")

        caption_text = caption_td.get_text(strip=True) if caption_td and caption_td.get_text(strip=True) else ""

        # Step 1A: Assign alt text based on rules
        if image_index == 0:
            # First image (cover photo)
            alt_text = f"{BLOG_TITLE} | {BLOG_AUTHOR} \u2013 {post_title}"
        elif any(k in skip_keywords for k in ["peak", "best", "1", "2"]):
            # Tagged as peak/best/1/2
            if caption_text:
                alt_text = f"{post_title} \u2013 {caption_text}"
            else:
                alt_text = post_title
        elif "3" in skip_keywords:
            # Tag 3 → empty alt
            alt_text = ""
        else:
            alt_text = ""

        img["alt"] = alt_text

        # Step 2: Determine correct resolution
        src = img.get("src", "")
        href = a_tag.get("href", "")

        if image_index == 0:
            # First image high resolution
            new_src = re.sub(r"/s\d+/", "/s1200/", src)
            new_href = re.sub(r"/s\d+/", "/s1600/", href)
        else:
            # Other images downgraded to resolution
            new_src = re.sub(r"/s\d+/", "/s600/", src)
            new_href = re.sub(r"/s\d+/", "/s1000/", href)

        # Add -rw (WebP) if missing
        new_src = re.sub(r"(/s\d+)(/)", r"\1-rw\2", new_src)
        new_href = re.sub(r"(/s\d+)(/)", r"\1-rw\2", new_href)
        img["src"] = new_src
        a_tag["href"] = new_href

        # Step 3: Add lightbox attribute
        a_tag["data-lightbox"] = "Gallery"

        # Step 4: Loading and priority
        if image_index == 0:
            img["loading"] = "eager"
            img["fetchpriority"] = "high"
            img["class"] = img.get("class", []) + ["cover-photo"]
        else:
            img["loading"] = "lazy"
            img["fetchpriority"] = "low"

        image_index += 1

        # Step 5: Wrap in <picture> with WebP only (no JPEG fallback)
        picture = soup.new_tag("picture")
        source = soup.new_tag("source", srcset=new_src, type="image/webp")
        picture.append(source)

        img.extract()
        picture.append(img)

        a_tag.clear()
        a_tag.append(picture)

    return soup.prettify()

def render_post_html(entry, index, entries_per_page, slugify_func, post_id):

    published_raw = entry.get("published", {}).get("$t", "1970-01-01T00:00:00Z")
    published_dt = datetime.strptime(published_raw, "%Y-%m-%dT%H:%M:%S.%f%z")

    # Format published date in Slovenian (Unicode-safe)
    published = format_datetime(published_dt, "EEEE, d. MMMM y", locale="sl")


    title = entry.get("title", {}).get("$t", f"untitled-{index}")
    thumbnail = entry.get("media$thumbnail", {}).get("url", NO_IMAGE)
    link_list = entry.get("link", [])
    raw_link = next((l["href"] for l in link_list if l.get("rel") == "alternate"), "#")
    alternate_link = override_domain(raw_link, BASE_SITE_URL)
    categories = entry.get("category", [])

    label_one = next((c["term"].replace("1. ", "") for c in categories if c["term"].startswith("1. ")), "")
    label_six = next((c["term"].replace("6. ", "") for c in categories if c["term"].startswith("6. ")), "")

    label_one_link = f"{BASE_SITE_URL}/search/labels/{slugify_func(label_one)}/" if label_one else ""
    label_six_link = f"{BASE_SITE_URL}/search/labels/{slugify_func(label_six)}/" if label_six else ""

    page_number = 1 if entries_per_page == 0 else (index // entries_per_page + 1)

    style_attr = "" if entries_per_page == 0 else " visually-hidden"

    # --- Extract summary / description for alt text ---
    content_html = entry.get("content", {}).get("$t", "")
    soup = BeautifulSoup(content_html, "html.parser")

    def normalize(text):
        return ' '.join(text.split()).strip().lower()

    unwanted = [
        normalize("Summary, only on the post-container view."),
        normalize("Kaj češ lepšega, kot biti v naravi.")
    ]

    # Try extracting a <summary> or <meta name="description">
    summary_tag = soup.find("summary")
    if summary_tag and normalize(summary_tag.get_text()) not in unwanted:
        description = summary_tag.get_text().strip()
    else:
        meta_tag = soup.find("meta", attrs={"name": "description"})
        if meta_tag and normalize(meta_tag.get("content", "")) not in unwanted:
            description = meta_tag["content"].strip()
        else:
            description = title

    # Fallback alt text content
    alt_text = f"{description}"

    # --- Render HTML ---
    return f"""
          <div class="photo-entry" data-page="{page_number}"{style_attr}>
            <article class="my-post-outer-container">
              <div class="post">
                {'<div class="my-tag-container"><a href="' + label_six_link + '" class="my-labels label-six">' + label_six + '</a></div>' if label_six else ""}
                <a href="{alternate_link}" class="my-post-link" aria-label="{title}">
                  <div class="my-title-container">
                    {'<a href="' + label_one_link + '" class="my-labels">' + label_one + '</a>' if label_one else ""}
                    <h2 class="my-title">{title}</h2>
                  </div>
                </a>
                <div class="my-meta-data">
                  <div class="author-date">Dne {published}</div>
                </div>
                <div class="my-thumbnail" id="post-snippet-{post_id}">
                  <div class="my-snippet-thumbnail">
                    {'<img src="' + thumbnail.replace('/s72-c', '/s600-rw') + '" alt="' + alt_text + '">' if thumbnail else ""}
                  </div>
                </div>
                <a href="{alternate_link}" aria-label="{title}"></a>
              </div>
            </article>
          </div>"""

def replace_mypost_scripts_with_rendered_posts(content_html, entries, entries_per_page, slugify_func, render_func):
    """
    Replace <script> blocks containing one var postTitleX and optional var displayModeX
    with rendered post HTML from entries.

    Each <script> has one declaration like:
      var postTitle0 = '1234567890';
      var displayMode0 = 'alwaysVisible';

    If displayMode is not 'alwaysVisible', wraps content in a hidden div.

    Returns prettified updated HTML.
    """

    soup = BeautifulSoup(content_html, 'html.parser')

    # Build lookup of post_id -> (index, entry)
    post_id_to_entry = {}
    for idx, entry in enumerate(entries):
        full_id = entry.get("id", {}).get("$t", "")
        match = re.search(r'post-(\d+)$', full_id)
        if match:
            post_id = match.group(1)
            post_id_to_entry[post_id] = (idx, entry)

    for script in soup.find_all("script"):
        if not script.string:
            continue

        content = script.string

        # Match one postTitleX and one displayModeX in this script block
        m_title = re.search(r"var\s+postTitle(\d+)\s*=\s*['\"](\d+)['\"]\s*;", content)
        if not m_title:
            continue

        idx = m_title.group(1)
        post_id = m_title.group(2)

        # Find displayMode for the same index, default if missing
        m_mode = re.search(rf"var\s+displayMode{idx}\s*=\s*['\"]([^'\"]+)['\"]\s*;", content)
        display_mode = m_mode.group(1) if m_mode else "default"

        if post_id not in post_id_to_entry:
            continue

        post_index, post_entry = post_id_to_entry[post_id]

        rendered_html = render_func(
            post_entry,
            post_index,
            entries_per_page,
            slugify_func,
            post_id
        )

        if display_mode != "alwaysVisible":
            rendered_html = f'<div class="my-post-container" style="display:none;">{rendered_html}</div>'

        # Insert rendered HTML after script and remove the script tag
        script.insert_after(BeautifulSoup(rendered_html, "html.parser"))
        script.decompose()

    return soup.prettify()

def build_archive_sidebar_html(entries):
    """
    Generate complete archive sidebar HTML from Blogger entries.
    Clicking a year/month navigates to the correct archive page,
    arrow still expands/collapses the section.
    Numbers are displayed with a space before parentheses.
    """
    archive_dict = generate_unique_slugs(entries, return_type="archive")

    archive_html = """<aside class="sidebar-archive">
  <h2>Arhiv</h2>
"""

    for y in sorted(archive_dict.keys(), reverse=True):
        year_posts = archive_dict[y]
        year_count = sum(len(posts) for posts in year_posts.values())
        # Year link with space before parentheses
        archive_html += f"""  <details open>
    <summary><a href="{BASE_SITE_URL}/posts/{y}/">{y}</a>&nbsp;<span class="post-count" dir="ltr">({year_count})</span></summary>
"""

        for m in sorted(year_posts.keys(), reverse=True):
            posts = year_posts[m]
            try:
                # Format month name in Slovenian
                dummy_date = datetime.strptime(m, '%m')
                month_name = format_datetime(dummy_date, "LLLL", locale="sl")
            except ValueError:
                month_name = m
            month_label = f"{month_name} {y}"

            # Month link with space before parentheses
            archive_html += f"""    <details class="month-group">
      <summary><a href="{BASE_SITE_URL}/posts/{y}/{m}/">{month_label}</a>&nbsp;<span class="post-count" dir="ltr">({len(posts)})</span></summary>
      <ul>
"""

            for slug, title in posts:
                safe_title = (
                    title.replace("&", "&amp;")
                         .replace("<", "&lt;")
                         .replace(">", "&gt;")
                         .replace('"', "&quot;")
                         .replace("'", "&#x27;")
                )
                archive_html += f"""        <li><a href="{BASE_SITE_URL}/posts/{y}/{m}/{slug}/">{safe_title}</a></li>
"""

            archive_html += """      </ul>
    </details>
"""

        archive_html += "  </details>\n"

    archive_html += "</aside>"
    return archive_html

def save_archive_as_js(archive_html, output_path="assets/archive.js"):
    # Escape backticks so JS template literal doesn’t break
    safe_html = archive_html.replace("`", "\\`")

    js_code = f"""
document.addEventListener("DOMContentLoaded", function() {{
  // Insert archive HTML into placeholder
  document.getElementById("archive-placeholder").innerHTML = `{safe_html}`;

  // Add state remembering for all <details>
  document.querySelectorAll("#archive-placeholder details").forEach(function(det, idx) {{
    var key = "archive-state-" + idx;

    // Restore state from sessionStorage
    if (sessionStorage.getItem(key) === "open") {{
      det.setAttribute("open", "");
    }} else if (sessionStorage.getItem(key) === "closed") {{
      det.removeAttribute("open");
    }}

    // Save state when toggled
    det.addEventListener("toggle", function() {{
      sessionStorage.setItem(key, det.open ? "open" : "closed");
    }});
  }});
}});
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(js_code)

def save_navigation_as_js(labels_html, output_path="assets/navigation.js"):
    # Escape backticks so JS template literal doesn’t break
    safe_html = labels_html.replace("`", "\\`")

    js_code = f"""
document.addEventListener("DOMContentLoaded", function() {{
  // Insert labels HTML into placeholder
  document.getElementById("navigation-placeholder").innerHTML = `{safe_html}`;

  // Add state remembering for all <details>
  document.querySelectorAll("#navigation-placeholder details").forEach(function(det, idx) {{
    var key = "navigation-state-" + idx;

    // Restore state from sessionStorage
    if (sessionStorage.getItem(key) === "open") {{
      det.setAttribute("open", "");
    }} else if (sessionStorage.getItem(key) === "closed") {{
      det.removeAttribute("open");
    }}

    // Save state when toggled
    det.addEventListener("toggle", function() {{
      sessionStorage.setItem(key, det.open ? "open" : "closed");
    }});
  }});
}});
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(js_code)

def generate_labels_sidebar_html(feed_path):
    """Loads labels from a local Blogger JSON feed file and returns structured sidebar HTML."""

    # Load local JSON feed
    with open(feed_path, "r", encoding="utf-8") as f:
        feed_data = json.load(f)

    # Extract label terms
    labels_raw = [cat["term"] for cat in feed_data["feed"].get("category", [])]

    # Section titles by prefix number
    prefix_titles = {
        1: "Kategorija",
        2: "Država",
        3: "Gorstvo",
        4: "Časovno",
        5: "Ostalo",
        # 6 intentionally excluded from display
    }

    # Group labels by prefix
    label_groups = defaultdict(list)
    for label in labels_raw:
        match = re.match(r'^(\d+)', label)
        prefix = int(match.group(1)) if match else 99
        label_groups[prefix].append(label)

    # Sort prefixes and skip section 6
    sorted_prefixes = [p for p in sorted(label_groups.keys()) if p != 6]

    # HTML build
    label_html_parts = ["<aside class='sidebar-labels'><h2>Navigacija</h2>"]

    for idx, prefix in enumerate(sorted_prefixes):
        labels = sorted(label_groups[prefix], key=lambda l: l.lower())
        section_title = prefix_titles.get(prefix, "Ostalo")

        if idx == 0:
            label_html_parts.append(f"<div class='first-items'><h3>{section_title}:</h3><ul class='label-list'>")
        elif idx == 1:
            label_html_parts.append("<div class='remaining-items hidden' style='height:auto;'>")
            label_html_parts.append(f"<h3>{section_title}:</h3><ul class='label-list'>")
        else:
            label_html_parts.append(f"<h3>{section_title}:</h3><ul class='label-list'>")

        for raw_label in labels:
            clean_label = re.sub(r'^\d+\.\s*', '', raw_label)
            slug = slugify(clean_label)
            label_html_parts.append(
                f"<li><a class='label-name' href='{BASE_SITE_URL}/search/labels/{slug}/'>{clean_label}</a></li>"
            )

        label_html_parts.append("</ul>")

    # Closing tags
    if sorted_prefixes:
        label_html_parts.append("</div>")

    if len(sorted_prefixes) > 1:
        label_html_parts.append("""
        <span class='show-more pill-button'>Pokaži več</span>
        <span class='show-less pill-button hidden'>Pokaži manj</span>
        """)

    label_html_parts.append("</aside>")

    return "\n".join(label_html_parts)

def render_sidebar_settings(picture_settings=True, map_settings=True, current_page=""):
    sections = []

    # Always include the main heading once
    heading = "<h2>Nastavitve</h2>"

    if picture_settings:
        label_filter_html = generate_label_filter_section(feed_path=BASE_FEED_PATH)

        # Base section
        section_html = f"""
        <h3 class="title">Objave in predvajalniki slik</h3>
        <div style="display: inline-block; border-style: double; margin-left: 5px; padding: 5px;">
            <b>Število slik:</b> <span id="imagesLoadedCount">0</span>
        </div>
        <div style="display: flex; flex-direction: column; margin-left: 5px; margin-top: 15px; margin-bottom: 10px;">
            <label for='photosSliderElement'>
                <b>Obseg prikazanih slik:</b> <span id='photosValueElement'></span>
            </label>
            <input id='photosSliderElement' max='1' min='-1' step='2' type='range' value='initPhotos' style="width: 160px;"/>
        </div>
        """

        # Add the conditional section if the page matches
        if current_page in ("slideshow_page", "gallery_page"):
            section_html += f"""
        <div style="display: flex; align-items: center; gap: 5px; margin-left: 5px;">
            <span><b>Naključno prikazovanje:</b></span>
            <button id="toggleRandomButton" style="padding: 5px;">DA</button>
        </div>
        <div style="margin-top: 10px; margin-left: 5px;">
            <div><b>Slike iz objav:</b></div>
            <div style="margin-top: 5px; margin-left: 20px;">
                <b>med:</b> <input type="date" id="startDateInput">
            </div>
            <div style="margin-top: 5px; margin-left: 20px;">
                <b>in:</b> <input type="date" id="endDateInput">
            </div>
        </div>
        {label_filter_html}
        """

        sections.append(section_html)

    if map_settings:
        sections.append("""          <div id='map-settings'>
            <h3 class='title'>Zemljevid</h3>
            <!-- Slider Section -->
            <div style='display: flex; flex-direction: column; margin-left: 5px; margin-top: 5px; margin-bottom: 10px;'>
                <label for='photosMapSliderElement'>Obseg prikazanih slik: <span id='photosMapValueElement'/></label>
                <input id='photosMapSliderElement' max='3' min='-2' step='1' style='width: 160px;' type='range' value='initMapPhotos'/>
            </div>

            <!-- Date and Time Filters -->
            <div class='form-group'>
                <label for='dayFilterStart'>Od dne:</label>
                <input class='input-field' id='dayFilterStart' type='date'/>
            </div>
            <div class='form-group'>
                <label for='timeFilterStart'>od ure:</label>
                <input class='input-field' id='timeFilterStart' type='time'/>
            </div>
            <div class='form-group'>
                <label for='dayFilterEnd'>Do dne:</label>
                <input class='input-field' id='dayFilterEnd' type='date'/>
            </div>
            <div class='form-group'>
                <label for='timeFilterEnd'>do ure:</label>
                <input class='input-field' id='timeFilterEnd' type='time'/>
            </div>

            <!-- Daily Time Filters -->
            <div class='form-group'>
                <label for='dailyTimeFilterStart'>Med:</label>
                <input class='input-field' id='dailyTimeFilterStart' type='time' value='00:00'/>
            </div>
            <div class='form-group'>
                <label for='dailyTimeFilterEnd'>in:</label>
                <input class='input-field' id='dailyTimeFilterEnd' type='time' value='23:59'/>
            </div>

            <!-- Apply Filters Button -->
            <div class='form-group' style='display: flex; justify-content: center;'>
                <button class='pill-button' id='applyFilters'>Uporabi filtre</button>
            </div>
          </div>""")

    if not sections:
        return ""

    settings_html = "\n".join([heading] + sections)
    return f"""
    <div class="settings">
      {settings_html}
    </div>
    """
def generate_label_filter_section(feed_path):
    """
    Loads labels from a local Blogger JSON feed file and returns HTML for
    a selectable label filter section with collapsible checkboxes (play button style)
    and a Clear Filters button.
    """

    # Load local JSON feed
    with open(feed_path, "r", encoding="utf-8") as f:
        feed_data = json.load(f)

    labels_raw = [cat["term"] for cat in feed_data["feed"].get("category", [])]

    prefix_titles = {
        1: "Kategorija",
        2: "Država",
        3: "Gorstvo",
        4: "Časovno",
        5: "Ostalo",
    }

    label_groups = defaultdict(list)
    for label in labels_raw:
        match = re.match(r'^(\d+)', label)
        prefix = int(match.group(1)) if match else 99
        label_groups[prefix].append(label)

    sorted_prefixes = [p for p in sorted(label_groups.keys()) if p != 6]

    html_parts = [
        "<section class='label-filter-section' style='display: flex; flex-direction: column; margin-left: 5px; margin-top: 15px;'>"
    ]
    html_parts.append("<b>Prikaz slik iz objav z izbranimi oznakami:</b>")

    for prefix in sorted_prefixes:
        labels = sorted(label_groups[prefix], key=lambda l: l.lower())
        section_title = prefix_titles.get(prefix, "Ostalo")
        section_id = f"section_{prefix}"

        # Collapsible section with ▶ icon initially
        html_parts.append(f"""
        <div style="margin-bottom: 10px;">
            <button type="button" class="collapse-btn" 
                onclick="toggleSection('{section_id}', this)" 
                style="background:none;border:none;cursor:pointer;font-weight:bold;display:flex;align-items:center;gap:5px;">
                <span class="arrow-icon">▶</span> {section_title}
            </button>
            <div id="{section_id}" style="display:none; margin-top: 5px;">
                <ul class='label-filter-list'>
        """)

        for raw_label in labels:
            clean_label = re.sub(r'^\d+\.\s*', '', raw_label)
            html_parts.append(
                f"<li>"
                f"<label>"
                f"<input type='checkbox' class='label-filter-checkbox' data-prefix='{prefix}' value='{clean_label}'> {clean_label}"
                f"</label>"
                f"</li>"
            )

        html_parts.append("</ul></div></div>")

    # Add Clear Filters button
    html_parts.append("""
    <div style="margin-top: 10px;">
        <button type="button" id="clear-filters-btn" 
            style="background:#eee; border:1px solid #ccc; padding:5px 10px; cursor:pointer; border-radius:4px;">
            🗑️ Počisti filtre
        </button>
    </div>
    """)

    html_parts.append("</section>")

    return "\n".join(html_parts)






def generate_sidebar_html(picture_settings, map_settings, current_page):
    # Render settings section (includes conditional logic for photo player page)
    settings_html = render_sidebar_settings(picture_settings, map_settings, current_page)

    # Include labels and archive only if current page is posts or labels
    posts_sections = ""
    if current_page in ["posts", "labels", "home"]:
        posts_sections = f"""
        <div class="labels" id="navigation-placeholder">
          <script src="{BASE_SITE_URL}/assets/navigation.js"></script>
        </div>
        <div class="archive" id="archive-placeholder">
          <script src="{BASE_SITE_URL}/assets/archive.js"></script>
        </div>
        """

    # Include random image only on home page
    random_photo_sections = ""
    if current_page in ["home"]:
        random_photo_sections = f"""
        <div class="random-photo">
          <h2 class="title">Naključna fotografija</h2>
          <a href="{BASE_SITE_URL}/predvajalnik-fotografij/">
          <div class="slideshow-container">
            <!-- First image (initial) -->
            <div class="mySlides slide1" style="opacity: 1;">
              <div class="uppertext">{SLIDESHOW_COVER_UPPER_TEXT}</div>
              <img src={SLIDESHOW_COVER_IMAGE} alt="Initial Image" />
              <div class="text">{SLIDESHOW_COVER_TEXT}</div>
            </div>
            <div class="mySlides slide2">
              <div class="uppertext"></div>
              <img src="" alt="" />
              <div class="text"></div>
            </div>
          </div>
        </a>
      </div>"""

    # Full sidebar HTML
    return f"""
    <div class="sidebar-container">
      <div class="sidebar" id="sidebar">
        {random_photo_sections}
        <div class="pages">
          <aside class='sidebar-pages'><h2>Strani</h2>
            <li><a href="{BASE_SITE_URL}">Dnevnik</a></li>
            <li><a href="{BASE_SITE_URL}/predvajalnik-fotografij/">Predvajalnik naključnih fotografij</a></li>
            <li><a href="{BASE_SITE_URL}/galerija-fotografij/">Galerija fotografij</a></li>
            <li><a href="{BASE_SITE_URL}/seznam-aktivnosti/">Seznam aktivnosti</a></li>
            <li><a href="{BASE_SITE_URL}/zemljevid/">Zemljevid</a></li>
            <li><a href="{BASE_SITE_URL}/uporabne-povezave/">Uporabne povezave</a></li>
          </aside>
        </div>
        {settings_html}
        {posts_sections}
      </div>
    </div>
    """
def generate_header_html():
    return f"""
    <h1>
      <span style="position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; border: 0; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap;">
        {BLOG_TITLE}
      </span>
      <a class='logo-svg' href="{BASE_SITE_URL}">
        {BLOG_TITLE_SVG}
      </a>
    </h1>
    <div class="header-left">
      <button class="menu-toggle" onclick="toggleSidebar()">☰</button>
    </div>

    <div class="header-right">
      <button id="searchToggle" class="search-toggle" aria-label="Search">
        <svg xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            width="24" height="24"
            fill="none" stroke="#000" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
      </button>
      <div id="searchContainer" class="search-container">
        <input type="text" id="searchBox" placeholder="Išči objave...">

        <!-- Close button inside the search container -->
        <button id="searchClose" class="search-close" aria-label="Close search">
          ×
        </button>
      </div>
    </div>"""

def generate_footer_html():
    return f"""
  <footer class="site-footer" style="position: relative;">

    <p>
      Poganja 
      <a href="https://github.com" target="_blank" rel="noopener noreferrer" style="text-decoration: none;">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="72 72 496 496" width="16" height="16" fill="currentColor" style="vertical-align: text-top; margin-right: -1px;">
          <!--!Font Awesome Free v7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free -->
          <path fill="#f3891d" d="M237.9 461.4C237.9 463.4 235.6 465 232.7 465C229.4 465.3 227.1 463.7 227.1 461.4C227.1 459.4 229.4 457.8 232.3 457.8C235.3 457.5 237.9 459.1 237.9 461.4zM206.8 456.9C206.1 458.9 208.1 461.2 211.1 461.8C213.7 462.8 216.7 461.8 217.3 459.8C217.9 457.8 216 455.5 213 454.6C210.4 453.9 207.5 454.9 206.8 456.9zM251 455.2C248.1 455.9 246.1 457.8 246.4 460.1C246.7 462.1 249.3 463.4 252.3 462.7C255.2 462 257.2 460.1 256.9 458.1C256.6 456.2 253.9 454.9 251 455.2zM316.8 72C178.1 72 72 177.3 72 316C72 426.9 141.8 521.8 241.5 555.2C254.3 557.5 258.8 549.6 258.8 543.1C258.8 536.9 258.5 502.7 258.5 481.7C258.5 481.7 188.5 496.7 173.8 451.9C173.8 451.9 162.4 422.8 146 415.3C146 415.3 123.1 399.6 147.6 399.9C147.6 399.9 172.5 401.9 186.2 425.7C208.1 464.3 244.8 453.2 259.1 446.6C261.4 430.6 267.9 419.5 275.1 412.9C219.2 406.7 162.8 398.6 162.8 302.4C162.8 274.9 170.4 261.1 186.4 243.5C183.8 237 175.3 210.2 189 175.6C209.9 169.1 258 202.6 258 202.6C278 197 299.5 194.1 320.8 194.1C342.1 194.1 363.6 197 383.6 202.6C383.6 202.6 431.7 169 452.6 175.6C466.3 210.3 457.8 237 455.2 243.5C471.2 261.2 481 275 481 302.4C481 398.9 422.1 406.6 366.2 412.9C375.4 420.8 383.2 435.8 383.2 459.3C383.2 493 382.9 534.7 382.9 542.9C382.9 549.4 387.5 557.3 400.2 555C500.2 521.8 568 426.9 568 316C568 177.3 455.5 72 316.8 72zM169.2 416.9C167.9 417.9 168.2 420.2 169.9 422.1C171.5 423.7 173.8 424.4 175.1 423.1C176.4 422.1 176.1 419.8 174.4 417.9C172.8 416.3 170.5 415.6 169.2 416.9zM158.4 408.8C157.7 410.1 158.7 411.7 160.7 412.7C162.3 413.7 164.3 413.4 165 412C165.7 410.7 164.7 409.1 162.7 408.1C160.7 407.5 159.1 407.8 158.4 408.8zM190.8 444.4C189.2 445.7 189.8 448.7 192.1 450.6C194.4 452.9 197.3 453.2 198.6 451.6C199.9 450.3 199.3 447.3 197.3 445.4C195.1 443.1 192.1 442.8 190.8 444.4zM179.4 429.7C177.8 430.7 177.8 433.3 179.4 435.6C181 437.9 183.7 438.9 185 437.9C186.6 436.6 186.6 434 185 431.7C183.6 429.4 181 428.4 179.4 429.7z"/>
        </svg>
        GitHub
      </a>
    </p>
    <p>© {datetime.now().year} Matej Langus. Vse pravice pridržane. Temo izdelal <a href="https://metodlangus.github.io/" target="_blank">Metod Langus</a>.</p>
  </footer>
  </footer>"""

def generate_back_to_top_html():
    return """<button id="backToTop" title="Na vrh">↑</button>"""

def generate_searchbox_html():
    return f"""
    <div id="searchResults"></div>"""

def generate_post_navigation_html(entries, slugs, index, local_tz, year, month):
    """
    Generates HTML for previous and next post navigation based on the current post index.

    Args:
        entries (list): List of feed entry dicts.
        slugs (list): List of slug strings.
        index (int): Index of the current post.
        local_tz (tzinfo): Local timezone to convert dates.
        year (str): Fallback year (usually current post's year).
        month (str): Fallback month (usually current post's month).

    Returns:
        str: HTML navigation block.
    """

    # --- Previous post ---
    if index < len(entries) - 1:
        prev_entry = entries[index + 1]
        prev_title = prev_entry.get("title", {}).get("$t", "")
        prev_slug = slugs[index + 1]
        _, prev_year, prev_month = parse_entry_date(prev_entry, index=index + 1)
    else:
        prev_slug = prev_title = prev_year = prev_month = ""

    # --- Next post ---
    if index > 0:
        next_entry = entries[index - 1]
        next_title = next_entry.get("title", {}).get("$t", "")
        next_slug = slugs[index - 1]
        _, next_year, next_month = parse_entry_date(next_entry, index=index - 1)
    else:
        next_slug = next_title = next_year = next_month = ""

    # --- HTML navigation block ---
    nav_html = """
    <div class="nav-links-wrapper">
      <div class="nav-links">
    """

    if prev_slug:
        nav_html += f"""
        <div class="prev-link">
          <div class="pager-title">Prejšnja objava</div>
          <a href="{BASE_SITE_URL}/posts/{prev_year}/{prev_month}/{prev_slug}/">&larr; {prev_title}</a>
        </div>
        """

    if next_slug:
        nav_html += f"""
        <div class="next-link">
          <div class="pager-title">Naslednja objava</div>
          <a href="{BASE_SITE_URL}/posts/{next_year}/{next_month}/{next_slug}/">{next_title} &rarr;</a>
        </div>
        """

    nav_html += """
      </div>
    </div>
    """

    return nav_html

def generate_labels_html(entry, title, slug, year, month, formatted_date, post_id, label_posts_raw,
                         slugify, remove_first_prefix, remove_all_prefixes):
    labels_raw = []
    labels_html = "<div class='post-labels'><em>No labels</em></div>"

    if "category" in entry and isinstance(entry["category"], list):
        for cat in entry["category"]:
            label_raw = cat.get("term", "")
            labels_raw.append(label_raw)

            # Store raw-labeled post
            label_posts_raw[label_raw].append({
                "title": title,
                "slug": slug,
                "year": year,
                "month": month,
                "date": formatted_date,
                "postId": post_id
            })

        if labels_raw:
            label_links = []
            for label_raw in labels_raw:
                slug_part = remove_first_prefix(label_raw)
                label_url = f"{BASE_SITE_URL}/search/labels/{slugify(slug_part)}/"
                label_text = remove_all_prefixes(label_raw)
                label_links.append(f"<a class='my-labels' href='{label_url}'>{label_text}</a>")
            labels_html = "<div class='post-labels'>" + " ".join(label_links) + "</div>"

    return labels_html

def generate_homepage_html(entries):
    """Generates complete HTML <article> containers with Blogger-style pagination, sorted newest → oldest."""
    homepage_html = ""

    # Helper to extract published datetime from entry
    def get_published_date(entry):
        published_str = entry.get("published", {}).get("$t", "")
        try:
            # Parse ISO format
            return datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except Exception:
            return datetime.min  # fallback if missing

    # Sort entries newest first
    sorted_entries = sorted(entries, key=get_published_date, reverse=True)

    for i, entry in enumerate(sorted_entries):
        full_id = entry.get("id", {}).get("$t", "")
        match = re.search(r'post-(\d+)$', full_id)
        post_id = match.group(1) if match else ""

        if not post_id:
            print(f"Warning: Post at index {i} missing valid 'postId'")
            continue

        homepage_html += render_post_html(entry, i, entries_per_page, slugify, post_id)

    return homepage_html

# Helper to remove just the first prefix
def remove_first_prefix(label):
    return re.sub(r"^\d+\.\s*", "", label)

# Helper to remove all numeric prefixes
def remove_all_prefixes(label):
    return re.sub(r"^(?:\d+\.\s*)+", "", label)

def indent_xml(elem, level=0):
    """Pretty-print XML."""
    i = "\n" + "   " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "   "
        for child in elem:
            indent_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i
    return elem

def generate_url_element(loc, lastmod=None, changefreq=None, priority=None):
    """Create a <url> element for sitemap."""
    url = Element("url")
    SubElement(url, "loc").text = loc
    if changefreq:
        SubElement(url, "changefreq").text = changefreq
    if priority:
        SubElement(url, "priority").text = str(priority)
    if lastmod:
        SubElement(url, "lastmod").text = lastmod
    return url

def generate_sitemap_from_folder(folder_path: Path, exclude_dirs=None, exclude_files=None):
    """
    Generate sitemap.xml by scanning all .html files in folder_path,
    excluding directories in exclude_dirs and files in exclude_files.
    """
    if exclude_dirs is None:
        exclude_dirs = []
    if exclude_files is None:
        exclude_files = []

    lastmod_db = load_lastmod_db()
    new_lastmod_db = {}  # Collect updated entries

    urlset = Element("urlset", {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"})

    for html_file in folder_path.rglob("*.html"):
        relative_path = html_file.relative_to(folder_path).as_posix()

        # Skip excluded directories
        if any(f"{excl}/" in relative_path for excl in exclude_dirs):
            continue

        # Skip excluded files
        if relative_path in exclude_files:
            continue

        # Compute hash & lastmod
        md5 = compute_md5(html_file)
        key = relative_path

        if key in lastmod_db and lastmod_db[key]["md5"] == md5:
            # Unchanged → keep old lastmod
            lastmod = lastmod_db[key]["lastmod"]
        else:
            # Changed → update time
            lastmod = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Persist entry so next run can compare correctly
        new_lastmod_db[key] = {
            "md5": md5,
            "lastmod": lastmod
        }

        # Build URL
        url = f"{BASE_SITE_URL}/{relative_path}"

        # Determine priority
        parts = Path(relative_path).parts

        if parts[-1] == "index.html" and len(parts) <= 2:
            priority = 1                       # Root index or one level deep index.html
        elif "posts" in parts:
            priority = 1                       # Any posts file
        elif parts[0] == "search":
            priority = 0.8                     # search/ directory
        elif len(parts) == 1 and parts[0] != "index.html":
            priority = 0.6                     # other root HTML files
        else:
            priority = 0.5                     # fallback default

        changefreq = "monthly"

        urlset.append(generate_url_element(url, lastmod=lastmod, changefreq=changefreq, priority=priority))

    # Save updated DB (this was missing)
    save_lastmod_db(new_lastmod_db)

    # Pretty-print & write XML
    indent_xml(urlset)
    ElementTree(urlset).write(SITEMAP_FILE, encoding="utf-8", xml_declaration=True)
    print(f"Sitemap je bil ustvarjen in shranjen kot {SITEMAP_FILE}")

def update_lastmod_tracking(folder_path: Path, exclude_dirs=None, exclude_files=None):
    """
    Compare local HTML MD5 checksums with local DB.
    Always update local lastmod.json.
    """
    if exclude_dirs is None:
        exclude_dirs = []
    if exclude_files is None:
        exclude_files = []

    try:
        os.sync()
    except AttributeError:
        pass
    time.sleep(0.1)

    # Load local lastmod DB
    remote_db_path = Path("build/lastmod.json")
    if remote_db_path.exists():
        try:
            with open(remote_db_path, "r", encoding="utf-8") as f:
                remote_db = json.load(f)
        except Exception as e:
            print(f"WARNING: Could not read lastmod DB: {e}")
            remote_db = {}
    else:
        print("WARNING: Local lastmod DB not found.")
        remote_db = {}

    new_lastmod_db = {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def comparison_keys(rel_path: str):
        # index.html → check both file and folder
        if rel_path.endswith("index.html"):
            folder_key = rel_path[:-10]  # remove index.html
            if not folder_key.endswith("/"):
                folder_key += "/"
            file_key = rel_path
            url = f"https://{GITHUB_REPO_NAME}/{folder_key}"
            return [file_key, folder_key], url, file_key

        # normal file
        return [rel_path], f"https://{GITHUB_REPO_NAME}/{rel_path}", rel_path

    # Scan all html files
    for html_file in folder_path.rglob("*.html"):
        rel = html_file.relative_to(folder_path).as_posix()

        if any(f"{d}/" in rel for d in exclude_dirs):
            continue
        if rel in exclude_files:
            continue

        md5 = compute_md5(html_file)
        keys_to_check, url_to_submit, storage_key = comparison_keys(rel)

        # Remote record
        old_md5 = None
        old_lastmod = None
        for k in keys_to_check:
            if k in remote_db:
                old_md5 = remote_db[k].get("md5")
                old_lastmod = remote_db[k].get("lastmod")
                break

        # Compare
        if old_md5 == md5 and old_md5 is not None:
            lastmod = old_lastmod or now
        else:
            lastmod = now

        # Save entry
        new_lastmod_db[storage_key] = {"md5": md5, "lastmod": lastmod}

    save_lastmod_db(new_lastmod_db)
    print(f"Processed {len(new_lastmod_db)} files")

def fetch_and_save_all_posts(entries):
    # HTML sections
    sidebar_html = generate_sidebar_html(picture_settings=True, map_settings=False, current_page="posts")
    header_html = generate_header_html()
    searchbox_html = generate_searchbox_html()
    footer_html = generate_footer_html()
    back_to_top_html = generate_back_to_top_html()

    local_tz = ZoneInfo("Europe/Ljubljana")
    label_posts_raw = defaultdict(list)
    slugs = generate_unique_slugs(entries, local_tz)

    for index, entry in enumerate(entries):  # Only first 5 entries entries[:5]
        title = entry.get("title", {}).get("$t", f"untitled-{index}")
        content_html = entry.get("content", {}).get("$t", "")
        slug = slugs[index]

        full_id = entry.get("id", {}).get("$t", "")
        post_id = full_id.split("post-")[-1] if "post-" in full_id else ""
        author = entry.get("author", {}).get("name", {}).get("$t", "")
        formatted_date, year, month = parse_entry_date(entry, index)

        # Replace custom post containers
        content_html = replace_mypost_scripts_with_rendered_posts(
            content_html,
            entries,
            entries_per_page=0,
            slugify_func=slugify,
            render_func=render_post_html
        )

        # Fix images for lightbox
        content_html = fix_images_for_lightbox(content_html, title)

        # First image for og:image
        soup = BeautifulSoup(content_html, "html.parser")
        first_img_tag = soup.find("img")
        og_image = first_img_tag["src"] if first_img_tag else DEFAULT_OG_IMAGE

        # Description extraction
        def normalize(text): return ' '.join(text.split()).strip().lower()
        unwanted = [normalize("Summary, only on the post-container view."), normalize("Kaj češ lepšega, kot biti v naravi.")]
        summary_tag = soup.find("summary")
        if summary_tag and normalize(summary_tag.get_text()) not in unwanted:
            description = summary_tag.get_text().strip()
        else:
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag and normalize(meta_tag.get("content", "")) not in unwanted:
                description = meta_tag["content"].strip()
            else:
                description = title

        og_url = f"{BASE_SITE_URL}/posts/{year}/{month}/{slug}/"
        metadata_html = f"<div class='post-date' data-date='{formatted_date}'></div>"
        nav_html = generate_post_navigation_html(entries, slugs, index, local_tz, year, month)
        labels_html = generate_labels_html(entry, title, slug, year, month, formatted_date, post_id,
                                           label_posts_raw, slugify, remove_first_prefix, remove_all_prefixes)

        # Schema.org JSON-LD
        structured_data = f"""
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    "headline": "{title}",
    "image": "{og_image}",
    "author": {{
      "@type": "Person",
      "name": "{BLOG_AUTHOR}"
    }},
    "publisher": {{
      "@type": "Person",
      "name": "{BLOG_TITLE}",
      "logo": {{
        "@type": "ImageObject",
        "url": "https://matejlezeljetam.blogspot.com/favicon.ico"
      }}
    }},
    "description": "{description}",
    "datePublished": "{formatted_date}",
    "url": "{og_url}"
  }}
  </script>
"""

        # GitHub Comments (Utterances)
        comments_html = f"""
      <section id="comments">
        <h2>Komentarji</h2>
        <script src="https://utteranc.es/client.js"
          repo="{GITHUB_USER_NAME}/{GITHUB_REPO_NAME}"
          issue-term="pathname"
          theme="github-light"
          crossorigin="anonymous"
          async>
        </script>
      </section>"""

        # Create nested folder and save as index.html
        post_dir = OUTPUT_DIR / "posts" / year / month / slug
        post_dir.mkdir(parents=True, exist_ok=True)
        filename = post_dir / "index.html"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"""<!DOCTYPE html>
<html lang="sl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=350, initial-scale=1, maximum-scale=2.0, user-scalable=yes">
  <meta name="description" content="{description}" />
  <meta name="keywords" content="gorske avanture, pohodništvo, gore, fotografije, narava, prosti čas, {BLOG_TITLE}, {BLOG_AUTHOR}" />
  <meta name="author" content="{BLOG_AUTHOR}" />

  <title>{title} | {BLOG_TITLE}</title>
  <link rel="canonical" href="{og_url}">
  <link rel="alternate" href="{og_url}" hreflang="sl" />
  <link rel="alternate" href="{BASE_SITE_URL}" hreflang="x-default" />

  <meta property="og:title" content="{title}">
  <meta property="og:type" content="article">
  <meta property="og:image" content="{og_image}">
  <meta property="og:url" content="{og_url}">
  <meta property="og:description" content="{description}">

  <script>
    var postTitle = {title!r};
    var postId = {post_id!r};
    var author = {author!r};
  </script>

  {structured_data}

  <!-- Favicon -->
  <link rel="icon" href="https://matejlezeljetam.blogspot.com/favicon.ico" type="image/x-icon">

  <!-- Fonts & CSS -->
  <link href="https://fonts.googleapis.com/css2?family=Rubik+Doodle+Shadow&display=swap" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@300;700&family=Open+Sans&display=swap" rel="stylesheet">
  <link href='https://metodlangus.github.io/plugins/leaflet/1.7.1/leaflet.min.css' rel='stylesheet'>
  <link href='https://metodlangus.github.io/plugins/@raruto/leaflet-elevation/dist/leaflet-elevation.min.css' rel='stylesheet'>
  <link href='https://metodlangus.github.io/plugins/leaflet-fullscreen/v1.0.1/leaflet.fullscreen.css' rel='stylesheet'>
  <link href='https://metodlangus.github.io/scripts/leaflet-download-gpx-button.css' rel='stylesheet'>
  <link href='https://metodlangus.github.io/plugins/lightbox2/2.11.1/css/lightbox.min.css' rel='stylesheet'>
  <link href='https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css' rel='stylesheet'>
  <link href='https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css' rel='stylesheet'>
  <link href='https://cdn.jsdelivr.net/npm/leaflet-control-geocoder@3.1.0/dist/Control.Geocoder.min.css' rel='stylesheet'>
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/Main.css">
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/MyMapScript.css">
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/MySlideshowScript.css">
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/MyPostContainerScript.css">
</head>

<body>
  <div class="page-wrapper">
    <!-- Top Header -->
    <header class="top-header">
      {header_html}
    </header>

    <!-- Main Layout -->
    <div class="main-layout">
      {sidebar_html}
      <div class="content-wrapper">
        {searchbox_html}
        <h2>{title}</h2>
        {metadata_html}
        {content_html}
        {labels_html}
        {nav_html}
        {comments_html}
      </div>
    </div>
  </div>

  <!-- Footer -->
  {back_to_top_html}
  {footer_html}

  <script src='https://metodlangus.github.io/plugins/leaflet/1.7.1/leaflet.min.js'></script>
  <script src='https://metodlangus.github.io/plugins/togeojson/0.16.0/togeojson.min.js'></script>
  <script src='https://metodlangus.github.io/plugins/leaflet-gpx/1.6.0/gpx.min.js'></script>
  <script src='https://metodlangus.github.io/plugins/@raruto/leaflet-elevation/dist/leaflet-elevation.min.js'></script>
  <script src='https://metodlangus.github.io/plugins/leaflet-fullscreen/v1.0.1/Leaflet.fullscreen.min.js'></script>
  <script src='https://metodlangus.github.io/plugins/leaflet-polylinedecorator/1.1.0/leaflet.polylineDecorator.min.js'></script>
  <script src='https://metodlangus.github.io/scripts/leaflet-download-gpx-button.js'></script>
  <script src='https://metodlangus.github.io/plugins/lightbox2/2.11.1/js/lightbox-plus-jquery.min.js'></script>
  <script src='https://metodlangus.github.io/scripts/full_img_size_button.js'></script>
  <script src='https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js'></script>
  <script src='https://cdn.jsdelivr.net/npm/leaflet-control-geocoder@3.1.0/dist/Control.Geocoder.min.js'></script>
  <script src="{BASE_SITE_URL}/assets/SiteConfig.js" defer></script>
  <script src="https://metodlangus.github.io/assets/Main.js" defer></script>
  <script src="https://matejlangus.github.io/map/assets/MyMapScript.js" defer></script>
  <script src="https://metodlangus.github.io/assets/MyFiltersScriptModule.js" defer></script>
  <script src="https://metodlangus.github.io/assets/MySlideshowScriptModule.js" defer></script>
</body>
</html>""")

        print(f"Saved: {filename}")

    return label_posts_raw


def generate_label_pages(entries, label_posts_raw):
    labels_dir = OUTPUT_DIR / "search/labels"
    labels_dir.mkdir(parents=True, exist_ok=True)

    sidebar_html = generate_sidebar_html(picture_settings=False, map_settings=False, current_page="labels")
    header_html = generate_header_html()
    searchbox_html = generate_searchbox_html()
    footer_html = generate_footer_html()
    back_to_top_html = generate_back_to_top_html()

    # Build lookup dictionary
    entry_lookup = {}
    for entry in entries:
        full_id = entry.get("id", {}).get("$t", "")
        match = re.search(r'post-(\d+)$', full_id)
        post_id = match.group(1) if match else ""
        if post_id:
            entry_lookup[post_id] = entry

    for label, posts in label_posts_raw.items():
        label_slug = slugify(remove_first_prefix(label))
        label_clean = re.sub(r"^(?:\d+\.\s*)+", "", label)

        # Create folder for each label page
        label_dir = labels_dir / label_slug
        label_dir.mkdir(parents=True, exist_ok=True)
        filename = label_dir / "index.html"

        # Sort posts by date descending
        posts_sorted = sorted(posts, key=lambda x: x['date'], reverse=True)

        post_scripts_html = ""
        for i, post in enumerate(posts_sorted):
            post_id = str(post.get('postId', '')).strip()
            if not post_id:
                print(f"Warning: Post at index {i} missing 'postId'")
                continue

            entry = entry_lookup.get(post_id)
            if not entry:
                print(f"Warning: Entry with postId {post_id} not found in entries")
                continue

            post_scripts_html += render_post_html(entry, i, entries_per_page, slugify, post_id)

        # --- Schema.org structured data (JSON-LD)
        schema_jsonld = f"""
        <script type="application/ld+json">
        {{
          "@context": "https://schema.org",
          "@type": "WebPage",
          "name": "Prikaz objav z oznako: {label_clean}",
          "url": "{BASE_SITE_URL}/search/labels/{label_slug}/",
          "description": "Prikaz objav z oznako: {label_clean} - gorske avanture in nepozabni trenutki.",
          "inLanguage": "sl",
          "isPartOf": {{
            "@type": "WebSite",
            "name": "{BLOG_TITLE}",
            "url": "{BASE_SITE_URL}/"
          }},
          "publisher": {{
            "@type": "Person",
            "name": "{BLOG_AUTHOR}",
            "url": "{BASE_SITE_URL}/"
          }}
        }}
        </script>
        """

        html_content = f"""<!DOCTYPE html>
<html lang="sl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=350, initial-scale=1, maximum-scale=2.0, user-scalable=yes">
  <meta name="description" content="Prikaz objav z oznako: {label_clean} - gorske avanture in nepozabni trenutki." />
  <meta name="keywords" content="gorske avanture, pohodništvo, gore, fotografije, narava, prosti čas, {BLOG_TITLE}, {BLOG_AUTHOR}" />
  <meta name="author" content="{BLOG_AUTHOR}" />

  <meta property="og:title" content="Prikaz objav z oznako: {label_clean}" />
  <meta property="og:description" content="Prikaz objav z oznako: {label_clean} - gorske avanture in nepozabni trenutki." />
  <meta property="og:image" content="{DEFAULT_OG_IMAGE}" />
  <meta property="og:image:alt" content="Prikaz objav z oznako: {label_clean}" />
  <meta property="og:url" content="{BASE_SITE_URL}/search/labels/{label_slug}/" />
  <meta property="og:type" content="website" />

  <title>Prikaz objav z oznako: {label_clean} | {BLOG_TITLE}</title>

  <!-- Canonical & hreflang -->
  <link rel="canonical" href="{BASE_SITE_URL}/search/labels/{label_slug}/" />
  <link rel="alternate" href="{BASE_SITE_URL}/search/labels/{label_slug}/" hreflang="sl" />
  <link rel="alternate" href="{BASE_SITE_URL}" hreflang="x-default" />

  {schema_jsonld}

  <!-- Favicon -->
  <link rel="icon" href="https://matejlezeljetam.blogspot.com/favicon.ico" type="image/x-icon">

  <!-- Fonts & CSS -->
  <link href="https://fonts.googleapis.com/css2?family=Rubik+Doodle+Shadow&display=swap" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@300;700&family=Open+Sans&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/Main.css">
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/MyPostContainerScript.css">
</head>

<body>
  <div class="page-wrapper">
    <!-- Top Header -->
    <header class="top-header">
      {header_html}
    </header>

    <!-- Main Layout -->
    <div class="main-layout">
      {sidebar_html}
      <div class="content-wrapper">
        {searchbox_html}
        <h1>Prikaz objav z oznako: {label_clean}</h1>
        <div class="blog-posts hfeed container">
          {post_scripts_html}
        </div>
        <div id="blog-pager" class="blog-pager"></div>
      </div>
    </div>
  </div>

  <!-- Footer -->
  {back_to_top_html}
  {footer_html}

  <script src="{BASE_SITE_URL}/assets/SiteConfig.js" defer></script>
  <script src="https://metodlangus.github.io/assets/Main.js" defer></script>
</body>
</html>"""

        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"Generated label page: {filename}")


def generate_archive_pages(entries):
    """
    Generates yearly and monthly archive pages with posts sorted by date.
    """
    from collections import defaultdict

    # Slovene month names
    month_names_sl = {
        "01": "januar",
        "02": "februar",
        "03": "marec",
        "04": "april",
        "05": "maj",
        "06": "junij",
        "07": "julij",
        "08": "avgust",
        "09": "september",
        "10": "oktober",
        "11": "november",
        "12": "december"
    }

    # Prepare HTML snippets
    sidebar_html = generate_sidebar_html(picture_settings=False, map_settings=False, current_page="posts")
    header_html = generate_header_html()
    searchbox_html = generate_searchbox_html()
    footer_html = generate_footer_html()
    back_to_top_html = generate_back_to_top_html()

    local_tz = ZoneInfo("Europe/Ljubljana")
    # Organize posts by year and month
    archive_dict = defaultdict(lambda: defaultdict(list))

    slugs = generate_unique_slugs(entries, local_tz)

    for index, entry in enumerate(entries):
        title = entry.get("title", {}).get("$t", f"untitled-{index}")
        full_id = entry.get("id", {}).get("$t", "")
        post_id = full_id.split("post-")[-1] if "post-" in full_id else ""
        formatted_date, year, month = parse_entry_date(entry, index)
        month_str = f"{int(month):02}"  # Ensure two digits
        archive_dict[year][month_str].append({
            "entry": entry,
            "slug": slugs[index],
            "date": formatted_date,
            "post_id": post_id
        })

    # Generate yearly and monthly pages
    for year, months in archive_dict.items():
        # --- Year page ---
        year_dir = OUTPUT_DIR / "posts" / year
        year_dir.mkdir(parents=True, exist_ok=True)
        year_filename = year_dir / "index.html"

        # Flatten all posts for the year
        year_posts = []
        for month in sorted(months.keys(), reverse=True):
            for post_info in sorted(months[month], key=lambda x: x['date'], reverse=True):
                year_posts.append(post_info)

        year_posts_html = ""
        for i, post_info in enumerate(year_posts):
            year_posts_html += render_post_html(post_info["entry"], i, entries_per_page, slugify, post_info["post_id"])

        # --- Schema.org structured data (JSON-LD)
        schema_jsonld = f"""
        <script type="application/ld+json">
        {{
          "@context": "https://schema.org",
          "@type": "WebPage",
          "name": "Prikaz objav, dodanih na: {year}",
          "url": "{BASE_SITE_URL}/posts/{year}/",
          "description": "Prikaz objav, dodanih na: {year} - gorske avanture in nepozabni trenutki.",
          "inLanguage": "sl",
          "isPartOf": {{
            "@type": "WebSite",
            "name": "{BLOG_TITLE}",
            "url": "{BASE_SITE_URL}/"
          }},
          "publisher": {{
            "@type": "Person",
            "name": "{BLOG_AUTHOR}",
            "url": "{BASE_SITE_URL}/"
          }}
        }}
        </script>
        """

        html_year = f"""<!DOCTYPE html>
<html lang="sl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=350, initial-scale=1, maximum-scale=2.0, user-scalable=yes">
  <meta name="description" content="Prikaz objav, dodanih na: {year} - gorske avanture in nepozabni trenutki." />
  <meta name="keywords" content="gorske avanture, pohodništvo, gore, fotografije, narava, prosti čas, {BLOG_TITLE}, {BLOG_AUTHOR}" />
  <meta name="author" content="{BLOG_AUTHOR}" />

  <meta property="og:title" content="Prikaz objav, dodanih na: {year}" />
  <meta property="og:description" content="Prikaz objav, dodanih na: {year} - gorske avanture in nepozabni trenutki." />
  <meta property="og:image" content="{DEFAULT_OG_IMAGE}" />
  <meta property="og:image:alt" content="Prikaz objav, dodanih na: {year}" />
  <meta property="og:url" content="{BASE_SITE_URL}/posts/{year}/" />
  <meta property="og:type" content="website" />

  <title>Prikaz objav, dodanih na: {year} | {BLOG_TITLE}</title>

  <!-- Canonical & hreflang -->
  <link rel="canonical" href="{BASE_SITE_URL}/posts/{year}/" />
  <link rel="alternate" href="{BASE_SITE_URL}/posts/{year}/" hreflang="sl" />
  <link rel="alternate" href="{BASE_SITE_URL}" hreflang="x-default" />

  {schema_jsonld}

  <!-- Favicon -->
  <link rel="icon" href="{BASE_SITE_URL}/photos/favicon.ico" type="image/x-icon">

  <!-- Fonts & CSS -->
  <link href="https://fonts.googleapis.com/css2?family=Rubik+Doodle+Shadow&display=swap" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@300;700&family=Open+Sans&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/Main.css">
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/MyPostContainerScript.css">
</head>
<body>
  <div class="page-wrapper">
    <!-- Top Header -->
    <header class="top-header">
      {header_html}
    </header>

    <!-- Main Layout -->
    <div class="main-layout">
      {sidebar_html}
      <div class="content-wrapper">
        {searchbox_html}
        <h1>Prikaz objav, dodanih na: {year}</h1>
        <div class="blog-posts hfeed container">
          {year_posts_html}
        </div>
        <div id="blog-pager" class="blog-pager"></div>
      </div>
    </div>
  </div>

  <!-- Footer -->
  {back_to_top_html}
  {footer_html}

  <script src="{BASE_SITE_URL}/assets/SiteConfig.js" defer></script>
  <script src="https://metodlangus.github.io/assets/Main.js" defer></script>
</body>
</html>"""

        with open(year_filename, "w", encoding="utf-8") as f:
            f.write(html_year)
        print(f"Generated year archive page: {year_filename}")

        # --- Month pages ---
        for month, posts in months.items():
            month_dir = year_dir / month
            month_dir.mkdir(parents=True, exist_ok=True)
            month_filename = month_dir / "index.html"

            month_name_sl = month_names_sl.get(month, month)  # Slovene month name

            month_posts_sorted = sorted(posts, key=lambda x: x['date'], reverse=True)
            month_posts_html = ""
            for i, post_info in enumerate(month_posts_sorted):
                month_posts_html += render_post_html(post_info["entry"], i, entries_per_page, slugify, post_info["post_id"])

            # --- Schema.org structured data (JSON-LD)
            schema_jsonld = f"""
            <script type="application/ld+json">
            {{
              "@context": "https://schema.org",
              "@type": "WebPage",
              "name": "Prikaz objav, dodanih na: {month_name_sl}, {year}",
              "url": "{BASE_SITE_URL}/posts/{year}/{month}/",
              "description": "Prikaz objav, dodanih na: {month_name_sl}, {year} - gorske avanture in nepozabni trenutki.",
              "inLanguage": "sl",
              "isPartOf": {{
                "@type": "WebSite",
                "name": "{BLOG_TITLE}",
                "url": "{BASE_SITE_URL}/"
              }},
              "publisher": {{
                "@type": "Person",
                "name": "{BLOG_AUTHOR}",
                "url": "{BASE_SITE_URL}/"
              }}
            }}
            </script>
            """

            html_month = f"""<!DOCTYPE html>
<html lang="sl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=350, initial-scale=1, maximum-scale=2.0, user-scalable=yes">
  <meta name="description" content="Prikaz objav, dodanih na: {month_name_sl}, {year} - gorske avanture in nepozabni trenutki." />
  <meta name="keywords" content="gorske avanture, pohodništvo, gore, fotografije, narava, prosti čas, {BLOG_TITLE}, {BLOG_AUTHOR}" />
  <meta name="author" content="{BLOG_AUTHOR}" />

  <meta property="og:title" content="Prikaz objav, dodanih na: {month_name_sl}, {year}" />
  <meta property="og:description" content="Prikaz objav, dodanih na: {month_name_sl}, {year} - gorske avanture in nepozabni trenutki." />
  <meta property="og:image" content="{DEFAULT_OG_IMAGE}" />
  <meta property="og:image:alt" content="Prikaz objav, dodanih na: {month_name_sl}, {year}" />
  <meta property="og:url" content="{BASE_SITE_URL}/posts/{year}/{month}/" />
  <meta property="og:type" content="website" />

  <title>Prikaz objav, dodanih na: {month_name_sl}, {year} | {BLOG_TITLE}</title>

  <!-- Canonical & hreflang -->
  <link rel="canonical" href="{BASE_SITE_URL}/posts/{year}/{month}/" />
  <link rel="alternate" href="{BASE_SITE_URL}/posts/{year}/{month}/" hreflang="sl" />
  <link rel="alternate" href="{BASE_SITE_URL}" hreflang="x-default" />

  {schema_jsonld}

  <!-- Favicon -->
  <link rel="icon" href="{BASE_SITE_URL}/photos/favicon.ico" type="image/x-icon">

  <!-- Fonts & CSS -->
  <link href="https://fonts.googleapis.com/css2?family=Rubik+Doodle+Shadow&display=swap" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@300;700&family=Open+Sans&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/Main.css">
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/MyPostContainerScript.css">
</head>
<body>
  <div class="page-wrapper">
    <!-- Top Header -->
    <header class="top-header">
      {header_html}
    </header>

    <!-- Main Layout -->
    <div class="main-layout">
      {sidebar_html}
      <div class="content-wrapper">
        {searchbox_html}
        <h1>Prikaz objav, dodanih na: {month_name_sl}, {year}</h1>
        <div class="blog-posts hfeed container">
          {month_posts_html}
        </div>
        <div id="blog-pager" class="blog-pager"></div>
      </div>
    </div>
  </div>

  <!-- Footer -->
  {back_to_top_html}
  {footer_html}

  <script src="{BASE_SITE_URL}/assets/SiteConfig.js" defer></script>
  <script src="https://metodlangus.github.io/assets/Main.js" defer></script>
</body>
</html>"""

            with open(month_filename, "w", encoding="utf-8") as f:
                f.write(html_month)
            print(f"Generated month archive page: {month_filename}")


def generate_predvajalnik_page(current_page):
    output_dir = OUTPUT_DIR / "predvajalnik-fotografij"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "index.html"

    sidebar_html = generate_sidebar_html(picture_settings=True, map_settings=False, current_page=current_page)
    header_html = generate_header_html()
    searchbox_html = generate_searchbox_html()
    footer_html = generate_footer_html()
    back_to_top_html = generate_back_to_top_html()

    # --- Schema.org structured data (JSON-LD)
    schema_jsonld = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "WebPage",
      "name": "Predvajalnik naključnih fotografij",
      "url": "{BASE_SITE_URL}/predvajalnik-fotografij/",
      "description": "Predvajalnik naključnih fotografij gorskih avantur in nepozabnih trenutkov.",
      "inLanguage": "sl",
      "isPartOf": {
        "@type": "WebSite",
        "name": "{BLOG_TITLE}",
        "url": "{BASE_SITE_URL}/"
      },
      "publisher": {
        "@type": "Person",
        "name": "{BLOG_AUTHOR}",
        "url": "{BASE_SITE_URL}/"
      },
      "potentialAction": {
        "@type": "SearchAction",
        "target": "{BASE_SITE_URL}/search?q={search_term_string}",
        "query-input": "required name=search_term_string"
      }
    }
    </script>
    """

    html_content = f"""<!DOCTYPE html>
<html lang="sl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=350, initial-scale=1, maximum-scale=2.0, user-scalable=yes">
  <meta name="description" content="Predvajalnik naključnih fotografij gorskih avantur in nepozabnih trenutkov." />
  <meta name="keywords" content="gorske avanture, pohodništvo, gore, fotografije, narava, prosti čas, {BLOG_TITLE}, {BLOG_AUTHOR}" />
  <meta name="author" content="{BLOG_AUTHOR}" />

  <meta property="og:title" content="Predvajalnik naključnih fotografij" />
  <meta property="og:description" content="Predvajalnik naključnih fotografij gorskih avantur in nepozabnih trenutkov." />
  <meta property="og:image" content="{DEFAULT_OG_IMAGE}" />
  <meta property="og:image:alt" content="Gorski razgledi in narava v slikah" />
  <meta property="og:url" content="{BASE_SITE_URL}/predvajalnik-fotografij/" />
  <meta property="og:type" content="website" />

  <title>Predvajalnik naključnih fotografij | {BLOG_TITLE}</title>

  <!-- Canonical & hreflang -->
  <link rel="canonical" href="{BASE_SITE_URL}/predvajalnik-fotografij/" />
  <link rel="alternate" href="{BASE_SITE_URL}/predvajalnik-fotografij/" hreflang="sl" />
  <link rel="alternate" href="{BASE_SITE_URL}/" hreflang="x-default" />

  {schema_jsonld}

  <script>
    var postTitle = 'Predvajalnik naključnih fotografij';
    var author = '{BLOG_AUTHOR}';
  </script>

  <!-- Favicon -->
  <link rel="icon" href="https://matejlezeljetam.blogspot.com/favicon.ico" type="image/x-icon">

  <!-- Fonts & CSS -->
  <link href="https://fonts.googleapis.com/css2?family=Rubik+Doodle+Shadow&display=swap" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@300;700&family=Open+Sans&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/Main.css">
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/MySlideshowScript.css">
</head>

<body>
  <div class="page-wrapper">
    <!-- Top Header -->
    <header class="top-header">
      {header_html}
    </header>

    <!-- Main Layout -->
    <div class="main-layout">
      {sidebar_html}
      <div class="content-wrapper">
        {searchbox_html}
        <h1>Predvajalnik naključnih fotografij</h1>
        <script> 
          var slideshowTitle0 = 'All pictures';
          var CoverPhoto0 = '';
        </script>
      </div>
    </div>
  </div>

  <!-- Footer -->
  {back_to_top_html}
  {footer_html}

  <script src="{BASE_SITE_URL}/assets/SiteConfig.js" defer></script>
  <script src="https://metodlangus.github.io/assets/Main.js" defer></script>
  <script src="https://metodlangus.github.io/assets/MySlideshowScriptModule.js" defer></script>
  <script src="https://metodlangus.github.io/assets/MyFiltersScriptModule.js" defer></script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Generated random slideshow page: {output_path}")


def generate_gallery_page(current_page):
    output_dir = OUTPUT_DIR / "galerija-fotografij"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "index.html"

    sidebar_html = generate_sidebar_html(picture_settings=True, map_settings=False, current_page=current_page)
    header_html = generate_header_html()
    searchbox_html = generate_searchbox_html()
    footer_html = generate_footer_html()
    back_to_top_html = generate_back_to_top_html()

    # --- Schema.org structured data (JSON-LD)
    schema_jsonld = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "WebPage",
      "name": "Galerija fotografij",
      "url": "{BASE_SITE_URL}/galerija-fotografij/",
      "description": "Galerija gorskih avantur in nepozabnih trenutkov.",
      "inLanguage": "sl",
      "isPartOf": {
        "@type": "WebSite",
        "name": "{BLOG_TITLE}",
        "url": "{BASE_SITE_URL}/"
      },
      "publisher": {
        "@type": "Person",
        "name": "{BLOG_AUTHOR}",
        "url": "{BASE_SITE_URL}/"
      },
      "potentialAction": {
        "@type": "SearchAction",
        "target": "{BASE_SITE_URL}/search?q={search_term_string}",
        "query-input": "required name=search_term_string"
      }
    }
    </script>
    """

    html_content = f"""<!DOCTYPE html>
<html lang="sl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=350, initial-scale=1, maximum-scale=2.0, user-scalable=yes">
  <meta name="description" content="Galerija gorskih avantur in nepozabnih trenutkov." />
  <meta name="keywords" content="gorske avanture, pohodništvo, gore, fotografije, narava, prosti čas, {BLOG_TITLE}, {BLOG_AUTHOR}" />
  <meta name="author" content="{BLOG_AUTHOR}" />

  <meta property="og:title" content="Galerija fotografij" />
  <meta property="og:description" content="Galerija gorskih avantur in nepozabnih trenutkov." />
  <meta property="og:image" content="{DEFAULT_OG_IMAGE}" />
  <meta property="og:image:alt" content="Galerija gorskih avantur" />
  <meta property="og:url" content="{BASE_SITE_URL}/galerija-fotografij/" />
  <meta property="og:type" content="website" />

  <title>Galerija spominov | {BLOG_TITLE}</title>

  <!-- Canonical & hreflang -->
  <link rel="canonical" href="{BASE_SITE_URL}/galerija-fotografij/" />
  <link rel="alternate" href="{BASE_SITE_URL}/galerija-fotografij/" hreflang="sl" />
  <link rel="alternate" href="{BASE_SITE_URL}/" hreflang="x-default" />

  {schema_jsonld}

  <script>
    var postTitle = 'Galerija fotografij';
    var author = '{BLOG_AUTHOR}';
  </script>

  <!-- Favicon -->
  <link rel="icon" href="https://matejlezeljetam.blogspot.com/favicon.ico" type="image/x-icon">

  <!-- Fonts & CSS -->
  <link href="https://fonts.googleapis.com/css2?family=Rubik+Doodle+Shadow&display=swap" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@300;700&family=Open+Sans&display=swap" rel="stylesheet">
  <link href='https://metodlangus.github.io/plugins/lightbox2/2.11.1/css/lightbox.min.css' rel='stylesheet'>
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/Main.css">
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/MyGalleryScript.css">
</head>

<body>
  <div class="page-wrapper">
    <!-- Top Header -->
    <header class="top-header">
      {header_html}
    </header>

    <!-- Main Layout -->
    <div class="main-layout">
      {sidebar_html}
      <div class="content-wrapper">
        {searchbox_html}
        <h1>Galerija spominov</h1>
        <div id='loadingMessage'>Nalaganje ...</div>
        <div id="gallery" class="my-gallery-wrapper">
          <div class="gallery-container" id="galleryContainer">
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Footer -->
  {back_to_top_html}
  {footer_html}

  <script src='https://metodlangus.github.io/plugins/lightbox2/2.11.1/js/lightbox-plus-jquery.min.js'></script>
  <script src='https://metodlangus.github.io/scripts/full_img_size_button.js'></script>
  <script src="{BASE_SITE_URL}/assets/SiteConfig.js" defer></script>
  <script src="https://metodlangus.github.io/assets/Main.js" defer></script>
  <script src="https://metodlangus.github.io/assets/MyFiltersScriptModule.js" defer></script>
  <script src="https://metodlangus.github.io/assets/MyGalleryScriptModule.js" defer></script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Generated gallery page: {output_path}")


def generate_peak_list_page():
    output_dir = OUTPUT_DIR / "seznam-aktivnosti"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "index.html"

    sidebar_html = generate_sidebar_html(picture_settings=False, map_settings=False, current_page="peak-list")
    header_html = generate_header_html()
    searchbox_html = generate_searchbox_html()
    footer_html = generate_footer_html()
    back_to_top_html = generate_back_to_top_html()

    # --- Schema.org structured data (JSON-LD)
    schema_jsonld = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "WebPage",
      "name": "Seznam aktivnosti",
      "url": "{BASE_SITE_URL}/seznam-aktivnosti/",
      "description": "Seznam obiskanih vrhov na gorskih avanturah.",
      "inLanguage": "sl",
      "isPartOf": {
        "@type": "WebSite",
        "name": "{BLOG_TITLE}",
        "url": "{BASE_SITE_URL}/"
      },
      "publisher": {
        "@type": "Person",
        "name": "{BLOG_AUTHOR}",
        "url": "{BASE_SITE_URL}/"
      },
      "potentialAction": {
        "@type": "SearchAction",
        "target": "{BASE_SITE_URL}/search?q={search_term_string}",
        "query-input": "required name=search_term_string"
      }
    }
    </script>
    """

    html_content = f"""<!DOCTYPE html>
<html lang="sl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=350, initial-scale=1, maximum-scale=2.0, user-scalable=yes">
  <meta name="description" content="Seznam aktivnosti." />
  <meta name="keywords" content="gorske avanture, pohodništvo, gore, fotografije, narava, prosti čas, {BLOG_TITLE}, {BLOG_AUTHOR}" />
  <meta name="author" content="{BLOG_AUTHOR}" />

  <meta property="og:title" content="Seznam aktivnosti" />
  <meta property="og:description" content="Seznam aktivnosti." />
  <meta property="og:image" content="{DEFAULT_OG_IMAGE}" />
  <meta property="og:image:alt" content="Seznam aktivnosti" />
  <meta property="og:url" content="{BASE_SITE_URL}/seznam-aktivnosti/" />
  <meta property="og:type" content="website" />

  <title>Seznam aktivnosti | {BLOG_TITLE}</title>

  <!-- Canonical & hreflang -->
  <link rel="canonical" href="{BASE_SITE_URL}/seznam-aktivnosti/" />
  <link rel="alternate" href="{BASE_SITE_URL}/seznam-aktivnosti/" hreflang="sl" />
  <link rel="alternate" href="{BASE_SITE_URL}/" hreflang="x-default" />

  {schema_jsonld}

  <script>
    var postTitle = 'Seznam aktivnosti';
    var author = '{BLOG_AUTHOR}';
  </script>

  <!-- Favicon -->
  <link rel="icon" href="https://matejlezeljetam.blogspot.com/favicon.ico" type="image/x-icon">

  <!-- Fonts & CSS -->
  <link href="https://fonts.googleapis.com/css2?family=Rubik+Doodle+Shadow&display=swap" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@300;700&family=Open+Sans&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/Main.css">
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/MyPeakListScript.css">
</head>

<body>
  <div class="page-wrapper">
    <!-- Top Header -->
    <header class="top-header">
      {header_html}
    </header>

    <!-- Main Layout -->
    <div class="main-layout">
      {sidebar_html}
      <div class="content-wrapper">
        {searchbox_html}
        <h1>Seznam aktivnosti</h1>
        <div id='loadingMessage'>Nalaganje ...</div>
        <div id='mountainContainer'></div>
      </div>
    </div>
  </div>

  <!-- Footer -->
  {back_to_top_html}
  {footer_html}

  <script src="{BASE_SITE_URL}/assets/SiteConfig.js" defer></script>
  <script src="https://metodlangus.github.io/assets/Main.js" defer></script>
  <script src="https://metodlangus.github.io/assets/MyPeakListScriptModule.js" defer></script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Generated peak list page: {output_path}")


def generate_home_si_page(homepage_html):
    output_path = OUTPUT_DIR / "index.html"

    sidebar_html = generate_sidebar_html(picture_settings=False, map_settings=False, current_page="home")
    header_html = generate_header_html()
    searchbox_html = generate_searchbox_html()
    footer_html = generate_footer_html()
    back_to_top_html = generate_back_to_top_html()

    # --- Schema.org structured data (JSON-LD)
    schema_jsonld = f"""
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "WebSite",
      "name": "{BLOG_TITLE}",
      "url": "{BASE_SITE_URL}/",
      "description": "Gorske avanture in nepozabni trenutki: Lepote gorskega sveta in predvajalniki slik, ki vas popeljejo skozi dogodivščine.",
      "publisher": {{
        "@type": "Person",
        "name": "{BLOG_AUTHOR}",
        "url": "{BASE_SITE_URL}/"
      }},
      "potentialAction": {{
        "@type": "SearchAction",
        "target": "{BASE_SITE_URL}/search?q={{search_term_string}}",
        "query-input": "required name=search_term_string"
      }}
    }}
    </script>
    """

    html_content = f"""<!DOCTYPE html>
<html lang="sl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=350, initial-scale=1, maximum-scale=2.0, user-scalable=yes">
    <meta name="description" content="Gorske avanture in nepozabni trenutki: Lepote gorskega sveta in predvajalniki slik, ki vas popeljejo skozi dogodivščine." />
    <meta name="keywords" content="gorske avanture, pustolovščine, pohodništvo, gore, fotografije, narava, prosti čas, {BLOG_TITLE}, {BLOG_AUTHOR}" />
    <meta name="author" content="{BLOG_AUTHOR}" />

    <title>{BLOG_TITLE} | Gorske pustolovščine skozi slike | {BLOG_AUTHOR}</title>
    <link rel="canonical" href="{BASE_SITE_URL}/" />

    {schema_jsonld}

    <meta property="og:title" content="{BLOG_TITLE} | Gorske pustolovščine skozi slike | {BLOG_AUTHOR}" />
    <meta property="og:description" content="Gorske avanture in nepozabni trenutki: Lepote gorskega sveta in predvajalniki slik, ki vas popeljejo skozi dogodivščine." />
    <meta property="og:image" content="{DEFAULT_OG_IMAGE}" />
    <meta property="og:image:alt" content="Gorski razgledi in narava" />
    <meta property="og:url" content="{BASE_SITE_URL}/" />
    <meta property="og:type" content="website" />

    <link rel="alternate" href="{BASE_SITE_URL}/" hreflang="sl" />
    <link rel="alternate" href="{BASE_SITE_URL}/en/" hreflang="en" />
    <link rel="alternate" href="{BASE_SITE_URL}/" hreflang="x-default" />

    <!-- Favicon -->
    <link rel="icon" href="https://matejlezeljetam.blogspot.com/favicon.ico" type="image/x-icon">

    <!-- Fonts & CSS -->
  <link href="https://fonts.googleapis.com/css2?family=Rubik+Doodle+Shadow&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@300;700&family=Open+Sans&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://metodlangus.github.io/assets/Main.css">
    <link rel="stylesheet" href="https://metodlangus.github.io/assets/MyRandomPhoto.css">
    <link rel="stylesheet" href="https://metodlangus.github.io/assets/MyPostContainerScript.css">
</head>

<body>
  <div class="page-wrapper">
    <!-- Top Header -->
    <header class="top-header home">
      {header_html}
    </header>

    <!-- Main Layout -->
    <div class="main-layout">
      {sidebar_html}
      <div class="content-wrapper">
        {searchbox_html}
        <div class="blog-posts hfeed container home">
          {homepage_html}
        </div>
        <div id="blog-pager" class="blog-pager"></div>
      </div>
    </div>
  </div>

  <!-- Footer -->
  {back_to_top_html}
  {footer_html}

  <script src="{BASE_SITE_URL}/assets/SiteConfig.js" defer></script>
  <script src="https://metodlangus.github.io/assets/Main.js" defer></script>
  <script src="https://metodlangus.github.io/assets/MyRandomPhotoModule.js" defer></script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Generated home SI page: {output_path}")


def generate_useful_links_page():
    output_dir = OUTPUT_DIR / "uporabne-povezave"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "index.html"

    # Sidebar, header, footer, etc.
    sidebar_html = generate_sidebar_html(picture_settings=False, map_settings=False, current_page="useful-links")
    header_html = generate_header_html()
    searchbox_html = generate_searchbox_html()
    footer_html = generate_footer_html()
    back_to_top_html = generate_back_to_top_html()

    # --- Schema.org structured data (JSON-LD)
    schema_jsonld = f"""
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "WebPage",
      "name": "Uporabne povezave",
      "url": "{BASE_SITE_URL}/uporabne-povezave/",
      "description": "Seznam uporabnih povezav do drugih blogov in vsebin.",
      "inLanguage": "sl",
      "isPartOf": {{
        "@type": "WebSite",
        "name": "{BLOG_TITLE}",
        "url": "{BASE_SITE_URL}/"
      }},
      "publisher": {{
        "@type": "Person",
        "name": "{BLOG_AUTHOR}",
        "url": "{BASE_SITE_URL}/"
      }},
      "potentialAction": {{
        "@type": "SearchAction",
        "target": "{BASE_SITE_URL}/search?q={{search_term_string}}",
        "query-input": "required name=search_term_string"
      }}
    }}
    </script>
    """

    # Generate HTML for the links
    links_html = """<div id="useful-links-container"></div>"""

    # Main HTML content
    html_content = f"""<!DOCTYPE html>
<html lang="sl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=350, initial-scale=1, maximum-scale=2.0, user-scalable=yes">
  <meta name="description" content="Seznam uporabnih povezav do drugih blogov in vsebin." />
  <meta name="keywords" content="uporabne povezave, blog, pohodništvo, gore, narava, {BLOG_TITLE}, {BLOG_AUTHOR}" />
  <meta name="author" content="{BLOG_AUTHOR}" />

  <meta property="og:title" content="Uporabne povezave" />
  <meta property="og:description" content="Seznam uporabnih povezav do drugih blogov in vsebin." />
  <meta property="og:image" content="{DEFAULT_OG_IMAGE}" />
  <meta property="og:image:alt" content="Uporabne povezave" />
  <meta property="og:url" content="{BASE_SITE_URL}/uporabne-povezave.html" />
  <meta property="og:type" content="website" />

  <title>Uporabne povezave | {BLOG_TITLE}</title>

  <!-- Canonical & hreflang -->
  <link rel="canonical" href="{BASE_SITE_URL}/uporabne-povezave.html" />
  <link rel="alternate" href="{BASE_SITE_URL}/uporabne-povezave.html" hreflang="sl" />
  <link rel="alternate" href="{BASE_SITE_URL}" hreflang="x-default" />

  {schema_jsonld}

  <script>
    var postTitle = 'Uporabne povezave';
    var author = '{BLOG_AUTHOR}';
  </script>

  <!-- Favicon -->
  <link rel="icon" href="https://matejlezeljetam.blogspot.com/favicon.ico" type="image/x-icon">

  <!-- Fonts & CSS -->
  <link href="https://fonts.googleapis.com/css2?family=Rubik+Doodle+Shadow&display=swap" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Merriweather:wght@300;700&family=Open+Sans&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://metodlangus.github.io/assets/Main.css">
</head>

<body>
  <div class="page-wrapper">
    <header class="top-header">{header_html}</header>
    <div class="main-layout">
      {sidebar_html}
      <div class="content-wrapper">
        {searchbox_html}
        <h1>Uporabne povezave</h1>
        <p>Zbirka povezav do drugih blogov in ostalih uporabnih spletnih vsebin:</p>
        {links_html}
      </div>
    </div>
  </div>

  {back_to_top_html}
  {footer_html}

  <script src="{BASE_SITE_URL}/assets/SiteConfig.js" defer></script>
  <script src="https://metodlangus.github.io/assets/Main.js" defer></script>
  <script src="{BASE_SITE_URL}/assets/MyUsefulLinksScript.js" defer></script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Generated useful links page: {output_path}")


def generate_404_page():
    output_path = OUTPUT_DIR / "404.html"

    html_content = f"""<!DOCTYPE html>
<html lang="sl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">

  <title>Napaka 404 – Stran ne obstaja | {BLOG_TITLE}</title>

  <meta name="description" content="Napaka 404 – Stran, ki jo iščete, ne obstaja. Morda je bila odstranjena ali premaknjena. Oglejte si vsebino na {BLOG_TITLE}.">
  <meta name="keywords" content="404, napaka 404, stran ne obstaja, pohodništvo, blog, {BLOG_TITLE}, {BLOG_AUTHOR}">
  <meta name="author" content="{BLOG_AUTHOR}">

  <!-- Canonical & hreflang -->
  <link rel="canonical" href="{BASE_SITE_URL}/404.html" />
  <link rel="alternate" href="{BASE_SITE_URL}/404.html" hreflang="sl" />
  <link rel="alternate" href="{BASE_SITE_URL}" hreflang="x-default" />

  <!-- OpenGraph -->
  <meta property="og:title" content="Napaka 404 – Stran ne obstaja">
  <meta property="og:description" content="Stran ne obstaja. Nadaljujte brskanje po blogu {BLOG_TITLE}.">
  <meta property="og:image" content="{DEFAULT_OG_IMAGE}">
  <meta property="og:image:alt" content="Napaka 404">
  <meta property="og:url" content="{BASE_SITE_URL}/404.html">
  <meta property="og:type" content="website">

  <!-- Structured Data -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "WebPage",
    "name": "Napaka 404 – Stran ne obstaja",
    "url": "{BASE_SITE_URL}/404.html",
    "description": "Stran ne obstaja. Nadaljujte brskanje po blogu {BLOG_TITLE}.",
    "inLanguage": "sl",
    "isPartOf": {{
      "@type": "WebSite",
      "name": "{BLOG_TITLE}",
      "url": "{BASE_SITE_URL}/"
    }},
    "publisher": {{
      "@type": "Person",
      "name": "{BLOG_AUTHOR}",
      "url": "{BASE_SITE_URL}/"
    }}
  }}
</script>

  <!-- Favicon -->
  <link rel="icon" href="https://matejlezeljetam.blogspot.com/favicon.ico" type="image/x-icon">

  <!-- CSS -->
  <link rel="stylesheet" href="{BASE_SITE_URL}/assets/My404PageScript.css">
</head>

<body>
  <h1>404</h1>
  <p>Ups! Stran, ki jo iščete, ne obstaja. Morda je bila premaknjena ali izbrisana.</p>
  <a href="{BASE_SITE_URL}/" class="home-btn">Domov</a>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Generated 404 page: {output_path}")


if __name__ == "__main__":
    entries = fetch_all_entries()
    label_posts_raw = fetch_and_save_all_posts(entries)  # This function should return { label: [ {postId, date, html}, ... ] }

    # 1. Build the archive HTML from entries
    generate_archive_pages(entries)
    archive_html = build_archive_sidebar_html(entries)
    # 2. Save it as assets/archive.js
    save_archive_as_js(archive_html, "assets/archive.js")

    # 1. Generate the labels HTML
    labels_sidebar_html = generate_labels_sidebar_html(feed_path=BASE_FEED_PATH)
    # 2. Save it as assets/navigation.js
    save_navigation_as_js(labels_sidebar_html, "assets/navigation.js")

    generate_label_pages(entries, label_posts_raw)
    generate_predvajalnik_page(current_page="slideshow_page")
    generate_gallery_page(current_page="gallery_page")
    generate_peak_list_page()
    generate_useful_links_page()

    homepage_html = generate_homepage_html(entries)
    generate_home_si_page(homepage_html)
    generate_404_page()

    generate_sitemap_from_folder(
        Path(LOCAL_REPO_PATH),
        exclude_dirs=["node_modules", "arhiv"],
        exclude_files=["Relive _ Settings.html"]
    )

    update_lastmod_tracking(
        Path(LOCAL_REPO_PATH),
        exclude_dirs=[],
        exclude_files=["Relive _ Settings.html"]
    )