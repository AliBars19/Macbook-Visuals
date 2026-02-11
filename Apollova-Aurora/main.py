#!/usr/bin/env python3
"""
Music Video Automation - Apollova Aurora
Full visual effects lyric videos with color extraction and beat sync
"""
import os
import sys
import json
import shutil
from pathlib import Path
from rich.console import Console

# Ensure scripts directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.config import Config
from scripts.audio_processing import download_audio, trim_audio, detect_beats
from scripts.image_processing import download_image, extract_colors
from scripts.lyric_processing import transcribe_audio
from scripts.song_database import SongDatabase

console = Console()

# Initialize song database with shared path
SHARED_DB = Path(__file__).parent.parent / "database" / "songs.db"
song_db = SongDatabase(db_path=str(SHARED_DB))


def check_job_progress(job_folder):
    """Check which stages are already complete for a job"""
    stages = {
        "audio_downloaded": os.path.exists(os.path.join(job_folder, "audio_source.mp3")),
        "audio_trimmed": os.path.exists(os.path.join(job_folder, "audio_trimmed.wav")),
        "beats_generated": os.path.exists(os.path.join(job_folder, "beats.json")),
        "lyrics_transcribed": os.path.exists(os.path.join(job_folder, "lyrics.txt")),
        "image_downloaded": os.path.exists(os.path.join(job_folder, "cover.png")),
        "job_complete": os.path.exists(os.path.join(job_folder, "job_data.json"))
    }
    
    job_data = {}
    json_path = os.path.join(job_folder, "job_data.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                job_data = json.load(f)
        except:
            pass
    
    return stages, job_data


def check_existing_jobs():
    """Check if jobs folder already has completed jobs and offer to delete"""
    jobs_dir = os.path.join(os.path.dirname(__file__), Config.JOBS_DIR)
    
    if not os.path.exists(jobs_dir):
        return True
    
    existing_jobs = []
    for i in range(1, 13):
        job_folder = os.path.join(jobs_dir, f"job_{i:03}")
        job_data_path = os.path.join(job_folder, "job_data.json")
        if os.path.exists(job_data_path):
            existing_jobs.append(i)
    
    if not existing_jobs:
        return True
    
    console.print(f"[yellow]⚠️  Found {len(existing_jobs)} existing completed jobs in {jobs_dir}[/yellow]")
    console.print(f"[dim]   Jobs: {', '.join(str(j) for j in existing_jobs)}[/dim]")
    
    response = input("\nDelete existing jobs and start fresh? (y/N): ").strip().lower()
    
    if response == 'y':
        for i in range(1, 13):
            job_folder = os.path.join(jobs_dir, f"job_{i:03}")
            if os.path.exists(job_folder):
                try:
                    shutil.rmtree(job_folder)
                    console.print(f"[dim]   Deleted job_{i:03}[/dim]")
                except Exception as e:
                    console.print(f"[red]   Failed to delete job_{i:03}: {e}[/red]")
        console.print("[green]✓ Cleared existing jobs[/green]\n")
        return True
    else:
        console.print("[yellow]Keeping existing jobs. Will skip completed ones.[/yellow]\n")
        return True


def process_single_job(job_id):
    """Process a single job with database caching"""
    job_folder = os.path.join(os.path.dirname(__file__), Config.JOBS_DIR, f"job_{job_id:03}")
    os.makedirs(job_folder, exist_ok=True)
    
    console.print(f"\n[bold cyan]━━━ Aurora Job {job_id:03} ━━━[/bold cyan]")
    
    stages, job_data = check_job_progress(job_folder)
    
    # Check if job is already complete
    if stages["job_complete"] and all([
        stages["audio_downloaded"],
        stages["audio_trimmed"],
        stages["beats_generated"],
        stages["lyrics_transcribed"],
        stages["image_downloaded"]
    ]):
        song_title = job_data.get("song_title", "Unknown")
        console.print(f"[green]✓ Job {job_id:03} already complete: {song_title}[/green]")
        return True
    
    # Get Song Title
    song_title = job_data.get("song_title")
    if not song_title:
        song_title = input(f"[Job {job_id}] Song Title (Artist - Song): ").strip()
    else:
        console.print(f"[dim]Song: {song_title}[/dim]")
    
    # Check Database for Cached Parameters
    cached_song = song_db.get_song(song_title)
    cached_lyrics = None
    cached_beats = None
    cached_colors = None
    cached_image_url = None
    
    if cached_song:
        console.print(f"[green]✓ Found '{song_title}' in database![/green]")
        audio_url = cached_song["youtube_url"]
        start_time = cached_song["start_time"]
        end_time = cached_song["end_time"]
        cached_lyrics = cached_song["transcribed_lyrics"]
        cached_beats = cached_song["beats"]
        cached_colors = cached_song["colors"]
        cached_image_url = cached_song["genius_image_url"]
        
        console.print(f"[dim]  URL: {audio_url}[/dim]")
        console.print(f"[dim]  Time: {start_time} → {end_time}[/dim]")
        if cached_lyrics:
            console.print(f"[dim]  Cached lyrics: {len(cached_lyrics)} segments ⚡[/dim]")
    else:
        console.print(f"[yellow]'{song_title}' not in database. Creating new entry...[/yellow]")
    
    # === Audio Download ===
    if not stages["audio_downloaded"]:
        if cached_song:
            audio_url = cached_song["youtube_url"]
            console.print(f"[dim]Using cached URL[/dim]")
        else:
            audio_url = input(f"[Job {job_id}] Audio URL: ").strip()
        
        console.print("[cyan]Downloading audio...[/cyan]")
        try:
            audio_path = download_audio(audio_url, job_folder)
        except Exception as e:
            console.print(f"[red]Failed to download audio: {e}[/red]")
            return False
    else:
        audio_path = os.path.join(job_folder, "audio_source.mp3")
        console.print("✓ Audio already downloaded")
        if cached_song:
            audio_url = cached_song["youtube_url"]
        elif "youtube_url" in job_data:
            audio_url = job_data.get("youtube_url", "unknown")
        else:
            audio_url = "unknown"
    
    # === Audio Trimming ===
    if not stages["audio_trimmed"]:
        if cached_song:
            start_time = cached_song["start_time"]
            end_time = cached_song["end_time"]
            console.print(f"[dim]Using cached timing: {start_time} → {end_time}[/dim]")
        else:
            start_time = input(f"[Job {job_id}] Start time (MM:SS or press Enter for 00:00): ").strip()
            if not start_time:
                start_time = "00:00"
            
            if start_time == "00:00":
                end_time = "01:01"
                console.print(f"[dim]Auto-set end time to {end_time}[/dim]")
            else:
                end_time = input(f"[Job {job_id}] End time (MM:SS): ").strip()
        
        console.print("[cyan]Trimming audio...[/cyan]")
        try:
            trimmed_path = trim_audio(job_folder, start_time, end_time)
        except Exception as e:
            console.print(f"[red]Failed to trim audio: {e}[/red]")
            return False
    else:
        trimmed_path = os.path.join(job_folder, "audio_trimmed.wav")
        console.print("✓ Audio already trimmed")
        if cached_song:
            start_time = cached_song["start_time"]
            end_time = cached_song["end_time"]
        else:
            start_time = job_data.get("start_time", "00:00")
            end_time = job_data.get("end_time", "01:01")
    
    # === Beat Detection ===
    beats_path = os.path.join(job_folder, "beats.json")
    if cached_beats:
        console.print("[green]✓ Using cached beat data[/green]")
        beats = cached_beats
        with open(beats_path, "w", encoding="utf-8") as f:
            json.dump(beats, f, indent=4)
    elif not stages["beats_generated"]:
        console.print("[cyan]Detecting beats...[/cyan]")
        beats = detect_beats(job_folder)
        with open(beats_path, "w", encoding="utf-8") as f:
            json.dump(beats, f, indent=4)
    else:
        with open(beats_path, "r", encoding="utf-8") as f:
            beats = json.load(f)
        console.print("✓ Beats already detected")
    
    # === Lyrics Transcription ===
    if cached_lyrics:
        console.print(f"[green]✓ Using cached transcription ({len(cached_lyrics)} segments) ⚡[/green]")
        lyrics_path = os.path.join(job_folder, "lyrics.txt")
        transcribed_lyrics = cached_lyrics
        with open(lyrics_path, "w", encoding="utf-8") as f:
            json.dump(cached_lyrics, f, indent=4, ensure_ascii=False)
    elif not stages["lyrics_transcribed"]:
        console.print("[cyan]Transcribing lyrics (this will be cached)...[/cyan]")
        try:
            lyrics_path = transcribe_audio(job_folder, song_title)
            with open(lyrics_path, "r", encoding="utf-8") as f:
                transcribed_lyrics = json.load(f)
        except Exception as e:
            console.print(f"[yellow]Warning: Transcription failed: {e}[/yellow]")
            lyrics_path = os.path.join(job_folder, "lyrics.txt")
            transcribed_lyrics = []
            with open(lyrics_path, "w", encoding="utf-8") as f:
                json.dump([], f)
    else:
        lyrics_path = os.path.join(job_folder, "lyrics.txt")
        with open(lyrics_path, "r", encoding="utf-8") as f:
            transcribed_lyrics = json.load(f)
        console.print("✓ Lyrics already transcribed")
    
    # === Image Download ===
    genius_image_url = None
    
    if cached_image_url and cached_image_url != "fetched_from_genius":
        console.print("[green]✓ Using cached image URL[/green]")
        if not stages["image_downloaded"]:
            console.print("[cyan]Downloading image...[/cyan]")
            try:
                image_path = download_image(job_folder, cached_image_url)
                genius_image_url = cached_image_url
            except Exception as e:
                console.print(f"[yellow]Cached image failed, trying Genius...[/yellow]")
                cached_image_url = None
    
    if (not cached_image_url or cached_image_url == "fetched_from_genius") and not stages["image_downloaded"]:
        console.print("[cyan]Fetching cover image from Genius...[/cyan]")
        try:
            from scripts.genius_processing import fetch_genius_image_with_url
            image_path, genius_image_url = fetch_genius_image_with_url(song_title, job_folder)
            
            if not image_path:
                console.print("[yellow]Couldn't auto-fetch image from Genius[/yellow]")
                image_url = input(f"[Job {job_id}] Enter Cover Image URL manually: ").strip()
                console.print("[cyan]Downloading image...[/cyan]")
                image_path = download_image(job_folder, image_url)
                genius_image_url = image_url
        except Exception as e:
            console.print(f"[yellow]Auto-fetch failed: {e}[/yellow]")
            image_url = input(f"[Job {job_id}] Enter Cover Image URL manually: ").strip()
            console.print("[cyan]Downloading image...[/cyan]")
            try:
                image_path = download_image(job_folder, image_url)
                genius_image_url = image_url
            except Exception as e2:
                console.print(f"[red]Failed to download image: {e2}[/red]")
                return False
    elif stages["image_downloaded"]:
        image_path = os.path.join(job_folder, "cover.png")
        genius_image_url = cached_image_url if cached_image_url and cached_image_url != "fetched_from_genius" else None
        console.print("✓ Image already downloaded")
    
    # === Color Extraction ===
    if cached_colors:
        console.print(f"[green]✓ Using cached colors: {', '.join(cached_colors)}[/green]")
        colors = cached_colors
    else:
        console.print("[cyan]Extracting colors...[/cyan]")
        colors = extract_colors(job_folder)
    
    # === Save to Database ===
    if not cached_song:
        console.print(f"[cyan]💾 Saving '{song_title}' to database...[/cyan]")
        song_db.add_song(
            song_title=song_title,
            youtube_url=audio_url,
            start_time=start_time,
            end_time=end_time,
            genius_image_url=genius_image_url,
            transcribed_lyrics=transcribed_lyrics if 'transcribed_lyrics' in locals() else None,
            colors=colors,
            beats=beats
        )
        console.print("[green]✓ Song saved to database for future use[/green]")
    else:
        song_db.mark_song_used(song_title)
        console.print(f"[green]✓ Marked '{song_title}' as used in database[/green]")
        
        # Update any new data that wasn't cached
        song_db.update_colors_and_beats(song_title, colors, beats)
        if 'transcribed_lyrics' in locals() and transcribed_lyrics:
            song_db.update_lyrics(song_title, transcribed_lyrics)
        # Update image URL if we fetched a new one
        if genius_image_url and genius_image_url != "fetched_from_genius":
            song_db.update_image_url(song_title, genius_image_url)
    
    # === Save Job Data ===
    job_data = {
        "job_id": job_id,
        "audio_source": os.path.abspath(audio_path).replace("\\", "/"),
        "audio_trimmed": os.path.abspath(trimmed_path).replace("\\", "/"),
        "cover_image": os.path.abspath(image_path).replace("\\", "/"),
        "colors": colors,
        "lyrics_file": os.path.abspath(lyrics_path).replace("\\", "/"),
        "beats": beats,
        "job_folder": os.path.abspath(job_folder).replace("\\", "/"),
        "song_title": song_title,
        "youtube_url": audio_url,
        "start_time": start_time,
        "end_time": end_time
    }
    
    json_path = os.path.join(job_folder, "job_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(job_data, f, indent=4)
    
    console.print(f"[green]✓ Aurora Job {job_id:03} complete[/green]")
    return True


def batch_generate_jobs():
    """Generate all jobs with database caching"""
    console.print("\n[bold cyan]🎬 Apollova Aurora - Music Video Automation[/bold cyan]\n")

    # Check for existing jobs first
    check_existing_jobs()

    # Validate config
    Config.validate()

    # Create jobs directory
    jobs_dir = os.path.join(os.path.dirname(__file__), Config.JOBS_DIR)
    os.makedirs(jobs_dir, exist_ok=True)
    
    # Show database stats
    stats = song_db.get_stats()
    if stats["total_songs"] > 0:
        console.print(f"[dim]📊 Database: {stats['total_songs']} songs, "
                     f"{stats['cached_lyrics']} with cached lyrics[/dim]\n")
    
    # Process each job
    total_jobs = Config.TOTAL_JOBS
    
    for job_id in range(1, total_jobs + 1):
        success = process_single_job(job_id)
        
        if not success:
            console.print(f"\n[yellow]⚠️  Job {job_id} had errors, continuing...[/yellow]")
    
    console.print("\n[bold green]✅ All Aurora jobs processed![/bold green]")
    
    # Show updated stats
    stats = song_db.get_stats()
    console.print(f"\n[cyan]📊 Database now has:[/cyan]")
    console.print(f"   {stats['total_songs']} songs")
    console.print(f"   {stats['cached_lyrics']} with cached lyrics")
    console.print(f"   {stats['total_uses']} total uses")
    
    console.print("\n[cyan]Next step:[/cyan] Run the After Effects JSX script")
    console.print("[dim]File → Scripts → Run Script File... → scripts/JSX/automateMV_batch.jsx[/dim]\n")


if __name__ == "__main__":
    try:
        batch_generate_jobs()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]❌ Fatal error: {e}[/red]")
        raise