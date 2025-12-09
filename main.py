import os
import json

from scripts.audio_processing import (
    download_audio,
    trimming_audio,
    detect_beats
)
from scripts.lyric_processing import transcribe_audio

from scripts.image_processing import (
    image_download,
    image_extraction
)

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
