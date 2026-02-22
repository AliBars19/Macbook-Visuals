# Apollova Installer

## Quick Start

1. **Run Setup.exe** - This will install required Python packages
2. **Choose options:**
   - GPU Acceleration (optional, +1.5GB, requires NVIDIA GPU)
   - Desktop shortcut (optional)
3. **Click Install** and wait for completion
4. **Launch Apollova** using the created launcher

## Requirements

- Windows 10/11 (64-bit)
- Python 3.10 or higher (Setup will prompt to install if missing)
- Adobe After Effects (for rendering)
- NVIDIA GPU with CUDA support (optional, for GPU acceleration)

## Folder Structure

```
Apollova/
├── Setup.exe           # Run once to install dependencies
├── Apollova.exe        # Main application launcher
├── Uninstall.exe       # Remove installed packages
├── assets/             # Application code
├── templates/          # After Effects templates
├── database/           # Song database
├── Apollova-Aurora/    # Aurora template jobs
├── Apollova-Mono/      # Mono template jobs
└── Apollova-Onyx/      # Onyx template jobs
```

## Whisper Models

Whisper transcription models are downloaded on first use:
- tiny: ~75MB (fastest)
- base: ~140MB (balanced)
- small: ~460MB (recommended)
- medium: ~1.5GB (accurate)
- large: ~3GB (most accurate)

## Uninstalling

Run `Uninstall.exe` to remove installed Python packages.
Then delete the Apollova folder.

## Troubleshooting

**"Python not found"**
- Install Python 3.10+ from python.org
- Or check "Download and install Python" in Setup

**GPU acceleration not working**
- Ensure you have an NVIDIA GPU
- Update GPU drivers
- Reinstall with GPU option checked

**After Effects not launching**
- Set the correct path in Settings tab
- Ensure After Effects is installed
