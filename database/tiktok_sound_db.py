import requests
import os
import yaml
import json
import time
import re
import unicodedata
from playwright.sync_api import sync_playwright

# ---------------- CONFIG LOAD ----------------
config_file = "database/config.yaml"

with open(config_file, "r") as f:
    cfg = yaml.safe_load(f)

db_path = cfg["db_path"]
genres_cfg = cfg["genres"]
spotify_client_id = cfg.get("spotify_client_id")
spotify_client_secret = cfg.get("spotify_client_secret")

# Load DB
if os.path.exists(db_path):
    with open(db_path, "r", encoding="utf-8") as f:
        data = json.load(f)
else:
    data = []


# -------------------------------------------------------------
# Username helper
# -------------------------------------------------------------
def extract_username(url):
    if "tiktok.com" in url:
        return url.split("@")[-1].replace("/", "")
    if url.startswith("@"):
        return url[1:]
    return url


# -------------------------------------------------------------
# PLAYWRIGHT: Load all video URLs (desktop mode)
# -------------------------------------------------------------
def get_user_videos(username, headless=False):
    print(f"Scraping profile: @{username}")

    profile_url = f"https://www.tiktok.com/@{username}"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={"width": 1600, "height": 900},
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )

        page = context.new_page()
        page.goto(profile_url, timeout=60000)
        page.wait_for_timeout(3000)

        if "verify" in page.url.lower():
            print("CAPTCHA. Run with headless=False.")
            browser.close()
            return []

        links = set()
        same = 0
        last_count = 0

        print("   → Scrolling...")

        while True:
            for _ in range(8):
                page.mouse.wheel(0, 250)
                page.wait_for_timeout(200)

            new = page.eval_on_selector_all(
                "a[href*='/video/']",
                "els => els.map(e => e.href.split('?')[0])"
            )

            for link in new:
                if "/video/" in link:
                    links.add(link)

            if len(links) == last_count:
                same += 1
            else:
                same = 0
                last_count = len(links)

            if same >= 12:
                break

            page.evaluate("window.scrollBy(0, document.body.scrollHeight * 0.2);")
            page.wait_for_timeout(1200)

        browser.close()

    print(f"   → Found {len(links)} videos")
    return list(links)


# -------------------------------------------------------------
# Artist cleaner for Spotify
# -------------------------------------------------------------
def clean_artist_name(raw):
    if not raw:
        return None

    s = raw.lower().strip()

    if any(x in s for x in ["original sound", "som original", "sonido original", "unknown"]):
        return None

    s = ''.join(ch for ch in raw if ch.isalnum() or ch in " &,-()")

    for sep in [" & ", ",", "/", " feat", " ft", " x ", ";"]:
        if sep in s.lower():
            return s.split(sep)[0].strip()

    return s.strip()



# -------------------------------------------------------------
# Extract TikTok oEmbed Data
# -------------------------------------------------------------
def get_tiktok_oembed(url):
    try:
        r = requests.get(f"https://www.tiktok.com/oembed?url={url}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f" oEmbed error: {e}")
        return None


# -------------------------------------------------------------
# Extract music title/artist from oEmbed HTML
# -------------------------------------------------------------
def extract_music_from_oembed(oembed):
    html = oembed.get("html", "")

    match = re.search(r'title="♬\s*(.*?)"', html)
    if not match:
        return None, None

    full = match.group(1).strip()

    if "original sound" in full.lower() or "som original" in full.lower():
        return None, None

 
    parts = full.split(" - ")

    if len(parts) >= 2:
        title = parts[0].strip()
        artist = parts[-1].strip()  
    else:
        title = full
        artist = None

    return title, artist



# -------------------------------------------------------------
# SPOTIFY HELPERS
# -------------------------------------------------------------
def get_spotify_token(cid, secret):
    if not cid or not secret:
        print("No Spotify client_id / client_secret in config.yaml")
        return None

    try:
        r = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(cid, secret)
        )
        if r.status_code != 200:
            print(" Spotify token request failed:", r.status_code, r.text)
            return None

        data = r.json()
        token = data.get("access_token")
        if not token:
            print(" No access_token in Spotify response:", data)
        return token
    except Exception as e:
        print("Exception while getting Spotify token:", e)
        return None


def spotify_search(title, artist, token):

    if artist:
        q = f"track:{title} artist:{artist}"
        track = _spotify_query(q, token)
        if track: return track

    q = f"track:{title}"
    track = _spotify_query(q, token)
    if track: return track

    simple_title = re.sub(r"[^a-zA-Z0-9 ]", "", title)
    q = simple_title
    return _spotify_query(q, token)


def _spotify_query(q, token):
    r = requests.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": q, "type": "track", "limit": 1}
    )
    items = r.json().get("tracks", {}).get("items", [])
    return items[0] if items else None



def get_artist_genres(artist_id, token):
    try:
        r = requests.get(
            f"https://api.spotify.com/v1/artists/{artist_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        if r.status_code != 200:
            print(f" Spotify artist fetch failed ({r.status_code}): {r.text}")
            return []
        return r.json().get("genres", [])
    except Exception as e:
        print(" Exception while fetching artist genres:", e)
        return []


# -------------------------------------------------------------
# GENRE BUCKET
# -------------------------------------------------------------
def assign_genre(spotify_genres, genres_cfg):
    text = " ".join(spotify_genres).lower()
    for bucket, keywords in genres_cfg.items():
        if bucket == "general":
            continue
        for kw in keywords:
            if kw.lower() in text:
                return bucket
    return "general"


# -------------------------------------------------------------
# MAIN PIPELINE
# -------------------------------------------------------------
def main():

    # Spotify token
    spotify_token = get_spotify_token(spotify_client_id, spotify_client_secret)
    if spotify_token:
        print("Spotify token loaded.")
    else:
        print("No Spotify token — all genres will stay 'general'.")

    existing_ids = {item["video_id"] for item in data}
    new_items = []

    # ---- Step 1: scrape URLs ----
    all_links = []
    for chan in cfg["channels"]:
        username = extract_username(chan)
        all_links += get_user_videos(username, headless=False)

    print(f"\nTotal video URLs: {len(all_links)}\n")

    # ---- Step 2: extract oEmbed music safely ----
    for url in all_links:
        vid_id = url.split("/")[-1]
        if vid_id in existing_ids:
            continue

        print(f"→ Extracting sound for {vid_id}")

        oembed = get_tiktok_oembed(url)
        if not oembed:
            print(" oEmbed failed.")
            continue

        title, artist = extract_music_from_oembed(oembed)
        if not title:
            print(" No music found.")
            continue

        print(f"  Title: {title} | Raw artist: {artist}")

        final_genre = "general"
        spotify_genres = []

        if spotify_token:
            clean_name = clean_artist_name(artist)
            track = None

            # First try: track + cleaned artist
            if clean_name:
                print(f" Spotify search with artist: {clean_name}")
                track = spotify_search(title, clean_name, spotify_token)

            # Fallback: track only (no artist filter)
            if not track:
                print(" Fallback Spotify search with title only")
                track = spotify_search(title, None, spotify_token)

            # If still no match → SKIP THE ENTRY
            if not track:
                print(" Not on Spotify → SKIPPING song")
                continue
            
            # If match found → assign genre
            artist_id = track["artists"][0]["id"]
            spotify_genres = get_artist_genres(artist_id, spotify_token)
            final_genre = assign_genre(spotify_genres, genres_cfg)
            print(f" Spotify genres: {spotify_genres} → bucket: {final_genre}")

        
        # ---- Ensure song is not already in DB ----
        song_key = (title.lower(), (artist or "").lower())

        existing_song_keys = {
            (item["sound_title"].lower(), (item["sound_author"] or "").lower())
            for item in data
        }

        if song_key in existing_song_keys:
            print("Song already exists in DB, skipping.")
            continue


        new_items.append({
            "video_id": vid_id,
            "sound_title": title,
            "sound_author": artist,
            "genre": final_genre,
            "used": False
        })

    # ---- Step 3: Save DB ----
    combined = data + new_items
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    print(f"\n Added {len(new_items)} new items")
    print(f" DB now contains {len(combined)} sounds")


if __name__ == "__main__":
    main()
