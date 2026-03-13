# Multi-Surf Crack 2D — User Guide

A desktop app for analyzing cracked reinforced concrete panels.
No OpenSees scripting knowledge required.

---

## What Can I Do With This?

If you have a cracked concrete panel — a wall, a beam web, a column,
or a beam-column joint — this tool lets you:

- **Draw the crack** on a panel sketch (freehand, by clicking, or by
  tracing over a photo of the real crack)
- **Build a mesh** around it automatically
- **Assign crack material behavior** — choose how the crack resists
  sliding and opening forces
- **Apply loads and boundary conditions** by clicking on the mesh
- **Run a nonlinear analysis** and see how the crack responds
- **Plot results** — force vs displacement, crack opening, crack slip,
  deformed shape
- **Export a Python script** you can run independently

---

## What Do I Need to Install?

### On any machine (Windows, Mac, Linux)

You need:

- **Python 3.10 or 3.11**
  *(Python 3.12 has known issues with PyQt5 — use 3.10 or 3.11)*
- **Git** (to clone this repo)
- The Python packages listed in `requirements.txt`

You do NOT need to compile anything for basic use.

---

## How Do I Run It?

### Step 1 — Get the code

```bash
git clone <repo-url>
cd multi-surf-crack2D
```

### Step 2 — Create a Python environment and install packages

```bash
python -m venv .venv
pip install -r requirements.txt
```

### Step 3 — Install OpenSeesPy in your environment

```bash
pip install openseespy
```

### Step 4 — Launch the GUI

```bash
python gui_wsl.py
```

That is all. The GUI will open.

---

## Platform-Specific Instructions

### Windows

You have two options:

**Option A — Run everything on Windows directly (simplest)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install openseespy
python gui_wsl.py
```

In the GUI **Run tab**, set the activate command to:
```
.venv\Scripts\activate
```

**Option B — GUI on Windows, solver in WSL (recommended for MultiSurfCrack2D)**

1. Install WSL2 with Ubuntu from the Microsoft Store
2. Open Ubuntu terminal and run:

```bash
python3 -m venv ~/ops_env
source ~/ops_env/bin/activate
pip install openseespy
```

3. Launch the GUI from Windows as normal (`python gui_wsl.py`)
4. In the GUI **Run tab**, click **Auto-Detect** — it will find your
   WSL environment automatically

---

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install openseespy
python gui_wsl.py
```

In the GUI **Run tab**, set the activate command to:
```
source .venv/bin/activate
```

---

### Linux (Ubuntu / Debian)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install openseespy
python gui_wsl.py
```

In the GUI **Run tab**, set the activate command to:
```
source .venv/bin/activate
```

---

## Using the GUI — Step by Step

### ① Geometry Tab — Build your panel and draw the crack

1. Enter your panel **Width**, **Height**, and **Thickness** in meters
2. Set mesh density with **nx** (horizontal) and **ny** (vertical divisions)
3. Click **Generate Mesh** — a triangular mesh appears on the canvas
4. Add a crack line by one of these methods:
   - Type a Y position (height from base in meters) in the crack field
   - Click **Crack Mode** then click on the canvas at the crack height
   - Click **Hand Draw** and drag to sketch the crack freehand
   - Click **Upload Image** to load a photo and trace the crack on top
5. Assign boundary conditions:
   - Click **Fix Bottom** to pin all bottom nodes (typical wall setup)
   - Or click individual nodes on the canvas and check Fix X / Fix Y
6. Assign loads:
   - Click **Uniform Top Load** and enter a total force value, or
   - Click individual nodes and enter Fx / Fy values directly

---

### ② Crack Materials Tab — Choose how each crack behaves

1. Click **Refresh from Geometry** to populate the crack element table
2. Use the **Template** section to set default properties for all cracks
3. Click any row to override that specific crack element individually
4. Choose a material type:

| Material | What it does | Requires custom build? |
|---|---|---|
| `Elastic` | Linear spring | No |
| `ElasticPPGap` | Elastic until gap opens | No |
| `EPPGap Macro (4-spring)` | Realistic cyclic crack hysteresis | No — **recommended** |
| `CustomBilinear` | User-defined curve | No |
| `MultiSurfCrack2D` | Full plasticity model (Galik et al.) | Yes — see below |

5. Set **crack width** (mm) and **orientation** (degrees) per element

---

### ③ Analysis Tab — Set up loading

- **Monotonic** — push in one direction to a target displacement
- **Reversed-Cyclic** — push-pull cycles, like earthquake loading
- Control method: **DisplacementControl** (recommended) or **LoadControl**
- Advanced: solver, algorithm, tolerance, max iterations

---

### ④ Run Tab — Run the analysis

1. Click **Auto-Detect** to find your OpenSeesPy installation
2. Click **Validate Backend** to confirm it works
3. Click **▶ Run Analysis**
4. Watch live output in the console
5. Errors are shown with exact messages if something goes wrong

---

### ⑤ Results Tab — View what happened

- **Force vs Displacement** — overall panel response
- **Crack Opening (w)** — how each crack opened over load steps
- **Crack Slip (s)** — how each crack slid over load steps
- **Deformed Mesh** — visual of panel deformation
- **Contour Plot** — displacement or stress field
- **Click any crack marker** on the canvas → full response history popup
- **Save PNG** or **Export CSV** from the toolbar

---

### ⑥ Script Tab — Get the OpenSeesPy script

- View the full generated Python script for your model
- **Copy** to clipboard or **Save** as a `.py` file
- The saved script runs independently on any machine with OpenSeesPy

---

## Do I Need to Compile Anything?

**No — for most users.**

`pip install openseespy` gives you everything needed for `Elastic`,
`ElasticPPGap`, `EPPGap Macro (4-spring)`, and `CustomBilinear`.

**Only if you need `MultiSurfCrack2D`:**

```bash
bash build_msc2d.sh
```

This compiles the custom material into OpenSees from source.
Requires WSL on Windows, or Linux/macOS terminal.
See `SETUP_FOR_COLLABORATORS.md` for full instructions.

> If `MultiSurfCrack2D` is selected but not available, the runner
> automatically falls back to `EPPGap Macro` so your run still completes.

---

## Where Are My Files?

| What | Where |
|---|---|
| Analysis runs | `~/panel_analysis_runs/run_YYYYMMDD_HHMMSS/` |
| Backend settings | `panel_gui_config.json` (project folder, not tracked by git) |
| Exported scripts | Your choice via Save dialog |
| Exported plots / CSV | Your choice via Save dialog |

---

## Troubleshooting

**GUI does not open**
→ Check Python version (`python --version`) — must be 3.10 or 3.11
→ Check PyQt5 is installed: `pip show PyQt5`

**"No module named openseespy"**
→ Run `pip install openseespy` in the same environment as the GUI

**Analysis fails immediately**
→ Run tab → click **Validate Backend** and check the error message
→ Make sure the activate command matches your environment path

**"MultiSurfCrack2D is unknown"**
→ Your OpenSees does not have the custom material
→ Switch to `EPPGap Macro (4-spring)` for the same run, or
→ Follow the build instructions in `SETUP_FOR_COLLABORATORS.md`

**Analysis runs but does not converge**
→ Reduce displacement increment in the Analysis tab
→ Switch algorithm to KrylovNewton
→ Reduce total load magnitude



