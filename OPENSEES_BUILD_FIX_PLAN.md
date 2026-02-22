# OpenSees Build Fix Plan: MultiSurfCrack2D Integration
**Date:** February 21, 2026
**Goal:** Compile MultiSurfCrack2D into OpenSeesPy so `ops.nDMaterial('MultiSurfCrack2D', ...)` works without fallback

---

## Current Problem
```
WARNING material type MultiSurfCrack2D is unknown
[FALLBACK REASON] MultiSurfCrack2D not in OpenSees build
```

**Root Cause:** Material not registered in OpenSees build system.

---

## Solution Overview

### Files to Integrate
- **Source:** `c:\Users\himan\multi-surf-crack2D\multi-surf-crack2d.cpp` (38KB)
- **Header:** `c:\Users\himan\multi-surf-crack2D\multi-surf-crack2d.h` (10KB)
- **In WSL:** `/mnt/c/Users/himan/multi-surf-crack2D/`

### Key Details from Source Code

**Class Definition:**
- Class: `MultiSurfCrack2D` extends `NDMaterial`
- Type name: `"MultiSurfCrack2D"`
- Tag ID: `ND_TAG_MultiSurfCrack2D` (needs to be defined)
- Material Factory Function: `void* OPS_MultiSurfCrack2D()` (lines 19-66)
- Parameters: 21 doubles + 1 optional int (23 args total)

**Constructor Signature:**
```cpp
MultiSurfCrack2D(int tag,
    Matrix De,           // elastic loading stiffness (2x2)
    Matrix DeU,          // elastic unloading stiffness (2x2)
    double fc,           // concrete strength (MPa)
    double ag,           // aggregate diameter (mm)
    double fcl,          // crack closure stress (MPa)
    double Acr,          // nominal crack area
    double rho_lok,      // interlock dilation parameter
    double chi_lok,      // interlock cohesion ratio
    double rho_act,      // rubble dilation parameter
    double mu,           // friction coefficient
    double chi,          // unloading cohesion ratio
    double zeta,         // slip break point
    double kappa,        // roughness transition
    double theta,        // contact angle (radians)
    double w0,           // initial crack width (mm)
    int cPath);          // 0=default, 1=width-constant
```

---

## STEP-BY-STEP FIX

### STEP 1: Setup OpenSees Source in WSL

**Command:**
```bash
wsl bash -c "
cd ~
git clone --depth 1 https://github.com/OpenSees/OpenSees.git
cd OpenSees
echo 'OpenSees cloned: ready for modification'
"
```

**Expected Output:**
```
Cloning into 'OpenSees'...
[Progress messages...]
OpenSees cloned: ready for modification
```

**Time:** ~2-3 minutes (depends on network)

---

### STEP 2: Copy MultiSurfCrack2D Source Files

**Commands:**
```bash
wsl bash -c "
cp /mnt/c/Users/himan/multi-surf-crack2D/multi-surf-crack2d.h ~/OpenSees/SRC/material/nD/
cp /mnt/c/Users/himan/multi-surf-crack2D/multi-surf-crack2d.cpp ~/OpenSees/SRC/material/nD/
echo 'Files copied to SRC/material/nD/'
ls -lh ~/OpenSees/SRC/material/nD/multi-surf*
"
```

**Expected Output:**
```
Files copied to SRC/material/nD/
-rw-r--r--  1 himan himan  10020 Feb 21 XX:XX /home/himan/OpenSees/SRC/material/nD/multi-surf-crack2d.h
-rw-r--r--  1 himan himan  38279 Feb 21 XX:XX /home/himan/OpenSees/SRC/material/nD/multi-surf-crack2d.cpp
```

---

### STEP 3: Define Material Tag in NDMaterial.h

**File:** `~/OpenSees/SRC/material/nD/NDMaterial.h`

**Find line with other ND_TAG definitions, e.g.:**
```cpp
#define ND_TAG_DruckerPragerPlaneStrain    7777
#define ND_TAG_PlanStrainMaterial 7778
```

**Add after existing tags (e.g., after line ~100):**
```cpp
#define ND_TAG_MultiSurfCrack2D            8899
```

**Full Edit Command:**
```bash
wsl bash -c "
grep -n 'define ND_TAG' ~/OpenSees/SRC/material/nD/NDMaterial.h | tail -5
"
```

This shows where to add it. Then:

```bash
wsl bash -c "
# Find the line number of the last ND_TAG definition
last_tag_line=\$(grep -n 'define ND_TAG' ~/OpenSees/SRC/material/nD/NDMaterial.h | tail -1 | cut -d: -f1)
echo \"Last ND_TAG at line: \$last_tag_line\"

# Add our new tag after it
sed -i \"\${last_tag_line}a #define ND_TAG_MultiSurfCrack2D            8899\" ~/OpenSees/SRC/material/nD/NDMaterial.h

# Verify
grep -A 1 'ND_TAG_MultiSurfCrack2D' ~/OpenSees/SRC/material/nD/NDMaterial.h
"
```

---

### STEP 4: Register Material in NDMaterialFactory (C++ Factory Code)

**File:** `~/OpenSees/SRC/material/nD/materialpackage.cpp`

**Find the section with existing materials, e.g.:**
```cpp
extern void* OPS_ElasticIsotropic();
extern void* OPS_ElasticOrthotropic();
extern void* OPS_DruckerPrager();
...
```

**Add near the top of the extern declarations:**
```cpp
extern void* OPS_MultiSurfCrack2D();
```

**Then find the dispatcher section (usually a big if/else or map), e.g.:**
```cpp
if (strcmp(argv[0], "ElasticIsotropic") == 0)
    return (OPS_ElasticIsotropic)();
else if (strcmp(argv[0], "ElasticOrthotropic") == 0)
    return (OPS_ElasticOrthotropic)();
...
```

**Add before the final `else` (so it catches "MultiSurfCrack2D"):**
```cpp
else if (strcmp(argv[0], "MultiSurfCrack2D") == 0)
    return ((void *)new MultiSurfCrack2D());
```

**Alternative: If using a map/registry system, add:**
```cpp
theMaterials->add("MultiSurfCrack2D", OPS_MultiSurfCrack2D);
```

**Finding the exact location:**
```bash
wsl bash -c "
grep -n 'OPS_Elastic' ~/OpenSees/SRC/material/nD/materialpackage.cpp | head -5
grep -n 'strcmp.*ElasticIsotropic' ~/OpenSees/SRC/material/nD/materialpackage.cpp | head -2
"
```

---

### STEP 5: Update CMakeLists.txt to Compile Multi SurfCrack2D

**File:** `~/OpenSees/SRC/material/nD/CMakeLists.txt`

**Find section with material sources:**
```cmake
set(MATERIAL_NDMATERIAL_SOURCES
    ...
    Elastic3D.cpp
    DruckerPrager.cpp
    ...
)
```

**Add our file:**
```cmake
    MultiSurfCrack2D.cpp
```

**Auto-add script:**
```bash
wsl bash -c "
# Check if already there
if ! grep -q 'MultiSurfCrack2D.cpp' ~/OpenSees/SRC/material/nD/CMakeLists.txt; then
    # Find the MATERIAL_NDMATERIAL_SOURCES line
    start_line=\$(grep -n 'set(MATERIAL_NDMATERIAL_SOURCES' ~/OpenSees/SRC/material/nD/CMakeLists.txt | head -1 | cut -d: -f1)
    # Find the corresponding closing paren
    end_line=\$((start_line + 50))  # search next 50 lines
    insert_line=\$(sed -n \"\${start_line},\${end_line}p\" ~/OpenSees/SRC/material/nD/CMakeLists.txt | grep -n ')' | head -1 | cut -d: -f1)
    insert_line=\$((start_line + insert_line - 2))

    # Insert before the closing paren
    sed -i \"\${insert_line}a \    MultiSurfCrack2D.cpp\" ~/OpenSees/SRC/material/nD/CMakeLists.txt
    echo \"Added MultiSurfCrack2D.cpp to CMakeLists.txt at line \$insert_line\"
else
    echo \"MultiSurfCrack2D.cpp already in CMakeLists.txt\"
fi

# Verify
grep 'MultiSurfCrack2D.cpp' ~/OpenSees/SRC/material/nD/CMakeLists.txt
"
```

---

### STEP 6: Build OpenSeesPy

**Commands:**
```bash
wsl bash -c "
cd ~/OpenSees
mkdir -p build
cd build

# Configure with OpenSeesPy support
cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DOpenSees_BUILD_PYTHON=ON \
  -DOpenSees_PYTHON_VERSION=3.12

# Build (this takes 10-30 minutes depending on system)
cmake --build . -j4

echo '===== BUILD COMPLETE ====='
ls -lh lib/opensees.so 2>/dev/null || echo 'Not built as .so (may be in site-packages)'
"
```

**Expected Output:**
```
===== BUILD COMPLETE =====
[Possibly a .so file listing]
```

**Time:** 10-30 minutes

---

### STEP 7: Install OpenSeesPy to venv

**Commands:**
```bash
wsl bash -c "
source ~/ops_env/bin/activate

cd ~/OpenSees/build

# Install the compiled version
pip install -e .

echo '===== INSTALLATION COMPLETE ====='
"
```

**Expected Output:**
```
Processing /home/himan/OpenSees
Installing collected packages: openseespy
  Running setup.py develop for openseespy
Successfully installed openseespy
===== INSTALLATION COMPLETE =====
```

---

### STEP 8: Verify MultiSurfCrack2D is Available

**Test Script:** Run this in WSL:

```bash
wsl bash -c "
source ~/ops_env/bin/activate

python3 << 'PYTEST'
import openseespy.opensees as ops

print('[TEST] Creating OpenSees model...')
ops.wipe()
ops.model('basic', '-ndm', 2, '-ndf', 2)

print('[TEST] Attempting to create MultiSurfCrack2D material...')
try:
    ops.nDMaterial('MultiSurfCrack2D', 1,
        210, 5.95, 0,      # De: kn, kt, De_12
        210, 5.95, 0,      # DeU: kn, kt, DeU_12
        30, 25, 5, 1,      # fc, ag, fcl, Acr
        0.5, 0.3, 0.5, 0.7, 0.5,  # rho_lok, chi_lok, rho_act, mu, chi
        0.3, 1.0, 0.785, 0.01,    # zeta, kappa, theta, w0
        0)                 # cPath
    print('[PASS] ✓ MultiSurfCrack2D material created successfully!')
except Exception as e:
    print(f'[FAIL] ✗ MultiSurfCrack2D failed: {e}')
    import traceback
    traceback.print_exc()

# Check stderr for warnings
print('[TEST] Check above for \"WARNING material type\" messages')
print('[TEST] If none: MultiSurfCrack2D is properly registered!')
PYTEST
"
```

**Expected Output:**
```
[TEST] Creating OpenSees model...
[TEST] Attempting to create MultiSurfCrack2D material...
[PASS] ✓ MultiSurfCrack2D material created successfully!
[TEST] Check above for "WARNING material type" messages
[TEST] If none: MultiSurfCrack2D is properly registered!
```

---

### STEP 9: Test with GUI

**Commands:**
```bash
cd c:\Users\himan\multi-surf-crack2D
python gui_wsl.py
```

**In GUI:**
1. Go to **Run** tab
2. Click **"🧪 Run Integration Self-Test"**
3. Expected console output:
   ```
   [SELFTEST] TEST 1: [PASS] MultiSurfCrack2D material created successfully
   [SELFTEST] TEST 2: [PASS] Element created with zeroLengthND (RECOMMENDED)
   [SELFTEST] TEST 3: [PASS] Analysis ran successfully (status=0)
   [PASS] ✓ COMPREHENSIVE SELF-TEST PASSED
   ```

4. Run normal analysis with MultiSurfCrack2D selected
5. Expected console output:
   ```
   [INSTRUMENTATION] Creating crack interface elements...
   [ELEMENT_TYPE] Crack 0: zeroLengthND
   [USING MultiSurfCrack2D] Crack 0: MultiSurfCrack2D + zeroLengthND (RECOMMENDED)
   [SUMMARY] ✓ Successfully using MultiSurfCrack2D for 1/1 cracks
   ```

---

## Common Build Issues & Fixes

### Issue 1: CMake not found
**Fix:**
```bash
wsl bash -c "sudo apt-get update && sudo apt-get install -y cmake"
```

### Issue 2: Compiler not found (gcc/g++)
**Fix:**
```bash
wsl bash -c "sudo apt-get install -y build-essential gfortran"
```

### Issue 3: Python development headers missing
**Fix:**
```bash
wsl bash -c "sudo apt-get install -y python3.12-dev"
```

### Issue 4: Build fails with "MultiSurfCrack2D.h not found"
**Fix:**
```bash
wsl bash -c "
# Manually edit CMakeLists.txt to add include path
sed -i '/target_include_directories(opensees/a \  \${CMAKE_CURRENT_SOURCE_DIR}/material/nD' ~/OpenSees/CMakeLists.txt
"
```

### Issue 5: Still get "WARNING material type unknown"
**Causes:**
1. File not in CMakeLists.txt
2. Registration function not called
3. Needs rebuild
4. Still using old openseespy (not the new build)

**Diagnosis:**
```bash
wsl bash -c "
python3 -c 'import openseespy.opensees as ops; print(ops.__file__)'
"
```

**Should show:** `/home/himan/ops_env/lib/python3.12/site-packages/openseespy`

If shows system path → reinstall with `pip install -e .`

### Issue 6: Build takes too long
**Workaround:** Use parallel build with more cores:
```bash
cmake --build . -j8
```

Or compile just the essentials:
```bash
cmake .. -DOpenSees_BUILD_PYTHON_OPTIONAL_FEATURES=OFF
cmake --build . -j4
```

---

## Quick Reference: File Changes Needed

| File | Change | Location |
|------|--------|----------|
| `SRC/material/nD/NDMaterial.h` | Add `#define ND_TAG_MultiSurfCrack2D 8899` | After last ND_TAG definition |
| `SRC/material/nD/materialpackage.cpp` | Add `extern void* OPS_MultiSurfCrack2D();` | Top with other externs |
| `SRC/material/nD/materialpackage.cpp` | Add dispatcher check for "MultiSurfCrack2D" | Main if/else block |
| `SRC/material/nD/CMakeLists.txt` | Add `MultiSurfCrack2D.cpp` to SOURCES | MATERIAL_NDMATERIAL_SOURCES |
| (Copy) | Copy multi-surf-crack2d.cpp to SRC/material/nD/ | New file |
| (Copy) | Copy multi-surf-crack2d.h to SRC/material/nD/ | New file |

---

## Expected Result After Successful Build

### Console Output (No Errors):
```
[TEST] Creating OpenSees model...
[TEST] Attempting to create MultiSurfCrack2D material...
[PASS] ✓ MultiSurfCrack2D material created successfully!
```

### GUI Output:
```
[INSTRUMENTATION] Creating crack interface elements...
[ELEMENT_TYPE] Crack 0: zeroLengthND
[USING MultiSurfCrack2D] Crack 0: MultiSurfCrack2D + zeroLengthND (RECOMMENDED)
[SUMMARY] ✓ Successfully using MultiSurfCrack2D for N/N cracks
```

### NO More Fallback:
```
❌ NO: [FALLBACK REASON] MultiSurfCrack2D not in OpenSees build
❌ NO: WARNING material type MultiSurfCrack2D is unknown
✅ YES: Material created and used for cracks
```

---

## Time Estimate

| Step | Time | Notes |
|------|------|-------|
| 1. Clone OpenSees | 2-3 min | Network dependent |
| 2. Copy files | <1 min | Fast |
| 3. Edit NDMaterial.h | <1 min | One line |
| 4. Edit materialpackage.cpp | 1-2 min | Find and add |
| 5. Update CMakeLists.txt | <1 min | Auto-add |
| 6. Build OpenSees | 15-30 min | Depends on CPU cores |
| 7. Install | 2-3 min | pip install |
| 8. Verify | <1 min | Quick test |
| **TOTAL** | **30-45 min** | First-time build |

---

## Success Criteria

✅ **All of these must be true:**
1. `ops.nDMaterial('MultiSurfCrack2D', ...)` creates material without warnings
2. No "WARNING material type unknown" messages
3. GUI shows `[USING MultiSurfCrack2D]` for cracks
4. GUI shows `[SUMMARY] ✓ Successfully using MultiSurfCrack2D for N/N cracks`
5. Self-test button passes `[PASS]` all three tests
6. NO fallback to Elastic materials

---

## Next: Detailed Step-by-Step Commands

See: OPENSEES_BUILD_DETAILED_COMMANDS.md (next section)

