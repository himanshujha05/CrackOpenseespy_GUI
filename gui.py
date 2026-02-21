"""
Multi-Surface Crack 2D - OpenSeesPy GUI
=========================================
PyQt5-based graphical front-end for building, running, and post-processing
reinforced-concrete crack-interface models in OpenSeesPy.

Model topology
--------------
  Vertical bar with N cracks -> (2N+2) nodes, (N+1) truss segments, N zeroLength
  springs.  Each crack is a pair of co-located nodes joined by a zeroLength
  element whose normal stiffness (kn) and shear stiffness (kt) are user-defined.

Analysis types
--------------
  - Static - Load Control
  - Static - Displacement Control

Usage
-----
  python gui.py
"""

import sys
import traceback
import json
import subprocess
import time
from pathlib import Path
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QDoubleSpinBox, QSpinBox, QCheckBox, QSplitter,
    QMessageBox, QFileDialog, QFrame, QScrollArea,
    QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# WSL helper and embedded runner script
# ---------------------------------------------------------------------------
def win_to_wsl(p):
    p = Path(p); drv = p.drive.rstrip(":").lower()
    rest = p.as_posix().split(":/", 1)[-1]
    return f"/mnt/{drv}/{rest}"

# Embedded OpenSeesPy runner — written to a temp file and executed in WSL
_RUNNER_PY = r'''
import sys, json
import numpy as np

def run_model(p):
    import openseespy.opensees as ops

    ops.wipe()
    ops.model('basic', '-ndm', 2, '-ndf', 2)

    L = float(p['bar_length'])
    A = float(p['bar_area'])
    Es = float(p['Es'])
    fsy = float(p['fsy'])
    ele_type = p.get('ele_type', 'Truss')

    crack_data = sorted(p.get('crack_data', []), key=lambda c: c['y'])
    crack_data = [c for c in crack_data if 0.001 * L < c['y'] < 0.999 * L]

    rebar_mat = 1
    mat_type = p.get('mat_type', 'Elastic')
    if mat_type == 'ElasticPP':
        eps_y = fsy / Es
        ops.uniaxialMaterial('ElasticPP', rebar_mat, Es, eps_y)
    elif mat_type == 'Steel02':
        b = float(p.get('hardening_ratio', 0.01))
        R0 = float(p.get('R0', 15.0))
        cR1 = float(p.get('cR1', 0.925))
        cR2 = float(p.get('cR2', 0.15))
        ops.uniaxialMaterial('Steel02', rebar_mat, fsy, Es, b, R0, cR1, cR2)
    else:
        ops.uniaxialMaterial('Elastic', rebar_mat, Es)

    n_tag = 0; e_tag = 0

    def mk_node(x, y, fix_x=1, fix_y=0):
        nonlocal n_tag; n_tag += 1
        ops.node(n_tag, x, y); ops.fix(n_tag, fix_x, fix_y); return n_tag

    def mk_truss(i, j):
        nonlocal e_tag; e_tag += 1
        ops.element(ele_type, e_tag, i, j, A, rebar_mat); return e_tag

    def mk_crack(i, j, kn, kt, ci):
        nonlocal e_tag
        mx = 10 + ci * 2; my = 11 + ci * 2
        ops.uniaxialMaterial('Elastic', mx, max(float(kt), 1.0))
        ops.uniaxialMaterial('Elastic', my, float(kn))
        e_tag += 1
        ops.element('zeroLength', e_tag, i, j, '-mat', mx, my, '-dir', 1, 2)
        return e_tag

    base = mk_node(0.0, 0.0, fix_x=1, fix_y=1)
    prev = base; truss_eles = []; crack_nodes = []

    for ci, crack in enumerate(crack_data):
        y_c = float(crack['y'])
        nb = mk_node(0.0, y_c); truss_eles.append(mk_truss(prev, nb))
        na = mk_node(0.0, y_c); mk_crack(nb, na, crack['kn'], crack['kt'], ci)
        crack_nodes.append((nb, na, y_c)); prev = na

    top = mk_node(0.0, L); truss_eles.append(mk_truss(prev, top))
    loaded_node = top; free_dof = 2; force_ele = truss_eles[0]

    ops.timeSeries('Linear', 1); ops.pattern('Plain', 1, 1)
    ref_load = fsy * A
    analysis_type = p.get('analysis_type', 'DisplacementControl')
    if analysis_type == 'LoadControl':
        ops.load(loaded_node, 0.0, ref_load)
    else:
        ops.load(loaded_node, 0.0, 1.0)

    ops.constraints('Plain'); ops.numberer('Plain'); ops.system('BandGeneral')
    ops.algorithm(p.get('algorithm', 'Newton'))
    ops.test('NormDispIncr', float(p.get('tol', 1e-6)), int(p.get('max_iter', 100)))

    disp_list = []; force_list = []; crack_openings = [[] for _ in crack_nodes]

    def collect():
        disp_list.append(ops.nodeDisp(loaded_node, free_dof))
        force_list.append(-ops.eleForce(force_ele, free_dof))
        for k, (nb, na, _) in enumerate(crack_nodes):
            crack_openings[k].append(ops.nodeDisp(na, free_dof) - ops.nodeDisp(nb, free_dof))

    ops.analysis('Static')
    if analysis_type == 'LoadControl':
        incr = float(p.get('load_incr', 0.01))
        steps = max(1, int(1.0 / incr))
        ops.integrator('LoadControl', incr)
        for _ in range(steps):
            if ops.analyze(1) == 0: collect()
            else: break
    else:
        target = float(p.get('target_disp', 0.5))
        incr = float(p.get('disp_incr', 0.001))
        steps = max(1, int(abs(target) / max(abs(incr), 1e-12)))
        ops.integrator('DisplacementControl', loaded_node, free_dof, incr)
        for _ in range(steps):
            if ops.analyze(1) == 0: collect()
            else: break

    disp = np.array(disp_list, dtype=float)
    force = np.array(force_list, dtype=float)
    crack_openings_np = [np.array(x, dtype=float) for x in crack_openings]
    crack_positions = [float(y) for (_, _, y) in crack_nodes]
    return {
        "disp": disp, "force": force,
        "crack_openings": crack_openings_np,
        "crack_positions": np.array(crack_positions, dtype=float),
        "status": "ok" if len(disp_list) else "failed",
        "message": f"{len(disp_list)} steps converged | {len(crack_nodes)} crack(s)",
        "fy": float(ref_load),
    }

def main():
    if len(sys.argv) != 3:
        print("Usage: runner.py params.json results.npz"); sys.exit(2)
    with open(sys.argv[1]) as f: p = json.load(f)
    r = run_model(p)
    np.savez(sys.argv[2],
        disp=r["disp"], force=r["force"],
        crack_positions=r["crack_positions"],
        status=np.array([r["status"]]),
        message=np.array([r["message"]]),
        fy=np.array([r["fy"]]),
        crack_openings=np.array(r["crack_openings"], dtype=object))
    print(r["message"]); sys.exit(0 if r["status"] == "ok" else 1)

if __name__ == "__main__":
    main()
'''


# ---------------------------------------------------------------------------
# Colour palette  (dark-blue / steel theme)
# ---------------------------------------------------------------------------
STYLE = """
QMainWindow, QDialog { background-color: #1e2a38; }
QWidget { background-color: #1e2a38; color: #dce6f0; font-family: 'Segoe UI', Arial; font-size: 13px; }
QTabWidget::pane { border: 1px solid #3a5068; background: #243447; }
QTabBar::tab {
    background: #16202c; color: #90aac4; padding: 8px 18px;
    border: 1px solid #3a5068; border-bottom: none; border-radius: 4px 4px 0 0; }
QTabBar::tab:selected { background: #243447; color: #6ec6f5; font-weight: bold; }
QGroupBox {
    border: 1px solid #3a5068; border-radius: 6px; margin-top: 10px;
    padding: 8px; color: #6ec6f5; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    background: #16202c; border: 1px solid #3a5068; border-radius: 4px;
    padding: 4px 8px; color: #dce6f0; selection-background-color: #2d6a9f; }
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #6ec6f5; }
QComboBox QAbstractItemView { background: #16202c; selection-background-color: #2d6a9f; }
QPushButton {
    background: #2d6a9f; color: #fff; border-radius: 5px; padding: 7px 18px;
    font-weight: bold; border: none; }
QPushButton:hover { background: #3a89cc; }
QPushButton:pressed { background: #1a4f7a; }
QPushButton:disabled { background: #2e4057; color: #607080; }
QPushButton#btn_danger { background: #8b2020; }
QPushButton#btn_danger:hover { background: #b02828; }
QPushButton#btn_success { background: #1e6b3e; }
QPushButton#btn_success:hover { background: #278a50; }
QTableWidget {
    background: #16202c; gridline-color: #2e4057; border: 1px solid #3a5068;
    color: #dce6f0; }
QHeaderView::section {
    background: #243447; color: #6ec6f5; padding: 5px;
    border: 1px solid #3a5068; font-weight: bold; }
QTextEdit {
    background: #101820; color: #a8d8a8; border: 1px solid #3a5068;
    border-radius: 4px; font-family: Consolas, monospace; font-size: 12px; }
QScrollBar:vertical { background: #16202c; width: 10px; }
QScrollBar::handle:vertical { background: #3a5068; border-radius: 4px; }
QLabel#heading { color: #6ec6f5; font-size: 15px; font-weight: bold; }
QLabel#subheading { color: #90aac4; font-size: 12px; }
QCheckBox { spacing: 6px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #3a5068; border-radius: 3px; }
QCheckBox::indicator:checked { background: #2d6a9f; }
QSplitter::handle { background: #3a5068; }
QToolTip { background: #243447; color: #dce6f0; border: 1px solid #3a5068;
           padding: 4px; font-size: 12px; }
"""


# ---------------------------------------------------------------------------
# Worker thread - runs OpenSeesPy so GUI stays responsive
# ---------------------------------------------------------------------------
class AnalysisWorker(QThread):
    log      = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, params: dict):
        super().__init__()
        self.params = params

    def run(self):
        try:
            import openseespy.opensees as ops
            result = run_opensees_model(ops, self.params, self.log)
            self.finished.emit(result)
        except Exception:
            self.error.emit(traceback.format_exc())


# ---------------------------------------------------------------------------
# Core OpenSeesPy model builder  (called from worker thread)
# ---------------------------------------------------------------------------
def run_opensees_model(ops, p: dict, log_fn) -> dict:
    """
    Multi-crack bar model.

    Topology (example with 2 cracks at y=a and y=b, 0<a<b<L):

      Node 1  y=0   -> fixed pin
       Truss #1
      Node 2  y=a   -> below crack 1  (fix x)
      Node 3  y=a   -> above crack 1  (fix x)  -- zeroLength
       Truss #2
      Node 4  y=b   -> below crack 2  (fix x)
      Node 5  y=b   -> above crack 2  (fix x)  -- zeroLength
       Truss #3
      Node 6  y=L   -> loaded tip    (fix x, free y)
    """
    ops.wipe()
    ops.model('basic', '-ndm', 2, '-ndf', 2)
    log_fn.emit("-- Model initialised (2D, 2-DOF) --")

    L         = p['bar_length']
    A         = p['bar_area']
    Es        = p['Es']
    fsy       = p['fsy']
    ele_type  = p.get('ele_type', 'Truss')

    crack_data = sorted(p.get('crack_data', []), key=lambda c: c['y'])
    crack_data = [c for c in crack_data if 0.001 * L < c['y'] < 0.999 * L]
    log_fn.emit(f"  Bar: L={L}, A={A}  |  {len(crack_data)} crack(s)")

    # -- Rebar material ------------------------------------------------
    rebar_mat = 1
    mat_type  = p['mat_type']
    if mat_type == 'ElasticPP':
        eps_y = fsy / Es
        ops.uniaxialMaterial('ElasticPP', rebar_mat, Es, eps_y)
        log_fn.emit(f"  Rebar ElasticPP: Es={Es}, fsy={fsy}")
    elif mat_type == 'Steel02':
        b = p.get('hardening_ratio', 0.01)
        ops.uniaxialMaterial('Steel02', rebar_mat, fsy, Es, b,
                             p.get('R0', 15.0), p.get('cR1', 0.925), p.get('cR2', 0.15))
        log_fn.emit(f"  Rebar Steel02: Es={Es}, fsy={fsy}, b={b}")
    else:
        ops.uniaxialMaterial('Elastic', rebar_mat, Es)
        log_fn.emit(f"  Rebar Elastic: E={Es}")

    # -- Node / element counters ---------------------------------------
    _n = [0]; _e = [0]
    def mk_node(x, y, fix_x=1, fix_y=0):
        _n[0] += 1; ops.node(_n[0], x, y); ops.fix(_n[0], fix_x, fix_y); return _n[0]
    def mk_truss(i, j):
        _e[0] += 1; ops.element(ele_type, _e[0], i, j, A, rebar_mat); return _e[0]
    def mk_crack(i, j, kn, kt, ci):
        mx = 10 + ci * 2;  my = 11 + ci * 2
        ops.uniaxialMaterial('Elastic', mx, max(kt, 1.0))
        ops.uniaxialMaterial('Elastic', my, kn)
        _e[0] += 1
        ops.element('zeroLength', _e[0], i, j, '-mat', mx, my, '-dir', 1, 2)
        return _e[0]

    # -- Build topology ------------------------------------------------
    base = mk_node(0.0, 0.0, fix_x=1, fix_y=1)

    prev   = base
    crack_nodes = []
    truss_eles  = []

    for ci, crack in enumerate(crack_data):
        y_c = crack['y']
        n_b = mk_node(0.0, y_c)
        t   = mk_truss(prev, n_b)
        truss_eles.append(t)
        log_fn.emit(f"  Truss {t}: {prev}->{n_b}  y=[prev->{y_c:.3f}]")

        n_a = mk_node(0.0, y_c)
        ce  = mk_crack(n_b, n_a, crack['kn'], crack['kt'], ci)
        crack_nodes.append((n_b, n_a, y_c))
        log_fn.emit(f"  Crack {ce}: {n_b}->{n_a}  y={y_c:.3f}  kn={crack['kn']:.2e}  kt={crack['kt']:.2e}")

        prev = n_a

    top = mk_node(0.0, L)
    t   = mk_truss(prev, top)
    truss_eles.append(t)
    log_fn.emit(f"  Truss {t}: {prev}->{top}  y=[prev->{L}]")
    log_fn.emit(f"  Total: {_n[0]} nodes, {_e[0]} elements  (first truss tag={truss_eles[0]})")

    loaded_node = top
    free_dof    = 2
    force_ele   = truss_eles[0]

    # -- Loads ---------------------------------------------------------
    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)
    ref_load = fsy * A
    if p['analysis_type'] == 'LoadControl':
        ops.load(loaded_node, 0.0, ref_load)
        log_fn.emit(f"  LoadControl, ref = {ref_load:.3f} (Fy*A)")
    else:
        ops.load(loaded_node, 0.0, 1.0)

    # -- Solver --------------------------------------------------------
    ops.constraints('Plain')
    ops.numberer('Plain')
    ops.system('BandGeneral')
    ops.algorithm(p.get('algorithm', 'Newton'))
    ops.test('NormDispIncr', p.get('tol', 1e-6), p.get('max_iter', 100))

    disp_list  = []
    force_list = []
    crack_openings = [[] for _ in crack_nodes]

    def _collect():
        disp_list.append(ops.nodeDisp(loaded_node, free_dof))
        force_list.append(-ops.eleForce(force_ele, free_dof))
        for k, (nb, na, _) in enumerate(crack_nodes):
            crack_openings[k].append(
                ops.nodeDisp(na, free_dof) - ops.nodeDisp(nb, free_dof))

    if p['analysis_type'] == 'LoadControl':
        incr      = p.get('load_incr', 0.01)
        num_steps = int(1.0 / incr)
        ops.integrator('LoadControl', incr)
        ops.analysis('Static')
        log_fn.emit(f"  LoadControl: incr={incr}, steps={num_steps}")
        for n in range(num_steps):
            ok = ops.analyze(1)
            if ok == 0: _collect()
            else: log_fn.emit(f"  Diverged at step {n}"); break

    else:  # DisplacementControl
        target    = p.get('target_disp', 1.0)
        incr      = p.get('disp_incr', 0.01)
        num_steps = int(abs(target) / abs(incr))
        ops.integrator('DisplacementControl', loaded_node, free_dof, incr)
        ops.analysis('Static')
        log_fn.emit(f"  DispControl: incr={incr}, target={target}, steps={num_steps}")
        for n in range(num_steps):
            ok = ops.analyze(1)
            if ok == 0: _collect()
            else: log_fn.emit(f"  Diverged at step {n}"); break

    log_fn.emit(f"-- Done: {len(disp_list)} converged steps --")
    return {
        'disp':            np.array(disp_list),
        'force':           np.array(force_list),
        'crack_openings':  [np.array(co) for co in crack_openings],
        'crack_positions': [c['y'] for c in crack_data],
        'status':          'ok' if disp_list else 'failed',
        'message':         f"{len(disp_list)} steps converged | {len(crack_data)} crack(s)",
    }


# ---------------------------------------------------------------------------
# Matplotlib canvas widget
# ---------------------------------------------------------------------------
class MplCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.fig = Figure(facecolor='#101820')
        self.ax  = self.fig.add_subplot(111)
        self._style_axes()
        self.canvas  = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setStyleSheet("background:#16202c; color:#dce6f0;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toolbar)
        lay.addWidget(self.canvas)

    def _style_axes(self):
        ax = self.ax
        ax.set_facecolor('#101820')
        ax.tick_params(colors='#90aac4')
        ax.xaxis.label.set_color('#dce6f0')
        ax.yaxis.label.set_color('#dce6f0')
        ax.title.set_color('#6ec6f5')
        for spine in ax.spines.values():
            spine.set_edgecolor('#3a5068')

    def plot(self, x, y, xlabel='', ylabel='', title='', label='', color='#6ec6f5'):
        self.ax.cla()
        self._style_axes()
        self.ax.plot(x, y, '-o', color=color, markersize=3, linewidth=1.8, label=label)
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        self.ax.set_title(title)
        self.ax.grid(True, alpha=0.2, color='#3a5068')
        if label:
            self.ax.legend(facecolor='#16202c', edgecolor='#3a5068', labelcolor='#dce6f0')
        self.canvas.draw()

    def add_line(self, x, y, label='', color='#f5a623'):
        self.ax.plot(x, y, '-s', color=color, markersize=3, linewidth=1.8, label=label)
        self.ax.legend(facecolor='#16202c', edgecolor='#3a5068', labelcolor='#dce6f0')
        self.canvas.draw()


# ---------------------------------------------------------------------------
# Helper: labelled spin-box row
# ---------------------------------------------------------------------------
def dbl_field(label, val, lo, hi, decimals=4, step=0.001, tooltip=''):
    sb = QDoubleSpinBox()
    sb.setRange(lo, hi)
    sb.setDecimals(decimals)
    sb.setSingleStep(step)
    sb.setValue(val)
    sb.setFixedWidth(140)
    lbl = QLabel(label)
    if tooltip:
        lbl.setToolTip(tooltip)
        sb.setToolTip(tooltip)
    return lbl, sb


# ===================================================================
# Tab 1 - Geometry & Crack Interfaces   (REWRITTEN - multi-crack)
# ===================================================================
class GeometryTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setSpacing(12)

        heading = QLabel("Model Geometry & Crack Interfaces")
        heading.setObjectName("heading")
        outer.addWidget(heading)

        desc = QLabel("Define the rebar bar dimensions and place crack interfaces along its length.\n"
                       "Each crack becomes a zero-length element with paired nodes in the OpenSees model.")
        desc.setObjectName("subheading")
        desc.setWordWrap(True)
        outer.addWidget(desc)

        # -- Bar / member properties -----------------------------------
        grp_geo = QGroupBox("Member Geometry")
        form    = QFormLayout(grp_geo)
        form.setSpacing(8)

        _, self.sb_len  = dbl_field("Bar Length", 5.0, 0.01, 1e4, 3, 0.1,
                                     "Total length of the rebar bar (L)")
        _, self.sb_area = dbl_field("Cross-section Area", 1.0, 1e-6, 1e6, 4, 0.1,
                                     "Cross-sectional area of the bar (A)")

        form.addRow("Bar Length  (L):", self.sb_len)
        form.addRow("Area  (A):", self.sb_area)
        outer.addWidget(grp_geo)

        # -- Crack Interfaces ------------------------------------------
        grp_crack = QGroupBox("Crack Interfaces  (ZeroLength Elements)")
        lay_crack = QVBoxLayout(grp_crack)

        btn_row = QHBoxLayout()
        self.btn_add_crack = QPushButton("+ Add Crack")
        self.btn_add_crack.setToolTip("Add a new crack interface along the bar")
        self.btn_remove_crack = QPushButton("Remove Selected")
        self.btn_remove_crack.setObjectName("btn_danger")
        self.btn_remove_crack.setToolTip("Remove the selected crack(s) from the table")
        btn_row.addWidget(self.btn_add_crack)
        btn_row.addWidget(self.btn_remove_crack)
        btn_row.addStretch()
        lay_crack.addLayout(btn_row)

        self.crack_table = QTableWidget(0, 3)
        self.crack_table.setHorizontalHeaderLabels([
            "Position (y)", "kn  (Normal Stiffness)", "kt  (Shear Stiffness)"
        ])
        self.crack_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.crack_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.crack_table.setMinimumHeight(120)
        self.crack_table.setMaximumHeight(220)
        lay_crack.addWidget(self.crack_table)

        help_lbl = QLabel(
            "Position must be between 0 and L (exclusive).  "
            "kn = normal (opening) stiffness,  kt = shear (sliding) stiffness.\n"
            "Values can be entered in scientific notation, e.g. 1e6."
        )
        help_lbl.setObjectName("subheading")
        help_lbl.setWordWrap(True)
        lay_crack.addWidget(help_lbl)
        outer.addWidget(grp_crack)

        # -- BC summary ------------------------------------------------
        grp_bc = QGroupBox("Boundary Conditions  (auto-assigned)")
        lay_bc = QVBoxLayout(grp_bc)
        self.lbl_bc = QLabel("")
        self.lbl_bc.setWordWrap(True)
        self.lbl_bc.setObjectName("subheading")
        lay_bc.addWidget(self.lbl_bc)
        outer.addWidget(grp_bc)
        self._update_bc_label()

        outer.addStretch()

        # Wiring
        self.btn_add_crack.clicked.connect(self._add_crack)
        self.btn_remove_crack.clicked.connect(self._remove_crack)
        self.crack_table.model().rowsInserted.connect(self._update_bc_label)
        self.crack_table.model().rowsRemoved.connect(self._update_bc_label)

    def _add_crack(self):
        row = self.crack_table.rowCount()
        self.crack_table.insertRow(row)
        L = self.sb_len.value()
        y_default = L * (row + 1) / (row + 2)

        self.crack_table.setItem(row, 0, QTableWidgetItem(f"{y_default:.3f}"))
        self.crack_table.setItem(row, 1, QTableWidgetItem("1e6"))
        self.crack_table.setItem(row, 2, QTableWidgetItem("1e4"))
        self.crack_table.selectRow(row)

    def _remove_crack(self):
        rows = sorted(set(idx.row() for idx in self.crack_table.selectedIndexes()),
                       reverse=True)
        for row in rows:
            self.crack_table.removeRow(row)

    def _update_bc_label(self, *_args):
        n_cracks = self.crack_table.rowCount()
        n_nodes  = 2 + 2 * n_cracks
        lines = [
            f"Total nodes: {n_nodes}   |   "
            f"Truss elements: {n_cracks + 1}   |   "
            f"ZeroLength cracks: {n_cracks}",
            "",
            "Node 1 (y=0) :  fixed X, fixed Y  (pin support)",
        ]
        node = 1
        for i in range(n_cracks):
            node += 1
            lines.append(f"Node {node} (below crack {i+1}) :  fixed X, free Y")
            node += 1
            lines.append(f"Node {node} (above crack {i+1}) :  fixed X, free Y")
        node += 1
        lines.append(f"Node {node} (y=L, top) :  fixed X, free Y  (loaded)")
        self.lbl_bc.setText("\n".join(lines))

    def get_params(self) -> dict:
        crack_data = []
        for row in range(self.crack_table.rowCount()):
            try:
                y  = float(self.crack_table.item(row, 0).text())
                kn = float(self.crack_table.item(row, 1).text())
                kt = float(self.crack_table.item(row, 2).text())
                crack_data.append({'y': y, 'kn': kn, 'kt': kt})
            except (ValueError, AttributeError, TypeError):
                pass
        return {
            'bar_length':  self.sb_len.value(),
            'bar_area':    self.sb_area.value(),
            'crack_data':  crack_data,
        }

    def validate(self):
        """Return list of error strings (empty = valid)."""
        errors = []
        L = self.sb_len.value()
        if L <= 0:
            errors.append("Bar length must be > 0.")
        if self.sb_area.value() <= 0:
            errors.append("Cross-section area must be > 0.")
        for row in range(self.crack_table.rowCount()):
            try:
                y = float(self.crack_table.item(row, 0).text())
                if y <= 0 or y >= L:
                    errors.append(f"Crack {row+1}: position y={y} must be between 0 and L={L}.")
                kn = float(self.crack_table.item(row, 1).text())
                if kn <= 0:
                    errors.append(f"Crack {row+1}: kn must be > 0.")
                kt = float(self.crack_table.item(row, 2).text())
                if kt < 0:
                    errors.append(f"Crack {row+1}: kt must be >= 0.")
            except (ValueError, AttributeError, TypeError):
                errors.append(f"Crack {row+1}: invalid numeric values.")
        return errors


# ===================================================================
# Tab 2 - Material
# ===================================================================
class MaterialTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setSpacing(12)

        heading = QLabel("Reinforcement Material")
        heading.setObjectName("heading")
        outer.addWidget(heading)

        desc = QLabel("Define the uniaxial stress-strain behavior for the rebar elements.")
        desc.setObjectName("subheading")
        desc.setWordWrap(True)
        outer.addWidget(desc)

        # -- Type selector ---------------------------------------------
        grp_type = QGroupBox("Material Model")
        lay_type = QVBoxLayout(grp_type)
        row = QHBoxLayout()
        row.addWidget(QLabel("Material type:"))
        self.cmb_mat = QComboBox()
        self.cmb_mat.addItems(['ElasticPP', 'Steel02', 'Elastic'])
        self.cmb_mat.setFixedWidth(180)
        self.cmb_mat.setToolTip(
            "ElasticPP: Elastic-perfectly-plastic (bilinear)\n"
            "Steel02: Giuffre-Menegotto-Pinto (smooth transition)\n"
            "Elastic: Purely linear-elastic"
        )
        row.addWidget(self.cmb_mat)
        row.addStretch()
        lay_type.addLayout(row)
        outer.addWidget(grp_type)

        # -- Common parameters ----------------------------------------
        grp_com = QGroupBox("Common Parameters")
        frm = QFormLayout(grp_com)
        frm.setSpacing(8)
        _, self.sb_Es  = dbl_field("Elastic Modulus (Es)", 200000.0, 1.0, 1e9, 1, 1000.0,
                                    "Young's modulus of the steel reinforcement")
        _, self.sb_fsy = dbl_field("Yield Strength  (fsy)", 500.0,  1.0, 1e6, 1, 10.0,
                                    "Yield stress of the reinforcement")
        frm.addRow("Es:", self.sb_Es)
        frm.addRow("fsy:", self.sb_fsy)
        outer.addWidget(grp_com)

        # -- Steel02-specific ------------------------------------------
        self.grp_s02 = QGroupBox("Steel02 Parameters")
        frm2 = QFormLayout(self.grp_s02)
        frm2.setSpacing(8)
        _, self.sb_b   = dbl_field("Hardening ratio  (b)",  0.01,  0, 1,    4, 0.005,
                                    "Ratio of post-yield tangent to initial elastic tangent")
        _, self.sb_R0  = dbl_field("Transition param (R0)", 15.0,  0, 30,   2, 1.0,
                                    "Controls the transition from elastic to plastic branch")
        _, self.sb_cR1 = dbl_field("cR1",  0.925, 0, 1, 4, 0.01,
                                    "Coefficient for R0 modification on loading reversal")
        _, self.sb_cR2 = dbl_field("cR2",  0.150, 0, 1, 4, 0.01,
                                    "Coefficient for R0 modification on loading reversal")
        frm2.addRow("b:", self.sb_b)
        frm2.addRow("R0:", self.sb_R0)
        frm2.addRow("cR1:", self.sb_cR1)
        frm2.addRow("cR2:", self.sb_cR2)
        self.grp_s02.setEnabled(False)
        outer.addWidget(self.grp_s02)

        self.cmb_mat.currentTextChanged.connect(self._on_mat_changed)

        # -- Reference values table ------------------------------------
        grp_ref = QGroupBox("Quick Reference - Typical Steel Values")
        lay_ref = QVBoxLayout(grp_ref)
        tbl = QTableWidget(3, 3)
        tbl.setHorizontalHeaderLabels(["Grade", "Es (MPa)", "fsy (MPa)"])
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for row_i, (g, e, f) in enumerate([
                ("Grade 300",  200000, 300),
                ("Grade 500",  200000, 500),
                ("A615 Gr 60", 200000, 414)]):
            tbl.setItem(row_i, 0, QTableWidgetItem(g))
            tbl.setItem(row_i, 1, QTableWidgetItem(str(e)))
            tbl.setItem(row_i, 2, QTableWidgetItem(str(f)))
        tbl.setMaximumHeight(120)
        lay_ref.addWidget(tbl)
        outer.addWidget(grp_ref)

        outer.addStretch()

    def _on_mat_changed(self, text):
        self.grp_s02.setEnabled(text == 'Steel02')

    def get_params(self) -> dict:
        return {
            'mat_type':        self.cmb_mat.currentText(),
            'Es':              self.sb_Es.value(),
            'fsy':             self.sb_fsy.value(),
            'hardening_ratio': self.sb_b.value(),
            'R0':              self.sb_R0.value(),
            'cR1':             self.sb_cR1.value(),
            'cR2':             self.sb_cR2.value(),
        }


# ===================================================================
# Tab 3 - Analysis Settings
# ===================================================================
class AnalysisTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setSpacing(12)

        heading = QLabel("Analysis Configuration")
        heading.setObjectName("heading")
        outer.addWidget(heading)

        desc = QLabel("Configure the element type, loading strategy, and nonlinear solver options.")
        desc.setObjectName("subheading")
        desc.setWordWrap(True)
        outer.addWidget(desc)

        # -- Element type ----------------------------------------------
        grp_ele = QGroupBox("Element Type")
        lay_ele = QHBoxLayout(grp_ele)
        lay_ele.addWidget(QLabel("Element:"))
        self.cmb_ele = QComboBox()
        self.cmb_ele.addItems(['Truss', 'corotTruss'])
        self.cmb_ele.setFixedWidth(160)
        self.cmb_ele.setToolTip(
            "Truss: Small-deformation truss element\n"
            "corotTruss: Co-rotational (large deformation) truss"
        )
        lay_ele.addWidget(self.cmb_ele)
        lay_ele.addStretch()
        outer.addWidget(grp_ele)

        # -- Integrator ------------------------------------------------
        grp_int = QGroupBox("Integrator / Loading")
        lay_int = QVBoxLayout(grp_int)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Analysis type:"))
        self.cmb_anl = QComboBox()
        self.cmb_anl.addItems(['DisplacementControl', 'LoadControl'])
        self.cmb_anl.setFixedWidth(200)
        self.cmb_anl.setToolTip(
            "DisplacementControl: Prescribe displacement increments at loaded node\n"
            "LoadControl: Prescribe load factor increments"
        )
        row1.addWidget(self.cmb_anl)
        row1.addStretch()
        lay_int.addLayout(row1)

        self.grp_dc = QGroupBox("Displacement Control Parameters")
        frm_dc = QFormLayout(self.grp_dc)
        frm_dc.setSpacing(8)
        _, self.sb_d_incr   = dbl_field("Disp increment", 0.001, 1e-6, 1000, 5, 0.001,
                                         "Displacement increment per analysis step")
        _, self.sb_d_target = dbl_field("Target displacement", 0.5, 0.001, 1e4, 3, 0.1,
                                         "Total target displacement at loaded node")
        frm_dc.addRow("d per step:", self.sb_d_incr)
        frm_dc.addRow("Target:", self.sb_d_target)
        lay_int.addWidget(self.grp_dc)

        self.grp_lc = QGroupBox("Load Control Parameters")
        frm_lc = QFormLayout(self.grp_lc)
        frm_lc.setSpacing(8)
        _, self.sb_l_incr = dbl_field("Load factor increment", 0.01, 1e-6, 1, 4, 0.01,
                                       "Load factor increment per step (0 to 1)")
        frm_lc.addRow("dLambda per step:", self.sb_l_incr)
        self.grp_lc.setVisible(False)
        lay_int.addWidget(self.grp_lc)

        self.cmb_anl.currentTextChanged.connect(self._on_anl_changed)
        outer.addWidget(grp_int)

        # -- Solver options --------------------------------------------
        grp_sol = QGroupBox("Solver Options")
        frm_sol = QFormLayout(grp_sol)
        frm_sol.setSpacing(8)

        self.cmb_alg = QComboBox()
        self.cmb_alg.addItems(['Newton', 'NewtonLineSearch', 'KrylovNewton', 'ModifiedNewton'])
        self.cmb_alg.setFixedWidth(180)
        self.cmb_alg.setToolTip(
            "Newton: Standard Newton-Raphson\n"
            "NewtonLineSearch: Newton with line search\n"
            "KrylovNewton: Krylov-subspace acceleration\n"
            "ModifiedNewton: Modified Newton (reuses tangent)"
        )

        _, self.sb_tol = dbl_field("Convergence tol", 1e-6, 1e-12, 1e-2, 8, 1e-7,
                                    "NormDispIncr convergence tolerance")
        self.sb_tol.setDecimals(10)
        self.sb_iter = QSpinBox()
        self.sb_iter.setRange(1, 1000)
        self.sb_iter.setValue(100)
        self.sb_iter.setFixedWidth(140)
        self.sb_iter.setToolTip("Maximum Newton-Raphson iterations per step")

        frm_sol.addRow("Algorithm:", self.cmb_alg)
        frm_sol.addRow("Tolerance:", self.sb_tol)
        frm_sol.addRow("Max iterations:", self.sb_iter)
        outer.addWidget(grp_sol)

        outer.addStretch()

    def _on_anl_changed(self, text):
        self.grp_dc.setVisible(text == 'DisplacementControl')
        self.grp_lc.setVisible(text == 'LoadControl')

    def get_params(self) -> dict:
        return {
            'ele_type':      self.cmb_ele.currentText(),
            'analysis_type': self.cmb_anl.currentText(),
            'disp_incr':     self.sb_d_incr.value(),
            'target_disp':   self.sb_d_target.value(),
            'load_incr':     self.sb_l_incr.value(),
            'algorithm':     self.cmb_alg.currentText(),
            'tol':           self.sb_tol.value(),
            'max_iter':      self.sb_iter.value(),
        }


# ===================================================================
# Tab 4 - Run & Console
# ===================================================================
class RunTab(QWidget):
    run_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setSpacing(10)

        heading = QLabel("Run Analysis")
        heading.setObjectName("heading")
        outer.addWidget(heading)

        # -- Buttons ---------------------------------------------------
        btn_row = QHBoxLayout()
        self.btn_run   = QPushButton("Run Analysis")
        self.btn_run.setObjectName("btn_success")
        self.btn_run.setToolTip("Build the OpenSees model and run the analysis")
        self.btn_clear = QPushButton("Clear Console")
        self.btn_script = QPushButton("Export Script")
        self.btn_script.setToolTip("Generate a standalone .py script you can download")
        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(self.btn_clear)
        btn_row.addWidget(self.btn_script)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        # -- Status label ----------------------------------------------
        self.lbl_status = QLabel("Ready.  Configure your model, then click Run.")
        self.lbl_status.setStyleSheet("color: #90aac4; font-size: 13px;")
        outer.addWidget(self.lbl_status)

        # -- Model summary (pre-run) ----------------------------------
        self.grp_summary = QGroupBox("Model Summary  (pre-run check)")
        lay_sum = QVBoxLayout(self.grp_summary)
        self.lbl_summary = QLabel("No model built yet.")
        self.lbl_summary.setWordWrap(True)
        self.lbl_summary.setObjectName("subheading")
        lay_sum.addWidget(self.lbl_summary)
        outer.addWidget(self.grp_summary)

        # -- Console ---------------------------------------------------
        grp_console = QGroupBox("Console Output")
        lay_console = QVBoxLayout(grp_console)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(260)
        lay_console.addWidget(self.console)
        outer.addWidget(grp_console)

        self.btn_run.clicked.connect(self.run_requested.emit)
        self.btn_clear.clicked.connect(self.console.clear)

    def show_summary(self, p):
        n_cracks = len(p.get('crack_data', []))
        n_nodes  = 2 + 2 * n_cracks
        n_eles   = (n_cracks + 1) + n_cracks
        lines = [
            f"Bar:  L = {p['bar_length']},  A = {p['bar_area']}",
            f"Material:  {p['mat_type']}  (Es = {p['Es']},  fsy = {p['fsy']})",
            f"Cracks:  {n_cracks}   |   Nodes: {n_nodes}   |   Elements: {n_eles}",
            f"Analysis:  {p['analysis_type']}   |   Algorithm: {p.get('algorithm', 'Newton')}",
        ]
        if n_cracks > 0:
            crack_data = sorted(p.get('crack_data', []), key=lambda c: c['y'])
            for i, c in enumerate(crack_data):
                lines.append(f"  Crack {i+1}:  y = {c['y']:.3f},  kn = {c['kn']:.2e},  kt = {c['kt']:.2e}")
        self.lbl_summary.setText("\n".join(lines))

    def append_log(self, msg: str):
        self.console.append(msg)
        self.console.verticalScrollBar().setValue(
            self.console.verticalScrollBar().maximum())

    def set_status(self, msg: str, ok: bool = True):
        colour = "#a8d8a8" if ok else "#e87070"
        self.lbl_status.setStyleSheet(f"color: {colour}; font-weight: bold; font-size: 13px;")
        self.lbl_status.setText(msg)


# ===================================================================
# Tab 5 - Results / Plots   (REWRITTEN - crack opening support)
# ===================================================================
class ResultsTab(QWidget):
    _CRACK_COLORS = ['#6ec6f5', '#f5a623', '#e84040', '#a8d8a8', '#c882e8',
                     '#f5e623', '#e87070', '#70e8c8']

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setSpacing(8)

        heading = QLabel("Results & Post-Processing")
        heading.setObjectName("heading")
        outer.addWidget(heading)

        # -- Plot controls ---------------------------------------------
        ctrl = QHBoxLayout()

        ctrl.addWidget(QLabel("Plot:"))
        self.cmb_plot_type = QComboBox()
        self.cmb_plot_type.addItems(['Force - Displacement', 'Crack Opening History'])
        self.cmb_plot_type.setFixedWidth(200)
        self.cmb_plot_type.setToolTip("Select which response quantity to plot")
        ctrl.addWidget(self.cmb_plot_type)

        self.lbl_crack_sel = QLabel("  Crack:")
        self.cmb_crack_sel = QComboBox()
        self.cmb_crack_sel.setFixedWidth(180)
        self.cmb_crack_sel.setToolTip("Select which crack interface to plot")
        self.lbl_crack_sel.setVisible(False)
        self.cmb_crack_sel.setVisible(False)
        ctrl.addWidget(self.lbl_crack_sel)
        ctrl.addWidget(self.cmb_crack_sel)

        ctrl.addWidget(QLabel("  X-axis:"))
        self.cmb_x = QComboBox()
        self.cmb_x.addItems(['Displacement', 'Step'])
        self.cmb_x.setFixedWidth(130)
        ctrl.addWidget(self.cmb_x)

        self.btn_replot = QPushButton("Re-plot")
        self.btn_save   = QPushButton("Save Figure")
        self.btn_export = QPushButton("Export CSV")
        ctrl.addWidget(self.btn_replot)
        ctrl.addWidget(self.btn_save)
        ctrl.addWidget(self.btn_export)
        ctrl.addStretch()
        outer.addLayout(ctrl)

        # -- Canvas ----------------------------------------------------
        self.canvas = MplCanvas()
        outer.addWidget(self.canvas)

        # -- Summary table ---------------------------------------------
        grp_tbl = QGroupBox("Key Results")
        lay_tbl = QVBoxLayout(grp_tbl)
        self.tbl_res = QTableWidget(0, 4)
        self.tbl_res.setHorizontalHeaderLabels(
            ["Step", "Displacement", "Force", "Force/Fy"])
        self.tbl_res.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_res.setMaximumHeight(180)
        lay_tbl.addWidget(self.tbl_res)
        outer.addWidget(grp_tbl)

        # internal storage
        self._disp  = np.array([])
        self._force = np.array([])
        self._fy    = 1.0
        self._crack_openings  = []
        self._crack_positions = []

        self.cmb_plot_type.currentTextChanged.connect(self._on_plot_type_changed)
        self.cmb_crack_sel.currentIndexChanged.connect(self._replot)
        self.cmb_x.currentIndexChanged.connect(self._replot)
        self.btn_replot.clicked.connect(self._replot)
        self.btn_save.clicked.connect(self._save_fig)
        self.btn_export.clicked.connect(self._export_csv)

    def _on_plot_type_changed(self, text):
        is_crack = (text == 'Crack Opening History')
        self.lbl_crack_sel.setVisible(is_crack)
        self.cmb_crack_sel.setVisible(is_crack)
        self._replot()

    def update_results(self, result, fy):
        self._disp  = result['disp']
        self._force = result['force']
        self._fy    = fy if fy else 1.0
        self._crack_openings  = result.get('crack_openings', [])
        self._crack_positions = result.get('crack_positions', [])

        self.cmb_crack_sel.blockSignals(True)
        self.cmb_crack_sel.clear()
        if self._crack_openings:
            self.cmb_crack_sel.addItem("All Cracks (overlay)")
            for i, pos in enumerate(self._crack_positions):
                self.cmb_crack_sel.addItem(f"Crack {i+1}  (y = {pos:.3f})")
        self.cmb_crack_sel.blockSignals(False)

        self._replot()
        self._fill_table()

    def _replot(self):
        if self._disp.size == 0:
            return
        plot_type = self.cmb_plot_type.currentText()
        if plot_type == 'Crack Opening History':
            self._plot_crack_opening()
        else:
            self._plot_force_disp()

    def _plot_force_disp(self):
        x_key = self.cmb_x.currentText()
        x = np.arange(len(self._disp)) if x_key == 'Step' else self._disp
        y = self._force
        xl = 'Step' if x_key == 'Step' else 'Displacement'
        self.canvas.plot(x, y, xlabel=xl, ylabel='Force',
                         title='Load-Displacement Response', label='Response')
        self.canvas.ax.axhline(self._fy, color='#f5a623',
                               linestyle='--', linewidth=1.2, label=f'Fy = {self._fy:.1f}')
        self.canvas.ax.legend(facecolor='#16202c', edgecolor='#3a5068',
                              labelcolor='#dce6f0')
        self.canvas.canvas.draw()

    def _plot_crack_opening(self):
        if not self._crack_openings:
            self.canvas.plot([], [], title='No crack data available')
            return

        self.canvas.ax.cla()
        self.canvas._style_axes()

        sel = self.cmb_crack_sel.currentIndex()
        x_key = self.cmb_x.currentText()
        x = np.arange(len(self._disp)) if x_key == 'Step' else self._disp
        xl = 'Step' if x_key == 'Step' else 'Displacement'

        if sel <= 0:  # "All Cracks" or nothing selected
            for i, co in enumerate(self._crack_openings):
                clr = self._CRACK_COLORS[i % len(self._CRACK_COLORS)]
                pos = self._crack_positions[i]
                self.canvas.ax.plot(x[:len(co)], co, '-o', color=clr,
                                    markersize=3, linewidth=1.8,
                                    label=f'Crack {i+1} (y={pos:.3f})')
        else:
            idx = sel - 1
            if idx < len(self._crack_openings):
                co  = self._crack_openings[idx]
                pos = self._crack_positions[idx]
                clr = self._CRACK_COLORS[idx % len(self._CRACK_COLORS)]
                self.canvas.ax.plot(x[:len(co)], co, '-o', color=clr,
                                    markersize=3, linewidth=1.8,
                                    label=f'Crack {idx+1} (y={pos:.3f})')

        self.canvas.ax.set_xlabel(xl)
        self.canvas.ax.set_ylabel('Crack Opening')
        self.canvas.ax.set_title('Crack Opening History')
        self.canvas.ax.grid(True, alpha=0.2, color='#3a5068')
        self.canvas.ax.legend(facecolor='#16202c', edgecolor='#3a5068',
                              labelcolor='#dce6f0')
        self.canvas.canvas.draw()

    def _fill_table(self):
        self.tbl_res.setRowCount(0)
        n_cracks = len(self._crack_openings)
        cols = ["Step", "Displacement", "Force", "Force/Fy"]
        for i in range(n_cracks):
            cols.append(f"Crack {i+1} Opening")
        self.tbl_res.setColumnCount(len(cols))
        self.tbl_res.setHorizontalHeaderLabels(cols)
        self.tbl_res.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        step = np.arange(1, len(self._disp) + 1)
        indices = list(range(0, len(self._disp), max(1, len(self._disp) // 20)))
        if (len(self._disp) - 1) not in indices:
            indices.append(len(self._disp) - 1)
        for i in indices:
            r = self.tbl_res.rowCount()
            self.tbl_res.insertRow(r)
            self.tbl_res.setItem(r, 0, QTableWidgetItem(str(int(step[i]))))
            self.tbl_res.setItem(r, 1, QTableWidgetItem(f"{self._disp[i]:.5f}"))
            self.tbl_res.setItem(r, 2, QTableWidgetItem(f"{self._force[i]:.3f}"))
            ratio = self._force[i] / self._fy if self._fy else 0
            self.tbl_res.setItem(r, 3, QTableWidgetItem(f"{ratio:.4f}"))
            for ci, co in enumerate(self._crack_openings):
                if i < len(co):
                    self.tbl_res.setItem(r, 4 + ci,
                                          QTableWidgetItem(f"{co[i]:.6f}"))

    def _save_fig(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Figure", "response.png",
            "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if path:
            self.canvas.fig.savefig(path, dpi=150, bbox_inches='tight',
                                    facecolor=self.canvas.fig.get_facecolor())

    def _export_csv(self):
        if self._disp.size == 0:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "results.csv", "CSV (*.csv)")
        if path:
            cols = [
                np.arange(1, len(self._disp) + 1),
                self._disp, self._force,
                self._force / (self._fy if self._fy else 1)
            ]
            header_parts = ['Step', 'Displacement', 'Force', 'Force_over_Fy']
            for i, co in enumerate(self._crack_openings):
                padded = np.zeros(len(self._disp))
                padded[:len(co)] = co
                cols.append(padded)
                header_parts.append(f'Crack{i+1}_Opening')
            data = np.column_stack(cols)
            np.savetxt(path, data, delimiter=',',
                       header=','.join(header_parts), comments='')


# ===================================================================
# Tab 6 - Script Generator
# ===================================================================
class ScriptTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setSpacing(8)

        heading = QLabel("Generated OpenSeesPy Script")
        heading.setObjectName("heading")
        outer.addWidget(heading)

        desc = QLabel("A standalone Python script that reproduces this model.  "
                       "You can download and run it independently.")
        desc.setObjectName("subheading")
        desc.setWordWrap(True)
        outer.addWidget(desc)

        ctrl = QHBoxLayout()
        self.btn_gen  = QPushButton("Generate Script")
        self.btn_gen.setToolTip("Regenerate the script from current model parameters")
        self.btn_copy = QPushButton("Copy to Clipboard")
        self.btn_save = QPushButton("Save .py File")
        ctrl.addWidget(self.btn_gen)
        ctrl.addWidget(self.btn_copy)
        ctrl.addWidget(self.btn_save)
        ctrl.addStretch()
        outer.addLayout(ctrl)

        self.editor = QTextEdit()
        self.editor.setFont(QFont("Consolas", 11))
        outer.addWidget(self.editor)

        self.btn_copy.clicked.connect(self._copy)
        self.btn_save.clicked.connect(self._save)

    def set_script(self, script: str):
        self.editor.setPlainText(script)

    def _copy(self):
        QApplication.clipboard().setText(self.editor.toPlainText())

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Script", "opensees_model.py", "Python (*.py)")
        if path:
            with open(path, 'w') as fh:
                fh.write(self.editor.toPlainText())


# ===================================================================
# Tab - Model Viewer   (REWRITTEN - multi-crack topology)
# ===================================================================
_CRACK_COLORS = {
    'Red':    '#e84040',
    'Orange': '#f5a623',
    'Yellow': '#f5e623',
    'White':  '#dce6f0',
    'Cyan':   '#6ec6f5',
}

class ModelViewTab(QWidget):
    def __init__(self):
        super().__init__()
        self._params = {}
        self._result = None

        self._drawing_mode  = False
        self._hand_cracks   = []
        self._preview_line  = None
        self._press_xy      = None

        outer = QVBoxLayout(self)
        outer.setSpacing(6)

        heading = QLabel("Model Visualisation  &  Crack Annotation")
        heading.setObjectName("heading")
        outer.addWidget(heading)

        # -- Row 1: model view controls --------------------------------
        row1 = QHBoxLayout()
        self.btn_draw   = QPushButton("Draw Model")
        self.btn_draw.setToolTip("Redraw the model using current parameters")
        self.btn_deform = QPushButton("Deformed Shape")
        self.btn_deform.setEnabled(False)
        self.btn_deform.setToolTip("Show the deformed shape from analysis results")
        self.btn_both   = QPushButton("Overlay Both")
        self.btn_both.setEnabled(False)
        self.btn_reset  = QPushButton("Reset View")

        row1.addWidget(self.btn_draw)
        row1.addWidget(self.btn_deform)
        row1.addWidget(self.btn_both)
        row1.addWidget(self.btn_reset)
        row1.addWidget(QLabel("  Deform scale:"))
        self.sb_scale = QDoubleSpinBox()
        self.sb_scale.setRange(1, 10000)
        self.sb_scale.setValue(50)
        self.sb_scale.setSingleStep(10)
        self.sb_scale.setFixedWidth(80)
        self.sb_scale.setToolTip("Scale factor for deformed shape visualisation")
        row1.addWidget(self.sb_scale)
        row1.addStretch()
        outer.addLayout(row1)

        # -- Row 2: hand-draw crack annotation tools -------------------
        grp_hd = QGroupBox("Hand-Draw Crack Annotations  (visual only, click & drag)")
        lay_hd = QHBoxLayout(grp_hd)
        lay_hd.setSpacing(6)

        self.btn_pen = QPushButton("Draw Crack")
        self.btn_pen.setCheckable(True)
        self.btn_pen.setFixedWidth(110)
        self.btn_pen.setToolTip("Toggle freehand crack drawing mode (visual annotation only)")
        self.btn_erase = QPushButton("Undo Last")
        self.btn_clr   = QPushButton("Clear All")
        self.btn_clr.setObjectName("btn_danger")

        lay_hd.addWidget(self.btn_pen)
        lay_hd.addWidget(self.btn_erase)
        lay_hd.addWidget(self.btn_clr)

        lay_hd.addWidget(QLabel("  Color:"))
        self.cmb_color = QComboBox()
        self.cmb_color.addItems(list(_CRACK_COLORS.keys()))
        self.cmb_color.setFixedWidth(80)
        lay_hd.addWidget(self.cmb_color)

        lay_hd.addWidget(QLabel("  Style:"))
        self.cmb_style = QComboBox()
        self.cmb_style.addItems(["Zigzag", "Straight", "Dashed"])
        self.cmb_style.setFixedWidth(80)
        lay_hd.addWidget(self.cmb_style)

        lay_hd.addWidget(QLabel("  Width:"))
        self.sb_lw = QDoubleSpinBox()
        self.sb_lw.setRange(0.5, 6.0)
        self.sb_lw.setValue(2.0)
        self.sb_lw.setSingleStep(0.5)
        self.sb_lw.setFixedWidth(60)
        lay_hd.addWidget(self.sb_lw)

        self.chk_snap = QCheckBox("Snap nodes")
        self.chk_snap.setToolTip("Snap crack endpoints to nearest model node")
        lay_hd.addWidget(self.chk_snap)

        self.lbl_coords = QLabel("  x=--  y=--")
        self.lbl_coords.setStyleSheet("color:#90aac4; font-size:11px;")
        lay_hd.addWidget(self.lbl_coords)
        lay_hd.addStretch()
        outer.addWidget(grp_hd)

        # -- Canvas ----------------------------------------------------
        self.fig = Figure(facecolor='#101820')
        self.ax  = self.fig.add_subplot(111)
        self._style_ax()
        self.canvas  = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setStyleSheet("background:#16202c; color:#dce6f0;")
        outer.addWidget(self.toolbar)
        outer.addWidget(self.canvas)

        # -- Info bar --------------------------------------------------
        grp_info = QGroupBox("Model Summary")
        lay_info = QVBoxLayout(grp_info)
        self.lbl_info = QLabel("Click  'Draw Model'  to preview.  "
                               "Then toggle  Draw Crack  and drag on the canvas for annotations.")
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet("color:#90aac4; font-size:12px;")
        lay_info.addWidget(self.lbl_info)
        grp_info.setMaximumHeight(80)
        outer.addWidget(grp_info)

        # -- Button wiring ---------------------------------------------
        self.btn_draw.clicked.connect(self._draw_undeformed)
        self.btn_deform.clicked.connect(self._draw_deformed)
        self.btn_both.clicked.connect(self._draw_both)
        self.btn_reset.clicked.connect(self._reset_view)
        self.btn_pen.toggled.connect(self._toggle_draw_mode)
        self.btn_erase.clicked.connect(self._undo_crack)
        self.btn_clr.clicked.connect(self._clear_cracks)

        self.canvas.mpl_connect('button_press_event',   self._mp_press)
        self.canvas.mpl_connect('motion_notify_event',  self._mp_move)
        self.canvas.mpl_connect('button_release_event', self._mp_release)

    # -- axes style ----------------------------------------------------
    def _style_ax(self):
        self.ax.set_facecolor('#101820')
        self.ax.tick_params(colors='#90aac4')
        self.ax.xaxis.label.set_color('#dce6f0')
        self.ax.yaxis.label.set_color('#dce6f0')
        self.ax.title.set_color('#6ec6f5')
        for spine in self.ax.spines.values():
            spine.set_edgecolor('#3a5068')

    # -- called from MainWindow ----------------------------------------
    def set_params(self, p):
        self._params = p

    def set_result(self, result):
        self._result = result
        self.btn_deform.setEnabled(True)
        self.btn_both.setEnabled(True)

    # -- build topology from params (matches run_opensees_model) -------
    def _build_topology(self):
        L = self._params.get('bar_length', 5.0)
        crack_data = sorted(self._params.get('crack_data', []), key=lambda c: c['y'])
        crack_data = [c for c in crack_data if 0.001 * L < c['y'] < 0.999 * L]

        nodes    = {}   # tag -> np.array([x, y])
        trusses  = []   # (tag, ni, nj)
        cracks   = []   # (tag, n_below, n_above, y_pos)
        n_tag = 0
        e_tag = 0

        n_tag += 1
        nodes[n_tag] = np.array([0.0, 0.0])
        prev = n_tag

        for ci, cd in enumerate(crack_data):
            y_c = cd['y']
            n_tag += 1; nodes[n_tag] = np.array([0.0, y_c])
            n_below = n_tag
            e_tag += 1; trusses.append((e_tag, prev, n_below))

            n_tag += 1; nodes[n_tag] = np.array([0.0, y_c])
            n_above = n_tag
            e_tag += 1; cracks.append((e_tag, n_below, n_above, y_c))

            prev = n_above

        n_tag += 1; nodes[n_tag] = np.array([0.0, L])
        e_tag += 1; trusses.append((e_tag, prev, n_tag))

        return nodes, trusses, cracks, crack_data

    def _crack_color(self):
        return _CRACK_COLORS.get(self.cmb_color.currentText(), '#e84040')

    def _snap(self, x, y):
        if not self.chk_snap.isChecked() or not self._params:
            return x, y
        nodes, _, _, _ = self._build_topology()
        L   = self._params.get('bar_length', 1.0)
        tol = L * 0.06
        best, best_d = None, float('inf')
        for coord in nodes.values():
            d = np.hypot(x - coord[0], y - coord[1])
            if d < best_d:
                best_d, best = d, coord
        if best is not None and best_d < tol:
            return best[0], best[1]
        return x, y

    # -- draw-mode toggle ----------------------------------------------
    def _toggle_draw_mode(self, on):
        self._drawing_mode = on
        if on:
            self.btn_pen.setText("Drawing...")
            self.btn_pen.setStyleSheet("background:#8b2020; color:#fff; font-weight:bold;")
            self.toolbar.setEnabled(False)
            self.canvas.setCursor(Qt.CrossCursor)
        else:
            self.btn_pen.setText("Draw Crack")
            self.btn_pen.setStyleSheet("")
            self.toolbar.setEnabled(True)
            self.canvas.setCursor(Qt.ArrowCursor)
            if self._preview_line:
                try: self._preview_line.remove()
                except ValueError: pass
                self._preview_line = None
            self._press_xy = None
            self.canvas.draw_idle()

    # -- matplotlib mouse handlers -------------------------------------
    def _mp_press(self, event):
        if not self._drawing_mode or event.inaxes != self.ax:
            return
        if event.button == 1 and event.xdata is not None:
            self._press_xy = self._snap(event.xdata, event.ydata)
        elif event.button == 3:
            self._press_xy = None
            if self._preview_line:
                try: self._preview_line.remove()
                except ValueError: pass
                self._preview_line = None
            self.canvas.draw_idle()

    def _mp_move(self, event):
        if not self._drawing_mode or self._press_xy is None:
            return
        if event.inaxes != self.ax or event.xdata is None:
            return
        x0, y0 = self._press_xy
        x1, y1 = self._snap(event.xdata, event.ydata)
        self.lbl_coords.setText(f"  x={x1:.3f}  y={y1:.3f}")
        if self._preview_line:
            try: self._preview_line.remove()
            except ValueError: pass
        self._preview_line, = self.ax.plot(
            [x0, x1], [y0, y1],
            color=self._crack_color(), lw=1.4,
            linestyle='--', alpha=0.65, zorder=15)
        self.canvas.draw_idle()

    def _mp_release(self, event):
        if not self._drawing_mode or event.button != 1:
            return
        if self._press_xy is None or event.inaxes != self.ax or event.xdata is None:
            return
        x0, y0 = self._press_xy
        x1, y1 = self._snap(event.xdata, event.ydata)
        length = np.hypot(x1 - x0, y1 - y0)
        if length > 1e-10:
            self._hand_cracks.append({
                'xy':    ((x0, y0), (x1, y1)),
                'color': self._crack_color(),
                'lw':    self.sb_lw.value(),
                'style': self.cmb_style.currentText(),
            })
        if self._preview_line:
            try: self._preview_line.remove()
            except ValueError: pass
            self._preview_line = None
        self._press_xy = None
        self._refresh()

    def _undo_crack(self):
        if self._hand_cracks:
            self._hand_cracks.pop()
            self._refresh()

    def _clear_cracks(self):
        self._hand_cracks.clear()
        self._refresh()

    # -- render a single user crack annotation -------------------------
    def _render_crack(self, crack):
        (x0, y0), (x1, y1) = crack['xy']
        color = crack['color']
        lw    = crack['lw']
        style = crack['style']
        length = np.hypot(x1 - x0, y1 - y0)

        if style == 'Zigzag' and length > 0:
            n_seg = max(6, int(length / (self._params.get('bar_length', 1) * 0.04)))
            dx = (x1 - x0) / n_seg
            dy = (y1 - y0) / n_seg
            amp = length * 0.04
            px = -(y1 - y0) / length * amp
            py =  (x1 - x0) / length * amp
            xs, ys = [x0], [y0]
            for i in range(1, n_seg):
                sign = 1 if i % 2 else -1
                xs.append(x0 + i * dx + sign * px)
                ys.append(y0 + i * dy + sign * py)
            xs.append(x1); ys.append(y1)
            self.ax.plot(xs, ys, color=color, lw=lw, zorder=12)
        elif style == 'Dashed':
            self.ax.plot([x0, x1], [y0, y1],
                         color=color, lw=lw, linestyle='--', zorder=12)
        else:
            self.ax.plot([x0, x1], [y0, y1],
                         color=color, lw=lw, zorder=12)

        angle  = np.degrees(np.arctan2(y1 - y0, x1 - x0))
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        L_ref  = self._params.get('bar_length', 1.0)
        self.ax.text(mx + L_ref * 0.03, my, f"{length:.2g} | {angle:.0f} deg",
                     color=color, fontsize=7, va='bottom', alpha=0.85, zorder=13)

    # -- structural model drawing helpers ------------------------------
    def _draw_support_pin(self, ax, x, y, s):
        ax.fill([x-s, x+s, x, x-s], [y-s, y-s, y, y-s],
                color='#f5a623', alpha=0.85, zorder=3)
        ax.plot([x-s*1.3, x+s*1.3], [y-s, y-s], color='#f5a623', lw=2, zorder=3)

    def _draw_support_roller(self, ax, x, y, s):
        ax.add_patch(plt.Circle((x, y-s*0.6), s*0.45,
                                color='#6ec6f5', zorder=3, alpha=0.85))
        ax.plot([x-s*1.3, x+s*1.3], [y-s*1.15, y-s*1.15],
                color='#6ec6f5', lw=2)

    def _draw_load_arrow(self, ax, x, y, L):
        al = L * 0.18
        ax.annotate('', xy=(x, y), xytext=(x, y + al),
                    arrowprops=dict(arrowstyle='->', color='#e87070',
                                   lw=2.2, mutation_scale=18))
        ax.text(x + L*0.04, y + al*0.5, 'F',
                color='#e87070', fontsize=11, fontweight='bold', va='center')

    def _draw_spring_symbol(self, ax, x, y, L, label=''):
        """Draw a zigzag spring symbol at a crack location."""
        w, n_coils = L * 0.04, 4
        seg_h = L * 0.012
        xs = [x]
        ys = [y - seg_h * n_coils / 2]
        for i in range(1, n_coils + 1):
            side = w if i % 2 else -w
            xs.append(x + side)
            ys.append(y - seg_h * n_coils / 2 + i * seg_h)
        xs.append(x)
        ys.append(y + seg_h * n_coils / 2)
        ax.plot(xs, ys, color='#e84040', lw=2.5, zorder=5)
        if label:
            ax.text(x + L * 0.05, y, label, color='#e84040',
                    fontsize=8, va='center', zorder=6)

    def _draw_dim(self, ax, x, y0, y1, L):
        off = L * 0.12
        ax.annotate('', xy=(x+off, y1), xytext=(x+off, y0),
                    arrowprops=dict(arrowstyle='<->', color='#90aac4', lw=1.2))
        ax.text(x+off*1.35, (y0+y1)/2, f'L = {L:.3g}',
                color='#90aac4', fontsize=9, va='center')

    def _draw_model(self, ax, deformed=False, result=None, scale=50.0, alpha=1.0):
        """Draw the full multi-crack bar model."""
        if not self._params:
            return

        nodes, trusses, cracks, crack_data = self._build_topology()
        L = self._params['bar_length']

        # Compute deformed positions if requested
        deformed_nodes = {}
        if deformed and result is not None and len(result.get('disp', [])) > 0:
            total_disp = result['disp'][-1]
            crack_opens = [co[-1] if len(co) > 0 else 0.0
                           for co in result.get('crack_openings', [])]
            total_crack_open = sum(crack_opens)
            bar_deform = total_disp - total_crack_open
            n_trusses = len(trusses)
            seg_deform = bar_deform / n_trusses if n_trusses > 0 else 0

            cum_deform = 0.0
            n_tag = 0

            n_tag += 1
            deformed_nodes[n_tag] = np.array([0.0, 0.0])

            crack_idx = 0
            for ci, cd in enumerate(crack_data):
                n_tag += 1
                cum_deform += seg_deform
                deformed_nodes[n_tag] = np.array([0.0, cd['y'] + cum_deform * scale])

                n_tag += 1
                if crack_idx < len(crack_opens):
                    cum_deform += crack_opens[crack_idx]
                deformed_nodes[n_tag] = np.array([0.0, cd['y'] + cum_deform * scale])
                crack_idx += 1

            n_tag += 1
            cum_deform += seg_deform
            deformed_nodes[n_tag] = np.array([0.0, L + cum_deform * scale])

        # Draw truss elements
        for idx_t, (etag, ni, nj) in enumerate(trusses):
            p1 = nodes[ni]
            p2 = nodes[nj]
            if deformed and deformed_nodes:
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]],
                        color='#3a5068', lw=3, alpha=0.3, linestyle='--')
                d1, d2 = deformed_nodes[ni], deformed_nodes[nj]
                ax.plot([d1[0], d2[0]], [d1[1], d2[1]],
                        color='#a8d8a8', lw=3.5, alpha=alpha, zorder=4)
            else:
                lbl = 'Truss (rebar)' if idx_t == 0 else ''
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]],
                        color='#6ec6f5', lw=4, alpha=alpha, zorder=4, label=lbl)

        # Draw crack (zeroLength) elements
        for i, (etag, nb, na, y_c) in enumerate(cracks):
            if deformed and deformed_nodes:
                dy = deformed_nodes[na][1] - deformed_nodes[nb][1]
                mid_y = (deformed_nodes[na][1] + deformed_nodes[nb][1]) / 2
                self._draw_spring_symbol(ax, 0.0, mid_y, L,
                                          label=f'C{i+1}  dw={dy:.4f}')
            else:
                self._draw_spring_symbol(ax, 0.0, y_c, L,
                                          label=f'Crack {i+1}')

        # Draw nodes
        drawn_nodes = deformed_nodes if (deformed and deformed_nodes) else nodes
        for tag, coord in drawn_nodes.items():
            ax.plot(coord[0], coord[1], 'o', color='#f5a623', ms=9, zorder=7)
            ax.text(coord[0] - L*0.06, coord[1], f' N{tag}',
                    color='#f5a623', fontsize=8, va='center', ha='right')

        # Supports and load arrow
        base = drawn_nodes[1]
        top_tag = max(drawn_nodes.keys())
        top  = drawn_nodes[top_tag]

        s = L * 0.07
        self._draw_support_pin(ax, base[0], base[1], s)
        self._draw_support_roller(ax, top[0], top[1], s)
        self._draw_load_arrow(ax, top[0], top[1], L)
        self._draw_dim(ax, base[0], base[1], nodes[max(nodes.keys())][1], L)

        if deformed and result is not None and len(result.get('disp', [])) > 0:
            ax.annotate(
                f"d = {result['disp'][-1]:.4f}\nF = {result['force'][-1]:.2f}",
                xy=top, color='#a8d8a8', fontsize=9, va='bottom',
                xytext=(top[0] + L*0.1, top[1]),
                arrowprops=dict(arrowstyle='->', color='#a8d8a8', lw=1))

        ax.axhline(0, color='#3a5068', lw=0.6, alpha=0.4)
        ax.axvline(0, color='#3a5068', lw=0.6, alpha=0.4)
        ax.set_xlabel('x'); ax.set_ylabel('y')
        ax.grid(True, alpha=0.15, color='#3a5068')
        ax.set_aspect('equal', adjustable='datalim')
        pad = L * 0.35
        ax.set_xlim(-pad, pad)
        ax.set_ylim(-L*0.25, L*1.45)
        if ax.get_legend_handles_labels()[1]:
            ax.legend(facecolor='#16202c', edgecolor='#3a5068',
                      labelcolor='#dce6f0', fontsize=9, loc='upper right')

    # -- full refresh --------------------------------------------------
    def _refresh(self):
        if not self._params:
            return
        L = self._params['bar_length']
        try:
            xlim = self.ax.get_xlim()
            ylim = self.ax.get_ylim()
            had_limits = (xlim != (0.0, 1.0))
        except Exception:
            had_limits = False

        self.ax.cla()
        self._style_ax()
        self._draw_model(self.ax)
        for c in self._hand_cracks:
            self._render_crack(c)

        if had_limits:
            self.ax.set_xlim(xlim)
            self.ax.set_ylim(ylim)

        n_annot = len(self._hand_cracks)
        n_model = len(self._params.get('crack_data', []))
        parts = []
        if n_model: parts.append(f'{n_model} model crack{"s" if n_model != 1 else ""}')
        if n_annot: parts.append(f'{n_annot} annotation{"s" if n_annot != 1 else ""}')
        self.ax.set_title('Model  (' + ',  '.join(parts) + ')' if parts else 'Model')
        self.canvas.draw_idle()
        self._update_info()

    def _clear_ax(self):
        self.ax.cla()
        self._style_ax()

    def _draw_undeformed(self):
        if not self._params:
            self.lbl_info.setText("Set parameters first.")
            return
        self._refresh()

    def _draw_deformed(self):
        if self._result is None:
            self.lbl_info.setText("Run analysis first.")
            return
        scl = self.sb_scale.value()
        self._clear_ax()
        self._draw_model(self.ax, deformed=True, result=self._result, scale=scl)
        for c in self._hand_cracks:
            self._render_crack(c)
        self.ax.set_title(f'Deformed Shape  (x{scl:.0f})')
        self.canvas.draw()

    def _draw_both(self):
        if self._result is None:
            return
        scl = self.sb_scale.value()
        self._clear_ax()
        self._draw_model(self.ax, alpha=0.3)
        self._draw_model(self.ax, deformed=True, result=self._result, scale=scl)
        for c in self._hand_cracks:
            self._render_crack(c)
        self.ax.set_title(f'Undeformed + Deformed  (x{scl:.0f})')
        self.canvas.draw()

    def _reset_view(self):
        if not self._params:
            return
        L   = self._params.get('bar_length', 5.0)
        pad = L * 0.35
        self.ax.set_xlim(-pad, pad)
        self.ax.set_ylim(-L*0.25, L*1.45)
        self.canvas.draw_idle()

    def _update_info(self):
        if not self._params:
            return
        p = self._params
        L = p['bar_length']
        crack_data = p.get('crack_data', [])
        n_cracks = len(crack_data)
        n_nodes = 2 + 2 * n_cracks
        n_eles  = (n_cracks + 1) + n_cracks
        n_annot = len(self._hand_cracks)

        parts = [
            f"Nodes: {n_nodes}",
            f"Elements: {n_eles}  ({n_cracks+1} truss + {n_cracks} zeroLength)",
            f"L={L:.4g}",
            f"A={p.get('bar_area', 1):.4g}",
            f"Mat: {p.get('mat_type', '?')}",
            f"Es={p.get('Es', 0):.4g}",
            f"fsy={p.get('fsy', 0):.4g}",
        ]
        if n_annot:
            parts.append(f"{n_annot} annotation(s)")
        self.lbl_info.setText("    ".join(parts))


# ===================================================================
# Script builder  (REWRITTEN - multi-crack support)
# ===================================================================
def build_script(p):
    mat    = p['mat_type']
    Es     = p['Es'];  fsy = p['fsy']
    L      = p['bar_length'];  A = p['bar_area']
    anl    = p['analysis_type']
    algo   = p['algorithm']
    tol    = p['tol'];  mi = p['max_iter']
    ele_t  = p['ele_type']

    crack_data = sorted(p.get('crack_data', []), key=lambda c: c['y'])
    crack_data = [c for c in crack_data if 0.001 * L < c['y'] < 0.999 * L]

    lines = [
        '"""',
        'OpenSeesPy Model - Multi-Surface Crack 2D',
        f'Auto-generated by the GUI  |  {len(crack_data)} crack(s)',
        '"""',
        'import openseespy.opensees as ops',
        'import numpy as np',
        'import matplotlib.pyplot as plt',
        '',
        '# == Model setup ============================================================',
        'ops.wipe()',
        "ops.model('basic', '-ndm', 2, '-ndf', 2)",
        '',
        '# == Material ================================================================',
    ]

    if mat == 'ElasticPP':
        eps_y = fsy / Es
        lines.append(f"ops.uniaxialMaterial('ElasticPP', 1, {Es}, {eps_y:.6f})  # Es={Es}, fsy={fsy}")
    elif mat == 'Steel02':
        b = p['hardening_ratio']; R0 = p['R0']; cR1 = p['cR1']; cR2 = p['cR2']
        lines.append(f"ops.uniaxialMaterial('Steel02', 1, {fsy}, {Es}, {b}, {R0}, {cR1}, {cR2})")
    else:
        lines.append(f"ops.uniaxialMaterial('Elastic', 1, {Es})")

    lines += ['', '# == Nodes & Boundary Conditions ============================================']

    node_tag = 0; ele_tag = 0; prev_node = None
    truss_cmds = []; crack_cmds = []

    node_tag += 1
    lines.append(f'ops.node({node_tag}, 0.0, 0.0)')
    lines.append(f'ops.fix({node_tag}, 1, 1)  # pinned base')
    prev_node = node_tag

    for ci, crack in enumerate(crack_data):
        y_c = crack['y']; kn = crack['kn']; kt = crack['kt']

        node_tag += 1; n_below = node_tag
        lines.append(f'ops.node({n_below}, 0.0, {y_c})  # below crack {ci+1}')
        lines.append(f'ops.fix({n_below}, 1, 0)')
        ele_tag += 1
        truss_cmds.append(f"ops.element('{ele_t}', {ele_tag}, {prev_node}, {n_below}, {A}, 1)")

        node_tag += 1; n_above = node_tag
        lines.append(f'ops.node({n_above}, 0.0, {y_c})  # above crack {ci+1}')
        lines.append(f'ops.fix({n_above}, 1, 0)')

        mx = 10 + ci * 2; my = 11 + ci * 2
        crack_cmds.append(f"ops.uniaxialMaterial('Elastic', {mx}, {max(kt, 1.0)})  # shear crack {ci+1}")
        crack_cmds.append(f"ops.uniaxialMaterial('Elastic', {my}, {kn})  # normal crack {ci+1}")
        ele_tag += 1
        crack_cmds.append(
            f"ops.element('zeroLength', {ele_tag}, {n_below}, {n_above}, "
            f"'-mat', {mx}, {my}, '-dir', 1, 2)  # crack {ci+1}")

        prev_node = n_above

    node_tag += 1; top_tag = node_tag
    lines.append(f'ops.node({top_tag}, 0.0, {L})  # loaded tip')
    lines.append(f'ops.fix({top_tag}, 1, 0)')
    ele_tag += 1
    truss_cmds.append(f"ops.element('{ele_t}', {ele_tag}, {prev_node}, {top_tag}, {A}, 1)")

    first_truss_tag = 1

    if crack_cmds:
        lines += ['', '# == Crack Interface Materials & Elements ====================================']
        lines += crack_cmds

    lines += ['', '# == Truss Elements ==========================================================']
    lines += truss_cmds

    lines += [
        '',
        '# == Load pattern ============================================================',
        "ops.timeSeries('Linear', 1)",
        "ops.pattern('Plain', 1, 1)",
    ]
    ref_force = fsy * A
    if anl == 'LoadControl':
        lines.append(f"ops.load({top_tag}, 0.0, {ref_force})  # ref = Fy*A")
    else:
        lines.append(f"ops.load({top_tag}, 0.0, 1.0)  # unit reference for DispControl")

    lines += [
        '',
        '# == Analysis setup ==========================================================',
        "ops.constraints('Plain')",
        "ops.numberer('Plain')",
        "ops.system('BandGeneral')",
        f"ops.algorithm('{algo}')",
        f"ops.test('NormDispIncr', {tol}, {mi})",
    ]

    if anl == 'LoadControl':
        incr = p['load_incr']; steps = int(1.0 / incr)
        lines += [
            f"ops.integrator('LoadControl', {incr})",
            "ops.analysis('Static')",
        ]
    else:
        target = p['target_disp']; incr = p['disp_incr']
        steps = int(abs(target) / abs(incr))
        lines += [
            f"ops.integrator('DisplacementControl', {top_tag}, 2, {incr})",
            "ops.analysis('Static')",
        ]

    # Build crack node pairs for recording
    crack_node_pairs = []
    n = 1
    for ci in range(len(crack_data)):
        n_below = n + 1 + ci * 2
        n_above = n + 2 + ci * 2
        crack_node_pairs.append((n_below, n_above))

    lines += [
        '',
        '# == Run & collect results ===================================================',
        'disp_list  = []',
        'force_list = []',
    ]

    if crack_data:
        lines.append(f'crack_openings = [[] for _ in range({len(crack_data)})]')
        lines.append(f'crack_node_pairs = {crack_node_pairs}')

    lines += [
        '',
        f'for step in range({steps}):',
        '    ok = ops.analyze(1)',
        '    if ok == 0:',
        f'        disp_list.append(ops.nodeDisp({top_tag}, 2))',
        f'        force_list.append(-ops.eleForce({first_truss_tag}, 2))',
    ]

    if crack_data:
        lines += [
            '        for k, (nb, na) in enumerate(crack_node_pairs):',
            '            crack_openings[k].append(ops.nodeDisp(na, 2) - ops.nodeDisp(nb, 2))',
        ]

    lines += [
        '    else:',
        '        print(f"Analysis failed at step {step}"); break',
        '',
        'disp  = np.array(disp_list)',
        'force = np.array(force_list)',
        'print(f"Completed {len(disp_list)} steps")',
    ]

    # Plot
    if crack_data:
        lines += [
            '',
            '# == Plot ====================================================================',
            'fig, axes = plt.subplots(1, 2, figsize=(12, 5))',
            '',
            "axes[0].plot(disp, force, '-o', markersize=3, linewidth=1.8)",
            "axes[0].set_xlabel('Displacement')",
            "axes[0].set_ylabel('Force')",
            "axes[0].set_title('Load-Displacement Response')",
            "axes[0].grid(True, alpha=0.3)",
            '',
            f'for i in range({len(crack_data)}):',
            '    co = np.array(crack_openings[i])',
            '    axes[1].plot(disp[:len(co)], co, "-o", markersize=3, linewidth=1.8,',
            '                label=f"Crack {i+1}")',
            "axes[1].set_xlabel('Displacement')",
            "axes[1].set_ylabel('Crack Opening')",
            "axes[1].set_title('Crack Opening History')",
            "axes[1].legend()",
            "axes[1].grid(True, alpha=0.3)",
        ]
    else:
        lines += [
            '',
            '# == Plot ====================================================================',
            "plt.figure(figsize=(7, 5))",
            "plt.plot(disp, force, '-o', markersize=3, linewidth=1.8)",
            "plt.xlabel('Displacement')",
            "plt.ylabel('Force')",
            "plt.title('Load-Displacement Response')",
            "plt.grid(True, alpha=0.3)",
        ]

    lines += ['', 'plt.tight_layout()', 'plt.show()']
    return '\n'.join(lines)


# ===================================================================
# Main Window   (FIXED - proper crack_data flow + validation)
# ===================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multi-Surface Crack 2D  |  OpenSeesPy GUI")
        self.setMinimumSize(1100, 750)
        self._worker = None
        self._last_result = None

        central = QWidget()
        self.setCentralWidget(central)
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(10, 10, 10, 10)

        title = QLabel("Multi-Surface Crack 2D  -  OpenSeesPy Interactive Analyser")
        title.setObjectName("heading")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:17px; padding:6px; color:#6ec6f5;")
        main_lay.addWidget(title)

        self.tabs = QTabWidget()
        self.tab_geo  = GeometryTab()
        self.tab_mat  = MaterialTab()
        self.tab_anl  = AnalysisTab()
        self.tab_view = ModelViewTab()
        self.tab_run  = RunTab()
        self.tab_res  = ResultsTab()
        self.tab_scr  = ScriptTab()

        self.tabs.addTab(self.tab_geo,  "  1. Geometry  ")
        self.tabs.addTab(self.tab_mat,  "  2. Material  ")
        self.tabs.addTab(self.tab_anl,  "  3. Analysis  ")
        self.tabs.addTab(self.tab_view, "  4. Model View  ")
        self.tabs.addTab(self.tab_run,  "  5. Run  ")
        self.tabs.addTab(self.tab_res,  "  6. Results  ")
        self.tabs.addTab(self.tab_scr,  "  7. Script  ")
        main_lay.addWidget(self.tabs)

        self.statusBar().showMessage("Ready  |  OpenSeesPy GUI  v2.0  |  Multi-Crack Support")
        self.statusBar().setStyleSheet("background:#16202c; color:#90aac4;")

        self.tab_run.run_requested.connect(self._start_analysis)
        self.tab_run.btn_script.clicked.connect(self._generate_script)
        self.tab_scr.btn_gen.clicked.connect(self._generate_script)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        QTimer.singleShot(500, self._check_opensees)

    def _on_tab_changed(self, idx):
        widget = self.tabs.widget(idx)
        if widget is self.tab_view:
            p = self._collect_params()
            self.tab_view.set_params(p)
            self.tab_view._draw_undeformed()
        elif widget is self.tab_run:
            p = self._collect_params()
            self.tab_run.show_summary(p)

    def _collect_params(self):
        p = {}
        p.update(self.tab_geo.get_params())
        p.update(self.tab_mat.get_params())
        p.update(self.tab_anl.get_params())
        return p

    def _check_opensees(self):
        try:
            import openseespy.opensees as ops
            ver = ops.pyversion()
            self.tab_run.append_log(f"OpenSeesPy detected - version {ver}")
            self.statusBar().showMessage(f"OpenSeesPy v{ver}  |  Ready  |  Multi-Crack Support")
        except Exception:
            self.tab_run.append_log("WARNING: OpenSeesPy could not be imported.")
            self.tab_run.append_log("  Install with:  pip install openseespy")
            self.tab_run.append_log("  You can still configure the model and export scripts.")

    def _start_analysis(self):
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Busy", "Analysis already running.")
            return

        errors = self.tab_geo.validate()
        if errors:
            QMessageBox.warning(self, "Validation Error",
                                "Please fix the following issues:\n\n" + "\n".join(errors))
            return

        p = self._collect_params()
        self.tab_run.show_summary(p)
        self.tab_run.set_status("Running...", ok=True)
        self.tab_run.btn_run.setEnabled(False)
        self.tab_run.append_log("\n" + "-" * 50)
        self.tab_run.append_log("Starting analysis...")

        self._worker = AnalysisWorker(p)
        self._worker.log.connect(self.tab_run.append_log)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, result):
        self.tab_run.btn_run.setEnabled(True)
        msg = result['message']
        if result['status'] == 'ok':
            self.tab_run.set_status(f"Done - {msg}", ok=True)
            self.tab_run.append_log(f"SUCCESS: {msg}")
            self._last_result = result
            p = self._collect_params()
            fy = p['fsy'] * p['bar_area']
            self.tab_res.update_results(result, fy)
            self.tab_view.set_params(p)
            self.tab_view.set_result(result)
            self.tabs.setCurrentWidget(self.tab_res)
        else:
            self.tab_run.set_status("Analysis failed - check console.", ok=False)
            self.tab_run.append_log("FAILED: no converged steps.")

    def _on_error(self, tb):
        self.tab_run.btn_run.setEnabled(True)
        self.tab_run.set_status("Error - see console.", ok=False)
        self.tab_run.append_log("\nERROR:\n" + tb)

    def _generate_script(self):
        p = self._collect_params()
        script = build_script(p)
        self.tab_scr.set_script(script)
        self.tabs.setCurrentWidget(self.tab_scr)


# ===================================================================
# Entry point
# ===================================================================
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
