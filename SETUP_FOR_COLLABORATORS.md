# Collaborator Setup Guide

## Goal
Run the GUI and analysis after cloning this repository, with minimum setup effort.

## What collaborators need
- Python 3.10+
- OpenSeesPy installed in the solver environment
- This repository cloned locally

## Fast setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python gui_wsl.py
```

## Backend modes
- Windows: GUI can call WSL backend from the Run tab.
- Linux/macOS: GUI can run local backend from the Run tab.

Set the Run tab activate command to match the solver environment, for example:
- `source ~/ops_env/bin/activate`
- `source .venv/bin/activate`
- `conda activate opensees`

## Custom material build (only if required)
If you must use custom `MultiSurfCrack2D` inside OpenSees, build on the target machine:
```bash
bash build_msc2d.sh
```

If custom material is not available, the runner uses a stable fallback interface model.

## Notes for sharing with professor
- Share source code, not compiled `.so/.pyd` binaries.
- Compiled OpenSees binaries are platform and Python-version specific.
- For repeatable runs, also share the parameter JSON used in the paper case.
