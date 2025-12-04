import os
import json
import re
import yaml
from datetime import datetime,timedelta
import random

config_file = "database/config.yaml"
if not os.path.exists(config_file):
    raise FileNotFoundError("Config file missing — make sure config.yaml exists")

with open(config_file, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

db_path = cfg["db_path"]

if not os.path.exists(db_path):
    raise FileNotFoundError(f"Database not found at {db_path}")

with open(db_path, "r", encoding="utf-8") as f:
    db = json.load(f)


genres_available = list(cfg["genres"].keys())
print(f"\nAvailable topics: {genres_available}")
song_genre = input("Enter genre to output: ").strip().lower()
if song_genre not in genres_available:
    raise ValueError(f"'{song_genre}' not in {genres_available}")

def is_on_cooldown(video):
    used_list = video.get("used_in_compilation", [])
    if not used_list:
        return False  

    last_used_str = used_list[-1]  
    try:
        ts_part = last_used_str.split("_compilation_")[-1].replace(".mp4", "")
        last_used_dt = datetime.strptime(ts_part, "%Y-%m-%d_%H-%M-%S")
    except Exception:
        return False  
    return datetime.now() - last_used_dt < timedelta(days=30)


eligible = []
for song in db:
    if song["genre"].lower() != song_genre:
        continue

    if is_on_cooldown(song):
        continue

    eligible.append(song)

if not eligible:
    print(f"\nNo songs available for genre '{song_genre}' (all on cooldown or missing).")
    exit()

chosen = random.choice(eligible)

print("\n Selected track:")
print("----------------------------")
print(f" Title : {chosen['sound_title']}")
print(f" Artist: {chosen['sound_author']}")
print(f" Genre : {chosen['genre']}")
print(f" Video : https://www.tiktok.com/@username/video/{chosen['video_id']}")
print("----------------------------\n")


timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
used_entry = f"used_compilation_{timestamp}.mp4"

if "used_in_compilation" not in chosen:
    chosen["used_in_compilation"] = []

chosen["used_in_compilation"].append(used_entry)

with open(db_path, "w", encoding="utf-8") as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

print(f"Updated '{chosen['sound_title']}' as used.")
print(f"Saved to {db_path}")