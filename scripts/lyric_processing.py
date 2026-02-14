"""
Aurora Lyric Processing - Line-level transcription with Genius alignment
Uses the shared sliding window alignment engine for accurate lyrics.

Output format: segments with {t, lyric_prev, lyric_current, lyric_next1, lyric_next2}
"""
import os
import json
import re
from stable_whisper import load_model

from scripts.config import Config
from scripts.genius_processing import fetch_genius_lyrics
from scripts.lyric_alignment import align_genius_to_whisper


def transcribe_audio(job_folder, song_title=None):
    """
    Transcribe audio and align with Genius lyrics for Aurora template.
    
    Returns path to saved lyrics.txt file, or None on failure.
    """
    print(f"\n✎ Aurora Transcription ({Config.WHISPER_MODEL})...")
    
    audio_path = os.path.join(job_folder, "audio_trimmed.wav")
    
    if not os.path.exists(audio_path):
        print("❌ Trimmed audio not found")
        return None
    
    try:
        # Load model
        os.makedirs(Config.WHISPER_CACHE_DIR, exist_ok=True)
        
        model = load_model(
            Config.WHISPER_MODEL,
            download_root=Config.WHISPER_CACHE_DIR,
            in_memory=False
        )
        
        # Build context prompt from song title
        initial_prompt = _build_initial_prompt(song_title)
        
        # Primary transcription with optimized settings
        result = model.transcribe(
            audio_path,
            vad=True,
            vad_threshold=0.35,
            suppress_silence=True,
            regroup=True,
            temperature=0,
            initial_prompt=initial_prompt,
            condition_on_previous_text=False,  # Prevents hallucination chains
        )
        
        # Fallback if empty
        if not result.segments:
            print("  Empty transcription, retrying with fallback params...")
            result = model.transcribe(
                audio_path,
                vad=False,
                suppress_silence=False,
                regroup=True,
                temperature=0.3,
                initial_prompt=initial_prompt,
                condition_on_previous_text=False,
            )
        
        if not result.segments:
            print("❌ Whisper returned no segments")
            return None
        
        # Build initial segments
        segments = [
            {
                "t": float(seg.start),
                "lyric_prev": "",
                "lyric_current": seg.text.strip(),
                "lyric_next1": "",
                "lyric_next2": ""
            }
            for seg in result.segments
            if seg.text.strip()  # Skip empty segments
        ]
        
        if not segments:
            print("❌ No valid segments after filtering")
            return None
        
        # Fetch and align Genius lyrics
        genius_text = None
        if song_title and Config.GENIUS_API_TOKEN:
            print("✎ Fetching Genius lyrics...")
            genius_text = fetch_genius_lyrics(song_title)
            
            if genius_text:
                # Save reference copy
                genius_path = os.path.join(job_folder, "genius_lyrics.txt")
                with open(genius_path, "w", encoding="utf-8") as f:
                    f.write(genius_text)
                
                # Align using sliding window approach
                print("✎ Aligning lyrics (sliding window)...")
                segments = align_genius_to_whisper(
                    segments, genius_text, segment_text_key="lyric_current"
                )
            else:
                print("  ⚠ Using Whisper text only (Genius unavailable)")
        
        # Build prev/next references for After Effects
        _build_lyric_context(segments)
        
        # Wrap long lines for display
        for seg in segments:
            seg["lyric_current"] = _wrap_line(seg["lyric_current"])
            seg["lyric_prev"] = _wrap_line(seg["lyric_prev"])
            seg["lyric_next1"] = _wrap_line(seg["lyric_next1"])
            seg["lyric_next2"] = _wrap_line(seg["lyric_next2"])
        
        # Save
        lyrics_path = os.path.join(job_folder, "lyrics.txt")
        with open(lyrics_path, "w", encoding="utf-8") as f:
            json.dump(segments, f, indent=4, ensure_ascii=False)
        
        valid_count = len([s for s in segments if s["lyric_current"].strip()])
        print(f"✓ Transcription complete: {valid_count} segments")
        return lyrics_path
        
    except Exception as e:
        print(f"❌ Transcription failed: {e}")
        raise


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _build_initial_prompt(song_title):
    """Build Whisper initial prompt from song title for better accuracy"""
    if not song_title:
        return None
    
    if " - " in song_title:
        artist, track = song_title.split(" - ", 1)
        return f"Lyrics from the song '{track}' by {artist}."
    
    return f"Lyrics from the song '{song_title}'."


def _build_lyric_context(segments):
    """
    Populate lyric_prev, lyric_next1, lyric_next2 fields.
    Only uses segments that have non-empty lyric_current.
    """
    # Get indices of non-empty segments
    active_indices = [
        i for i, seg in enumerate(segments)
        if seg["lyric_current"].strip()
    ]
    
    for pos, i in enumerate(active_indices):
        # Previous
        if pos > 0:
            segments[i]["lyric_prev"] = segments[active_indices[pos - 1]]["lyric_current"]
        
        # Next 1
        if pos < len(active_indices) - 1:
            segments[i]["lyric_next1"] = segments[active_indices[pos + 1]]["lyric_current"]
        
        # Next 2
        if pos < len(active_indices) - 2:
            segments[i]["lyric_next2"] = segments[active_indices[pos + 2]]["lyric_current"]


def _wrap_line(text, limit=None):
    """Wrap long lines for After Effects text display"""
    if limit is None:
        limit = Config.MAX_LINE_LENGTH
    
    text = text.strip()
    
    # Already wrapped or empty
    if not text or "\\r" in text:
        return text
    
    # Fits in one line
    if len(text) <= limit:
        return text
    
    # Find space to split
    cut = text.rfind(" ", 0, limit)
    if cut == -1:
        cut = limit
    
    first = text[:cut].strip()
    rest = text[cut:].strip()
    
    return f"{first} \\r {rest}"
