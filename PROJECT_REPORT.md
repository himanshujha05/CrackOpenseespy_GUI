# 2D RC Panel Crack Analysis Tool — Project Report

## 1. Project Overview

This project implements a **GUI-based 2D Reinforced Concrete (RC) Panel Analysis Tool** for studying cyclic crack behavior using the finite element method. It is built around the **MultiSurfCrack2D** material model — a plasticity-based interface material developed to describe the cyclic response of cracks in reinforced concrete.

The tool enables a complete analysis workflow: defining panel geometry, placing cracks, assigning boundary conditions and loads, running nonlinear static FEM analysis via **OpenSeesPy**, and visualizing the results — all through an interactive desktop GUI.

**Key highlights:**
- Multiple-yield-surface formulation based on plasticity theory
- Crack-width-based yield surfaces
- Configuration-dependent behavior (aggregate interlock vs. free slip)
- Valid for flexural cracks, shear cracks, mixed-mode cracks, and crushing
- Zero-length node-to-node interface elements for crack representation
- Plane-stress triangular finite elements (tri31)

---

## 2. Architecture & Technology Stack

| Component | Technology |
|-----------|-----------|
| GUI Framework | PyQt5 (widgets, layouts, signals/slots) |
| FEM Solver | OpenSeesPy (running in WSL — Windows Subsystem for Linux) |
| Plotting | Matplotlib (embedded in Qt with interactive toolbar) |
| Numerical Computing | NumPy |
| Data Serialization | JSON (parameters), NPZ (results) |
| Platform | Windows GUI ↔ WSL backend (cross-platform bridge) |

### How the GUI Connects to the Solver

The GUI runs natively on Windows. When the user clicks **Run Analysis**, the tool:
1. Serializes all parameters (geometry, mesh, crack materials, BCs, loads, analysis settings) to a `params.json` file
2. Writes a standalone `runner.py` script into a timestamped run folder (`~/panel_analysis_runs/run_YYYYMMDD_HHMMSS`)
3. Spawns a **WSL subprocess** that activates the Python environment and executes the runner
4. The runner loads OpenSeesPy, builds the FE model, runs the analysis, and saves results to `results.npz`
5. The GUI reads back the results and populates the visualization plots

This Windows ↔ WSL bridge allows the GUI to leverage OpenSeesPy (which requires Linux compilation for the custom material) while keeping the user interface native on Windows.

---

## 3. GUI Structure & Behavior

The GUI uses a **dark theme** (GitHub-inspired color palette) with **6 tabs**, each handling a distinct phase of the analysis workflow.

### Tab 1: Geometry

**Purpose:** Define the RC panel, generate mesh, place cracks, assign boundary conditions and loads.

**Panel Definition:**
- Width (W), Height (H), Thickness (t) in meters
- Young's modulus (Ec) in MPa, Poisson's ratio (nu)

**Mesh Generation:**
- User sets grid subdivisions (nx, ny)
- Clicking "Generate Mesh" creates a structured triangular mesh (2 triangles per grid cell)
- The mesh is displayed on an interactive canvas on the right side

**Crack Placement (3 modes):**
- **Click Mode:** Click directly on the mesh canvas at the desired Y-position to add/remove horizontal crack lines
- **Hand Draw Mode:** Drag the mouse to sketch crack strokes; the tool auto-converts them to Y-positions
- **Manual Entry:** Type comma-separated Y-values in a text field

When a crack is placed at a Y-position, the mesh generator **duplicates the row of nodes** at that location — creating a "below" node and an "above" node at each crack position. These paired nodes are later connected by zero-length interface elements.

**Boundary Conditions:**
- Quick buttons: "Fix Bottom" (pins all nodes at y ≈ 0), "Roller Top" (fixes X-direction at y ≈ H)
- Per-node assignment: Select a node on the canvas, then toggle Fix X / Fix Y checkboxes
- A summary table shows all applied BCs

**Applied Loads:**
- Quick button: "Uniform Top Load" (distributes a total Fy equally among all top nodes)
- Per-node assignment: Select a node, enter Fx and Fy values (in kN)
- A summary table shows all applied loads

**Interactive Canvas Features:**
- Nodes are color-coded: blue (normal), green (selected), amber (fixed BC), red (loaded), orange/violet (crack below/above pairs)
- Triangular elements shown with gray outlines
- Crack lines drawn as thick red horizontal lines
- Load arrows and BC support symbols displayed
- Dimension labels (W, H) shown on the panel

### Tab 2: Crack Material Parameters

**Purpose:** Define the constitutive material model for each crack interface.

**Available Material Types:**
| Material | Description |
|----------|-------------|
| MultiSurfCrack2D | Plasticity-based model with multiple yield surfaces (requires custom OpenSees build) |
| Elastic | Simple linear spring with kn (normal) and kt (shear) stiffness |
| ElasticPPGap | Elastic perfectly-plastic with initial gap distance |
| CustomBilinear | Piecewise linear behavior (uses Steel01 internally) |

**Key Parameters:**
- kn: Normal stiffness (kN/m per link)
- kt: Shear/tangential stiffness (kN/m per link)
- gap: Initial gap distance (for ElasticPPGap)
- eta (η): Hardening ratio

**Auto kn/kt Calculator:**
Uses Divakar equations (Eq. 31/32) to compute stiffness values from concrete compressive strength (f'c) and initial crack width (w0).

**Workflow:** Click "Refresh from Geometry" to populate the per-crack table, configure the global template, then "Apply Material to All" to fill every crack row. Individual cracks can be fine-tuned by editing cells directly.

### Tab 3: Analysis Settings

**Purpose:** Configure the nonlinear static analysis parameters.

**Analysis Types:**
- **DisplacementControl:** Applies incremental displacement at a reference node (default). User sets displacement increment and target displacement.
- **LoadControl:** Applies incremental load scaling. User sets load increment fraction.

**Solver Configuration:**
- Algorithm: NewtonLineSearch (default), Newton, KrylovNewton, ModifiedNewton
- Convergence tolerance (default 1e-8)
- Maximum iterations per step (default 400)
- Load factor cap (stops analysis if exceeded)

**Built-in robustness:** If a step fails to converge, the runner automatically tries fallback algorithms and solver combinations (Constraints, System solvers, Test types with tolerance multipliers). If that also fails, it attempts step cutback (halving the increment, retrying up to 12 times).

### Tab 4: Run

**Purpose:** Execute the analysis, monitor progress in real time.

**WSL Environment Setup:**
- User specifies the activation command for the Python environment in WSL (e.g., `source ~/ops_env/bin/activate`)
- The tab auto-checks WSL and OpenSeesPy availability on startup

**Buttons:**
- **Run Analysis:** Validates the setup, creates a run folder, spawns a WSL worker thread, and streams console output in real time
- **Validate OpenSees Build:** Tests whether MultiSurfCrack2D material and zeroLengthND element are available
- **Run Integration Self-Test:** 3-part test (material → element → analysis) to confirm the custom material works correctly
- **Clear Console**

**Console output** shows: node/element counts, analysis progress, convergence info, and final status (SUCCESS / PARTIAL / FAILED).

### Tab 5: Results

**Purpose:** Visualize analysis outputs with interactive plots.

**7 Plot Types:**
1. **Force–Displacement Curve** — Global structural response
2. **Crack Opening History** — Normal opening at each crack vs. analysis step
3. **Crack Slip History** — Tangential slip at each crack vs. analysis step
4. **Crack Hysteresis (Slip vs. Force)** — Cyclic behavior at each crack interface
5. **Deformed Mesh** — Undeformed (faint) + deformed (bright) overlay with adjustable scale factor
6. **Displacement Magnitude Contour** — Filled contour plot with colorbar
7. **Crack Behavior Overlay** — Hand-drawn crack strokes overlaid on mesh, colored by metric (opening or slip), with a step slider

**Controls:** Crack filter dropdown (select individual crack or all), scale factor for deformed mesh, matplotlib navigation toolbar (pan, zoom, save PNG).

### Tab 6: Script

**Purpose:** Export a standalone Python script that can be run independently.

- **Generate/Refresh Script:** Creates a self-contained `.py` file with all parameters embedded
- **Copy to Clipboard / Save .py:** For sharing or running on a remote cluster
- The generated script can be executed anywhere OpenSeesPy is installed:
  ```
  python panel_analysis.py params.json results.npz
  ```

---

## 4. Finite Element Concepts Implemented

### 4.1 Mesh Generation
- The panel is discretized into a **structured triangular mesh** using `tri31` plane-stress elements
- Each rectangular grid cell is divided into 2 triangles
- At crack positions, nodes are **duplicated** to create discontinuities (below/above pairs)

### 4.2 Crack Interface Elements
- Cracks are modeled using **zero-length elements** connecting the duplicated node pairs
- Each zero-length element carries uniaxial material springs in the normal and tangential directions
- This approach captures crack opening (normal separation) and crack slip (tangential sliding) independently

### 4.3 MultiSurfCrack2D Material Model
The core scientific contribution. This plasticity-based model features:
- **Multiple yield surfaces** that capture the evolving response as cracks open and close
- **Crack-width-dependent** yield surface definitions
- **Aggregate interlock** behavior: resistance to shear sliding when crack faces are in contact
- **Free slip** behavior: reduced resistance when crack faces separate
- Handles general crack types: flexural, shear, mixed-mode, and crushing

### 4.4 Fallback Macro-Element
When MultiSurfCrack2D is not compiled into OpenSees, the tool provides an **EPPGap macro-element** fallback:
- 4 tangential (shear) springs with staggered gaps — approximates progressive engagement
- 1 normal spring — captures opening/closing behavior
- Uses `ElasticPPGap` uniaxial material for each spring

### 4.5 Analysis Procedure
- **Static nonlinear analysis** with either displacement control or load control
- Newton-family algorithms with automatic fallback
- Convergence based on NormUnbalance or NormDispIncr
- Step cutback for difficult convergence regions

### 4.6 Output Quantities
At each converged step, the solver records:
- Reference node displacement and total reaction force (for force-displacement curve)
- Per-crack normal opening (relative displacement in crack-normal direction)
- Per-crack tangential slip (relative displacement in crack-tangent direction)
- Full nodal displacement field at the last step (for deformed mesh and contour plots)

---

## 5. Scripts — Concepts, Implementation & How They Work

### 5.1 The Embedded Runner Script (`RUNNER_PY` inside `gui_wsl.py`)

The core computational engine is a **~700-line Python script embedded as a string constant** (`RUNNER_PY`) inside `gui_wsl.py`. This design means the GUI is fully self-contained — it carries its own solver logic and writes it to disk at runtime.

**Concept:** Separate the GUI (presentation layer) from the solver (computation layer). The GUI collects all user inputs into a single JSON parameter dictionary, then hands it to the runner script which executes inside WSL where OpenSeesPy is installed.

**How the runner script works step-by-step:**

```
params.json  →  runner.py (in WSL)  →  results.npz
                    │
                    ├── (A) Check if MultiSurfCrack2D is available in the OpenSees build
                    ├── (B) Run sanity checks on the model
                    │       - Validate element-node references
                    │       - Check boundary conditions prevent rigid body motion
                    │       - Verify reference node has a free DOF
                    │       - BFS connectivity check for isolated nodes
                    ├── (C) Sanitize crack links
                    │       - Deduplicate Y-positions within tolerance
                    │       - Remove self-links and duplicate pairs
                    ├── Build OpenSeesPy model
                    │       - Create nodes from mesh_nodes
                    │       - Apply boundary conditions (fix commands)
                    │       - Create tri31 plane-stress elements with ElasticIsotropic material
                    │       - Create crack interface elements (zero-length with springs)
                    │       - Apply loads (Linear time series + Plain pattern)
                    ├── (D) Run nonlinear static analysis with auto-recovery
                    │       - Step 0: Full recovery (try all solver combinations)
                    │       - Remaining steps: Fast path (algorithm fallback only)
                    │       - If step fails: Cutback (halve increment, retry up to 12×)
                    │       - If cutback fails: Full recovery again
                    │       - Collect displacement, force, crack opening, crack slip per step
                    └── (E) Save outputs
                            - results.npz (arrays: disp, force, crack data, node displacements)
                            - run.log (text log of all solver messages)
```

**Key implementation details in the runner:**

1. **Material Detection & Fallback:**
   - The runner first tries to create a test MultiSurfCrack2D nDMaterial
   - If the custom material is not compiled into OpenSees, it falls back to an **EPPGap macro-element**: 4 parallel shear springs with staggered gaps + 1 normal spring
   - This fallback still captures nonlinear crack behavior (gap opening, plastic slip) even without the full MultiSurfCrack2D model

2. **Crack Material Assignment:**
   - Each crack link reads its material type and parameters (kn, kt, gap, eta) from the `crack_mat_data` array
   - For `MultiSurfCrack2D` or `ElasticPPGap`: creates `ElasticPPGap` uniaxial materials
   - For `Elastic`: creates simple `Elastic` uniaxial springs
   - For `CustomBilinear`: creates `Steel01` bilinear materials
   - Springs are assigned to zero-length elements in directions 1 (tangential) and 2 (normal)

3. **Robust Convergence Strategy:**
   - **Algorithm fallback:** Tries NewtonLineSearch → ModifiedNewton → KrylovNewton → Newton
   - **Full recovery:** Tries combinations of Constraints (Plain, Transformation) × Systems (UmfPack, BandGeneral) × Algorithms × Tests (NormDispIncr, NormUnbalance with tolerance multipliers 1×, 10×, 100×)
   - **Step cutback:** Halves the displacement/load increment up to 12 times
   - This multi-level strategy ensures the analysis converges even for difficult nonlinear problems

4. **Output Collection:**
   - At each converged step, records reference node displacement and total reaction force
   - For each crack Y-position, computes average opening (normal relative displacement) and slip (tangential relative displacement) across all node pairs at that Y
   - At the final step, saves the full nodal displacement field for deformed mesh plots

### 5.2 File-by-File Breakdown

#### `gui_wsl.py` — Main GUI Application (3201 lines)

This is the primary file containing everything:

| Section | Lines | What It Does |
|---------|-------|-------------|
| Imports & Style | 1–100 | PyQt5, Matplotlib, NumPy imports; dark theme CSS stylesheet |
| Helper functions | 100–180 | `dsb()`, `isb()`, `mk_lbl()`, `sep()` — widget factory functions |
| `PanelMeshCanvas` | 180–570 | Custom QWidget for interactive 2D mesh visualization with mouse modes |
| `GeometryTab` | 570–950 | Panel definition, mesh generation, crack placement, BC/load assignment |
| `CrackMaterialTab` | 950–1200 | Material type selection, kn/kt calculator, per-crack parameter table |
| `AnalysisTab` | 1200–1400 | Analysis type, solver algorithm, tolerance, step configuration |
| `RunTab` | 1400–1700 | WSL environment config, run/validate/self-test buttons, console output |
| `ResultsTab` | 1700–1824 | 7 plot types with Matplotlib, crack filter, scale controls |
| `ScriptTab` | 1824–1854 | Script display editor, copy/save buttons |
| Self-Test functions | 1856–2080 | `run_comprehensive_self_test()`, `attempt_auto_fix()`, build validation |
| **`RUNNER_PY`** | **2081–2786** | **The embedded FEM solver script (described above)** |
| `WSLWorker` | 2792–2860 | QThread subclass — writes params/runner to disk, spawns WSL subprocess |
| `MainWindow` | 2860–3170 | Tab assembly, parameter collection (`_build_params()`), script generation |
| Entry point | 3177–3201 | `main()` — creates QApplication, applies style, shows window |

**How script generation works (Tab 6):**
- `_build_params()` collects all GUI state into a single Python dictionary
- The dictionary is JSON-serialized and embedded as `PARAMS = {...}` in the script header
- The full `RUNNER_PY` constant is appended after the header
- The result is a **completely self-contained Python file** that can run without the GUI

#### `opensees_model1.py` — 1D Rebar-with-Cracks Model (194 lines)

**Concept:** A simpler 1D predecessor script that models a vertical rebar with crack interfaces.

**How it works:**
- Creates a 1D column of truss elements along the Y-axis
- At each crack Y-position, duplicates the node (below/above) and inserts a zero-length crack element
- Rebar material options: `Elastic`, `ElasticPP` (elastic perfectly-plastic), `Steel02` (Giuffré-Menegotto-Pinto cyclic steel)
- Crack elements use simple `Elastic` springs for kn (normal) and kt (shear)
- Runs either LoadControl or DisplacementControl analysis
- Collects force-displacement curve and crack opening histories
- Saves results to `results.npz`
- Can be executed standalone: `python opensees_model1.py params.json results.npz`

**This script served as the prototype** for the more sophisticated 2D runner. The concepts of node duplication at cracks, zero-length interface elements, and the analysis/output collection pattern were first developed here and then extended to 2D.

#### `model.py` — Minimal OpenSeesPy Sanity Check (16 lines)

**Concept:** The simplest possible OpenSeesPy model — verifies that OpenSeesPy is correctly installed.

**What it does:**
- Creates 2 nodes and 1 elastic truss element
- Prints the OpenSeesPy version if successful
- Used to quickly test whether the WSL environment is working

### 5.3 The Scripting Concept — Design Philosophy

The project follows a **layered scripting architecture**:

```
Layer 3:  gui_wsl.py          ← Full interactive GUI (PyQt5)
              │                    Collects parameters → calls Layer 2
              │
Layer 2:  RUNNER_PY            ← Embedded FEM solver script
          (runner.py on disk)     Pure computation, no GUI dependency
              │                    Reads params.json → produces results.npz
              │
Layer 1:  opensees_model1.py   ← Prototype 1D model
          model.py                Development/testing scripts
```

**Why this design:**
1. **Separation of concerns:** The GUI handles user interaction; the runner handles computation. They communicate through JSON (in) and NPZ (out).
2. **Portability:** The exported script (from Tab 6) runs anywhere OpenSeesPy is installed — no PyQt5, no Windows, no WSL needed. This means users can run analyses on HPC clusters or share scripts with collaborators.
3. **Reproducibility:** Every run saves its `params.json` and `runner.py` in a timestamped folder, so any analysis can be exactly reproduced later.
4. **Incremental development:** The project evolved from `model.py` (basic test) → `opensees_model1.py` (1D prototype) → `RUNNER_PY` (full 2D solver) → `gui_wsl.py` (complete GUI wrapping everything).

---

## 6. End-to-End Workflow Summary

```
┌─────────────────────────────────────────────────────────┐
│                    USER WORKFLOW                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. GEOMETRY TAB                                        │
│     Define panel (W, H, t, Ec, nu)                      │
│     Generate triangular mesh (nx × ny grid)             │
│     Place horizontal crack lines (click/draw/type)      │
│     Assign boundary conditions (fix bottom, roller top) │
│     Apply loads (uniform top load or per-node)          │
│                                                         │
│  2. CRACK MATERIAL TAB                                  │
│     Select material model (MultiSurfCrack2D / Elastic / │
│       ElasticPPGap / CustomBilinear)                    │
│     Set stiffness parameters (kn, kt, gap, eta)         │
│     Apply to all cracks or fine-tune individually       │
│                                                         │
│  3. ANALYSIS SETTINGS TAB                               │
│     Choose DisplacementControl or LoadControl            │
│     Set increment, target, tolerance, algorithm          │
│                                                         │
│  4. RUN TAB                                             │
│     Verify WSL environment                              │
│     Click "Run Analysis"                                │
│     Monitor real-time console output                    │
│     Wait for SUCCESS / PARTIAL / FAILED status          │
│                                                         │
│  5. RESULTS TAB                                         │
│     View Force-Displacement curve                       │
│     Inspect crack opening and slip histories            │
│     Examine deformed mesh and displacement contours     │
│     Analyze crack hysteresis behavior                   │
│                                                         │
│  6. SCRIPT TAB                                          │
│     Export standalone Python script                     │
│     Run on remote cluster or share with collaborators   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 7. Technical Implementation Details

### GUI Implementation
- Built with **PyQt5** using a custom dark stylesheet (GitHub-inspired palette)
- The mesh canvas is a **custom QWidget** with full `paintEvent` rendering: triangles, color-coded nodes, crack lines, load arrows, BC symbols, dimension labels
- Three interaction modes on the canvas: node selection, crack placement (click), and freehand crack drawing
- Analysis runs on a **separate QThread** (WSLWorker) so the GUI remains responsive during computation
- Results are loaded from `.npz` files and plotted with **Matplotlib** embedded in Qt

### FEM Runner
- The runner is **embedded as a Python string constant** (~700 lines) inside `gui_wsl.py`
- It is written to disk alongside `params.json` before each run
- Includes comprehensive **sanity checks**: valid node references, sufficient BC constraints, free DOF at reference node, mesh connectivity
- **Crack link sanitization**: deduplicates Y-positions, removes self-links and duplicate pairs
- **Robust convergence strategy**: algorithm fallback → full solver-combination recovery → step cutback (up to 12 halvings)

### Cross-Platform Bridge (Windows ↔ WSL)
- Windows paths are converted to WSL format (`C:\Users\...` → `/mnt/c/Users/...`)
- The GUI spawns `wsl bash -lc "..."` subprocesses
- Output is captured and streamed to the console widget in real time
- Run folders are created under `~/panel_analysis_runs/` with timestamps

---

## 8. Summary

This project delivers a complete, interactive desktop tool for **2D reinforced concrete panel crack analysis**. It wraps a sophisticated finite element workflow — from mesh generation and crack placement to nonlinear analysis and result visualization — into an accessible GUI. The core innovation is the integration of the **MultiSurfCrack2D** plasticity-based material model, which captures realistic cyclic crack behavior including aggregate interlock and free-slip mechanics. The tool bridges Windows (GUI) and Linux (solver) seamlessly through WSL, and can also export standalone scripts for batch or remote execution.
