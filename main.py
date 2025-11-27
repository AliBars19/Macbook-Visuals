import os
import json

import yt_dlp # for audio extraction
import ffmpeg
from pydub import AudioSegment

from html import unescape
import re

import requests # for image extraction
from PIL import Image
from io import BytesIO

from colorthief import ColorThief #For image colour extraction
import matplotlib.pyplot as plt

import librosa

GENIUS_API_TOKEN = "1rnjcBnyL8eAARorEsLIG-JxO8JtsvAfygrPhd7uPxcXxMYK0NaNlL_i-jCsW0zt"
GENIUS_BASE_URL = "https://api.genius.com"

#------------------------------------------ JOB PROGRESS CHECKER
def check_job_progress(job_folder):

    stages = {
        "audio_downloaded": os.path.exists(os.path.join(job_folder, "audio_source.mp3")),
        "audio_trimmed": os.path.exists(os.path.join(job_folder, "audio_trimmed.wav")),
        "lyrics_transcribed": os.path.exists(os.path.join(job_folder, "lyrics.txt")),
        "image_downloaded": os.path.exists(os.path.join(job_folder, "cover.png")),
        "job_json": os.path.exists(os.path.join(job_folder, "job_data.json")),
        "beats_generated": os.path.exists(os.path.join(job_folder, "beats.json"))
    }

    # If job_data.json exists, read it to reuse info
    job_data = {}
    json_path = os.path.join(job_folder, "job_data.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                job_data = json.load(f)
        except Exception:
            pass

    return stages, job_data

#------------------------------------------- EXTRACTING AUDIO

def download_audio(url,job_folder):
    output_path = os.path.join(job_folder, 'audio_source.%(ext)s')
 
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path,
        'postprocessors': [{  # Extract audio using ffmpeg
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }]
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    mp3_path = os.path.join(job_folder, 'audio_source.mp3')
    return mp3_path # return path of mp3

#---------------------------------------- TRIMMING AUDIO


 
def trimming_audio(job_folder,start_time, end_time):

    def mmss_to_millisecondsaudio(time_str):
        m, s = map(int, time_str.split(':'))
        return ((m * 60) + s) * 1000
    
    audio_import = os.path.join(job_folder,'audio_source.mp3')# Load audio file
    song = AudioSegment.from_file(audio_import, format="mp3")
    
    start_ms = mmss_to_millisecondsaudio(start_time)# Convert to milliseconds
    end_ms = mmss_to_millisecondsaudio(end_time)

    if start_ms < end_ms:
        clip = song[start_ms:end_ms]# Slice the audio
    else:
        print("start time cannot be bigger than end time")
        return None
    
    export_path = os.path.join(job_folder, "audio_trimmed.wav")# Export new audio clip
    clip.export(export_path, format="wav")
    print("New Audio file is created and saved")
    return export_path


#---------------------------------------- DOWNLOADING PNG

def image_download(job_folder,url):
    image_save_path = os.path.join(job_folder,'cover.png')
    response = requests.get(url)
    print(response)
    if response.status_code == 200:
        img = Image.open(BytesIO(response.content))
        img.save(image_save_path)
    else:
        print("BAD IMAGE LINK")

    return image_save_path    

#--------------------------------------- EXTRACTING COLORS FROM PNG

def image_extraction(job_folder):
    image_import_path = os.path.join(job_folder,'cover.png')

    extractionimg = ColorThief(image_import_path) # setup image for extraction

    palette = extractionimg.get_palette(color_count=4) # getting the 4 most dominant colours
    colorshex = []

    for r,g,b in palette: 
        hexvalue = '#' + format(r,'02x') + format(g,'02x') + format(b,'02x')# convert rgb values into hex
        colorshex.append(hexvalue)

    return colorshex
#--------------------------------------

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

from difflib import SequenceMatcher

def align_genius_to_whisper(whisper_segments, genius_text, max_chars=25):
    """
    Aligns clean Genius lyric lines onto Whisper time segments.
    Keeps Whisper timing but replaces segmented text with Genius lines.
    """
    import re
    from difflib import SequenceMatcher

    if not whisper_segments or not genius_text:
        return whisper_segments

    # ---------------------------------------------------
    # 1) Clean and split Genius into usable lyric lines
    # ---------------------------------------------------
    genius_lines = [
        line.strip()
        for line in genius_text.splitlines()
        if line.strip()
    ]

    # Normalization helper
    def clean(x):
        x = x.lower()
        x = re.sub(r"\[.*?\]", "", x)          # remove [Music], [Intro], etc
        x = re.sub(r"\(.*?\)", "", x)          # remove (yeah), (laughs), etc
        x = re.sub(r"[^a-z0-9]+", " ", x)      # keep letters/numbers
        x = re.sub(r"\s+", " ", x)
        return x.strip()


    # Normalize the search lines
    genius_clean = [clean(l) for l in genius_lines]

    # ---------------------------------------------------
    # 2) Prepare Whisper segments (normalized)
    # ---------------------------------------------------
    whisper_clean = [
        clean(seg["lyric_current"]) for seg in whisper_segments
    ]

    used = set()

    # ---------------------------------------------------
    # 3) Scoring function with length penalty
    # ---------------------------------------------------
    def score_pair(a, b):
        """
        a = genius line
        b = whisper text
        """
        if not a or not b:
            return 0.0

        base = SequenceMatcher(None, a, b).ratio()

        # length similarity penalty
        len_ratio = min(len(a), len(b)) / max(len(a), len(b))

        return base * len_ratio

    # ---------------------------------------------------
    # 4) Assign each Genius line to best Whisper segment
    # ---------------------------------------------------
    for i, g_line in enumerate(genius_clean):

        best_idx = -1
        best_score = 0.0

        for j, w_line in enumerate(whisper_clean):
            if j in used:
                continue

            s = score_pair(g_line, w_line)

            if s > best_score:
                best_idx = j
                best_score = s

        # Tuneable threshold — 0.07 works extremely well
        if best_score >= 0.045 and best_idx >= 0:
            whisper_segments[best_idx]["lyric_current"] = genius_lines[i]
            used.add(best_idx)
        else:
            print(f"[WARN] Genius line not matched: {genius_lines[i]}")

    return whisper_segments

#-------------------------------------- Taking in lyrics & Transcribe
import whisper


def transcribe_audio(job_folder, song_title=None):

    print("\n Transcribing audio with Whisper...")

    audio_path = os.path.join(job_folder, "audio_trimmed.wav")

    # ---------------------------
    # Load Whisper
    # ---------------------------
    model = whisper.load_model("medium")

    result = model.transcribe(
        audio_path,
        word_timestamps=False,
        condition_on_previous_text=False
    )

    segments = result.get("segments", [])
    final_list = []

    # ---------------------------
    # STEP 1 — KEEP WHISPER SEGMENTS INTACT
    # ---------------------------
    for seg in segments:
        final_list.append({
            "t": float(seg["start"]),
            "lyric_prev": "",
            "lyric_current": seg["text"].strip(),
            "lyric_next1": "",
            "lyric_next2": ""
        })

    # ---------------------------
    # STEP 2 — Fetch Genius lyrics
    # ---------------------------
    genius_text = None

    if song_title and GENIUS_API_TOKEN:
        print(" Fetching Genius lyrics for:", song_title)
        genius_text = fetch_genius_lyrics(song_title)

        if genius_text:
            # Save raw Genius lyrics
            genius_path = os.path.join(job_folder, "genius_lyrics.txt")
            with open(genius_path, "w", encoding="utf-8") as gf:
                gf.write(genius_text)
            print(" Genius lyrics saved to", genius_path)
        else:
            print(" Genius failed — keeping Whisper lyrics")

    # ---------------------------
    # STEP 3 — Align Genius → Whisper
    # ---------------------------
    if genius_text:
        final_list = align_genius_to_whisper(final_list, genius_text, max_chars=25)

    # ---------------------------
    # STEP 4 — Chunk all final lines to max 25 chars
    # ---------------------------
    def wrap_chunk(text, limit=25):
        """
        Splits long lines into 1–2 lines separated with "MVAE".
        """
        words = text.split()
        out, buf = [], ""

        for w in words:
            # If adding next word exceeds limit, create a new line
            if len((buf + " " + w).strip()) > limit:
                if buf:
                    out.append(buf.strip())
                buf = w
            else:
                buf = (buf + " " + w).strip()

        if buf:
            out.append(buf)

        return "MVAE".join(out)

    for seg in final_list:
        seg["lyric_current"] = wrap_chunk(seg["lyric_current"], limit=25)

    # ---------------------------
    # STEP 5 — Save JSON
    # ---------------------------
    lyrics_path = os.path.join(job_folder, "lyrics.txt")

    with open(lyrics_path, "w", encoding="utf-8") as f:
        text = json.dumps(final_list, indent=4, ensure_ascii=False)
        text = text.replace("\\\\n", "\\n")
        f.write(text)

    print(f" Transcription complete: {len(final_list)} lines saved to {lyrics_path}")
    return lyrics_path

def detect_beats(job_folder):

    audio_path = os.path.join(job_folder, "audio_trimmed.wav")
    
    y, sr = librosa.load(audio_path, sr=None)

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    
    beats_list = [float(t) for t in beat_times]

    try:
        tempo_val = float(tempo)
    except:
        tempo_val = float(tempo[0]) if hasattr(tempo, "__len__") else 0.0

    print(f"  Detected {len(beats_list)} beats (tempo ≈ {tempo_val:.1f} BPM).")


    return beats_list

#-------------------------MAIN----------------------------------------

def batch_generate_jobs():
    base_jobs = 12  # total jobs to create

    for i in range(1, base_jobs + 1):
        job_id = i
        job_folder = f"jobs/job_{job_id:03}"
        os.makedirs(job_folder, exist_ok=True)
        print(f"\n--- Checking Job {job_id:03} ---")

        stages, job_data = check_job_progress(job_folder)

        # Reuse previously stored song title if it exists
        song_title = job_data.get("song_title") if job_data else None

        #Audio download
        if not stages["audio_downloaded"]:
            mp3url = input(f"[Job {job_id}] Enter AUDIO URL: ")
            audio_path = download_audio(mp3url, job_folder)
        else:
            audio_path = os.path.join(job_folder, "audio_source.mp3")
            print(f"✓ Audio already downloaded for job {job_id:03}")
        
        #Song title
        if not song_title:
            song_title = input(f"[Job {job_id}] Enter SONG TITLE (Artist - Song): ")
    
        #Audio trimming
        if not stages["audio_trimmed"]:
            start_time = input(f"[Job {job_id}] Enter start time (MM:SS): ")
            end_time = input(f"[Job {job_id}] Enter end time (MM:SS): ")
            clipped_path = trimming_audio(job_folder, start_time, end_time)
        else:
            clipped_path = os.path.join(job_folder, "audio_trimmed.wav")
            print(f"✓ Audio already trimmed for job {job_id:03}")

        beats_path = os.path.join(job_folder, "beats.json")
        if not stages["beats_generated"]:
            beats = detect_beats(job_folder)
            with open(beats_path, "w", encoding="utf-8") as f:
                json.dump(beats, f, indent=4)
        else:
            with open(beats_path, "r", encoding="utf-8") as f:
                beats = json.load(f)
            print(f"✓ Beats already detected for job {job_id:03}")

        #Lyrics
        if not stages["lyrics_transcribed"]:
            lyrics_path = transcribe_audio(job_folder, song_title=song_title)
        else:
            lyrics_path = os.path.join(job_folder, "lyrics.txt")
            print(f"✓ Lyrics already transcribed for job {job_id:03}")

        #Image
        if not stages["image_downloaded"]:
            imgurl = input(f"[Job {job_id}] Enter IMAGE URL: ")
            image_path = image_download(job_folder, imgurl)
        else:
            image_path = os.path.join(job_folder, "cover.png")
            print(f"✓ Image already downloaded for job {job_id:03}")

        #Colors
        colors = image_extraction(job_folder)

        
        # Save or update job data
        job_data = {
            "job_id": job_id,
            "audio_source": audio_path.replace("\\", "/"),
            "audio_trimmed": clipped_path.replace("\\", "/"),
            "cover_image": image_path.replace("\\", "/"),
            "colors": colors,
            "lyrics_file": lyrics_path.replace("\\", "/"),
            "job_folder": job_folder.replace("\\", "/"),
            "beats": beats,
            "song_title": song_title
        }

        json_path = os.path.join(job_folder, "job_data.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(job_data, f, indent=4)

        print(f" Job {job_id:03} is ready or up to date.")
    print("\n" + "\n" + "\n" + "\n" + "All Jobs Complete, Run JSX script in AE")

if __name__ == "__main__":
    batch_generate_jobs()
