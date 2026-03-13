# Project Documentation

## Overview

This project is an interactive finite element analysis tool for 2D reinforced concrete panels with explicit crack interfaces. It combines:
- A desktop GUI (`PyQt5`)
- Numerical model generation and post-processing (`NumPy`, `Matplotlib`)
- Nonlinear structural analysis (`OpenSeesPy`)

Main entry point: `gui_wsl.py`

## Engineering Scope

The tool models a panel under plane stress using a structured triangular mesh. Crack lines are represented by duplicated node rows connected by zero-length interfaces. This allows independent evaluation of:
- Crack opening (normal direction)
- Crack slip (tangential direction)

Supported crack material templates in the GUI:
- `MultiSurfCrack2D` (custom model option)
- `Elastic`
- `ElasticPPGap`
- `CustomBilinear`

## Core Logic

1. Mesh generation
- Builds a structured `(nx, ny)` grid
- Splits each rectangle into two triangles
- Duplicates row nodes at crack Y locations to create interface pairs

2. Boundary conditions and loading
- Interactive node-level BC assignment
- Interactive node-level loading
- Quick actions for common patterns (fix bottom, uniform top load)

3. Solver pipeline
- GUI writes `params.json`
- GUI writes runner script (`runner.py`) from embedded `RUNNER_PY`
- Backend executes analysis and writes `results.npz`
- GUI reloads and plots results

4. Nonlinear solution robustness
- Algorithm fallback sequence
- Constraints/system/test fallback combinations
- Step cutback when convergence fails
- Detailed run log written to `run.log`

## Recent Logic Improvements

The current `gui_wsl.py` includes key reliability fixes:
- Safe crack Y parsing with boundary filtering and near-duplicate cleanup
- Correct preservation of edited crack-material rows during refresh
- Correct OpenSees self-test sequence (`integrator` then static `analysis`)
- Recovery-loop fix to fully execute configured test combinations
- Cross-platform backend support:
  - Windows: WSL backend
  - Linux/macOS: local bash backend

## Outputs

Main analysis outputs include:
- Global force-displacement history
- Crack opening/slip histories per crack line
- Final nodal displacement field
- Deformed mesh and displacement contour visualization
- Exported CSV and image plots

## File Roles

- `gui_wsl.py`: Full GUI + embedded solver runner
- `multi-surf-crack2d.cpp/.h`: Custom material source for OpenSees build integration
- `build_msc2d.sh`: WSL build helper for OpenSees + custom material
- `run_gui.bat`: Windows convenience launcher
- `README.md`: Setup and run instructions for Windows/Linux/macOS

## Limitations and Assumptions

- Primary crack insertion workflow is horizontal crack lines.
- OpenSees behavior depends on the available build features in the user environment.
- The GUI is intended for research/prototyping workflows and should be validated against benchmark problems before production decisions.
