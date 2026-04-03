#!/usr/bin/env python3
"""
RC Panel Crack Analysis — OpenSeesPy Desktop GUI

A plane-stress panel analysis tool for studying crack behavior in
reinforced concrete. Generates triangular meshes, assigns crack interface
elements, runs the analysis through an OpenSeesPy backend, and plots results.

Crack interface materials
  - MultiSurfCrack2D  requires a custom OpenSees build with the model compiled in
  - EPPGap Macro      4-spring fallback that works with standard openseespy
  - Elastic / ElasticPPGap / CustomBilinear  simple alternatives

Quick start
  python gui_wsl.py

Requirements
  PyQt5 >= 5.15, matplotlib >= 3.7, numpy >= 1.24, openseespy

Architecture
  GeometryTab       panel dimensions, mesh generation, crack placement, BCs
  CrackMaterialTab  per-element crack material assignment
  AnalysisTab       solver settings and loading protocol
  RunTab            launches OpenSeesPy via WSL subprocess, streams output
  ResultsTab        force-displacement, crack histories, deformed mesh plots
  ScriptTab         exports a standalone runnable OpenSeesPy script
"""

import sys, json, time, math, traceback, subprocess, shlex
from pathlib import Path
import numpy as np

REQUIREMENTS = """
PyQt5>=5.15
matplotlib>=3.7
numpy>=1.24
openseespy
"""

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QTextEdit, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QDoubleSpinBox, QSpinBox, QFileDialog,
    QMessageBox, QCheckBox, QSplitter, QScrollArea,
    QFrame, QSlider, QAbstractItemView, QDialog, QAbstractSpinBox,
    QSizePolicy, QAction, QMenu, QRadioButton,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject, QEvent
from PyQt5.QtGui import (
    QFont, QPainter, QPen, QBrush, QColor,
    QPainterPath, QFontMetrics, QImage,
)

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.tri import Triangulation


# colour palette / constants , shared theme and app settings

BG_DEEP  = "#0d1117"
BG_PANEL = "#161b22"
BG_CARD  = "#1c2128"
BG_INPUT = "#111827"
BORDER   = "#455063"
C1       = "#58a6ff"   # blue
C2       = "#3fb950"   # green
C3       = "#f78166"   # red
C4       = "#d2a679"   # amber
TXT      = "#e6edf3"
TXTS     = "#b8c2cf"
CRACK_BELOW = "#ff8c42"   # orange  — node on the BELOW side of a crack
CRACK_ABOVE = "#c084fc"   # violet  — node on the ABOVE side of a crack

STYLE = f"""
QMainWindow,QDialog{{background:{BG_DEEP};}}
QWidget{{background:{BG_DEEP};color:{TXT};
  font-family:'Segoe UI','Cascadia Code','Consolas',sans-serif;font-size:13px;}}
QScrollArea,QScrollArea>QWidget,QScrollArea>QWidget>QWidget{{background:{BG_DEEP};}}
QTabWidget::pane{{border:1px solid {BORDER};background:{BG_PANEL};border-radius:0 4px 4px 4px;}}
QTabBar::tab{{background:{BG_DEEP};color:{TXTS};padding:9px 20px;
  border:1px solid {BORDER};border-bottom:none;border-radius:4px 4px 0 0;
    font-weight:bold;font-size:12px;margin-right:2px;min-height:20px;}}
QTabBar::tab:selected{{background:{BG_PANEL};color:{C1};border-bottom:2px solid {C1};}}
QTabBar::tab:hover:!selected{{color:{TXT};background:{BG_CARD};}}
QGroupBox{{border:1px solid {BORDER};border-radius:6px;margin-top:16px;
    padding:16px 12px 12px 12px;color:{C1};font-weight:bold;font-size:12px;letter-spacing:.6px;}}
QGroupBox::title{{subcontrol-origin:margin;left:12px;padding:0 8px;background:{BG_PANEL};}}
QLineEdit,QDoubleSpinBox,QSpinBox,QComboBox{{
  background:{BG_INPUT};border:1px solid {BORDER};border-radius:4px;
    padding:6px 10px;color:{TXT};font-size:13px;min-height:32px;
    selection-background-color:{C1};selection-color:{BG_DEEP};}}
QLineEdit:focus,QDoubleSpinBox:focus,QSpinBox:focus,QComboBox:focus{{
  border:1px solid {C1};background:{BG_CARD};}}
QComboBox{{padding-right:30px;}}
QComboBox QAbstractItemView{{background:{BG_CARD};border:1px solid {BORDER};
  selection-background-color:{C1};color:{TXT};}}
QComboBox::drop-down{{border:none;width:22px;}}
QPushButton{{background:{C1};color:{BG_DEEP};border-radius:5px;padding:8px 20px;
    font-weight:bold;font-size:12px;border:1px solid transparent;min-height:34px;}}
QPushButton:hover{{background:#79b8ff;}}
QPushButton:pressed{{background:#388bfd;}}
QPushButton:disabled{{background:{BORDER};color:{TXTS};}}
QPushButton#danger{{background:{C3};color:{BG_DEEP};}}
QPushButton#danger:hover{{background:#ff7b72;}}
QPushButton#success{{background:{C2};color:{BG_DEEP};font-size:13px;font-weight:bold;}}
QPushButton#success:hover{{background:#56d364;}}
QPushButton#success:disabled{{background:{BORDER};color:{TXTS};}}
QPushButton#flat{{background:{BG_CARD};color:{TXTS};border:1px solid {BORDER};}}
QPushButton#flat:hover{{color:{TXT};border-color:{TXTS};}}
QPushButton#flat:disabled{{background:{BG_DEEP};color:{BORDER};border-color:{BORDER};}}
QPushButton#amber{{background:{C4};color:{BG_DEEP};font-weight:bold;}}
QPushButton#amber:hover{{background:#e5c07b;}}
QPushButton#warn{{background:{C4};color:{BG_DEEP};font-weight:bold;font-size:12px;}}
QTableWidget{{background:{BG_INPUT};gridline-color:{BORDER};
  border:1px solid {BORDER};border-radius:4px;color:{TXT};}}
QHeaderView::section{{background:{BG_CARD};color:{C1};padding:7px;
  border:none;border-right:1px solid {BORDER};border-bottom:1px solid {BORDER};
  font-weight:bold;font-size:11px;}}
QTableWidget::item:selected{{background:{C1};color:{BG_DEEP};}}
QTextEdit{{background:{BG_INPUT};color:#b5cfe9;border:1px solid {BORDER};
  border-radius:4px;font-family:'Cascadia Code','Fira Code','Consolas',monospace;font-size:12px;}}
QScrollBar:vertical{{background:{BG_INPUT};width:8px;border-radius:4px;}}
QScrollBar::handle:vertical{{background:{BORDER};border-radius:4px;min-height:20px;}}
QScrollBar::handle:vertical:hover{{background:{TXTS};}}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}
QScrollBar:horizontal{{height:0px;}}
QLabel#heading{{color:{C1};font-size:18px;font-weight:bold;letter-spacing:1px;}}
QLabel#sub{{color:{TXTS};font-size:12px;line-height:1.35;}}
QLabel#param{{color:{C4};font-size:12px;font-weight:bold;}}
QToolTip{{background:{BG_CARD};color:{TXT};border:1px solid {C1};padding:6px;
  border-radius:4px;font-size:12px;}}
QCheckBox{{color:{TXT};spacing:8px;font-size:13px;}}
QCheckBox::indicator{{width:15px;height:15px;border:1px solid {BORDER};
  border-radius:3px;background:{BG_INPUT};}}
QCheckBox::indicator:checked{{background:{C1};border-color:{C1};}}
QFormLayout QLabel{{color:{TXT};font-size:13px;}}
"""

APP_CONFIG_FILE = Path(__file__).with_name("panel_gui_config.json")
PROJECT_FILE_VERSION = "1.0"


# helper functions — small utilities reused across tabs

def win_to_wsl(p):
    p = Path(p); drv = p.drive.rstrip(":").lower()
    rest = p.as_posix().split(":/", 1)[-1]
    return f"/mnt/{drv}/{rest}"

def mkd(path): Path(path).mkdir(parents=True, exist_ok=True)

def dsb(val, lo, hi, dec=4, step=0.001, w=155, tip=""):
    sb = QDoubleSpinBox()
    sb.setRange(lo, hi); sb.setDecimals(dec)
    sb.setSingleStep(step); sb.setValue(val)
    sb.setMinimumWidth(w); sb.setMinimumHeight(34)
    if tip: sb.setToolTip(tip)
    return sb

def isb(val, lo, hi, w=120, tip=""):
    sb = QSpinBox(); sb.setRange(lo, hi); sb.setValue(val)
    sb.setMinimumWidth(w); sb.setMinimumHeight(34)
    if tip: sb.setToolTip(tip)
    return sb

def mk_lbl(txt, kind=""):
    lb = QLabel(txt)
    if kind: lb.setObjectName(kind)
    return lb

def sep():
    f = QFrame(); f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"color:{BORDER};background:{BORDER};max-height:1px;")
    return f


class SpinboxWheelEventFilter(QObject):
    """Prevent mouse wheel from changing numeric inputs while scrolling panes."""
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and isinstance(obj, QAbstractSpinBox):
            event.ignore()
            return True
        return super().eventFilter(obj, event)

def snap_crack_y(y, H, ny, allow_edge=True):
    """
    Keep this part of the workflow stable and explicit for future debugging.
    """
    H = max(float(H), 1e-9)
    ny = max(int(ny), 1)
    dy = H / ny
    edge_tol = 0.45 * dy if allow_edge else 0.0
    if allow_edge and y <= edge_tol:
        return 0.0
    if allow_edge and y >= H - edge_tol:
        return H
    j = min(range(ny + 1), key=lambda idx: abs(idx * dy - y))
    return round(j * dy, 8)

def deg_to_axes(theta_deg):
    th = math.radians(float(theta_deg))
    tx, ty = math.cos(th), math.sin(th)
    nx, ny = -ty, tx
    return tx, ty, nx, ny

def point_to_segment_distance(px, py, ax, ay, bx, by):
    """
    Keep this part of the workflow stable and explicit for future debugging.
    """
    vx = bx - ax
    vy = by - ay
    seg2 = vx * vx + vy * vy
    if seg2 <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * vx + (py - ay) * vy) / seg2
    t = max(0.0, min(1.0, t))
    qx = ax + t * vx
    qy = ay + t * vy
    return math.hypot(px - qx, py - qy)

def point_to_polyline_distance(px, py, pts):
    if not pts:
        return float("inf")
    if len(pts) == 1:
        return math.hypot(px - pts[0][0], py - pts[0][1])
    return min(
        point_to_segment_distance(px, py, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
        for i in range(len(pts) - 1)
    )

def stroke_angle_deg(stroke, default_deg=0.0):
    if not stroke or len(stroke) < 2:
        return float(default_deg)
    x0, y0 = stroke[0]
    x1, y1 = stroke[-1]
    if abs(x1 - x0) < 1e-12 and abs(y1 - y0) < 1e-12:
        return float(default_deg)
    return math.degrees(math.atan2(y1 - y0, x1 - x0))

def compute_mesh_divisions(W, H, max_elem_size, max_aspect):
    """
    Build or refresh mesh-related data used by the geometry and analysis flow.
    """
    W = max(float(W), 1e-9)
    H = max(float(H), 1e-9)
    max_elem_size = max(float(max_elem_size), 1e-6)
    max_aspect = max(float(max_aspect), 1.0)
    nx = max(1, math.ceil(W / max_elem_size))
    ny = max(1, math.ceil(H / max_elem_size))
    for _ in range(8):
        dx = W / max(nx, 1)
        dy = H / max(ny, 1)
        ratio_xy = dx / max(dy, 1e-12)
        ratio_yx = dy / max(dx, 1e-12)
        changed = False
        if ratio_xy > max_aspect:
            ny = max(ny, math.ceil(ny * ratio_xy / max_aspect))
            changed = True
        if ratio_yx > max_aspect:
            nx = max(nx, math.ceil(nx * ratio_yx / max_aspect))
            changed = True
        if not changed:
            break
    return nx, ny

def mesh_preview_text(W, H, nx, ny):
    dx = float(W) / max(int(nx), 1)
    dy = float(H) / max(int(ny), 1)
    aspect = max(dx / max(dy, 1e-12), dy / max(dx, 1e-12))
    return (f"Preview: {int(nx)} x {int(ny)} cells  =  {2 * int(nx) * int(ny)} triangles"
            f"   |   dx={dx:.3f} m, dy={dy:.3f} m, aspect={aspect:.2f}")

def snap_crack_specs(crack_specs, H, enable_edge_snap=True, edge_snap_threshold=0.15):
    """
    Keep this part of the workflow stable and explicit for future debugging.
    """
    H = max(float(H), 1e-9)
    snapped = []
    messages = []
    for spec in crack_specs or []:
        item = dict(spec)
        y_in = float(item.get("y", 0.0))
        y_out = min(max(y_in, 0.0), H)
        snapped_edge = False
        if enable_edge_snap:
            frac = y_out / H
            if frac < float(edge_snap_threshold):
                y_out = 0.0
                snapped_edge = True
            elif frac > (1.0 - float(edge_snap_threshold)):
                y_out = H
                snapped_edge = True
        item["y"] = round(y_out, 8)
        item["snapped_to_edge"] = snapped_edge
        if snapped_edge:
            edge_name = "bottom" if y_out <= 0.0 else "top"
            messages.append(f"Crack at y={y_in:.3f} snapped to {edge_name} edge")
        snapped.append(item)
    return snapped, messages



# mesh generation — panel triangulation and crack pair setup

def generate_panel_mesh(W, H, nx, ny, crack_ys=None, crack_specs=None,
                       enable_edge_snap=True, edge_snap_threshold=0.15):
    """
    Structured triangular mesh for a W×H panel.
    Crack rows duplicate nodes so zeroLength interface elements can be inserted.

    Returns
    -------
    nodes      : {nid: (x, y)}
    tris       : [(eid, n1, n2, n3)]
    crack_pairs: [(nid_below, nid_above, y, x, tx, ty, nx, ny)]
    crack_rows : set of j-indices that are crack rows
    """
    crack_specs = list(crack_specs or [])
    if not crack_specs:
        crack_specs = [{"y": float(yc), "angle_deg": 0.0} for yc in (crack_ys or [])]
    crack_specs, snap_messages = snap_crack_specs(
        crack_specs, H,
        enable_edge_snap=enable_edge_snap,
        edge_snap_threshold=edge_snap_threshold,
    )

    dx = W / max(nx, 1)
    dy = H / max(ny, 1)
    grid_ys = [j * dy for j in range(ny + 1)]

    crack_rows = set()
    row_specs = {}
    for spec in crack_specs:
        yc = float(spec.get("y", 0.0))
        if yc <= 0.0:
            best_j = 0
        elif yc >= H:
            best_j = ny
        else:
            best_j = min(range(1, ny), key=lambda j: abs(grid_ys[j] - yc))
        crack_rows.add(best_j)
        row_specs.setdefault(best_j, []).append(spec)

    nodes = {}; nid = 1; node_grid = {}

    for j in range(ny + 1):
        for i in range(nx + 1):
            x = round(i * dx, 8); y = round(j * dy, 8)
            if j in crack_rows:
                nodes[nid] = (x, y); node_grid[(i, j, 'below')] = nid; nid += 1
                nodes[nid] = (x, y); node_grid[(i, j, 'above')] = nid; nid += 1
            else:
                nodes[nid] = (x, y); node_grid[(i, j, None)] = nid; nid += 1

    def _gn(i, j, side='above'):
        return node_grid[(i, j, side)] if j in crack_rows else node_grid[(i, j, None)]

    tris = []; eid = 1
    for j in range(ny):
        for i in range(nx):
            bl = _gn(i,   j,   'above'); br = _gn(i+1, j,   'above')
            tl = _gn(i,   j+1, 'below'); tr = _gn(i+1, j+1, 'below')
            tris.append((eid, bl, br, tr)); eid += 1
            tris.append((eid, bl, tr, tl)); eid += 1

    crack_pairs = []
    for j in sorted(crack_rows):
        y = round(j * dy, 8)
        specs_here = row_specs.get(j, [{"angle_deg": 0.0}])
        spec = min(specs_here, key=lambda it: abs(float(it.get("y", y)) - y))
        tx, ty, cnx, cny = deg_to_axes(float(spec.get("angle_deg", 0.0)))
        for i in range(nx + 1):
            x = round(i * dx, 8)
            crack_pairs.append((
                node_grid[(i, j, 'below')], node_grid[(i, j, 'above')],
                y, x, tx, ty, cnx, cny,
            ))

    return nodes, tris, crack_pairs, crack_rows, snap_messages, crack_specs



# canvas widget — mesh drawing and interactive picking

class PanelMeshCanvas(QWidget):
    """
    2D triangulated mesh with interactive node selection.

    Modes
    -----
    MODE_SELECT : click a node to select it (for BC / load assignment)
    MODE_CRACK  : click at any Y to add / remove a pending crack line
    """
    node_clicked         = pyqtSignal(int)
    box_selection_changed = pyqtSignal(list)
    crack_y_added        = pyqtSignal(float)
    crack_y_removed      = pyqtSignal(float)
    hand_strokes_changed = pyqtSignal()
    hand_stroke_erased   = pyqtSignal(int)

    MODE_SELECT = "select"
    MODE_CRACK  = "crack"
    MODE_DRAW   = "draw"
    MODE_BOX    = "box"

    def __init__(self):
        """
        Set up widget state, defaults, and signal wiring for this section.
        """
        super().__init__()
        self.setMinimumSize(300, 400)
        self.nodes        = {}       # {nid: (x, y)}
        self.tris         = []       # [(eid, n1, n2, n3)]
        self.crack_pairs  = []       # [(nb, na, y, x, tx, ty, cnx, cny)]
        self.crack_rows   = set()
        self.panel_W      = 1.0
        self.panel_H      = 2.0
        self.bc_nodes     = {}       # {nid: (fix_x, fix_y)}
        self.load_nodes   = {}       # {nid: (Fx, Fy)}
        self.selected_node = None
        self.show_ids     = True
        self.show_elem_ids = False
        self.mode         = self.MODE_SELECT
        self._hover_model = None
        self._pending_crack_ys = []
        self._below_nodes = set()    # nids on the BELOW side of cracks (orange)
        self._above_nodes = set()    # nids on the ABOVE side of cracks (violet)
        self.show_crack_links = True # draw short lines between each (below,above) pair
        self.show_bcs   = True
        self.show_loads = True
        self.hand_strokes = []       # list of completed strokes; each is [(x,y), ...] model coords
        self._cur_stroke  = []       # stroke currently being drawn
        self._drawing     = False    # True while LMB is held in MODE_DRAW
        self._box_start = None   # (px, py) pixel coords where drag started
        self._box_end   = None   # (px, py) current drag end
        self._box_selected = set()  # nids selected by the box
        self._bg_image    = QImage()
        self._bg_path     = ""
        self._highlighted_pairs = set()
        self.setMouseTracking(True)

    # coordinate transforms between model space and canvas pixels
    def _margins(self): return 52, 24, 30, 44

    def _scale(self):
        ml, mt, mr, mb = self._margins()
        dw = self.width() - ml - mr; dh = self.height() - mt - mb
        sx = dw / max(self.panel_W, 1e-6); sy = dh / max(self.panel_H, 1e-6)
        return min(sx, sy)

    def _to_px(self, mx, my):
        ml, mt, mr, mb = self._margins()
        dw = self.width() - ml - mr; dh = self.height() - mt - mb
        sc = self._scale()
        ox = ml + (dw - sc * self.panel_W) / 2; oy = mt + (dh - sc * self.panel_H) / 2
        return int(ox + mx * sc), int(oy + (self.panel_H - my) * sc)

    def _to_model(self, px, py):
        ml, mt, mr, mb = self._margins()
        dw = self.width() - ml - mr; dh = self.height() - mt - mb
        sc = self._scale()
        ox = ml + (dw - sc * self.panel_W) / 2; oy = mt + (dh - sc * self.panel_H) / 2
        return (px - ox) / sc, self.panel_H - (py - oy) / sc

    def _node_near(self, px, py, r=9):
        best, bd = None, r * r
        for nid, (nx_, ny_) in self.nodes.items():
            ppx, ppy = self._to_px(nx_, ny_)
            d = (ppx - px)**2 + (ppy - py)**2
            if d < bd: bd = d; best = nid
        return best

    # public canvas API used by tabs
    def set_mesh(self, nodes, tris, crack_pairs, crack_rows, W, H):
        self.nodes = nodes; self.tris = tris
        self.crack_pairs = crack_pairs; self.crack_rows = crack_rows
        self.panel_W = W; self.panel_H = H
        self.selected_node = None
        # Build below/above sets for color-coded crack node display
        self._below_nodes = {cp[0] for cp in crack_pairs}
        self._above_nodes = {cp[1] for cp in crack_pairs}
        self.update()

    def clear_mesh(self):
        self.nodes = {}; self.tris = []; self.crack_pairs = []
        self.crack_rows = set(); self.selected_node = None
        self._below_nodes = set(); self._above_nodes = set()
        self.update()

    def set_pending_cracks(self, crack_ys, W, H):
        self._pending_crack_ys = list(crack_ys)
        self.panel_W = max(W, 0.01); self.panel_H = max(H, 0.01)
        self.update()

    def set_bc_nodes(self, d):   self.bc_nodes = dict(d); self.update()
    def set_load_nodes(self, d): self.load_nodes = dict(d); self.update()

    def set_mode(self, mode):
        self.mode = mode
        if mode == self.MODE_DRAW:
            self.setCursor(Qt.CrossCursor)
        elif mode == self.MODE_CRACK:
            self.setCursor(Qt.UpArrowCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        self.update()

    def set_background_image(self, image_path):
        image = QImage(image_path or "")
        if image.isNull():
            self._bg_image = QImage()
            self._bg_path = ""
        else:
            self._bg_image = image
            self._bg_path = str(image_path)
        self.update()

    def clear_background_image(self):
        self._bg_image = QImage()
        self._bg_path = ""
        self.update()

    def set_highlighted_crack_pairs(self, pair_keys):
        self._highlighted_pairs = set(pair_keys or [])
        self.update()

    def background_image_path(self):
        return self._bg_path

    def _erase_nearest_stroke(self, mx, my):
        """
        Keep this part of the workflow stable and explicit for future debugging.
        """
        if not self.hand_strokes:
            return False
        tol = max(self.panel_W, self.panel_H) * 0.03
        best_idx = -1
        best_dist = tol
        for idx, stroke in enumerate(self.hand_strokes):
            dist = point_to_polyline_distance(mx, my, stroke)
            if dist <= best_dist:
                best_dist = dist
                best_idx = idx
        if best_idx >= 0:
            self.hand_strokes.pop(best_idx)
            self.hand_stroke_erased.emit(best_idx)
            self.hand_strokes_changed.emit()
            self.update()
            return True
        return False

    def _draw_background(self, painter):
        """
        Keep this part of the workflow stable and explicit for future debugging.
        """
        if self._bg_image.isNull() or self.panel_W <= 0 or self.panel_H <= 0:
            return
        x0, y0 = self._to_px(0, 0)
        x1, y1 = self._to_px(self.panel_W, self.panel_H)
        left = min(x0, x1)
        top = min(y0, y1)
        width = abs(x1 - x0)
        height = abs(y1 - y0)
        painter.save()
        painter.setOpacity(0.42)
        painter.drawImage(left, top, self._bg_image.scaled(
            width, height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        painter.restore()

    # mouse interaction handlers
    def mousePressEvent(self, event):
        """
        Handle a UI event and keep the related state in sync.
        """
        px, py = event.x(), event.y()
        if self.mode == self.MODE_DRAW and event.button() == Qt.RightButton:
            mx, my = self._to_model(px, py)
            if self._erase_nearest_stroke(mx, my):
                return
        if event.button() != Qt.LeftButton:
            return
        if self.mode == self.MODE_SELECT:
            nid = self._node_near(px, py)
            if nid is not None:
                self.selected_node = nid; self.node_clicked.emit(nid); self.update()
        elif self.mode == self.MODE_CRACK:
            _, my = self._to_model(px, py)
            my = max(0.005 * self.panel_H, min(0.995 * self.panel_H, my))
            for yc in list(self._pending_crack_ys):
                if abs(yc - my) < 0.04 * self.panel_H:
                    self.crack_y_removed.emit(yc); return
            self.crack_y_added.emit(my)
        elif self.mode == self.MODE_DRAW:
            self._drawing = True
            mx, my = self._to_model(px, py)
            self._cur_stroke = [(mx, my)]
            self.update()
        elif self.mode == self.MODE_BOX:
            self._box_start = (px, py); self._box_end = (px, py); self.update()

    def mouseMoveEvent(self, event):
        self._hover_model = self._to_model(event.x(), event.y())
        if self.mode == self.MODE_BOX and self._box_start:
            self._box_end = (event.x(), event.y()); self.update()
        if self.mode == self.MODE_DRAW and self._drawing:
            mx, my = self._hover_model
            if (not self._cur_stroke or
                    math.hypot(mx - self._cur_stroke[-1][0],
                               my - self._cur_stroke[-1][1]) > 1e-3):
                self._cur_stroke.append((mx, my))
        self.update()

    def mouseReleaseEvent(self, event):
        if self.mode == self.MODE_BOX and self._box_start and event.button() == Qt.LeftButton:
            x0 = min(self._box_start[0], self._box_end[0])
            x1 = max(self._box_start[0], self._box_end[0])
            y0 = min(self._box_start[1], self._box_end[1])
            y1 = max(self._box_start[1], self._box_end[1])
            selected = [nid for nid, (nx_, ny_) in self.nodes.items()
                        if x0 <= self._to_px(nx_, ny_)[0] <= x1
                        and y0 <= self._to_px(nx_, ny_)[1] <= y1]
            self._box_selected = set(selected)
            self.box_selection_changed.emit(selected)
            self._box_start = None; self._box_end = None; self.update()
        if (self.mode == self.MODE_DRAW and event.button() == Qt.LeftButton
                and self._drawing):
            self._drawing = False
            if len(self._cur_stroke) >= 2:
                self.hand_strokes.append(list(self._cur_stroke))
                self.hand_strokes_changed.emit()
            self._cur_stroke = []
            self.update()

    def leaveEvent(self, event):
        self._hover_model = None; self.update()

    # painting pipeline for mesh, crack links, and overlays
    def paintEvent(self, event):
        """
        Handle a UI event and keep the related state in sync.
        """
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        p.fillRect(0, 0, W, H, QColor(BG_PANEL))
        self._draw_background(p)

        if not self.nodes:
            self._paint_empty(p, W, H); p.end(); return

        # Triangles
        p.setPen(QPen(QColor(BORDER), 0.7)); p.setBrush(Qt.NoBrush)
        for _, n1, n2, n3 in self.tris:
            coords = [self._to_px(*self.nodes[n]) for n in (n1, n2, n3)]
            path = QPainterPath()
            path.moveTo(*coords[0]); path.lineTo(*coords[1])
            path.lineTo(*coords[2]); path.closeSubpath()
            p.drawPath(path)

        if self.show_elem_ids and len(self.tris) <= 400:
            p.setFont(QFont("Consolas", 6))
            p.setPen(QPen(QColor(C4), 1))
            for eid, n1, n2, n3 in self.tris:
                if n1 in self.nodes and n2 in self.nodes and n3 in self.nodes:
                    cx = (self.nodes[n1][0] + self.nodes[n2][0] + self.nodes[n3][0]) / 3
                    cy = (self.nodes[n1][1] + self.nodes[n2][1] + self.nodes[n3][1]) / 3
                    ppx, ppy = self._to_px(cx, cy)
                    p.drawText(ppx - 4, ppy + 3, str(eid))

        # Crack lines (red thick) + edge-snap indicator
        if self.crack_pairs:
            by_y = {}
            for cp in self.crack_pairs:
                by_y.setdefault(round(cp[2], 6), []).append(cp[3])
            p.setPen(QPen(QColor(C3), 3))
            for y, xs in sorted(by_y.items()):
                xs_s = sorted(xs)
                if len(xs_s) >= 2:
                    xL_px, yp = self._to_px(xs_s[0], y)
                    xR_px, _ = self._to_px(xs_s[-1], y)
                    p.drawLine(xL_px, yp, xR_px, yp)
                    # Edge-snapped indicator
                    if (abs(y) < 0.05 * self.panel_H or
                            abs(y - self.panel_H) < 0.05 * self.panel_H):
                        p.setPen(QPen(QColor(C4), 1))
                        p.setFont(QFont("Consolas", 8))
                        p.drawText(xR_px + 4, yp - 4, "EDGE-SNAPPED")
                        p.setPen(QPen(QColor(C3), 3))

        # Crack interface elements: perpendicular tick marks at each crack node
        # (zero-length elements between coincident nodes are invisible as lines)
        if self.show_crack_links and self.crack_pairs:
            tick_len_px = 8
            pen_crack = QPen(QColor("#ff6b35"), 2)
            p.setPen(pen_crack)
            for cp in self.crack_pairs:
                nb, na = cp[0], cp[1]
                if nb in self.nodes and na in self.nodes:
                    xc, yc = cp[3] if len(cp) > 3 else self.nodes[nb][0], cp[2]
                    px_c, py_c = self._to_px(float(xc), float(yc))
                    p.drawLine(px_c, py_c - tick_len_px, px_c, py_c + tick_len_px)
                    p.drawLine(px_c - 3, py_c, px_c + 3, py_c)

        if self._highlighted_pairs:
            p.setPen(QPen(QColor("#ffd54f"), 2.5))
            p.setBrush(QBrush(QColor("#ffd54f")))
            for cp in self.crack_pairs:
                pair_key = (int(cp[0]), int(cp[1]))
                if pair_key not in self._highlighted_pairs:
                    continue
                x = float(cp[3]) if len(cp) > 3 else self.nodes.get(cp[0], (0.0, 0.0))[0]
                y = float(cp[2])
                px, py = self._to_px(x, y)
                p.drawEllipse(px - 5, py - 5, 10, 10)
                p.drawLine(px - 8, py, px + 8, py)

        # Nodes
        # Crack pair nodes share the same coordinates; draw below (orange, larger)
        # first then above (violet, smaller) on top — result is an orange ring with
        # a violet centre, making crack pairs visually distinct at a glance.
        p.setFont(QFont("Consolas", 7))
        show_label = self.show_ids and len(self.nodes) <= 300
        for nid, (nx_, ny_) in self.nodes.items():
            ppx, ppy = self._to_px(nx_, ny_)
            if nid == self.selected_node:
                p.setBrush(QBrush(QColor(C2))); p.setPen(QPen(QColor("#ffffff"), 1.5))
                p.drawEllipse(ppx - 6, ppy - 6, 12, 12)
            elif nid in self.bc_nodes:
                p.setBrush(QBrush(QColor(C4))); p.setPen(QPen(QColor(C4), 1))
                p.drawEllipse(ppx - 4, ppy - 4, 8, 8)
            elif nid in self.load_nodes:
                p.setBrush(QBrush(QColor(C3))); p.setPen(QPen(QColor(C3), 1))
                p.drawEllipse(ppx - 4, ppy - 4, 8, 8)
            elif nid in self._below_nodes:
                # Below-crack node: orange, slightly larger
                p.setBrush(QBrush(QColor(CRACK_BELOW))); p.setPen(QPen(QColor(CRACK_BELOW), 1))
                p.drawEllipse(ppx - 5, ppy - 5, 10, 10)
            elif nid in self._above_nodes:
                # Above-crack node: violet, drawn on top of the orange below-node
                p.setBrush(QBrush(QColor(CRACK_ABOVE))); p.setPen(QPen(QColor(CRACK_ABOVE), 1))
                p.drawEllipse(ppx - 3, ppy - 3, 6, 6)
            else:
                p.setBrush(QBrush(QColor(C1))); p.setPen(QPen(QColor(C1), 0.5))
                p.drawEllipse(ppx - 3, ppy - 3, 6, 6)
            if show_label:
                p.setPen(QPen(QColor(TXTS), 1))
                p.drawText(ppx + 5, ppy - 2, str(nid))

        # Load arrows
        if self.show_loads:
            for nid, (Fx, Fy) in self.load_nodes.items():
                if nid not in self.nodes: continue
                ppx, ppy = self._to_px(*self.nodes[nid])
                if abs(Fy) > 1e-10:
                    s = -1 if Fy > 0 else 1
                    self._arrow(p, ppx, ppy, 0, s * 22, C3)
                if abs(Fx) > 1e-10:
                    s = 1 if Fx > 0 else -1
                    self._arrow(p, ppx, ppy, s * 22, 0, C3)

        # BC supports (triangle hatch at bottom)
        if self.show_bcs:
            for nid, (fx, fy) in self.bc_nodes.items():
                if nid not in self.nodes: continue
                ppx, ppy = self._to_px(*self.nodes[nid])
                p.setPen(QPen(QColor(C4), 1))
                p.setBrush(Qt.NoBrush)
                if fy:
                    path = QPainterPath()
                    path.moveTo(ppx, ppy); path.lineTo(ppx - 6, ppy + 10); path.lineTo(ppx + 6, ppy + 10)
                    path.closeSubpath(); p.drawPath(path)
                if fx:
                    path = QPainterPath()
                    path.moveTo(ppx, ppy); path.lineTo(ppx - 10, ppy - 6); path.lineTo(ppx - 10, ppy + 6)
                    path.closeSubpath(); p.drawPath(path)

        # Crack-mode hover line
        if self.mode == self.MODE_CRACK and self._hover_model:
            _, my = self._hover_model
            if 0 < my < self.panel_H:
                yp = self._to_px(0, my)[1]
                xL = self._to_px(0, 0)[0]; xR = self._to_px(self.panel_W, 0)[0]
                p.setPen(QPen(QColor(C3), 1, Qt.DashLine))
                p.drawLine(xL, yp, xR, yp)
                p.setPen(QPen(QColor(C3), 1))
                p.setFont(QFont("Consolas", 9))
                p.drawText(xR + 4, yp + 4, f"y={my:.3f}")

        # Dimension labels
        p.setPen(QPen(QColor(TXTS), 1)); p.setFont(QFont("Consolas", 8))
        mx, mby = self._to_px(self.panel_W / 2, 0)
        p.drawText(mx - 18, mby + 22, f"W={self.panel_W:.3f}")
        lx, ly = self._to_px(0, self.panel_H / 2)
        p.save(); p.translate(lx - 22, ly); p.rotate(-90)
        p.drawText(-18, 4, f"H={self.panel_H:.3f}"); p.restore()

        # Hand-drawn strokes — completed ones (solid red) + in-progress (dashed)
        pen_stroke = QPen(QColor("#ff4444"), 3); pen_stroke.setCapStyle(Qt.RoundCap)
        pen_cur    = QPen(QColor("#ff8888"), 2, Qt.DashLine)
        for stroke in self.hand_strokes:
            if len(stroke) < 2: continue
            p.setPen(pen_stroke)
            pts = [self._to_px(x, y) for x, y in stroke]
            for i in range(len(pts) - 1):
                p.drawLine(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])
        if len(self._cur_stroke) >= 2:
            p.setPen(pen_cur)
            pts = [self._to_px(x, y) for x, y in self._cur_stroke]
            for i in range(len(pts) - 1):
                p.drawLine(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1])

        if self.mode == self.MODE_BOX and self._box_start and self._box_end:
            p.setPen(QPen(QColor(C1), 1, Qt.DashLine))
            p.setBrush(QBrush(QColor(C1 + "33")))
            rx = min(self._box_start[0], self._box_end[0])
            ry = min(self._box_start[1], self._box_end[1])
            rw = abs(self._box_end[0] - self._box_start[0])
            rh = abs(self._box_end[1] - self._box_start[1])
            p.drawRect(rx, ry, rw, rh)

        # Stats bar
        p.setPen(QPen(QColor(C4), 1)); p.setFont(QFont("Consolas", 8))
        nn = len(self.nodes); nt = len(self.tris); nc = len(self.crack_pairs)
        p.drawText(6, H - 6, f"nodes={nn}  tri={nt}  crack_links={nc}")

        # Legend
        legend = [
            ("●", C1, "Node"), ("●", C2, "Selected"),
            ("●", C4, "Fixed BC"), ("●", C3, "Loaded"),
            ("●", CRACK_BELOW, "Crack ↓"), ("●", CRACK_ABOVE, "Crack ↑"),
            ("╋", "#ff6b35", "Interface Elem"),
        ]
        lx_ = W - 120
        for i, (sym, col, txt) in enumerate(legend):
            p.setPen(QPen(QColor(col), 1))
            p.drawText(lx_, H - 6 - i * 13, f"{sym} {txt}")
        p.end()

    def _paint_empty(self, p, W, H):
        """
        Keep this part of the workflow stable and explicit for future debugging.
        """
        if self.panel_W > 0 and self.panel_H > 0:
            self._draw_background(p)
            x0, y0 = self._to_px(0, 0); x1, y1 = self._to_px(self.panel_W, self.panel_H)
            p.setPen(QPen(QColor(BORDER), 1.5)); p.setBrush(Qt.NoBrush)
            p.drawRect(x0, y1, x1 - x0, y0 - y1)
            p.setPen(QPen(QColor(C3), 2, Qt.DashLine))
            for yc in self._pending_crack_ys:
                yp = self._to_px(0, yc)[1]
                p.drawLine(x0, yp, x1, yp)
        p.setPen(QPen(QColor(TXTS), 1)); p.setFont(QFont("Segoe UI", 10))
        msg = "Set dimensions  →  Generate Mesh"
        fm = QFontMetrics(p.font())
        p.drawText((W - fm.horizontalAdvance(msg)) // 2, H // 2, msg)

    def _arrow(self, p, x, y, dx, dy, color):
        """
        Keep this part of the workflow stable .
        """
        p.setPen(QPen(QColor(color), 2))
        p.drawLine(x, y, x + dx, y + dy)
        ln = math.hypot(dx, dy)
        if ln < 1e-3: return
        ux, uy = dx / ln, dy / ln
        ax = x + dx - ux * 8; ay = y + dy - uy * 8
        path = QPainterPath()
        path.moveTo(x + dx, y + dy)
        path.lineTo(ax - uy * 4, ay + ux * 4)
        path.lineTo(ax + uy * 4, ay - ux * 4)
        path.closeSubpath(); p.fillPath(path, QBrush(QColor(color)))

    # hand-draw stroke helpers
    def get_hand_strokes(self):
        """Return a deep copy of all completed strokes."""
        return [list(s) for s in self.hand_strokes]

    def set_hand_strokes(self, strokes):
        """Replace all strokes (list of lists of (x,y) tuples)."""
        self.hand_strokes = [list(s) for s in strokes]
        self.update()

    def clear_hand_strokes(self):
        self.hand_strokes = []; self._cur_stroke = []; self._drawing = False
        self.hand_strokes_changed.emit(); self.update()

    def undo_hand_stroke(self):
        if self.hand_strokes:
            self.hand_strokes.pop()
            self.hand_strokes_changed.emit(); self.update()



# geometry tab — panel dimensions, cracks, BCs, and mesh controls

class GeometryTab(QWidget):
    mesh_generated = pyqtSignal()

    def __init__(self):
        """
        Set up widget state, defaults, and signal wiring for this section.
        """
        super().__init__()
        root = QHBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # ── left scroll panel ─────────────────────────────────────────────────
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFixedWidth(460)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left = QWidget(); left.setMaximumWidth(438); lv = QVBoxLayout(left)
        lv.setContentsMargins(16, 8, 10, 8); lv.setSpacing(6)
        lv.addWidget(mk_lbl("2D Panel Geometry", "heading"))

        # Panel dimensions
        grp_dim = QGroupBox("Panel Dimensions")
        fd = QFormLayout(grp_dim); fd.setSpacing(6)
        self.sb_W  = dsb(1.0,  0.01, 1e4, 3, 0.1,  tip="Panel width W (m)")
        self.sb_H  = dsb(2.0,  0.01, 1e4, 3, 0.1,  tip="Panel height H (m)")
        self.sb_t  = dsb(0.2,  0.001, 10., 3, 0.01, tip="Panel thickness t (m) — used for plane-stress area scaling")
        fd.addRow("Width W (m):",     self.sb_W)
        fd.addRow("Height H (m):",    self.sb_H)
        fd.addRow("Thickness t (m):", self.sb_t)
        lv.addWidget(grp_dim)

        grp_img = QGroupBox("Background Image")
        vi = QVBoxLayout(grp_img); vi.setSpacing(6)
        vi.addWidget(mk_lbl(
            "Upload a cracked-panel photo and trace over it on the canvas.\n"
            "The image is scaled to the current panel outline.", "sub"))
        img_row = QHBoxLayout()
        self.btn_upload_img = QPushButton("Upload Image")
        self.btn_upload_img.setObjectName("flat")
        self.btn_clear_img = QPushButton("Clear Image")
        self.btn_clear_img.setObjectName("flat")
        img_row.addWidget(self.btn_upload_img)
        img_row.addWidget(self.btn_clear_img)
        img_row.addStretch()
        vi.addLayout(img_row)
        self.lbl_bg_img = mk_lbl("No background image loaded.", "sub")
        vi.addWidget(self.lbl_bg_img)
        lv.addWidget(grp_img)

        # Mesh density
        grp_mesh = QGroupBox("Mesh Density")
        fm = QFormLayout(grp_mesh); fm.setSpacing(6)
        mode_row = QHBoxLayout()
        self.rb_mesh_divisions = QRadioButton("nx / ny mode")
        self.rb_mesh_elem_size = QRadioButton("Element size mode")
        self.rb_mesh_divisions.setChecked(True)
        mode_row.addWidget(self.rb_mesh_divisions)
        mode_row.addWidget(self.rb_mesh_elem_size)
        mode_row.addStretch()
        self.sb_nx = isb(6,  1, 200, tip="Divisions in X")
        self.sb_ny = isb(12, 1, 200, tip="Divisions in Y")
        self.sb_max_elem = dsb(0.2, 1e-3, 1e4, 3, 0.01, tip="Maximum element edge size (m)")
        self.sb_max_aspect = dsb(2.0, 1.0, 25.0, 2, 0.1, tip="Maximum allowable cell aspect ratio")
        mesh_mode_wrap = QWidget(); mesh_mode_wrap.setLayout(mode_row)
        fm.addRow("Control mode:", mesh_mode_wrap)
        fm.addRow("nx (X divisions):", self.sb_nx)
        fm.addRow("ny (Y divisions):", self.sb_ny)
        fm.addRow("Max element size (m):", self.sb_max_elem)
        fm.addRow("Max aspect ratio:", self.sb_max_aspect)
        self.lbl_mesh_preview = mk_lbl("", "sub")
        self.lbl_mesh_preview.setWordWrap(True)
        fm.addRow("Preview:", self.lbl_mesh_preview)
        lv.addWidget(grp_mesh)

        # Generate Mesh + Validate buttons
        btn_row = QHBoxLayout()
        self.btn_gen = QPushButton("Generate Mesh")
        self.btn_gen.setObjectName("amber")
        self.btn_gen.setMinimumHeight(36)
        self.btn_gen.setStyleSheet(
            f"background:{C4};color:{BG_DEEP};font-weight:bold;font-size:13px;"
            f"padding:8px 16px;border-radius:5px;border:none;")
        self.btn_gen.setToolTip("Generate triangular mesh with crack interfaces")

        self.btn_validate = QPushButton("Validate Mesh")
        self.btn_validate.setObjectName("flat")
        self.btn_validate.setMinimumHeight(36)
        self.btn_validate.setToolTip(
            "Check mesh integrity: degenerate triangles, crack pair validity,\n"
            "connectivity on both sides of each crack")

        self.btn_clear_mesh = QPushButton("Clear Mesh")
        self.btn_clear_mesh.setObjectName("danger")
        self.btn_clear_mesh.setMinimumHeight(36)
        self.btn_clear_mesh.setToolTip("Clear the current mesh, BCs, and loads from the canvas")

        btn_row.addWidget(self.btn_gen, stretch=2)
        btn_row.addWidget(self.btn_validate, stretch=1)
        btn_row.addWidget(self.btn_clear_mesh, stretch=1)
        lv.addLayout(btn_row)

        # Mesh info label
        self.lbl_mesh_info = mk_lbl("Mesh not generated.", "sub")
        self.lbl_mesh_info.setWordWrap(True)
        lv.addWidget(self.lbl_mesh_info)

        # Concrete elastic properties
        grp_conc = QGroupBox("Concrete (Plane Stress)")
        fc_ = QFormLayout(grp_conc); fc_.setSpacing(6)
        self.sb_Ec = dsb(30000., 100., 1e7, 0, 500., tip="Elastic modulus Ec (MPa)")
        self.sb_nu = dsb(0.20,   0.0,  0.49, 2, 0.01, tip="Poisson ratio ν")
        fc_.addRow("Ec (MPa):", self.sb_Ec)
        fc_.addRow("ν:",        self.sb_nu)
        lv.addWidget(grp_conc)

        # Crack lines
        grp_crack = QGroupBox("Crack Lines")
        vc = QVBoxLayout(grp_crack); vc.setSpacing(6)
        vc.addWidget(mk_lbl(
            "Type Y positions (m) or click the canvas in Crack mode.\n"
            "Crack lines become zeroLength interface elements.", "sub"))
        row_inp1 = QHBoxLayout()
        self.txt_crack_y = QLineEdit()
        self.txt_crack_y.setPlaceholderText("e.g. 0.5, 1.0, 1.5  (m from base)")
        self.btn_crack_mode = QPushButton("✏ Crack Mode")
        self.btn_crack_mode.setObjectName("flat")
        self.btn_crack_mode.setCheckable(True)
        self.btn_crack_mode.setToolTip("Toggle crack placement mode: click canvas to add/remove crack Y")
        self.btn_box_select = QPushButton("▭ Box Select")
        self.btn_box_select.setObjectName("flat")
        self.btn_box_select.setCheckable(True)
        self.btn_box_select.setToolTip("Drag a box on the canvas to select multiple nodes")
        row_inp1.addWidget(self.txt_crack_y, stretch=1)
        row_inp1.addWidget(self.btn_crack_mode)
        row_inp1.addWidget(self.btn_box_select)
        vc.addLayout(row_inp1)
        row_inp2 = QHBoxLayout()
        row_inp2.addWidget(mk_lbl("θ (deg):"))
        self.sb_crack_angle = dsb(0.0, -180., 180., 1, 1.0, w=80, tip="Default crack orientation angle from horizontal (deg)")
        row_inp2.addWidget(self.sb_crack_angle)
        row_inp2.addStretch()
        vc.addLayout(row_inp2)
        self.lbl_crack_ys = mk_lbl("No crack lines defined.", "sub")
        vc.addWidget(self.lbl_crack_ys)
        snap_row = QHBoxLayout()
        self.chk_edge_snap = QCheckBox("Enable edge snapping")
        self.chk_edge_snap.setChecked(True)
        self.sb_edge_snap_threshold = dsb(0.15, 0.0, 0.49, 2, 0.01, w=90, tip="Fraction of panel height used for edge snapping")
        snap_row.addWidget(self.chk_edge_snap)
        snap_row.addWidget(mk_lbl("Threshold:"))
        snap_row.addWidget(self.sb_edge_snap_threshold)
        snap_row.addStretch()
        vc.addLayout(snap_row)
        self.lbl_edge_snap = mk_lbl("", "sub")
        self.lbl_edge_snap.setStyleSheet(f"color:{C4};font-size:12px;font-weight:bold;")
        self.lbl_edge_snap.setWordWrap(True)
        vc.addWidget(self.lbl_edge_snap)
        # ── Hand-draw sub-section ──────────────────────────────────────────
        vc.addWidget(sep())
        row_hd = QHBoxLayout()
        self.btn_hand_draw   = QPushButton("Draw Crack")
        self.btn_hand_draw.setObjectName("flat")
        self.btn_hand_draw.setCheckable(True)
        self.btn_hand_draw.setToolTip("Toggle draw mode: drag to sketch a crack stroke; right-click a stroke to erase it")
        self.btn_undo_stroke = QPushButton("Undo")
        self.btn_undo_stroke.setObjectName("flat")
        self.btn_undo_stroke.setToolTip("Remove the last drawn stroke")
        self.btn_clr_strokes = QPushButton("Clear")
        self.btn_clr_strokes.setObjectName("flat")
        self.btn_clr_strokes.setToolTip("Remove all hand-drawn strokes")
        row_hd.addWidget(self.btn_hand_draw)
        row_hd.addWidget(self.btn_undo_stroke)
        row_hd.addWidget(self.btn_clr_strokes)
        row_hd.addStretch()
        vc.addLayout(row_hd)
        self.lbl_hand_strokes = mk_lbl("hand strokes: 0", "sub")
        vc.addWidget(self.lbl_hand_strokes)
        vc.addWidget(mk_lbl(
            "Drawn cracks stay visible in red and snap to the nearest mesh row for analysis input.",
            "sub"))
        lv.addWidget(grp_crack)

        # Boundary conditions
        grp_bc = QGroupBox("Boundary Conditions")
        vbc = QVBoxLayout(grp_bc); vbc.setSpacing(6)
        vbc.addWidget(mk_lbl(
            "Click a node on the canvas, then assign its fixity below.\n"
            "Use Quick-assign buttons to fix the full bottom or top edge.", "sub"))

        # Quick-assign buttons
        row_qa_top = QHBoxLayout()
        row_qa_bottom = QHBoxLayout()
        self.btn_fix_bot = QPushButton("Fix Bottom (ux=uy=0)")
        self.btn_fix_bot.setObjectName("flat")
        self.btn_roller_top = QPushButton("Roller Top (ux=0)")
        self.btn_roller_top.setObjectName("flat")
        self.btn_clr_bc = QPushButton("Clear All BC")
        self.btn_clr_bc.setObjectName("danger")
        row_qa_top.addWidget(self.btn_fix_bot)
        row_qa_top.addWidget(self.btn_roller_top)
        row_qa_top.addStretch()
        row_qa_bottom.addWidget(self.btn_clr_bc)
        row_qa_bottom.addStretch()
        vbc.addLayout(row_qa_top)
        vbc.addLayout(row_qa_bottom)

        # Selected node BC assignment
        self.lbl_sel_node = mk_lbl("No node selected.", "sub")
        vbc.addWidget(self.lbl_sel_node)
        node_bc_row_checks = QHBoxLayout()
        node_bc_row_buttons = QHBoxLayout()
        self.chk_fix_x = QCheckBox("Fix X")
        self.chk_fix_y = QCheckBox("Fix Y")
        self.btn_apply_bc = QPushButton("Apply BC")
        self.btn_apply_bc.setEnabled(False)
        self.btn_clear_node_bc = QPushButton("Clear Node BC")
        self.btn_clear_node_bc.setObjectName("flat"); self.btn_clear_node_bc.setEnabled(False)
        node_bc_row_checks.addWidget(self.chk_fix_x)
        node_bc_row_checks.addWidget(self.chk_fix_y)
        node_bc_row_checks.addStretch()
        node_bc_row_buttons.addWidget(self.btn_apply_bc)
        node_bc_row_buttons.addWidget(self.btn_clear_node_bc)
        node_bc_row_buttons.addStretch()
        vbc.addLayout(node_bc_row_checks)
        vbc.addLayout(node_bc_row_buttons)

        # BC table
        self.tbl_bc = QTableWidget(0, 3)
        self.tbl_bc.setHorizontalHeaderLabels(["Node", "Fix X", "Fix Y"])
        self.tbl_bc.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_bc.setMaximumHeight(70)
        vbc.addWidget(self.tbl_bc)
        lv.addWidget(grp_bc)

        # Applied loads
        grp_load = QGroupBox("Applied Loads")
        vld = QVBoxLayout(grp_load); vld.setSpacing(6)
        vld.addWidget(mk_lbl(
            "Select a node, enter Fx/Fy (kN), then Apply Load.\n"
            "Quick-assign applies uniform load to the full top edge.", "sub"))

        row_load_btns = QHBoxLayout()
        self.btn_top_disp = QPushButton("Uniform Top Load")
        self.btn_top_disp.setObjectName("flat")
        self.btn_clr_loads = QPushButton("Clear All Loads")
        self.btn_clr_loads.setObjectName("danger")
        row_load_btns.addWidget(self.btn_top_disp)
        row_load_btns.addWidget(self.btn_clr_loads)
        vld.addLayout(row_load_btns)

        # Top load quick value
        row_top_load = QHBoxLayout()
        row_top_load.addWidget(mk_lbl("Total Fy (kN):"))
        self.sb_top_fy = dsb(-1000., -1e8, 1e8, 1, 100., w=120, tip="Total Y force at top edge (kN), split equally across top nodes")
        row_top_load.addWidget(self.sb_top_fy)
        row_top_load.addStretch()
        vld.addLayout(row_top_load)

        # Per-node load assignment
        load_row_inputs = QHBoxLayout()
        load_row_buttons = QHBoxLayout()
        load_row_inputs.addWidget(mk_lbl("Fx (kN):"))
        self.sb_node_Fx = dsb(0., -1e9, 1e9, 3, 10., w=90)
        load_row_inputs.addWidget(self.sb_node_Fx)
        load_row_inputs.addWidget(mk_lbl("  Fy (kN):"))
        self.sb_node_Fy = dsb(0., -1e9, 1e9, 3, 10., w=90)
        load_row_inputs.addWidget(self.sb_node_Fy)
        load_row_inputs.addStretch()
        self.btn_apply_load = QPushButton("Apply Load")
        self.btn_apply_load.setEnabled(False)
        self.btn_clear_node_load = QPushButton("Clear")
        self.btn_clear_node_load.setObjectName("flat"); self.btn_clear_node_load.setEnabled(False)
        load_row_buttons.addWidget(self.btn_apply_load)
        load_row_buttons.addWidget(self.btn_clear_node_load)
        load_row_buttons.addStretch()
        vld.addLayout(load_row_inputs)
        vld.addLayout(load_row_buttons)

        self.tbl_loads = QTableWidget(0, 3)
        self.tbl_loads.setHorizontalHeaderLabels(["Node", "Fx (kN)", "Fy (kN)"])
        self.tbl_loads.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_loads.setMaximumHeight(70)
        vld.addWidget(self.tbl_loads)
        lv.addWidget(grp_load)

        # Reinforcement (Crossing Cracks)
        grp_rebar = QGroupBox("Reinforcement (Crossing Cracks)")
        vr = QVBoxLayout(grp_rebar); vr.setSpacing(6)
        fr = QFormLayout(); fr.setSpacing(6)
        self.cmb_rebar_crack_y = QComboBox()
        self.sb_rebar_As = dsb(100.0, 1e-6, 1e9, 3, 10.0,
            tip="Rebar area As (mm^2)")
        self.sb_rebar_Es = dsb(200000.0, 1., 1e9, 0, 1000.,
            tip="Steel elastic modulus Es (MPa)")
        self.sb_rebar_fy = dsb(500.0, 1e-6, 1e9, 1, 10.0,
            tip="Steel yield stress fy (MPa)")
        self.sb_rebar_Lunb = dsb(0.05, 0.0, 10., 4, 0.01,
            tip="Unbonded length L_unb (m)")
        x_row = QHBoxLayout()
        self.sb_rebar_x = dsb(0.0, -1e6, 1e6, 4, 0.01,
            tip="Bar x position along crack (m)")
        self.chk_rebar_uniform = QCheckBox("uniform")
        x_row.addWidget(self.sb_rebar_x)
        x_row.addWidget(self.chk_rebar_uniform)
        x_wrap = QWidget(); x_wrap.setLayout(x_row)
        fr.addRow("Crack Y (m):", self.cmb_rebar_crack_y)
        fr.addRow("As (mm^2):", self.sb_rebar_As)
        fr.addRow("Es (MPa):", self.sb_rebar_Es)
        fr.addRow("fy (MPa):", self.sb_rebar_fy)
        fr.addRow("L_unb (m):", self.sb_rebar_Lunb)
        fr.addRow("X position (m):", x_wrap)
        vr.addLayout(fr)

        rebar_btn_row = QHBoxLayout()
        self.btn_add_rebar = QPushButton("Add Rebar")
        self.btn_add_rebar.setObjectName("flat")
        self.btn_remove_rebar = QPushButton("Remove Selected")
        self.btn_remove_rebar.setObjectName("danger")
        rebar_btn_row.addWidget(self.btn_add_rebar)
        rebar_btn_row.addWidget(self.btn_remove_rebar)
        rebar_btn_row.addStretch()
        vr.addLayout(rebar_btn_row)

        self.tbl_rebar = QTableWidget(0, 6)
        self.tbl_rebar.setHorizontalHeaderLabels([
            "Crack Y", "As (mm^2)", "Es (MPa)", "fy (MPa)", "L_unb (m)", "X (m)"
        ])
        self.tbl_rebar.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_rebar.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_rebar.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tbl_rebar.setMaximumHeight(160)
        vr.addWidget(self.tbl_rebar)
        lv.addWidget(grp_rebar)
        self._rebar_definitions = []
        self.chk_rebar_uniform.toggled.connect(self.sb_rebar_x.setDisabled)
        self.btn_add_rebar.clicked.connect(self._add_rebar_definition)
        self.btn_remove_rebar.clicked.connect(self._remove_selected_rebar_definitions)
        self._crack_ys = []
        self._hand_crack_ys = []
        self._hand_crack_defs = []
        self._rebar_definitions = []
        self._refresh_rebar_crack_y_options()

        lv.addStretch()

        scroll.setWidget(left)
        root.addWidget(scroll)

        #right panel: mesh canvas 
        right = QWidget(); right.setStyleSheet(f"background:{BG_PANEL};")
        rv = QVBoxLayout(right); rv.setContentsMargins(8, 16, 16, 16); rv.setSpacing(6)
        mode_row = QHBoxLayout()
        self.lbl_canvas_hint = mk_lbl("Select mode: click a node to assign BC / load", "sub")
        self.lbl_canvas_mode = mk_lbl("Mode: Select", "sub")
        self.lbl_canvas_mode.setStyleSheet(f"color:{C4};font-weight:bold;")
        self.chk_show_ids = QCheckBox("Node IDs")
        self.chk_show_ids.setChecked(True)
        self.chk_show_elem_ids = QCheckBox("Elem IDs")
        self.chk_show_elem_ids.setChecked(False)
        self.chk_show_crack_links = QCheckBox("Crack Links")
        self.chk_show_crack_links.setChecked(True)
        self.chk_show_bcs = QCheckBox("BCs")
        self.chk_show_bcs.setChecked(True)
        self.chk_show_loads = QCheckBox("Loads")
        self.chk_show_loads.setChecked(True)
        mode_row.addWidget(self.lbl_canvas_hint, stretch=1)
        mode_row.addWidget(self.lbl_canvas_mode)
        mode_row.addWidget(self.chk_show_ids)
        mode_row.addWidget(self.chk_show_elem_ids)
        mode_row.addWidget(self.chk_show_crack_links)
        mode_row.addWidget(self.chk_show_bcs)
        mode_row.addWidget(self.chk_show_loads)
        rv.addLayout(mode_row)
        self.canvas = PanelMeshCanvas()
        rv.addWidget(self.canvas, stretch=1)
        root.addWidget(right, stretch=1)

        # internal state
        self._mesh_data = None   # {nodes, tris, crack_pairs, crack_rows, W, H, nx, ny, crack_ys}
        self._bc_nodes  = {}     # {nid: (fix_x, fix_y)}
        self._load_nodes = {}    # {nid: (Fx, Fy)}
        self._selected_node = None
        self._crack_ys      = []
        self._hand_strokes  = []   # mirror of canvas.hand_strokes
        self._hand_crack_ys = []   # y_mean derived from each hand stroke
        self._hand_crack_defs = []
        self._bg_image_path = ""
        self._snap_messages = []
        self._syncing_mesh_controls = False
        self._box_selected_nodes = []

        # wire
        self.btn_gen.clicked.connect(self._generate)
        self.btn_validate.clicked.connect(self._validate_mesh)
        self.btn_clear_mesh.clicked.connect(self._clear_mesh)
        self.btn_upload_img.clicked.connect(self._upload_background_image)
        self.btn_clear_img.clicked.connect(self._clear_background_image)
        self.btn_crack_mode.toggled.connect(self._toggle_crack_mode)
        self.btn_box_select.toggled.connect(self._toggle_box_mode)
        self.txt_crack_y.editingFinished.connect(self._sync_crack_ys_from_text)
        self.canvas.node_clicked.connect(self._on_node_clicked)
        self.canvas.box_selection_changed.connect(self._on_box_selection_changed)
        self.canvas.crack_y_added.connect(self._add_crack_y)
        self.canvas.crack_y_removed.connect(self._remove_crack_y)
        self.canvas.hand_strokes_changed.connect(self._on_hand_strokes_changed)
        self.btn_hand_draw.toggled.connect(self._toggle_hand_draw)
        self.btn_undo_stroke.clicked.connect(self.canvas.undo_hand_stroke)
        self.btn_clr_strokes.clicked.connect(self.canvas.clear_hand_strokes)
        self.btn_fix_bot.clicked.connect(self._fix_bottom)
        self.btn_roller_top.clicked.connect(self._roller_top)
        self.btn_clr_bc.clicked.connect(self._clear_all_bc)
        self.btn_apply_bc.clicked.connect(self._apply_bc_to_node)
        self.btn_clear_node_bc.clicked.connect(self._clear_node_bc)
        self.btn_top_disp.clicked.connect(self._apply_top_load)
        self.btn_clr_loads.clicked.connect(self._clear_all_loads)
        self.btn_apply_load.clicked.connect(self._apply_load_to_node)
        self.btn_clear_node_load.clicked.connect(self._clear_node_load)
        self.chk_show_ids.toggled.connect(self._toggle_ids)
        self.chk_show_elem_ids.toggled.connect(self._toggle_elem_ids)
        self.chk_show_crack_links.toggled.connect(self._toggle_crack_links)
        self.chk_show_bcs.toggled.connect(lambda on: setattr(self.canvas, 'show_bcs', on) or self.canvas.update())
        self.chk_show_loads.toggled.connect(lambda on: setattr(self.canvas, 'show_loads', on) or self.canvas.update())
        for sb in [self.sb_W, self.sb_H]:
            sb.valueChanged.connect(self._on_dim_change)
            sb.valueChanged.connect(self._on_mesh_control_changed)
        self.sb_nx.valueChanged.connect(self._on_mesh_divisions_changed)
        self.sb_ny.valueChanged.connect(self._on_mesh_divisions_changed)
        self.sb_max_elem.valueChanged.connect(self._on_mesh_element_mode_changed)
        self.sb_max_aspect.valueChanged.connect(self._on_mesh_element_mode_changed)
        self.rb_mesh_divisions.toggled.connect(self._on_mesh_mode_toggled)
        self.rb_mesh_elem_size.toggled.connect(self._on_mesh_mode_toggled)
        self.chk_edge_snap.toggled.connect(self._on_dim_change)
        self.sb_edge_snap_threshold.valueChanged.connect(self._on_dim_change)
        self._on_dim_change()
        self._sync_mesh_controls_from_divisions()
        self._on_mesh_mode_toggled()
        self._set_canvas_mode(PanelMeshCanvas.MODE_SELECT)

    # ─ handlers for geometry and mesh control changes, crack spec updates, and background image management
    def _on_dim_change(self):
        self.canvas.set_pending_cracks(self._crack_ys, self.sb_W.value(), self.sb_H.value())
        self._update_edge_snap_preview()

    def _current_mesh_mode(self):
        return "elem_size" if self.rb_mesh_elem_size.isChecked() else "divisions"

    def _sync_mesh_controls_from_divisions(self):
        """
        Build or refresh mesh-related data used by the geometry and analysis flow.
        """
        if self._syncing_mesh_controls:
            return
        self._syncing_mesh_controls = True
        try:
            W = self.sb_W.value(); H = self.sb_H.value()
            nx = self.sb_nx.value(); ny = self.sb_ny.value()
            dx = W / max(nx, 1); dy = H / max(ny, 1)
            self.sb_max_elem.setValue(max(dx, dy))
            self.sb_max_aspect.setValue(max(dx / max(dy, 1e-12), dy / max(dx, 1e-12)))
            self.lbl_mesh_preview.setText(mesh_preview_text(W, H, nx, ny))
        finally:
            self._syncing_mesh_controls = False

    def _sync_mesh_controls_from_element_mode(self):
        """
        Build or refresh mesh-related data used by the geometry and analysis flow.
        """
        if self._syncing_mesh_controls:
            return
        self._syncing_mesh_controls = True
        try:
            nx, ny = compute_mesh_divisions(
                self.sb_W.value(), self.sb_H.value(),
                self.sb_max_elem.value(), self.sb_max_aspect.value(),
            )
            self.sb_nx.setValue(nx)
            self.sb_ny.setValue(ny)
            self.lbl_mesh_preview.setText(mesh_preview_text(self.sb_W.value(), self.sb_H.value(), nx, ny))
        finally:
            self._syncing_mesh_controls = False

    def _on_mesh_mode_toggled(self):
        use_elem = self._current_mesh_mode() == "elem_size"
        self.sb_nx.setEnabled(not use_elem)
        self.sb_ny.setEnabled(not use_elem)
        if use_elem:
            self._sync_mesh_controls_from_element_mode()
        else:
            self._sync_mesh_controls_from_divisions()

    def _on_mesh_divisions_changed(self):
        if self._current_mesh_mode() == "divisions":
            self._sync_mesh_controls_from_divisions()
        else:
            self.lbl_mesh_preview.setText(mesh_preview_text(self.sb_W.value(), self.sb_H.value(), self.sb_nx.value(), self.sb_ny.value()))

    def _on_mesh_element_mode_changed(self):
        if self._current_mesh_mode() == "elem_size":
            self._sync_mesh_controls_from_element_mode()
        else:
            self.lbl_mesh_preview.setText(mesh_preview_text(self.sb_W.value(), self.sb_H.value(), self.sb_nx.value(), self.sb_ny.value()))

    def _on_mesh_control_changed(self):
        if self._current_mesh_mode() == "elem_size":
            self._sync_mesh_controls_from_element_mode()
        else:
            self._sync_mesh_controls_from_divisions()

    def _build_crack_specs(self):
        """
        Keep this part of the workflow stable .
        """
        H = max(self.sb_H.value(), 1e-6)
        tol = max(0.01 * H, H / max(self.sb_ny.value(), 1) * 0.25)
        specs = []
        manual_ys = []
        for y in self._crack_ys:
            if any(abs(y - hy) < tol for hy in self._hand_crack_ys):
                continue
            manual_ys.append(y)
        for y in manual_ys:
            specs.append({"y": float(y), "angle_deg": float(self.sb_crack_angle.value()), "source": "manual"})
        specs.extend(dict(item) for item in self._hand_crack_defs)
        specs.sort(key=lambda item: float(item.get("y", 0.0)))
        return specs

    def _update_edge_snap_preview(self):
        specs = self._build_crack_specs()
        _, msgs = snap_crack_specs(
            specs, self.sb_H.value(),
            enable_edge_snap=self.chk_edge_snap.isChecked(),
            edge_snap_threshold=self.sb_edge_snap_threshold.value(),
        )
        self._snap_messages = msgs
        self.lbl_edge_snap.setText("\n".join(msgs) if msgs else "")

    def _sync_background_label(self):
        if self._bg_image_path:
            self.lbl_bg_img.setText(f"Image loaded: {Path(self._bg_image_path).name}")
        else:
            self.lbl_bg_img.setText("No background image loaded.")

    def _upload_background_image(self):
        """
        Read or write project state while keeping backward compatibility in mind.
        """
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Upload Background Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        if not path:
            return
        self.canvas.set_background_image(path)
        self._bg_image_path = self.canvas.background_image_path()
        self._sync_background_label()

    def _clear_background_image(self):
        self.canvas.clear_background_image()
        self._bg_image_path = ""
        self._sync_background_label()

    def _snap_stroke_y(self, stroke):
        if not stroke:
            return None
        y_mean = sum(pt[1] for pt in stroke) / len(stroke)
        return snap_crack_y(
            y_mean, self.sb_H.value(), self.sb_ny.value(),
            allow_edge=self.chk_edge_snap.isChecked(),
        )

    def _toggle_crack_mode(self, on):
        if on:
            self._set_canvas_mode(PanelMeshCanvas.MODE_CRACK)
        elif not self.btn_hand_draw.isChecked() and not self.btn_box_select.isChecked():
            self._set_canvas_mode(PanelMeshCanvas.MODE_SELECT)

    def _toggle_box_mode(self, on):
        if on:
            self._set_canvas_mode(PanelMeshCanvas.MODE_BOX)
        elif not self.btn_hand_draw.isChecked() and not self.btn_crack_mode.isChecked():
            self._set_canvas_mode(PanelMeshCanvas.MODE_SELECT)

    def _add_crack_y(self, y):
        if not any(abs(y - yc) < 0.01 * self.sb_H.value() for yc in self._crack_ys):
            self._crack_ys.append(y); self._crack_ys.sort()
        self._refresh_crack_label()
        self.canvas.set_pending_cracks(self._crack_ys, self.sb_W.value(), self.sb_H.value())
        self._update_crack_text()

    def _remove_crack_y(self, y):
        self._crack_ys = [yc for yc in self._crack_ys if abs(yc - y) > 0.01 * self.sb_H.value()]
        self._refresh_crack_label()
        self.canvas.set_pending_cracks(self._crack_ys, self.sb_W.value(), self.sb_H.value())
        self._update_crack_text()

    def _sync_crack_ys_from_text(self):
        """
        Keep this part of the workflow stable .
        """
        H = max(self.sb_H.value(), 1e-6)
        tol = 0.01 * H
        ys = []
        for s in self.txt_crack_y.text().replace(";", ",").split(","):
            s = s.strip()
            if not s:
                continue
            try:
                y = float(s)
            except ValueError:
                continue
            # Avoid boundary cracks and merge near-duplicate Y values.
            if tol < y < (H - tol):
                ys.append(y)
        ys = sorted(ys)
        dedup = []
        for y in ys:
            if not dedup or abs(y - dedup[-1]) >= tol:
                dedup.append(y)
        self._crack_ys = dedup
        self._refresh_crack_label()
        self.canvas.set_pending_cracks(self._crack_ys, self.sb_W.value(), self.sb_H.value())

    def _update_crack_text(self):
        self.txt_crack_y.blockSignals(True)
        self.txt_crack_y.setText(", ".join(f"{y:.3f}" for y in self._crack_ys))
        self.txt_crack_y.blockSignals(False)

    def _refresh_crack_label(self):
        if self._crack_ys:
            self.lbl_crack_ys.setText(
                f"{len(self._crack_ys)} crack line(s) at Y = " +
                ", ".join(f"{y:.3f}" for y in self._crack_ys) +
                f"   |   default θ = {self.sb_crack_angle.value():.1f}°")
        else:
            self.lbl_crack_ys.setText("No crack lines defined.")
        self._refresh_rebar_crack_y_options()
        self._update_edge_snap_preview()

    def _refresh_rebar_crack_y_options(self):
        ys = sorted(float(y) for y in self._crack_ys)
        current = self.cmb_rebar_crack_y.currentData()
        self.cmb_rebar_crack_y.blockSignals(True)
        self.cmb_rebar_crack_y.clear()
        for y in ys:
            self.cmb_rebar_crack_y.addItem(f"{y:.4f}", y)
        self.cmb_rebar_crack_y.blockSignals(False)
        if current is not None:
            for idx in range(self.cmb_rebar_crack_y.count()):
                if abs(float(self.cmb_rebar_crack_y.itemData(idx)) - float(current)) < 1e-9:
                    self.cmb_rebar_crack_y.setCurrentIndex(idx)
                    break
        self.btn_add_rebar.setEnabled(self.cmb_rebar_crack_y.count() > 0)

    def _refresh_rebar_table(self):
        self.tbl_rebar.setRowCount(len(self._rebar_definitions))
        for r, rb in enumerate(self._rebar_definitions):
            x_val = rb.get("x", None)
            cells = [
                f"{float(rb.get('crack_y', 0.0)):.4f}",
                f"{float(rb.get('As', 0.0)):.3f}",
                f"{float(rb.get('Es', 0.0)):.1f}",
                f"{float(rb.get('fy', 0.0)):.1f}",
                f"{float(rb.get('L_unb', 0.0)):.4f}",
                "uniform" if x_val is None else f"{float(x_val):.4f}",
            ]
            for c, txt in enumerate(cells):
                self.tbl_rebar.setItem(r, c, QTableWidgetItem(txt))

    def _add_rebar_definition(self):
        if self.cmb_rebar_crack_y.count() == 0:
            QMessageBox.warning(self, "No Crack Rows", "Define at least one crack Y before adding rebar.")
            return
        crack_y = float(self.cmb_rebar_crack_y.currentData())
        entry = {
            "crack_y": crack_y,
            "As": float(self.sb_rebar_As.value()),
            "Es": float(self.sb_rebar_Es.value()),
            "fy": float(self.sb_rebar_fy.value()),
            "L_unb": float(self.sb_rebar_Lunb.value()),
            "x": None if self.chk_rebar_uniform.isChecked() else float(self.sb_rebar_x.value()),
        }
        self._rebar_definitions.append(entry)
        self._refresh_rebar_table()

    def _remove_selected_rebar_definitions(self):
        rows = sorted({idx.row() for idx in self.tbl_rebar.selectionModel().selectedRows()}, reverse=True)
        if not rows:
            return
        for row in rows:
            if 0 <= row < len(self._rebar_definitions):
                self._rebar_definitions.pop(row)
        self._refresh_rebar_table()

    # hand-draw handlers
    def _toggle_hand_draw(self, on):
        if on:
            self._set_canvas_mode(PanelMeshCanvas.MODE_DRAW)
        elif not self.btn_crack_mode.isChecked() and not self.btn_box_select.isChecked():
            self._set_canvas_mode(PanelMeshCanvas.MODE_SELECT)

    def _set_canvas_mode(self, mode):
        self.canvas.set_mode(mode)
        self.btn_crack_mode.blockSignals(True)
        self.btn_hand_draw.blockSignals(True)
        self.btn_box_select.blockSignals(True)
        self.btn_crack_mode.setChecked(mode == PanelMeshCanvas.MODE_CRACK)
        self.btn_hand_draw.setChecked(mode == PanelMeshCanvas.MODE_DRAW)
        self.btn_box_select.setChecked(mode == PanelMeshCanvas.MODE_BOX)
        self.btn_crack_mode.blockSignals(False)
        self.btn_hand_draw.blockSignals(False)
        self.btn_box_select.blockSignals(False)
        if mode == PanelMeshCanvas.MODE_DRAW:
            self.lbl_canvas_mode.setText("Mode: ✏ Draw (drag to sketch crack)")
            self.lbl_canvas_hint.setText("Draw mode: drag to trace a crack; click Draw Crack again to return to Select.")
        elif mode == PanelMeshCanvas.MODE_CRACK:
            self.lbl_canvas_mode.setText("Mode: ➕ Crack (click to place/remove)")
            self.lbl_canvas_hint.setText("Crack mode: click canvas to add/remove crack line.")
        elif mode == PanelMeshCanvas.MODE_BOX:
            self.lbl_canvas_mode.setText("Mode: ▭ Box Select (drag to select nodes)")
            self.lbl_canvas_hint.setText("Box mode: drag a rectangle to select multiple nodes for bulk BC/load operations.")
        else:
            self.lbl_canvas_mode.setText("Mode: ↖ Select (click a node)")
            self.lbl_canvas_hint.setText("Select mode: click a node to assign BC / load")

    def _on_box_selection_changed(self, nids):
        self._box_selected_nodes = [int(nid) for nid in nids]
        if self._box_selected_nodes:
            self.lbl_sel_node.setText(f"{len(self._box_selected_nodes)} nodes selected by box.")
            self.btn_apply_bc.setEnabled(True)
            self.btn_apply_load.setEnabled(True)
        else:
            self.lbl_sel_node.setText("No node selected.")

    def _node_map_get(self, dct, nid, default):
        return dct.get(nid, dct.get(str(nid), default))

    def _node_map_pop(self, dct, nid):
        dct.pop(nid, None)
        dct.pop(str(nid), None)

    def _node_map_set(self, dct, nid, value):
        key = int(nid)
        dct[key] = value
        dct.pop(str(key), None)

    def _on_hand_strokes_changed(self):
        """
        Handle a UI event and keep the related state in sync.
        """
        strokes = self.canvas.get_hand_strokes()
        H = max(self.sb_H.value(), 1e-6)
        tol = max(0.01 * H, H / max(self.sb_ny.value(), 1) * 0.25)
        new_ys = []
        new_defs = []
        for stroke in strokes:
            y_snap = self._snap_stroke_y(stroke)
            if y_snap is not None:
                new_ys.append(y_snap)
                new_defs.append({
                    "y": float(y_snap),
                    "angle_deg": float(stroke_angle_deg(stroke, self.sb_crack_angle.value())),
                    "source": "hand",
                })
        for y_old in self._hand_crack_ys:
            if not any(abs(y_old - y_new) < tol for y_new in new_ys):
                self._remove_crack_y(y_old)
        for y_new in new_ys:
            if not any(abs(y_new - yc) < tol for yc in self._crack_ys):
                self._add_crack_y(y_new)
        self._hand_strokes  = strokes
        self._hand_crack_ys = new_ys
        self._hand_crack_defs = new_defs
        if new_ys:
            ys_txt = ", ".join(
                f"{item['y']:.3f}@{item['angle_deg']:.1f}°" for item in new_defs
            )
            self.lbl_hand_strokes.setText(f"hand strokes: {len(strokes)}  |  snapped rows: {ys_txt}")
        else:
            self.lbl_hand_strokes.setText(f"hand strokes: {len(strokes)}")
        self._update_edge_snap_preview()

    def _generate(self):
        # Merge any Y values the user typed but hasn't committed yet
        """
        Build or refresh mesh-related data used by the geometry and analysis flow.
        """
        txt = self.txt_crack_y.text().strip()
        if txt:
            H = max(self.sb_H.value(), 1e-6)
            tol = 0.01 * H
            parsed = []
            for s in txt.replace(";", ",").split(","):
                s = s.strip()
                if s:
                    try:
                        y = float(s)
                    except ValueError:
                        continue
                    if tol < y < (H - tol):
                        parsed.append(y)
            if parsed:
                parsed = sorted(parsed)
                dedup = []
                for y in parsed:
                    if not dedup or abs(y - dedup[-1]) >= tol:
                        dedup.append(y)
                self._crack_ys = dedup
                self._refresh_crack_label()
        # Keep existing _crack_ys if text field is empty (canvas-click values)
        W = self.sb_W.value(); H = self.sb_H.value()
        if self._current_mesh_mode() == "elem_size":
            nx, ny = compute_mesh_divisions(W, H, self.sb_max_elem.value(), self.sb_max_aspect.value())
            self._syncing_mesh_controls = True
            try:
                self.sb_nx.setValue(nx)
                self.sb_ny.setValue(ny)
            finally:
                self._syncing_mesh_controls = False
        else:
            nx = self.sb_nx.value(); ny = self.sb_ny.value()
        crack_specs = self._build_crack_specs()
        # Save old mesh/BC/load state before re-meshing for snapping
        prev_nodes = self._mesh_data.get("nodes", {}) if self._mesh_data else {}
        old_bc = dict(self._bc_nodes); old_ld = dict(self._load_nodes)

        nodes, tris, crack_pairs, crack_rows, snap_messages, snapped_specs = generate_panel_mesh(
            W, H, nx, ny, self._crack_ys,
            crack_specs=crack_specs,
            enable_edge_snap=self.chk_edge_snap.isChecked(),
            edge_snap_threshold=self.sb_edge_snap_threshold.value(),
        )
        self._mesh_data = dict(nodes=nodes, tris=tris, crack_pairs=crack_pairs,
                               crack_rows=crack_rows, W=W, H=H, nx=nx, ny=ny,
                               crack_ys=self._crack_ys,
                               crack_specs=snapped_specs,
                               snap_messages=snap_messages)
        # Preserve BCs and loads by snapping to nearest new node
        self._bc_nodes = {}; self._load_nodes = {}
        if (old_bc or old_ld) and prev_nodes:
            new_nids = sorted(nodes.keys())
            new_coords = [(nodes[n][0], nodes[n][1]) for n in new_nids]
            def _find_nearest(x, y):
                best_d = float('inf'); best_nid = None
                for i, (nx_, ny_) in enumerate(new_coords):
                    d = (nx_ - x)**2 + (ny_ - y)**2
                    if d < best_d:
                        best_d = d; best_nid = new_nids[i]
                return best_nid
            for nid_str, bc_val in old_bc.items():
                nid = int(nid_str)
                if nid in prev_nodes:
                    ox, oy = prev_nodes[nid]
                    new_nid = _find_nearest(ox, oy)
                    if new_nid is not None:
                        self._bc_nodes[int(new_nid)] = bc_val
            for nid_str, ld_val in old_ld.items():
                nid = int(nid_str)
                if nid in prev_nodes:
                    ox, oy = prev_nodes[nid]
                    new_nid = _find_nearest(ox, oy)
                    if new_nid is not None:
                        self._load_nodes[int(new_nid)] = ld_val
        self.canvas.set_mesh(nodes, tris, crack_pairs, crack_rows, W, H)
        self.canvas.set_bc_nodes(self._bc_nodes)
        self.canvas.set_load_nodes(self._load_nodes)
        nn = len(nodes); nt = len(tris); nc = len(crack_pairs)
        self.lbl_mesh_info.setText(
            f"Mesh ready: {nn} nodes, {nt} triangles, {nc} crack links, "
            f"{len(self._crack_ys)} crack line(s).")
        self.lbl_mesh_preview.setText(mesh_preview_text(W, H, nx, ny))
        self.lbl_edge_snap.setText("\n".join(snap_messages) if snap_messages else "")
        # Aspect ratio feedback
        dx = W / max(nx, 1); dy = H / max(ny, 1)
        ar = max(dx / max(dy, 1e-9), dy / max(dx, 1e-9))
        max_ar = self.sb_max_aspect.value()
        if ar > max_ar:
            QMessageBox.warning(self, "Mesh Quality Warning",
                f"Element aspect ratio = {ar:.2f} exceeds the threshold of {max_ar:.1f}.\n\n"
                f"dx = {dx:.4f} m,  dy = {dy:.4f} m\n\n"
                f"Consider adjusting nx or ny to reduce aspect ratio below {max_ar:.1f}.\n"
                f"Poor aspect ratios reduce solver accuracy and convergence.")
        self._update_bc_table(); self._update_load_table()
        self.mesh_generated.emit()

    def _on_node_clicked(self, nid):
        """
        Handle a UI event and keep the related state in sync.
        """
        self._selected_node = nid
        md = self._mesh_data
        if md is None: return
        x, y = md["nodes"][nid]
        self.lbl_sel_node.setText(f"Node #{nid}  (x={x:.4f}, y={y:.4f})")
        bc = self._node_map_get(self._bc_nodes, nid, (0, 0))
        self.chk_fix_x.setChecked(bool(bc[0])); self.chk_fix_y.setChecked(bool(bc[1]))
        ld = self._node_map_get(self._load_nodes, nid, (0., 0.))
        self.sb_node_Fx.setValue(ld[0]); self.sb_node_Fy.setValue(ld[1])
        self.btn_apply_bc.setEnabled(True); self.btn_clear_node_bc.setEnabled(True)
        self.btn_apply_load.setEnabled(True); self.btn_clear_node_load.setEnabled(True)

    def _apply_bc_to_node(self):
        if self._selected_node is None or self._mesh_data is None: return
        nid = self._selected_node
        fx = 1 if self.chk_fix_x.isChecked() else 0
        fy = 1 if self.chk_fix_y.isChecked() else 0
        if fx or fy:
            self._node_map_set(self._bc_nodes, nid, (fx, fy))
        else:
            self._node_map_pop(self._bc_nodes, nid)
        self.canvas.set_bc_nodes(self._bc_nodes); self._update_bc_table()

    def _clear_node_bc(self):
        if self._selected_node is None: return
        self._node_map_pop(self._bc_nodes, self._selected_node)
        self.chk_fix_x.setChecked(False); self.chk_fix_y.setChecked(False)
        self.canvas.set_bc_nodes(self._bc_nodes); self._update_bc_table()

    def _fix_bottom(self):
        if self._mesh_data is None: return
        for nid, (_, y) in self._mesh_data["nodes"].items():
            if abs(y) < 1e-8: self._bc_nodes[nid] = (1, 1)
        self.canvas.set_bc_nodes(self._bc_nodes); self._update_bc_table()

    def _roller_top(self):
        if self._mesh_data is None: return
        H = self._mesh_data["H"]
        for nid, (_, y) in self._mesh_data["nodes"].items():
            if abs(y - H) < 1e-8: self._bc_nodes[nid] = (1, 0)
        self.canvas.set_bc_nodes(self._bc_nodes); self._update_bc_table()

    def _clear_all_bc(self):
        self._bc_nodes.clear()
        self.canvas.set_bc_nodes(self._bc_nodes); self._update_bc_table()

    def _apply_load_to_node(self):
        if self._selected_node is None or self._mesh_data is None: return
        nid = self._selected_node
        Fx = self.sb_node_Fx.value(); Fy = self.sb_node_Fy.value()
        if abs(Fx) > 1e-12 or abs(Fy) > 1e-12:
            self._node_map_set(self._load_nodes, nid, (Fx, Fy))
        else:
            self._node_map_pop(self._load_nodes, nid)
        self.canvas.set_load_nodes(self._load_nodes); self._update_load_table()

    def _clear_node_load(self):
        if self._selected_node is None: return
        self._node_map_pop(self._load_nodes, self._selected_node)
        self.sb_node_Fx.setValue(0.); self.sb_node_Fy.setValue(0.)
        self.canvas.set_load_nodes(self._load_nodes); self._update_load_table()

    def _apply_top_load(self):
        if self._mesh_data is None: return
        H = self._mesh_data["H"]
        top = [nid for nid, (_, y) in self._mesh_data["nodes"].items() if abs(y - H) < 1e-8]
        if not top:
            QMessageBox.warning(self, "No Top Nodes", "Generate mesh first."); return
        total_Fy = self.sb_top_fy.value()
        fper = total_Fy / len(top)
        for nid in top: self._load_nodes[nid] = (0., fper)
        self.canvas.set_load_nodes(self._load_nodes); self._update_load_table()

    def _clear_all_loads(self):
        self._load_nodes.clear()
        self.canvas.set_load_nodes(self._load_nodes); self._update_load_table()

    def _clear_mesh(self):
        ans = QMessageBox.question(self, "Clear Mesh",
            "This will remove the mesh, all BCs, and all loads. Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        self._mesh_data = None
        self._bc_nodes.clear()
        self._load_nodes.clear()
        self.canvas.clear_mesh()
        self.canvas.set_bc_nodes(self._bc_nodes)
        self.canvas.set_load_nodes(self._load_nodes)
        self._update_bc_table()
        self._update_load_table()
        self.lbl_mesh_info.setText("Mesh cleared.")
        self.lbl_mesh_info.setStyleSheet(f"color:{TXTS};")
        self.mesh_generated.emit()

    def _update_bc_table(self):
        items = sorted((int(nid), vals) for nid, vals in self._bc_nodes.items())
        self.tbl_bc.setRowCount(len(items))
        for i, (nid, (fx, fy)) in enumerate(items):
            self.tbl_bc.setItem(i, 0, QTableWidgetItem(str(nid)))
            self.tbl_bc.setItem(i, 1, QTableWidgetItem("✓" if fx else ""))
            self.tbl_bc.setItem(i, 2, QTableWidgetItem("✓" if fy else ""))

    def _update_load_table(self):
        items = sorted((int(nid), vals) for nid, vals in self._load_nodes.items())
        self.tbl_loads.setRowCount(len(items))
        for i, (nid, (Fx, Fy)) in enumerate(items):
            self.tbl_loads.setItem(i, 0, QTableWidgetItem(str(nid)))
            self.tbl_loads.setItem(i, 1, QTableWidgetItem(f"{Fx:.3f}"))
            self.tbl_loads.setItem(i, 2, QTableWidgetItem(f"{Fy:.3f}"))

    def _toggle_ids(self, on):
        self.canvas.show_ids = on; self.canvas.update()

    def _toggle_elem_ids(self, on):
        self.canvas.show_elem_ids = on; self.canvas.update()

    def _toggle_crack_links(self, on):
        self.canvas.show_crack_links = on; self.canvas.update()

    def _validate_mesh(self):
        """Check mesh integrity and report issues to the user."""
        md = self._mesh_data
        if md is None:
            QMessageBox.warning(self, "No Mesh", "Generate a mesh first.")
            return

        errs = []
        warns = []
        nodes = md["nodes"]
        tris = md["tris"]
        crack_pairs = md["crack_pairs"]

        # 1. No degenerate triangles (repeated node IDs)
        for eid, n1, n2, n3 in tris:
            if n1 == n2 or n2 == n3 or n1 == n3:
                errs.append(f"Degenerate triangle elem {eid}: nodes ({n1},{n2},{n3})")

        # 2. All node IDs referenced by triangles exist
        all_tri_nids = set()
        for _, n1, n2, n3 in tris:
            all_tri_nids.update([n1, n2, n3])
        missing = all_tri_nids - set(nodes.keys())
        if missing:
            errs.append(f"Triangles reference {len(missing)} non-existent node(s): "
                        + ", ".join(str(n) for n in sorted(missing)[:10]))

        # 3. Crack pairs: both node IDs exist
        for cp in crack_pairs:
            nb, na = cp[0], cp[1]
            if nb not in nodes:
                errs.append(f"Crack pair below-node {nb} does not exist")
            if na not in nodes:
                errs.append(f"Crack pair above-node {na} does not exist")

        # 4. If cracks defined, check pairs count > 0
        if md.get("crack_ys") and not crack_pairs:
            errs.append("Crack Y positions defined but no crack pairs generated.")

        # 5. Check that below nodes connect to triangles below and above nodes above
        below_nids = {cp[0] for cp in crack_pairs}
        above_nids = {cp[1] for cp in crack_pairs}
        below_in_tris = below_nids & all_tri_nids
        above_in_tris = above_nids & all_tri_nids
        if below_nids and not below_in_tris:
            errs.append("Below-crack nodes are NOT connected to any triangle!")
        elif below_nids:
            pct = 100 * len(below_in_tris) / len(below_nids)
            if pct < 100:
                warns.append(f"{pct:.0f}% of below-crack nodes connected to triangles "
                             f"({len(below_in_tris)}/{len(below_nids)})")
        if above_nids and not above_in_tris:
            errs.append("Above-crack nodes are NOT connected to any triangle!")
        elif above_nids:
            pct = 100 * len(above_in_tris) / len(above_nids)
            if pct < 100:
                warns.append(f"{pct:.0f}% of above-crack nodes connected to triangles "
                             f"({len(above_in_tris)}/{len(above_nids)})")

        # 6. Check crack pairs actually split connectivity
        for cp in crack_pairs:
            nb, na = cp[0], cp[1]
            # Both should be in triangles but in DIFFERENT triangles
            nb_tris = {eid for eid, n1, n2, n3 in tris if nb in (n1, n2, n3)}
            na_tris = {eid for eid, n1, n2, n3 in tris if na in (n1, n2, n3)}
            if nb_tris & na_tris:
                errs.append(f"Crack pair ({nb},{na}) share triangles — mesh not split!")
                break  # one error is enough

        # Build report
        if not errs and not warns:
            msg = (f"Mesh valid.\n"
                   f"  {len(nodes)} nodes, {len(tris)} triangles, "
                   f"{len(crack_pairs)} crack links.\n"
                   f"  {len(below_nids)} below-crack + {len(above_nids)} above-crack nodes.\n"
                   f"  All below/above nodes connected to triangles on their side.")
            self.lbl_mesh_info.setText(msg)
            self.lbl_mesh_info.setStyleSheet(f"color:{C2};")
            QMessageBox.information(self, "Mesh Valid", msg)
        else:
            lines = []
            if errs:
                lines.append("ERRORS:")
                lines.extend(f"  - {e}" for e in errs)
            if warns:
                lines.append("WARNINGS:")
                lines.extend(f"  - {w}" for w in warns)
            full = "\n".join(lines)
            self.lbl_mesh_info.setText(full)
            self.lbl_mesh_info.setStyleSheet(f"color:{C3};")
            QMessageBox.warning(self, "Mesh Issues", full)

    # public interface for project save/load and inter-tab communication
    def validate(self):
        errs = []
        if self._mesh_data is None:
            errs.append("Mesh not generated. Set dimensions and click Generate Mesh.")
        else:
            if not self._bc_nodes:
                errs.append("No boundary conditions assigned (click Fix Bottom or assign manually).")
            if not self._load_nodes:
                errs.append("No loads applied (click Uniform Top Load or assign manually).")
        return errs

    def get_params(self):
        """
        Return a plain data snapshot used by other tabs or project save/load.
        """
        md = self._mesh_data or {}
        p = {
            "panel_W":  self.sb_W.value(),
            "panel_H":  self.sb_H.value(),
            "panel_t":  self.sb_t.value(),
            "panel_Ec": self.sb_Ec.value(),
            "panel_nu": self.sb_nu.value(),
            "mesh_mode": self._current_mesh_mode(),
            "mesh_nx":  self.sb_nx.value(),
            "mesh_ny":  self.sb_ny.value(),
            "max_elem_size": self.sb_max_elem.value(),
            "max_aspect": self.sb_max_aspect.value(),
            "enable_edge_snap": self.chk_edge_snap.isChecked(),
            "edge_snap_threshold": self.sb_edge_snap_threshold.value(),
            "default_crack_angle_deg": self.sb_crack_angle.value(),
            "crack_ys": list(self._crack_ys),
        }
        if md:
            p["mesh_nodes"]       = {str(k): list(v) for k, v in md["nodes"].items()}
            p["mesh_tris"]        = [[e, n1, n2, n3] for e, n1, n2, n3 in md["tris"]]
            p["mesh_crack_pairs"] = [list(cp) for cp in md["crack_pairs"]]
            p["crack_specs"]      = [dict(spec) for spec in md.get("crack_specs", [])]
            p["snap_messages"]    = list(md.get("snap_messages", []))
        p["bc_nodes"]    = {str(k): list(v) for k, v in self._bc_nodes.items()}
        p["load_nodes"]  = {str(k): list(v) for k, v in self._load_nodes.items()}
        p["hand_crack_strokes"] = [[[pt[0], pt[1]] for pt in s]
                                   for s in self._hand_strokes]
        p["hand_crack_ys"]      = list(self._hand_crack_ys)
        p["hand_crack_defs"]    = [dict(item) for item in self._hand_crack_defs]
        p["rebar_definitions"]  = [dict(item) for item in self._rebar_definitions]
        p["background_image"]   = self._bg_image_path
        return p

    def set_project_state(self, state):
        """
        Apply incoming state to the widget and refresh dependent UI pieces.
        """
        self._syncing_mesh_controls = True
        try:
            self.sb_W.setValue(float(state.get("panel_W", 1.0)))
            self.sb_H.setValue(float(state.get("panel_H", 2.0)))
            self.sb_t.setValue(float(state.get("panel_t", 0.2)))
            self.sb_Ec.setValue(float(state.get("panel_Ec", 30000.0)))
            self.sb_nu.setValue(float(state.get("panel_nu", 0.2)))
            self.sb_nx.setValue(int(state.get("mesh_nx", 6)))
            self.sb_ny.setValue(int(state.get("mesh_ny", 12)))
            self.sb_max_elem.setValue(float(state.get("max_elem_size", 0.2)))
            self.sb_max_aspect.setValue(float(state.get("max_aspect", 2.0)))
            self.chk_edge_snap.setChecked(bool(state.get("enable_edge_snap", True)))
            self.sb_edge_snap_threshold.setValue(float(state.get("edge_snap_threshold", 0.15)))
            self.sb_crack_angle.setValue(float(state.get("default_crack_angle_deg", 0.0)))
            mode = state.get("mesh_mode", "divisions")
            self.rb_mesh_elem_size.setChecked(mode == "elem_size")
            self.rb_mesh_divisions.setChecked(mode != "elem_size")
        finally:
            self._syncing_mesh_controls = False
        self._crack_ys = list(float(v) for v in state.get("crack_ys", []))
        self._hand_crack_ys = list(float(v) for v in state.get("hand_crack_ys", []))
        self._hand_crack_defs = [dict(item) for item in state.get("hand_crack_defs", [])]
        self._rebar_definitions = [
            {
                "crack_y": float(item.get("crack_y", 0.0)),
                "As": float(item.get("As", 0.0)),
                "Es": float(item.get("Es", 200000.0)),
                "fy": float(item.get("fy", 500.0)),
                "L_unb": float(item.get("L_unb", 0.05)),
                "x": (None if item.get("x", None) is None else float(item.get("x"))),
            }
            for item in state.get("rebar_definitions", [])
        ]
        self._refresh_rebar_table()
        self._hand_strokes = [list((float(pt[0]), float(pt[1])) for pt in stroke)
                              for stroke in state.get("hand_crack_strokes", [])]
        self.canvas.set_hand_strokes(self._hand_strokes)
        self._bg_image_path = str(state.get("background_image", "") or "")
        if self._bg_image_path and Path(self._bg_image_path).exists():
            self.canvas.set_background_image(self._bg_image_path)
        else:
            self._bg_image_path = ""
            self.canvas.clear_background_image()
        self._sync_background_label()
        self._update_crack_text()
        self._refresh_crack_label()
        self._on_mesh_mode_toggled()
        self._generate()
        self._bc_nodes = {int(k): tuple(v) for k, v in state.get("bc_nodes", {}).items()}
        self._load_nodes = {int(k): tuple(v) for k, v in state.get("load_nodes", {}).items()}
        self.canvas.set_bc_nodes(self._bc_nodes)
        self.canvas.set_load_nodes(self._load_nodes)
        self._update_bc_table()
        self._update_load_table()

    def reset_project_state(self):
        self.set_project_state({})
        self._mesh_data = None
        self._bc_nodes = {}
        self._load_nodes = {}
        self.canvas.set_mesh({}, [], [], set(), self.sb_W.value(), self.sb_H.value())
        self.canvas.set_bc_nodes(self._bc_nodes)
        self.canvas.set_load_nodes(self._load_nodes)
        self.lbl_mesh_info.setText("Mesh not generated.")

    def get_mesh_data(self):
        return self._mesh_data



# crack materials tab — per-interface material assignment

class PreviewWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, mat_vals, amplitude, n_cycles, activate_cmd, is_windows, python_cmd):
        super().__init__()
        self.mat_vals = dict(mat_vals or {})
        self.amplitude = float(amplitude)
        self.n_cycles = int(n_cycles)
        self.activate_cmd = str(activate_cmd or "true")
        self.is_windows = bool(is_windows)
        self.python_cmd = str(python_cmd or "python3")

    def run(self):
        import tempfile

        mat_json = json.dumps(self.mat_vals)
        amp = max(float(self.amplitude), 1e-9)
        ncy = max(int(self.n_cycles), 1)
        script = f"""
import json, math, sys
import openseespy.opensees as ops

try:
    cm = json.loads({repr(mat_json)})
    ops.wipe()
    ops.model('basic', '-ndm', 1, '-ndf', 1)
    ops.node(1, 0.0)
    ops.node(2, 0.0)
    ops.fix(1, 1)

    mat_type = str(cm.get('mat_type', 'Elastic'))
    kt = max(float(cm.get('kt', 5.95)), 1e-6)
    gap = float(cm.get('gap', 0.001))
    eta = float(cm.get('eta', 0.02))
    mt = mat_type.lower().replace(' ', '')
    if ('simplespring' in mt) or ('calvi2015' in mt):
        sp_Ks = float(cm.get('sp_Ks', cm.get('kt', 200.0)))
        ops.uniaxialMaterial('Elastic', 1, sp_Ks)
    elif ('eppgap' in mt) or ('elasticppgap' in mt) or ('macro' in mt):
        ops.uniaxialMaterial('ElasticPPGap', 1, kt, kt * 5.0, gap, eta)
    elif ('bilinear' in mt) or ('custom' in mt):
        ops.uniaxialMaterial('Steel01', 1, kt * max(gap, 1e-9), kt, eta)
    elif ('multisurfcrack2d' in mt) or ('multi' in mt):
        raise RuntimeError('MultiSurfCrack2D preview is not supported in uniaxial tester mode')
    else:
        ops.uniaxialMaterial('Elastic', 1, kt)

    ops.element('zeroLength', 1, 1, 2, '-mat', 1, '-dir', 1)

    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)
    ops.load(2, 1.0)
    ops.constraints('Plain')
    ops.numberer('RCM')
    ops.system('BandGeneral')
    ops.test('NormDispIncr', 1e-8, 100)
    ops.algorithm('KrylovNewton')

    slip = []
    force = []
    steps_half = 10
    targets = []
    for _ in range(max(int({ncy}), 1)):
        targets.extend([float({amp}), -float({amp}), 0.0])

    current = 0.0
    for tgt in targets:
        incr = (float(tgt) - float(current)) / float(steps_half)
        if abs(incr) < 1e-12:
            continue
        ops.integrator('DisplacementControl', 2, 1, incr)
        ops.analysis('Static')
        for _ in range(steps_half):
            ok = ops.analyze(1)
            if ok != 0:
                break
            du = float(ops.nodeDisp(2, 1))
            ef = ops.eleForce(1)
            f = float(ef[0]) if ef else 0.0
            slip.append(du)
            force.append(f)
        current = float(ops.nodeDisp(2, 1))

    print(json.dumps({{"slip": slip, "force": force}}))
except Exception as e:
    print(str(e), file=sys.stderr)
    raise
"""

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix="_preview_worker.py", delete=False, encoding="utf-8") as tf:
                tf.write(script)
                tmp_path = Path(tf.name)

            if self.is_windows:
                wsl_script = win_to_wsl(tmp_path)
                if self.activate_cmd.strip():
                    cmd = ["wsl", "bash", "-lc", f"{self.activate_cmd} && python3 {shlex.quote(wsl_script)}"]
                else:
                    cmd = ["wsl", "bash", "-lc", f"python3 {shlex.quote(wsl_script)}"]
            else:
                if self.activate_cmd.strip():
                    cmd = ["bash", "-lc", f"{self.activate_cmd} && {self.python_cmd} {shlex.quote(str(tmp_path))}"]
                else:
                    cmd = [self.python_cmd, str(tmp_path)]

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or proc.stdout or "Preview runner failed").strip())

            payload = None
            for line in reversed((proc.stdout or "").splitlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    break
                except Exception:
                    continue
            if not isinstance(payload, dict):
                raise RuntimeError("Preview output JSON not found in runner stdout")
            self.finished.emit(payload)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            try:
                if tmp_path is not None and tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass

class CrackMaterialTab(QWidget):
    def __init__(self):
        """
        Set up widget state, defaults, and signal wiring for this section.
        """
        super().__init__()
        self._geo_ref = None
        self._msc2d_defaults = {
            "msc_E": 210.0, "msc_H": 5.95, "msc_M": 0.0, "msc_K": 0.0,
            "msc_Eunl": 210.0, "msc_Hunl": 5.95, "msc_Munl": 0.0, "msc_Kunl": 0.0,
            "msc_fc": 30.0, "msc_ag": 25.0, "msc_fcl": 5.0, "msc_Acr": 1.0,
            "msc_rho_lok": 0.5, "msc_chi_lok": 0.3, "msc_rho_act": 0.5,
            "msc_mu": 0.7, "msc_chi_act": 0.5, "msc_zeta": 0.3,
            "msc_kappa": 1.0, "msc_theta": 0.785, "msc_w": 0.01, "msc_cPath": 0,
        }
        self._msc2d_keys = list(self._msc2d_defaults.keys())

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content.setMinimumWidth(480)
        outer = QVBoxLayout(content)
        outer.setContentsMargins(16, 16, 16, 12)
        outer.setSpacing(10)

        outer.addWidget(mk_lbl("Crack Interface Materials", "heading"))
        outer.addWidget(mk_lbl(
            "Each crack interface element can be edited independently.\n"
            "Select table rows to highlight them on the mesh canvas.", "sub"))

        ctrl = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh from Geometry")
        self.btn_refresh.setObjectName("amber")
        self.btn_apply_sel = QPushButton("Apply to Selected")
        self.btn_apply_sel.setObjectName("flat")
        self.btn_apply_all = QPushButton("Apply Material to All")
        self.btn_apply_all.setObjectName("flat")
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.setObjectName("flat")
        self.btn_reset_default = QPushButton("Reset to Default")
        self.btn_reset_default.setObjectName("flat")
        ctrl.addWidget(self.btn_refresh)
        ctrl.addWidget(self.btn_apply_sel)
        ctrl.addWidget(self.btn_apply_all)
        ctrl.addWidget(self.btn_select_all)
        ctrl.addWidget(self.btn_reset_default)
        ctrl.addStretch()
        outer.addLayout(ctrl)

        _IN = "#1d2f45"
        _BD = "#4d8fcc"
        crack_font = QFont("Segoe UI", 11)
        SP_EXP = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        combo_css = (
            f"QComboBox{{background:{_IN};color:{TXT};border:2px solid {_BD};"
            f"border-radius:4px;padding:4px 8px;min-height:28px;font-size:12px;}}"
            f"QComboBox::drop-down{{width:22px;border:none;}}"
            f"QComboBox QAbstractItemView{{background:#1a2738;color:{TXT};"
            f"border:1px solid {_BD};selection-background-color:#2d5a8e;}}"
        )
        spin_css = (
            f"QDoubleSpinBox,QSpinBox{{background:{_IN};color:{TXT};border:2px solid {_BD};"
            f"border-radius:4px;padding:4px 8px;min-height:28px;font-size:12px;}}"
            f"QDoubleSpinBox::up-button,QDoubleSpinBox::down-button,"
            f"QSpinBox::up-button,QSpinBox::down-button"
            f"{{width:0;height:0;border:none;}}"
        )

        def _make_combo(items, tip=""):
            cb = QComboBox()
            cb.addItems(items)
            if tip: cb.setToolTip(tip)
            cb.setFont(crack_font)
            cb.setStyleSheet(combo_css)
            cb.setSizePolicy(SP_EXP)
            cb.setMinimumWidth(160)
            cb.setMinimumHeight(34)
            return cb

        def _make_dsb(val, lo, hi, dec=4, step=0.001, tip=""):
            """
            Keep this part of the workflow stable and explicit for future debugging.
            """
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi); sb.setDecimals(dec)
            sb.setSingleStep(step); sb.setValue(val)
            if tip: sb.setToolTip(tip)
            sb.setFont(crack_font)
            sb.setButtonSymbols(QAbstractSpinBox.NoButtons)
            sb.setAlignment(Qt.AlignLeft)
            sb.setStyleSheet(spin_css)
            sb.setSizePolicy(SP_EXP)
            sb.setMinimumWidth(160); sb.setMinimumHeight(34)
            return sb

        def _make_isb(val, lo, hi, tip=""):
            """
            Keep this part of the workflow 
            """
            sb = QSpinBox()
            sb.setRange(lo, hi); sb.setValue(int(val))
            if tip: sb.setToolTip(tip)
            sb.setFont(crack_font)
            sb.setButtonSymbols(QAbstractSpinBox.NoButtons)
            sb.setAlignment(Qt.AlignLeft)
            sb.setStyleSheet(spin_css)
            sb.setSizePolicy(SP_EXP)
            sb.setMinimumWidth(160); sb.setMinimumHeight(34)
            return sb

        mat_items = [
            "MultiSurfCrack2D", "EPPGap Macro (4-spring)",
            "Elastic", "ElasticPPGap", "CustomBilinear", "Calvi2015 (EPP-normal / Elastic-shear)",
        ]
        mat_tip = (
            "MultiSurfCrack2D: plasticity-based multi-yield-surface crack model (the reference paper)\n"
            "EPPGap Macro (4-spring): 4 parallel ElasticPPGap shear springs + 1 elastic normal spring\n"
            "Elastic: linear spring (kn/kt)\n"
            "ElasticPPGap: elastic + perfect plastic gap spring\n"
            "CustomBilinear: piecewise linear force-displacement\n"
            "Calvi2015 (EPP-normal / Elastic-shear): bilinear normal+shear spring for Calvi 2015 validation"
        )

        # Template group box
        grp_tmpl = QGroupBox("Template (applied to all cracks)")
        grp_tmpl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        ft = QFormLayout()
        ft.setContentsMargins(12, 12, 12, 12)
        ft.setHorizontalSpacing(16); ft.setVerticalSpacing(8)
        ft.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        ft.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.cmb_mat_tmpl  = _make_combo(mat_items, mat_tip)
        self.sb_width_tmpl = _make_dsb(0.001, 0., 10.,   4, 0.001, "Initial crack width (m)")
        self.sb_ang_tmpl   = _make_dsb(0.0, -180., 180., 1, 1.0,   "Crack orientation (deg)")
        self.sb_kn_tmpl    = _make_dsb(210.0, 1e-6, 1e9, 2, 10.,   "Normal stiffness kn (kN/m)")
        self.sb_kt_tmpl    = _make_dsb(5.95,  1e-6, 1e9, 3, 1.,    "Shear stiffness kt (kN/m)")
        self.sb_gap_tmpl   = _make_dsb(0.001, 0., 10.,   4, 0.001, "Gap before spring engages (m)")
        self.sb_eta_tmpl   = _make_dsb(0.02,  0., 1.,    3, 0.01,  "Hardening ratio eta")
        self.sb_yield_tmpl = _make_dsb(0.001, 0., 10.,   4, 0.001, "Yield displacement (m)")

        ft.addRow("Material type:",     self.cmb_mat_tmpl)
        ft.addRow("Width (m):",         self.sb_width_tmpl)
        ft.addRow("Orientation (deg):", self.sb_ang_tmpl)
        ft.addRow("kn (kN/m):",         self.sb_kn_tmpl)
        ft.addRow("kt (kN/m):",         self.sb_kt_tmpl)
        ft.addRow("gap (m):",           self.sb_gap_tmpl)
        ft.addRow("eta hardening:",     self.sb_eta_tmpl)
        ft.addRow("Yield disp (m):",    self.sb_yield_tmpl)

        auto_row = QHBoxLayout(); auto_row.setSpacing(6)
        self.sb_fc_auto = _make_dsb(30., 1., 200., 1, 1., "f'c (MPa) for auto kn/kt")
        self.sb_w0_auto = _make_dsb(0.1, 0.001, 5., 3, 0.01, "w0 (mm) for auto kn/kt")
        self.sb_fc_auto.setMinimumWidth(80); self.sb_fc_auto.setMaximumWidth(110)
        self.sb_w0_auto.setMinimumWidth(80); self.sb_w0_auto.setMaximumWidth(110)
        self.btn_auto_knkt = QPushButton("Auto kn/kt")
        self.btn_auto_knkt.setObjectName("flat")
        self.btn_auto_knkt.setToolTip("Compute kn/kt from Divakar Eq.31/32")
        self.btn_set_msc2d_defaults = QPushButton("Set MSC2D Defaults")
        self.btn_set_msc2d_defaults.setObjectName("flat")
        self.btn_set_msc2d_defaults.setToolTip(
            "Set template to MultiSurfCrack2D with Table 2 defaults and apply to all crack elements")
        auto_row.addWidget(mk_lbl("f'c:")); auto_row.addWidget(self.sb_fc_auto)
        auto_row.addSpacing(8)
        auto_row.addWidget(mk_lbl("w0 (mm):")); auto_row.addWidget(self.sb_w0_auto)
        auto_row.addSpacing(8)
        auto_row.addWidget(self.btn_auto_knkt)
        auto_row.addWidget(self.btn_set_msc2d_defaults)
        auto_row.addStretch()
        auto_wrap = QWidget(); auto_wrap.setLayout(auto_row)
        ft.addRow("", auto_wrap)
        self._form_tmpl = ft
        self._tmpl_auto_wrap = auto_wrap
        grp_tmpl.setLayout(ft)
        outer.addWidget(grp_tmpl)

        # Selected Element Editor group box
        grp_edit = QGroupBox("Selected Element Editor")
        grp_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        fe = QFormLayout()
        fe.setContentsMargins(12, 12, 12, 12)
        fe.setHorizontalSpacing(16); fe.setVerticalSpacing(8)
        fe.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        fe.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.lbl_selected = mk_lbl("No crack element selected.", "sub")
        self.cmb_mat_sel  = _make_combo(mat_items)
        self.sb_width_sel = _make_dsb(0.001, 0., 10.,   4, 0.001)
        self.sb_ang_sel   = _make_dsb(0.0, -180., 180., 1, 1.0)
        self.sb_kn_sel    = _make_dsb(210.0, 1e-6, 1e9, 2, 10.)
        self.sb_kt_sel    = _make_dsb(5.95,  1e-6, 1e9, 3, 1.)
        self.sb_gap_sel   = _make_dsb(0.001, 0., 10.,   4, 0.001)
        self.sb_eta_sel   = _make_dsb(0.02,  0., 1.,    3, 0.01)
        self.sb_yield_sel = _make_dsb(0.001, 0., 10.,   4, 0.001)
        self.chk_epp_damage_sel = QCheckBox("Enable damage")

        fe.addRow(self.lbl_selected)
        fe.addRow("Material:",          self.cmb_mat_sel)
        fe.addRow("Width (m):",         self.sb_width_sel)
        fe.addRow("Orientation (deg):", self.sb_ang_sel)
        fe.addRow("kn (kN/m):",         self.sb_kn_sel)
        fe.addRow("kt (kN/m):",         self.sb_kt_sel)
        fe.addRow("gap (m):",           self.sb_gap_sel)
        fe.addRow("eta:",               self.sb_eta_sel)
        fe.addRow("Yield disp (m):",    self.sb_yield_sel)
        fe.addRow("",                   self.chk_epp_damage_sel)
        grp_edit.setLayout(fe)
        self._form_edit = fe
        outer.addWidget(grp_edit)

        # EPPGap info label
        self.lbl_eppgap_info = mk_lbl(
            "EPPGap Macro — 4 parallel shear springs + 1 normal spring\n\n"
            "Spring shares of kt:  15%,  20%,  25%,  40%\n"
            "Gap multipliers:      0.35, 0.75, 1.25, 1.80 x gap\n"
            "Yield multipliers:    0.20, 0.45, 0.90, 1.50\n\n"
            "Normal spring: elastic with stiffness kn\n"
            "This matches the crack hysteresis shape described in the paper.",
            "sub"
        )
        self.lbl_eppgap_info.setWordWrap(True)
        self.lbl_eppgap_info.setVisible(False)
        outer.addWidget(self.lbl_eppgap_info)

        # Calvi2015 group (Calvi validation material)
        self.grp_spring = QGroupBox("Calvi2015 (EPP-normal / Elastic-shear)")
        self.grp_spring.setToolTip(
            "Bilinear normal spring (ElasticPPGap — open in tension, rigid in compression) + linear shear spring. "
            "Designed for Calvi 2015 experimental validation. For general use, prefer ElasticPPGap or MultiSurfCrack2D."
        )
        self.grp_spring.setVisible(False)
        fm_sp = QFormLayout(self.grp_spring)
        fm_sp.setContentsMargins(12, 12, 12, 12)
        fm_sp.setHorizontalSpacing(16); fm_sp.setVerticalSpacing(8)
        fm_sp.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        fm_sp.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.sb_sp_Kn = _make_dsb(500000.0, 0.0, 1e12, 0, 1000.0,
            tip="Normal stiffness Kn (kN/m) — resistance to crack opening")
        self.sb_sp_Ks = _make_dsb(200000.0, 0.0, 1e12, 0, 1000.0,
            tip="Shear (tangential) stiffness Ks (kN/m) — resistance to crack slip")
        self.sb_sp_gap = _make_dsb(0.0, -10., 0., 4, 0.001,
            tip="Compression gap (m) — crack closes at this opening. 0 = no gap")
        self.sb_sp_w0 = _make_dsb(0.0, 0.0, 50., 4, 0.01,
            tip="Initial crack width w0 (mm) — pre-existing crack opening")

        fm_sp.addRow("Kn (kN/m):", self.sb_sp_Kn)
        fm_sp.addRow("Ks (kN/m):", self.sb_sp_Ks)
        fm_sp.addRow("Gap (m):", self.sb_sp_gap)
        fm_sp.addRow("w0 (mm):", self.sb_sp_w0)

        lbl_spring_note = mk_lbl(
            "Calvi2015 bilinear spring (kN/m units) — suitable for Calvi 2015 validation.\n"
            "Use MultiSurfCrack2D for full cyclic behavior.", "sub")
        lbl_spring_note.setWordWrap(True)
        fm_sp.addRow(lbl_spring_note)
        self.grp_spring.setLayout(fm_sp)
        outer.addWidget(self.grp_spring)

        # MultiSurfCrack2D parameter editor
        self.grp_msc2d = QGroupBox("MultiSurfCrack2D Parameters")
        self.grp_msc2d.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        fm2 = QFormLayout()
        fm2.setContentsMargins(12, 12, 12, 12)
        fm2.setHorizontalSpacing(16); fm2.setVerticalSpacing(8)
        fm2.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        fm2.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.lbl_msc2d_info = mk_lbl(
            "These parameters are passed directly to "
            "ops.nDMaterial('MultiSurfCrack2D', ...)\n"
            "Defaults from paper", "sub")
        self.lbl_msc2d_info.setWordWrap(True)

        self.sb_msc_E    = _make_dsb(210.0, 0., 1e9, 3, 1.0,  "E: loading normal stiffness (kN/m)")
        self.sb_msc_H    = _make_dsb(5.95, -1e9, 1e9, 3, 0.1, "H: loading coupling stiffness (kN/m)")
        self.sb_msc_M    = _make_dsb(0.0, -1e9, 1e9, 3, 0.1,  "M: loading off-diagonal stiffness (kN/m)")
        self.sb_msc_K    = _make_dsb(0.0,  0., 1e9, 3, 0.1,   "K: loading shear stiffness (kN/m)")
        self.sb_msc_Eunl = _make_dsb(210.0, 0., 1e9, 3, 1.0,  "Eunl: unloading normal stiffness (kN/m)")
        self.sb_msc_Hunl = _make_dsb(5.95, -1e9, 1e9, 3, 0.1, "Hunl: unloading coupling stiffness (kN/m)")
        self.sb_msc_Munl = _make_dsb(0.0, -1e9, 1e9, 3, 0.1,  "Munl: unloading off-diagonal stiffness (kN/m)")
        self.sb_msc_Kunl = _make_dsb(0.0,  0., 1e9, 3, 0.1,   "Kunl: unloading shear stiffness (kN/m)")
        self.sb_msc_fc   = _make_dsb(30.0,  0., 500., 3, 0.5,  "fc: concrete compressive strength (MPa)")
        self.sb_msc_ag   = _make_dsb(25.0,  0., 200., 3, 0.5,  "ag: maximum aggregate size (mm)")
        self.sb_msc_fcl  = _make_dsb(5.0,   0., 200., 3, 0.5,  "fcl: crack closure stress (MPa)")
        self.sb_msc_Acr  = _make_dsb(1.0,   0., 1e6,  5, 0.1,  "Acr: crack area (m^2)")
        self.sb_msc_rho_lok  = _make_dsb(0.5, -100., 100., 5, 0.01, "rho_lok: aggregate interlock dilation")
        self.sb_msc_chi_lok  = _make_dsb(0.3, -100., 100., 5, 0.01, "chi_lok: aggregate interlock cohesion")
        self.sb_msc_rho_act  = _make_dsb(0.5, -100., 100., 5, 0.01, "rho_act: frictional unloading dilation")
        self.sb_msc_mu       = _make_dsb(0.7, -100., 100., 5, 0.01, "mu: friction coefficient")
        self.sb_msc_chi_act  = _make_dsb(0.5, -100., 100., 5, 0.01, "chi_act: unloading cohesion")
        self.sb_msc_zeta     = _make_dsb(0.3, -100., 100., 5, 0.01, "zeta: pinching parameter")
        self.sb_msc_kappa    = _make_dsb(1.0, -100., 100., 5, 0.01, "kappa: roughness parameter")
        self.sb_msc_theta    = _make_dsb(0.785, -20., 20., 6, 0.01, "theta: contact angle (rad)")
        self.sb_msc_w        = _make_dsb(0.01,  0., 1000., 6, 0.001,"w: initial crack width (mm)")
        self.sb_msc_cPath    = _make_isb(0, 0, 1, "cPath: critical path flag (0 or 1)")

        self._msc2d_widgets = {
            "msc_E": self.sb_msc_E, "msc_H": self.sb_msc_H,
            "msc_M": self.sb_msc_M, "msc_K": self.sb_msc_K,
            "msc_Eunl": self.sb_msc_Eunl, "msc_Hunl": self.sb_msc_Hunl,
            "msc_Munl": self.sb_msc_Munl, "msc_Kunl": self.sb_msc_Kunl,
            "msc_fc": self.sb_msc_fc, "msc_ag": self.sb_msc_ag,
            "msc_fcl": self.sb_msc_fcl, "msc_Acr": self.sb_msc_Acr,
            "msc_rho_lok": self.sb_msc_rho_lok, "msc_chi_lok": self.sb_msc_chi_lok,
            "msc_rho_act": self.sb_msc_rho_act, "msc_mu": self.sb_msc_mu,
            "msc_chi_act": self.sb_msc_chi_act, "msc_zeta": self.sb_msc_zeta,
            "msc_kappa": self.sb_msc_kappa, "msc_theta": self.sb_msc_theta,
            "msc_w": self.sb_msc_w, "msc_cPath": self.sb_msc_cPath,
        }

        fm2.addRow(self.lbl_msc2d_info)
        fm2.addRow("E (kN/m):",    self.sb_msc_E)
        fm2.addRow("H (kN/m):",    self.sb_msc_H)
        fm2.addRow("M (kN/m):",    self.sb_msc_M)
        fm2.addRow("K (kN/m):",    self.sb_msc_K)
        fm2.addRow("Eunl (kN/m):", self.sb_msc_Eunl)
        fm2.addRow("Hunl (kN/m):", self.sb_msc_Hunl)
        fm2.addRow("Munl (kN/m):", self.sb_msc_Munl)
        fm2.addRow("Kunl (kN/m):", self.sb_msc_Kunl)
        fm2.addRow("fc (MPa):",    self.sb_msc_fc)
        fm2.addRow("ag (mm):",     self.sb_msc_ag)
        fm2.addRow("fcl (MPa):",   self.sb_msc_fcl)
        fm2.addRow("Acr (m^2):",   self.sb_msc_Acr)
        fm2.addRow("rho_lok:",     self.sb_msc_rho_lok)
        fm2.addRow("chi_lok:",     self.sb_msc_chi_lok)
        fm2.addRow("rho_act:",     self.sb_msc_rho_act)
        fm2.addRow("mu:",          self.sb_msc_mu)
        fm2.addRow("chi_act:",     self.sb_msc_chi_act)
        fm2.addRow("zeta:",        self.sb_msc_zeta)
        fm2.addRow("kappa:",       self.sb_msc_kappa)
        fm2.addRow("theta (rad):", self.sb_msc_theta)
        fm2.addRow("w (mm):",      self.sb_msc_w)
        fm2.addRow("cPath:",       self.sb_msc_cPath)

        msc_btn_row = QHBoxLayout()
        self.btn_reset_msc2d_defaults = QPushButton("Reset to Paper Defaults (Table 2)")
        self.btn_reset_msc2d_defaults.setObjectName("flat")
        self.btn_reset_msc2d_defaults.setToolTip(
            "Reset all MultiSurfCrack2D parameters to paper Table 2 defaults")
        msc_btn_row.addWidget(self.btn_reset_msc2d_defaults)
        msc_btn_row.addStretch()
        msc_btn_wrap = QWidget(); msc_btn_wrap.setLayout(msc_btn_row)
        fm2.addRow("", msc_btn_wrap)
        self.grp_msc2d.setLayout(fm2)
        self.grp_msc2d.setVisible(False)
        outer.addWidget(self.grp_msc2d)

        # Material response preview
        grp_preview = QGroupBox("Material Response Preview")
        hpv = QHBoxLayout(grp_preview)
        left_preview = QWidget()
        fl_prev = QFormLayout(left_preview)
        self.btn_preview = QPushButton("▶ Preview")
        self.btn_preview.setObjectName("flat")
        self.sb_preview_amp = dsb(0.002, 1e-6, 1.0, 4, 0.0005, w=120)
        self.sb_preview_cycles = isb(3, 1, 10, w=120)
        self.lbl_preview_status = mk_lbl("Idle", "sub")
        fl_prev.addRow(self.btn_preview)
        fl_prev.addRow("Amplitude (m):", self.sb_preview_amp)
        fl_prev.addRow("Cycles:", self.sb_preview_cycles)
        fl_prev.addRow("Status:", self.lbl_preview_status)
        hpv.addWidget(left_preview, stretch=0)

        self.preview_fig = Figure(facecolor=BG_DEEP, tight_layout=True)
        self.ax_prev = self.preview_fig.add_subplot(111)
        self.ax_prev.set_facecolor(BG_PANEL)
        self.ax_prev.tick_params(colors=TXTS, labelsize=9)
        self.ax_prev.xaxis.label.set_color(TXT)
        self.ax_prev.yaxis.label.set_color(TXT)
        for s in self.ax_prev.spines.values():
            s.set_edgecolor(BORDER)
        self.ax_prev.grid(True, alpha=0.15, color=BORDER, linestyle="--")
        self.ax_prev.set_title("Force vs Displacement", color=C1)
        self.ax_prev.set_xlabel("Displacement (m)")
        self.ax_prev.set_ylabel("Force (kN)")
        self.preview_canvas = FigureCanvas(self.preview_fig)
        hpv.addWidget(self.preview_canvas, stretch=1)
        outer.addWidget(grp_preview)
        outer.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        # Crack Element Table pinned at bottom
        grp_tbl = QGroupBox("Crack Element Table")
        vt = QVBoxLayout(grp_tbl); vt.setSpacing(6)
        vt.addWidget(mk_lbl(
            "Each row is one interface element between two duplicated crack nodes.\n"
            "Selecting rows highlights those elements on the Geometry canvas in yellow.", "sub"))
        self.tbl = QTableWidget(0, 11)
        self.tbl.setHorizontalHeaderLabels([
            "Elem", "Y pos (m)", "X pos (m)", "Width (m)", "Orient (deg)",
            "Material", "kn (kN/m)", "kt (kN/m)", "gap (m)", "eta", "theta (rad)"
        ])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.ExtendedSelection)
        vt.addWidget(self.tbl, stretch=1)
        root.addWidget(grp_tbl, stretch=1)

        # Wire signals
        self.btn_refresh.clicked.connect(self.refresh_from_geometry)
        self.btn_apply_sel.clicked.connect(self._apply_editor_to_selected)
        self.btn_apply_all.clicked.connect(self._apply_template_to_all)
        self.btn_select_all.clicked.connect(self.tbl.selectAll)
        self.btn_reset_default.clicked.connect(self._reset_default)
        self.btn_auto_knkt.clicked.connect(self._auto_kn_kt)
        self.btn_set_msc2d_defaults.clicked.connect(self._set_msc2d_defaults_template_all)
        self.btn_reset_msc2d_defaults.clicked.connect(self._reset_msc2d_defaults)
        self.btn_preview.clicked.connect(self._run_preview)
        self.cmb_mat_sel.currentTextChanged.connect(self._update_material_type_visibility)
        self.cmb_mat_tmpl.currentTextChanged.connect(self._on_tmpl_mat_changed)
        self.tbl.itemSelectionChanged.connect(self._on_selection_changed)
        self._update_material_type_visibility(self.cmb_mat_sel.currentText())
        self._on_tmpl_mat_changed(self.cmb_mat_tmpl.currentText())

    def _auto_kn_kt(self):
        w = max(self.sb_w0_auto.value(), 0.001)
        fc = max(self.sb_fc_auto.value(), 1e-6)
        kn = (2. + w) / w
        kt = 0.00595 * (25.4 / w)**1.6148 * (fc / 34.5)**0.193
        self.sb_kn_tmpl.setValue(kn)
        self.sb_kt_tmpl.setValue(kt)

    def _is_msc2d_type(self, mat_type):
        return "multisurfcrack2d" in str(mat_type or "").strip().lower()

    def _is_eppgap_macro_type(self, mat_type):
        mt = str(mat_type or "").strip().lower()
        return "eppgap macro" in mt or ("macro" in mt and "eppgap" in mt)

    def _msc2d_values_from_widgets(self):
        vals = {}
        for key, w in self._msc2d_widgets.items():
            vals[key] = int(w.value()) if key == "msc_cPath" else float(w.value())
        return vals

    def _set_msc2d_widgets(self, vals=None):
        vals = dict(vals or {})
        for key, default in self._msc2d_defaults.items():
            value = vals.get(key, default)
            if key == "msc_cPath":
                self._msc2d_widgets[key].setValue(int(value))
            else:
                self._msc2d_widgets[key].setValue(float(value))

    def _reset_msc2d_defaults(self):
        self._set_msc2d_widgets(self._msc2d_defaults)

    def _is_simple_spring_type(self, mat_type):
        mt = str(mat_type or "").strip().lower().replace(" ", "")
        return ("simplespring" in mt) or ("calvi2015" in mt)

    def _update_material_type_visibility(self, mat_type=None):
        mt = mat_type if mat_type is not None else self.cmb_mat_sel.currentText()
        self.grp_msc2d.setVisible(self._is_msc2d_type(mt))
        self.lbl_eppgap_info.setVisible(self._is_eppgap_macro_type(mt))
        self.grp_spring.setVisible(self._is_simple_spring_type(mt))

        mt_l = str(mt or "").strip().lower()
        show_kn_kt_only = mt_l == "elastic"
        show_elasticpp = "elasticppgap" in mt_l
        show_epp_macro = self._is_eppgap_macro_type(mt)

        self._set_form_field_visible(self.sb_width_sel, not (show_kn_kt_only or show_elasticpp or show_epp_macro))
        self._set_form_field_visible(self.sb_ang_sel, not (show_kn_kt_only or show_elasticpp or show_epp_macro))
        self._set_form_field_visible(self.sb_kn_sel, True)
        self._set_form_field_visible(self.sb_kt_sel, True)
        self._set_form_field_visible(self.sb_gap_sel, show_epp_macro or show_elasticpp)
        self._set_form_field_visible(self.sb_eta_sel, show_epp_macro or show_elasticpp)
        self._set_form_field_visible(self.sb_yield_sel, show_elasticpp)
        self._set_form_field_visible(self.chk_epp_damage_sel, show_epp_macro or show_elasticpp)

    def _set_form_field_visible(self, field_widget, visible):
        lbl = self._form_edit.labelForField(field_widget) if hasattr(self, "_form_edit") else None
        if lbl is not None:
            lbl.setVisible(visible)
        field_widget.setVisible(visible)

    def _on_tmpl_mat_changed(self, mat_type=None):
        mt = mat_type if mat_type is not None else self.cmb_mat_tmpl.currentText()
        is_msc2d = self._is_msc2d_type(mt)
        show_basic = not is_msc2d
        mt_l = str(mt or "").strip().lower()
        show_yield = ("elasticppgap" in mt_l) or self._is_simple_spring_type(mt)

        for widget in [self.sb_kn_tmpl, self.sb_kt_tmpl, self.sb_gap_tmpl, self.sb_eta_tmpl]:
            lbl = self._form_tmpl.labelForField(widget) if hasattr(self, "_form_tmpl") else None
            if lbl is not None:
                lbl.setVisible(show_basic)
            widget.setVisible(show_basic)

        lbl_y = self._form_tmpl.labelForField(self.sb_yield_tmpl) if hasattr(self, "_form_tmpl") else None
        if lbl_y is not None:
            lbl_y.setVisible(show_yield)
        self.sb_yield_tmpl.setVisible(show_yield)

        if hasattr(self, "_tmpl_auto_wrap"):
            self._tmpl_auto_wrap.setVisible(show_basic)

    def _run_preview(self):
        vals = self._editor_values()
        amp = float(self.sb_preview_amp.value())
        cycles = int(self.sb_preview_cycles.value())
        activate_cmd = "true"
        python_cmd = "python3"
        is_windows = sys.platform.startswith("win")
        try:
            mw = self.window()
            if hasattr(mw, "run") and callable(getattr(mw.run, "get_activate", None)):
                activate_cmd = mw.run.get_activate()
            if hasattr(mw, "run") and hasattr(mw.run, "python_cmd"):
                python_cmd = str(getattr(mw.run, "python_cmd") or "python3")
        except Exception:
            pass

        self.btn_preview.setEnabled(False)
        self.lbl_preview_status.setStyleSheet(f"color:{TXTS};")
        self.lbl_preview_status.setText("Running preview...")

        self._preview_worker = PreviewWorker(vals, amp, cycles, activate_cmd, is_windows, python_cmd)
        self._preview_worker.finished.connect(self._on_preview_done)
        self._preview_worker.error.connect(self._on_preview_error)
        self._preview_worker.start()

    def _on_preview_done(self, result):
        slip = np.array(result.get("slip", []), dtype=float)
        force = np.array(result.get("force", []), dtype=float)

        self.ax_prev.cla()
        self.ax_prev.set_facecolor(BG_PANEL)
        self.ax_prev.tick_params(colors=TXTS, labelsize=9)
        self.ax_prev.xaxis.label.set_color(TXT)
        self.ax_prev.yaxis.label.set_color(TXT)
        for s in self.ax_prev.spines.values():
            s.set_edgecolor(BORDER)
        self.ax_prev.grid(True, alpha=0.15, color=BORDER, linestyle="--")
        self.ax_prev.plot(slip, force, color=C1, lw=1.8)
        self.ax_prev.set_title("Force vs Displacement", color=C1)
        self.ax_prev.set_xlabel("Displacement (m)")
        self.ax_prev.set_ylabel("Force (kN)")

        self.preview_canvas.draw_idle()
        self.btn_preview.setEnabled(True)
        self.lbl_preview_status.setStyleSheet(f"color:{C2};")
        self.lbl_preview_status.setText("Preview ready")

    def _on_preview_error(self, msg):
        self.btn_preview.setEnabled(True)
        self.lbl_preview_status.setStyleSheet(f"color:{C3};")
        self.lbl_preview_status.setText(str(msg)[:120])

    def _set_msc2d_defaults_template_all(self):
        """
        Keep this part of the workflow stable and explicit for future debugging.
        """
        self.cmb_mat_tmpl.setCurrentText("MultiSurfCrack2D")
        self.cmb_mat_sel.setCurrentText("MultiSurfCrack2D")
        self._set_msc2d_widgets(self._msc2d_defaults)
        if self.tbl.rowCount() > 0:
            self._apply_template_to_all()
        else:
            QMessageBox.information(
                self, "No Crack Elements",
                "Generate a mesh with crack lines first,\n"
                "then click Refresh from Geometry.")

    def _template_values(self):
       
        vals = dict(
            width=self.sb_width_tmpl.value(),
            orientation_deg=self.sb_ang_tmpl.value(),
            mat_type=self.cmb_mat_tmpl.currentText(),
            kn=self.sb_kn_tmpl.value(), kt=self.sb_kt_tmpl.value(),
            gap=self.sb_gap_tmpl.value(), eta=self.sb_eta_tmpl.value(),
            yield_disp=self.sb_yield_tmpl.value(),
            epp_damage=False,
        )
        if self._is_msc2d_type(vals["mat_type"]):
            vals.update(self._msc2d_values_from_widgets())
        if self._is_simple_spring_type(vals["mat_type"]):
            vals.update({"sp_Kn": self.sb_sp_Kn.value(), "sp_Ks": self.sb_sp_Ks.value(),
                         "sp_gap": self.sb_sp_gap.value(), "sp_w0": self.sb_sp_w0.value()})
        return vals

    def _editor_values(self):
       
        vals = dict(
            width=self.sb_width_sel.value(),
            orientation_deg=self.sb_ang_sel.value(),
            mat_type=self.cmb_mat_sel.currentText(),
            kn=self.sb_kn_sel.value(), kt=self.sb_kt_sel.value(),
            gap=self.sb_gap_sel.value(), eta=self.sb_eta_sel.value(),
            yield_disp=self.sb_yield_sel.value(),
            epp_damage=self.chk_epp_damage_sel.isChecked(),
        )
        if "elasticppgap" in vals["mat_type"].lower():
            vals["gap"] = vals["yield_disp"]
        if self._is_msc2d_type(vals["mat_type"]):
            vals.update(self._msc2d_values_from_widgets())
        if self._is_simple_spring_type(vals["mat_type"]):
            vals.update({"sp_Kn": self.sb_sp_Kn.value(), "sp_Ks": self.sb_sp_Ks.value(),
                         "sp_gap": self.sb_sp_gap.value(), "sp_w0": self.sb_sp_w0.value()})
        return vals

    def _selected_rows(self):
        return sorted({idx.row() for idx in self.tbl.selectionModel().selectedRows()})

    def _row_meta(self, row):
        item = self.tbl.item(row, 0)
        return item.data(Qt.UserRole) if item is not None else {}

    def _default_row_values(self, cp, idx):
       
        tx = float(cp[4]) if len(cp) >= 6 else 1.0
        ty = float(cp[5]) if len(cp) >= 6 else 0.0
        ang = math.degrees(math.atan2(ty, tx))
        vals = self._template_values()
        vals["orientation_deg"] = ang
        vals.setdefault("width", vals["gap"])
        vals["element_index"] = idx + 1
        vals["y"] = float(cp[2])
        vals["x"] = float(cp[3]) if len(cp) > 3 else 0.0
        vals["below_node"] = int(cp[0])
        vals["above_node"] = int(cp[1])
        return vals

    def _set_row_values(self, row, vals, meta=None):
        
        meta = dict(meta or self._row_meta(row) or {})
        meta["pair_key"] = (int(vals["below_node"]), int(vals["above_node"]))
        default_snap = {k: vals.get(k, self._msc2d_defaults[k]) for k in self._msc2d_defaults}
        default_snap.update({k: vals[k] for k in ("width","orientation_deg","mat_type","kn","kt","gap","eta")})
        meta["default_values"] = dict(meta.get("default_values") or default_snap)
        msc_vals = {}
        src = dict(meta.get("msc2d", {}))
        for key, default in self._msc2d_defaults.items():
            msc_vals[key] = int(vals.get(key, src.get(key, default))) if key == "msc_cPath" \
                            else float(vals.get(key, src.get(key, default)))
        meta["msc2d"] = msc_vals
        meta["spring"] = {
            "sp_Kn": float(vals.get("sp_Kn", 500000.0)),
            "sp_Ks": float(vals.get("sp_Ks", 200000.0)),
            "sp_gap": float(vals.get("sp_gap", 0.0)),
            "sp_w0": float(vals.get("sp_w0", 0.0)),
        }
        meta["advanced"] = {
            "yield_disp": float(vals.get("yield_disp", vals.get("gap", 0.001))),
            "epp_damage": bool(vals.get("epp_damage", False)),
        }
        theta_rad = float(vals.get("theta_rad", math.radians(vals.get("orientation_deg", 0.0))))
        cells = [
            str(int(vals["element_index"])),
            f"{vals['y']:.4f}", f"{vals['x']:.4f}",
            f"{vals['width']:.4f}", f"{vals['orientation_deg']:.1f}",
            vals["mat_type"],
            f"{vals['kn']:.3f}", f"{vals['kt']:.3f}",
            f"{vals['gap']:.4f}", f"{vals['eta']:.3f}",
            f"{theta_rad:.4f}",
        ]
        for col, text in enumerate(cells):
            item = self.tbl.item(row, col)
            if item is None:
                item = QTableWidgetItem(text)
                self.tbl.setItem(row, col, item)
            else:
                item.setText(text)
            if col == 0:
                item.setData(Qt.UserRole, meta)

    def _set_editor_values(self, vals):
        
        self.cmb_mat_sel.blockSignals(True)
        self.cmb_mat_sel.setCurrentText(vals["mat_type"])
        self.cmb_mat_sel.blockSignals(False)
        self.sb_width_sel.setValue(float(vals["width"]))
        self.sb_ang_sel.setValue(float(vals["orientation_deg"]))
        self.sb_kn_sel.setValue(float(vals["kn"]))
        self.sb_kt_sel.setValue(float(vals["kt"]))
        self.sb_gap_sel.setValue(float(vals["gap"]))
        self.sb_eta_sel.setValue(float(vals["eta"]))
        self.sb_yield_sel.setValue(float(vals.get("yield_disp", vals.get("gap", 0.001))))
        self.chk_epp_damage_sel.setChecked(bool(vals.get("epp_damage", False)))
        self._set_msc2d_widgets(vals)
        self._update_material_type_visibility(vals["mat_type"])

    def _row_values(self, row):
       
        meta = self._row_meta(row)
        pair_key = tuple(meta.get("pair_key", (0, 0)))
        theta_item = self.tbl.item(row, 10)
        theta_rad = float(theta_item.text()) if theta_item and theta_item.text() else 0.0
        vals = dict(
            element_index=int(float(self.tbl.item(row, 0).text())),
            y=float(self.tbl.item(row, 1).text()),
            x=float(self.tbl.item(row, 2).text()),
            width=float(self.tbl.item(row, 3).text()),
            orientation_deg=float(self.tbl.item(row, 4).text()),
            mat_type=self.tbl.item(row, 5).text(),
            kn=float(self.tbl.item(row, 6).text()),
            kt=float(self.tbl.item(row, 7).text()),
            gap=float(self.tbl.item(row, 8).text()),
            eta=float(self.tbl.item(row, 9).text()),
            theta_rad=theta_rad,
            below_node=int(pair_key[0]),
            above_node=int(pair_key[1]),
        )
        msc = dict(meta.get("msc2d", {}))
        for key, default in self._msc2d_defaults.items():
            vals[key] = int(msc.get(key, default)) if key == "msc_cPath" \
                        else float(msc.get(key, default))
        sp = dict(meta.get("spring", {}))
        vals["sp_Kn"] = float(sp.get("sp_Kn", 500000.0))
        vals["sp_Ks"] = float(sp.get("sp_Ks", 200000.0))
        vals["sp_gap"] = float(sp.get("sp_gap", 0.0))
        vals["sp_w0"] = float(sp.get("sp_w0", 0.0))
        adv = dict(meta.get("advanced", {}))
        vals["yield_disp"] = float(adv.get("yield_disp", vals.get("gap", 0.001)))
        vals["epp_damage"] = bool(adv.get("epp_damage", False))
        return vals

    def _apply_template_to_all(self):
        vals = self._template_values()
        for r in range(self.tbl.rowCount()):
            row_vals = self._row_values(r)
            row_vals.update(vals)
            row_vals["yield_disp"] = vals.get("yield_disp", row_vals.get("yield_disp", row_vals.get("gap", 0.001)))
            self._set_row_values(r, row_vals)
        if self.tbl.rowCount():
            self.tbl.selectRow(0)

    def _apply_editor_to_selected(self):
        
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, "No Selection",
                "Select one or more crack elements first.")
            return
        vals = self._editor_values()
        for row in rows:
            row_vals = self._row_values(row)
            row_vals.update(vals)
            self._set_row_values(row, row_vals)
        self._sync_canvas_highlight()

    def _reset_default(self):
        rows = self._selected_rows() or list(range(self.tbl.rowCount()))
        for row in rows:
            meta = self._row_meta(row)
            default_vals = dict(meta.get("default_values", self._template_values()))
            row_vals = self._row_values(row)
            row_vals.update(default_vals)
            self._set_row_values(row, row_vals, meta)
        self._on_selection_changed()

    def set_geo_ref(self, geo_tab):
        self._geo_ref = geo_tab

    def _sync_canvas_highlight(self):
        geo = self._geo_ref
        if geo is None: return
        pair_keys = []
        for row in self._selected_rows():
            meta = self._row_meta(row)
            if meta.get("pair_key"):
                pair_keys.append(tuple(meta["pair_key"]))
        geo.canvas.set_highlighted_crack_pairs(pair_keys)

    def _on_selection_changed(self):
       
        rows = self._selected_rows()
        if not rows:
            self.lbl_selected.setText("No crack element selected.")
            self._sync_canvas_highlight()
            return
        first = self._row_values(rows[0])
        self.lbl_selected.setText(
            f"Selected {len(rows)} element(s)  |  "
            f"Elem {first['element_index']} at x={first['x']:.3f}, y={first['y']:.3f}")
        self._set_editor_values(first)
        self._sync_canvas_highlight()

    def refresh_from_geometry(self, geo_tab=None):
       
        geo = geo_tab or self._geo_ref
        if geo is None: return
        md = geo.get_mesh_data()
        if md is None:
            QMessageBox.information(self, "No Mesh",
                "Generate a mesh on the Geometry tab first.")
            return
        crack_pairs = list(md["crack_pairs"])
        existing = {}
        for r in range(self.tbl.rowCount()):
            try:
                vals = self._row_values(r)
                if vals["below_node"] and vals["above_node"]:
                    existing[(vals["below_node"], vals["above_node"])] = vals
            except Exception:
                pass
        self.tbl.setRowCount(len(crack_pairs))
        for i, cp in enumerate(crack_pairs):
            pair_key = (int(cp[0]), int(cp[1]))
            if pair_key in existing:
                vals = existing[pair_key]
                vals["element_index"] = i + 1
                vals["y"] = float(cp[2])
                vals["x"] = float(cp[3]) if len(cp) > 3 else vals["x"]
                vals["below_node"] = pair_key[0]
                vals["above_node"] = pair_key[1]
                self._set_row_values(i, vals)
            else:
                vals = self._default_row_values(cp, i)
                self._set_row_values(i, vals, {"default_values": dict(vals)})
        if crack_pairs:
            self.tbl.selectRow(0)
        else:
            self._on_selection_changed()

    def get_params(self):
        
        data = []
        for r in range(self.tbl.rowCount()):
            try:
                vals = self._row_values(r)
                if not self._is_msc2d_type(vals.get("mat_type")):
                    for key in self._msc2d_keys:
                        vals.pop(key, None)
                data.append(vals)
            except Exception:
                pass
        return {"crack_mat_data": data}

    def set_project_state(self, state, geo_tab=None):
        
        geo = geo_tab or self._geo_ref
        if geo is not None:
            self.refresh_from_geometry(geo)
        rows = list(state.get("crack_mat_data", []))
        for row_idx, vals in enumerate(rows):
            if row_idx >= self.tbl.rowCount():
                break
            row_vals = self._row_values(row_idx)
            row_vals.update(dict(vals))
            self._set_row_values(row_idx, row_vals)
        if self.tbl.rowCount():
            self.tbl.selectRow(0)
            self._on_selection_changed()

    def reset_project_state(self):
        self.tbl.setRowCount(0)
        self.lbl_selected.setText("No crack element selected.")



# analysis settings tab — solver options and loading control

class AnalysisTab(QWidget):
    def __init__(self):
        
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)
        outer.addWidget(mk_lbl("Analysis Configuration", "heading"))

        grp_static = QGroupBox("Static Analysis")
        grp_static.setMinimumHeight(320)
        grp_static.setStyleSheet(f"""
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 16px;
    padding: 14px 10px 10px 10px;
}}
QComboBox, QDoubleSpinBox, QSpinBox {{
    background: {BG_INPUT};
    color: {TXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 10px;
    min-height: 32px;
    font-size: 13px;
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {BG_CARD};
    color: {TXT};
    border: 1px solid {BORDER};
    selection-background-color: {C1};
}}
""")
        form = QFormLayout(grp_static)
        form.setSpacing(10)
        form.setContentsMargins(10, 10, 10, 10)
        form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["DisplacementControl", "LoadControl"])
        self.sb_ref_node = QSpinBox()
        self.sb_ref_node.setRange(0, 999999)
        self.sb_ref_node.setValue(0)
        self.sb_ref_node.setToolTip(
            "Node ID to use as displacement control reference. Set to 0 to auto-select from loaded nodes.")
        self.cmb_ref_dof = QComboBox()
        self.cmb_ref_dof.addItems(["Auto", "DOF 1 (X)", "DOF 2 (Y)"])
        self.cmb_ref_dof.setToolTip(
            "Degree of freedom to control. Auto selects based on dominant load direction.")
        self.cmb_system = QComboBox()
        self.cmb_system.addItems(["UmfPack", "BandGeneral", "ProfileSPD"])
        self.cmb_constraints = QComboBox()
        self.cmb_constraints.addItems(["Plain", "Transformation", "Lagrange"])
        self.cmb_numberer = QComboBox()
        self.cmb_numberer.addItems(["RCM", "Plain"])

        self.sb_di  = dsb(0.0005, 1e-7, 1e3, 6, 0.0001,
                          tip="Displacement increment per step (m, DisplacementControl)")
        self.sb_tgt = dsb(0.05,   0.0,  1e4, 6, 0.01,
                          tip="Target total displacement (m, DisplacementControl)")
        self.sb_li  = dsb(0.01,   1e-7, 1.0, 6, 0.01,
                          tip="Load increment fraction per step (LoadControl, 0.01 = 1% of total)")
        self.cmb_alg = QComboBox()
        self.cmb_alg.addItems(["KrylovNewton", "NewtonLineSearch", "Newton", "ModifiedNewton"])
        self.sb_tol  = dsb(1e-8,  1e-14, 1e-2, 12, 1e-9, tip="Convergence tolerance (NormUnbalance)")
        self.sb_iter = isb(400, 1, 5000, tip="Max iterations per step")
        self.sb_lam  = dsb(1., 0.1, 1e9, 1, 0.1, tip="Stop if load factor exceeds this value")

        for w in [self.cmb_type, self.cmb_system, self.cmb_constraints, self.cmb_numberer, self.cmb_alg]:
            w.setMinimumHeight(32)
        self.sb_ref_node.setMinimumHeight(32)
        self.cmb_ref_dof.setMinimumHeight(32)
        for w in [self.sb_di, self.sb_tgt, self.sb_li, self.sb_tol, self.sb_iter, self.sb_lam]:
            w.setMinimumHeight(32)

        form.addRow("Analysis type:",       self.cmb_type)
        form.addRow("Control node (0 = auto):", self.sb_ref_node)
        form.addRow("Control DOF:", self.cmb_ref_dof)
        form.addRow("Equation solver:",     self.cmb_system)
        form.addRow("Constraint handler:",  self.cmb_constraints)
        form.addRow("Numberer:",            self.cmb_numberer)
        form.addRow("Disp. increment (m):", self.sb_di)
        form.addRow("Target disp. (m):",    self.sb_tgt)
        form.addRow("Load incr. fraction:", self.sb_li)
        form.addRow("Algorithm:",           self.cmb_alg)
        form.addRow("Tolerance:",           self.sb_tol)
        form.addRow("Max iterations:",      self.sb_iter)
        form.addRow("Load factor cap λ:",   self.sb_lam)
        outer.addWidget(grp_static)

        grp_lp = QGroupBox("Loading Protocol")
        flp = QFormLayout(grp_lp)
        flp.setSpacing(8)
        proto_row = QHBoxLayout()
        self.rb_monotonic = QRadioButton("Monotonic")
        self.rb_reversed_cyclic = QRadioButton("Reversed-Cyclic")
        self.rb_monotonic.setChecked(True)
        proto_row.addWidget(self.rb_monotonic)
        proto_row.addWidget(self.rb_reversed_cyclic)
        proto_row.addStretch()
        proto_wrap = QWidget(); proto_wrap.setLayout(proto_row)
        self.sb_cycle_count = isb(3, 1, 100, tip="Number of reversed cycles")
        self.sb_cycle_amplitude = dsb(0.005, 1e-6, 1e6, 6, 0.001, tip="Cycle amplitude in active control units")
        self.sb_cycle_scale = dsb(1.0, 0.1, 10.0, 2, 0.1, tip="Amplitude multiplier applied each cycle")
        self.sb_half_cycle_steps = isb(10, 1, 1000, tip="Analysis steps per half-cycle")
        self.tbl_cycles = QTableWidget(0, 2)
        self.tbl_cycles.setHorizontalHeaderLabels(["Amplitude", "Half-cycle steps"])
        self.tbl_cycles.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_cycles.setMaximumHeight(120)
        self.btn_add_cycle    = QPushButton("+ Add Cycle");    self.btn_add_cycle.setObjectName("flat")
        self.btn_remove_cycle = QPushButton("− Remove Last");  self.btn_remove_cycle.setObjectName("flat")
        cycle_btn_row = QHBoxLayout()
        cycle_btn_row.addWidget(self.btn_add_cycle)
        cycle_btn_row.addWidget(self.btn_remove_cycle)
        cycle_btn_row.addStretch()
        cycle_btn_wrap = QWidget(); cycle_btn_wrap.setLayout(cycle_btn_row)
        flp.addRow("Protocol:", proto_wrap)
        flp.addRow("Number of cycles:", self.sb_cycle_count)
        flp.addRow("Amplitude per cycle:", self.sb_cycle_amplitude)
        flp.addRow("Amplitude increase:", self.sb_cycle_scale)
        flp.addRow("Steps per half-cycle:", self.sb_half_cycle_steps)
        flp.addRow("Custom cycles:", self.tbl_cycles)
        flp.addRow("", cycle_btn_wrap)
        flp.addRow("", QWidget())   # spacer row
        outer.addWidget(grp_lp)

        note = mk_lbl(
            "DisplacementControl: applies incremental displacement at the load DOF.\n"
            "LoadControl: applies incremental force up to the pattern load.\n"
            "Algorithm fallback order: KrylovNewton → NewtonLineSearch → ModifiedNewton → Newton.\n"
            "Step size is halved up to 12 times if convergence fails.", "sub")
        note.setWordWrap(True)
        outer.addWidget(note)
        outer.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll)

        self.cmb_type.currentTextChanged.connect(self._update_protocol_labels)
        self.cmb_type.currentTextChanged.connect(self._on_analysis_type_changed)
        self.rb_monotonic.toggled.connect(self._update_protocol_visibility)
        self.btn_add_cycle.clicked.connect(self._add_cycle_row)
        self.btn_remove_cycle.clicked.connect(self._remove_last_cycle_row)
        self._update_protocol_labels()
        self._update_protocol_visibility()
        self._on_analysis_type_changed(self.cmb_type.currentText())

    def _on_analysis_type_changed(self, mode):
        is_disp = (mode == "DisplacementControl")
        self.sb_di.setEnabled(is_disp)
        self.sb_tgt.setEnabled(is_disp)
        self.sb_ref_node.setEnabled(is_disp)
        self.cmb_ref_dof.setEnabled(is_disp)
        self.sb_li.setEnabled(not is_disp)

        if is_disp:
            self.sb_di.setToolTip("Displacement increment per step (m, DisplacementControl)")
            self.sb_tgt.setToolTip("Target total displacement (m, DisplacementControl)")
            self.sb_ref_node.setToolTip(
                "Node ID to use as displacement control reference. Set to 0 to auto-select from loaded nodes.")
            self.cmb_ref_dof.setToolTip(
                "Degree of freedom to control. Auto selects based on dominant load direction.")
            self.sb_li.setToolTip("Not used in DisplacementControl mode")
        else:
            self.sb_di.setToolTip("Not used in LoadControl mode")
            self.sb_tgt.setToolTip("Not used in LoadControl mode")
            self.sb_ref_node.setToolTip("Not used in LoadControl mode")
            self.cmb_ref_dof.setToolTip("Not used in LoadControl mode")
            self.sb_li.setToolTip("Load increment fraction per step (LoadControl, 0.01 = 1% of total)")

    def _update_protocol_labels(self):
        units = "m" if self.cmb_type.currentText() == "DisplacementControl" else "load factor"
        self.sb_cycle_amplitude.setToolTip(f"Cycle amplitude in {units}")

    def _update_protocol_visibility(self):
        on = self.rb_reversed_cyclic.isChecked()
        for w in [
            self.sb_cycle_count, self.sb_cycle_amplitude, self.sb_cycle_scale,
            self.sb_half_cycle_steps, self.tbl_cycles, self.btn_add_cycle, self.btn_remove_cycle,
        ]:
            w.setEnabled(on)

    def _add_cycle_row(self):
        r = self.tbl_cycles.rowCount()
        self.tbl_cycles.insertRow(r)
        self.tbl_cycles.setItem(r, 0, QTableWidgetItem("0.005"))
        self.tbl_cycles.setItem(r, 1, QTableWidgetItem("10"))

    def _remove_last_cycle_row(self):
        if self.tbl_cycles.rowCount() > 0:
            self.tbl_cycles.removeRow(self.tbl_cycles.rowCount() - 1)

    def _get_custom_cycles(self):
        cycles = []
        for r in range(self.tbl_cycles.rowCount()):
            try:
                amp   = float(self.tbl_cycles.item(r, 0).text())
                steps = int(self.tbl_cycles.item(r, 1).text())
                cycles.append({"amplitude": amp, "half_cycle_steps": steps})
            except Exception:
                pass
        return cycles

    def get_params(self):
        
        return {
            "analysis_type": self.cmb_type.currentText(),
            "ref_node": self.sb_ref_node.value(),
            "ref_dof_mode": self.cmb_ref_dof.currentText(),
            "solver_system": self.cmb_system.currentText(),
            "constraint_handler": self.cmb_constraints.currentText(),
            "numberer": self.cmb_numberer.currentText(),
            "disp_incr":     self.sb_di.value(),
            "target_disp":   self.sb_tgt.value(),
            "load_incr":     self.sb_li.value(),
            "algorithm":     self.cmb_alg.currentText(),
            "tol":           self.sb_tol.value(),
            "max_iter":      self.sb_iter.value(),
            "max_load_factor": self.sb_lam.value(),
            "loading_protocol": "reversed-cyclic" if self.rb_reversed_cyclic.isChecked() else "monotonic",
            "cycle_count": self.sb_cycle_count.value(),
            "cycle_amplitude": self.sb_cycle_amplitude.value(),
            "cycle_amplitude_scale": self.sb_cycle_scale.value(),
            "steps_per_half_cycle": self.sb_half_cycle_steps.value(),
            "custom_cycles": self._get_custom_cycles(),
        }

    def set_project_state(self, state):
        
        self.cmb_type.setCurrentText(state.get("analysis_type", "DisplacementControl"))
        self.sb_ref_node.setValue(int(state.get("ref_node", 0)))
        self.cmb_ref_dof.setCurrentText(state.get("ref_dof_mode", "Auto"))
        self.cmb_system.setCurrentText(state.get("solver_system", "UmfPack"))
        self.cmb_constraints.setCurrentText(state.get("constraint_handler", "Plain"))
        self.cmb_numberer.setCurrentText(state.get("numberer", "RCM"))
        self.sb_di.setValue(float(state.get("disp_incr", 0.0005)))
        self.sb_tgt.setValue(float(state.get("target_disp", 0.05)))
        self.sb_li.setValue(float(state.get("load_incr", 0.01)))
        self.cmb_alg.setCurrentText(state.get("algorithm", "KrylovNewton"))
        self.sb_tol.setValue(float(state.get("tol", 1e-8)))
        self.sb_iter.setValue(int(state.get("max_iter", 400)))
        self.sb_lam.setValue(float(state.get("max_load_factor", 1.0)))
        protocol = state.get("loading_protocol", "monotonic")
        self.rb_reversed_cyclic.setChecked(protocol == "reversed-cyclic")
        self.rb_monotonic.setChecked(protocol != "reversed-cyclic")
        self.sb_cycle_count.setValue(int(state.get("cycle_count", 3)))
        self.sb_cycle_amplitude.setValue(float(state.get("cycle_amplitude", 0.005)))
        self.sb_cycle_scale.setValue(float(state.get("cycle_amplitude_scale", 1.0)))
        self.sb_half_cycle_steps.setValue(int(state.get("steps_per_half_cycle", 10)))
        self.tbl_cycles.setRowCount(0)
        for cyc in state.get("custom_cycles", []) or []:
            try:
                r = self.tbl_cycles.rowCount()
                self.tbl_cycles.insertRow(r)
                self.tbl_cycles.setItem(r, 0, QTableWidgetItem(str(float(cyc.get("amplitude", 0.005)))))
                self.tbl_cycles.setItem(r, 1, QTableWidgetItem(str(int(cyc.get("half_cycle_steps", 10)))))
            except Exception:
                pass
        self._update_protocol_labels()
        self._update_protocol_visibility()

    def reset_project_state(self):
        self.set_project_state({})



# run tab — backend checks and analysis launch controls

class RunTab(QWidget):
    run_requested = pyqtSignal()
    auto_detect_requested = pyqtSignal()

    def __init__(self):
        
        super().__init__()
        self.backend_mode = "wsl"
        self.python_cmd = "python3"
        outer = QVBoxLayout(self); outer.setContentsMargins(16, 16, 16, 16); outer.setSpacing(10)
        outer.addWidget(mk_lbl("Run Analysis  (GUI → OpenSeesPy Backend)", "heading"))

        grp_wsl = QGroupBox("Solver Environment")
        wf = QFormLayout(grp_wsl); wf.setSpacing(6)
        self.wsl_activate = QLineEdit("source ~/ops_env/bin/activate")
        self.wsl_activate.setToolTip(
            "WSL activate command or direct Python command used to launch OpenSeesPy.\n"
            "Examples:\n"
            "  source ~/ops_env/bin/activate   (virtualenv)\n"
            "  conda activate opensees          (conda)\n"
            "  true                             (WSL system python with openseespy)\n"
            "  C:/Python311/python.exe          (Windows python)")
        self.lbl_detect = mk_lbl("Detection: not run yet.", "sub")
        wf.addRow("Activate / Python cmd:", self.wsl_activate)
        wf.addRow("Status:", self.lbl_detect)
        outer.addWidget(grp_wsl)

        brow = QHBoxLayout()
        self.btn_run   = QPushButton("▶  Run Analysis")
        self.btn_run.setObjectName("success"); self.btn_run.setMinimumHeight(40)
        self.btn_auto_detect = QPushButton("Auto-Detect")
        self.btn_auto_detect.setObjectName("flat")
        self.btn_validate_build = QPushButton("✓ Validate OpenSees Build")
        self.btn_validate_build.setObjectName("flat")
        self.btn_validate_build.setToolTip("Check if OpenSeesPy backend is working correctly via WSL or local Python")
        self.btn_self_test = QPushButton("🧪 Test MultiSurfCrack2D")
        self.btn_self_test.setObjectName("flat")
        self.btn_self_test.setToolTip("Test if MultiSurfCrack2D material is available in your OpenSees build")
        self.btn_clear = QPushButton("Clear Console"); self.btn_clear.setObjectName("flat")
        brow.addWidget(self.btn_run); brow.addWidget(self.btn_auto_detect); brow.addWidget(self.btn_validate_build); brow.addWidget(self.btn_self_test); brow.addWidget(self.btn_clear); brow.addStretch()
        outer.addLayout(brow)

        self.lbl_status = mk_lbl("Ready. Configure Geometry → Crack Materials → Analysis → Run.", "sub")
        outer.addWidget(self.lbl_status)

        grp_con = QGroupBox("Console Output")
        lc = QVBoxLayout(grp_con)
        self.console = QTextEdit(); self.console.setReadOnly(True); self.console.setMinimumHeight(320)
        lc.addWidget(self.console)
        outer.addWidget(grp_con, stretch=1)

        self.btn_run.clicked.connect(self.run_requested.emit)
        self.btn_auto_detect.clicked.connect(self.auto_detect_requested.emit)
        self.btn_validate_build.clicked.connect(self._validate_build)
        self.btn_self_test.clicked.connect(self._run_self_test)
        self.btn_clear.clicked.connect(self.console.clear)

    def _validate_build(self):
        
        self.append("\n" + "="*60)
        self.append("VALIDATING OpenSeesPy BACKEND")
        self.append("="*60)
        act = self.get_activate()
        import subprocess, sys
        is_windows = sys.platform.startswith("win")
        if is_windows:
            cmd = ["wsl", "bash", "-lc",
                   f"{act} && python3 -c \"import openseespy.opensees as ops; print('MultiSurfCrack2D:', ops.version())\""]
        else:
            cmd = ["bash", "-lc",
                   f"{act} && python3 -c \"import openseespy.opensees as ops; print('MultiSurfCrack2D:', ops.version())\""]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode == 0 and proc.stdout.strip():
                self.append(f"PASS: {proc.stdout.strip()}")
                QMessageBox.information(self, "Backend Valid", f"OpenSeesPy is working.\n{proc.stdout.strip()}")
            else:
                self.append(f"FAIL: {proc.stderr.strip() or proc.stdout.strip()}")
                QMessageBox.warning(self, "Backend Failed", f"OpenSeesPy check failed.\n{proc.stderr.strip()}")
        except Exception as e:
            self.append(f"ERROR: {e}")
        self.append("="*60 + "\n")

    def _run_self_test(self):
       
        self.append("\n" + "="*60)
        self.append("TESTING MultiSurfCrack2D AVAILABILITY")
        self.append("="*60)
        act = self.get_activate()
        import subprocess, sys
        is_windows = sys.platform.startswith("win")
        test_script = (
            "import openseespy.opensees as ops; "
            "ops.wipe(); ops.model('basic','-ndm',2,'-ndf',2); "
            "ops.node(1,0,0); ops.node(2,0,0); "
            "ops.nDMaterial('MultiSurfCrack2D',1,"
            "210,5.95,0,0,210,5.95,0,0,30,25,5,1,0.5,0.3,0.5,0.7,0.5,0.3,1,0.785,0.01,0); "
            "print('MultiSurfCrack2D: OK')"
        )
        if is_windows:
            cmd = ["wsl", "bash", "-lc", f"{act} && python3 -c \"{test_script}\""]
        else:
            cmd = ["bash", "-lc", f"{act} && python3 -c \"{test_script}\""]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode == 0 and "OK" in proc.stdout:
                self.append("PASS: MultiSurfCrack2D is available in this OpenSees build")
                QMessageBox.information(self, "Test Passed", "MultiSurfCrack2D is confirmed working.")
            else:
                out = proc.stderr.strip() or proc.stdout.strip()
                self.append(f"FAIL: MultiSurfCrack2D not available\n{out}")
                self.append("INFO: EPPGap Macro fallback will be used automatically")
                QMessageBox.warning(self, "MultiSurfCrack2D Not Found",
                    f"MultiSurfCrack2D is not in this OpenSees build.\n\n"
                    f"The GUI will automatically use EPPGap Macro instead.\n\n{out}")
        except Exception as e:
            self.append(f"ERROR: {e}")
        self.append("="*60 + "\n")

    def apply_backend_config(self, cfg):
        self.backend_mode = cfg.get("backend_mode", "wsl")
        self.python_cmd = cfg.get("python_cmd", self.python_cmd)
        cmd = cfg.get("activate_cmd", "source ~/ops_env/bin/activate")
        self.wsl_activate.setText(cmd)
        self.set_detection_status(cfg.get("status_label", "Detection: not run yet."), ok=cfg.get("status_ok", True))

    def get_backend_config(self):
        return {
            "backend_mode": self.backend_mode,
            "activate_cmd": self.get_activate(),
            "python_cmd": self.python_cmd,
            "status_label": self.lbl_detect.text(),
            "status_ok": "not found" not in self.lbl_detect.text().lower(),
        }

    def get_activate(self): return self.wsl_activate.text().strip() or "true"

    def set_detection_status(self, msg, ok=True):
        self.lbl_detect.setText(msg)
        self.lbl_detect.setStyleSheet(f"color:{C2 if ok else C3};font-weight:bold;")

    def append(self, msg):
        self.console.append(msg)
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    def set_status(self, msg, ok=True):
        self.lbl_status.setStyleSheet(f"color:{C2 if ok else C3};font-weight:bold;")
        self.lbl_status.setText(msg)



# Crack Response Dialog

class CrackResponseDialog(QDialog):
    def __init__(self, element_meta, parent=None):
        """
        Set up widget state, defaults, and signal wiring for this section.
        """
        super().__init__(parent)
        self.setWindowTitle(f"Crack Element {element_meta.get('element_index', '?')} Response")
        self.resize(920, 560)
        lay = QVBoxLayout(self)
        title = mk_lbl(
            f"Elem {element_meta.get('element_index', '?')}  |  x={element_meta.get('x', 0.0):.3f} m  y={element_meta.get('y', 0.0):.3f} m  |  {element_meta.get('mat_type', 'Unknown')}",
            "sub"
        )
        lay.addWidget(title)

        fig = Figure(facecolor=BG_DEEP, tight_layout=True)
        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)
        for ax in (ax1, ax2):
            ax.set_facecolor(BG_PANEL)
            ax.tick_params(colors=TXTS, labelsize=9)
            ax.xaxis.label.set_color(TXT); ax.yaxis.label.set_color(TXT)
            ax.title.set_color(C1)
            for s in ax.spines.values():
                s.set_edgecolor(BORDER)
            ax.grid(True, alpha=0.15, color=BORDER, linestyle="--")

        slips = np.array(element_meta.get("slips", []), dtype=float)
        shear = np.array(element_meta.get("shear_forces", []), dtype=float)
        openings = np.array(element_meta.get("openings", []), dtype=float)
        width0 = float(element_meta.get("width", 0.0))
        crack_width = width0 + openings
        normal_stress = np.array(element_meta.get("normal_stresses", []), dtype=float)

        ax1.plot(slips, shear, color=C1, lw=1.8)
        ax1.set_title("Shear Force vs Slip")
        ax1.set_xlabel("Slip (m)")
        ax1.set_ylabel("Shear force (kN)")

        ax2.plot(crack_width, normal_stress, color=C3, lw=1.8)
        ax2.set_title("Normal Stress vs Crack Width")
        ax2.set_xlabel("Crack width (m)")
        ax2.set_ylabel("Normal stress (MPa)")

        canv = FigureCanvas(fig)
        lay.addWidget(canv, stretch=1)


class BodyElementDialog(QDialog):
    """Pop-up showing stress history for a selected triangular body element."""
    def __init__(self, eid, stress_history, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Body Element {eid} — Stress History")
        self.resize(960, 480)
        lay = QVBoxLayout(self)
        lay.addWidget(mk_lbl(f"Element {eid}  |  tri31 PlaneStress — Stress vs Load Step", "sub"))

        fig = Figure(facecolor=BG_DEEP, tight_layout=True)
        axes = [fig.add_subplot(1, 3, i + 1) for i in range(3)]
        titles = ["sxx vs Step", "syy vs Step", "txy vs Step"]
        colors = [C1, C2, C3]
        steps = np.arange(len(stress_history))

        for ax, col, title, idx in zip(axes, colors, titles, range(3)):
            ax.set_facecolor(BG_PANEL)
            ax.tick_params(colors=TXTS, labelsize=9)
            for spine in ax.spines.values():
                spine.set_edgecolor(BORDER)
            ax.grid(True, alpha=0.15, color=BORDER, linestyle="--")
            ax.set_title(title, color=C1, fontsize=10)
            ax.set_xlabel("Step", color=TXT, fontsize=9)
            ax.set_ylabel("Stress (MPa)", color=TXT, fontsize=9)
            vals = [s[idx] if not np.isnan(s[idx]) else 0.0 for s in stress_history]
            ax.plot(steps, vals, color=col, lw=1.8)

        canv = FigureCanvas(fig)
        lay.addWidget(canv, stretch=1)
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)


# results tab — charts, contours, and crack response plots

class ResultsTab(QWidget):
    PLOT_OPTS = [
        "Force–Displacement",
        "Crack Opening History",
        "Crack Slip History",
        "Crack Hysteresis (Slip vs Force)",
        "Deformed Mesh",
        "Displacement Magnitude Contour",
        "Crack Behavior Overlay",
    ]
    COLORS = ["#58a6ff", "#3fb950", "#f78166", "#d2a679", "#c9d1d9", "#8b949e"]

    def __init__(self):
        """
        Set up widget state, defaults, and signal wiring for this section.
        """
        super().__init__()
        outer = QVBoxLayout(self); outer.setContentsMargins(16, 16, 16, 16); outer.setSpacing(8)
        outer.addWidget(mk_lbl("Analysis Results", "heading"))

        ctrl = QHBoxLayout()
        self.cmb_plot  = QComboBox(); self.cmb_plot.addItems(self.PLOT_OPTS)
        self.cmb_crack = QComboBox(); self.cmb_crack.setFixedWidth(200)
        self.sb_scale  = dsb(100., 0.1, 1e6, 1, 10., w=100, tip="Deformation scale factor for mesh plot")
        self.btn_rp    = QPushButton("Replot");     self.btn_rp.setObjectName("flat")
        self.btn_save  = QPushButton("Save PNG");   self.btn_save.setObjectName("flat")
        self.btn_csv   = QPushButton("Export CSV"); self.btn_csv.setObjectName("flat")
        self.btn_load_exp = QPushButton("Load Exp. Data"); self.btn_load_exp.setObjectName("flat")
        self.btn_clear_exp = QPushButton("Clear Exp."); self.btn_clear_exp.setObjectName("flat")
        self.btn_clear_exp.setEnabled(False)
        for w in [mk_lbl("Plot:"), self.cmb_plot,
                  mk_lbl("  Crack:"), self.cmb_crack,
                  mk_lbl("  Scale ×"), self.sb_scale,
                  self.btn_rp, self.btn_save, self.btn_csv,
                  self.btn_load_exp, self.btn_clear_exp]:
            ctrl.addWidget(w)
        ctrl.addStretch()
        outer.addLayout(ctrl)

        # Overlay-mode controls (hidden unless "Crack Behavior Overlay") 
        self._overlay_ctrl = QWidget()
        ocl = QHBoxLayout(self._overlay_ctrl)
        ocl.setContentsMargins(0, 0, 0, 0); ocl.setSpacing(6)
        self.cmb_ov_metric = QComboBox()
        self.cmb_ov_metric.addItems(["Opening", "Slip"])
        self.sld_step = QSlider(Qt.Horizontal)
        self.sld_step.setMinimum(0); self.sld_step.setMaximum(0)
        self.sld_step.setValue(0); self.sld_step.setFixedWidth(220)
        self.lbl_step = mk_lbl("Step: 0/0", "sub")
        for w in [mk_lbl("Metric:"), self.cmb_ov_metric,
                  mk_lbl("  Step:"), self.sld_step, self.lbl_step]:
            ocl.addWidget(w)
        ocl.addStretch()
        outer.addWidget(self._overlay_ctrl)
        self._overlay_ctrl.setVisible(False)

        self.fig = Figure(facecolor=BG_DEEP, tight_layout=True)
        self.ax  = self.fig.add_subplot(111)
        self._style_ax()
        self.canv = FigureCanvas(self.fig)
        self.tb   = NavigationToolbar(self.canv, self)
        self.tb.setStyleSheet(f"background:{BG_PANEL};color:{TXT};")
        outer.addWidget(self.tb); outer.addWidget(self.canv, stretch=1)

        self._reset()
        self.canv.mpl_connect("button_press_event", self._on_canvas_click)
        self.cmb_plot.currentTextChanged.connect(self._on_plot_mode_changed)
        self.cmb_crack.currentIndexChanged.connect(self.replot)
        self.sb_scale.valueChanged.connect(self.replot)
        self.btn_rp.clicked.connect(self.replot)
        self.btn_save.clicked.connect(self._save)
        self.btn_csv.clicked.connect(self._csv)
        self.cmb_ov_metric.currentIndexChanged.connect(self.replot)
        self.sld_step.valueChanged.connect(self._on_step_slider)
        self.btn_load_exp.clicked.connect(self._load_exp_data)
        self.btn_clear_exp.clicked.connect(self._clear_exp_data)

    def _style_ax(self):
        self.ax.set_facecolor(BG_PANEL)
        self.ax.tick_params(colors=TXTS, labelsize=9)
        self.ax.xaxis.label.set_color(TXT); self.ax.yaxis.label.set_color(TXT)
        self.ax.title.set_color(C1)
        for s in self.ax.spines.values(): s.set_edgecolor(BORDER)
        self.ax.grid(True, alpha=0.15, color=BORDER, linestyle="--")

    def _load_exp_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Experimental Data CSV", "",
            "CSV files (*.csv);;All Files (*)")
        if not path:
            return
        try:
            import csv
            disp_vals = []; force_vals = []
            with open(path, newline='', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                header = next(reader, None)  # skip header
                for row in reader:
                    if len(row) >= 2:
                        disp_vals.append(float(row[0]))
                        force_vals.append(float(row[1]))
            self._exp_disp = np.array(disp_vals)
            self._exp_force = np.array(force_vals)
            self.btn_clear_exp.setEnabled(True)
            self.replot()
        except Exception as e:
            QMessageBox.warning(self, "Load Error", f"Failed to load CSV:\n{e}")

    def _clear_exp_data(self):
        self._exp_disp = None
        self._exp_force = None
        self.btn_clear_exp.setEnabled(False)
        self.replot()

    def _on_plot_mode_changed(self, mode):
        is_overlay = (mode == "Crack Behavior Overlay")
        self._overlay_ctrl.setVisible(is_overlay)
        self.replot()

    def _on_step_slider(self, val):
        n = max(len(self._disp), 1)
        self.lbl_step.setText(f"Step: {val}/{n - 1}")
        self.replot()

    def _reset(self):
        self._disp = np.array([]); self._force = np.array([])
        self._crack_pos = np.array([])
        self._co = []; self._cs = []
        self._mesh_nodes = {}; self._mesh_tris = []
        self._node_disp_last = {}
        self._hand_strokes = []
        self._hand_ys      = []
        self._element_responses = []
        self._elem_stress_keys = np.array([], dtype=np.int32)
        self._elem_stress_vals = np.array([])
        self._exp_disp = None
        self._exp_force = None

    def set_results(self, r):

        self._disp  = r["disp"]; self._force = r["force"]
        self._crack_pos = r.get("crack_positions", np.array([]))
        self._co    = r.get("crack_openings", [])
        self._cs    = r.get("crack_slips", [])
        self._element_responses = list(r.get("element_responses", []))
        self._mesh_nodes     = r.get("mesh_nodes", {})
        self._mesh_tris      = r.get("mesh_tris", [])
        self._node_disp_last = r.get("node_disp_last", {})
        self._hand_strokes   = r.get("hand_crack_strokes", [])
        self._hand_ys        = r.get("hand_crack_ys", [])
        self._elem_stress_keys = r.get("esh_keys", np.array([], dtype=np.int32))
        self._elem_stress_vals = r.get("esh_vals", np.array([]))
        # Update step slider range to match number of converged steps
        n = max(len(self._disp) - 1, 0)
        self.sld_step.blockSignals(True)
        self.sld_step.setMaximum(n); self.sld_step.setValue(n)
        self.sld_step.blockSignals(False)
        self.lbl_step.setText(f"Step: {n}/{n}")
        self.cmb_crack.blockSignals(True); self.cmb_crack.clear()
        self.cmb_crack.addItem("All Cracks")
        for i, y in enumerate(self._crack_pos):
            self.cmb_crack.addItem(f"Crack {i+1}  y={float(y):.3f}")
        self.cmb_crack.blockSignals(False)
        self.replot()

    def replot(self):
       
        self.ax.cla(); self._style_ax()
        mode = self.cmb_plot.currentText()
        sel  = self.cmb_crack.currentIndex()
        C    = self.COLORS

        if mode == "Force–Displacement":
            if self._disp.size == 0:
                self.ax.set_title("No data"); self.canv.draw(); return
            self.ax.plot(self._disp, self._force, color=C1, lw=1.8, label="Response")
            if self._exp_disp is not None and self._exp_force is not None:
                self.ax.plot(self._exp_disp, self._exp_force,
                             color="#f0883e", lw=1.5, ls="--", label="Experimental")
            self.ax.set_xlabel("Displacement (m)"); self.ax.set_ylabel("Force (kN)")
            self.ax.set_title("Force–Displacement Response")
            self.ax.legend(facecolor=BG_CARD, edgecolor=BORDER, labelcolor=TXT, fontsize=9)

        elif mode in ("Crack Opening History", "Crack Slip History"):
            data = self._co if "Opening" in mode else self._cs
            ylabel = "Opening (m)" if "Opening" in mode else "Slip (m)"
            title  = "Crack Opening History" if "Opening" in mode else "Crack Slip History"
            if not data:
                self.ax.set_title("No crack data"); self.canv.draw(); return
            items = list(range(len(data))) if sel <= 0 else [sel - 1]
            for i in items:
                arr = data[i]
                lbl = (f"Crack {i+1} y={float(self._crack_pos[i]):.3f}"
                       if i < len(self._crack_pos) else f"Crack {i+1}")
                self.ax.plot(np.arange(len(arr)), arr, color=C[i % len(C)], lw=1.6, label=lbl)
            self.ax.set_xlabel("Step"); self.ax.set_ylabel(ylabel); self.ax.set_title(title)
            self.ax.legend(facecolor=BG_CARD, edgecolor=BORDER, labelcolor=TXT, fontsize=9)

        elif mode == "Crack Hysteresis (Slip vs Force)":
            if not self._cs or self._disp.size == 0:
                self.ax.set_title("No data"); self.canv.draw(); return
            items = list(range(len(self._cs))) if sel <= 0 else [sel - 1]
            for i in items:
                n = min(len(self._cs[i]), len(self._force))
                lbl = (f"Crack {i+1} y={float(self._crack_pos[i]):.3f}"
                       if i < len(self._crack_pos) else f"Crack {i+1}")
                self.ax.plot(self._cs[i][:n], self._force[:n],
                             color=C[i % len(C)], lw=1.2, label=lbl)
            self.ax.set_xlabel("Crack Slip (m)"); self.ax.set_ylabel("Total Force (kN)")
            self.ax.set_title("Crack Hysteresis — Slip vs Force")
            self.ax.legend(facecolor=BG_CARD, edgecolor=BORDER, labelcolor=TXT, fontsize=9)

        elif mode == "Deformed Mesh":
            self._plot_deformed()

        elif mode == "Displacement Magnitude Contour":
            self._plot_contour()

        elif mode == "Crack Behavior Overlay":
            self._plot_crack_overlay()

        self.canv.draw()

    def _plot_deformed(self):
       
        if not self._mesh_nodes or not self._mesh_tris:
            self.ax.set_title("No mesh data (run analysis first)"); return
        scale = self.sb_scale.value()
        nodes = self._mesh_nodes; nd = self._node_disp_last
        def _safe_nd(n):
            return nd.get(n, nd.get(str(n), [0.0, 0.0]))
        # Undeformed (faint)
        for _, n1, n2, n3 in self._mesh_tris:
            xs = [nodes[n][0] for n in (n1, n2, n3, n1)]
            ys = [nodes[n][1] for n in (n1, n2, n3, n1)]
            self.ax.plot(xs, ys, color="#30363d", lw=0.4, zorder=1)
        # Deformed (bright)
        for _, n1, n2, n3 in self._mesh_tris:
            xs = [nodes[n][0] + scale * _safe_nd(n)[0] for n in (n1, n2, n3, n1)]
            ys = [nodes[n][1] + scale * _safe_nd(n)[1] for n in (n1, n2, n3, n1)]
            self.ax.plot(xs, ys, color=C1, lw=0.7, zorder=2)
        self.ax.set_aspect("equal"); self.ax.set_xlabel("X (m)"); self.ax.set_ylabel("Y (m)")
        self.ax.set_title(f"Deformed Mesh  (scale ×{scale:.0f})")
        self.ax.text(0.02, 0.97, f"scale ×{scale:.0f}", transform=self.ax.transAxes,
                     va="top", color=TXTS, fontsize=9, family="monospace")
        self._draw_clickable_crack_markers()

    def _plot_contour(self):
       
        if not self._mesh_nodes or not self._node_disp_last:
            self.ax.set_title("No displacement data (run analysis first)"); return
        nodes = self._mesh_nodes; nd = self._node_disp_last
        def _safe_nd(n):
            return nd.get(n, nd.get(str(n), [0.0, 0.0]))
        nids  = sorted(nodes.keys())
        nid_idx = {n: i for i, n in enumerate(nids)}
        xs = np.array([nodes[n][0] for n in nids])
        ys = np.array([nodes[n][1] for n in nids])
        mag = np.array([math.hypot(*_safe_nd(n)) for n in nids])
        # Build triangulation
        valid_tris = []
        for _, n1, n2, n3 in self._mesh_tris:
            if n1 in nid_idx and n2 in nid_idx and n3 in nid_idx:
                valid_tris.append([nid_idx[n1], nid_idx[n2], nid_idx[n3]])
        if not valid_tris:
            self.ax.set_title("Cannot build triangulation"); return
        tri_arr = np.array(valid_tris)
        triang = Triangulation(xs, ys, tri_arr)
        cf = self.ax.tricontourf(triang, mag * 1000., levels=16, cmap="plasma")
        self.fig.colorbar(cf, ax=self.ax, label="Displacement magnitude (mm)")
        self.ax.triplot(triang, color=BORDER, lw=0.3, alpha=0.4)
        self.ax.set_aspect("equal"); self.ax.set_xlabel("X (m)"); self.ax.set_ylabel("Y (m)")
        self.ax.set_title("Displacement Magnitude Contour")
        self._draw_clickable_crack_markers()

    def _plot_crack_overlay(self):
        """Draw hand-drawn strokes over the undeformed mesh, styled by crack scalar."""
        if not self._hand_strokes:
            self.ax.set_title(
                "No hand-drawn cracks available\n"
                "(draw strokes in Geometry tab  ✏ Draw mode, then re-run analysis)")
            return

        # Light undeformed mesh backdrop
        nodes = self._mesh_nodes
        if nodes and self._mesh_tris:
            for _, n1, n2, n3 in self._mesh_tris:
                xs_ = [nodes[n][0] for n in (n1, n2, n3, n1)]
                ys_ = [nodes[n][1] for n in (n1, n2, n3, n1)]
                self.ax.plot(xs_, ys_, color=BORDER, lw=0.3, alpha=0.4, zorder=1)

        step_idx     = self.sld_step.value()
        metric       = self.cmb_ov_metric.currentText()
        data_arr     = self._co if metric == "Opening" else self._cs
        stroke_color = "#ff7043" if metric == "Opening" else "#ab47bc"

        # Tolerance for matching stroke y_mean to a crack position
        H = 1.0
        if nodes:
            all_ys = [nodes[n][1] for n in nodes]
            H = max(all_ys) if all_ys else 1.0
        tol = max(5e-3 * H, 1e-4)

        legend_handles = []; legend_labels = []
        for si, stroke in enumerate(self._hand_strokes):
            if not stroke:
                continue
            xs_s  = [pt[0] for pt in stroke]
            ys_s  = [pt[1] for pt in stroke]
            y_mean = sum(ys_s) / len(ys_s)

            # Find nearest crack position in analysis results
            crack_idx = None
            if len(self._crack_pos) > 0:
                dists = [abs(float(cp) - y_mean) for cp in self._crack_pos]
                best  = int(min(range(len(dists)), key=lambda i: dists[i]))
                if dists[best] < tol:
                    crack_idx = best

            # Read scalar at step
            val = 0.0
            if crack_idx is not None and crack_idx < len(data_arr):
                arr = data_arr[crack_idx]
                if arr:
                    idx = min(step_idx, len(arr) - 1)
                    try: val = float(arr[idx])
                    except (TypeError, IndexError): val = 0.0

            mag   = abs(val)
            lw    = min(max(2.0 + mag * 2000.0, 2.0), 10.0)
            alpha = min(max(0.3 + mag * 500.0,  0.3),  1.0)
            line, = self.ax.plot(xs_s, ys_s, color=stroke_color, lw=lw,
                                 alpha=alpha, solid_capstyle='round', zorder=3)
            if crack_idx is not None:
                lbl = (f"Stroke {si+1}  y≈{y_mean:.3f} m : "
                       f"{metric.lower()} = {val * 1000.0:.3f} mm")
            else:
                lbl = f"Stroke {si+1}  y≈{y_mean:.3f} m : no matching crack"
            legend_handles.append(line); legend_labels.append(lbl)

        if legend_handles:
            self.ax.legend(legend_handles, legend_labels,
                           facecolor=BG_CARD, edgecolor=BORDER,
                           labelcolor=TXT, fontsize=8)

        self.ax.set_aspect("equal")
        self.ax.set_xlabel("X (m)"); self.ax.set_ylabel("Y (m)")
        n_steps = len(self._disp)
        step_label = f"{step_idx}/{max(n_steps - 1, 0)}" if n_steps else "0/0"
        self.ax.set_title(
            f"Crack Behavior Overlay — {metric}   Step {step_label}")
        self.ax.text(0.02, 0.97,
                     f"Strokes: {len(self._hand_strokes)}   "
                     f"lw ∝ {metric.lower()} magnitude",
                     transform=self.ax.transAxes, va="top",
                     color=TXTS, fontsize=8, family="monospace")
        self._draw_clickable_crack_markers()

    def _draw_clickable_crack_markers(self):
        if not self._element_responses:
            return
        xs = [float(meta.get("x", 0.0)) for meta in self._element_responses]
        ys = [float(meta.get("y", 0.0)) for meta in self._element_responses]
        self.ax.scatter(xs, ys, s=28, facecolors='none', edgecolors="#ffd54f",
                        linewidths=1.2, zorder=6)
        self.ax.text(0.02, 0.03, "Click a crack marker or any triangle to view element response history.",
                     transform=self.ax.transAxes, color=TXTS, fontsize=8, family="monospace")

    def _on_canvas_click(self, event):
        """
        Handle a UI event and keep the related state in sync.
        Clicking a crack marker opens CrackResponseDialog.
        Clicking a triangle body element opens BodyElementDialog.
        """
        mode = self.cmb_plot.currentText()
        if mode not in ("Deformed Mesh", "Displacement Magnitude Contour", "Crack Behavior Overlay"):
            return
        if event.inaxes != self.ax or event.xdata is None or event.ydata is None:
            return

        # First try crack interface element markers
        if self._element_responses:
            xs = [float(meta.get("x", 0.0)) for meta in self._element_responses]
            ys = [float(meta.get("y", 0.0)) for meta in self._element_responses]
            bounds_x = max(xs) - min(xs) if len(xs) > 1 else 1.0
            bounds_y = max(ys) - min(ys) if len(ys) > 1 else 1.0
            tol = 0.04 * max(bounds_x, bounds_y, 1.0)
            best_idx = None
            best_dist = tol
            for idx, (xv, yv) in enumerate(zip(xs, ys)):
                dist = math.hypot(event.xdata - xv, event.ydata - yv)
                if dist <= best_dist:
                    best_idx = idx
                    best_dist = dist
            if best_idx is not None:
                dlg = CrackResponseDialog(self._element_responses[best_idx], self)
                dlg.exec_()
                return

        # Then try body triangle elements
        self._on_mesh_click(event)

    def _on_mesh_click(self, event):
        """Find which tri element was clicked and show its stress history."""
        if event.inaxes != self.ax:
            return
        if not self._mesh_tris:
            return
        if len(self._elem_stress_keys) == 0:
            return
        cx, cy = event.xdata, event.ydata
        if cx is None or cy is None:
            return
        nodes = self._mesh_nodes
        best_eid, best_dist = None, float('inf')
        for tri_row in self._mesh_tris:
            eid, n1, n2, n3 = int(tri_row[0]), tri_row[1], tri_row[2], tri_row[3]
            if n1 in nodes and n2 in nodes and n3 in nodes:
                x1, y1 = nodes[n1]; x2, y2 = nodes[n2]; x3, y3 = nodes[n3]
                cx_e = (x1 + x2 + x3) / 3; cy_e = (y1 + y2 + y3) / 3
                d = (cx_e - cx) ** 2 + (cy_e - cy) ** 2
                if d < best_dist:
                    best_dist = d; best_eid = eid
        if best_eid is None:
            return
        idx_arr = np.where(self._elem_stress_keys == best_eid)[0]
        if len(idx_arr) == 0:
            QMessageBox.information(self, "No Data",
                f"No stress history recorded for element {best_eid}.")
            return
        history = self._elem_stress_vals[idx_arr[0]]  # shape (n_steps, 3)
        dlg = BodyElementDialog(best_eid, history, parent=self)
        dlg.exec_()

    def _save(self):
        p, _ = QFileDialog.getSaveFileName(self, "Save", "result.png", "PNG (*.png);;PDF (*.pdf)")
        if p: self.fig.savefig(p, dpi=150, bbox_inches="tight", facecolor=self.fig.get_facecolor())

    def _csv(self):
        
        if self._disp.size == 0: return
        p, _ = QFileDialog.getSaveFileName(self, "Export CSV", "results.csv", "CSV (*.csv)")
        if not p: return
        n = len(self._disp)
        cols = [np.arange(1, n + 1), self._disp, self._force]
        hdrs = ["Step", "Disp_m", "Force_kN"]
        for i, a in enumerate(self._co):
            pad = np.zeros(n); pad[:len(a)] = a; cols.append(pad); hdrs.append(f"Crack{i+1}_Open_m")
        for i, a in enumerate(self._cs):
            pad = np.zeros(n); pad[:len(a)] = a; cols.append(pad); hdrs.append(f"Crack{i+1}_Slip_m")
        np.savetxt(p, np.column_stack(cols), delimiter=",",
                   header=",".join(hdrs), comments="")



# script export tab — generate a standalone runner script

class ScriptTab(QWidget):
    def __init__(self):
        """
        Set up widget state, defaults, and signal wiring for this section.
        """
        super().__init__()
        outer = QVBoxLayout(self); outer.setContentsMargins(16, 16, 16, 16); outer.setSpacing(8)
        outer.addWidget(mk_lbl("Standalone OpenSeesPy Script", "heading"))
        outer.addWidget(mk_lbl(
            "Export a self-contained script that can be run anywhere OpenSeesPy is installed.", "sub"))
        brow = QHBoxLayout()
        self.btn_gen  = QPushButton("Generate / Refresh Script"); self.btn_gen.setObjectName("amber")
        self.btn_copy = QPushButton("Copy to Clipboard");         self.btn_copy.setObjectName("flat")
        self.btn_save = QPushButton("Save .py …");                self.btn_save.setObjectName("flat")
        for b in [self.btn_gen, self.btn_copy, self.btn_save]: brow.addWidget(b)
        brow.addStretch()
        outer.addLayout(brow)
        self.lbl_hint = mk_lbl("Script not yet generated. Click Generate or Run Analysis.", "sub")
        outer.addWidget(self.lbl_hint)
        self.editor = QTextEdit(); self.editor.setFont(QFont("Cascadia Code", 10))
        outer.addWidget(self.editor, stretch=1)
        self.btn_copy.clicked.connect(
            lambda: QApplication.clipboard().setText(self.editor.toPlainText()))
        self.btn_save.clicked.connect(self._save)

    def set_script(self, s):
        self.editor.setPlainText(s)
        self.lbl_hint.setText("Script ready — Copy or Save .py to export.")
        self.lbl_hint.setStyleSheet(f"color:{C2};font-size:12px;")

    def _save(self):
        p, _ = QFileDialog.getSaveFileName(self, "Save", "panel_analysis.py", "Python (*.py)")
        if p: Path(p).write_text(self.editor.toPlainText(), encoding="utf-8")




# OpenSeesPy runner (RUNNER_PY string) — subprocess script body

RUNNER_PY = r'''
import sys, json, traceback, math, os, time as _time
import numpy as np

_LOG_LINES = []

def _log(msg):
    _LOG_LINES.append(msg)
    print(msg)


# quick probe: check if this OpenSees build even knows MultiSurfCrack2D
def _check_multisurfcrack2d(ops):
    """Return True if MultiSurfCrack2D nDMaterial is available in this build."""
    try:
        ops.wipe()
        ops.model('basic', '-ndm', 2, '-ndf', 2)
        ops.node(99990, 0.0, 0.0)
        ops.node(99991, 0.0, 0.0)
        ops.nDMaterial('MultiSurfCrack2D', 99990,
                       210.0, 5.95, 0.0, 0.0,
                       210.0, 5.95, 0.0, 0.0,
                       30.0, 25.0, 5.0, 1.0,
                       0.5, 0.3, 0.5, 0.7,
                       0.5, 0.3, 1.0, 0.785, 0.01,
                       0)
        ops.wipe()
        return True
    except Exception:
        ops.wipe()
        return False


def _check_multisurf_2d_link_compat(ops):
    """
    Return True if this build can create a 2D (ndf=2) zeroLengthND link
    with MultiSurfCrack2D. This is the exact compatibility needed by tri31.
    """
    try:
        ops.wipe()
        ops.model('basic', '-ndm', 2, '-ndf', 2)
        ops.node(99980, 0.0, 0.0)
        ops.node(99981, 0.0, 0.0)
        ops.nDMaterial('MultiSurfCrack2D', 99980,
                       210.0, 5.95, 0.0, 0.0,
                       210.0, 5.95, 0.0, 0.0,
                       30.0, 25.0, 5.0, 1.0,
                       0.5, 0.3, 0.5, 0.7,
                       0.5, 0.3, 1.0, 0.785, 0.01,
                       0)
        ops.element('zeroLengthND', 99980, 99980, 99981, 99980)
        ops.wipe()
        return True
    except Exception:
        ops.wipe()
        return False


def _create_eppgap_macro(ops, ci, nb, na, kn, kt, gap, eta, elt_base,
                         tx=1.0, ty=0.0, nx_=0.0, ny_=1.0):
    """
    Fallback macro-element: 4 parallel shear springs (ElasticPPGap) +
    1 normal spring.  Provides nonzero initial stiffness in both directions.
    Returns list of element ids created.
    """
    base_mat = 50000 + ci * 10
    elt_ids = []

    # --- 4 tangential (shear) springs with staggered gaps ---
    spring_shares = [0.15, 0.20, 0.25, 0.40]
    gap_mults = [0.35, 0.75, 1.25, 1.80]
    yield_mults = [0.20, 0.45, 0.90, 1.50]
    base_gap = max(float(gap), 1e-6)
    for k in range(4):
        tag_t = base_mat + k
        frac_kt = kt * spring_shares[k]
        gap_k = base_gap * gap_mults[k]
        fy_k = max(frac_kt * base_gap * yield_mults[k], 1e-8)
        try:
            ops.uniaxialMaterial('ElasticPPGap', tag_t,
                                 frac_kt, fy_k, gap_k, eta)
        except Exception:
            ops.uniaxialMaterial('Elastic', tag_t, frac_kt)
        eid = elt_base + ci * 5 + k
        ops.element('zeroLength', eid, nb, na, '-mat', tag_t, '-dir', 1,
                    '-orient', tx, ty, 0.0, nx_, ny_, 0.0)
        elt_ids.append(eid)

    # --- 1 normal spring ---
    tag_n = base_mat + 4
    ops.uniaxialMaterial('Elastic', tag_n, kn)
    eid_n = elt_base + ci * 5 + 4
    ops.element('zeroLength', eid_n, nb, na, '-mat', tag_n, '-dir', 2,
                '-orient', tx, ty, 0.0, nx_, ny_, 0.0)
    elt_ids.append(eid_n)
    return elt_ids



def _compute_tributary_lengths(crack_pairs, panel_W):
    by_y = {}
    for cp in crack_pairs:
        by_y.setdefault(round(float(cp[2]), 8), []).append(cp)
    tributary = {}
    for _, cps in by_y.items():
        cps = sorted(cps, key=lambda cp: float(cp[3]))
        if len(cps) == 1:
            tributary[(int(cps[0][0]), int(cps[0][1]))] = float(panel_W)
            continue
        xs = [float(cp[3]) for cp in cps]
        for idx, cp in enumerate(cps):
            if idx == 0:
                trib = 0.5 * (xs[1] - xs[0])
            elif idx == len(cps) - 1:
                trib = 0.5 * (xs[-1] - xs[-2])
            else:
                trib = 0.5 * (xs[idx + 1] - xs[idx - 1])
            tributary[(int(cp[0]), int(cp[1]))] = max(trib, 1e-9)
    return tributary


# basic guardrails so we fail early with a useful message
def _sanity_checks(p, mesh_nodes, mesh_tris, bc_nodes, load_nodes):
    warnings = []
    auto_fixes = {}
    if not mesh_tris:
        warnings.append("sanity fail: no triangular elements")
    if not bc_nodes:
        warnings.append("sanity fail: no boundary conditions assigned")
    if not load_nodes:
        warnings.append("sanity fail: no loads applied")
    n_fix_ux = sum(1 for v in bc_nodes.values() if int(v[0]) == 1)
    n_fix_uy = sum(1 for v in bc_nodes.values() if int(v[1]) == 1)
    if n_fix_ux == 0:
        warnings.append("sanity warn: no Ux restraints; rigid-body drift is possible")
    if n_fix_uy == 0:
        warnings.append("sanity warn: no Uy restraints; rigid-body drift is possible")
    ok = len([w for w in warnings if 'FAIL' in w]) == 0
    for w in warnings:
        _log(w)
    return ok, warnings, auto_fixes


# clean up crack links before model assembly
def _sanitize_crack_pairs(crack_pairs, panel_H, tol_frac=0.01):
    """
    Deduplicate cracks by Y with tolerance, skip self-links, duplicate links,
    and tiny links. Returns cleaned list + logs.
    """
    tol = tol_frac * panel_H
    requested = len(crack_pairs)

    # Deduplicate by Y with tolerance
    seen_ys = []
    y_map = {}  # old_y -> canonical_y
    for cp in crack_pairs:
        yc = float(cp[2])
        matched = False
        for sy in seen_ys:
            if abs(yc - sy) < tol:
                y_map[yc] = sy
                matched = True
                break
        if not matched:
            seen_ys.append(yc)
            y_map[yc] = yc

    # Filter links
    cleaned = []
    seen_pairs = set()
    for cp in crack_pairs:
        nb = int(cp[0]); na = int(cp[1])
        yc = float(cp[2])

        # Skip self-links
        if nb == na:
            _log(f"skip crack link: same node on both sides ({nb})")
            continue

        # Skip duplicate node-pair links
        pair_key = (min(nb, na), max(nb, na))
        if pair_key in seen_pairs:
            _log(f"skip duplicate crack link: {nb}-{na}")
            continue
        seen_pairs.add(pair_key)

        # Skip tiny links (nodes at same position with zero-length crack)
        # This is only a sanity filter — zeroLength elements are fine
        cleaned.append(cp)

    unique = len(cleaned)
    _log(f"sanitized {requested} -> {unique} unique crack pairs (tol={tol:.4f} m)")
    return cleaned


# analysis setup and fallback strategy for touchy nonlinear steps
def _build_analysis(ops, p, at, ln, dof, incr, alg,
                    sys_type='UmfPack', constr_type='Plain',
                    test_type='NormDispIncr', test_tol=None, test_iter=None):
    ops.wipeAnalysis()
    try:
        ops.constraints(constr_type)
    except Exception:
        ops.constraints('Transformation')
    try:
        ops.numberer(p.get('numberer', 'RCM'))
    except Exception:
        ops.numberer('RCM')
    try:
        ops.system(sys_type)
    except Exception:
        ops.system('BandGeneral')
    tol_ = float(test_tol if test_tol is not None else p.get('tol', 1e-8))
    itr_ = int(test_iter if test_iter is not None else p.get('max_iter', 400))
    ops.test(test_type, tol_, itr_)
    if alg == 'NewtonLineSearch':
        try:    ops.algorithm('NewtonLineSearch', '-type', 'Bisection')
        except: ops.algorithm('Newton')
    elif alg == 'KrylovNewton':   ops.algorithm('KrylovNewton')
    elif alg == 'ModifiedNewton': ops.algorithm('ModifiedNewton')
    else:                         ops.algorithm('Newton')
    if at == 'LoadControl':
        ops.integrator('LoadControl', float(incr))
    else:
        ops.integrator('DisplacementControl', int(ln), int(dof), float(incr))
    ops.analysis('Static')


def _step_with_recovery(ops, p, at, ln, dof, incr, step_num=0):
    base_tol = float(p.get('tol', 1e-8))
    base_iter = int(p.get('max_iter', 400))
    combos = [
        ('KrylovNewton',  'UmfPack',     'Plain',          'NormDispIncr', 1.0,   1.0),
        ('NewtonLineSearch','UmfPack',   'Plain',          'NormDispIncr', 10.0,  2.0),
        ('ModifiedNewton','BandGeneral', 'Transformation', 'NormUnbalance', 10.0,  2.0),
        ('Newton',        'BandGeneral', 'Transformation', 'NormUnbalance', 100.0, 3.0),
    ]
    for alg, sys_t, constr, test_type, tol_mult, iter_mult in combos:
        t_tol = base_tol * tol_mult
        t_iter = int(base_iter * iter_mult)
        _log(f"  trying: {alg} / {sys_t} / {constr}")
        try:
            _build_analysis(ops, p, at, ln, dof, incr, alg, sys_t, constr, test_type, t_tol, t_iter)
            if ops.analyze(1) == 0:
                return 0, alg, sys_t, constr
        except Exception:
            pass
    _log(f"step {step_num}: recovery options exhausted")
    return -1, 'Newton', 'BandGeneral', 'Transformation'


def _step_normal(ops, p, at, ln, dof, incr, sys_type, constr_type):
    """Normal step with algorithm fallback only (fast path)."""
    for alg in ['KrylovNewton', 'NewtonLineSearch', 'ModifiedNewton', 'Newton']:
        _build_analysis(ops, p, at, ln, dof, incr, alg, sys_type, constr_type)
        if ops.analyze(1) == 0:
            return 0, alg
    return -1, 'Newton'


def _cutback(ops, p, at, ln, dof, incr, max_cuts=12,
             sys_type='UmfPack', constr_type='Plain'):
    cur = float(incr)
    for _ in range(max_cuts + 1):
        ok, alg = _step_normal(ops, p, at, ln, dof, cur, sys_type, constr_type)
        if ok == 0:
            return 0, cur, alg
        cur *= 0.5
    return -1, cur, 'Newton'


def _build_loading_targets(p):
    protocol = str(p.get('loading_protocol', 'monotonic')).lower()
    if protocol != 'reversed-cyclic':
        return []
    custom_cycles = p.get('custom_cycles', []) or []
    if custom_cycles:
        targets = []
        for row in custom_cycles:
            try:
                amp = float(row.get('amplitude', 0.0))
                half_steps = max(int(row.get('half_cycle_steps', p.get('steps_per_half_cycle', 10))), 1)
            except Exception:
                continue
            for target in [amp, -amp, 0.0]:
                targets.append((float(target), half_steps))
        return targets
    cycle_count = max(int(p.get('cycle_count', 3)), 1)
    base_amp = float(p.get('cycle_amplitude', p.get('target_disp', 0.005)))
    amp_scale = max(float(p.get('cycle_amplitude_scale', 1.0)), 1e-9)
    amps = [base_amp * (amp_scale ** idx) for idx in range(cycle_count)]
    targets = []
    for amp in amps:
        half_steps = max(int(p.get('steps_per_half_cycle', 10)), 1)
        for target in [float(amp), -float(amp), 0.0]:
            targets.append((target, half_steps))
    return targets


# full analysis flow used by the GUI subprocess
def run_model_2d(p):
    import openseespy.opensees as ops

    disp_l = []; force_l = []; open_l = []; slip_l = []
    status = "failed"; msg = "failed"
    node_disp_last = {}
    cpos = []
    nc_y = 0        # safe default — overwritten after crack_y_set is built
    pair_meta = []  # safe default — overwritten after crack loop
    auto_fixes = {} # safe default — overwritten by _sanity_checks

    try:
        # probe material availability before committing to full model build
        mscrack_available = _check_multisurfcrack2d(ops)
        mscrack_2d_usable = _check_multisurf_2d_link_compat(ops) if mscrack_available else False
        if mscrack_available:
            _log("material check: MultiSurfCrack2D is available")
            if mscrack_2d_usable:
                _log("material check: MultiSurfCrack2D works with 2D zeroLengthND")
            else:
                _log("material check: MultiSurfCrack2D exists but 2D zeroLengthND failed")
        else:
            _log("material check: MultiSurfCrack2D not available; EPPGap fallback will be used")

        # params arrive as a flat dict from the GUI
        mesh_nodes_raw = p.get('mesh_nodes', {})
        mesh_tris_raw  = p.get('mesh_tris', [])
        bc_nodes_raw   = p.get('bc_nodes', {})
        load_nodes_raw = p.get('load_nodes', {})

        if not mesh_tris_raw:
            raise RuntimeError("[PRECHECK FAIL] No triangular elements (mesh_tris is empty)")
        if not bc_nodes_raw:
            raise RuntimeError("[PRECHECK FAIL] No boundary conditions (bc_nodes is empty)")
        if not load_nodes_raw:
            raise RuntimeError("[PRECHECK FAIL] No loads applied (load_nodes is empty)")

        _log(f"precheck ok: {len(mesh_nodes_raw)} nodes, {len(mesh_tris_raw)} elements,"
             f" {len(bc_nodes_raw)} BC nodes, {len(load_nodes_raw)} load nodes")

        # quick sanity pass before we allocate model objects
        san_ok, san_warns, auto_fixes = _sanity_checks(
            p, mesh_nodes_raw, mesh_tris_raw, bc_nodes_raw, load_nodes_raw)

        # hard-stop issues
        fatal = [w for w in san_warns if 'FAIL' in w]
        if fatal:
            raise RuntimeError("Sanity checks failed:\n" + "\n".join(fatal))

        # normalize crack links (duplicates, self-links, tolerance)
        crack_pairs_raw = p.get('mesh_crack_pairs', [])
        W = float(p['panel_W']); H = float(p['panel_H'])
        crack_pairs = _sanitize_crack_pairs(crack_pairs_raw, H)

        # build OpenSees model objects (units: m, kN, MPa)
        ops.wipe()
        ops.model('basic', '-ndm', 2, '-ndf', 2)

        t  = float(p.get('panel_t', 0.2))
        Ec = float(p.get('panel_Ec', 30000.))
        nu = float(p.get('panel_nu', 0.2))

        ops.nDMaterial('ElasticIsotropic', 1, Ec, nu)

        mesh_nodes = p['mesh_nodes']
        for nid_str, (x, y) in mesh_nodes.items():
            ops.node(int(nid_str), float(x), float(y))

        bc_nodes = p.get('bc_nodes', {})
        for nid_str in mesh_nodes:
            nid = int(nid_str)
            if nid_str in bc_nodes:
                fx, fy = bc_nodes[nid_str]
                ops.fix(nid, int(fx), int(fy))
            else:
                pass  # ndf=2: no rotational DOF to constrain

        mesh_tris = p['mesh_tris']
        for e, n1, n2, n3 in mesh_tris:
            try:
                ops.element('tri31', int(e), int(n1), int(n2), int(n3), t, 'PlaneStress', 1)
            except Exception:
                try:
                    ops.element('Tri31', int(e), int(n1), int(n2), int(n3), t, 'PlaneStress', 1)
                except Exception:
                    ops.element('tri31', int(e), int(n1), int(n2), int(n3), t, 'PlaneStress', 1)

        # add interface elements for each crack pair
        crack_mat_data = p.get('crack_mat_data', [])
        _log("─" * 50)
        _log(f"creating {len(crack_pairs)} crack interface elements...")
        _log("─" * 50)

        # one compatibility summary is enough
        if mscrack_available and mscrack_2d_usable:
            _log("material mode: using MultiSurfCrack2D zeroLengthND links")
        elif mscrack_available and not mscrack_2d_usable:
            _log("material mode: MultiSurfCrack2D exists but this build can't use it in 2D links")
            _log("material mode: falling back to EPPGap macro elements")
        else:
            _log("material mode: MultiSurfCrack2D not available in this build")
            _log("material mode: falling back to EPPGap macro elements")

        def _find_mat(cp, idx):
            default = {
                'mat_type': 'Elastic', 'kn': 210., 'kt': 5.95, 'gap': 0.001, 'eta': 0.02,
                'width': 0.001, 'orientation_deg': 0.0,
                'below_node': int(cp[0]), 'above_node': int(cp[1]),
                'x': float(cp[3]), 'y': float(cp[2]),
            }
            if not crack_mat_data:
                return default
            for cm in crack_mat_data:
                if (int(cm.get('below_node', -1)) == int(cp[0]) and
                        int(cm.get('above_node', -1)) == int(cp[1])):
                    merged = dict(default)
                    merged.update(cm)
                    return merged
            if idx < len(crack_mat_data):
                merged = dict(default)
                merged.update(crack_mat_data[idx])
                return merged
            closest = min(crack_mat_data, key=lambda cm: abs(float(cm.get('y', 0.0)) - float(cp[2])))
            merged = dict(default)
            merged.update(closest)
            return merged

        elt_base = len(mesh_tris) + 1
        # each fallback macro uses 5 zeroLength elements
        elt_base_macro = elt_base + len(crack_pairs) + 100
        tributary_lengths = _compute_tributary_lengths(crack_pairs, W)
        pair_meta = []

        crack_y_set = sorted(set(float(cp[2]) for cp in crack_pairs))
        cpos = crack_y_set

        n_mscrack_ok = 0
        n_fallback = 0

        for ci, cp in enumerate(crack_pairs):
            nb = int(cp[0]); na = int(cp[1]); yc = float(cp[2])
            if len(cp) >= 8:
                c_tx, c_ty = float(cp[4]), float(cp[5])
                c_nx, c_ny = float(cp[6]), float(cp[7])
            else:
                c_tx, c_ty = 1.0, 0.0
                c_nx, c_ny = 0.0, 1.0

            cm = _find_mat(cp, ci)
            mat_type = str(cm.get('mat_type', 'MultiSurfCrack2D'))
            mat_id = 10000 + ci
            kn = max(float(cm.get('kn', 210.0)), 1e-6)
            kt = max(float(cm.get('kt', 5.95)), 1e-6)
            gap = float(cm.get('gap', 0.001))
            eta = float(cm.get('eta', 0.02))
            width = float(cm.get('width', gap))
            orientation_deg = float(cm.get('orientation_deg', math.degrees(math.atan2(c_ty, c_tx))))
            c_tx, c_ty, c_nx, c_ny = math.cos(math.radians(orientation_deg)), math.sin(math.radians(orientation_deg)), -math.sin(math.radians(orientation_deg)), math.cos(math.radians(orientation_deg))

            use_mscrack = ('multisurfcrack2d' in mat_type.lower() or 'multi' in mat_type.lower())
            use_macro = 'macro' in mat_type.lower()

            if use_mscrack:
                if mscrack_available and mscrack_2d_usable:
                    try:
                        # preferred path: actual MultiSurfCrack2D + zeroLengthND
                        msc_E = float(cm.get('msc_E', 210.0))
                        msc_H = float(cm.get('msc_H', 5.95))
                        msc_M = float(cm.get('msc_M', 0.0))
                        msc_K = float(cm.get('msc_K', 0.0))
                        msc_Eunl = float(cm.get('msc_Eunl', 210.0))
                        msc_Hunl = float(cm.get('msc_Hunl', 5.95))
                        msc_Munl = float(cm.get('msc_Munl', 0.0))
                        msc_Kunl = float(cm.get('msc_Kunl', 0.0))
                        msc_fc = float(cm.get('msc_fc', 30.0))
                        msc_ag = float(cm.get('msc_ag', 25.0))
                        msc_fcl = float(cm.get('msc_fcl', 5.0))
                        msc_Acr = float(cm.get('msc_Acr', 1.0))
                        msc_rho_lok = float(cm.get('msc_rho_lok', 0.5))
                        msc_chi_lok = float(cm.get('msc_chi_lok', 0.3))
                        msc_rho_act = float(cm.get('msc_rho_act', 0.5))
                        msc_mu = float(cm.get('msc_mu', 0.7))
                        msc_chi_act = float(cm.get('msc_chi_act', 0.5))
                        msc_zeta = float(cm.get('msc_zeta', 0.3))
                        msc_kappa = float(cm.get('msc_kappa', 1.0))
                        msc_theta = float(cm.get('msc_theta', 0.785))
                        msc_w = float(cm.get('msc_w', 0.01))
                        msc_cPath = int(cm.get('msc_cPath', 0))

                        _log(f"MSC2D crack {ci}: fc={msc_fc} MPa ag={msc_ag} mm "
                             f"rho_lok={msc_rho_lok} mu={msc_mu} kappa={msc_kappa}")

                        ops.nDMaterial('MultiSurfCrack2D', mat_id,
                                       msc_E, msc_H, msc_M, msc_K,
                                       msc_Eunl, msc_Hunl, msc_Munl, msc_Kunl,
                                       msc_fc, msc_ag, msc_fcl, msc_Acr,
                                       msc_rho_lok, msc_chi_lok,
                                       msc_rho_act, msc_mu, msc_chi_act,
                                       msc_zeta, msc_kappa, msc_theta, msc_w,
                                       msc_cPath)
                        elt_id = elt_base + ci
                        ops.element('zeroLengthND', elt_id, nb, na, mat_id,
                                    '-orient', c_nx, c_ny, 0.0, c_tx, c_ty, 0.0)
                        n_mscrack_ok += 1
                        pair_meta.append(dict(
                            element_index=ci + 1, below_node=nb, above_node=na,
                            element_id=elt_id,
                            x=float(cp[3]), y=yc, width=width, orientation_deg=orientation_deg,
                            mat_type=mat_type, kn=kn, kt=kt, gap=gap, eta=eta,
                            tx=c_tx, ty=c_ty, nx=c_nx, ny=c_ny,
                            tributary_length=tributary_lengths.get((nb, na), 1e-9),
                            area=max(tributary_lengths.get((nb, na), 1e-9) * t, 1e-9),
                            openings=[], slips=[], shear_forces=[], normal_stresses=[],
                        ))
                        continue
                    except Exception as e_ms:
                        _log(f"MSC2D link failed at crack {ci} (y={yc:.6f} m); using fallback: {e_ms}")

                _create_eppgap_macro(ops, ci, nb, na, kn, kt, gap, eta, elt_base_macro,
                                     c_tx, c_ty, c_nx, c_ny)
                n_fallback += 1
                elt_id = elt_base_macro + ci * 5
            elif use_macro:
                _create_eppgap_macro(ops, ci, nb, na, kn, kt, gap, eta, elt_base_macro,
                                     c_tx, c_ty, c_nx, c_ny)
                elt_id = elt_base_macro + ci * 5
            else:
                # plain material path when no macro/multisurface behavior is requested
                mat_t = mat_id * 2
                mat_n = mat_id * 2 + 1

                if ('simplespring' in mat_type.lower().replace(' ', '')) or ('calvi2015' in mat_type.lower().replace(' ', '')):
                    sp_Kn = float(cm.get('sp_Kn', cm.get('kn', 500.0)))
                    sp_Ks = float(cm.get('sp_Ks', cm.get('kt', 200.0)))
                    sp_gap = float(cm.get('sp_gap', 0.0))
                    try:
                        ops.uniaxialMaterial('ElasticPPGap', mat_n, sp_Kn, sp_Kn * 1e6, sp_gap, 0.0, 'damage')
                    except Exception:
                        ops.uniaxialMaterial('Elastic', mat_n, sp_Kn)
                    ops.uniaxialMaterial('Elastic', mat_t, sp_Ks)
                    _log(f"  [MAT] Calvi2015 (EPP-normal / Elastic-shear) crack {ci}: Kn={sp_Kn}, Ks={sp_Ks}, gap={sp_gap}")
                elif 'eppgap' in mat_type.lower() or 'elasticppgap' in mat_type.lower():
                    ops.uniaxialMaterial('ElasticPPGap', mat_t, kt, kt * 5., gap, eta)
                    ops.uniaxialMaterial('ElasticPPGap', mat_n, kn, kn * 10., 0.0, eta)
                elif 'bilinear' in mat_type.lower() or 'custom' in mat_type.lower():
                    ops.uniaxialMaterial('Steel01', mat_t, kt * gap, kt, eta)
                    ops.uniaxialMaterial('Steel01', mat_n, kn * gap, kn, eta)
                else:
                    ops.uniaxialMaterial('Elastic', mat_t, kt)
                    ops.uniaxialMaterial('Elastic', mat_n, kn)

                elt_id = elt_base + ci
                ops.element('zeroLength', elt_id, nb, na, '-mat', mat_t, mat_n, '-dir', 1, 2,
                            '-orient', c_tx, c_ty, 0.0, c_nx, c_ny, 0.0)

            pair_meta.append(dict(
                element_index=ci + 1, below_node=nb, above_node=na,
                element_id=elt_id,
                x=float(cp[3]), y=yc, width=width, orientation_deg=orientation_deg,
                mat_type=mat_type, kn=kn, kt=kt, gap=gap, eta=eta,
                tx=c_tx, ty=c_ty, nx=c_nx, ny=c_ny,
                tributary_length=tributary_lengths.get((nb, na), 1e-9),
                area=max(tributary_lengths.get((nb, na), 1e-9) * t, 1e-9),
                openings=[], slips=[], shear_forces=[], normal_stresses=[],
            ))

            _log(f"crack elements ready: {n_mscrack_ok} MSC2D, {n_fallback} EPPGap fallback, "
                 f"{len(crack_pairs) - n_mscrack_ok - n_fallback} standard")

        # add reinforcement truss elements crossing selected crack rows
        rebar_definitions = list(p.get('rebar_definitions', []))
        elt_base_rebar = elt_base_macro + 500
        rebar_mat_base = 90000
        # ── ID collision guards ──
        max_macro_elt = elt_base_macro + len(crack_pairs) * 5
        if max_macro_elt >= elt_base_rebar:
            elt_base_rebar = max_macro_elt + 100
            _log(f"WARNING: rebar element base adjusted to {elt_base_rebar} to avoid collision with macro crack elements")
        _log(f"Rebar element IDs: {elt_base_rebar} to {elt_base_rebar + len(rebar_definitions)}")
        max_crack_mat = 10000 + len(crack_pairs) * 2 + 1
        if max_crack_mat >= rebar_mat_base:
            rebar_mat_base = max_crack_mat + 1000
            _log(f"WARNING: rebar material base adjusted to {rebar_mat_base} to avoid collision with crack material IDs")
        _log(f"Rebar material IDs: {rebar_mat_base} to {rebar_mat_base + len(rebar_definitions)}")
        if rebar_definitions:
            crack_pairs_by_y = {}
            for cp in crack_pairs:
                y_key = round(float(cp[2]), 8)
                crack_pairs_by_y.setdefault(y_key, []).append(cp)
            for y_key, cps in crack_pairs_by_y.items():
                crack_pairs_by_y[y_key] = sorted(cps, key=lambda it: float(it[3]))

            uniform_groups = {}
            for ridx, rb in enumerate(rebar_definitions):
                try:
                    ry = round(float(rb.get('crack_y', 0.0)), 8)
                except Exception:
                    continue
                if rb.get('x', None) is None:
                    uniform_groups.setdefault(ry, []).append(ridx)

            uniform_targets = {}
            for ry, idxs in uniform_groups.items():
                cps = crack_pairs_by_y.get(ry, [])
                if not cps:
                    continue
                x_vals = [float(cp[3]) for cp in cps]
                x_min = min(x_vals)
                x_max = max(x_vals)
                span = max(x_max - x_min, 0.0)
                n_uniform = len(idxs)
                for j, ridx in enumerate(idxs, start=1):
                    if span <= 1e-12:
                        uniform_targets[ridx] = x_min
                    else:
                        uniform_targets[ridx] = x_min + span * (j / (n_uniform + 1.0))

            n_rebar_created = 0
            for ridx, rb in enumerate(rebar_definitions):
                try:
                    crack_y = round(float(rb.get('crack_y', 0.0)), 8)
                    As = max(float(rb.get('As', 0.0)), 1e-12)
                    Es = max(float(rb.get('Es', 200000.0)), 1e-9)
                    fy = max(float(rb.get('fy', 500.0)), 1e-9)
                    L_unb = float(rb.get('L_unb', 0.0))
                    x_raw = rb.get('x', None)
                    x_target = uniform_targets.get(ridx, None if x_raw is None else float(x_raw))
                except Exception as e_rb:
                    _log(f"rebar skipped #{ridx + 1}: invalid definition ({e_rb})")
                    continue

                cps = crack_pairs_by_y.get(crack_y, [])
                if not cps:
                    _log(f"rebar skipped #{ridx + 1}: no crack pairs found at y={crack_y:.6f}")
                    continue

                if x_target is None:
                    cp_sel = cps[len(cps) // 2]
                else:
                    cp_sel = min(cps, key=lambda it: abs(float(it[3]) - float(x_target)))

                nb = int(cp_sel[0])
                na = int(cp_sel[1])
                x_sel = float(cp_sel[3])

                if L_unb <= 0.0:
                    _log(
                        f"WARNING: rebar at crack_y={crack_y:.6f} x={x_sel:.6f} skipped — L_unb must be > 0"
                    )
                    continue

                As_m2 = As * 1e-6
                Es_kNm2 = Es * 1000.0
                fy_kNm2 = fy * 1000.0
                k_eff = Es_kNm2 * As_m2 / L_unb
                Fy_kN = fy_kNm2 * As_m2

                rebar_mat_id = rebar_mat_base + ridx
                rebar_elt_id = elt_base_rebar + ridx

                ops.uniaxialMaterial('Steel01', rebar_mat_id, Fy_kN, k_eff, 0.01)
                ops.element('Truss', rebar_elt_id, nb, na, 1.0, rebar_mat_id)
                n_rebar_created += 1
                _log(
                    f"Rebar truss elt={rebar_elt_id} crack_y={crack_y:.6f} x={x_sel:.6f} "
                    f"As={As:.3f}mm2 Es={Es:.3f}MPa fy={fy:.3f}MPa L_unb={L_unb:.4f}m "
                    f"k_eff={k_eff:.1f}kN/m"
                )

            _log(f"rebar truss elements created: {n_rebar_created}/{len(rebar_definitions)}")

        # apply nodal loads
        load_nodes = p.get('load_nodes', {})
        if not load_nodes:
            raise RuntimeError("No loads applied. Assign loads on the Geometry tab.")

        ops.timeSeries('Linear', 1)
        ops.pattern('Plain', 1, 1)
        for nid_str, (Fx, Fy) in load_nodes.items():
            ops.load(int(nid_str), float(Fx), float(Fy))

        # don't call loadConst('-time', 0.0) here
        # it resets reference load and can break DisplacementControl at step 0.

        fixed_nids = [int(k) for k in bc_nodes.keys()]

        # pick a stable reference DOF for control integrators
        at = p.get('analysis_type', 'DisplacementControl')
        ref_nid = auto_fixes.get('ref_node', None)
        ref_dof = auto_fixes.get('ref_dof', None)
        at_auto_switched = False

        if at == 'DisplacementControl':
            if ref_nid is None:
                for nid_str, (Fx, Fy) in load_nodes.items():
                    candidate = int(nid_str)
                    bc_v = bc_nodes.get(nid_str, [0, 0])
                    dof_cand = 2 if abs(Fy) > abs(Fx) else 1
                    if int(bc_v[dof_cand - 1]) != 1:
                        ref_nid = candidate; ref_dof = dof_cand
                        break
            if ref_nid is None:
                _log("control mode: no loaded free DOF found, switching to LoadControl")
                at = 'LoadControl'; at_auto_switched = True
            else:
                _log(f"control mode: DisplacementControl on node {ref_nid} dof {ref_dof}")

        if p.get('ref_node', 0) > 0:
            ref_nid = int(p['ref_node'])
            ref_dof_mode = str(p.get('ref_dof_mode', 'Auto'))
            if ref_dof_mode == 'DOF 1 (X)':
                ref_dof = 1
            elif ref_dof_mode == 'DOF 2 (Y)':
                ref_dof = 2
            _log(f"[CONTROL] user-specified ref_nid={ref_nid} ref_dof={ref_dof}")

        if at == 'LoadControl':
            for nid_str, (Fx, Fy) in load_nodes.items():
                ref_nid = int(nid_str)
                ref_dof = 2 if abs(Fy) > abs(Fx) else 1
                break
            _log(f"control mode: {'auto-switched ' if at_auto_switched else ''}"
                 f"ref_nid={ref_nid}  ref_dof={ref_dof}  analysis=LoadControl")

        ml   = float(p.get('max_load_factor', 50.))
        nc_y = len(crack_y_set)
        open_l = [[] for _ in range(nc_y)]
        slip_l = [[] for _ in range(nc_y)]
        elem_stress_history = {}  # {eid: [(sxx, syy, sxy), ...]}

        active_sys = p.get('solver_system', 'UmfPack')
        active_constr = p.get('constraint_handler', 'Plain')
        protocol = str(p.get('loading_protocol', 'monotonic')).lower()
        cycle_targets = _build_loading_targets(p)

        def collect():
            disp_l.append(ops.nodeDisp(ref_nid, ref_dof))
            ops.reactions()
            tot_f = 0.
            for fnid in fixed_nids:
                try: tot_f += abs(ops.nodeReaction(fnid, ref_dof))
                except: pass
            force_l.append(tot_f)
            for yi, yv in enumerate(crack_y_set):
                dw_sum = ds_sum = cnt = 0
                for meta in pair_meta:
                    if abs(meta['y'] - yv) < 1e-6:
                        try:
                            dux = ops.nodeDisp(meta['above_node'], 1) - ops.nodeDisp(meta['below_node'], 1)
                            duy = ops.nodeDisp(meta['above_node'], 2) - ops.nodeDisp(meta['below_node'], 2)
                            opening = dux * meta['nx'] + duy * meta['ny']
                            slip = dux * meta['tx'] + duy * meta['ty']
                            try:
                                forces = ops.eleForce(meta['element_id'])
                                shear_force = forces[0] if forces else 0.0
                                normal_force = forces[1] if len(forces) > 1 else 0.0
                            except Exception:
                                shear_force = 0.0
                                normal_force = 0.0
                            normal_stress = normal_force / max(meta['area'], 1e-9) / 1000.0
                            meta['openings'].append(opening)
                            meta['slips'].append(slip)
                            meta['shear_forces'].append(shear_force)
                            meta['normal_stresses'].append(normal_stress)
                            dw_sum += opening
                            ds_sum += slip
                            cnt += 1
                        except: pass
                open_l[yi].append(dw_sum / max(cnt, 1))
                slip_l[yi].append(ds_sum / max(cnt, 1))
            # Collect body element stress at each converged step
            for tri_row in mesh_tris:
                eid = int(tri_row[0])
                try:
                    s = ops.eleResponse(eid, 'stress')
                    if s and len(s) >= 3:
                        elem_stress_history.setdefault(eid, []).append((s[0], s[1], s[2]))
                except Exception:
                    pass

        failed = False; fm = ""

        if at == 'LoadControl':
            base_incr = float(p.get('load_incr', 0.01))
        else:
            base_incr = float(p.get('disp_incr', 0.0005))

        if protocol == 'reversed-cyclic' and cycle_targets:
            collect()
            _log(f"cyclic protocol: {len(cycle_targets)} targets")
            st = 0
            for target, cycle_half_steps in cycle_targets:
                if failed:
                    break
                try:
                    current = float(ops.getTime()) if at == 'LoadControl' else float(ops.nodeDisp(ref_nid, ref_dof))
                except Exception:
                    current = 0.0
                incr = (float(target) - current) / max(cycle_half_steps, 1)
                for _ in range(cycle_half_steps):
                    st += 1
                    try:
                        if abs(ops.getTime()) > ml:
                            failed = True; fm = 'load factor cap reached'; break
                    except Exception:
                        pass
                    ok, cur, alg = _cutback(ops, p, at, ref_nid, ref_dof, incr,
                                            sys_type=active_sys, constr_type=active_constr)
                    if ok == 0:
                        collect(); incr = cur
                    else:
                        ok2, alg2, s2, c2 = _step_with_recovery(
                            ops, p, at, ref_nid, ref_dof, incr, step_num=st)
                        if ok2 == 0:
                            collect(); active_sys = s2; active_constr = c2
                        else:
                            failed = True; fm = f'cycle step {st} alg={alg}'; break
        else:
            # step 0 is where singular models fail, so use full recovery
            ok0, alg0, active_sys, active_constr = _step_with_recovery(
                ops, p, at, ref_nid, ref_dof, base_incr, step_num=0)

            if ok0 == 0:
                collect()
                _log(f"step 0 converged with {alg0} / {active_sys} / {active_constr}")
            else:
                n_fixed_dofs = sum(int(v[0]) + int(v[1]) for v in bc_nodes.values())
                total_load = sum(abs(float(Fx)) + abs(float(Fy))
                                 for Fx, Fy in load_nodes.values())
                _log(f"step 0 failed: nodes={len(mesh_nodes)}, elems={len(mesh_tris)}, "
                     f"Fixed DOFs={n_fixed_dofs}, ref_nid={ref_nid}, ref_dof={ref_dof}, "
                     f"Total load={total_load:.4g}")
                raise RuntimeError(
                    f"Analysis failed at step 0.\n"
                    f"  Nodes={len(mesh_nodes)}, Elements={len(mesh_tris)}, "
                    f"Fixed DOFs={n_fixed_dofs}, ref_nid={ref_nid}, ref_dof={ref_dof}\n"
                    "  All solver/constraint/algorithm/test combos exhausted.\n"
                    "Possible causes: insufficient BCs, singular stiffness, bad mesh.")

            # main step loop with cutback + fallback
            if at == 'LoadControl':
                incr  = base_incr
                steps = max(0, int(1. / max(incr, 1e-12)) - 1)
                for st in range(steps):
                    ok, cur, alg = _cutback(ops, p, at, ref_nid, ref_dof, incr,
                                            sys_type=active_sys, constr_type=active_constr)
                    if ok == 0:
                        collect(); incr = min(incr, cur)
                    else:
                        ok2, alg2, s2, c2 = _step_with_recovery(
                            ops, p, at, ref_nid, ref_dof, incr, step_num=st+1)
                        if ok2 == 0:
                            collect(); active_sys = s2; active_constr = c2
                        else:
                            failed = True; fm = f"step {st + 1} alg={alg}"; break
            else:
                tgt   = float(p.get('target_disp', 0.05))
                incr  = base_incr
                steps = max(0, int(abs(tgt) / max(abs(incr), 1e-12)) - 1)
                for st in range(steps):
                    try:
                        if abs(ops.getTime()) > ml:
                            failed = True; fm = "load factor cap reached"; break
                    except: pass
                    ok, cur, alg = _cutback(ops, p, at, ref_nid, ref_dof, incr,
                                            sys_type=active_sys, constr_type=active_constr)
                    if ok == 0:
                        collect(); incr = min(incr, cur)
                    else:
                        ok2, alg2, s2, c2 = _step_with_recovery(
                            ops, p, at, ref_nid, ref_dof, incr, step_num=st+1)
                        if ok2 == 0:
                            collect(); active_sys = s2; active_constr = c2
                        else:
                            failed = True; fm = f"step {st + 1} alg={alg}"; break

        # snapshot final nodal displacement field for post-processing
        for nid_str in mesh_nodes:
            nid = int(nid_str)
            try:
                node_disp_last[nid] = [ops.nodeDisp(nid, 1), ops.nodeDisp(nid, 2)]
            except: pass

        status = ("ok" if not failed else "partial") if disp_l else "failed"
        msg = (f"{len(disp_l)} steps converged | {nc_y} crack line(s) | "
               f"panel {float(p['panel_W']):.2f}x{float(p['panel_H']):.2f} | {status}")
        if fm: msg += " | " + fm

    except Exception as e:
        tb_ = traceback.format_exc()
        status = "partial" if disp_l else "failed"
        msg = f"Exception: {e}\n{tb_}"
        print(msg, file=sys.stderr)

    a  = lambda x: np.array(x, dtype=float)
    la = lambda x: [a(v) for v in x] if x else []
    nids_arr = np.array(sorted(node_disp_last.keys()), dtype=int)
    disp_arr = (np.array([node_disp_last[n] for n in nids_arr], dtype=float)
                if len(nids_arr) else np.zeros((0, 2)))

    _log("─" * 50)
    _log(f"summary: status={status}")
    _log(f"summary: converged steps={len(disp_l)}")
    _log(f"summary: crack lines={nc_y}")
    if pair_meta:
        n_ms = sum(1 for m in pair_meta if 'multisurfcrack2d' in str(m.get('mat_type','')).lower())
        n_ep = sum(1 for m in pair_meta if 'macro' in str(m.get('mat_type','')).lower())
        n_el = len(pair_meta) - n_ms - n_ep
        _log(f"summary: crack elements={n_ms} MSC2D, {n_ep} EPPGap macro, {n_el} other")
    _log("─" * 50)

    # Serialize elem_stress_history for npz
    esh_keys = np.array(sorted(elem_stress_history.keys()), dtype=np.int32) if elem_stress_history else np.array([], dtype=np.int32)
    if len(esh_keys) > 0:
        max_steps = max(len(elem_stress_history[k]) for k in esh_keys)
        esh_vals = np.full((len(esh_keys), max_steps, 3), np.nan, dtype=np.float64)
        for i, k in enumerate(esh_keys):
            hist = elem_stress_history[k]
            for j, (sxx, syy, sxy) in enumerate(hist):
                esh_vals[i, j, :] = [sxx, syy, sxy]
    else:
        esh_vals = np.zeros((0, 0, 3), dtype=np.float64)

    return dict(
        disp=a(disp_l), force=a(force_l),
        crack_positions=a(cpos),
        crack_openings=la(open_l), crack_slips=la(slip_l),
        element_responses=pair_meta,
        node_disp_last_ids=nids_arr, node_disp_last_vals=disp_arr,
        esh_keys=esh_keys, esh_vals=esh_vals,
        status=status, message=msg,
        log=list(_LOG_LINES),
    )


def main():
    if len(sys.argv) == 3:
        with open(sys.argv[1], encoding='utf-8') as f:
            p = json.load(f)

        r = run_model_2d(p)

        # always dump outputs, even on partial runs
        out_dir = os.path.dirname(os.path.abspath(sys.argv[2]))

        # persist runner log next to results
        try:
            log_path = os.path.join(out_dir, 'run.log')
            with open(log_path, 'w', encoding='utf-8') as lf:
                lf.write('\n'.join(r.get('log', _LOG_LINES)))
            print(f"[OUTPUT] run.log written ({len(r.get('log', _LOG_LINES))} lines)")
        except Exception as e_log:
            print(f"[OUTPUT WARN] Could not write run.log: {e_log}")

        # Write params.json copy (already written by GUI, but ensure it exists)
        try:
            pj_path = os.path.join(out_dir, 'params.json')
            if not os.path.exists(pj_path):
                with open(pj_path, 'w', encoding='utf-8') as pf:
                    json.dump(p, pf, indent=2)
        except Exception:
            pass

        # Always write results.npz (even if partial/failed)
        nids = r['node_disp_last_ids']; nvals = r['node_disp_last_vals']
        np.savez(sys.argv[2],
            disp=r['disp'], force=r['force'],
            crack_positions=r['crack_positions'],
            crack_openings=np.array(r['crack_openings'], dtype=object),
            crack_slips=np.array(r['crack_slips'], dtype=object),
            element_responses=np.array(r['element_responses'], dtype=object),
            node_disp_last_ids=nids, node_disp_last_vals=nvals,
            esh_keys=r.get('esh_keys', np.array([], dtype=np.int32)),
            esh_vals=r.get('esh_vals', np.zeros((0, 0, 3))),
            status=np.array([r['status']]),
            message=np.array([r['message']]))
        print(r['message'])
        sys.exit(0 if r['status'] in ('ok', 'partial') else 1)
    else:
        print("Usage: python runner.py params.json results.npz")
        sys.exit(2)


if __name__ == "__main__":
    main()
'''



# WSL worker thread — runs solver subprocess and streams logs

class WSLWorker(QThread):
    log      = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, params, run_dir, activate, is_windows, backend_mode="wsl", python_cmd="python3"):
        super().__init__()
        self.params   = params
        self.run_dir  = Path(run_dir)
        self.activate = activate
        self.is_windows = bool(is_windows)
        self.backend_mode = backend_mode
        self.python_cmd = python_cmd or "python3"

    def run(self):
        
        try:
            mkd(self.run_dir)
            pp  = self.run_dir / "params.json"
            rp  = self.run_dir / "runner.py"
            np_ = self.run_dir / "results.npz"

            pp.write_text(json.dumps(self.params, indent=2), encoding='utf-8')
            rp.write_text(RUNNER_PY.lstrip(), encoding='utf-8')

            if self.backend_mode == "windows":
                cmd = [self.python_cmd, str(rp), str(pp), str(np_)]
                bash = " ".join(shlex.quote(part) for part in cmd)
            elif self.is_windows:
                pp_w  = win_to_wsl(str(pp))
                rp_w  = win_to_wsl(str(rp))
                np_w  = win_to_wsl(str(np_))
                bash = f"{self.activate} && python3 {rp_w} {pp_w} {np_w}"
                cmd  = ["wsl", "bash", "-lc", bash]
            else:
                pp_q = shlex.quote(str(pp))
                rp_q = shlex.quote(str(rp))
                np_q = shlex.quote(str(np_))
                bash = f"{self.activate} && python3 {rp_q} {pp_q} {np_q}"
                cmd  = ["bash", "-lc", bash]
            self.log.emit(f"[CMD] {bash[:140]}")
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
            if proc.stdout.strip(): self.log.emit(proc.stdout.strip())
            if proc.stderr.strip(): self.log.emit("[STDERR] " + proc.stderr.strip())

            # Show run.log if it was written
            log_file = self.run_dir / "run.log"
            if log_file.exists():
                try:
                    log_text = log_file.read_text(encoding='utf-8')
                    if log_text.strip():
                        self.log.emit("\n── run.log ──")
                        for line in log_text.strip().split('\n')[-50:]:
                            self.log.emit(line)
                except Exception:
                    pass

            if proc.returncode != 0 and not np_.exists():
                err_detail = ""
                if proc.stderr.strip():
                    err_detail += proc.stderr.strip()
                if proc.stdout.strip():
                    err_detail += "\n" + proc.stdout.strip()
                raise RuntimeError(
                    f"Analysis FAILED (returncode={proc.returncode}).\n"
                    f"{err_detail}\n\n"
                    "Possible causes:\n"
                    "  1. MultiSurfCrack2D not in build (EPPGap fallback should have run)\n"
                    "  2. Wrong activate command in Run tab\n"
                    "  3. openseespy not installed in that env\n"
                    "  4. WSL path mapping issue\n"
                    "Check console output above for the Python traceback.")

            if not np_.exists():
                raise RuntimeError(
                    "results.npz was not created.\n"
                    "Possible causes:\n"
                    "  1. Wrong activate command in Run tab\n"
                    "  2. openseespy not installed in that env\n"
                    "  3. WSL path mapping issue\n"
                    "Check console output above for the Python traceback.")

            data   = np.load(str(np_), allow_pickle=True)
            def arr(k): return np.array(data[k], dtype=float)
            def obj(k): return [np.array(x, dtype=float) for x in list(data[k])]

            # Reconstruct node_disp_last dict
            nids  = np.array(data["node_disp_last_ids"], dtype=int)
            nvals = np.array(data["node_disp_last_vals"], dtype=float)
            node_disp_last = {int(n): list(nvals[i]) for i, n in enumerate(nids)}

            # Reconstruct mesh data from params (for deformed mesh plot)
            mesh_nodes = {int(k): v for k, v in self.params.get("mesh_nodes", {}).items()}
            mesh_tris  = [[int(x) for x in row] for row in self.params.get("mesh_tris", [])]

            raw_status = str(data["status"][0])
            raw_message = str(data["message"][0])
            # For partial results, keep the status from the runner
            # Only override to "failed" if returncode is non-zero AND status was not "partial"
            if proc.returncode != 0 and raw_status != "partial":
                raw_status = "failed"
                raw_message = f"[FAIL returncode={proc.returncode}] {raw_message}"
                if proc.stderr.strip():
                    self.log.emit("[FAIL STDERR] " + proc.stderr.strip()[:1000])

            # Load body element stress history if available
            esh_keys = np.array(data["esh_keys"], dtype=np.int32) if "esh_keys" in data else np.array([], dtype=np.int32)
            esh_vals = np.array(data["esh_vals"], dtype=np.float64) if "esh_vals" in data else np.array([])

            result = dict(
                status=raw_status,
                message=raw_message,
                disp=arr("disp"), force=arr("force"),
                crack_positions=arr("crack_positions"),
                crack_openings=obj("crack_openings"),
                crack_slips=obj("crack_slips"),
                element_responses=list(data["element_responses"]) if "element_responses" in data else [],
                node_disp_last=node_disp_last,
                mesh_nodes=mesh_nodes,
                mesh_tris=mesh_tris,
                esh_keys=esh_keys,
                esh_vals=esh_vals,
                returncode=proc.returncode,
            )
            self.finished.emit(result)
        except subprocess.TimeoutExpired:
            self.error.emit("Analysis timed out after 600 seconds.")
        except Exception:
            self.error.emit(traceback.format_exc())



# main window — wires tabs, persistence, and run workflow

class MainWindow(QMainWindow):
    def __init__(self):
        """
        Set up widget state, defaults, and signal wiring for this section.
        """
        super().__init__()
        self.setMinimumSize(1300, 860)
        self.RUNS_DIR = str(Path.home() / "panel_analysis_runs")
        self._worker  = None
        self._is_windows = sys.platform.startswith("win")
        self._project_path = None
        self._dirty = False
        self._suspend_dirty = False
        self._recent_files = []

        root = QWidget(); self.setCentralWidget(root)
        vl   = QVBoxLayout(root); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(0)

        #  header
        hdr = QWidget()
        hdr.setStyleSheet(f"background:{BG_PANEL};border-bottom:1px solid {BORDER};")
        hl  = QHBoxLayout(hdr); hl.setContentsMargins(20, 10, 20, 10)
        t1  = QLabel("2D RC PANEL ANALYSIS")
        t1.setStyleSheet(f"color:{C1};font-size:16px;font-weight:bold;letter-spacing:2px;")
        t2  = QLabel("  Plane Stress  ·  tri31  ·  zeroLength Cracks  ·  OpenSeesPy")
        t2.setStyleSheet(f"color:{TXTS};font-size:12px;")
        self.lbl_wsl = QLabel("Backend: checking…")
        self.lbl_wsl.setStyleSheet(f"color:{C4};font-size:12px;font-weight:bold;")
        hl.addWidget(t1); hl.addWidget(t2); hl.addStretch(); hl.addWidget(self.lbl_wsl)
        vl.addWidget(hdr)

        #  quick-actions toolbar
        qa = QWidget()
        qa.setStyleSheet(f"background:{BG_CARD};border-bottom:1px solid {BORDER};")
        qal = QHBoxLayout(qa); qal.setContentsMargins(16, 7, 16, 7); qal.setSpacing(8)

        self.btn_run = QPushButton("▶  Run Analysis")
        self.btn_run.setMinimumHeight(36)
        self.btn_run.setStyleSheet(
            f"background:{C2};color:{BG_DEEP};font-weight:bold;font-size:13px;"
            f"padding:7px 22px;border-radius:5px;border:none;")
        self.btn_run.setToolTip("Run the 2D panel analysis in WSL OpenSeesPy.")

        self.btn_refresh_cracks = QPushButton("↺  Refresh Crack Materials")
        self.btn_refresh_cracks.setObjectName("warn")
        self.btn_refresh_cracks.setToolTip(
            "Load current crack lines from Geometry tab into the Crack Materials tab.")

        self.btn_gen_script = QPushButton("📋  Export Script")
        self.btn_gen_script.setObjectName("flat")

        self.btn_save_png = QPushButton("💾  Save PNG")
        self.btn_save_png.setObjectName("flat"); self.btn_save_png.setEnabled(False)

        self.btn_csv = QPushButton("📊  Export CSV")
        self.btn_csv.setObjectName("flat"); self.btn_csv.setEnabled(False)

        self.btn_gen_script_now = QPushButton("📋 Generate Script")
        self.btn_gen_script_now.setObjectName("flat")
        self.btn_gen_script_now.setToolTip(
            "Export a standalone OpenSeesPy script now (no need to run analysis first).")

        self.btn_example = QPushButton("📂 Calvi Panel")
        self.btn_example.setObjectName("flat")
        self.btn_example.setToolTip(
            "Load the Calvi 2015 cracked panel example: single horizontal crack, "
            "unbonded reinforcement, 1.0x2.0 m panel.")

        self.lbl_workflow = QLabel(
            "  ① Geometry  →  ② Crack Materials  →  ③ Analysis  →  ▶ Run Analysis  →  ⑤ Results")
        self.lbl_workflow.setStyleSheet(f"color:{TXTS};font-size:10px;")

        for w in [self.btn_run, self.btn_refresh_cracks, self.btn_gen_script,
                  self.btn_gen_script_now, self.btn_example,
                  self.btn_save_png, self.btn_csv, self.lbl_workflow]:
            qal.addWidget(w)
        qal.addStretch()
        vl.addWidget(qa)

        # tabs
        body = QWidget(); body.setStyleSheet(f"background:{BG_DEEP};")
        bl   = QVBoxLayout(body); bl.setContentsMargins(12, 12, 12, 12)
        self.tabs = QTabWidget()

        self.geo  = GeometryTab()
        self.crk  = CrackMaterialTab()
        self.crk.set_geo_ref(self.geo)
        self.anl  = AnalysisTab()
        self.run  = RunTab()
        self.res  = ResultsTab()
        self.scr  = ScriptTab()
        self._load_backend_config()

        for name, tab in [
            ("① Geometry",        self.geo),
            ("② Crack Materials", self.crk),
            ("③ Analysis",        self.anl),
            ("④ Run",             self.run),
            ("⑤ Results",         self.res),
            ("⑥ Script",          self.scr),
        ]:
            self.tabs.addTab(tab, name)

        bl.addWidget(self.tabs); vl.addWidget(body, stretch=1)

        self.statusBar().showMessage(
            "Ready — set panel geometry, assign BCs/loads, then Run Analysis.")
        self.statusBar().setStyleSheet(
            f"background:{BG_PANEL};color:{TXTS};border-top:1px solid {BORDER};")

        #  wire signals
        self.run.run_requested.connect(self.start_analysis)
        self.run.auto_detect_requested.connect(self.auto_detect_backend)
        self.btn_run.clicked.connect(self.start_analysis)
        self.btn_refresh_cracks.clicked.connect(self._refresh_cracks)
        self.btn_gen_script.clicked.connect(self.generate_script)
        self.scr.btn_gen.clicked.connect(self.generate_script)
        self.btn_save_png.clicked.connect(lambda: self.res._save())
        self.btn_csv.clicked.connect(lambda: self.res._csv())
        self.btn_gen_script_now.clicked.connect(self._generate_script_now)
        self.btn_example.clicked.connect(self._load_calvi_example)

        self._setup_menu()
        self._install_spinbox_wheel_guard()
        self._install_dirty_tracking()
        self._update_window_title()

        self.geo.mesh_generated.connect(lambda: self.crk.refresh_from_geometry(self.geo))

        QTimer.singleShot(900, self.check_wsl)

    #  helpers
    def _refresh_cracks(self):
        self.crk.refresh_from_geometry(self.geo)
        self.tabs.setCurrentWidget(self.crk)

    def _params(self):
        p = {}
        p.update(self.geo.get_params())
        p.update(self.crk.get_params())
        p.update(self.anl.get_params())
        return p

    def _setup_menu(self):
        
        file_menu = self.menuBar().addMenu("File")

        self.act_new = QAction("New Project", self)
        self.act_new.setShortcut("Ctrl+N")
        self.act_open = QAction("Load Project", self)
        self.act_open.setShortcut("Ctrl+O")
        self.act_save = QAction("Save Project", self)
        self.act_save.setShortcut("Ctrl+S")
        self.act_save_as = QAction("Save Project As", self)
        self.act_save_as.setShortcut("Ctrl+Shift+S")
        self.recent_menu = QMenu("Recent Files", self)

        file_menu.addAction(self.act_new)
        file_menu.addAction(self.act_open)
        file_menu.addAction(self.act_save)
        file_menu.addAction(self.act_save_as)
        file_menu.addMenu(self.recent_menu)

        self.act_new.triggered.connect(self.new_project)
        self.act_open.triggered.connect(self.load_project)
        self.act_save.triggered.connect(self.save_project)
        self.act_save_as.triggered.connect(self.save_project_as)
        self._refresh_recent_files_menu()

    def _install_dirty_tracking(self):
        
        def _connect_spinboxes(parent):
           
            for widget in parent.findChildren(QDoubleSpinBox):
                widget.valueChanged.connect(lambda *_: self._set_dirty(True))
            for widget in parent.findChildren(QSpinBox):
                widget.valueChanged.connect(lambda *_: self._set_dirty(True))
            for widget in parent.findChildren(QLineEdit):
                widget.textChanged.connect(lambda *_: self._set_dirty(True))
            for widget in parent.findChildren(QComboBox):
                widget.currentTextChanged.connect(lambda *_: self._set_dirty(True))
            for widget in parent.findChildren(QCheckBox):
                widget.toggled.connect(lambda *_: self._set_dirty(True))
            for widget in parent.findChildren(QRadioButton):
                widget.toggled.connect(lambda *_: self._set_dirty(True))

        for parent in [self.geo, self.crk, self.anl, self.run]:
            _connect_spinboxes(parent)
        self.crk.tbl.itemChanged.connect(lambda *_: self._set_dirty(True))

    def _install_spinbox_wheel_guard(self):
        self._spinbox_wheel_guard = SpinboxWheelEventFilter(self)
        for sb in self.findChildren(QAbstractSpinBox):
            sb.installEventFilter(self._spinbox_wheel_guard)
            sb.setFocusPolicy(Qt.StrongFocus)

    def _update_window_title(self):
        name = Path(self._project_path).name if self._project_path else "New Project"
        dirty = " *" if self._dirty else ""
        self.setWindowTitle(f"2D RC Panel Analysis  ·  OpenSeesPy  ·  {name}{dirty}")

    def _set_dirty(self, dirty=True):
        if self._suspend_dirty:
            return
        self._dirty = bool(dirty)
        self._update_window_title()

    def _refresh_recent_files_menu(self):
        
        self.recent_menu.clear()
        if not self._recent_files:
            act = QAction("No recent files", self)
            act.setEnabled(False)
            self.recent_menu.addAction(act)
            return
        for path in self._recent_files[:5]:
            act = QAction(path, self)
            act.triggered.connect(lambda checked=False, p=path: self.load_project(p))
            self.recent_menu.addAction(act)

    def _add_recent_file(self, path):
        path = str(Path(path))
        self._recent_files = [p for p in self._recent_files if p != path]
        self._recent_files.insert(0, path)
        self._recent_files = self._recent_files[:5]
        self._refresh_recent_files_menu()
        self._save_backend_config()

    def _confirm_discard_changes(self):
        
        if not self._dirty:
            return True
        ans = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Continue and discard them?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return ans == QMessageBox.Yes

    def _collect_project_state(self):
        
        geo = self.geo.get_params()
        crk = self.crk.get_params()
        anl = self.anl.get_params()
        run_cfg = self.run.get_backend_config()
        return {
            "version": PROJECT_FILE_VERSION,
            "panel": {
                "W": geo.get("panel_W", 1.0),
                "H": geo.get("panel_H", 2.0),
                "t": geo.get("panel_t", 0.2),
                "Ec": geo.get("panel_Ec", 30000.0),
                "nu": geo.get("panel_nu", 0.2),
            },
            "mesh": {
                "mode": geo.get("mesh_mode", "divisions"),
                "nx": geo.get("mesh_nx", 6),
                "ny": geo.get("mesh_ny", 12),
                "max_elem_size": geo.get("max_elem_size", 0.2),
                "max_aspect": geo.get("max_aspect", 2.0),
                "enable_edge_snap": geo.get("enable_edge_snap", True),
                "edge_snap_threshold": geo.get("edge_snap_threshold", 0.15),
                "default_crack_angle_deg": geo.get("default_crack_angle_deg", 0.0),
            },
            "crack_ys": geo.get("crack_ys", []),
            "hand_strokes": geo.get("hand_crack_strokes", []),
            "hand_crack_defs": geo.get("hand_crack_defs", []),
            "background_image": geo.get("background_image", ""),
            "bc_nodes": geo.get("bc_nodes", {}),
            "load_nodes": geo.get("load_nodes", {}),
            "crack_materials": crk.get("crack_mat_data", []),
            "analysis": anl,
            "wsl_activate": run_cfg.get("activate_cmd", "source ~/ops_env/bin/activate"),
            "run": run_cfg,
        }

    def _apply_project_state(self, project_state):
        
        panel = project_state.get("panel", {})
        mesh = project_state.get("mesh", {})
        flat_geo = {
            "panel_W": panel.get("W", 1.0),
            "panel_H": panel.get("H", 2.0),
            "panel_t": panel.get("t", 0.2),
            "panel_Ec": panel.get("Ec", 30000.0),
            "panel_nu": panel.get("nu", 0.2),
            "mesh_mode": mesh.get("mode", "divisions"),
            "mesh_nx": mesh.get("nx", 6),
            "mesh_ny": mesh.get("ny", 12),
            "max_elem_size": mesh.get("max_elem_size", 0.2),
            "max_aspect": mesh.get("max_aspect", 2.0),
            "enable_edge_snap": mesh.get("enable_edge_snap", True),
            "edge_snap_threshold": mesh.get("edge_snap_threshold", 0.15),
            "default_crack_angle_deg": mesh.get("default_crack_angle_deg", 0.0),
            "crack_ys": project_state.get("crack_ys", []),
            "hand_crack_strokes": project_state.get("hand_strokes", []),
            "hand_crack_ys": [item.get("y", 0.0) for item in project_state.get("hand_crack_defs", [])],
            "hand_crack_defs": project_state.get("hand_crack_defs", []),
            "background_image": project_state.get("background_image", ""),
            "bc_nodes": project_state.get("bc_nodes", {}),
            "load_nodes": project_state.get("load_nodes", {}),
        }
        self._suspend_dirty = True
        try:
            self.geo.set_project_state(flat_geo)
            self.crk.set_project_state({"crack_mat_data": project_state.get("crack_materials", [])}, self.geo)
            self.anl.set_project_state(project_state.get("analysis", {}))
            self.run.apply_backend_config(project_state.get("run", {
                **self._default_backend_config(),
                "activate_cmd": project_state.get("wsl_activate", "source ~/ops_env/bin/activate"),
            }))
        finally:
            self._suspend_dirty = False
        self._set_dirty(False)

    def new_project(self):
       
        if not self._confirm_discard_changes():
            return
        self._project_path = None
        self._suspend_dirty = True
        try:
            self.geo.reset_project_state()
            self.crk.reset_project_state()
            self.anl.reset_project_state()
            self.run.apply_backend_config(self._default_backend_config())
        finally:
            self._suspend_dirty = False
        self._set_dirty(False)

    def save_project(self):
        if self._project_path:
            return self._save_project_to_path(self._project_path)
        return self.save_project_as()

    def save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", self._project_path or "panel_project.json", "JSON (*.json)")
        if not path:
            return False
        return self._save_project_to_path(path)

    def _save_project_to_path(self, path):
        """
        Read or write project state while keeping backward compatibility in mind.
        """
        try:
            Path(path).write_text(json.dumps(self._collect_project_state(), indent=2), encoding="utf-8")
            self._project_path = str(Path(path))
            self._add_recent_file(self._project_path)
            self._set_dirty(False)
            self.statusBar().showMessage(f"Project saved to {self._project_path}")
            return True
        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", str(exc))
            return False

    def load_project(self, path=None):
        """
        Read or write project state while keeping backward compatibility in mind.
        """
        if not self._confirm_discard_changes():
            return False
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "JSON (*.json)")
        if not path:
            return False
        try:
            project_state = json.loads(Path(path).read_text(encoding="utf-8"))
            self._project_path = str(Path(path))
            self._apply_project_state(project_state)
            self._add_recent_file(self._project_path)
            self.statusBar().showMessage(f"Project loaded from {self._project_path}")
            return True
        except Exception as exc:
            QMessageBox.warning(self, "Load Failed", str(exc))
            return False

    def _default_backend_config(self):
        return {
            "backend_mode": "wsl" if self._is_windows else "local",
            "activate_cmd": "source ~/ops_env/bin/activate",
            "python_cmd": sys.executable,
            "status_label": "Detection: not run yet.",
            "status_ok": True,
        }

    def _load_backend_config(self):
        """
        Read or write project state while keeping backward compatibility in mind.
        """
        cfg = self._default_backend_config()
        try:
            if APP_CONFIG_FILE.exists():
                loaded = json.loads(APP_CONFIG_FILE.read_text(encoding="utf-8"))
                cfg.update(loaded)
                self._recent_files = [str(Path(p)) for p in loaded.get("recent_files", []) if p]
        except Exception:
            pass
        self.run.apply_backend_config(cfg)
        if hasattr(self, "recent_menu"):
            self._refresh_recent_files_menu()

    def _save_backend_config(self):
        try:
            cfg = self.run.get_backend_config()
            cfg["recent_files"] = list(self._recent_files[:5])
            APP_CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        except Exception as exc:
            self.run.append(f"[CONFIG WARN] Could not save {APP_CONFIG_FILE.name}: {exc}")

    def _probe_wsl_activate(self, activate_cmd):
        cmd = ["wsl", "bash", "-lc",
               f"{activate_cmd} && python3 -c \"import openseespy.opensees as ops, sys; print(sys.executable)\""]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        exe = proc.stdout.strip().splitlines()[-1] if proc.returncode == 0 and proc.stdout.strip() else ""
        return proc.returncode == 0 and bool(exe), exe

    def _probe_wsl_python(self, python_cmd):
        cmd = ["wsl", "bash", "-lc",
               f"{python_cmd} -c \"import openseespy.opensees as ops, sys; print(sys.executable)\""]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        exe = proc.stdout.strip().splitlines()[-1] if proc.returncode == 0 and proc.stdout.strip() else ""
        return proc.returncode == 0 and bool(exe), exe

    def _probe_windows_python(self, python_cmd):
        proc = subprocess.run(
            [python_cmd, "-c", "import openseespy.opensees as ops, sys; print(sys.executable)"],
            capture_output=True, text=True, timeout=25
        )
        exe = proc.stdout.strip().splitlines()[-1] if proc.returncode == 0 and proc.stdout.strip() else ""
        return proc.returncode == 0 and bool(exe), exe

    def auto_detect_backend(self):
        """
        Keep this part of the workflow stable and explicit for future debugging.
        """
        self.run.append("[AUTO-DETECT] Searching for OpenSeesPy backend...")
        workspace = Path(__file__).resolve().parent

        if self._is_windows:
            wsl_venv_paths = [
                f"source {win_to_wsl(str(workspace / '.venv'))}/bin/activate",
                "source ~/ops_env/bin/activate",
                "source ~/.venv/bin/activate",
                "source ~/venv/bin/activate",
                "source ~/opensees-env/bin/activate",
            ]
            for act in wsl_venv_paths:
                try:
                    ok, exe = self._probe_wsl_activate(act)
                except Exception:
                    ok, exe = False, ""
                if ok:
                    self.run.backend_mode = "wsl"
                    self.run.python_cmd = "python3"
                    self.run.wsl_activate.setText(act)
                    msg = f"Detected WSL virtualenv: {exe}"
                    self.run.set_detection_status(msg, ok=True)
                    self.run.append(f"[AUTO-DETECT] {msg}")
                    self._save_backend_config()
                    self.check_wsl()
                    return

            conda_setup = [
                "~/miniconda3/etc/profile.d/conda.sh",
                "~/anaconda3/etc/profile.d/conda.sh",
                "~/mambaforge/etc/profile.d/conda.sh",
            ]
            env_names = []
            for setup in conda_setup:
                try:
                    proc = subprocess.run(
                        ["wsl", "bash", "-lc", f"source {setup} >/dev/null 2>&1; conda env list --json"],
                        capture_output=True, text=True, timeout=25
                    )
                    if proc.returncode == 0 and proc.stdout.strip():
                        envs = json.loads(proc.stdout).get("envs", [])
                        env_names = [Path(env).name for env in envs if env]
                        if env_names:
                            for env_name in env_names:
                                act = f"source {setup} && conda activate {env_name}"
                                try:
                                    ok, exe = self._probe_wsl_activate(act)
                                except Exception:
                                    ok, exe = False, ""
                                if ok:
                                    self.run.backend_mode = "wsl"
                                    self.run.python_cmd = "python3"
                                    self.run.wsl_activate.setText(act)
                                    msg = f"Detected WSL conda env '{env_name}': {exe}"
                                    self.run.set_detection_status(msg, ok=True)
                                    self.run.append(f"[AUTO-DETECT] {msg}")
                                    self._save_backend_config()
                                    self.check_wsl()
                                    return
                except Exception:
                    continue

            try:
                ok, exe = self._probe_wsl_python("python3")
            except Exception:
                ok, exe = False, ""
            if ok:
                self.run.backend_mode = "wsl"
                self.run.python_cmd = "python3"
                self.run.wsl_activate.setText("true")
                msg = f"Detected WSL system python: {exe}"
                self.run.set_detection_status(msg, ok=True)
                self.run.append(f"[AUTO-DETECT] {msg}")
                self._save_backend_config()
                self.check_wsl()
                return

            windows_candidates = [
                workspace / ".venv" / "Scripts" / "python.exe",
                Path(sys.executable),
                Path("python.exe"),
            ]
            for candidate in windows_candidates:
                try:
                    ok, exe = self._probe_windows_python(str(candidate))
                except Exception:
                    ok, exe = False, ""
                if ok:
                    self.run.backend_mode = "windows"
                    self.run.python_cmd = exe or str(candidate)
                    self.run.wsl_activate.setText(exe or str(candidate))
                    msg = f"Detected Windows python: {exe or candidate}"
                    self.run.set_detection_status(msg, ok=True)
                    self.run.append(f"[AUTO-DETECT] {msg}")
                    self._save_backend_config()
                    self.check_wsl()
                    return

        msg = "Detection: OpenSeesPy not found in WSL virtualenv, WSL conda, WSL python3, or Windows python."
        self.run.set_detection_status(msg, ok=False)
        self.run.append(f"[AUTO-DETECT] {msg}")
        self._save_backend_config()

    def check_wsl(self):
        """
        Keep this part of the workflow stable and explicit for future debugging.
        """
        act = self.run.get_activate()
        mode = self.run.backend_mode
        if mode == "windows":
            cmd = [self.run.python_cmd, "-c", "import openseespy.opensees; print('OK')"]
            backend_name = "Windows"
        elif self._is_windows:
            cmd = ["wsl", "bash", "-lc",
                   f"{act} && python3 -c \"import openseespy.opensees; print('OK')\""]
            backend_name = "WSL"
        else:
            cmd = ["bash", "-lc",
                   f"{act} && python3 -c \"import openseespy.opensees; print('OK')\""]
            backend_name = "Local"
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            ok   = "OK" in proc.stdout
            self.lbl_wsl.setText(f"{backend_name}: {'✓ OK' if ok else 'NOT READY'}")
            self.lbl_wsl.setStyleSheet(
                f"color:{C2 if ok else C3};font-size:12px;font-weight:bold;")
            self.run.set_detection_status(f"{backend_name} backend: {'ready' if ok else 'not ready'}", ok=ok)
            self.run.append(f"✓ {backend_name} OpenSeesPy ready." if ok else
                            f"{backend_name} check failed — fix 'Activate command' in Run tab.")
            if not ok and proc.stderr.strip():
                self.run.append(proc.stderr.strip()[:500])
        except Exception as e:
            self.lbl_wsl.setText(f"{backend_name}: ERROR")
            self.lbl_wsl.setStyleSheet(f"color:{C3};font-size:11px;font-weight:bold;")
            self.run.append(f"{backend_name} check error: {e}")

    def start_analysis(self):
        """
        Run the backend workflow and stream status so failures are visible quickly.
        """
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Busy", "Analysis already running."); return

        errs = self.geo.validate()
        if errs:
            self.tabs.setCurrentWidget(self.geo)
            msg = "  ⚠  " + "   |   ".join(errs)
            self.lbl_workflow.setText(msg)
            self.lbl_workflow.setStyleSheet(f"color:{C3};font-size:11px;font-weight:bold;")
            QMessageBox.warning(self, "Validation Errors", "\n".join(errs))
            return

        # Auto-refresh crack materials if table is empty
        if self.crk.tbl.rowCount() == 0:
            self.crk.refresh_from_geometry(self.geo)

        p   = self._params()
        ts  = time.strftime("%Y%m%d_%H%M%S")
        rd  = Path(self.RUNS_DIR) / f"run_{ts}"
        act = self.run.get_activate()
        self._save_backend_config()

        nn  = len(p.get("mesh_nodes", {}))
        nt  = len(p.get("mesh_tris",  []))
        nc  = len(p.get("mesh_crack_pairs", []))
        nld = len(p.get("load_nodes",  {}))
        nbc = len(p.get("bc_nodes",    {}))

        self.run.append(f"\n{'━'*60}")
        self.run.append(f"Run folder : {rd}")
        self.run.append(f"Panel      : {p.get('panel_W'):.3f} × {p.get('panel_H'):.3f} m  "
                        f"t={p.get('panel_t'):.3f} m  Ec={p.get('panel_Ec'):.0f} MPa")
        self.run.append(f"Mesh       : {nn} nodes, {nt} tri, {nc} crack links")
        self.run.append(f"BCs        : {nbc} fixed DOFs    Loads: {nld} loaded nodes")
        self.run.append(f"Analysis   : {p.get('analysis_type')}  "
                        f"target={p.get('target_disp')}  incr={p.get('disp_incr')}  "
                        f"protocol={p.get('loading_protocol', 'monotonic')}")
        backend_name = "WSL" if self._is_windows else "local backend"
        self.run.set_status(f"Running in {backend_name}…")
        self.run.btn_run.setEnabled(False)
        self.btn_run.setEnabled(False)
        self.btn_run.setText("Running...")
        self.lbl_workflow.setText("  Analysis running — see ④ Run tab for progress…")
        self.lbl_workflow.setStyleSheet(f"color:{C4};font-size:10px;")
        self.statusBar().showMessage(f"Analysis running in {backend_name}…")

        self._worker = WSLWorker(
            p, str(rd), act, self._is_windows,
            backend_mode=self.run.backend_mode,
            python_cmd=self.run.python_cmd,
        )
        self._worker.log.connect(self.run.append)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_err)
        self._worker.start()

    def _on_done(self, result):
        """
        Handle a UI event and keep the related state in sync.
        """
        self.run.btn_run.setEnabled(True)
        self.btn_run.setEnabled(True)
        self.btn_run.setText("▶  Run Analysis")
        msg = result["message"]
        self.run.set_status(f"{'✓' if result['status']=='ok' else '⚠'} {msg}",
                            ok=(result["status"] == "ok"))
        self.run.append(f"\n{'SUCCESS' if result['status']=='ok' else 'PARTIAL/FAILED'}: {msg}")

        if result["disp"].size > 0:
            # Attach hand-drawn stroke data from the geometry tab
            geo_p = self.geo.get_params()
            result["hand_crack_strokes"] = geo_p.get("hand_crack_strokes", [])
            result["hand_crack_ys"]      = geo_p.get("hand_crack_ys", [])
            self.res.set_results(result)
            self.btn_save_png.setEnabled(True)
            self.btn_csv.setEnabled(True)
            self.tabs.setCurrentWidget(self.res)
            self.generate_script()
            self.lbl_workflow.setText(
                f"  Done ({len(result['disp'])} steps) — view ⑤ Results | Save PNG / CSV via toolbar")
            self.lbl_workflow.setStyleSheet(f"color:{C2};font-size:10px;font-weight:bold;")
        else:
            self.lbl_workflow.setText(
                f"  Analysis incomplete: {msg}  — check ④ Run tab console.")
            self.lbl_workflow.setStyleSheet(f"color:{C3};font-size:10px;font-weight:bold;")
        self.statusBar().showMessage(
            f"{result['status'].upper()}  |  {len(result['disp'])} steps converged")

    def _on_err(self, tb):
        self.run.btn_run.setEnabled(True)
        self.btn_run.setEnabled(True)
        self.btn_run.setText("▶  Run Analysis")
        self.run.set_status("Error in solver backend (see console)", ok=False)
        self.run.append("\nERROR:\n" + tb)
        self.lbl_workflow.setText(
            "  Error — see ④ Run tab console. Check activate command and OpenSeesPy install.")
        self.lbl_workflow.setStyleSheet(f"color:{C3};font-size:10px;font-weight:bold;")
        self.statusBar().showMessage("Error — see console.")

    def closeEvent(self, event):
        if self._confirm_discard_changes():
            event.accept()
        else:
            event.ignore()

    def _generate_script_now(self):
        """Generate script from current GUI state without running analysis."""
        errs = self.geo.validate()
        if errs:
            QMessageBox.warning(self, "Incomplete Model",
                "Fix these issues before generating script:\n\n" + "\n".join(errs))
            return
        if self.crk.tbl.rowCount() == 0:
            self.crk.refresh_from_geometry(self.geo)
        self.generate_script()
        self.tabs.setCurrentWidget(self.scr)
        self.statusBar().showMessage("Script generated — see Script tab.")
        QMessageBox.information(self, "Script Ready",
            "Standalone OpenSeesPy script has been generated.\n"
            "Switch to the Script tab to copy or save it.")

    def _load_calvi_example(self):
        """Load the Calvi 2015 experimental validation case."""
        ans = QMessageBox.question(self, "Load Calvi Example",
            "This will reset the current model and load the Calvi 2015 panel configuration.\n\n"
            "Panel: 1.0 x 2.0 m, crack at mid-height (y=1.0 m)\n"
            "Material: SimpleSpring (Kn=500, Ks=200 MPa/mm)\n"
            "BCs: bottom nodes pinned | Load: vertical on top nodes\n\n"
            "Continue?")
        if ans != QMessageBox.Yes:
            return
        # 1. Set geometry
        self.geo.sb_W.setValue(1.0)
        self.geo.sb_H.setValue(2.0)
        self.geo.sb_t.setValue(0.15)
        self.geo.sb_nx.setValue(6)
        self.geo.sb_ny.setValue(12)
        # 2. Set crack at mid-height
        self.geo._crack_ys = [1.0]
        self.geo.canvas.set_pending_cracks([1.0], 1.0, 2.0)
        self.geo._refresh_crack_label()
        # 3. Generate mesh
        self.geo._generate()
        md = self.geo.get_mesh_data()
        if md is None:
            QMessageBox.critical(self, "Error", "Failed to generate mesh.")
            return
        # 4. Apply pinned BCs to all bottom nodes (y ~ 0)
        self.geo._bc_nodes.clear()
        for nid, (x, y) in md["nodes"].items():
            if abs(y) < 1e-8:
                self.geo._bc_nodes[nid] = (1, 1)
        self.geo.canvas.set_bc_nodes(self.geo._bc_nodes)
        self.geo._update_bc_table()
        # 5. Apply downward load on all top nodes
        top_nodes = [nid for nid, (x, y) in md["nodes"].items()
                     if abs(y - 2.0) < 1e-8]
        self.geo._load_nodes.clear()
        total_load = -200.0
        per_node = total_load / max(len(top_nodes), 1)
        for nid in top_nodes:
            self.geo._load_nodes[nid] = (0.0, per_node)
        self.geo.canvas.set_load_nodes(self.geo._load_nodes)
        self.geo._update_load_table()
        # 6. Refresh crack materials with SimpleSpring defaults
        self.crk.refresh_from_geometry(self.geo)
        self.crk.cmb_mat_tmpl.setCurrentText("Calvi2015 (EPP-normal / Elastic-shear)")
        self.crk._apply_template_to_all()
        # 7. Set analysis to LoadControl
        idx = self.anl.cmb_type.findText("LoadControl")
        if idx >= 0:
            self.anl.cmb_type.setCurrentIndex(idx)
        # 8. Generate the script
        self.generate_script()
        self.statusBar().showMessage(
            "Calvi 2015 example loaded — review settings then Run Analysis.")
        QMessageBox.information(self, "Example Loaded",
            "Calvi 2015 panel configuration loaded successfully.\n\n"
            "Review BCs, loads, and crack material settings, then click Run Analysis.")

    def generate_script(self):
        """
        Build or refresh mesh-related data used by the geometry and analysis flow.
        """
        p = self._params()
        import json as _j
        py_p = _j.dumps(p, indent=2).replace(': true', ': True').replace(': false', ': False').replace(': null', ': None')
        nt = len(p.get("mesh_tris", []))
        nc = len(p.get("mesh_crack_pairs", []))

        # Clean header for the exported script
        hdr = (
            f'#!/usr/bin/env python3\n'
            f'"""\n'
            f'2D RC Panel Analysis — Standalone OpenSeesPy Script\n'
            f'Generated : {time.strftime("%Y-%m-%d %H:%M:%S")}\n'
            f'Panel     : {p.get("panel_W","?")} × {p.get("panel_H","?")} m\n'
            f'Mesh      : tri={nt}  crack_links={nc}\n'
            f'\n'
            f'Usage:\n'
            f'  python panel_analysis.py params.json results.npz\n'
            f'\n'
            f'This script loads parameters from params.json and runs the OpenSeesPy 2D RC panel analysis.\n'
            f'Crack materials: MultiSurfCrack2D (requires custom build), EPPGap Macro, Elastic.\n'
            f'Run in any environment with: pip install openseespy numpy\n'
            f'Results are saved to results.npz.\n'
            f'"""\n'
            f'\n'
            f'import json, sys\n\n'
            f'# Load parameters from external file\n'
            f'if len(sys.argv) == 3:\n'
            f'    with open(sys.argv[1], encoding="utf-8") as f:\n'
            f'        PARAMS = json.load(f)\n'
            f'    RESULTS_FILE = sys.argv[2]\n'
            f'else:\n'
            f'    # Fallback: embedded parameters (for direct execution)\n'
            f'    RESULTS_FILE = "results.npz"\n'
            f'    PARAMS = {py_p}\n'
            f'\n'
            f'# ────────────────────────────────────────────────────────────\n'
            f'# Runner implementation: call this after defining PARAMS above\n'
            f'# ────────────────────────────────────────────────────────────\n'
        )

        # Include the full runner code for standalone execution
        full_script = hdr + RUNNER_PY.lstrip()
        self.scr.set_script(full_script)
        self.lbl_workflow.setText(
            "  Script generated. Use ⑥ Script tab to copy or save.")



# Entry point

def main():
    
    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setStyleSheet(STYLE)
        w = MainWindow()
        w.show()
        sys.exit(app.exec_())
    except Exception as e:
        tb_str = traceback.format_exc()
        try:
            app2 = QApplication.instance() or QApplication(sys.argv)
            mb = QMessageBox()
            mb.setWindowTitle("Startup Error")
            mb.setText(str(e))
            mb.setDetailedText(tb_str)
            mb.exec_()
        except Exception:
            print("STARTUP ERROR:", tb_str)
        sys.exit(1)


if __name__ == "__main__":
    main()
