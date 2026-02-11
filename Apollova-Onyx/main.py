#!/usr/bin/env python3
"""
Apollova Onyx - Music Video Automation
Hybrid template: Word-by-word lyrics (left) + Spinning disc with album art (right)

NOTE: Onyx shares the nova_lyrics column with Mono for word-level transcription caching.
"""
import os
import json
from pathlib import Path
from rich.console import Console

from scripts.config import Config
from scripts.audio_processing import download_audio, trim_audio
from scripts.image_processing import download_image, extract_colors
from scripts.lyric_processing_onyx import transcribe_audio_onyx
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
        "onyx_data_created": os.path.exists(os.path.join(job_folder, "onyx_data.json")),
        "image_downloaded": os.path.exists(os.path.join(job_folder, "cover.png")),
        "job_complete": os.path.exists(os.path.join(job_folder, "job_data.json"))
    }
    
    # Load existing job data if available
    job_data = {}
    json_path = os.path.join(job_folder, "job_data.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                job_data = json.load(f)
        except:
            pass
    
    return stages, job_data


def process_single_job(job_id):
    """Process a single job with database caching"""
    job_folder = os.path.join(os.path.dirname(__file__), Config.JOBS_DIR, f"job_{job_id:03}")
    os.makedirs(job_folder, exist_ok=True)
    
    console.print(f"\n[bold magenta]━━━ Onyx Job {job_id:03} ━━━[/bold magenta]")
    
    stages, job_data = check_job_progress(job_folder)
    
    # === Check if job is already complete ===
    if stages["job_complete"] and all([
        stages["audio_downloaded"],
        stages["audio_trimmed"],
        stages["onyx_data_created"],
        stages["image_downloaded"]
    ]):
        song_title = job_data.get("song_title", "Unknown")
        console.print(f"[green]✓ Job {job_id:03} already complete: {song_title}[/green]")
        return True
    
    # === Get Song Title FIRST ===
    song_title = job_data.get("song_title")
    if not song_title:
        song_title = input(f"[Job {job_id}] Song Title (Artist - Song): ").strip()
    else:
        console.print(f"[dim]Song: {song_title}[/dim]")
    
    # === Check Database for Cached Parameters ===
    cached_song = song_db.get_song(song_title)
    cached_nova_lyrics = None  # Changed from cached_onyx_lyrics
    
    if cached_song:
        console.print(f"[green]✓ Found '{song_title}' in database![/green]")
        
        # Use cached parameters
        audio_url = cached_song["youtube_url"]
        start_time = cached_song["start_time"]
        end_time = cached_song["end_time"]
        cached_image_url = cached_song["genius_image_url"]
        cached_colors = cached_song["colors"]
        
        # Get word-level lyrics from nova_lyrics column (shared with Mono)
        cached_nova_lyrics = song_db.get_nova_lyrics(song_title)
        
        console.print(f"[dim]  URL: {audio_url}[/dim]")
        console.print(f"[dim]  Time: {start_time} → {end_time}[/dim]")
        if cached_nova_lyrics:
            console.print(f"[dim]  Cached word-level lyrics: {len(cached_nova_lyrics.get('markers', []))} markers ⚡[/dim]")
    else:
        console.print(f"[yellow]'{song_title}' not in database. Creating new entry...[/yellow]")
        cached_image_url = None
        cached_colors = None
    
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
            trimmed_path = trim_audio(audio_path, start_time, end_time, job_folder)
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
            end_time = job_data.get("end_time", "01:00")
    
    # === Image Download ===
    if not stages["image_downloaded"]:
        console.print("[cyan]Downloading cover art...[/cyan]")
        try:
            if cached_image_url:
                image_path = download_image(cached_image_url, job_folder)
                genius_image_url = cached_image_url
            else:
                # Try to get from Genius
                from scripts.genius_processing import get_song_image_url
                genius_image_url = get_song_image_url(song_title)
                if genius_image_url:
                    image_path = download_image(genius_image_url, job_folder)
                else:
                    console.print("[yellow]Could not find cover art automatically[/yellow]")
                    image_url = input(f"[Job {job_id}] Cover image URL: ").strip()
                    image_path = download_image(image_url, job_folder)
                    genius_image_url = image_url
        except Exception as e:
            console.print(f"[red]Failed to download image: {e}[/red]")
            return False
    else:
        image_path = os.path.join(job_folder, "cover.png")
        console.print("✓ Cover art already downloaded")
        genius_image_url = cached_image_url if cached_image_url else None
    
    # === Color Extraction ===
    if cached_colors:
        colors = cached_colors
        console.print(f"[dim]Using cached colors[/dim]")
    else:
        console.print("[cyan]Extracting colors from cover...[/cyan]")
        try:
            colors = extract_colors(image_path)
        except Exception as e:
            console.print(f"[yellow]Color extraction failed: {e}[/yellow]")
            colors = ["#1a1a2e", "#16213e"]  # Fallback colors
    
    # === Onyx Data Generation (Word-level transcription) ===
    onyx_data_path = os.path.join(job_folder, "onyx_data.json")
    
    if not stages["onyx_data_created"]:
        # Check if we have cached word-level lyrics from nova_lyrics column
        if cached_nova_lyrics and cached_nova_lyrics.get("markers"):
            console.print("[green]⚡ Using cached word-level lyrics from database[/green]")
            onyx_data = cached_nova_lyrics.copy()
            
            # Add colors and cover image path
            onyx_data["colors"] = colors
            onyx_data["cover_image"] = "cover.png"
            
            with open(onyx_data_path, "w", encoding="utf-8") as f:
                json.dump(onyx_data, f, indent=4, ensure_ascii=False)
        else:
            console.print("[cyan]Transcribing audio (word-level)...[/cyan]")
            try:
                onyx_data = transcribe_audio_onyx(job_folder, song_title)
                
                # Add colors and cover image path
                onyx_data["colors"] = colors
                onyx_data["cover_image"] = "cover.png"
                
                with open(onyx_data_path, "w", encoding="utf-8") as f:
                    json.dump(onyx_data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                console.print(f"[yellow]Warning: Transcription failed: {e}[/yellow]")
                onyx_data = {"markers": [], "colors": colors, "cover_image": "cover.png"}
                with open(onyx_data_path, "w", encoding="utf-8") as f:
                    json.dump(onyx_data, f)
    else:
        with open(onyx_data_path, "r", encoding="utf-8") as f:
            onyx_data = json.load(f)
        console.print("✓ Onyx data already created")
    
    # === Save to Database ===
    if not cached_song:
        console.print(f"[cyan]💾 Saving '{song_title}' to database...[/cyan]")
        song_db.add_song(
            song_title=song_title,
            youtube_url=audio_url,
            start_time=start_time,
            end_time=end_time,
            genius_image_url=genius_image_url if 'genius_image_url' in locals() else None,
            transcribed_lyrics=None,  # Don't overwrite Aurora's lyrics
            colors=colors,
            beats=None  # Onyx doesn't use beats
        )
        console.print("[green]✓ Song saved to database[/green]")
    else:
        song_db.mark_song_used(song_title)
        console.print(f"[green]✓ Marked '{song_title}' as used[/green]")
        
        # Update colors if needed
        if colors and not cached_colors:
            song_db.update_colors_and_beats(song_title, colors, None)
    
    # Save word-level lyrics to nova_lyrics column (shared with Mono)
    if onyx_data and onyx_data.get("markers"):
        # Only save the markers part to nova_lyrics (without colors/cover_image)
        lyrics_data = {
            "markers": onyx_data["markers"],
            "total_markers": len(onyx_data["markers"])
        }
        song_db.update_nova_lyrics(song_title, lyrics_data)
        console.print("[green]✓ Word-level lyrics saved to database (nova_lyrics)[/green]")
    
    # === Save Job Data ===
    job_data = {
        "job_id": job_id,
        "audio_source": os.path.abspath(audio_path).replace("\\", "/"),
        "audio_trimmed": os.path.abspath(trimmed_path).replace("\\", "/"),
        "cover_image": os.path.abspath(image_path).replace("\\", "/"),
        "colors": colors,
        "onyx_data": os.path.abspath(onyx_data_path).replace("\\", "/"),
        "job_folder": os.path.abspath(job_folder).replace("\\", "/"),
        "song_title": song_title,
        "youtube_url": audio_url,
        "start_time": start_time,
        "end_time": end_time,
        "marker_count": len(onyx_data.get("markers", []))
    }
    
    json_path = os.path.join(job_folder, "job_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(job_data, f, indent=4)
    
    console.print(f"[green]✓ Onyx Job {job_id:03} complete[/green]")
    return True


def batch_generate_jobs():
    """Generate all jobs with database caching"""
    console.print("\n[bold magenta]💿 Apollova Onyx - Music Video Automation[/bold magenta]\n")
    
    # Validate config
    Config.validate()
    
    # Create jobs directory
    os.makedirs(Config.JOBS_DIR, exist_ok=True)
    
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
    
    console.print("\n[bold green]✅ All Onyx jobs processed![/bold green]")
    
    # Show updated stats
    stats = song_db.get_stats()
    console.print(f"\n[cyan]📊 Database now has:[/cyan]")
    console.print(f"   {stats['total_songs']} songs")
    console.print(f"   {stats['cached_lyrics']} with cached lyrics")
    console.print(f"   {stats['total_uses']} total uses")
    
    console.print("\n[cyan]Next step:[/cyan] Run the After Effects JSX script")
    console.print("[dim]File → Scripts → Run Script File... → scripts/JSX/automateMV_onyx.jsx[/dim]\n")


if __name__ == "__main__":
    try:
        batch_generate_jobs()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]❌ Fatal error: {e}[/red]")
        raise