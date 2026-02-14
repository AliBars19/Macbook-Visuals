"""
Lyric Alignment Engine - Sliding window approach for matching
Whisper transcriptions to Genius lyrics.

Shared across Aurora, Mono, and Onyx templates.

Core Strategy:
  1. Whisper transcribes the audio clip → produces segments with text
  2. Genius provides the FULL song lyrics
  3. We concatenate Whisper text and find the best-matching WINDOW
     in the Genius lyrics using fuzzy matching
  4. Once the window is found, we do line-by-line alignment within it
  5. Repeated lines (choruses) are PRESERVED — not removed

This solves the fundamental problem: clips are a PORTION of the song,
so we need to find WHERE in the full lyrics the clip falls.
"""
import re
from rapidfuzz import fuzz


# ============================================================================
# PUBLIC API
# ============================================================================

def align_genius_to_whisper(whisper_segments, genius_text, segment_text_key="lyric_current"):
    """
    Align Genius lyrics to Whisper transcription segments.
    
    Works for any template - just specify which key holds the text:
      - Aurora: segment_text_key="lyric_current"
      - Mono/Onyx: segment_text_key="text"
    
    Args:
        whisper_segments: List of dicts with transcribed text
        genius_text: Full song lyrics string from Genius
        segment_text_key: Key name for the text field in segments
    
    Returns:
        Modified whisper_segments with Genius text replacing Whisper text
        where good matches are found. Timing data is preserved.
    """
    if not genius_text or not whisper_segments:
        return whisper_segments
    
    # Parse genius into lines (keep section headers for structure, filter for matching)
    genius_all_lines = []
    for ln in genius_text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        genius_all_lines.append(ln)
    
    # Separate lyric lines from section headers
    genius_lyric_lines = [
        ln for ln in genius_all_lines
        if not (ln.startswith("[") and ln.endswith("]"))
        and not (ln.startswith("(") and ln.endswith(")"))
    ]
    
    if not genius_lyric_lines:
        print("  ⚠ No lyric lines found in Genius text")
        return whisper_segments
    
    # Step 1: Find the best matching window in the full lyrics
    window_start = _find_lyrics_window(whisper_segments, genius_lyric_lines, segment_text_key)
    
    if window_start is None:
        print("  ⚠ Could not find matching window in Genius lyrics, using Whisper text")
        return whisper_segments
    
    # Step 2: Line-by-line alignment within the window
    whisper_segments = _align_within_window(
        whisper_segments, genius_lyric_lines, window_start, segment_text_key
    )
    
    # Step 3: Remove only Whisper artifacts (NOT legitimate repeats)
    whisper_segments = _remove_whisper_artifacts(whisper_segments, segment_text_key)
    
    return whisper_segments


# ============================================================================
# STEP 1: SLIDING WINDOW — Find where the clip falls in the full lyrics
# ============================================================================

def _find_lyrics_window(whisper_segments, genius_lines, segment_text_key):
    """
    Find the starting index in genius_lines where the Whisper transcription
    best matches, using a sliding window approach.
    
    Returns the index into genius_lines, or None if no good match found.
    """
    # Build a single block of Whisper text for matching
    whisper_block = " ".join(
        _clean_for_match(seg[segment_text_key])
        for seg in whisper_segments
        if seg.get(segment_text_key, "").strip()
    )
    
    if not whisper_block.strip():
        return None
    
    num_whisper_segments = len([s for s in whisper_segments if s.get(segment_text_key, "").strip()])
    
    # Window size: try matching blocks of roughly the same number of lines
    # as Whisper produced, with some padding
    window_size = max(num_whisper_segments, 3)
    padding = max(int(window_size * 0.5), 2)  # Allow some flexibility
    
    best_score = -1
    best_start = 0
    
    # Slide window across genius lines
    for start in range(len(genius_lines)):
        # Try different window sizes around the expected size
        for ws in range(max(1, window_size - padding), min(len(genius_lines) - start + 1, window_size + padding + 1)):
            end = start + ws
            if end > len(genius_lines):
                break
            
            genius_block = " ".join(
                _clean_for_match(genius_lines[i])
                for i in range(start, end)
            )
            
            # Use ratio for overall similarity
            score = fuzz.ratio(whisper_block, genius_block)
            
            # Also check token_sort_ratio for word-order independence
            sort_score = fuzz.token_sort_ratio(whisper_block, genius_block)
            
            # Combined score — weighted toward order-sensitive matching
            combined = (score * 0.7) + (sort_score * 0.3)
            
            if combined > best_score:
                best_score = combined
                best_start = start
    
    # Minimum threshold to accept the match
    if best_score < 40:
        print(f"  ⚠ Best window match score too low: {best_score:.1f}")
        return None
    
    print(f"  ✓ Found lyrics window at line {best_start + 1} (score: {best_score:.1f})")
    return best_start


# ============================================================================
# STEP 2: LINE-BY-LINE ALIGNMENT within the found window
# ============================================================================

def _align_within_window(whisper_segments, genius_lines, window_start, segment_text_key):
    """
    Once we know WHERE the clip falls in the full lyrics, do line-by-line
    alignment between Whisper segments and Genius lines.
    
    Key difference from old approach:
    - Allows the same Genius line to be used multiple times (for repeated choruses)
    - Uses a wider search window (not just 5 lines)
    - Falls back to Whisper text gracefully
    """
    min_score = 55  # Minimum fuzzy match score to accept
    
    genius_clean = [
        _clean_for_match(ln) for ln in genius_lines
    ]
    
    # Track position in genius lyrics - start from the found window
    genius_cursor = window_start
    
    # How far ahead to search from current position
    search_ahead = 8
    # How far back to search (for repeated sections like choruses)
    search_back = 15
    
    for i, seg in enumerate(whisper_segments):
        seg_text = seg.get(segment_text_key, "").strip()
        if not seg_text:
            continue
        
        whisper_clean = _clean_for_match(seg_text)
        if not whisper_clean:
            continue
        
        # Search for best match around current cursor position
        best_score = -1
        best_j = -1
        
        # Forward search (primary — most lyrics flow forward)
        forward_limit = min(len(genius_clean), genius_cursor + search_ahead)
        for j in range(genius_cursor, forward_limit):
            score = _match_score(whisper_clean, genius_clean[j])
            if score > best_score:
                best_score = score
                best_j = j
            # Early exit on excellent match
            if score >= 90:
                break
        
        # Backward search (for repeated sections like choruses)
        # Only if forward search didn't find a great match
        if best_score < 75:
            back_start = max(0, genius_cursor - search_back)
            for j in range(back_start, genius_cursor):
                score = _match_score(whisper_clean, genius_clean[j])
                # Need a higher threshold for backward matches to avoid false positives
                if score > best_score and score >= 70:
                    best_score = score
                    best_j = j
        
        # Apply the match
        if best_score >= min_score and best_j >= 0:
            seg[segment_text_key] = genius_lines[best_j]
            # Only advance cursor if we matched forward
            if best_j >= genius_cursor:
                genius_cursor = best_j + 1
        # else: keep Whisper text (it's the best we have)
    
    return whisper_segments


def _match_score(whisper_clean, genius_clean):
    """
    Calculate match score between a Whisper segment and a Genius line.
    Uses multiple fuzzy matching strategies and returns the best score.
    """
    # Standard ratio
    ratio = fuzz.ratio(whisper_clean, genius_clean)
    
    # Partial ratio (good when Whisper captures part of a line)
    partial = fuzz.partial_ratio(whisper_clean, genius_clean)
    
    # Token sort (word-order independent)
    token_sort = fuzz.token_sort_ratio(whisper_clean, genius_clean)
    
    # Weighted combination
    # Partial ratio is important because Whisper often captures partial lines
    return max(ratio, partial * 0.95, token_sort * 0.9)


# ============================================================================
# STEP 3: ARTIFACT REMOVAL (NOT blanket duplicate removal)
# ============================================================================

def _remove_whisper_artifacts(segments, segment_text_key):
    """
    Remove only clear Whisper transcription artifacts:
    - Identical consecutive lines with very small time gaps (<0.5s)
      These are Whisper stutters, not intentional repeats
    
    DOES NOT remove:
    - Chorus repeats (larger time gaps = intentional)
    - Any non-consecutive duplicates
    """
    if not segments or len(segments) < 2:
        return segments
    
    removed_count = 0
    
    for i in range(len(segments) - 1, 0, -1):  # Iterate backwards
        current_text = segments[i].get(segment_text_key, "").strip()
        prev_text = segments[i - 1].get(segment_text_key, "").strip()
        
        if not current_text or not prev_text:
            continue
        
        current_clean = _clean_for_match(current_text)
        prev_clean = _clean_for_match(prev_text)
        
        if current_clean == prev_clean:
            # Check time gap — only remove if it's a stutter (<0.5s gap)
            current_time = segments[i].get("t", segments[i].get("time", 0))
            prev_time = segments[i - 1].get("t", segments[i - 1].get("time", 0))
            prev_end = segments[i - 1].get("end_time", prev_time + 1)
            
            gap = current_time - prev_end
            
            if gap < 0.5:
                # Whisper stutter — remove the duplicate
                if segment_text_key == "lyric_current":
                    # Aurora format: clear the text but keep the segment
                    segments[i][segment_text_key] = ""
                else:
                    # Mono/Onyx: remove the entire marker
                    segments.pop(i)
                removed_count += 1
    
    if removed_count > 0:
        print(f"   Removed {removed_count} Whisper artifacts (stutters)")
    
    return segments


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def _clean_for_match(text):
    """Normalize text for fuzzy matching — remove punctuation, lowercase, collapse spaces"""
    if not text:
        return ""
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text
