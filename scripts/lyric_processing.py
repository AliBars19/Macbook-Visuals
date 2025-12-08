import re
from rapidfuzz import fuzz
import os 
from stable_whisper import load_model
import json

from scripts.genius_processing import fetch_genius_lyrics

def extract_genius_section(whisper_segments, genius_text):


    genius_lines = [
        ln.strip() for ln in genius_text.splitlines()
        if ln.strip() and not (ln.startswith("[") and ln.endswith("]"))
    ]

    if len(genius_lines) == 0:
        return []

    genius_clean = [
        re.sub(r"[^a-zA-Z0-9 ]+", " ", ln).lower()
        for ln in genius_lines
    ]

    whisper_clean = [
        re.sub(r"[^a-zA-Z0-9 ]+", " ", seg["lyric_current"]).lower()
        for seg in whisper_segments
    ]

    aligned = []
    last_idx = 0

    MIN_SCORE = 65

    for w in whisper_clean:
        if last_idx >= len(genius_clean):
            break

        best_score = -1
        best_j = last_idx

        for j in range(last_idx, len(genius_clean)):
            score = fuzz.partial_ratio(w, genius_clean[j])

            if score > best_score:
                best_score = score
                best_j = j

            if best_score >= 90:
                break

        if best_score < MIN_SCORE:
            break

        aligned.append(genius_lines[best_j])
        last_idx = best_j + 1 
    return aligned




def wrap_two_lines(text, max_chars=25):
    text = text.strip()

    if len(text) <= max_chars:
        return text

    cut = text.rfind(" ", 0, max_chars)
    if cut == -1:
        cut = max_chars

    first = text[:cut].rstrip()
    rest  = text[cut:].lstrip()

    return first + " \\r " + rest



def transcribe_audio(job_folder, song_title=None):
    print("\n Transcribing audio with stable-ts...")

    audio_path = os.path.join(job_folder, "audio_trimmed.wav")
    if not os.path.exists(audio_path):
        print("[ERROR] audio_trimmed.wav missing")
        return None

    # --- Stable Whisper ---
    safe_dir = os.path.join(os.getcwd(), "whisper_models")
    os.makedirs(safe_dir, exist_ok=True)

    model = load_model(
        "medium",
        download_root=safe_dir,
        in_memory=False
    )
    result = model.transcribe(
        audio_path,
        vad=True,                 
        suppress_silence=False,   
        regroup=True,             
        temperature=0,
    )

    if not result.segments:
        print("Whisper returned empty output — retrying with fallback params...")

        result = model.transcribe(
            audio_path,
            vad=False,
            suppress_silence=False,
            regroup=True,
            temperature=0.5,       
        )


    segments = result.segments
    final_list = [{
        "t": float(seg.start),
        "lyric_prev": "",
        "lyric_current": seg.text.strip(),
        "lyric_next1": "",
        "lyric_next2": ""
    } for seg in segments]

    genius_text = None
    if song_title:
        print("Fetching Genius lyrics...")
        genius_text = fetch_genius_lyrics(song_title)
        if genius_text:
            open(os.path.join(job_folder, "genius_lyrics.txt"), "w", encoding="utf-8").write(genius_text)

    if genius_text:
        print("Aligning Genius lyrics to Whisper timestamps...")
        aligned = extract_genius_section(final_list, genius_text)

        for i in range(min(len(final_list), len(aligned))):
            final_list[i]["lyric_current"] = aligned[i]

        
    def wrap_chunk(text, limit=25):
        text = text.strip()

        # If text already contains \r, do NOT wrap again
        if "\\r" in text:
            return text

        if len(text) <= limit:
            return text

        # Find a space near the limit to split once
        cut = text.rfind(" ", 0, limit)
        if cut == -1:
            cut = limit

        first = text[:cut].strip()
        rest  = text[cut:].strip()

        return f"{first} \\r {rest}"



    for seg in final_list:
        seg["lyric_current"] = wrap_chunk(seg["lyric_current"], 25)

    # --- Save ---
    lyrics_path = os.path.join(job_folder, "lyrics.txt")
    with open(lyrics_path, "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=4, ensure_ascii=False)

    print(f" Transcription complete: {len(final_list)} lines saved.")
    return lyrics_path



def align_genius_to_whisper(whisper_segments, genius_lines):
    

    if not whisper_segments or not genius_lines:
        return whisper_segments

    genius_lines = [ln for ln in genius_lines if ln.strip()]
    g = len(genius_lines)
    w = len(whisper_segments)

    if g == 0:
        return whisper_segments

    if g > w:
        remaining_g = g
        idx = 0
        remaining_w = w

        for i in range(w):
            group_size = round(remaining_g / remaining_w)
            group_size = max(1, group_size)

            group = genius_lines[idx: idx + group_size]
            idx += group_size

            remaining_g = g - idx
            remaining_w = w - i - 1

            whisper_segments[i]["lyric_current"] = " ".join(group)

        return whisper_segments

    for i, line in enumerate(genius_lines):
        whisper_segments[i]["lyric_current"] = line

    return whisper_segments