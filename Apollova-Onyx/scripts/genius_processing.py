"""Genius API integration for lyrics and cover art"""
import requests
import re
import json
from html import unescape

from scripts.config import Config
from scripts.image_processing import download_image


def fetch_genius_image_with_url(song_title, job_folder):
    """
    Fetch cover image from Genius and return both the local path AND the URL.
    Returns: (image_path, image_url) or (None, None) if failed
    """
    if not Config.GENIUS_API_TOKEN:
        return None, None
    
    if not song_title:
        return None, None
    
    headers = {"Authorization": f"Bearer {Config.GENIUS_API_TOKEN}"}
    
    # Parse "Artist - Song" format
    artist = None
    title = song_title.strip()
    if " - " in song_title:
        parts = song_title.split(" - ", 1)
        artist = parts[0].strip()
        title = parts[1].strip()
    
    query = f"{title} {artist}" if artist else title
    
    # Search Genius
    try:
        response = requests.get(
            f"{Config.GENIUS_BASE_URL}/search",
            params={"q": query},
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
    except Exception as e:
        print(f"  Genius search failed: {e}")
        return None, None
    
    # Get first result
    hits = data.get("response", {}).get("hits", [])
    if not hits:
        print("  No Genius results found")
        return None, None
    
    # Get song art URL
    song_info = hits[0]["result"]
    image_url = song_info.get("song_art_image_url") or song_info.get("header_image_url")
    
    if not image_url:
        print("  No image found in Genius result")
        return None, None
    
    # Download the image
    try:
        image_path = download_image(job_folder, image_url)
        return image_path, image_url  # Return BOTH path and URL
    except Exception as e:
        print(f"  Failed to download Genius image: {e}")
        return None, None


def fetch_genius_image(song_title, job_folder):
    """
    Legacy function - fetch cover image from Genius.
    Returns: image_path or None
    
    NOTE: Prefer fetch_genius_image_with_url() to also get the URL for database storage.
    """
    image_path, _ = fetch_genius_image_with_url(song_title, job_folder)
    return image_path


def get_genius_image_url(song_title):
    """
    Get ONLY the image URL from Genius (no download).
    Useful for database updates.
    """
    if not Config.GENIUS_API_TOKEN:
        return None
    
    if not song_title:
        return None
    
    headers = {"Authorization": f"Bearer {Config.GENIUS_API_TOKEN}"}
    
    # Parse "Artist - Song" format
    artist = None
    title = song_title.strip()
    if " - " in song_title:
        parts = song_title.split(" - ", 1)
        artist = parts[0].strip()
        title = parts[1].strip()
    
    query = f"{title} {artist}" if artist else title
    
    try:
        response = requests.get(
            f"{Config.GENIUS_BASE_URL}/search",
            params={"q": query},
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        hits = data.get("response", {}).get("hits", [])
        if not hits:
            return None
        
        song_info = hits[0]["result"]
        return song_info.get("song_art_image_url") or song_info.get("header_image_url")
        
    except Exception as e:
        print(f"  Genius API error: {e}")
        return None


def fetch_genius_lyrics(song_title):
    """Fetch lyrics text from Genius (for alignment with Whisper)"""
    if not Config.GENIUS_API_TOKEN:
        return None
    
    if not song_title:
        return None
    
    headers = {"Authorization": f"Bearer {Config.GENIUS_API_TOKEN}"}
    
    # Parse "Artist - Song" format
    artist = None
    title = song_title.strip()
    if " - " in song_title:
        parts = song_title.split(" - ", 1)
        artist = parts[0].strip()
        title = parts[1].strip()
    
    query = f"{title} {artist}" if artist else title
    
    # Search Genius
    try:
        response = requests.get(
            f"{Config.GENIUS_BASE_URL}/search",
            params={"q": query},
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
    except Exception as e:
        print(f"  Genius search failed: {e}")
        return None
    
    # Get first result
    hits = data.get("response", {}).get("hits", [])
    if not hits:
        print("  No Genius results found")
        return None
    
    song_info = hits[0]["result"]
    song_url = song_info.get("url")
    
    if not song_url:
        return None
    
    # Scrape lyrics from the page
    try:
        page_response = requests.get(song_url, timeout=10)
        page_response.raise_for_status()
        html = page_response.text
        
        # Extract lyrics using regex (Genius stores lyrics in data attributes)
        # Look for the lyrics container
        lyrics_match = re.search(r'<div[^>]*class="[^"]*Lyrics__Container[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
        
        if not lyrics_match:
            # Try alternative pattern
            lyrics_match = re.search(r'"lyrics":\s*"([^"]+)"', html)
            if lyrics_match:
                lyrics_text = lyrics_match.group(1)
                lyrics_text = lyrics_text.encode().decode('unicode_escape')
                return clean_lyrics(lyrics_text)
            return None
        
        lyrics_html = lyrics_match.group(1)
        
        # Clean HTML
        lyrics_text = re.sub(r'<br\s*/?>', '\n', lyrics_html)
        lyrics_text = re.sub(r'<[^>]+>', '', lyrics_text)
        lyrics_text = unescape(lyrics_text)
        
        return clean_lyrics(lyrics_text)
        
    except Exception as e:
        print(f"  Failed to scrape lyrics: {e}")
        return None


def clean_lyrics(text):
    """Clean up lyrics text"""
    if not text:
        return None
    
    lines = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        # Skip section headers like [Verse 1], [Chorus], etc.
        if line.startswith('[') and line.endswith(']'):
            continue
        # Skip parenthetical lines
        if line.startswith('(') and line.endswith(')'):
            continue
        lines.append(line)
    
    return '\n'.join(lines)