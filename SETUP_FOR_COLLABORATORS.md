# Collaborator Setup Guide

## Quick goal
Clone the project, install dependencies, and run the GUI.

## What you need
- Python 3.10 or newer
- OpenSeesPy available in your solver environment

## 1) Clone the project
```bash
git clone <repo-url>
cd multi-surf-crack2D
```

## 2) Create and activate a virtual environment

### Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Linux/macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3) Install packages
```bash
pip install -r requirements.txt
```

## 4) Start the GUI
```bash
python gui_wsl.py
```

On Windows, you can also run:
```powershell
.\run_gui.bat
```

## 5) First run setup (important)
Open the Run tab in the GUI and do this once:
1. Click Auto-Detect.
2. Select a working backend (WSL or local).
3. Click Validate Backend.
4. Run Analysis.

If OpenSeesPy is installed locally (not in WSL), choose local backend.

## Do you need `build_msc2d.sh`?
Most users: no.

You only need `build_msc2d.sh` if you specifically want to compile and use custom `MultiSurfCrack2D` integration in your own OpenSees build.

## Share-ready note
When sharing this project, share source code and docs.
Do not share compiled `.so` or `.pyd` binaries across machines because they are platform and Python-version specific.
