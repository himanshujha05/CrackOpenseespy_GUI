#!/usr/bin/env bash
# =============================================================================
# build_msc2d.sh  —  Build OpenSeesPy with MultiSurfCrack2D for WSL/Ubuntu
# =============================================================================
# Tested on: Ubuntu 24.04 LTS, Python 3.12, WSL2
# Usage (from WSL terminal):
#   bash /mnt/c/Users/himan/multi-surf-crack2D/build_msc2d.sh
#
# What it does:
#   1. Installs build tools (cmake, g++, gfortran, lapack, etc.)
#   2. Clones OpenSees v3.7.1 source from GitHub
#   3. Copies MultiSurfCrack2D.cpp / .h into the nD materials directory
#   4. Patches CMakeLists.txt and the nDMaterial dispatch table
#   5. Builds the OpenSeesPy shared library (~20-40 min on 4 cores)
#   6. Installs into ~/ops_env
#   7. Runs a quick smoke-test
# =============================================================================
set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
OPENSEES_TAG="v3.7.1"
BUILD_ROOT="$HOME/opensees_msc2d_build"
VENV="$HOME/ops_env"
WIN_SRC="/mnt/c/Users/himan/multi-surf-crack2D"
JOBS=$(nproc 2>/dev/null || echo 4)
PYTHON_EXE="$VENV/bin/python3"

# ── Helpers ─────────────────────────────────────────────────────────────────
info()  { printf '\033[1;34m[INFO]\033[0m  %s\n' "$*"; }
ok()    { printf '\033[1;32m[ OK ]\033[0m  %s\n' "$*"; }
warn()  { printf '\033[1;33m[WARN]\033[0m  %s\n' "$*"; }
die()   { printf '\033[1;31m[FAIL]\033[0m  %s\n' "$*"; exit 1; }
sep()   { echo ""; echo "$(printf '%.0s─' {1..70})"; echo ""; }

sep
info "OpenSeesPy + MultiSurfCrack2D  —  WSL build script"
info "Build root  : $BUILD_ROOT"
info "Virtual env : $VENV"
info "Cores       : $JOBS"
sep

# ── 1. Build dependencies ───────────────────────────────────────────────────
info "Installing build dependencies (may need sudo password)..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    cmake cmake-data ninja-build \
    g++ gfortran \
    liblapack-dev libblas-dev \
    libssl-dev libffi-dev \
    tcl-dev tk-dev \
    python3.12-dev python3.12-venv \
    git wget curl patchelf pkg-config
ok "Build dependencies ready."

# Some OpenSees sources include <tcl.h>/<tk.h> directly while Ubuntu installs
# headers under versioned dirs (e.g., /usr/include/tcl8.6). Create symlinks once.
if [ ! -f /usr/include/tcl.h ] && [ -f /usr/include/tcl8.6/tcl.h ]; then
    info "Creating /usr/include/tcl.h symlink -> /usr/include/tcl8.6/tcl.h"
    sudo ln -sf /usr/include/tcl8.6/tcl.h /usr/include/tcl.h
fi
if [ ! -f /usr/include/tk.h ] && [ -f /usr/include/tcl8.6/tk.h ]; then
    info "Creating /usr/include/tk.h symlink -> /usr/include/tcl8.6/tk.h"
    sudo ln -sf /usr/include/tcl8.6/tk.h /usr/include/tk.h
fi

# ── 2. Ensure venv exists ───────────────────────────────────────────────────
if [ ! -f "$VENV/bin/python3" ]; then
    info "Creating virtual environment at $VENV ..."
    python3.12 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet --upgrade pip wheel numpy
fi
ok "Virtual environment: $VENV"

# ── 3. Clone OpenSees ───────────────────────────────────────────────────────
mkdir -p "$BUILD_ROOT"
cd "$BUILD_ROOT"

if [ ! -d "OpenSees/.git" ]; then
    info "Cloning OpenSees $OPENSEES_TAG ..."
    git clone --depth=1 --branch "$OPENSEES_TAG" \
        https://github.com/OpenSees/OpenSees.git OpenSees 2>&1 | tail -5 || \
    { warn "Tag $OPENSEES_TAG not found, cloning HEAD...";
      git clone --depth=1 https://github.com/OpenSees/OpenSees.git OpenSees 2>&1 | tail -5; }
    ok "OpenSees cloned."
else
    info "OpenSees already cloned — skipping."
fi

# ── 4. Copy material source files ───────────────────────────────────────────
info "Copying MultiSurfCrack2D files..."
[ -f "$WIN_SRC/multi-surf-crack2d.cpp" ] || die "Not found: $WIN_SRC/multi-surf-crack2d.cpp"
[ -f "$WIN_SRC/multi-surf-crack2d.h"   ] || die "Not found: $WIN_SRC/multi-surf-crack2d.h"

cp -v "$WIN_SRC/multi-surf-crack2d.cpp" \
      "$BUILD_ROOT/OpenSees/SRC/material/nD/MultiSurfCrack2D.cpp"
cp -v "$WIN_SRC/multi-surf-crack2d.h" \
      "$BUILD_ROOT/OpenSees/SRC/material/nD/MultiSurfCrack2D.h"
ok "Files copied."

# ── 5. Patch CMakeLists.txt ─────────────────────────────────────────────────
info "Patching nD CMakeLists.txt..."
ND_CMAKE="$BUILD_ROOT/OpenSees/SRC/material/nD/CMakeLists.txt"

if grep -q "MultiSurfCrack2D" "$ND_CMAKE" 2>/dev/null; then
    info "CMakeLists.txt already patched."
else
    python3 - "$ND_CMAKE" <<'PYEOF'
import sys, re

path = sys.argv[1]
with open(path) as f:
    txt = f.read()

entry = "  MultiSurfCrack2D.cpp\n"

# Try to insert into an existing target_sources(...) block
m = re.search(r'(target_sources\s*\([^\)]*?)(\))', txt, re.DOTALL)
if m:
    new_txt = txt[:m.end(1)] + entry + txt[m.end(1):]
else:
    # Append a new target_sources call at end of file
    lib_m = re.search(r'target_sources\s*\((\w+)', txt)
    lib_name = lib_m.group(1) if lib_m else "OPS_Material"
    new_txt = txt + f"\ntarget_sources({lib_name}\n  PRIVATE\n{entry})\n"

with open(path, 'w') as f:
    f.write(new_txt)
print("  Patched:", path)
PYEOF
    ok "CMakeLists.txt patched."
fi

# ── 6. Patch the nDMaterial dispatch table ───────────────────────────────────
info "Locating nDMaterial dispatch file..."

# Search for the Python-interface dispatch (preferred) or Tcl dispatch
DISPATCH=""
PATTERNS="OpenSeesNDCommands.cpp TclNDMaterialCommand.cpp tclNDMaterial.cpp NDMaterial.cpp"
for pattern in $PATTERNS; do
    f=$(find "$BUILD_ROOT/OpenSees/SRC" -name "$pattern" 2>/dev/null | head -1)
    if [ -n "$f" ]; then DISPATCH="$f"; break; fi
done

# Fallback: search by content (look for a known material like ElasticIsotropic)
if [ -z "$DISPATCH" ]; then
    DISPATCH=$(grep -rl '"ElasticIsotropic"' \
        "$BUILD_ROOT/OpenSees/SRC" --include="*.cpp" 2>/dev/null | head -1 || true)
fi

if [ -z "$DISPATCH" ]; then
    warn "Could not locate dispatch file automatically."
    warn "You may need to manually add MultiSurfCrack2D to the dispatch table."
    warn "See MANUAL_REGISTRATION.md for instructions."
    # Write a helper doc
    cat > "$BUILD_ROOT/MANUAL_REGISTRATION.md" <<'EOF'
## Manual Registration of MultiSurfCrack2D

Find the file in OpenSees/SRC that dispatches nDMaterial by name.
Usually: SRC/material/nD/TclNDMaterialCommand.cpp or
         SRC/interpreter/OpenSeesNDCommands.cpp

1. Add near the top (with other extern declarations):
   extern void *OPS_MultiSurfCrack2D(void);

2. Add in the if-else chain (near "ElasticIsotropic"):
   } else if (strcmp(matType, "MultiSurfCrack2D") == 0) {
       theMaterial = (NDMaterial *)OPS_MultiSurfCrack2D();

3. Re-run the cmake build.
EOF
else
    info "Found dispatch file: $DISPATCH"
    if grep -q "MultiSurfCrack2D" "$DISPATCH" 2>/dev/null; then
        info "Dispatch already patched."
    else
        python3 - "$DISPATCH" <<'PYEOF'
import sys, re

path = sys.argv[1]
with open(path) as f:
    txt = f.read()

# --- 1. Add forward declaration ---
decl = 'extern void *OPS_MultiSurfCrack2D(void);\n'

# Insert before the first 'extern void *OPS_' we can find
# (or before the dispatch function body if no such pattern)
m = re.search(r'extern\s+void\s*\*\s*OPS_\w+', txt)
if m:
    txt = txt[:m.start()] + decl + txt[m.start():]
else:
    # Insert after all #includes
    inc_end = 0
    for inc_m in re.finditer(r'#include\s+[<"][^"<>]+[>"]', txt):
        inc_end = inc_m.end()
    txt = txt[:inc_end] + '\n' + decl + txt[inc_end:]

# --- 2. Add dispatch entry ---
# Find a suitable anchor (after ElasticIsotropic or J2Plasticity)
anchors = [
    r'(strcmp\s*\(\s*\w+\s*,\s*"ElasticIsotropic"\s*\))',
    r'(strcmp\s*\(\s*\w+\s*,\s*"J2Plasticity"\s*\))',
    r'(strcmp\s*\(\s*\w+\s*,\s*"ElasticOrthotropic"\s*\))',
]
anchor_pos = -1
for pat in anchors:
    m = re.search(pat, txt)
    if m:
        # Find end of the if/else block after this anchor
        # Look for the next closing brace after the OPS_ call
        block_start = m.start()
        brace_depth = 0
        i = block_start
        found_open = False
        while i < len(txt):
            if txt[i] == '{':
                brace_depth += 1
                found_open = True
            elif txt[i] == '}':
                brace_depth -= 1
                if found_open and brace_depth == 0:
                    anchor_pos = i + 1
                    break
            i += 1
        if anchor_pos != -1:
            break

new_entry = ('\n  } else if (strcmp(matType, "MultiSurfCrack2D") == 0) {\n'
             '    theMaterial = (NDMaterial *)OPS_MultiSurfCrack2D();\n')

if anchor_pos != -1:
    txt = txt[:anchor_pos] + new_entry + txt[anchor_pos:]
else:
    # Last resort: append near end of file before closing brace
    last_brace = txt.rfind('\n}')
    if last_brace != -1:
        txt = txt[:last_brace] + new_entry + txt[last_brace:]

with open(path, 'w') as f:
    f.write(txt)
print(f"  Patched dispatch: {path}")
PYEOF
        ok "Dispatch table patched."
    fi
fi

# ── 7. Configure cmake ───────────────────────────────────────────────────────
sep
info "Configuring cmake..."
mkdir -p "$BUILD_ROOT/build"
cd "$BUILD_ROOT/build"

cmake "$BUILD_ROOT/OpenSees" \
    -G "Unix Makefiles" \
    -DCMAKE_BUILD_TYPE=Release \
    -DPython_EXECUTABLE="$PYTHON_EXE" \
    -DOPENSEES_BUILD_OpenSeesPy=ON \
    -DOPENSEES_USE_MKL_SEQUENTIAL=OFF \
    2>&1 | tail -25

ok "cmake configured."

# ── 8. Build ─────────────────────────────────────────────────────────────────
sep
info "Building OpenSeesPy with $JOBS parallel jobs..."
info "(This typically takes 20-40 minutes. Go get a coffee.)"
make -j"$JOBS" OpenSeesPy 2>&1 | tee "$BUILD_ROOT/build.log" | \
    grep -E "(error:|warning:|Building|Linking|\[)" | tail -40

# Check build succeeded
SO=$(find "$BUILD_ROOT/build" \
    -name "opensees*.so" -o -name "libOpenSeesPy*.so" 2>/dev/null | head -1)
[ -n "$SO" ] || die "Build failed — no .so produced. See $BUILD_ROOT/build.log"
ok "Build succeeded: $SO"

# ── 9. Install into venv ─────────────────────────────────────────────────────
sep
info "Installing into $VENV ..."

source "$VENV/bin/activate"
SITE=$(python3 -c "import site; print(site.getsitepackages()[0])")

# The openseespylinux package holds the .so under opensees/
LINUX_PKG="$SITE/openseespylinux"
mkdir -p "$LINUX_PKG"

# Find the existing .so name (opensees.cpython-312-x86_64-linux-gnu.so or similar)
EXISTING_SO=$(find "$SITE" -name "opensees*.so" 2>/dev/null | head -1)
TARGET_NAME="opensees.so"
if [ -n "$EXISTING_SO" ]; then
    TARGET_NAME=$(basename "$EXISTING_SO")
    cp -v "$SO" "$(dirname "$EXISTING_SO")/$TARGET_NAME"
else
    cp -v "$SO" "$LINUX_PKG/$TARGET_NAME"
fi
ok "Installed: $TARGET_NAME"

# ── 10. Smoke test ───────────────────────────────────────────────────────────
sep
info "Running smoke test..."

python3 - <<'PYEOF'
import openseespy.opensees as ops

ops.wipe()
ops.model('basic', '-ndm', 2, '-ndf', 2)
ops.node(1, 0., 0.)
ops.node(2, 0., 1.)
ops.fix(1, 1, 1)
ops.fix(2, 1, 0)

w0 = 0.1; fc = 30.0; ag = 16.0
Dt = 0.00595 * (25.4/w0)**1.6148 * (fc/34.5)**0.193
Dn = (2.0 + w0) / w0

try:
    ops.nDMaterial('MultiSurfCrack2D', 1,
        Dt, 0., 0., Dn,    # De  loading stiffness [E,H,M,K]
        Dt, 0., 0., Dn,    # DeU unloading stiffness
        fc, ag,            # concrete strength, aggregate size
        0.0,               # fcl (crack closure stress)
        1.0,               # Acr (crack area)
        0.3, 0.18,         # rho_lok, chi_lok
        1.0, 0.2, 0.18,    # rho_act, mu, chi_act
        0.5, 0.75,         # zeta, kappa
        0.0, w0            # theta, initial crack width
    )
    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║  MultiSurfCrack2D: AVAILABLE             ║")
    print("  ║  nDMaterial created successfully!        ║")
    print("  ╚══════════════════════════════════════════╝")
    print()
except Exception as e:
    print(f"\n  [FAIL] Could not create MultiSurfCrack2D: {e}\n")
    raise
PYEOF

sep
ok "=== Build complete! ==="
info "MultiSurfCrack2D is now compiled into $VENV"
info "Restart the GUI to use it:"
info "  cd /mnt/c/Users/himan/multi-surf-crack2D"
info "  .venv/Scripts/python.exe gui_wsl.py"
info "  -> Material tab -> Crack Interface Material -> MultiSurfCrack2D (custom)"
sep
