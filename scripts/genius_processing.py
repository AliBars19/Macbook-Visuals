import requests
from html import unescape
import re
from rapidfuzz import fuzz

GENIUS_API_TOKEN = "1rnjcBnyL8eAARorEsLIG-JxO8JtsvAfygrPhd7uPxcXxMYK0NaNlL_i-jCsW0zt"
GENIUS_BASE_URL = "https://api.genius.com"

def fetch_genius_lyrics(song_title):
    
   
    if not GENIUS_API_TOKEN or not song_title:
        return None

    headers = {"Authorization": f"Bearer {GENIUS_API_TOKEN}"}

    artist = None
    title = song_title.strip()
    if " - " in song_title:
        artist, title = [x.strip() for x in song_title.split(" - ", 1)]

    title_l = title.lower()
    artist_l = artist.lower() if artist else None

    def safe_request(url, params=None):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=10)
            if r.status_code == 429:
                print("  [Genius] Rate limited — waiting 3 seconds...")
                import time
                time.sleep(3)
                return safe_request(url, params)
            r.raise_for_status()
            return r
        except:
            return None

    search = safe_request(
        f"{GENIUS_BASE_URL}/search",
        params={"q": f"{title} {artist}" if artist else title}
    )
    if not search:
        print("  [Genius] Search failed — using AZLyrics fallback.")
        return fetch_azlyrics(song_title)

    hits = search.json().get("response", {}).get("hits", [])
    if not hits:
        print("  [Genius] No hits — using AZLyrics fallback.")
        return fetch_azlyrics(song_title)

    from difflib import SequenceMatcher

    def score(result):
        result_title = result.get("title", "").lower()
        result_artist = result.get("primary_artist", {}).get("name", "").lower()

        title_sim = SequenceMatcher(None, title_l, result_title).ratio()

        artist_sim = 0
        if artist_l:
            artist_sim = SequenceMatcher(None, artist_l, result_artist).ratio()

        return (title_sim * 0.6) + (artist_sim * 0.4)

    best = max([h["result"] for h in hits], key=score)
    best_score = score(best)

    if best_score < 0.35:
        print("  [Genius] Match too weak — using AZLyrics fallback.")
        return fetch_azlyrics(song_title)

    url = best.get("url")
    if not url:
        print("  [Genius] No URL — fallback to AZLyrics.")
        return fetch_azlyrics(song_title)

    page = safe_request(url)
    if not page:
        print("  [Genius] Page failed — AZLyrics fallback.")
        return fetch_azlyrics(song_title)

    html = page.text

    containers = re.findall(
        r'<div[^>]+data-lyrics-container="true"[^>]*>(.*?)</div>',
        html,
        flags=re.DOTALL | re.IGNORECASE
    )
    if not containers:
        print("  [Genius] No lyrics containers — AZLyrics fallback.")
        return fetch_azlyrics(song_title)

    collected = []
    for block in containers:
        block = re.sub(r'<br\s*/?>', '\n', block)
        block = re.sub(r'<.*?>', '', block)
        collected.append(block.strip())

    text = unescape("\n".join(collected))

    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        low = line.lower()

        if line.startswith("[") and line.endswith("]"):
            continue

        if "contributorstranslations" in low:
            continue
        if re.match(r"^\d+\s+contributorstranslations$", low):
            continue

        lines.append(line)


    if not lines:
        print("  [Genius] Lyrics empty — fallback to AZLyrics.")
        return fetch_azlyrics(song_title)

    return "\n".join(lines)



def find_genius_region_for_trimmed_audio(whisper_segments, genius_text):
 
    lines = [ln.strip() for ln in genius_text.splitlines() if ln.strip()]
    trimmed_duration = whisper_segments[-1]["t"] - whisper_segments[0]["t"]

    approx_lines = int(trimmed_duration / 2.2)
    approx_lines = max(1, min(approx_lines, len(lines)))

    region = lines[:approx_lines]

    return region



def fetch_azlyrics(song_title):
    
    print("  [AZLyrics] Attempting fallback lyric extraction...")

    if " - " not in song_title:
        return None

    artist, title = [x.strip() for x in song_title.split(" - ", 1)]
    artist = artist.lower().replace(" ", "")
    title = title.lower().replace(" ", "")

    url = f"https://www.azlyrics.com/lyrics/{artist}/{title}.html"

    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            print("  [AZLyrics] Not found.")
            return None

        html = r.text

        # lyrics are between two <div>s without classes
        m = re.search(
            r'<!-- Usage of azlyrics.com content.*?-->(.*?)(</div>)',
            html,
            flags=re.DOTALL
        )
        if not m:
            print("  [AZLyrics] Parsing failed.")
            return None

        block = m.group(1)
        block = re.sub(r'<br\s*/?>', '\n', block)
        block = re.sub(r'<.*?>', '', block)

        cleaned = "\n".join([ln.strip() for ln in block.splitlines() if ln.strip()])
        return cleaned

    except Exception:
        return None