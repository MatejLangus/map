from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pathlib import Path
import json
import os
import time
import re



def load_ids_from_file(filepath: str):
    p = Path(filepath)
    if not p.exists():
        print(f"WARNING: {filepath} does not exist. Skipping ID comparison.")
        return set()

    ids = set()
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                # Extract the last part of the URL after the last '/'
                match = re.search(r"https?://[^/]+/view/([^'\"]+)", line)
                if match:
                    ids.add(match.group(1))
    return ids

def missing_relive_to_file():
    load_dotenv()

    EMAIL = os.getenv("RELIVE_EMAIL")
    PASSWORD = os.getenv("RELIVE_PASSWORD")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Login
            page.goto("https://www.relive.com/login")
            page.fill('input[name="email"]', EMAIL)
            page.fill('input[name="password"]', PASSWORD)
            page.click('input.login-button')
            page.wait_for_load_state("networkidle")
            print("Logged in successfully.")

            # Navigate to My Data
            page.goto("https://www.relive.com/settings/my-data")
            time.sleep(2)

            # Save HTML
            html = page.content()
            # Path("my_data.html").write_text(html, encoding="utf-8")
            # print("Saved My Data HTML to my_data.html")

            # Parse HTML
            print("Parsing HTML...")

            soup = BeautifulSoup(html, "html.parser")
            results = []

            cards = soup.select(".export-card")

            for card in cards:
                name_tag = card.find("h6")
                name = name_tag.get_text(strip=True) if name_tag else ""

                subtitle = card.find(class_="subtitle")
                date = ""
                if subtitle:
                    date = subtitle.get_text(strip=True).split("|")[0].strip()

                gpx_link = card.select_one('a[href*="/settings/my-data/"]')
                if not gpx_link:
                    continue

                href = gpx_link.get("href")
                id_ = href.split("/")[-1]

                results.append({
                    "date": date,
                    "name": name,
                    "id": id_,
                })

            # Save JSON
            # Path("relive_parsed.json").write_text(
            #    json.dumps(results, indent=2),
            #    encoding="utf-8"
            #)

            print(f"Extracted {len(results)} entries")
            print("Saved parsed data to relive_parsed.json")

            # ------------------------------------------------------------------------------------
            # ID COMPARISON WITH relive_data.txt
            # ------------------------------------------------------------------------------------
            parsed_ids = {item["id"] for item in results}

            file_ids = load_ids_from_file("relive_data.txt")


            print("Checking ID consistency...")

            missing_in_file = parsed_ids - file_ids
            extra_in_file = file_ids - parsed_ids

            print("-------------------------------------------------")
            if missing_in_file:
                    output_file = "missing_ids.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                for mid in missing_in_file:
                    f.write(f"https://www.relive.com/view/{mid}\n")
            print(f"Exported {len(missing_in_file)} missing IDs to {output_file}")

            print("-------------------------------------------------")
            if extra_in_file:
                print("IDs FOUND in relivedata.txt BUT NOT on Relive website:")
                for eid in sorted(extra_in_file):
                    print("  " + eid)
            else:
                print("No extra IDs in relivedata.txt.")

            print("-------------------------------------------------")
            print("ID comparison completed.")

        except Exception as e:
            print("Error:", e)
            page.screenshot(path="error.png")
        finally:
            browser.close()

def main():
    return            

if __name__ == "__main__":
    main()
