import re
from rapidfuzz import fuzz
import os 
from stable_whisper import load_model
import json

from scripts.genius_processing import fetch_genius_lyrics

def extract_genius_section(whisper_segments, genius_text):

    # full whisper text
    whisper_text = " ".join([seg["lyric_current"] for seg in whisper_segments])
    whisper_text_clean = re.sub(r"[^a-zA-Z0-9 ]+", " ", whisper_text).lower()

    genius_lines = [ln.strip() for ln in genius_text.splitlines() if ln.strip()]
    genius_clean = [re.sub(r"[^a-zA-Z0-9 ]+", " ", ln).lower() for ln in genius_lines]

    best_score = -1
    best_start = 0
    best_end = 0

    # try windows from 3 to 20 lines
    for start in range(len(genius_clean)):
        buf = ""
        for end in range(start, min(start + 20, len(genius_clean))):
            buf = (buf + " " + genius_clean[end]).strip()
            score = fuzz.partial_ratio(whisper_text_clean, buf)

            if score > best_score:
                best_score = score
                best_start = start
                best_end = end

    print(f"[SECTION] Best matching block: lines {best_start}–{best_end}, score={best_score}")

    # return EXACT subsection
    return genius_lines[best_start:best_end + 1]


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
        "large-v3",
        download_root=safe_dir,
        in_memory=False
    )
    result = model.transcribe(
        audio_path,
        vad=True,
        regroup=False,
        suppress_silence=True,
        temperature=0,
    )

    segments = result.segments
    final_list = [{
        "t": float(seg.start),
        "lyric_prev": "",
        "lyric_current": seg.text.strip(),
        "lyric_next1": "",
        "lyric_next2": ""
    } for seg in segments]

    # --- Fetch Genius ---
    genius_text = None
    if song_title:
        print("Fetching Genius lyrics...")
        genius_text = fetch_genius_lyrics(song_title)
        if genius_text:
            open(os.path.join(job_folder, "genius_lyrics.txt"), "w", encoding="utf-8").write(genius_text)

    # --- Region selection ---
    if genius_text:
        genius_section = extract_genius_section(final_list, genius_text)
        # Now replace whisper text with EXACT genius lines
        for i, line in enumerate(genius_section):
            if i < len(final_list):
                final_list[i]["lyric_current"] = line
        

    # --- AE soft wrap with literal "\r" ---
    def wrap_chunk(text, limit=25):
        words = text.split()
        out = []
        buf = ""
        for w in words:
            candidate = (buf + " " + w).strip()
            if len(candidate) > limit:
                if buf:
                    out.append(buf.strip())
                buf = w
            else:
                buf = candidate
        if buf:
            out.append(buf.strip())
        return " \\r ".join(out)

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

    # ---- CASE A: More Genius lines → merge into fewer segments ----
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

    # ---- CASE B: Fewer or equal Genius lines → assign 1-to-1 ----
    for i, line in enumerate(genius_lines):
        whisper_segments[i]["lyric_current"] = line

    return whisper_segments