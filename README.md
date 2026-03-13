# Multi-Surf Crack 2D

2D reinforced concrete panel analysis GUI with crack-interface modeling in OpenSeesPy.

## What This Project Does

The app lets you:
- Build a 2D plane-stress RC panel mesh using OpenSees 3-node triangular elements (`tri31`)
- Insert horizontal crack interfaces by duplicating mesh rows
- Trace cracks from a background image or hand-draw them on the mesh canvas
- Assign crack constitutive behavior with a global template and per-interface element overrides
- Apply boundary conditions and loads interactively
- Run nonlinear static analysis and visualize response curves, crack response histories, and fields

In simple terms, `tri31` is the standard 2D triangle element used to model the concrete panel body. Crack behavior is then added at the interfaces between duplicated node rows.

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

Then in the GUI Run tab either click `Auto-Detect` or set `Activate / Python cmd`, for example:

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

Run tab `Activate / Python cmd` example:

- `source .venv/bin/activate`

### macOS (local backend)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python gui_wsl.py
```

Run tab `Activate / Python cmd` example:

- `source .venv/bin/activate`

## Sharing This Repo With Others

Short answer: they do **not** need to compile everything unless they specifically need the custom `MultiSurfCrack2D` material inside OpenSees.

### Case A: Standard use (no custom OpenSees build)
Most users can run immediately after clone + `pip install -r requirements.txt`.

They can test different crack material options directly in the GUI:

- `MultiSurfCrack2D`
- `EPPGap Macro (4-spring)`
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
- Set panel size and mesh density
- Add crack rows manually, click to place them, or trace over an uploaded panel image
- Assign BCs and loads on the mesh canvas
2. Crack Materials tab:
- Refresh from geometry
- Use the Template group to define default crack properties
- Select table rows to edit individual crack interface elements in the Selected Element Editor
- Choose material type per interface element (`MultiSurfCrack2D`, `EPPGap Macro (4-spring)`, `Elastic`, `ElasticPPGap`, `CustomBilinear`)
3. Analysis tab:
- Choose `DisplacementControl` or `LoadControl`
- Select solver, constraint handler, and numberer when convergence tuning is needed
4. Run tab:
- Use `Auto-Detect` to locate a working OpenSeesPy backend, or enter the command manually
- Validate backend
- Run analysis
5. Results tab:
- Plot force-displacement, crack opening/slip, deformed mesh, contour
- Click crack markers to inspect per-element response histories

## Notes

- The GUI supports Windows with WSL or local Windows Python, plus Linux/macOS local backends.
- For cracks set to `MultiSurfCrack2D`, the runner now tries true `zeroLengthND` integration first and only falls back to the robust spring macro model when compatibility fails in that environment.
- Crack interface materials are managed per interface element in a scrollable editor with a template section, selected-element editor, and crack table.
- The GUI stores backend detection settings in a local `panel_gui_config.json` file; that file is machine-specific and is not tracked by git.
- Runs are saved under `~/panel_analysis_runs/`.
- For collaborator handoff checklist, see `SETUP_FOR_COLLABORATORS.md`.

## What To Send Your Professor

- This repository source code
- `README.md` and `SETUP_FOR_COLLABORATORS.md`
- Optional example parameter files (for the cases you used in your paper)

They can clone and run the GUI on their own machine. They only need custom OpenSees compilation if they explicitly want custom `MultiSurfCrack2D` built into their local OpenSees.