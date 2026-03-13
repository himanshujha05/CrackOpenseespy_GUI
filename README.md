# Multi-Surf Crack 2D

2D reinforced concrete panel analysis GUI with crack-interface modeling in OpenSeesPy.

## What This Project Does

The app lets you:
- Build a 2D plane-stress RC panel mesh (`tri31` elements)
- Insert horizontal crack interfaces by duplicating mesh rows
- Assign crack constitutive behavior per crack line
- Apply boundary conditions and loads interactively
- Run nonlinear static analysis and visualize response curves and fields

Primary GUI file: `gui_wsl.py`

## Quick Start (Human-Friendly)

If someone asks, "What do I need to run this?", the short answer is:

- Python 3.10+
- OpenSeesPy in the solver environment
- This repository cloned

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd multi-surf-crack2D
```

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If your system uses `python3` instead of `python`, replace `python` with `python3`.

On Windows PowerShell, activation is:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Run the GUI

```bash
python gui_wsl.py
```

On Windows, you can also run:

```powershell
.\run_gui.bat
```

## Machine-Specific Setup

### Windows (GUI + WSL backend)

Install on the machine:

- Python 3.10+ (Windows)
- WSL2 with Ubuntu
- OpenSeesPy inside WSL (or your WSL venv/conda env)

Then in the GUI Run tab set `Activate cmd`, for example:

- `source ~/ops_env/bin/activate`
- `source .venv/bin/activate`
- `conda activate opensees`

### Linux (local backend)

Example for Ubuntu:

```bash
sudo apt update
sudo apt install -y python3 python3-venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python gui_wsl.py
```

Run tab `Activate cmd` example:

- `source .venv/bin/activate`

### macOS (local backend)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python gui_wsl.py
```

Run tab `Activate cmd` example:

- `source .venv/bin/activate`

## Sharing This Repo With Others

Short answer: they do **not** need to compile everything unless they specifically need the custom `MultiSurfCrack2D` material inside OpenSees.

### Case A: Standard use (no custom OpenSees build)
Most users can run immediately after clone + `pip install -r requirements.txt`.

They can test different crack material options directly in the GUI:

- `MultiSurfCrack2D`
- `Elastic`
- `ElasticPPGap`
- `CustomBilinear`

If `MultiSurfCrack2D` cannot be used for the current 2D link path in that environment, the runner automatically uses a stable fallback model so analysis can still run.

### Case B: Custom material required (`MultiSurfCrack2D`)
If a collaborator must run with your custom material integrated into OpenSees, they must build OpenSees/OpenSeesPy on their own machine (or use a prebuilt artifact for their exact OS + Python version).

Use:

```bash
bash build_msc2d.sh
```

### Important portability note
Compiled binaries are platform-specific. A `.so/.pyd` built on one machine usually will not run on a different OS/Python ABI. For reproducible handoff, share:

- source code (this repo)
- dependency instructions
- build script (`build_msc2d.sh`) for custom integration
- optional container/CI wheel workflow if you want zero-manual setup

## Build Custom MultiSurfCrack2D in OpenSees (WSL)

If you need the custom C++ material build workflow, use:
- `build_msc2d.sh`

From WSL:
```bash
bash /mnt/c/Users/himan/multi-surf-crack2D/build_msc2d.sh
```

## Typical Workflow in GUI

1. Geometry tab:
- Set panel size, mesh density, crack lines
- Assign BCs and loads
2. Crack Materials tab:
- Refresh from geometry
- Choose material type per crack (`MultiSurfCrack2D`, `Elastic`, `ElasticPPGap`, `CustomBilinear`)
3. Analysis tab:
- Choose `DisplacementControl` or `LoadControl`
4. Run tab:
- Validate backend
- Run analysis
5. Results tab:
- Plot force-displacement, crack opening/slip, deformed mesh, contour

## Notes

- The GUI now supports Windows (WSL) and Linux/macOS (local bash backend).
- For cracks set to `MultiSurfCrack2D`, the runner now tries true `zeroLengthND` integration first and only falls back to the robust spring macro model when compatibility fails in that environment.
- Runs are saved under `~/panel_analysis_runs/`.
- For collaborator handoff checklist, see `SETUP_FOR_COLLABORATORS.md`.

## What To Send Your Professor

- This repository source code
- `README.md` and `SETUP_FOR_COLLABORATORS.md`
- Optional example parameter files (for the cases you used in your paper)

They can clone and run the GUI on their own machine. They only need custom OpenSees compilation if they explicitly want custom `MultiSurfCrack2D` built into their local OpenSees.