# MV-AE-Project-Automation

[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A fully automated pipeline for creating professional 3D music-video visuals ready for social media distribution. The project automates audio extraction, trimming, lyric transcription, color extraction from album art, and batch rendering via Adobe After Effects.

## Quick Snapshot

- **Language:** Python 3
- **AE Scripting:** Adobe After Effects ExtendScript (JSX)
- **Batch Mode:** `jobs/job_001` → `jobs/job_012` by default
- **Output:** H.264 MP4 files with synced lyrics and color-graded visuals

## Table of Contents

1. [Overview](#1--overview)
2. [Features](#2--features)
3. [Quick Start (Windows)](#3--quick-start-windows)
4. [After Effects Setup Checklist](#4--after-effects-setup-checklist)
5. [File Layout](#5--file-layout)
6. [Dependencies & Installation](#6--dependencies--installation)
7. [Usage Examples](#7--usage-examples)
8. [Troubleshooting](#8--troubleshooting)
9. [Configuration](#9--configuration)
10. [Contributing & License](#10--contributing--license)

## 1 — Overview

The pipeline consists of two main components:

- **`main.py`** — Python command-line tool that:
  - Downloads audio from YouTube or streaming URLs
  - Trims audio to specified timestamps
  - Downloads cover images from URLs
  - Extracts 4 dominant colors from cover art (hex format)
  - Transcribes lyrics using OpenAI Whisper with word-level timing
  - Writes `job_data.json` containing all metadata for each job

- **`scripts/automateMV_batch.jsx`** — After Effects ExtendScript that:
  - Imports job assets into AE project
  - Wires audio, cover images, and lyrics into templated compositions
  - Applies extracted colors to gradient effects
  - Populates text layers with synchronized lyrics
  - Automatically queues all jobs for rendering

## 2 — Features

✅ **Audio Processing**
- Download from YouTube/streaming links using `yt-dlp`
- Trim to custom timestamps (MM:SS format)
- Export as WAV for After Effects compatibility

✅ **Image Processing**
- Download cover images from any URL
- Extract 4 dominant colors using ColorThief
- Output colors in hex format for AE color grading

✅ **Lyric Transcription**
- Automatic speech-to-text using OpenAI Whisper
- Word-level timing synchronization
- Smart line wrapping (25-character limit per line)
- JSON output with precise timing data

✅ **After Effects Integration**
- Batch imports all job assets
- Auto-wires comps with audio, cover art, and lyrics
- Applies extracted colors to gradient effects
- Generates render queue automatically
- Exports to H.264 MP4 format

✅ **Job Management**
- Resume interrupted jobs seamlessly
- Cache intermediate results
- JSON-based metadata for transparency and debugging

## 3 — Quick Start (Windows)

### Prerequisites

- Python 3.8 or later
- Adobe After Effects (with scripting enabled)
- `ffmpeg` (must be on system PATH)

### Installation

**Step 1: Install Python Dependencies**

```powershell
python -m pip install -r requirements.txt
```

**Step 2: Install ffmpeg**

1. Download a build from:
   - [gyan.dev ffmpeg builds](https://www.gyan.dev/ffmpeg/builds/) (recommended for Windows)
   - [ffmpeg.org](https://ffmpeg.org/download.html)

2. Unzip and copy `ffmpeg.exe` to a folder on your PATH, or add the folder to PATH:
   ```powershell
   # Example: add to PATH
   $env:Path += ";C:\ffmpeg\bin"
   ```

3. Verify installation:
   ```powershell
   ffmpeg -version
   ```

**Step 3: Run Job Generator**

```powershell
python main.py
```

Follow the interactive prompts for each job (1–12):
- Audio URL (YouTube, SoundCloud, etc.)
- Start time (MM:SS format)
- End time (MM:SS format)
- Cover image URL
- Song title (Artist - Song)

Each completed job generates a folder in `jobs/job_###/` containing:
- `audio_source.mp3` — Original downloaded audio
- `audio_trimmed.wav` — Trimmed audio clip
- `cover.png` — Downloaded cover image
- `lyrics.txt` — Transcribed lyrics with timestamps (JSON)
- `job_data.json` — Complete metadata for AE import

## 4 — After Effects Setup Checklist

Before running the JSX script, verify your After Effects project template includes:

### Project Folder Structure

- `Foreground` (folder)
- `Background` (folder)
- `OUTPUT1` through `OUTPUT12` (folders)

### Required Compositions (Comps)

- `MAIN` — Master template (will be duplicated for each job)
- `OUTPUT 1` through `OUTPUT 12` — One per job
- `LYRIC FONT 1` through `LYRIC FONT 12` — Lyric display comps
- `Assets 1` through `Assets 12` — Album art and metadata
- `BACKGROUND 1` through `BACKGROUND 12` — Gradient backgrounds

### Required Layers & Effects

**In each `BACKGROUND N` comp:**
- Layer named `BG GRADIENT` with a **4-Color Gradient effect** applied

**In each `LYRIC FONT N` comp:**
- Text layer named `LYRIC CURRENT` (displays current lyric)
- Text layer named `LYRIC PREVIOUS` (displays previous lyric)
- Text layer named `LYRIC NEXT 1` (displays next lyric)
- Text layer named `LYRIC NEXT 2` (displays lyric after next)
- Audio layer named `AUDIO` (or any AVLayer with audio enabled)

### Running the AE Script

1. Open your After Effects template project
2. `File` → `Scripts` → `Run Script File...`
3. Select `scripts/automateMV_batch.jsx`
4. When prompted, navigate to and select the `jobs` folder
5. Script automatically:
   - Imports all job assets
   - Wires audio and images
   - Applies colors and populates lyrics
   - Queues renders
6. Review the Render Queue and click **Render**

## 5 — File Layout

```
MV-AE-Project-Automation/
├── main.py                          # Python job generator
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
├── scripts/
│   └── automateMV_batch.jsx         # After Effects automation script
├── database/
│   ├── config.yaml
│   ├── song_picker.py
│   ├── tiktok_sound_db.py
│   └── tiktok-sound.json
├── template/
│   └── 3D Apple Music.aep           # AE project template
├── jobs/
│   ├── job_001/
│   │   ├── audio_source.mp3         # Original audio
│   │   ├── audio_trimmed.wav        # Trimmed audio clip
│   │   ├── cover.png                # Album cover image
│   │   ├── lyrics.txt               # Transcribed lyrics (JSON)
│   │   ├── job_data.json            # Metadata for AE
│   │   ├── beats.json               # Beat analysis (optional)
│   │   └── genius_lyrics.txt        # Reference lyrics (optional)
│   ├── job_002/
│   └── ... (job_003 through job_012)
├── renders/                         # Output videos (auto-created)
│   └── job_001.mp4
└── whisper_models/                  # Cached Whisper models
    ├── small.pt
    └── medium.pt
```

## 6 — Dependencies & Installation

### Python Packages

All required packages are listed in `requirements.txt`:

| Package | Purpose |
|---------|---------|
| `yt-dlp` | Download audio from YouTube/streaming services |
| `ffmpeg` | External binary for audio conversion |
| `pydub` | Audio trimming and WAV export |
| `requests` | Download images from URLs |
| `Pillow` (PIL) | Image handling and validation |
| `colorthief` | Extract dominant colors from images |
| `openai-whisper` | Speech-to-text transcription |
| `matplotlib` | Optional color visualization |

### Install All Dependencies

```powershell
python -m pip install -r requirements.txt
```

### Whisper Model Notes

- First run downloads the Whisper model (~140 MB for `small`, ~1.4 GB for `large`)
- Models cached in `whisper_models/` directory
- Recommended: `small` (balanced speed/accuracy)
- Optional: `base`, `medium`, or `large` for higher accuracy

## 7 — Usage Examples

### Basic Workflow

```powershell
# 1. Generate job metadata, audio, images, and transcripts
python main.py

# 2. Follow prompts for 12 jobs (or as configured)
# Example input:
#   [Job 1] Enter AUDIO URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ
#   [Job 1] Enter start time (MM:SS): 00:15
#   [Job 1] Enter end time (MM:SS): 01:45
#   [Job 1] Enter IMAGE URL: https://example.com/cover.jpg
#   [Job 1] Enter SONG TITLE (Artist - Song): Rick Astley - Never Gonna Give You Up

# 3. Open AE and run the JSX script
# File → Scripts → Run Script File... → scripts/automateMV_batch.jsx

# 4. Review Render Queue and render
```

### Example `job_data.json`

```json
{
  "job_id": 1,
  "audio_source": "jobs/job_001/audio_source.mp3",
  "audio_trimmed": "jobs/job_001/audio_trimmed.wav",
  "cover_image": "jobs/job_001/cover.png",
  "colors": ["#ff5733", "#33ff57", "#3357ff", "#f0ff33"],
  "lyrics_file": "jobs/job_001/lyrics.txt",
  "job_folder": "jobs/job_001",
  "song_title": "Rick Astley - Never Gonna Give You Up"
}
```

### Example `lyrics.txt` (JSON Format)

```json
[
  {
    "t": 0.5,
    "lyric_prev": "",
    "lyric_current": "Never gonna give you up",
    "lyric_next1": "Never gonna let you down",
    "lyric_next2": "Never gonna run around"
  },
  {
    "t": 3.2,
    "lyric_prev": "Never gonna give you up",
    "lyric_current": "Never gonna let you down",
    "lyric_next1": "Never gonna run around",
    "lyric_next2": "And desert you"
  }
]
```

**Key Fields:**
- `t` — Start time in seconds
- `lyric_current` — Main lyric to display
- `lyric_prev`, `lyric_next1`, `lyric_next2` — Context for carousel effects

## 8 — Troubleshooting

### Audio Download Fails

**Problem:** `yt-dlp` error or URL not recognized

**Solutions:**
- Verify URL is valid (YouTube, SoundCloud, Spotify, etc.)
- Update `yt-dlp`: `python -m pip install --upgrade yt-dlp`
- Check internet connection
- Some sites may require cookies; check yt-dlp docs

### Audio Not Trimming / FFmpeg Errors

**Problem:** "ffmpeg not found" or audio conversion errors

**Solutions:**
- Verify `ffmpeg -version` works in PowerShell
- Add ffmpeg folder to PATH if not detected
- Reinstall ffmpeg from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)

### Whisper Transcription Slow or Failing

**Problem:** Whisper takes too long or runs out of memory

**Solutions:**
- Use `small` model instead of `medium`/`large`
- Check available disk space (models can be 140 MB–1.4 GB)
- Ensure audio is not excessively long; trim timestamps more aggressively
- Run on a machine with GPU for faster processing

### After Effects Script Errors

**Problem:** AE alerts about missing comps, layers, or naming mismatches

**Solutions:**
- Open template project and verify exact naming matches section 4 checklist
- Ensure all required folders and comps exist in correct structure
- Run AE's Script Debugger (`File` → `Scripts` → `Script Debugger`) for detailed error messages
- Check console output in Script Debugger window

### Colors Not Applying to Gradients

**Problem:** Gradients remain unchanged after script runs

**Solutions:**
- Verify `BG GRADIENT` layer exists in each `BACKGROUND N` comp
- Check that layer has a **4-Color Gradient effect** (not other gradient types)
- Ensure effect is named exactly `4-Color Gradient` or `4 Color Gradient`
- Re-run script or manually inspect the effect

### Lyrics Not Appearing in AE

**Problem:** Text layers stay blank or show placeholder text

**Solutions:**
- Verify text layers exist: `LYRIC CURRENT`, `LYRIC PREVIOUS`, `LYRIC NEXT 1`, `LYRIC NEXT 2`
- Check that `LYRIC FONT N` comps exist for each job
- Ensure audio layer is named `AUDIO` or is the primary audio layer
- Check `lyrics.txt` exists and is valid JSON
- Run script again or manually inspect layer expressions

### Render Queue Empty or Jobs Missing

**Problem:** No items appear in Render Queue after script runs

**Solutions:**
- Verify all `OUTPUT N` comps exist (1–12 or as configured)
- Check `job_data.json` files were created by Python script
- Ensure audio and image files are accessible and not moved
- Re-run Python script to regenerate missing metadata

## 9 — Configuration

### Adjust Job Count

Edit `main.py` and change the job count:

```python
def batch_generate_jobs():
    base_jobs = 12  # Change to desired number (e.g., 5, 20, etc.)
```

Then re-run:
```powershell
python main.py
```

### Customize Whisper Model

In `main.py`, find the transcription function and modify:

```python
model = whisper.load_model("small")  # Options: tiny, base, small, medium, large
```

- `tiny` / `base` — Fastest, lower accuracy
- `small` — Balanced (recommended)
- `medium` / `large` — Higher accuracy, slower, larger models

### Adjust Lyric Line Wrapping

In `main.py`, find `chunk_text()` function:

```python
def chunk_text(s, limit=25):  # Change 25 to desired character limit
```

## 10 — Contributing & License

### Contributing

We welcome improvements and bug reports!

**Workflow:**
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes with clear commit messages
4. Test thoroughly
5. Push and open a Pull Request with a description

**Areas for contribution:**
- Additional audio source support (Spotify, Apple Music, etc.)
- GUI for job configuration
- Batch error recovery
- Performance optimizations
- Extended After Effects features

### License

This project is licensed under the **MIT License**. See `LICENSE` file for details.

You are free to:
- Use commercially and privately
- Modify and distribute
- Use in derivative works

Please include the original license notice in any distributions.

---

**Last Updated:** December 2025  
**Maintainer:** [@AliBars19](https://github.com/AliBars19)

For questions or support, open an issue on GitHub or refer to the troubleshooting section above.
