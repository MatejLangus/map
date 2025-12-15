import os
import ast
from datetime import datetime
from slugify import slugify
import xml.etree.ElementTree as ET

# ----- CONFIG -----
GPX_FOLDER = "gpx-files"       # folder with your GPX files
METADATA_FILE = "relive_data.txt"  # file with one dict per line
output_file = "matched_activities.csv"
sitemap_path = "sitemap.xml"


def load_sitemap_urls(path: str):
    """Parse sitemap.xml and return a set of all <loc> URLs."""
    urls = set()

    try:
        tree = ET.parse(path)
        root = tree.getroot()

        for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
            urls.add(loc.text.strip())
    except Exception as e:
        print("Sitemap error:", e)

    return urls

def make_blog_url(name: str, start_date_local: str) -> str:
    """Create blog URL: posts/YYYY/MM/slug/index.html"""
    try:
        dt = datetime.fromisoformat(start_date_local.replace("Z", "+00:00"))
        year = dt.strftime("%Y")
        month = dt.strftime("%m")
    except Exception:
        year = "0000"
        month = "00"

    slug = slugify(name)
    return f"https://matejlangus.github.io/map/posts/{year}/{month}/{slug}/index.html"

def create_matched_csv():
    # ----- LOAD GPX FILES -----
    gpx_files = []
    for filename in os.listdir(GPX_FOLDER):
        if filename.lower().endswith(".gpx"):
            gpx_files.append( filename)

    print(f"Found {len(gpx_files)} GPX files.")

    # Extract last part of GPX filename (after '__')
    gpx_timestamps = {}
    for file in gpx_files:
        base = os.path.basename(file)
        last_part = os.path.splitext(base)[0].split(" ")[0]+os.path.splitext(base)[0].split(" ")[1][:2]
        gpx_timestamps[last_part] = file

    # ----- LOAD RELIVE ACTIVITIES -----
    relive_activities = []
    with open(METADATA_FILE, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                activity = ast.literal_eval(line)
                relive_activities.append(activity)
            except Exception as e:
                print(f"Skipping line {line_num} due to parse error: {e}")

    print(f"Loaded {len(relive_activities)} Relive activities.")


    # --- MATCH GPX TO RELIVE ---
    matched = []
    sitemap_urls = load_sitemap_urls(sitemap_path)

    for activity in relive_activities:
        start = activity.get('activity_info', {}).get('start_date_local', '')
        if start:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            relive_timestamp = dt.strftime("%Y-%m-%d%H")
            if relive_timestamp in gpx_timestamps:
                # get cover photo URL if available
                cover_url = activity.get("activity_info", {}).get("cover", {}).get("image", {}).get("url", "")
                blog_url = make_blog_url(
                activity.get("activity_info", {}).get("name"),
                start)
                if blog_url not in sitemap_urls:
                    blog_url = None
                   

                
                matched.append({
                    "gpx_file": gpx_timestamps[relive_timestamp],  # just filename
                    "relive_id": activity.get("id"),
                    "relive_url": activity.get("activity_page_url"),
                    "name": activity.get("activity_info", {}).get("name"),
                    "video_url": activity.get("video_url"),
                    "cover_photo": cover_url,
                    "blog_url": blog_url
                })
            else:
                print(activity.get("activity_info", {}).get("name"), relive_timestamp)

    print(f"Matched {len(matched)} activities.")

    # --- SAVE RESULTS ---
    import csv

    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["gpx_file", "relive_id","relive_url", "name", "video_url", "cover_photo", "blog_url"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in matched:
            writer.writerow(row)

    print(f"Results saved to {output_file}")


def main():
    create_matched_csv()           

if __name__ == "__main__":
    main()
