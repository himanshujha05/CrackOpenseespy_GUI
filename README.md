# Multi-Surf Crack 2D

Interactive 2D RC panel analysis tool with crack-interface modeling in OpenSeesPy.

## What this project does

This project gives you a desktop GUI to run nonlinear panel analysis without manually writing long OpenSees scripts.

You can:
- define panel geometry and mesh,
- place crack lines,
- assign crack material behavior,
- apply boundary conditions and loads,
- run analysis,
- view force-displacement and crack response plots.

Main app file: `gui_wsl.py`.

## Who this is for

- students validating panel behavior,
- researchers testing crack-interface settings,
- engineers building repeatable study cases.

## Quick start

### 1) Clone

```bash
git clone <your-repo-url>
cd multi-surf-crack2D
```

### 2) Create a virtual environment

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Run the GUI

```bash
python gui_wsl.py
```

Windows shortcut:

```powershell
.\run_gui.bat
```

## First run inside the GUI

Go to the Run tab and do this once:

1. Click `Auto-Detect`.
2. Select backend mode (`WSL` or `Local`) based on your machine.
3. Click `Validate Backend`.
4. Click `Run Analysis`.

If OpenSeesPy is installed in your local Python (not WSL), choose `Local` backend.

## Typical workflow

1. Geometry tab:
- set panel size and mesh density,
- add crack lines by typing Y values or using draw mode,
- assign BCs and loads.

2. Crack Materials tab:
- click `Refresh Crack Materials`,
- choose template material,
- edit selected crack rows if needed.

3. Analysis tab:
- choose `DisplacementControl` or `LoadControl`,
- set solver and convergence controls.

4. Run tab:
- validate backend,
- run analysis,
- monitor console log.

5. Results tab:
- inspect force-displacement,
- crack opening/slip histories,
- deformed mesh and contour,
- export PNG/CSV.

## Material models in the GUI

- `MultiSurfCrack2D`
- `EPPGap Macro (4-spring)`
- `Elastic`
- `ElasticPPGap`
- `CustomBilinear`

When `MultiSurfCrack2D` is not fully available in the runtime environment, the runner falls back to a stable interface model so the run can continue.

## Can others clone and run it?

Yes.

Most users only need:
- Python 3.10+,
- `pip install -r requirements.txt`,
- backend setup in the Run tab.

They do not need to compile custom code for normal GUI use.

## Do users need `build_msc2d.sh`?

Usually no.

`build_msc2d.sh` is only needed if someone specifically wants to compile custom `MultiSurfCrack2D` integration in their own OpenSees build.

## Work on this project (for contributors)

### Recommended dev flow

1. Create a branch.
2. Make small focused changes.
3. Run the GUI and test one analysis case.
4. Keep docs updated when behavior changes.

### Important files

- `gui_wsl.py`: main GUI and embedded runner logic
- `panel_analysis.py`: standalone analysis helper
- `multi-surf-crack2d.cpp` / `multi-surf-crack2d.h`: custom material source
- `SETUP_FOR_COLLABORATORS.md`: minimal setup handoff guide
- `PROJECT_DOCUMENTATION.md`: project-level technical summary

## Troubleshooting

If analysis does not start:

1. Check backend mode in Run tab.
2. Validate backend again.
3. Confirm OpenSeesPy is installed in the selected environment.
4. Review the run console and `run.log` in the run folder.

If crack plots are flat or empty:

1. Ensure crack lines exist in Geometry.
2. Regenerate mesh after crack edits.
3. Click `Refresh Crack Materials`.
4. Rerun analysis.

## Related docs

- `SETUP_FOR_COLLABORATORS.md`
- `PROJECT_DOCUMENTATION.md`
