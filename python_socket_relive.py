import socketio
import time
import re
import requests
from export_relive import missing_relive_to_file
from combine_relive_data import create_matched_csv

missing_relive_to_file()

sio = socketio.Client()

@sio.on("connect")
def on_connect():
    print("Connected to Relive realtime API")

@sio.on("activity_done")
def on_activity_done(data):
    print("Activity ID:", data.get("id"))
    print("Name:", data["activity_info"].get("name"))
    print("Page URL:", data.get("activity_page_url"))
    with open("relive_data.txt", "a", encoding="utf-8") as file1:
        file1.write(str(data) + "\n")
        sio.disconnect()




# Read links from file
with open("missing_ids.txt") as f:
    links = [line.strip() for line in f if line.strip()]

for link in links:
    time.sleep(1)
    print(f"Processing: {link}")
    try:
        r = requests.get(link)
        html = r.text

        # Look for activityId or activity_id
        match = re.search(r'"activityId\\":(\d+)', html)
        if match:
            activiti_id = match.group(1)
            print("Found activityId:", activiti_id)

            # Connect
            sio.connect("https://realtime.api.relive.cc", transports=["websocket"])

            # Subscribe to activity
            sio.emit("listen_activity_done", {"activityId": activiti_id})

            # Keep alive
            sio.wait()

        else:
            print("activityId not found")
    except Exception as e:
        print(f"Error fetching {link}: {e}")

create_matched_csv()



