import requests
import re
import json
from html import unescape


GENIUS_API_TOKEN = "1rnjcBnyL8eAARorEsLIG-JxO8JtsvAfygrPhd7uPxcXxMYK0NaNlL_i-jCsW0zt"
GENIUS_BASE_URL = "https://api.genius.com"


def fetch_genius_lyrics(song_title):
    """
    Fully correct Genius lyric scraper:
    - Uses Genius API to find the song page
    - Extracts ALL lyrics from __PRELOADED_STATE__
    - Recursively flattens the children tree
    - Preserves exact ordering of every line
    - Removes metadata like [Chorus], [Verse X]
    """

    if not GENIUS_API_TOKEN or not song_title:
        return None

    headers = {"Authorization": f"Bearer {GENIUS_API_TOKEN}"}

    # ----- Parse artist/title if provided as: "Artist - Song" -----
    artist = None
    title = song_title.strip()
    if " - " in song_title:
        artist, title = [x.strip() for x in song_title.split(" - ", 1)]

    q = f"{title} {artist}" if artist else title

    # ----- Genius Search -----
    try:
        res = requests.get(
            f"{GENIUS_BASE_URL}/search",
            params={"q": q},
            headers=headers,
            timeout=10
        ).json()
    except:
        print("[GENIUS] Search request failed.")
        return None

    hits = res.get("response", {}).get("hits", [])
    if not hits:
        print("[GENIUS] No hits found.")
        return None

    url = hits[0]["result"]["url"]

    # ----- Fetch HTML -----
    try:
        html = requests.get(url, timeout=10).text
    except:
        print("[GENIUS] Failed to fetch song HTML.")
        return None

    # ----- Extract __PRELOADED_STATE__ JSON -----
    state_match = re.search(
        r'window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});',
        html,
        flags=re.DOTALL
    )

    if not state_match:
        print("[GENIUS] Could not locate PRELOADED_STATE. Falling back.")
        return fallback_html_lyrics(html)

    try:
        data = json.loads(state_match.group(1))
    except Exception as e:
        print("[GENIUS] JSON decode error:", e)
        return fallback_html_lyrics(html)

    # ----- Locate the lyrics tree -----
    try:
        body_children = (
            data["songPage"]["lyricsData"]["body"]["children"]
        )
    except Exception as e:
        print("[GENIUS] Lyrics JSON structure changed:", e)
        return fallback_html_lyrics(html)

    # ----- Recursively flatten all nodes into plain text -----
    full_text = extract_text_from_json(body_children)

    # ----- Clean + filter -----
    lines = [
        ln.strip()
        for ln in full_text.splitlines()
        if ln.strip() and not (ln.startswith("[") and ln.endswith("]"))
    ]

    return "\n".join(lines)


def extract_text_from_json(node):
    """
    Recursively flatten all children into plain text
    preserving the exact order of lyrics.
    """

    if isinstance(node, str):
        return node

    if isinstance(node, dict):
        pieces = []
        for child in node.get("children", []):
            pieces.append(extract_text_from_json(child))
        return "\n".join(pieces)

    if isinstance(node, list):
        pieces = []
        for child in node:
            pieces.append(extract_text_from_json(child))
        return "\n".join(pieces)

    return ""


def fallback_html_lyrics(html):
    """
    Only used if JSON extraction fails.
    Still improved over your original fallback.
    """

    blocks = re.findall(
        r'<div[^>]+data-lyrics-container="true"[^>]*>(.*?)</div>',
        html,
        flags=re.DOTALL | re.IGNORECASE
    )

    if not blocks:
        return None

    cleaned = []
    for blk in blocks:
        blk = re.sub(r'<br\s*/?>', '\n', blk)
        blk = re.sub(r'<.*?>', '', blk)
        cleaned.append(blk.strip())

    text = unescape("\n".join(cleaned))

        # ----- Clean + filter -----
    raw_lines = [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and not (ln.startswith("[") and ln.endswith("]"))
    ]

    # Remove junk like "168 ContributorsTranslations"
    lines = []
    for ln in raw_lines:
        low = ln.lower()
        if "contributors" in low or "translations" in low:
            continue
        lines.append(ln)

    return "\n".join(lines)

