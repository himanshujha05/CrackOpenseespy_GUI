#!/usr/bin/env python3
"""
2D Reinforced Concrete Panel Analysis Tool — OpenSeesPy GUI
===========================================================
Strictly 2D plane-stress panel:
  - Triangular mesh (tri31 PlaneStress)
  - Interactive node selection for BC / load assignment
  - User-controlled crack interfaces (zeroLength)
  - Crack materials: Elastic, ElasticPPGap, Custom Bilinear
  - Full result visualisation (deformed mesh, contours, histories)

Run:
  python gui_wsl.py
"""

import sys, json, time, math, traceback, subprocess
from pathlib import Path
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QTextEdit, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QDoubleSpinBox, QSpinBox, QFileDialog,
    QMessageBox, QCheckBox, QSplitter, QScrollArea,
    QFrame,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import (
    QFont, QPainter, QPen, QBrush, QColor,
    QPainterPath, QFontMetrics,
)

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.tri import Triangulation

# ─── Colour palette ──────────────────────────────────────────────────────────
BG_DEEP  = "#0d1117"
BG_PANEL = "#161b22"
BG_CARD  = "#1c2128"
BG_INPUT = "#0d1117"
BORDER   = "#30363d"
C1       = "#58a6ff"   # blue
C2       = "#3fb950"   # green
C3       = "#f78166"   # red
C4       = "#d2a679"   # amber
TXT      = "#e6edf3"
TXTS     = "#8b949e"
CRACK_BELOW = "#ff8c42"   # orange  — node on the BELOW side of a crack
CRACK_ABOVE = "#c084fc"   # violet  — node on the ABOVE side of a crack

STYLE = f"""
QMainWindow,QDialog{{background:{BG_DEEP};}}
QWidget{{background:{BG_DEEP};color:{TXT};
  font-family:'Segoe UI','Cascadia Code','Consolas',sans-serif;font-size:13px;}}
QTabWidget::pane{{border:1px solid {BORDER};background:{BG_PANEL};border-radius:0 4px 4px 4px;}}
QTabBar::tab{{background:{BG_DEEP};color:{TXTS};padding:9px 20px;
  border:1px solid {BORDER};border-bottom:none;border-radius:4px 4px 0 0;
  font-weight:bold;font-size:12px;margin-right:2px;}}
QTabBar::tab:selected{{background:{BG_PANEL};color:{C1};border-bottom:2px solid {C1};}}
QTabBar::tab:hover:!selected{{color:{TXT};background:{BG_CARD};}}
QGroupBox{{border:1px solid {BORDER};border-radius:6px;margin-top:16px;
  padding:14px 10px 10px 10px;color:{C1};font-weight:bold;font-size:12px;letter-spacing:.6px;}}
QGroupBox::title{{subcontrol-origin:margin;left:12px;padding:0 6px;background:{BG_PANEL};}}
QLineEdit,QDoubleSpinBox,QSpinBox,QComboBox{{
  background:{BG_INPUT};border:1px solid {BORDER};border-radius:4px;
  padding:6px 10px;color:{TXT};font-size:13px;}}
QLineEdit:focus,QDoubleSpinBox:focus,QSpinBox:focus,QComboBox:focus{{
  border:1px solid {C1};background:{BG_CARD};}}
QDoubleSpinBox::up-button,QDoubleSpinBox::down-button,
QSpinBox::up-button,QSpinBox::down-button{{background:{BG_CARD};border:none;width:18px;}}
QComboBox QAbstractItemView{{background:{BG_CARD};border:1px solid {BORDER};
  selection-background-color:{C1};color:{TXT};}}
QComboBox::drop-down{{border:none;width:22px;}}
QPushButton{{background:{C1};color:{BG_DEEP};border-radius:5px;padding:8px 20px;
  font-weight:bold;font-size:12px;border:none;}}
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
QLabel#heading{{color:{C1};font-size:17px;font-weight:bold;letter-spacing:1px;}}
QLabel#sub{{color:{TXTS};font-size:12px;}}
QLabel#param{{color:{C4};font-size:12px;font-weight:bold;}}
QToolTip{{background:{BG_CARD};color:{TXT};border:1px solid {C1};padding:6px;
  border-radius:4px;font-size:12px;}}
QCheckBox{{color:{TXT};spacing:8px;font-size:13px;}}
QCheckBox::indicator{{width:15px;height:15px;border:1px solid {BORDER};
  border-radius:3px;background:{BG_INPUT};}}
QCheckBox::indicator:checked{{background:{C1};border-color:{C1};}}
"""

# ─── helpers ─────────────────────────────────────────────────────────────────
def win_to_wsl(p):
    p = Path(p); drv = p.drive.rstrip(":").lower()
    rest = p.as_posix().split(":/", 1)[-1]
    return f"/mnt/{drv}/{rest}"

def mkd(path): Path(path).mkdir(parents=True, exist_ok=True)

def dsb(val, lo, hi, dec=4, step=0.001, w=155, tip=""):
    sb = QDoubleSpinBox()
    sb.setRange(lo, hi); sb.setDecimals(dec)
    sb.setSingleStep(step); sb.setValue(val); sb.setFixedWidth(w)
    if tip: sb.setToolTip(tip)
    return sb

def isb(val, lo, hi, w=120, tip=""):
    sb = QSpinBox(); sb.setRange(lo, hi); sb.setValue(val); sb.setFixedWidth(w)
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


# ─── Mesh generation ──────────────────────────────────────────────────────────
def generate_panel_mesh(W, H, nx, ny, crack_ys):
    """
    Structured triangular mesh for a W×H panel.
    Crack rows duplicate nodes so zeroLength interface elements can be inserted.

    Returns
    -------
    nodes      : {nid: (x, y)}
    tris       : [(eid, n1, n2, n3)]
    crack_pairs: [(nid_below, nid_above, y, x)]
    crack_rows : set of j-indices that are crack rows
    """
    dx = W / max(nx, 1)
    dy = H / max(ny, 1)
    grid_ys = [j * dy for j in range(ny + 1)]

    crack_rows = set()
    for yc in crack_ys:
        if 0 < yc < H:
            best_j = min(range(1, ny), key=lambda j: abs(grid_ys[j] - yc))
            crack_rows.add(best_j)

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
        # For a horizontal crack: tangent = (1, 0), normal = (0, 1)
        # Stored as (nb, na, y, x, tx, ty, cnx, cny) so the runner can build
        # local-axis opening/slip without assuming global X/Y alignment.
        tx, ty, cnx, cny = 1.0, 0.0, 0.0, 1.0
        for i in range(nx + 1):
            x = round(i * dx, 8)
            crack_pairs.append((
                node_grid[(i, j, 'below')], node_grid[(i, j, 'above')],
                y, x, tx, ty, cnx, cny,
            ))

    return nodes, tris, crack_pairs, crack_rows


# =============================================================================
# Interactive Mesh Canvas
# =============================================================================
class PanelMeshCanvas(QWidget):
    """
    2D triangulated mesh with interactive node selection.

    Modes
    -----
    MODE_SELECT : click a node to select it (for BC / load assignment)
    MODE_CRACK  : click at any Y to add / remove a pending crack line
    """
    node_clicked    = pyqtSignal(int)
    crack_y_added   = pyqtSignal(float)
    crack_y_removed = pyqtSignal(float)

    MODE_SELECT = "select"
    MODE_CRACK  = "crack"

    def __init__(self):
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
        self.mode         = self.MODE_SELECT
        self._hover_model = None
        self._pending_crack_ys = []
        self._below_nodes = set()    # nids on the BELOW side of cracks (orange)
        self._above_nodes = set()    # nids on the ABOVE side of cracks (violet)
        self.show_crack_links = True # draw short lines between each (below,above) pair
        self.setMouseTracking(True)

    # ── coord transforms ──────────────────────────────────────────────────────
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

    # ── public API ────────────────────────────────────────────────────────────
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
        self.setCursor(Qt.CrossCursor if mode == self.MODE_CRACK else Qt.ArrowCursor)
        self.update()

    # ── events ────────────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton: return
        px, py = event.x(), event.y()
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

    def mouseMoveEvent(self, event):
        self._hover_model = self._to_model(event.x(), event.y()); self.update()

    def leaveEvent(self, event):
        self._hover_model = None; self.update()

    # ── paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        p.fillRect(0, 0, W, H, QColor(BG_PANEL))

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

        # Crack lines (red thick)
        if self.crack_pairs:
            by_y = {}
            for cp in self.crack_pairs:
                by_y.setdefault(round(cp[2], 6), []).append(cp[3])
            p.setPen(QPen(QColor(C3), 3))
            for y, xs in sorted(by_y.items()):
                xs_s = sorted(xs)
                if len(xs_s) >= 2:
                    p.drawLine(*self._to_px(xs_s[0], y), *self._to_px(xs_s[-1], y))

        # Crack links: short lines between each (below, above) pair
        # Drawn as small "X" marks to show the interface connection
        if self.show_crack_links and self.crack_pairs:
            p.setPen(QPen(QColor("#ff5555"), 1.5))
            for cp in self.crack_pairs:
                nb, na = cp[0], cp[1]
                if nb in self.nodes and na in self.nodes:
                    px1, py1 = self._to_px(*self.nodes[nb])
                    # Offset the above node marker slightly upward to show pair
                    p.drawLine(px1 - 3, py1 - 3, px1 + 3, py1 + 3)
                    p.drawLine(px1 - 3, py1 + 3, px1 + 3, py1 - 3)

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

        # Stats bar
        p.setPen(QPen(QColor(C4), 1)); p.setFont(QFont("Consolas", 8))
        nn = len(self.nodes); nt = len(self.tris); nc = len(self.crack_pairs)
        p.drawText(6, H - 6, f"nodes={nn}  tri={nt}  crack_links={nc}")

        # Legend
        legend = [
            ("●", C1, "Node"), ("●", C2, "Selected"),
            ("●", C4, "Fixed BC"), ("●", C3, "Loaded"),
            ("●", CRACK_BELOW, "Crack ↓"), ("●", CRACK_ABOVE, "Crack ↑"),
        ]
        lx_ = W - 120
        for i, (sym, col, txt) in enumerate(legend):
            p.setPen(QPen(QColor(col), 1))
            p.drawText(lx_, H - 6 - i * 13, f"{sym} {txt}")
        p.end()

    def _paint_empty(self, p, W, H):
        if self.panel_W > 0 and self.panel_H > 0:
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


# =============================================================================
# Tab 1: Geometry
# =============================================================================
class GeometryTab(QWidget):
    def __init__(self):
        super().__init__()
        root = QHBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # ── left scroll panel ─────────────────────────────────────────────────
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setMaximumWidth(460)
        left = QWidget(); lv = QVBoxLayout(left)
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

        # Mesh density
        grp_mesh = QGroupBox("Mesh Density")
        fm = QFormLayout(grp_mesh); fm.setSpacing(6)
        self.sb_nx = isb(6,  1, 200, tip="Divisions in X")
        self.sb_ny = isb(12, 1, 200, tip="Divisions in Y")
        fm.addRow("nx (X divisions):", self.sb_nx)
        fm.addRow("ny (Y divisions):", self.sb_ny)
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

        btn_row.addWidget(self.btn_gen, stretch=2)
        btn_row.addWidget(self.btn_validate, stretch=1)
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
        row_inp = QHBoxLayout()
        self.txt_crack_y = QLineEdit()
        self.txt_crack_y.setPlaceholderText("e.g. 0.5, 1.0, 1.5  (m from base)")
        self.btn_crack_mode = QPushButton("✏ Crack Mode")
        self.btn_crack_mode.setObjectName("flat")
        self.btn_crack_mode.setCheckable(True)
        self.btn_crack_mode.setToolTip("Toggle crack placement mode: click canvas to add/remove crack Y")
        row_inp.addWidget(self.txt_crack_y, stretch=1)
        row_inp.addWidget(self.btn_crack_mode)
        vc.addLayout(row_inp)
        self.lbl_crack_ys = mk_lbl("No crack lines defined.", "sub")
        vc.addWidget(self.lbl_crack_ys)
        lv.addWidget(grp_crack)

        # Boundary conditions
        grp_bc = QGroupBox("Boundary Conditions")
        vbc = QVBoxLayout(grp_bc); vbc.setSpacing(6)
        vbc.addWidget(mk_lbl(
            "Click a node on the canvas, then assign its fixity below.\n"
            "Use Quick-assign buttons to fix the full bottom or top edge.", "sub"))

        # Quick-assign buttons
        row_qa = QHBoxLayout()
        self.btn_fix_bot = QPushButton("Fix Bottom (ux=uy=0)")
        self.btn_fix_bot.setObjectName("flat")
        self.btn_roller_top = QPushButton("Roller Top (ux=0)")
        self.btn_roller_top.setObjectName("flat")
        self.btn_clr_bc = QPushButton("Clear All BC")
        self.btn_clr_bc.setObjectName("danger")
        row_qa.addWidget(self.btn_fix_bot)
        row_qa.addWidget(self.btn_roller_top)
        row_qa.addWidget(self.btn_clr_bc)
        vbc.addLayout(row_qa)

        # Selected node BC assignment
        self.lbl_sel_node = mk_lbl("No node selected.", "sub")
        vbc.addWidget(self.lbl_sel_node)
        node_bc_row = QHBoxLayout()
        self.chk_fix_x = QCheckBox("Fix X")
        self.chk_fix_y = QCheckBox("Fix Y")
        self.btn_apply_bc = QPushButton("Apply BC")
        self.btn_apply_bc.setEnabled(False)
        self.btn_clear_node_bc = QPushButton("Clear Node BC")
        self.btn_clear_node_bc.setObjectName("flat"); self.btn_clear_node_bc.setEnabled(False)
        node_bc_row.addWidget(self.chk_fix_x)
        node_bc_row.addWidget(self.chk_fix_y)
        node_bc_row.addWidget(self.btn_apply_bc)
        node_bc_row.addWidget(self.btn_clear_node_bc)
        node_bc_row.addStretch()
        vbc.addLayout(node_bc_row)

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
        load_row = QHBoxLayout()
        load_row.addWidget(mk_lbl("Fx (kN):"))
        self.sb_node_Fx = dsb(0., -1e9, 1e9, 3, 10., w=100)
        load_row.addWidget(self.sb_node_Fx)
        load_row.addWidget(mk_lbl("  Fy (kN):"))
        self.sb_node_Fy = dsb(0., -1e9, 1e9, 3, 10., w=100)
        load_row.addWidget(self.sb_node_Fy)
        self.btn_apply_load = QPushButton("Apply Load")
        self.btn_apply_load.setEnabled(False)
        self.btn_clear_node_load = QPushButton("Clear")
        self.btn_clear_node_load.setObjectName("flat"); self.btn_clear_node_load.setEnabled(False)
        load_row.addWidget(self.btn_apply_load)
        load_row.addWidget(self.btn_clear_node_load)
        load_row.addStretch()
        vld.addLayout(load_row)

        self.tbl_loads = QTableWidget(0, 3)
        self.tbl_loads.setHorizontalHeaderLabels(["Node", "Fx (kN)", "Fy (kN)"])
        self.tbl_loads.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_loads.setMaximumHeight(70)
        vld.addWidget(self.tbl_loads)
        lv.addWidget(grp_load)
        lv.addStretch()

        scroll.setWidget(left)
        root.addWidget(scroll)

        # ── right panel: mesh canvas ──────────────────────────────────────────
        right = QWidget(); right.setStyleSheet(f"background:{BG_PANEL};")
        rv = QVBoxLayout(right); rv.setContentsMargins(8, 16, 16, 16); rv.setSpacing(6)
        mode_row = QHBoxLayout()
        self.lbl_canvas_hint = mk_lbl("Select mode: click a node to assign BC / load", "sub")
        self.chk_show_ids = QCheckBox("Node IDs")
        self.chk_show_ids.setChecked(True)
        self.chk_show_crack_links = QCheckBox("Crack Links")
        self.chk_show_crack_links.setChecked(True)
        mode_row.addWidget(self.lbl_canvas_hint, stretch=1)
        mode_row.addWidget(self.chk_show_ids)
        mode_row.addWidget(self.chk_show_crack_links)
        rv.addLayout(mode_row)
        self.canvas = PanelMeshCanvas()
        rv.addWidget(self.canvas, stretch=1)
        root.addWidget(right, stretch=1)

        # internal state
        self._mesh_data = None   # {nodes, tris, crack_pairs, crack_rows, W, H, nx, ny, crack_ys}
        self._bc_nodes  = {}     # {nid: (fix_x, fix_y)}
        self._load_nodes = {}    # {nid: (Fx, Fy)}
        self._selected_node = None
        self._crack_ys = []

        # wire
        self.btn_gen.clicked.connect(self._generate)
        self.btn_validate.clicked.connect(self._validate_mesh)
        self.btn_crack_mode.toggled.connect(self._toggle_crack_mode)
        self.txt_crack_y.editingFinished.connect(self._sync_crack_ys_from_text)
        self.canvas.node_clicked.connect(self._on_node_clicked)
        self.canvas.crack_y_added.connect(self._add_crack_y)
        self.canvas.crack_y_removed.connect(self._remove_crack_y)
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
        self.chk_show_crack_links.toggled.connect(self._toggle_crack_links)
        for sb in [self.sb_W, self.sb_H]:
            sb.valueChanged.connect(self._on_dim_change)
        self._on_dim_change()

    # ── handlers ──────────────────────────────────────────────────────────────
    def _on_dim_change(self):
        self.canvas.set_pending_cracks(self._crack_ys, self.sb_W.value(), self.sb_H.value())

    def _toggle_crack_mode(self, on):
        if on:
            self.canvas.set_mode(PanelMeshCanvas.MODE_CRACK)
            self.lbl_canvas_hint.setText("Crack mode: click canvas to add/remove crack line. Right-click = node select.")
        else:
            self.canvas.set_mode(PanelMeshCanvas.MODE_SELECT)
            self.lbl_canvas_hint.setText("Select mode: click a node to assign BC / load")

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
        ys = []
        for s in self.txt_crack_y.text().replace(";", ",").split(","):
            s = s.strip()
            if s:
                try: ys.append(float(s))
                except ValueError: pass
        self._crack_ys = sorted(set(ys))
        self._refresh_crack_label()
        self.canvas.set_pending_cracks(self._crack_ys, self.sb_W.value(), self.sb_H.value())

    def _update_crack_text(self):
        self.txt_crack_y.blockSignals(True)
        self.txt_crack_y.setText(", ".join(f"{y:.3f}" for y in self._crack_ys))
        self.txt_crack_y.blockSignals(False)

    def _refresh_crack_label(self):
        if self._crack_ys:
            self.lbl_crack_ys.setText(f"{len(self._crack_ys)} crack line(s) at Y = " +
                                       ", ".join(f"{y:.3f}" for y in self._crack_ys))
        else:
            self.lbl_crack_ys.setText("No crack lines defined.")

    def _generate(self):
        # Merge any Y values the user typed but hasn't committed yet
        txt = self.txt_crack_y.text().strip()
        if txt:
            parsed = []
            for s in txt.replace(";", ",").split(","):
                s = s.strip()
                if s:
                    try: parsed.append(float(s))
                    except ValueError: pass
            if parsed:
                self._crack_ys = sorted(set(parsed))
                self._refresh_crack_label()
        # Keep existing _crack_ys if text field is empty (canvas-click values)
        W = self.sb_W.value(); H = self.sb_H.value()
        nx = self.sb_nx.value(); ny = self.sb_ny.value()
        nodes, tris, crack_pairs, crack_rows = generate_panel_mesh(W, H, nx, ny, self._crack_ys)
        self._mesh_data = dict(nodes=nodes, tris=tris, crack_pairs=crack_pairs,
                               crack_rows=crack_rows, W=W, H=H, nx=nx, ny=ny,
                               crack_ys=self._crack_ys)
        self._bc_nodes = {}; self._load_nodes = {}
        self.canvas.set_mesh(nodes, tris, crack_pairs, crack_rows, W, H)
        self.canvas.set_bc_nodes(self._bc_nodes)
        self.canvas.set_load_nodes(self._load_nodes)
        nn = len(nodes); nt = len(tris); nc = len(crack_pairs)
        self.lbl_mesh_info.setText(
            f"Mesh ready: {nn} nodes, {nt} triangles, {nc} crack links, "
            f"{len(self._crack_ys)} crack line(s).")
        self._update_bc_table(); self._update_load_table()

    def _on_node_clicked(self, nid):
        self._selected_node = nid
        md = self._mesh_data
        if md is None: return
        x, y = md["nodes"][nid]
        self.lbl_sel_node.setText(f"Node #{nid}  (x={x:.4f}, y={y:.4f})")
        bc = self._bc_nodes.get(nid, (0, 0))
        self.chk_fix_x.setChecked(bool(bc[0])); self.chk_fix_y.setChecked(bool(bc[1]))
        ld = self._load_nodes.get(nid, (0., 0.))
        self.sb_node_Fx.setValue(ld[0]); self.sb_node_Fy.setValue(ld[1])
        self.btn_apply_bc.setEnabled(True); self.btn_clear_node_bc.setEnabled(True)
        self.btn_apply_load.setEnabled(True); self.btn_clear_node_load.setEnabled(True)

    def _apply_bc_to_node(self):
        if self._selected_node is None or self._mesh_data is None: return
        nid = self._selected_node
        fx = 1 if self.chk_fix_x.isChecked() else 0
        fy = 1 if self.chk_fix_y.isChecked() else 0
        if fx or fy:
            self._bc_nodes[nid] = (fx, fy)
        else:
            self._bc_nodes.pop(nid, None)
        self.canvas.set_bc_nodes(self._bc_nodes); self._update_bc_table()

    def _clear_node_bc(self):
        if self._selected_node is None: return
        self._bc_nodes.pop(self._selected_node, None)
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
            self._load_nodes[nid] = (Fx, Fy)
        else:
            self._load_nodes.pop(nid, None)
        self.canvas.set_load_nodes(self._load_nodes); self._update_load_table()

    def _clear_node_load(self):
        if self._selected_node is None: return
        self._load_nodes.pop(self._selected_node, None)
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

    def _update_bc_table(self):
        self.tbl_bc.setRowCount(len(self._bc_nodes))
        for i, (nid, (fx, fy)) in enumerate(sorted(self._bc_nodes.items())):
            self.tbl_bc.setItem(i, 0, QTableWidgetItem(str(nid)))
            self.tbl_bc.setItem(i, 1, QTableWidgetItem("✓" if fx else ""))
            self.tbl_bc.setItem(i, 2, QTableWidgetItem("✓" if fy else ""))

    def _update_load_table(self):
        self.tbl_loads.setRowCount(len(self._load_nodes))
        for i, (nid, (Fx, Fy)) in enumerate(sorted(self._load_nodes.items())):
            self.tbl_loads.setItem(i, 0, QTableWidgetItem(str(nid)))
            self.tbl_loads.setItem(i, 1, QTableWidgetItem(f"{Fx:.3f}"))
            self.tbl_loads.setItem(i, 2, QTableWidgetItem(f"{Fy:.3f}"))

    def _toggle_ids(self, on):
        self.canvas.show_ids = on; self.canvas.update()

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

    # ── public interface ──────────────────────────────────────────────────────
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
        md = self._mesh_data or {}
        p = {
            "panel_W":  self.sb_W.value(),
            "panel_H":  self.sb_H.value(),
            "panel_t":  self.sb_t.value(),
            "panel_Ec": self.sb_Ec.value(),
            "panel_nu": self.sb_nu.value(),
            "crack_ys": list(self._crack_ys),
        }
        if md:
            p["mesh_nodes"]       = {str(k): list(v) for k, v in md["nodes"].items()}
            p["mesh_tris"]        = [[e, n1, n2, n3] for e, n1, n2, n3 in md["tris"]]
            p["mesh_crack_pairs"] = [list(cp) for cp in md["crack_pairs"]]
        p["bc_nodes"]    = {str(k): list(v) for k, v in self._bc_nodes.items()}
        p["load_nodes"]  = {str(k): list(v) for k, v in self._load_nodes.items()}
        return p

    def get_mesh_data(self):
        return self._mesh_data


# =============================================================================
# Tab 2: Crack Material Parameters
# =============================================================================
class CrackMaterialTab(QWidget):
    def __init__(self):
        super().__init__()
        self._geo_ref = None   # set by MainWindow after construction
        outer = QVBoxLayout(self); outer.setContentsMargins(16, 16, 16, 16); outer.setSpacing(10)
        outer.addWidget(mk_lbl("Crack Interface Materials", "heading"))
        outer.addWidget(mk_lbl(
            "Each crack line gets its own material model and stiffness parameters.\n"
            "Click Refresh to load crack lines from the Geometry tab.", "sub"))

        # Controls
        ctrl = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh from Geometry")
        self.btn_refresh.setObjectName("amber")
        self.btn_apply_all = QPushButton("Apply Material to All")
        self.btn_apply_all.setObjectName("flat")
        ctrl.addWidget(self.btn_refresh)
        ctrl.addWidget(self.btn_apply_all)
        ctrl.addStretch()
        outer.addLayout(ctrl)

        # Global template
        grp_tmpl = QGroupBox("Template (applied to all cracks)")
        ft = QFormLayout(grp_tmpl); ft.setSpacing(8)
        self.cmb_mat_tmpl = QComboBox()
        self.cmb_mat_tmpl.addItems([
            "MultiSurfCrack2D",  # NEW: Your custom multi-surface model
            "Elastic",
            "ElasticPPGap",
            "CustomBilinear"
        ])
        self.cmb_mat_tmpl.setToolTip(
            "MultiSurfCrack2D: plasticity-based multi-yield-surface crack model (requires OpenSees compilation)\n"
            "Elastic: linear spring (kn/kt)\n"
            "ElasticPPGap: elastic + perfect plastic gap spring\n"
            "CustomBilinear: piecewise linear force-displacement")

        self.sb_kn_tmpl  = dsb(210.0, 1e-6, 1e9, 2, 10., w=130, tip="Normal stiffness kn (kN/m per link)")
        self.sb_kt_tmpl  = dsb(5.95,  1e-6, 1e9, 3, 1.,  w=130, tip="Shear stiffness kt (kN/m per link)")
        self.sb_gap_tmpl = dsb(0.001, 0., 10.,  4, 0.001, w=130, tip="Gap before spring engages (m) — ElasticPPGap only")
        self.sb_eta_tmpl = dsb(0.02,  0., 1.,   3, 0.01,  w=130, tip="Hardening ratio η — ElasticPPGap only")

        # Auto kn/kt from concrete
        auto_row = QHBoxLayout()
        self.sb_fc_auto = dsb(30., 1., 200., 1, 1., w=100, tip="f'c (MPa) for auto kn/kt")
        self.sb_w0_auto = dsb(0.1, 0.001, 5., 3, 0.01, w=100, tip="w0 (mm) for auto kn/kt")
        self.btn_auto_knkt = QPushButton("Auto kn/kt")
        self.btn_auto_knkt.setObjectName("flat")
        self.btn_auto_knkt.setToolTip("Compute kn/kt from Divakar Eq.31/32")
        auto_row.addWidget(mk_lbl("f'c:")); auto_row.addWidget(self.sb_fc_auto)
        auto_row.addWidget(mk_lbl("  w0 (mm):")); auto_row.addWidget(self.sb_w0_auto)
        auto_row.addWidget(self.btn_auto_knkt); auto_row.addStretch()

        ft.addRow("Material type:", self.cmb_mat_tmpl)
        ft.addRow("kn (kN/m):",     self.sb_kn_tmpl)
        ft.addRow("kt (kN/m):",     self.sb_kt_tmpl)
        ft.addRow("gap (m):",        self.sb_gap_tmpl)
        ft.addRow("η hardening:",    self.sb_eta_tmpl)
        ft.addRow("",                auto_row)
        outer.addWidget(grp_tmpl)

        # Per-crack table
        grp_tbl = QGroupBox("Per-Crack Parameters")
        vt = QVBoxLayout(grp_tbl); vt.setSpacing(6)
        vt.addWidget(mk_lbl(
            "Double-click a cell to edit. Material: MultiSurfCrack2D / Elastic / ElasticPPGap / CustomBilinear.\n"
            "For MultiSurfCrack2D: set kn=normal stiffness, kt=shear stiffness. Additional parameters auto-filled.", "sub"))
        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["Y pos (m)", "Material", "kn (kN/m)", "kt (kN/m)", "gap (m)", "η"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        vt.addWidget(self.tbl, stretch=1)
        outer.addWidget(grp_tbl, stretch=1)

        # Wire
        self.btn_refresh.clicked.connect(self.refresh_from_geometry)
        self.btn_apply_all.clicked.connect(self._apply_template_to_all)
        self.btn_auto_knkt.clicked.connect(self._auto_kn_kt)

    def _auto_kn_kt(self):
        w = max(self.sb_w0_auto.value(), 0.001)
        fc = self.sb_fc_auto.value()
        kn = (2. + w) / w
        kt = 0.00595 * (25.4 / w)**1.6148 * (fc / 34.5)**0.193
        self.sb_kn_tmpl.setValue(kn)
        self.sb_kt_tmpl.setValue(kt)

    def _apply_template_to_all(self):
        mat  = self.cmb_mat_tmpl.currentText()
        kn   = self.sb_kn_tmpl.value()
        kt   = self.sb_kt_tmpl.value()
        gap  = self.sb_gap_tmpl.value()
        eta  = self.sb_eta_tmpl.value()
        for r in range(self.tbl.rowCount()):
            self.tbl.item(r, 1).setText(mat)
            self.tbl.item(r, 2).setText(f"{kn:.3f}")
            self.tbl.item(r, 3).setText(f"{kt:.3f}")
            self.tbl.item(r, 4).setText(f"{gap:.4f}")
            self.tbl.item(r, 5).setText(f"{eta:.3f}")

    def set_geo_ref(self, geo_tab):
        self._geo_ref = geo_tab

    def refresh_from_geometry(self, geo_tab=None):
        geo = geo_tab or self._geo_ref
        if geo is None: return
        md = geo.get_mesh_data()
        if md is None:
            QMessageBox.information(self, "No Mesh", "Generate a mesh on the Geometry tab first.")
            return
        crack_ys = sorted(set(round(cp[2], 6) for cp in md["crack_pairs"]))
        mat  = self.cmb_mat_tmpl.currentText()
        kn   = self.sb_kn_tmpl.value()
        kt   = self.sb_kt_tmpl.value()
        gap  = self.sb_gap_tmpl.value()
        eta  = self.sb_eta_tmpl.value()
        # Preserve existing edits
        existing = {}
        for r in range(self.tbl.rowCount()):
            try:
                y = float(self.tbl.item(r, 0).text())
                existing[round(y, 6)] = r
            except Exception:
                pass
        self.tbl.setRowCount(len(crack_ys))
        for i, y in enumerate(crack_ys):
            yr = round(y, 6)
            if yr in existing:
                old_r = existing[yr]
                row_data = [self.tbl.item(old_r, c).text() for c in range(6)]
                for c, txt in enumerate(row_data):
                    self.tbl.setItem(i, c, QTableWidgetItem(txt))
            else:
                self.tbl.setItem(i, 0, QTableWidgetItem(f"{y:.4f}"))
                self.tbl.setItem(i, 1, QTableWidgetItem(mat))
                self.tbl.setItem(i, 2, QTableWidgetItem(f"{kn:.3f}"))
                self.tbl.setItem(i, 3, QTableWidgetItem(f"{kt:.3f}"))
                self.tbl.setItem(i, 4, QTableWidgetItem(f"{gap:.4f}"))
                self.tbl.setItem(i, 5, QTableWidgetItem(f"{eta:.3f}"))

    def get_params(self):
        data = []
        for r in range(self.tbl.rowCount()):
            try:
                data.append({
                    "y":        float(self.tbl.item(r, 0).text()),
                    "mat_type": self.tbl.item(r, 1).text(),
                    "kn":       float(self.tbl.item(r, 2).text()),
                    "kt":       float(self.tbl.item(r, 3).text()),
                    "gap":      float(self.tbl.item(r, 4).text()),
                    "eta":      float(self.tbl.item(r, 5).text()),
                })
            except Exception:
                pass
        return {"crack_mat_data": data}


# =============================================================================
# Tab 3: Analysis Settings
# =============================================================================
class AnalysisTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self); outer.setContentsMargins(16, 16, 16, 16); outer.setSpacing(10)
        outer.addWidget(mk_lbl("Analysis Configuration", "heading"))

        grp = QGroupBox("Static Analysis")
        form = QFormLayout(grp); form.setSpacing(8)

        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["DisplacementControl", "LoadControl"])
        self.sb_di  = dsb(0.0005, 1e-7, 1e3, 6, 0.0001,
                          tip="Displacement increment per step (m, DisplacementControl)")
        self.sb_tgt = dsb(0.05,   0.0,  1e4, 6, 0.01,
                          tip="Target total displacement (m, DisplacementControl)")
        self.sb_li  = dsb(0.01,   1e-7, 1.0, 6, 0.01,
                          tip="Load increment fraction per step (LoadControl, 0.01 = 1% of total)")
        self.cmb_alg = QComboBox()
        self.cmb_alg.addItems(["NewtonLineSearch", "Newton", "KrylovNewton", "ModifiedNewton"])
        self.sb_tol  = dsb(1e-8,  1e-14, 1e-2, 12, 1e-9,  tip="Convergence tolerance (NormUnbalance)")
        self.sb_iter = isb(400, 1, 5000,                    tip="Max iterations per step")
        self.sb_lam  = dsb(50., 0.1, 1e9, 1, 5.,           tip="Stop if load factor exceeds this value")

        form.addRow("Analysis type:",       self.cmb_type)
        form.addRow("Disp. increment (m):", self.sb_di)
        form.addRow("Target disp. (m):",    self.sb_tgt)
        form.addRow("Load incr. fraction:", self.sb_li)
        form.addRow("Algorithm:",           self.cmb_alg)
        form.addRow("Tolerance:",           self.sb_tol)
        form.addRow("Max iterations:",      self.sb_iter)
        form.addRow("Load factor cap λ:",   self.sb_lam)

        outer.addWidget(grp)

        note = mk_lbl(
            "DisplacementControl: applies incremental displacement at the load DOF.\n"
            "LoadControl: applies incremental force up to the pattern load.\n"
            "Algorithm fallback order: NewtonLineSearch → KrylovNewton → ModifiedNewton → Newton.\n"
            "Step size is halved up to 12 times if convergence fails.", "sub")
        note.setWordWrap(True)
        outer.addWidget(note)
        outer.addStretch()

    def get_params(self):
        return {
            "analysis_type": self.cmb_type.currentText(),
            "disp_incr":     self.sb_di.value(),
            "target_disp":   self.sb_tgt.value(),
            "load_incr":     self.sb_li.value(),
            "algorithm":     self.cmb_alg.currentText(),
            "tol":           self.sb_tol.value(),
            "max_iter":      self.sb_iter.value(),
            "max_load_factor": self.sb_lam.value(),
        }


# =============================================================================
# Tab 4: Run
# =============================================================================
class RunTab(QWidget):
    run_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self); outer.setContentsMargins(16, 16, 16, 16); outer.setSpacing(10)
        outer.addWidget(mk_lbl("Run Analysis  (Windows GUI → WSL OpenSeesPy)", "heading"))

        grp_wsl = QGroupBox("WSL Environment")
        wf = QFormLayout(grp_wsl); wf.setSpacing(6)
        self.wsl_activate = QLineEdit("source ~/ops_env/bin/activate")
        self.wsl_activate.setToolTip(
            "WSL bash command to activate your Python environment with OpenSeesPy.\n"
            "Examples:\n"
            "  source ~/ops_env/bin/activate   (virtualenv)\n"
            "  conda activate opensees          (conda)\n"
            "  true                             (system python with openseespy)")
        wf.addRow("Activate cmd:", self.wsl_activate)
        outer.addWidget(grp_wsl)

        brow = QHBoxLayout()
        self.btn_run   = QPushButton("▶  Run Analysis")
        self.btn_run.setObjectName("success"); self.btn_run.setMinimumHeight(40)
        self.btn_validate_build = QPushButton("✓ Validate OpenSees Build")
        self.btn_validate_build.setObjectName("flat")
        self.btn_validate_build.setToolTip("Check if OpenSees has MultiSurfCrack2D and proper interface element support")
        self.btn_clear = QPushButton("Clear Console"); self.btn_clear.setObjectName("flat")
        brow.addWidget(self.btn_run); brow.addWidget(self.btn_validate_build); brow.addWidget(self.btn_clear); brow.addStretch()
        outer.addLayout(brow)

        self.lbl_status = mk_lbl("Ready. Configure Geometry → Crack Materials → Analysis → Run.", "sub")
        outer.addWidget(self.lbl_status)

        grp_con = QGroupBox("Console Output")
        lc = QVBoxLayout(grp_con)
        self.console = QTextEdit(); self.console.setReadOnly(True); self.console.setMinimumHeight(320)
        lc.addWidget(self.console)
        outer.addWidget(grp_con, stretch=1)

        self.btn_run.clicked.connect(self.run_requested.emit)
        self.btn_validate_build.clicked.connect(self._validate_build)
        self.btn_clear.clicked.connect(self.console.clear)

    def _validate_build(self):
        """Run OpenSees build validation check."""
        self.append("\n" + "="*70)
        self.append("VALIDATING OpenSees BUILD")
        self.append("="*70)
        success, msg, elem_type = test_multisurfcrack2d_support()
        self.append(f"Result: {'PASS' if success else 'FAIL'}")
        self.append(f"Message: {msg}")
        self.append(f"Element type: {elem_type}")
        self.append("="*70 + "\n")

        if success:
            QMessageBox.information(self, "Build Validation",
                                  f"✓ OpenSees is ready for MultiSurfCrack2D\n\nElement type: {elem_type}\n\n{msg}")
        else:
            QMessageBox.warning(self, "Build Validation Failed",
                              f"✗ OpenSees does not have required support\n\n{msg}")

    def get_activate(self): return self.wsl_activate.text().strip() or "true"

    def append(self, msg):
        self.console.append(msg)
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    def set_status(self, msg, ok=True):
        self.lbl_status.setStyleSheet(f"color:{C2 if ok else C3};font-weight:bold;")
        self.lbl_status.setText(msg)


# =============================================================================
# Tab 5: Results
# =============================================================================
class ResultsTab(QWidget):
    PLOT_OPTS = [
        "Force–Displacement",
        "Crack Opening History",
        "Crack Slip History",
        "Crack Hysteresis (Slip vs Force)",
        "Deformed Mesh",
        "Displacement Magnitude Contour",
    ]
    COLORS = ["#58a6ff", "#3fb950", "#f78166", "#d2a679", "#c9d1d9", "#8b949e"]

    def __init__(self):
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
        for w in [mk_lbl("Plot:"), self.cmb_plot,
                  mk_lbl("  Crack:"), self.cmb_crack,
                  mk_lbl("  Scale ×"), self.sb_scale,
                  self.btn_rp, self.btn_save, self.btn_csv]:
            ctrl.addWidget(w)
        ctrl.addStretch()
        outer.addLayout(ctrl)

        self.fig = Figure(facecolor=BG_DEEP, tight_layout=True)
        self.ax  = self.fig.add_subplot(111)
        self._style_ax()
        self.canv = FigureCanvas(self.fig)
        self.tb   = NavigationToolbar(self.canv, self)
        self.tb.setStyleSheet(f"background:{BG_PANEL};color:{TXT};")
        outer.addWidget(self.tb); outer.addWidget(self.canv, stretch=1)

        self._reset()
        self.cmb_plot.currentTextChanged.connect(self.replot)
        self.cmb_crack.currentIndexChanged.connect(self.replot)
        self.sb_scale.valueChanged.connect(self.replot)
        self.btn_rp.clicked.connect(self.replot)
        self.btn_save.clicked.connect(self._save)
        self.btn_csv.clicked.connect(self._csv)

    def _style_ax(self):
        self.ax.set_facecolor(BG_PANEL)
        self.ax.tick_params(colors=TXTS, labelsize=9)
        self.ax.xaxis.label.set_color(TXT); self.ax.yaxis.label.set_color(TXT)
        self.ax.title.set_color(C1)
        for s in self.ax.spines.values(): s.set_edgecolor(BORDER)
        self.ax.grid(True, alpha=0.15, color=BORDER, linestyle="--")

    def _reset(self):
        self._disp = np.array([]); self._force = np.array([])
        self._crack_pos = np.array([])
        self._co = []; self._cs = []
        self._mesh_nodes = {}; self._mesh_tris = []
        self._node_disp_last = {}

    def set_results(self, r):
        self._disp  = r["disp"]; self._force = r["force"]
        self._crack_pos = r.get("crack_positions", np.array([]))
        self._co    = r.get("crack_openings", [])
        self._cs    = r.get("crack_slips", [])
        self._mesh_nodes     = r.get("mesh_nodes", {})
        self._mesh_tris      = r.get("mesh_tris", [])
        self._node_disp_last = r.get("node_disp_last", {})
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

        self.canv.draw()

    def _plot_deformed(self):
        if not self._mesh_nodes or not self._mesh_tris:
            self.ax.set_title("No mesh data (run analysis first)"); return
        scale = self.sb_scale.value()
        nodes = self._mesh_nodes; nd = self._node_disp_last
        # Undeformed (faint)
        for _, n1, n2, n3 in self._mesh_tris:
            xs = [nodes[n][0] for n in (n1, n2, n3, n1)]
            ys = [nodes[n][1] for n in (n1, n2, n3, n1)]
            self.ax.plot(xs, ys, color="#30363d", lw=0.4, zorder=1)
        # Deformed (bright)
        for _, n1, n2, n3 in self._mesh_tris:
            xs = [nodes[n][0] + scale * nd.get(n, [0, 0])[0] for n in (n1, n2, n3, n1)]
            ys = [nodes[n][1] + scale * nd.get(n, [0, 0])[1] for n in (n1, n2, n3, n1)]
            self.ax.plot(xs, ys, color=C1, lw=0.7, zorder=2)
        self.ax.set_aspect("equal"); self.ax.set_xlabel("X (m)"); self.ax.set_ylabel("Y (m)")
        self.ax.set_title(f"Deformed Mesh  (scale ×{scale:.0f})")
        self.ax.text(0.02, 0.97, f"scale ×{scale:.0f}", transform=self.ax.transAxes,
                     va="top", color=TXTS, fontsize=9, family="monospace")

    def _plot_contour(self):
        if not self._mesh_nodes or not self._node_disp_last:
            self.ax.set_title("No displacement data (run analysis first)"); return
        nodes = self._mesh_nodes; nd = self._node_disp_last
        nids  = sorted(nodes.keys())
        nid_idx = {n: i for i, n in enumerate(nids)}
        xs = np.array([nodes[n][0] for n in nids])
        ys = np.array([nodes[n][1] for n in nids])
        mag = np.array([math.hypot(*nd.get(n, [0., 0.])) for n in nids])
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


# =============================================================================
# Tab 6: Script Export
# =============================================================================
class ScriptTab(QWidget):
    def __init__(self):
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


# =============================================================================
# OpenSees Validation & Element Creation Helper
# =============================================================================
def test_multisurfcrack2d_support():
    """
    Test if OpenSees build supports MultiSurfCrack2D and proper interface elements.
    Returns: (success: bool, message: str, element_type: str)
      element_type = 'zeroLengthND' or 'zeroLength' or 'unknown'
    """
    try:
        import openseespy.opensees as ops
        ops.wipe()
        ops.model('basic', '-ndm', 2, '-ndf', 2)

        # Create dummy nodes
        ops.node(1, 0.0, 0.0)
        ops.node(2, 0.0, 0.0)
        ops.fix(1, 1, 1)

        # Test 1: Can we create MultiSurfCrack2D?
        try:
            ops.nDMaterial('MultiSurfCrack2D', 100,
                          210, 5.95, 0.0,
                          210, 5.95, 0.0,
                          30, 25, 5, 1, 0.5, 0.3, 0.5, 0.7, 0.5,
                          0.3, 1.0, 0.785, 0.01, 0)
        except Exception as e_mat:
            return (False,
                   f"MultiSurfCrack2D material not available.\n"
                   f"OpenSees Error: {str(e_mat)}\n"
                   f"Fix: Recompile OpenSees with multi-surf-crack2d.cpp/.h included.",
                   'unknown')

        # Test 2: Try zeroLengthND (preferred)
        try:
            ops.element('zeroLengthND', 1001, 1, 2, 100)
            ops.wipe()
            ops.model('basic', '-ndm', 2, '-ndf', 2)
            ops.node(1, 0.0, 0.0)
            ops.node(2, 0.0, 0.0)
            ops.fix(1, 1, 1)
            return (True,
                   "OK: MultiSurfCrack2D + zeroLengthND (preferred element).",
                   'zeroLengthND')
        except Exception as e_nd:
            # Test 3: zeroLength with NDMaterial (may not work)
            try:
                ops.wipe()
                ops.model('basic', '-ndm', 2, '-ndf', 2)
                ops.node(1, 0.0, 0.0)
                ops.node(2, 0.0, 0.0)
                ops.fix(1, 1, 1)
                ops.nDMaterial('MultiSurfCrack2D', 100,
                              210, 5.95, 0.0,
                              210, 5.95, 0.0,
                              30, 25, 5, 1, 0.5, 0.3, 0.5, 0.7, 0.5,
                              0.3, 1.0, 0.785, 0.01, 0)
                ops.element('zeroLength', 1001, 1, 2, '-mat', 100, '-dir', 1, 2)
                return (True,
                       "PARTIAL: MultiSurfCrack2D available but using zeroLength (may not support 2D NDMaterial correctly).\n"
                       "Consider recompiling with zeroLengthND element.",
                       'zeroLength')
            except Exception as e_zl:
                return (False,
                       f"Neither zeroLengthND nor zeroLength supports MultiSurfCrack2D.\n"
                       f"zeroLengthND error: {str(e_nd)}\n"
                       f"zeroLength error: {str(e_zl)}\n"
                       f"Fix: Recompile OpenSees with zeroLengthND element and MultiSurfCrack2D.",
                       'unknown')

    except Exception as e:
        return (False, f"OpenSees test failed: {str(e)}", 'unknown')

# =============================================================================
# Runner script — executed inside WSL
# =============================================================================
RUNNER_PY = r'''
import sys, json, traceback, math
import numpy as np


def _build_analysis(ops, p, at, ln, dof, incr, alg):
    ops.wipeAnalysis()
    ops.constraints('Plain')
    ops.numberer('RCM')
    try:    ops.system('UmfPack')
    except: ops.system('BandGeneral')
    ops.test('NormUnbalance', float(p.get('tol', 1e-8)), int(p.get('max_iter', 400)))
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


def _step_with_fallback(ops, p, at, ln, dof, incr):
    for alg in ['NewtonLineSearch', 'KrylovNewton', 'ModifiedNewton', 'Newton']:
        _build_analysis(ops, p, at, ln, dof, incr, alg)
        if ops.analyze(1) == 0:
            return 0, alg
    return -1, 'Newton'


def _cutback(ops, p, at, ln, dof, incr, max_cuts=12):
    cur = float(incr)
    for _ in range(max_cuts + 1):
        ok, alg = _step_with_fallback(ops, p, at, ln, dof, cur)
        if ok == 0:
            return 0, cur, alg
        cur *= 0.5
    return -1, cur, 'Newton'


def run_model_2d(p):
    import openseespy.opensees as ops

    disp_l = []; force_l = []; open_l = []; slip_l = []
    status = "failed"; msg = "failed"
    node_disp_last = {}

    try:
        ops.wipe()
        ops.model('basic', '-ndm', 2, '-ndf', 2)

        W  = float(p['panel_W']);  H  = float(p['panel_H']); t  = float(p.get('panel_t',  0.2))
        Ec = float(p.get('panel_Ec', 30000.)); nu = float(p.get('panel_nu', 0.2))

        # Concrete NDMaterial (plane stress, linear elastic)
        ops.nDMaterial('ElasticIsotropic', 1, Ec, nu)

        # Nodes
        mesh_nodes = p['mesh_nodes']   # {str_nid: [x, y]}
        for nid_str, (x, y) in mesh_nodes.items():
            ops.node(int(nid_str), float(x), float(y))

        # Boundary conditions
        bc_nodes = p.get('bc_nodes', {})   # {str_nid: [fix_x, fix_y]}
        for nid_str, (fx, fy) in bc_nodes.items():
            ops.fix(int(nid_str), int(fx), int(fy))

        # Triangular elements (try lowercase then uppercase command name)
        mesh_tris = p['mesh_tris']   # [[eid, n1, n2, n3], ...]
        for e, n1, n2, n3 in mesh_tris:
            try:
                ops.element('tri31', int(e), int(n1), int(n2), int(n3), t, 'PlaneStress', 1)
            except Exception:
                try:
                    ops.element('Tri31', int(e), int(n1), int(n2), int(n3), t, 'PlaneStress', 1)
                except Exception:
                    ops.element('tri31', int(e), int(n1), int(n2), int(n3), t, 'PlaneStress', 1)

        # Crack interface elements
        # crack_pairs format: [[nb, na, y, x, tx, ty, cnx, cny], ...]
        #   tx,ty  = crack tangent vector (unit)
        #   cnx,cny = crack normal vector (unit)
        # For horizontal cracks: tangent=(1,0), normal=(0,1)
        crack_pairs   = p.get('mesh_crack_pairs', [])
        crack_mat_data = p.get('crack_mat_data', [])

        # Build lookup: y -> crack mat params
        def _find_mat(y_val):
            for cm in crack_mat_data:
                if abs(float(cm['y']) - y_val) < 1e-6:
                    return cm
            return {'mat_type': 'Elastic', 'kn': 210., 'kt': 5.95, 'gap': 0.001, 'eta': 0.02}

        elt_base = len(mesh_tris) + 1
        # Store (nb, na, yc, tx, ty, cnx, cny) for each crack link — used in collect()
        cnodes = []

        crack_y_set = sorted(set(round(float(cp[2]), 6) for cp in crack_pairs))
        cpos = crack_y_set

        for ci, cp in enumerate(crack_pairs):
            nb = int(cp[0]); na = int(cp[1]); yc = float(cp[2])
            # Extract orientation — default to horizontal if not provided
            if len(cp) >= 8:
                c_tx, c_ty   = float(cp[4]), float(cp[5])
                c_nx, c_ny   = float(cp[6]), float(cp[7])
            else:
                c_tx, c_ty   = 1.0, 0.0   # tangent along X
                c_nx, c_ny   = 0.0, 1.0   # normal  along Y

            cm = _find_mat(round(yc, 6))
            mat_type = str(cm.get('mat_type', 'MultiSurfCrack2D'))

            # Material tag for this crack
            mat_id = 10000 + ci

            # Try to use MultiSurfCrack2D if requested and available
            # Otherwise fall back to standard OpenSees materials
            if 'multisurfcrack2d' in mat_type.lower() or 'multi' in mat_type.lower():
                # MultiSurfCrack2D: NDMaterial for interface cracks
                # Parameters from crack_mat_data or use defaults for horizontal cracks
                fc   = float(cm.get('fc', 30.0))        # concrete strength (MPa)
                ag   = float(cm.get('ag', 25.0))        # max aggregate diameter (mm)
                fcl  = float(cm.get('fcl', 5.0))        # crack closure stress (MPa)
                Acr  = float(cm.get('Acr', 1.0))        # nominal crack area
                rho_lok = float(cm.get('rho_lok', 0.5)) # interlock dilation parameter
                chi_lok = float(cm.get('chi_lok', 0.3)) # interlock cohesion ratio
                rho_act = float(cm.get('rho_act', 0.5)) # rubble dilation parameter
                mu   = float(cm.get('mu', 0.7))         # friction coefficient
                chi  = float(cm.get('chi', 0.5))        # unloading cohesion ratio
                zeta = float(cm.get('zeta', 0.3))       # slip break point (pinching)
                kappa = float(cm.get('kappa', 1.0))     # roughness transition
                theta = float(cm.get('theta', 0.785))   # contact angle (radians)
                w0   = float(cm.get('w0', 0.01))        # initial crack width (mm)
                cPath = int(cm.get('cPath', 0))         # load path flag

                # De: elastic loading stiffness matrix (symmetric, 2x2)
                kn = max(float(cm.get('kn', 210.0)), 1e-6)
                kt = max(float(cm.get('kt', 5.95)), 1e-6)

                # FIX A: Create NDMaterial with proper error handling
                material_created = False
                try:
                    ops.nDMaterial('MultiSurfCrack2D', mat_id,
                                   kn, kt,                  # De_11, De_22
                                   0.0,                     # De_12
                                   kn, kt, 0.0,             # DeU_11, DeU_22, DeU_12
                                   fc, ag, fcl, Acr,
                                   rho_lok, chi_lok, rho_act, mu, chi, zeta, kappa, theta, w0, cPath)
                    material_created = True
                except Exception as e_mat:
                    # Material not available - explicit fallback
                    print(f"[CRITICAL FALLBACK] MultiSurfCrack2D material creation failed: {e_mat}")
                    print(f"[INFO] Will use Elastic spring model instead")
                    material_created = False

                if not material_created:
                    # FIX C: Explicit fallback with clear messaging
                    print(f"[FALLBACK REASON] crack {ci}: MultiSurfCrack2D not in OpenSees build")
                    ops.uniaxialMaterial('Elastic', mat_id*2, kt)
                    ops.uniaxialMaterial('Elastic', mat_id*2+1, kn)
                    elt_id = elt_base + ci
                    ops.element('zeroLength', elt_id, nb, na,
                                '-mat', mat_id*2, mat_id*2+1, '-dir', 1, 2)
                    cnodes.append((nb, na, yc, c_tx, c_ty, c_nx, c_ny))
                    continue

                # FIX B: Try to use correct element type for NDMaterial
                # Prefer zeroLengthND if available, otherwise try zeroLength
                elt_id = elt_base + ci
                element_created = False

                # Try zeroLengthND first (proper 2D ND element)
                try:
                    ops.element('zeroLengthND', elt_id, nb, na, mat_id)
                    element_created = True
                    print(f"[INFO] Crack {ci}: Using zeroLengthND with MultiSurfCrack2D (recommended)")
                except Exception as e_nd:
                    # Fallback: try zeroLength with NDMaterial
                    try:
                        ops.element('zeroLength', elt_id, nb, na, '-mat', mat_id, '-dir', 1, 2)
                        element_created = True
                        print(f"[WARNING] Crack {ci}: Using zeroLength with NDMaterial (may not work correctly)")
                    except Exception as e_zl:
                        # Both element types failed
                        element_created = False
                        print(f"[CRITICAL FALLBACK] Cannot create interface element for crack {ci}")
                        print(f"  zeroLengthND error: {e_nd}")
                        print(f"  zeroLength error: {e_zl}")

                if not element_created:
                    # FIX C: Second fallback - use Elastic springs
                    print(f"[FALLBACK REASON] crack {ci}: No proper ND interface element found")
                    ops.uniaxialMaterial('Elastic', mat_id*2, kt)
                    ops.uniaxialMaterial('Elastic', mat_id*2+1, kn)
                    ops.element('zeroLength', elt_id, nb, na,
                                '-mat', mat_id*2, mat_id*2+1, '-dir', 1, 2)
                    print(f"[FALLBACK] Crack {ci}: Using Elastic spring pair instead")

                cnodes.append((nb, na, yc, c_tx, c_ty, c_nx, c_ny))

            else:
                # Standard OpenSees materials (Elastic, ElasticPPGap, Steel01)
                kn  = max(float(cm.get('kn',  210.)), 1e-6)
                kt  = max(float(cm.get('kt',  5.95)), 1e-6)
                gap = float(cm.get('gap', 0.001))
                eta = float(cm.get('eta', 0.02))

                # mat_t = tangential (slip) material, mat_n = normal (opening) material
                mat_t = mat_id * 2
                mat_n = mat_id * 2 + 1

                if 'eppgap' in mat_type.lower() or 'elasticppgap' in mat_type.lower():
                    ops.uniaxialMaterial('ElasticPPGap', mat_t, kt, kt * 5., gap, eta, '-damage', 'NoDamage')
                    ops.uniaxialMaterial('ElasticPPGap', mat_n, kn, kn * 10., 0.0, eta, '-damage', 'NoDamage')
                elif 'bilinear' in mat_type.lower() or 'custom' in mat_type.lower():
                    ops.uniaxialMaterial('Steel01', mat_t, kt * gap, kt, eta)
                    ops.uniaxialMaterial('Steel01', mat_n, kn * gap, kn, eta)
                else:
                    # Default: Elastic
                    ops.uniaxialMaterial('Elastic', mat_t, kt)
                    ops.uniaxialMaterial('Elastic', mat_n, kn)

                elt_id = elt_base + ci
                ops.element('zeroLength', elt_id, nb, na, '-mat', mat_t, mat_n, '-dir', 1, 2)
                cnodes.append((nb, na, yc, c_tx, c_ty, c_nx, c_ny))

        # Loads
        load_nodes = p.get('load_nodes', {})   # {str_nid: [Fx, Fy]}
        if not load_nodes:
            raise RuntimeError("No loads applied. Assign loads on the Geometry tab.")

        ops.timeSeries('Linear', 1)
        ops.pattern('Plain', 1, 1)
        for nid_str, (Fx, Fy) in load_nodes.items():
            ops.load(int(nid_str), float(Fx), float(Fy))

        # Reference node for DisplacementControl: pick first loaded node
        ref_nid  = int(next(iter(load_nodes)))
        ref_ld   = load_nodes[next(iter(load_nodes))]
        ref_dof  = 2 if abs(ref_ld[1]) > abs(ref_ld[0]) else 1

        # Also find all fixed nodes for reaction collection
        fixed_nids = [int(k) for k in bc_nodes.keys()]

        at   = p.get('analysis_type', 'DisplacementControl')
        ml   = float(p.get('max_load_factor', 50.))
        nc_y = len(crack_y_set)
        open_l = [[] for _ in range(nc_y)]
        slip_l = [[] for _ in range(nc_y)]

        def collect():
            disp_l.append(ops.nodeDisp(ref_nid, ref_dof))
            ops.reactions()
            tot_f = 0.
            for fnid in fixed_nids:
                try: tot_f += abs(ops.nodeReaction(fnid, ref_dof))
                except: pass
            force_l.append(tot_f)
            # Average opening / slip per crack Y using local crack axes
            for yi, yv in enumerate(crack_y_set):
                dw_sum = ds_sum = cnt = 0
                for nb, na, yc, c_tx, c_ty, c_nx, c_ny in cnodes:
                    if abs(yc - yv) < 1e-6:
                        try:
                            dux = ops.nodeDisp(na, 1) - ops.nodeDisp(nb, 1)
                            duy = ops.nodeDisp(na, 2) - ops.nodeDisp(nb, 2)
                            # opening = relative disp projected onto crack normal
                            dw_sum += dux * c_nx + duy * c_ny
                            # slip = relative disp projected onto crack tangent
                            ds_sum += dux * c_tx + duy * c_ty
                            cnt += 1
                        except: pass
                open_l[yi].append(dw_sum / max(cnt, 1))
                slip_l[yi].append(ds_sum / max(cnt, 1))

        failed = False; fm = ""
        if at == 'LoadControl':
            incr  = float(p.get('load_incr', 0.01))
            steps = max(1, int(1. / incr))
            for st in range(steps):
                ok, cur, alg = _cutback(ops, p, at, ref_nid, ref_dof, incr)
                if ok == 0: collect(); incr = min(incr, cur)
                else: failed = True; fm = f"step {st} alg={alg}"; break
        else:
            tgt  = float(p.get('target_disp', 0.05))
            incr = float(p.get('disp_incr',  0.0005))
            steps = max(1, int(abs(tgt) / max(abs(incr), 1e-12)))
            for st in range(steps):
                try:
                    if abs(ops.getTime()) > ml:
                        failed = True; fm = "load factor cap reached"; break
                except: pass
                ok, cur, alg = _cutback(ops, p, at, ref_nid, ref_dof, incr)
                if ok == 0: collect(); incr = min(incr, cur)
                else: failed = True; fm = f"step {st} alg={alg}"; break

        # Collect last-step nodal displacements
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
    disp_arr = np.array([node_disp_last[n] for n in nids_arr], dtype=float) if len(nids_arr) else np.zeros((0, 2))

    return dict(
        disp=a(disp_l), force=a(force_l),
        crack_positions=a(cpos),
        crack_openings=la(open_l), crack_slips=la(slip_l),
        node_disp_last_ids=nids_arr, node_disp_last_vals=disp_arr,
        status=status, message=msg,
    )


def main():
    if len(sys.argv) == 3:
        with open(sys.argv[1]) as f:
            p = json.load(f)
        r = run_model_2d(p)
        nids = r['node_disp_last_ids']; nvals = r['node_disp_last_vals']
        np.savez(sys.argv[2],
            disp=r['disp'], force=r['force'],
            crack_positions=r['crack_positions'],
            crack_openings=np.array(r['crack_openings'], dtype=object),
            crack_slips=np.array(r['crack_slips'], dtype=object),
            node_disp_last_ids=nids, node_disp_last_vals=nvals,
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


# =============================================================================
# WSL Worker thread
# =============================================================================
class WSLWorker(QThread):
    log      = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, params, run_dir, activate):
        super().__init__()
        self.params   = params
        self.run_dir  = Path(run_dir)
        self.activate = activate

    def run(self):
        try:
            mkd(self.run_dir)
            pp  = self.run_dir / "params.json"
            rp  = self.run_dir / "runner.py"
            np_ = self.run_dir / "results.npz"

            pp.write_text(json.dumps(self.params, indent=2), encoding='utf-8')
            rp.write_text(RUNNER_PY.lstrip(), encoding='utf-8')

            pp_w  = win_to_wsl(str(pp))
            rp_w  = win_to_wsl(str(rp))
            np_w  = win_to_wsl(str(np_))

            bash = f"{self.activate} && python3 {rp_w} {pp_w} {np_w}"
            cmd  = ["wsl", "bash", "-lc", bash]
            self.log.emit(f"[CMD] {bash[:140]}")
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if proc.stdout.strip(): self.log.emit(proc.stdout.strip())
            if proc.stderr.strip(): self.log.emit("[STDERR] " + proc.stderr.strip())

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

            result = dict(
                status=str(data["status"][0]),
                message=str(data["message"][0]),
                disp=arr("disp"), force=arr("force"),
                crack_positions=arr("crack_positions"),
                crack_openings=obj("crack_openings"),
                crack_slips=obj("crack_slips"),
                node_disp_last=node_disp_last,
                mesh_nodes=mesh_nodes,
                mesh_tris=mesh_tris,
                returncode=proc.returncode,
            )
            self.finished.emit(result)
        except subprocess.TimeoutExpired:
            self.error.emit("Analysis timed out after 600 seconds.")
        except Exception:
            self.error.emit(traceback.format_exc())


# =============================================================================
# Main Window
# =============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("2D RC Panel Analysis  ·  OpenSeesPy")
        self.setMinimumSize(1300, 860)
        self.RUNS_DIR = str(Path.home() / "panel_analysis_runs")
        self._worker  = None

        root = QWidget(); self.setCentralWidget(root)
        vl   = QVBoxLayout(root); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(0)

        # ── header ────────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setStyleSheet(f"background:{BG_PANEL};border-bottom:1px solid {BORDER};")
        hl  = QHBoxLayout(hdr); hl.setContentsMargins(20, 10, 20, 10)
        t1  = QLabel("2D RC PANEL ANALYSIS")
        t1.setStyleSheet(f"color:{C1};font-size:16px;font-weight:bold;letter-spacing:2px;")
        t2  = QLabel("  Plane Stress  ·  tri31  ·  zeroLength Cracks  ·  OpenSeesPy")
        t2.setStyleSheet(f"color:{TXTS};font-size:12px;")
        self.lbl_wsl = QLabel("WSL: checking…")
        self.lbl_wsl.setStyleSheet(f"color:{C4};font-size:12px;font-weight:bold;")
        hl.addWidget(t1); hl.addWidget(t2); hl.addStretch(); hl.addWidget(self.lbl_wsl)
        vl.addWidget(hdr)

        # ── quick-actions toolbar ─────────────────────────────────────────────
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

        self.lbl_workflow = QLabel(
            "  ① Geometry  →  ② Crack Materials  →  ③ Analysis  →  ▶ Run Analysis  →  ⑤ Results")
        self.lbl_workflow.setStyleSheet(f"color:{TXTS};font-size:10px;")

        for w in [self.btn_run, self.btn_refresh_cracks, self.btn_gen_script,
                  self.btn_save_png, self.btn_csv, self.lbl_workflow]:
            qal.addWidget(w)
        qal.addStretch()
        vl.addWidget(qa)

        # ── tabs ──────────────────────────────────────────────────────────────
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

        # ── wire signals ──────────────────────────────────────────────────────
        self.run.run_requested.connect(self.start_analysis)
        self.btn_run.clicked.connect(self.start_analysis)
        self.btn_refresh_cracks.clicked.connect(self._refresh_cracks)
        self.btn_gen_script.clicked.connect(self.generate_script)
        self.scr.btn_gen.clicked.connect(self.generate_script)
        self.btn_save_png.clicked.connect(lambda: self.res._save())
        self.btn_csv.clicked.connect(lambda: self.res._csv())

        QTimer.singleShot(900, self.check_wsl)

    # ── helpers ───────────────────────────────────────────────────────────────
    def _refresh_cracks(self):
        self.crk.refresh_from_geometry(self.geo)
        self.tabs.setCurrentWidget(self.crk)

    def _params(self):
        p = {}
        p.update(self.geo.get_params())
        p.update(self.crk.get_params())
        p.update(self.anl.get_params())
        return p

    def check_wsl(self):
        act = self.run.get_activate()
        cmd = ["wsl", "bash", "-lc",
               f"{act} && python3 -c \"import openseespy.opensees; print('OK')\""]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            ok   = "OK" in proc.stdout
            self.lbl_wsl.setText(f"WSL: {'✓ OK' if ok else '✗ NOT READY'}")
            self.lbl_wsl.setStyleSheet(
                f"color:{C2 if ok else C3};font-size:12px;font-weight:bold;")
            self.run.append("✓ WSL OpenSeesPy ready." if ok else
                            "✗ WSL check failed — fix 'Activate command' in Run tab.")
            if not ok and proc.stderr.strip():
                self.run.append(proc.stderr.strip()[:500])
        except Exception as e:
            self.lbl_wsl.setText("WSL: ✗ ERROR")
            self.lbl_wsl.setStyleSheet(f"color:{C3};font-size:11px;font-weight:bold;")
            self.run.append(f"WSL check error: {e}")

    def start_analysis(self):
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
                        f"target={p.get('target_disp')}  incr={p.get('disp_incr')}")
        self.run.set_status("Running in WSL…")
        self.run.btn_run.setEnabled(False)
        self.btn_run.setEnabled(False)
        self.btn_run.setText("⏳  Running…")
        self.lbl_workflow.setText("  Analysis running in WSL — see ④ Run tab for progress…")
        self.lbl_workflow.setStyleSheet(f"color:{C4};font-size:10px;")
        self.statusBar().showMessage("Analysis running in WSL…")

        self._worker = WSLWorker(p, str(rd), act)
        self._worker.log.connect(self.run.append)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_err)
        self._worker.start()

    def _on_done(self, result):
        self.run.btn_run.setEnabled(True)
        self.btn_run.setEnabled(True)
        self.btn_run.setText("▶  Run Analysis")
        msg = result["message"]
        self.run.set_status(f"{'✓' if result['status']=='ok' else '⚠'} {msg}",
                            ok=(result["status"] == "ok"))
        self.run.append(f"\n{'SUCCESS' if result['status']=='ok' else 'PARTIAL/FAILED'}: {msg}")

        if result["disp"].size > 0:
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
        self.run.set_status("✗ Error in WSL (see console)", ok=False)
        self.run.append("\nERROR:\n" + tb)
        self.lbl_workflow.setText(
            "  Error — see ④ Run tab console. Check activate command & openseespy install.")
        self.lbl_workflow.setStyleSheet(f"color:{C3};font-size:10px;font-weight:bold;")
        self.statusBar().showMessage("Error — see console.")

    def generate_script(self):
        p = self._params()
        import json as _j
        py_p = _j.dumps(p, indent=2).replace(': true', ': True').replace(': false', ': False').replace(': null', ': None')
        nt = len(p.get("mesh_tris", []))
        nc = len(p.get("mesh_crack_pairs", []))
        hdr = (
            f'#!/usr/bin/env python3\n'
            f'"""\n'
            f'2D RC Panel Analysis — Standalone OpenSeesPy Script\n'
            f'Generated : {time.strftime("%Y-%m-%d %H:%M:%S")}\n'
            f'Panel     : {p.get("panel_W","?")} × {p.get("panel_H","?")} m\n'
            f'Mesh      : tri={nt}  crack_links={nc}\n'
            f'\n'
            f'Run:\n'
            f'  python panel_analysis.py params.json results.npz\n'
            f'"""\n'
            f'import json, sys\n\n'
            f'# ── Edit parameters here ──────────────────────────────────────\n'
            f'PARAMS = {py_p}\n\n'
            f'# ── Runner code ───────────────────────────────────────────────\n'
        )
        self.scr.set_script(hdr + RUNNER_PY.lstrip())
        self.lbl_workflow.setText(
            "  Script generated. Use ⑥ Script tab to copy or save.")


# =============================================================================
# Entry point
# =============================================================================
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
