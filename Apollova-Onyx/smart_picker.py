#!/usr/bin/env python3
"""
Smart Picker - Apollova Onyx
Auto-select 12 songs and run them with Onyx processing.
"""
import os
import sys
import time
import builtins
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.smart_picker import SmartSongPicker
from main import process_single_job
from rich.console import Console

console = Console()

SHARED_DB = Path(__file__).parent.parent / "database" / "songs.db"


def main():
    console.print("[bold magenta]💿 Smart Song Picker - Apollova Onyx[/bold magenta]\n")
    
    if not SHARED_DB.exists():
        console.print(f"[red]❌ Database not found at: {SHARED_DB}[/red]")
        console.print("[yellow]Run main.py first to create the database.[/yellow]")
        return
    
    picker = SmartSongPicker(db_path=str(SHARED_DB))
    stats = picker.get_database_stats()
    
    if stats['total_songs'] == 0:
        console.print("[red]❌ Database is empty. Add songs first using main.py[/red]")
        return
    
    console.print(f"[dim]📊 Database: {SHARED_DB}[/dim]")
    console.print(f"[dim]   {stats['total_songs']} songs, {stats['unused_songs']} unused[/dim]\n")
    
    songs = picker.get_available_songs(num_songs=12)
    
    if len(songs) < 12:
        console.print(f"[yellow]⚠️  Only {len(songs)} songs available[/yellow]\n")
    
    console.print("[cyan]📋 Next songs to process:[/cyan]")
    for i, song in enumerate(songs, 1):
        status = "unused" if song['use_count'] == 1 else f"{song['use_count']}x"
        console.print(f"  {i:2}. {song['song_title']:<45} ({status})")
    
    console.print()
    response = input(f"Run these {len(songs)} Onyx jobs? (Y/n): ").strip().lower()
    if response == 'n':
        console.print("Cancelled.")
        return
    
    console.print()
    
    song_index = [0]
    original_input = builtins.input
    
    def smart_input(prompt):
        if "Song Title" in prompt:
            if song_index[0] >= len(songs):
                return original_input(prompt)
            song = songs[song_index[0]]
            song_index[0] += 1
            console.print(f"{prompt}[auto] {song['song_title']}")
            return song['song_title']
        else:
            return original_input(prompt)
    
    builtins.input = smart_input
    
    start = time.time()
    successful = 0
    num_jobs = min(len(songs), 12)
    
    for i in range(1, num_jobs + 1):
        try:
            if process_single_job(i):
                successful += 1
        except Exception as e:
            console.print(f"[red]Job {i} failed: {e}[/red]")
            import traceback
            traceback.print_exc()
    
    elapsed = time.time() - start
    builtins.input = original_input
    
    console.print(f"\n[bold magenta]━━━ Onyx Summary ━━━[/bold magenta]")
    console.print(f"Completed: {successful}/{num_jobs}")
    console.print(f"Time: {elapsed:.1f}s")
    
    if successful == num_jobs:
        console.print(f"\n[green]✅ All Onyx jobs ready![/green]")
        console.print("[cyan]Next:[/cyan] Run the After Effects JSX script")
        console.print("[dim]File → Scripts → Run Script File... → scripts/JSX/automateMV_onyx.jsx[/dim]\n")


if __name__ == "__main__":
    main()