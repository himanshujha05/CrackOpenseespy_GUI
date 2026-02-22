# MultiSurfCrack2D Integration into GUI

**Date:** February 2026
**Status:** ✅ INTEGRATED

---

## What Was Done

Your **custom multi-surface crack plasticity model** (`MultiSurfCrack2D`) has been **integrated into the 2D panel analysis GUI** (`gui_wsl.py`). The GUI now supports using your advanced material model alongside standard OpenSees materials.

---

## Key Integration Points

### 1. Material Selection in GUI

**Location:** Crack Materials Tab → Template Material Type dropdown

**Options available:**
- ✅ **MultiSurfCrack2D** (NEW - your custom model)
- Elastic (standard)
- ElasticPPGap (standard)
- CustomBilinear (standard)

**Default:** MultiSurfCrack2D (assumes your model is compiled)

---

### 2. Material Parameters

The GUI accepts both **generic parameters** and **MultiSurfCrack2D-specific parameters**:

#### Generic Parameters (all models)
- `mat_type`: Material class name
- `kn`: Normal stiffness (kN/m)
- `kt`: Shear stiffness (kN/m)
- `gap`: Gap before engagement (m) — *optional, for ElasticPPGap*
- `eta`: Hardening ratio — *optional, for bilinear*

#### MultiSurfCrack2D-Specific Parameters
When `mat_type = "MultiSurfCrack2D"`, the runner also accepts:

```python
# From crack_mat_data dictionary:
{
    "y": 1.0,                    # crack Y position (m)
    "mat_type": "MultiSurfCrack2D",
    "kn": 210.0,                 # normal stiffness (kN/m)
    "kt": 5.95,                  # shear stiffness (kN/m)

    # MultiSurfCrack2D parameters:
    "fc": 30.0,                  # concrete strength (MPa)
    "ag": 25.0,                  # max aggregate diameter (mm)
    "fcl": 5.0,                  # crack closure stress (MPa)
    "Acr": 1.0,                  # nominal crack area
    "rho_lok": 0.5,              # interlock dilation parameter
    "chi_lok": 0.3,              # interlock cohesion ratio
    "rho_act": 0.5,              # rubble dilation parameter
    "mu": 0.7,                   # friction coefficient
    "chi": 0.5,                  # unloading cohesion ratio
    "zeta": 0.3,                 # slip break point (pinching)
    "kappa": 1.0,                # roughness transition parameter
    "theta": 0.785,              # average contact angle (radians)
    "w0": 0.01,                  # initial crack width (mm)
    "cPath": 0                   # 1=width-constant path, 0=otherwise
}
```

---

## How It Works in the Runner

### Code Location
**File:** `gui_wsl.py` lines 1643-1720
**Function:** `run_model_2d(p)` in RUNNER_PY

### Flow

```python
for ci, cp in enumerate(crack_pairs):
    nb = int(cp[0]); na = int(cp[1]); yc = float(cp[2])

    cm = _find_mat(round(yc, 6))  # get parameters from crack_mat_data
    mat_type = str(cm.get('mat_type', 'MultiSurfCrack2D'))  # default

    if 'multisurfcrack2d' in mat_type.lower():
        # Extract MultiSurfCrack2D parameters
        fc = cm.get('fc', 30.0)
        ag = cm.get('ag', 25.0)
        # ... (10 more parameters)

        try:
            # Create NDMaterial
            ops.nDMaterial('MultiSurfCrack2D', mat_id,
                          kn, kt, 0.0,      # De (elastic loading stiffness)
                          kn, kt, 0.0,      # DeU (elastic unloading stiffness)
                          fc, ag, fcl, Acr,
                          rho_lok, chi_lok, rho_act, mu, chi,
                          zeta, kappa, theta, w0, cPath)

            # Use it in zeroLength element
            ops.element('zeroLength', elt_id, nb, na,
                        '-mat', mat_id, '-dir', 1, 2)

        except Exception as e:
            # Fallback: MultiSurfCrack2D not available
            print(f"[WARNING] MultiSurfCrack2D not available: {e}")
            print(f"[FALLBACK] Using Elastic materials for crack {ci}")
            # Use standard Elastic instead
            ops.uniaxialMaterial('Elastic', mat_id*2, kt)
            ops.uniaxialMaterial('Elastic', mat_id*2+1, kn)
            ops.element('zeroLength', elt_id, nb, na,
                        '-mat', mat_id*2, mat_id*2+1, '-dir', 1, 2)
    else:
        # Use standard OpenSees materials (Elastic, ElasticPPGap, Steel01)
        # (existing logic unchanged)
```

---

## Requirements to Use MultiSurfCrack2D

### 1. Compile into OpenSees

Your material model **must be compiled into OpenSeesPy**. This requires:

1. **Have C++ source files:**
   - ✓ `multi-surf-crack2d.h` (already in project)
   - ✓ `multi-surf-crack2d.cpp` (already in project)

2. **Follow OpenSees compilation instructions:**
   - See: [RESSLab OpenSees Instructions](https://github.com/RESSLab-Team/OpenSees-Instructions)
   - See: [Compiling OpenSeesPy video](https://www.youtube.com/watch?v=l5-vJDZR_hA&list=PL3UAqrcSdYPwu7H_F5HSTvKAUtLxCLxsu)

3. **Replace the default OpenSeesPy installation** with your compiled version

### 2. Verify Installation

Test in WSL/Python:
```python
import openseespy.opensees as ops
ops.wipe()
ops.model('basic', '-ndm', 2, '-ndf', 2)

# Try to create the material
ops.nDMaterial('MultiSurfCrack2D', 1,
               210, 5.95, 0.0,   # kn, kt, De_12
               210, 5.95, 0.0,   # DeU
               30, 25, 5, 1.0,
               0.5, 0.3, 0.5, 0.7, 0.5,
               0.3, 1.0, 0.785, 0.01, 0)

print("SUCCESS: MultiSurfCrack2D available in OpenSees")
```

If you get an error like `"Unknown material type: MultiSurfCrack2D"`, you need to recompile OpenSees with the material included.

---

## User Workflow

### Step 1: Generate Mesh
```
① Geometry tab
   ├─ Set panel: W=1.0m, H=2.0m, nx=6, ny=12
   ├─ Enter cracks: "0.5, 1.0, 1.5"
   └─ Click "Generate Mesh"
      └─ Canvas shows 2D mesh with colored crack nodes
```

### Step 2: Assign Crack Materials
```
② Crack Materials tab
   ├─ Click "Refresh from Geometry"
   ├─ Material type: select "MultiSurfCrack2D"
   │  └─ Or: select "Elastic" if model not compiled
   ├─ Set parameters:
   │  ├─ kn = 210 (normal stiffness)
   │  ├─ kt = 5.95 (shear stiffness)
   │  └─ (others use defaults)
   ├─ Optional: edit per-crack parameters in table
   └─ Click "Apply Material to All"
```

### Step 3: Configure Analysis
```
③ Analysis tab
   ├─ DisplacementControl / LoadControl
   ├─ Algorithm: NewtonLineSearch
   └─ Tolerances: 1e-8, max 400 iterations
```

### Step 4: Run Analysis
```
④ Run tab
   ├─ Verify WSL activation command
   └─ Click "▶ Run Analysis"
      └─ OpenSeesPy creates model:
         ├─ Nodes (all original + duplicated)
         ├─ Triangles (split connectivity)
         ├─ MultiSurfCrack2D materials (if available)
         │  └─ OR fallback to Elastic (if not available)
         ├─ Runs static analysis with fallback convergence
         └─ Saves results
```

### Step 5: View Results
```
⑤ Results tab
   ├─ Force–Displacement curve
   ├─ Crack Opening History
   │  └─ Shows opening computed in local crack axes
   ├─ Crack Slip History
   │  └─ Shows slip computed in local crack axes
   ├─ Deformed Mesh
   └─ Displacement Magnitude Contour
```

---

## Error Handling & Fallback

### If MultiSurfCrack2D Not Available

**Console output:**
```
[WARNING] MultiSurfCrack2D not available: Unknown material type "MultiSurfCrack2D"
[FALLBACK] Using Elastic materials for crack 0
```

**Result:** Analysis still runs using standard Elastic materials (kn, kt as tangential/normal stiffness)

**Resolution:** Recompile OpenSees with the material included

---

## Data Structure

### Parameters Dictionary (JSON format)

```json
{
  "panel_W": 1.0,
  "panel_H": 2.0,
  "panel_t": 0.2,
  "panel_Ec": 30000,
  "panel_nu": 0.2,
  "mesh_nodes": {
    "1": [0.0, 0.0],
    "2": [0.167, 0.0],
    ...
  },
  "mesh_tris": [
    [1, 1, 2, 5],
    [2, 1, 5, 4],
    ...
  ],
  "mesh_crack_pairs": [
    [9, 10, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0],
    [11, 12, 1.0, 0.167, 1.0, 0.0, 0.0, 1.0],
    ...
  ],
  "crack_mat_data": [
    {
      "y": 1.0,
      "mat_type": "MultiSurfCrack2D",
      "kn": 210,
      "kt": 5.95,
      "fc": 30.0,
      "ag": 25.0,
      "fcl": 5.0,
      "Acr": 1.0,
      "rho_lok": 0.5,
      "chi_lok": 0.3,
      "rho_act": 0.5,
      "mu": 0.7,
      "chi": 0.5,
      "zeta": 0.3,
      "kappa": 1.0,
      "theta": 0.785,
      "w0": 0.01,
      "cPath": 0
    }
  ],
  "bc_nodes": {"1": [1, 1]},
  "load_nodes": {"25": [0.0, -1000]},
  "analysis_type": "DisplacementControl",
  "disp_incr": 0.0005,
  "target_disp": 0.05,
  "algorithm": "NewtonLineSearch",
  "tol": 1e-8,
  "max_iter": 400
}
```

---

## Technical Details

### Material Class Definition (from multi-surf-crack2d.h)

```cpp
class MultiSurfCrack2D: public NDMaterial
{
    // Constructor parameters:
    Matrix De,             // elastic loading stiffness (2x2)
    Matrix DeU,            // elastic unloading stiffness (2x2)
    double user_fc,        // concrete strength (MPa)
    double user_ag,        // max aggregate diameter (mm)
    double user_fcl,       // crack closure stress (MPa)
    double user_Acr,       // nominal crack area
    double user_rho_lok,   // interlock dilation parameter
    double user_chi_lok,   // interlock cohesion ratio
    double user_rho_act,   // rubble dilation parameter
    double user_mu,        // friction coefficient
    double user_chi,       // unloading cohesion ratio
    double user_zeta,      // slip break point
    double user_kappa,     // roughness transition parameter
    double user_theta,     // average contact angle (radians)
    double user_w,         // initial crack width (mm)
    int cPath              // load path flag
};
```

### OpenSees Command in RUNNER_PY

```python
ops.nDMaterial('MultiSurfCrack2D', mat_id,
               kn, kt, 0.0,           # De_11, De_22, De_12
               kn, kt, 0.0,           # DeU_11, DeU_22, DeU_12
               fc, ag, fcl, Acr,
               rho_lok, chi_lok, rho_act, mu, chi,
               zeta, kappa, theta, w0, cPath)
```

### Zero-Length Element Configuration

```python
ops.element('zeroLength', elt_id, nb, na,
            '-mat', mat_id, '-dir', 1, 2)
```

- **Materials:** `mat_id` is an NDMaterial (MultiSurfCrack2D)
- **Directions:** 1=X (global), 2=Y (global)
- **Node pair:** `(nb, na)` = (below-crack node, above-crack node)

---

## Testing

### 1. Verify OpenSees Compilation

```bash
# In WSL or native Python with OpenSeesPy
python3 -c "
import openseespy.opensees as ops
ops.wipe()
ops.model('basic', '-ndm', 2, '-ndf', 2)
try:
    ops.nDMaterial('MultiSurfCrack2D', 1, 210, 5.95, 0, 210, 5.95, 0, 30, 25, 5, 1, 0.5, 0.3, 0.5, 0.7, 0.5, 0.3, 1.0, 0.785, 0.01, 0)
    print('OK: MultiSurfCrack2D available')
except Exception as e:
    print(f'NOT AVAILABLE: {e}')
"
```

### 2. Test Full GUI Workflow

1. Start GUI: `python run_gui.bat`
2. Generate mesh (default settings)
3. Crack Materials: select "MultiSurfCrack2D"
4. Set kn=210, kt=5.95
5. Assign BC + loads
6. Run Analysis
7. Check console for success/fallback messages

### 3. Expected Results

**If MultiSurfCrack2D compiled:**
```
Console: (no warnings, just normal OpenSees output)
Results: Crack opening/slip computed using MultiSurfCrack2D stiffness
```

**If MultiSurfCrack2D not compiled:**
```
Console: [WARNING] MultiSurfCrack2D not available
         [FALLBACK] Using Elastic materials for crack 0
Results: Analysis still runs with Elastic materials
```

---

## Compilation Instructions

To compile MultiSurfCrack2D into OpenSeesPy:

1. **Get OpenSees source code:**
   ```bash
   git clone https://github.com/OpenSees/OpenSees.git
   cd OpenSees
   ```

2. **Add your material files:**
   ```bash
   # Copy multi-surf-crack2d.h and multi-surf-crack2d.cpp
   cp /path/to/multi-surf-crack2d.h SRC/material/nD/
   cp /path/to/multi-surf-crack2d.cpp SRC/material/nD/
   ```

3. **Register in Tcl_Wrapper.cpp:**
   - Add `extern int TclCommand_addMultiSurfCrack2D(...)`
   - Add to dispatcher logic

4. **Update CMakeLists.txt:**
   - Add source files to `ndMaterial_SOURCES`

5. **Build:**
   ```bash
   mkdir build && cd build
   cmake ..
   cmake --build . -j4
   ```

6. **Install:**
   ```bash
   pip install /path/to/compiled/openseespy
   ```

See: [RESSLab OpenSees Instructions](https://github.com/RESSLab-Team/OpenSees-Instructions)

---

## Summary

✅ **Integration Complete:**
- MultiSurfCrack2D now available in Crack Materials dropdown
- Parameters accepted and passed to OpenSees
- Fallback to Elastic if model not compiled
- Full 2D mesh support with proper crack node splitting
- Local-axis opening/slip computation (dot products)

✅ **Ready for:**
- Custom material research
- Advanced crack mechanics analysis
- Cyclic loading with multi-surface plasticity

⚠️ **Requires:**
- OpenSees recompilation with material source code
- See compilation instructions above

---

**Status:** Production Ready
**Date:** February 2026
