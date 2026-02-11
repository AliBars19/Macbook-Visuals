#!/usr/bin/env python3
"""
Music Video Automation - Apollova Mono
Minimal text-only lyric videos with word-by-word reveal
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
from scripts.audio_processing import download_audio, trim_audio
from scripts.lyric_processing import transcribe_audio_mono
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
        "mono_data_generated": os.path.exists(os.path.join(job_folder, "mono_data.json")),
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
    jobs_dir = os.path.join(os.path.dirname(__file__), "jobs")
    
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
    """Process a single job for Mono (minimal text-only style)"""
    job_folder = os.path.join(os.path.dirname(__file__), "jobs", f"job_{job_id:03}")
    os.makedirs(job_folder, exist_ok=True)
    
    console.print(f"\n[bold magenta]━━━ Mono Job {job_id:03} ━━━[/bold magenta]")
    
    stages, job_data = check_job_progress(job_folder)
    
    # Check if job is already complete
    if stages["job_complete"] and all([
        stages["audio_downloaded"],
        stages["audio_trimmed"],
        stages["mono_data_generated"]
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
    cached_mono_lyrics = None
    
    if cached_song:
        console.print(f"[green]✓ Found '{song_title}' in database![/green]")
        audio_url = cached_song["youtube_url"]
        start_time = cached_song["start_time"]
        end_time = cached_song["end_time"]
        
        # Get Mono-specific lyrics (word-level) from nova_lyrics column
        cached_mono_lyrics = song_db.get_nova_lyrics(song_title)
        
        console.print(f"[dim]  URL: {audio_url}[/dim]")
        console.print(f"[dim]  Time: {start_time} → {end_time}[/dim]")
        if cached_mono_lyrics:
            console.print(f"[dim]  Cached word-level lyrics: {len(cached_mono_lyrics.get('markers', []))} markers ⚡[/dim]")
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
    
    # === Mono Data Generation (Word-level transcription) ===
    mono_data_path = os.path.join(job_folder, "mono_data.json")
    
    if cached_mono_lyrics and cached_mono_lyrics.get("markers"):
        console.print(f"[green]⚡ Using cached word-level lyrics ({len(cached_mono_lyrics.get('markers', []))} markers)[/green]")
        transcribed_lyrics = cached_mono_lyrics
        with open(mono_data_path, "w", encoding="utf-8") as f:
            json.dump(transcribed_lyrics, f, indent=4, ensure_ascii=False)
    elif not stages["mono_data_generated"]:
        console.print("[cyan]Transcribing with word-level timestamps...[/cyan]")
        try:
            transcribed_lyrics = transcribe_audio_mono(job_folder, song_title)
            with open(mono_data_path, "w", encoding="utf-8") as f:
                json.dump(transcribed_lyrics, f, indent=4, ensure_ascii=False)
        except Exception as e:
            console.print(f"[yellow]Warning: Transcription failed: {e}[/yellow]")
            transcribed_lyrics = {"markers": [], "total_markers": 0}
            with open(mono_data_path, "w", encoding="utf-8") as f:
                json.dump(transcribed_lyrics, f)
    else:
        with open(mono_data_path, "r", encoding="utf-8") as f:
            transcribed_lyrics = json.load(f)
        console.print("✓ Mono data already generated")
    
    # === Save to Database ===
    if not cached_song:
        console.print(f"[cyan]💾 Saving '{song_title}' to database...[/cyan]")
        song_db.add_song(
            song_title=song_title,
            youtube_url=audio_url,
            start_time=start_time,
            end_time=end_time,
            genius_image_url=None,
            transcribed_lyrics=None,  # Don't overwrite Aurora's lyrics
            colors=None,
            beats=None
        )
        console.print("[green]✓ Song saved to database for future use[/green]")
    else:
        song_db.mark_song_used(song_title)
        console.print(f"[green]✓ Marked '{song_title}' as used in database[/green]")
    
    # Save Mono lyrics to nova_lyrics column (shared with Onyx)
    if transcribed_lyrics and transcribed_lyrics.get("markers"):
        song_db.update_nova_lyrics(song_title, transcribed_lyrics)
        console.print("[green]✓ Word-level lyrics saved to database (nova_lyrics)[/green]")
    
    # === Save Job Data ===
    job_data = {
        "job_id": job_id,
        "audio_source": os.path.abspath(audio_path).replace("\\", "/"),
        "audio_trimmed": os.path.abspath(trimmed_path).replace("\\", "/"),
        "mono_data": os.path.abspath(mono_data_path).replace("\\", "/"),
        "job_folder": os.path.abspath(job_folder).replace("\\", "/"),
        "song_title": song_title,
        "youtube_url": audio_url,
        "start_time": start_time,
        "end_time": end_time,
        "marker_count": len(transcribed_lyrics.get("markers", []))
    }
    
    json_path = os.path.join(job_folder, "job_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(job_data, f, indent=4)
    
    console.print(f"[green]✓ Mono Job {job_id:03} complete[/green]")
    return True


def batch_generate_jobs():
    """Generate all Mono jobs with database caching"""
    console.print("\n[bold magenta]🎬 Apollova Mono - Music Video Automation[/bold magenta]")
    console.print("[dim]Minimal text-only lyric videos[/dim]\n")
    
    # Check for existing jobs first
    check_existing_jobs()
    
    # Validate config
    Config.validate()
    
    # Create jobs directory
    jobs_dir = os.path.join(os.path.dirname(__file__), "jobs")
    os.makedirs(jobs_dir, exist_ok=True)
    
    # Show database stats
    stats = song_db.get_stats()
    console.print(f"[dim]📊 Database: {SHARED_DB}[/dim]")
    if stats["total_songs"] > 0:
        console.print(f"[dim]   {stats['total_songs']} songs, "
                     f"{stats.get('cached_nova_lyrics', 0)} with cached word-level lyrics[/dim]\n")
    
    # Process each job
    total_jobs = Config.TOTAL_JOBS
    
    for job_id in range(1, total_jobs + 1):
        success = process_single_job(job_id)
        
        if not success:
            console.print(f"\n[yellow]⚠️  Job {job_id} had errors, continuing...[/yellow]")
    
    console.print("\n[bold green]✅ All Mono jobs processed![/bold green]")
    
    # Show updated stats
    stats = song_db.get_stats()
    console.print(f"\n[magenta]📊 Database now has:[/magenta]")
    console.print(f"   {stats['total_songs']} songs")
    console.print(f"   {stats.get('cached_nova_lyrics', 0)} with cached word-level lyrics")
    console.print(f"   {stats['total_uses']} total uses")
    
    console.print("\n[magenta]Next step:[/magenta] Run the After Effects JSX script")
    console.print("[dim]File → Scripts → Run Script File... → scripts/JSX/automateMV_mono.jsx[/dim]\n")


if __name__ == "__main__":
    try:
        batch_generate_jobs()
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]❌ Fatal error: {e}[/red]")
        raise