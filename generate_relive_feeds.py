"""
/**
 * @file generate_relive_feeds.py
 * @brief Generates JSON feed and posts from Relive activity data, including CDN images and GPX links.
 *
 * Features:
 * - Skips private activities if configured.
 * - Processes media images and cover photo with separate CDN widths.
 * - Builds HTML content and JSON feed entries.
 * - Adds cover photo to feed in CDN format (width 600).
 * - Matches GPX files by timestamp or filename.
 *
 * @author Metod Langus
 * @date 2025-12-08
 */
"""

import os
import ast
import base64
import re
import json
from datetime import datetime
from pathlib import Path
from slugify import slugify

# ---------------- CONFIG ----------------
EXCLUDE_PRIVATE = True  # set to True to skip private activities

# CDN widths
CDN_SRC_WIDTH = 1000   # width for <img src>
CDN_HREF_WIDTH = 1600  # width for <a href>
CDN_FEED_COVER_WIDTH = 600  # width for feed cover image

# Paths
GITHUB_REPO_NAME = "matejlangus.github.io/map"
LOCAL_REPO_PATH = r"C:\Matej_blog\map"
source_file = r"C:\Matej_blog\map\relive_data.txt"

gpx_list_file = Path(LOCAL_REPO_PATH) / "gpx_files.txt"
GPX_BASE_URL = "https://matejlangus.github.io/map/gpx-files/"

data_root = Path("data")
data_root.mkdir(exist_ok=True)

posts_root = data_root / "posts"
feed_file = data_root / "all-posts.json"
posts_root.mkdir(exist_ok=True)

# Helper functions
def sanitize_name(name):
    if not name:
        return "activity"
    slug = slugify(name)
    return slug or "activity"

def iso_format(date_str):
    if not date_str:
        dt = datetime.now()
    else:
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                dt = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        else:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    ms = int(dt.microsecond / 1000)
    return dt.strftime(f"%Y-%m-%dT%H:%M:%S.{ms:03d}%z")

def relive_cdn(url: str, width: int) -> str:
    """
    Convert a Relive image URL into the relive CDN encoded form:
      https://img.relive.com/-/w:{width}/{base64(original_url)}
    Returns the CDN URL for requested width.
    """
    b64 = base64.b64encode(url.encode("utf-8")).decode("utf-8")
    return f"https://img.relive.com/-/w:{width}/{b64}"

# GPX index loading & parsing
def parse_datetime_from_token(token):
    token = token.strip()
    m = re.match(r"^(\d{8})[_-]?(\d{4,6})?$", token)
    if m:
        date_part = m.group(1)
        time_part = m.group(2)
        if time_part:
            if len(time_part) == 4:
                return datetime.strptime(date_part + time_part, "%Y%m%d%H%M")
            else:
                return datetime.strptime(date_part + time_part, "%Y%m%d%H%M%S")
        else:
            return datetime.strptime(date_part, "%Y%m%d")
    return None

# Read full GPX list with full-line retention
gpx_candidates = []
if gpx_list_file.exists():
    with open(gpx_list_file, "r", encoding="latin-1", errors="ignore") as gf:
        for raw in gf:
            full_line = raw.strip()
            if not full_line:
                continue
            mfile = re.search(r'(.+\.gpx)', full_line, flags=re.I)
            if not mfile:
                continue
            filename = mfile.group(1)
            m_ts = re.search(r'(\d{8}[_-]?\d{4,6})', filename)
            dt_found = None
            if m_ts:
                dt_found = parse_datetime_from_token(m_ts.group(1))
            else:
                m_date = re.search(r'(\d{8})', filename)
                if m_date:
                    dt_found = parse_datetime_from_token(m_date.group(1))
            gpx_candidates.append({
                "filename": filename,
                "fullpath": full_line,
                "dt": dt_found
            })
else:
    gpx_candidates = []

gpx_with_dt = [g for g in gpx_candidates if g["dt"] is not None]
gpx_without_dt = [g for g in gpx_candidates if g["dt"] is None]

# Build feed skeleton
all_terms_set = []
all_terms_list = []

feed = {
    "version": "1.0",
    "encoding": "UTF-8",
    "feed": {
        "xmlns": "http://www.w3.org/2005/Atom",
        "id": {"$t": "tag:blogger.com,1999:blog-activity-feed"},
        "updated": {"$t": iso_format(None)},
        "category": [],
        "title": {"type": "text", "$t": "Relive Activities"},
        "entry": []
    }
}

# Process activities
with open(source_file, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        # limit for testing / safety in original script
        # if i >= 5:
        #     break
        line = line.strip()
        if not line:
            continue

        activity = ast.literal_eval(line)
        info = activity.get('activity_info', {})

        # Skip private activities if configured
        privacy = info.get('privacy', {})
        if EXCLUDE_PRIVATE and privacy.get('value') == 'private':
            print(f"Skipping private activity: {info.get('name', activity.get('id'))}")
            continue

        activity_name = info.get('name', f"activity-{i+1}")
        slug = sanitize_name(activity_name)

        start_date = info.get('start_date_local') or info.get('start_date')
        if start_date:
            dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        else:
            dt = datetime.utcnow()

        year = dt.strftime("%Y")
        month = dt.strftime("%m")

        post_url = f"https://{GITHUB_REPO_NAME}/posts/{year}/{month}/{slug}/index.html"

        published = iso_format(start_date)
        updated = iso_format(start_date)

        raw_category = info.get('type', 'Other')
        term_with_prefix = f"1. {raw_category}"

        if term_with_prefix not in all_terms_set:
            all_terms_set.append(term_with_prefix)
            all_terms_list.append({"term": term_with_prefix})

        categories = [{"term": term_with_prefix}]

        # Images
        images_html = ""
        media_list = info.get('media', []) or []

        # Cover photo
        cover_photo_url = None
        thumbnail_url = None
        cover_width = 800  # default horizontal
        cover = info.get('cover', {})
        if cover and cover.get('type') == 'url' and 'image' in cover:
            img = cover['image']
            if 'url' in img:
                cover_photo_url = img['url']
                # Compute width from media list if possible
                cover_filename = cover_photo_url.split("/")[-1]
                for media in media_list:
                    for variant in media.get('variants', []):
                        url = variant.get('url', '')
                        if url.endswith(cover_filename):
                            h = variant.get('height')
                            w = variant.get('width')
                            if h and w:
                                cover_width = 600 if h > w else 800
                            break

        # Content HTML
        content_html = f"""
<div style="display: none;">
  <summary>{activity_name}</summary>
</div>
<span><a name='more'></a></span>
"""

        # Cover image with separate CDN widths
        if cover_photo_url:
            src_cdn = relive_cdn(cover_photo_url, CDN_SRC_WIDTH)
            href_cdn = relive_cdn(cover_photo_url, CDN_HREF_WIDTH)
            content_html += f"""
<a href="{href_cdn}" style="display: block; padding: 1em 0px; text-align: center;">
  <img data-skip="0;-1" alt="{activity_name}" border="0" src="{src_cdn}" width="{cover_width}" />
</a>

<hr />
"""

        # Peak/activity tag
        content_html += f"""
<div class="peak-tag"> 
  <br /><b><span style="font-size: 25px;">{activity_name}</span></b><br /><br />
</div>
"""

        # Media images
        for media in media_list:
            variants = media.get('variants', []) or []
            if not variants:
                continue
            original = variants[0]
            original_url = original.get('url')
            if not original_url:
                continue

            # Determine width attribute based on orientation (height/width) if available
            image_width = 600
            h = original.get('height')
            w = original.get('width')
            if h and w:
                if int(h) > int(w):
                    image_width = 450
                else:
                    image_width = 600
            else:
                # fallback keep 600
                image_width = 600

            # Skip cover if already added
            if cover_photo_url and original_url == cover_photo_url:
                data_skip = "0;-1"
            else:
                data_skip = "1"

            src_cdn = relive_cdn(original_url, CDN_SRC_WIDTH)
            href_cdn = relive_cdn(original_url, CDN_HREF_WIDTH)

            images_html += f"""
<div class="separator" style="clear: both;">
  <a href="{href_cdn}" style="display: block; padding: 1em 0px; text-align: center;">
    <img data-skip="{data_skip}" alt="{activity_name}" border="0" src="{src_cdn}" width="{image_width}" />
  </a>
</div>
"""
        content_html += images_html

        # Slideshow
        if cover_photo_url:
            content_html += f"""
<script>
var slideshowTitle0 = 'Make post slideshow';
var CoverPhoto0 = '{relive_cdn(cover_photo_url, CDN_SRC_WIDTH)}';
</script>
"""

        # GPX matching
        matched_gpx = None
        activity_dt_naive = dt.replace(tzinfo=None)
        best = None
        best_diff = None
        for g in gpx_with_dt:
            diff = abs((g["dt"] - activity_dt_naive).total_seconds())
            if best is None or diff < best_diff:
                best = g
                best_diff = diff
        if best is None and gpx_without_dt:
            lower_slug = slug.lower()
            for g in gpx_without_dt:
                if lower_slug in g["filename"].lower():
                    best = g
                    break

        if best and (best_diff is None or best_diff <= 86400):
            gpx_url = GPX_BASE_URL + best["fullpath"]
        else:
            gpx_url = ""

        content_html += f"""
<script>
var gpxURL0 = "{gpx_url}";
var ReliveURL0 = "{activity.get('activity_page_url', '')}";
var StravaURL0 = "";
</script>
"""

        # Build JSON entry
        entry = {
            "id": {"$t": f"tag:blogger.com,1999:blog-post-{activity.get('id')}"},
            "title": {"type": "text", "$t": activity_name},
            "author": {"name": {"$t": "Matej"}},
            "published": {"$t": published},
            "updated": {"$t": updated},
            "category": categories,
            "content": {"$t": content_html},
            "link": [
                {"rel": "alternate", "type": "text/html", "href": post_url},
                {"rel": "self", "type": "application/json", "href": f"{activity.get('id')}.json"}
            ]
        }

        # Add cover photo in feed JSON with w:600
        if cover_photo_url:
            entry["media$thumbnail"] = {
                "xmlns$media": "http://search.yahoo.com/mrss/",
                "url": relive_cdn(cover_photo_url, CDN_FEED_COVER_WIDTH),
                "height": "auto",
                "width": str(CDN_FEED_COVER_WIDTH)
            }

        feed["feed"]["entry"].append(entry)

        # Save JSON
        with open(posts_root / f"{activity.get('id')}.json", 'w', encoding='utf-8') as pf:
            json.dump({"version": "1.0", "encoding": "UTF-8", "entry": entry}, pf, indent=2, ensure_ascii=False)

feed["feed"]["category"] = all_terms_list

with open(feed_file, 'w', encoding='utf-8') as f:
    json.dump(feed, f, indent=2, ensure_ascii=False)

print(f"\n✅ Combined feed generated: {feed_file}")
print(f"✅ Individual feeds saved in {posts_root}/")
