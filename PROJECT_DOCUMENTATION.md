# Project Documentation

## What This Project Is

This project is a desktop tool for 2D reinforced concrete panel analysis with explicit crack interfaces.

In practical terms, it helps you:
- create a panel model,
- place crack lines,
- assign crack material behavior,
- run nonlinear OpenSeesPy analysis,
- and visualize force-displacement and crack response results.

Main application file: `gui_wsl.py`.

## Main Idea

The panel body is modeled with `tri31` plane-stress triangles.
Each crack line is represented by duplicated node rows connected with zero-length interface elements.

This lets the model track two crack responses separately:
- opening (normal direction),
- slip (tangential direction).

## Technology Stack

- GUI: `PyQt5`
- Computation and plotting: `NumPy`, `Matplotlib`
- Nonlinear solver: `OpenSeesPy`
- Data exchange: `JSON` for inputs and `NPZ` for outputs

## Supported Crack Material Options

The GUI supports multiple interface models:
- `MultiSurfCrack2D` (custom integration path)
- `Elastic`
- `ElasticPPGap`
- `CustomBilinear`
- `EPPGap Macro (4-spring)` fallback behavior when needed

## How a Run Works (End to End)

1. You define geometry, mesh, cracks, BCs, loads, and analysis settings in the GUI.
2. The GUI writes a run folder with `params.json` and `runner.py`.
3. The backend executes `runner.py` in the selected environment.
4. The solver writes `results.npz` and `run.log`.
5. The GUI reads those results and updates plots in the Results tab.

## Reliability Features

The analysis runner includes several safety layers:
- solver/algorithm fallback sequences,
- recovery attempts with multiple test/system/constraint combinations,
- step cutback when a step does not converge,
- detailed run logs for troubleshooting.

Recent reliability improvements include safer crack-Y parsing, better material-row refresh behavior, and corrected self-test/recovery flow.

## Output Data You Get

Each completed run can provide:
- force-displacement history,
- crack opening history,
- crack slip history,
- deformed mesh,
- displacement contour,
- crack hysteresis and overlay views,
- CSV/PNG exports.

## File Guide

- `gui_wsl.py`: full GUI, runner template, worker logic, results plotting
- `panel_analysis.py`: standalone analysis script helper
- `multi-surf-crack2d.cpp` and `multi-surf-crack2d.h`: custom material source code
- `build_msc2d.sh`: optional custom build helper
- `run_gui.bat`: Windows launcher
- `README.md`: setup and usage guide
- `SETUP_FOR_COLLABORATORS.md`: quick handoff instructions

## Platform Notes

- Windows users can run with WSL backend or local Python backend.
- Linux/macOS users can run local backend.
- Backend selection is configured from the Run tab and can be auto-detected/validated.

## Scope and Limitations

- Crack insertion workflow is currently focused on horizontal crack rows.
- Some advanced material behavior depends on OpenSees build capabilities in the runtime environment.
- This tool is intended for research and engineering study. Validate against benchmark or reference cases before production-critical decisions.

## Handoff Summary

For normal use, collaborators can clone, install dependencies, select a working backend, and run.
`build_msc2d.sh` is only needed when a collaborator specifically wants to compile custom `MultiSurfCrack2D` integration on their own machine.
