"""
Mono Lyric Processing - Word-level timestamp extraction
For minimal text-only lyric videos with word-by-word reveal

Uses the shared sliding window alignment engine for accurate lyrics.
Output: markers with {time, text, words[], color, end_time}
"""
import os
import json
import re
from stable_whisper import load_model

from scripts.config import Config
from scripts.genius_processing import fetch_genius_lyrics
from scripts.lyric_alignment import align_genius_to_whisper


def transcribe_audio_mono(job_folder, song_title=None):
    """
    Transcribe audio with word-level timestamps for Mono style videos.
    
    Returns dict with:
        - markers: list of marker objects for JSX
        - total_markers: count of markers
    """
    print(f"\n✎ Mono Transcription ({Config.WHISPER_MODEL})...")
    
    audio_path = os.path.join(job_folder, "audio_trimmed.wav")
    
    if not os.path.exists(audio_path):
        print("❌ Trimmed audio not found")
        return {"markers": [], "total_markers": 0}
    
    try:
        # Load model
        os.makedirs(Config.WHISPER_CACHE_DIR, exist_ok=True)
        
        model = load_model(
            Config.WHISPER_MODEL,
            download_root=Config.WHISPER_CACHE_DIR,
            in_memory=False
        )
        
        # Build context prompt
        initial_prompt = _build_initial_prompt(song_title)
        
        # Primary transcription with word-level timestamps
        result = model.transcribe(
            audio_path,
            word_timestamps=True,
            vad=True,
            vad_threshold=0.35,
            suppress_silence=True,
            regroup=True,
            temperature=0,
            initial_prompt=initial_prompt,
            condition_on_previous_text=False,
        )
        
        # Fallback if empty
        if not result.segments:
            print("  Empty transcription, retrying with fallback params...")
            result = model.transcribe(
                audio_path,
                word_timestamps=True,
                vad=False,
                suppress_silence=False,
                regroup=True,
                temperature=0.3,
                initial_prompt=initial_prompt,
                condition_on_previous_text=False,
            )
        
        if not result.segments:
            print("❌ Whisper returned no segments")
            return {"markers": [], "total_markers": 0}
        
        # Build raw markers from Whisper segments
        markers = _build_markers_from_segments(result.segments)
        
        if not markers:
            print("❌ No valid markers generated")
            return {"markers": [], "total_markers": 0}
        
        # Fetch Genius lyrics and align
        if song_title and Config.GENIUS_API_TOKEN:
            print("✎ Fetching Genius lyrics for alignment...")
            genius_text = fetch_genius_lyrics(song_title)
            
            if genius_text:
                # Save reference
                genius_path = os.path.join(job_folder, "genius_lyrics.txt")
                with open(genius_path, "w", encoding="utf-8") as f:
                    f.write(genius_text)
                
                # Align using sliding window
                print("✎ Aligning lyrics (sliding window)...")
                markers = align_genius_to_whisper(
                    markers, genius_text, segment_text_key="text"
                )
                
                # After alignment, rebuild word arrays from the new text
                # while preserving Whisper's timing
                markers = _rebuild_words_after_alignment(markers)
        
        # Assign alternating colors
        _assign_colors(markers)
        
        print(f"✓ Mono transcription complete: {len(markers)} markers")
        
        return {
            "markers": markers,
            "total_markers": len(markers)
        }
        
    except Exception as e:
        print(f"❌ Mono transcription failed: {e}")
        raise


# ============================================================================
# MARKER BUILDING
# ============================================================================

def _build_markers_from_segments(segments):
    """Build marker objects from Whisper segments with word timing"""
    markers = []
    
    for seg_idx, segment in enumerate(segments):
        seg_text = segment.text.strip()
        seg_start = float(segment.start)
        seg_end = float(segment.end)
        
        # Skip empty or very short segments
        if not seg_text or len(seg_text) < 2:
            continue
        
        # Skip overly long segments (merge errors)
        if seg_end - seg_start > 15:
            print(f"   ⚠ Skipping overly long segment: {seg_text[:30]}...")
            continue
        
        # Extract word timings
        words = _extract_word_timings(segment, seg_start, seg_end, seg_text)
        
        marker = {
            "time": seg_start,
            "text": seg_text,
            "words": words,
            "color": "",  # Assigned later
            "end_time": seg_end
        }
        
        markers.append(marker)
    
    return markers


def _extract_word_timings(segment, seg_start, seg_end, seg_text):
    """Extract word-level timings from a Whisper segment"""
    words = []
    
    if hasattr(segment, 'words') and segment.words:
        for word in segment.words:
            word_text = word.word.strip()
            if not word_text:
                continue
            
            word_start = float(word.start)
            word_end = float(word.end)
            
            # Validate word timing
            word_duration = word_end - word_start
            if word_duration > 5:
                word_end = word_start + min(word_duration, 1.0)
            
            words.append({
                "word": word_text,
                "start": round(word_start, 3),
                "end": round(word_end, 3)
            })
    else:
        # Fallback: distribute words evenly
        word_list = seg_text.split()
        if word_list:
            duration = seg_end - seg_start
            word_duration = duration / len(word_list)
            for i, w in enumerate(word_list):
                words.append({
                    "word": w,
                    "start": round(seg_start + (i * word_duration), 3),
                    "end": round(seg_start + ((i + 1) * word_duration), 3)
                })
    
    return words


def _rebuild_words_after_alignment(markers):
    """
    After Genius alignment, the 'text' field may have changed but
    'words' still has Whisper's original words. We need to map the
    new Genius words to the existing timing.
    
    Strategy: If word count is similar, map 1:1. If very different,
    distribute Genius words evenly across the segment's time span.
    """
    for marker in markers:
        genius_words = marker["text"].split()
        whisper_words = marker.get("words", [])
        
        if not genius_words or not whisper_words:
            continue
        
        # If the text didn't change (Whisper was used), skip
        whisper_text_joined = " ".join(w["word"] for w in whisper_words)
        if whisper_text_joined.strip().lower() == marker["text"].strip().lower():
            continue
        
        # Rebuild words with Genius text but Whisper timing
        new_words = []
        
        if len(genius_words) <= len(whisper_words):
            # Fewer or equal Genius words: map to first N Whisper timings
            for i, gw in enumerate(genius_words):
                new_words.append({
                    "word": gw,
                    "start": whisper_words[i]["start"],
                    "end": whisper_words[min(i, len(whisper_words) - 1)]["end"]
                })
        else:
            # More Genius words than Whisper words: distribute evenly
            seg_start = marker["time"]
            seg_end = marker["end_time"]
            duration = seg_end - seg_start
            word_dur = duration / len(genius_words)
            
            for i, gw in enumerate(genius_words):
                new_words.append({
                    "word": gw,
                    "start": round(seg_start + (i * word_dur), 3),
                    "end": round(seg_start + ((i + 1) * word_dur), 3)
                })
        
        marker["words"] = new_words
    
    return markers


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _build_initial_prompt(song_title):
    """Build Whisper initial prompt from song title"""
    if not song_title:
        return None
    
    if " - " in song_title:
        artist, track = song_title.split(" - ", 1)
        return f"Lyrics from the song '{track}' by {artist}."
    
    return f"Lyrics from the song '{song_title}'."


def _assign_colors(markers):
    """Assign alternating white/black colors to markers"""
    for i, marker in enumerate(markers):
        marker["color"] = "white" if i % 2 == 0 else "black"


def _fix_marker_gaps(markers):
    """Ensure word timings don't have large unexplained gaps"""
    for marker in markers:
        words = marker.get("words", [])
        if len(words) < 2:
            continue
        
        for i in range(1, len(words)):
            prev_end = words[i - 1]["end"]
            curr_start = words[i]["start"]
            gap = curr_start - prev_end
            
            if gap > 2.0:
                words[i]["start"] = prev_end + 0.1
    
    return markers
