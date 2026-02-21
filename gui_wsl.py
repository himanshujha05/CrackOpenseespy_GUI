#!/usr/bin/env python3
"""
Multi-Surface Crack Plasticity Model — OpenSeesPy GUI
======================================================
Galik, Calvi & Andreotti (2026)

FIXES vs previous version:
  - lbl() helper no longer shadowed by loop variable names
  - Mouse-click canvas to draw bar + cracks interactively
  - Run button properly wired and always clickable
  - WSL venv path shown/editable in Run tab
  - Better error reporting

Run:
  python crack_plasticity_gui.py
"""

import sys, json, time, math, traceback, subprocess
from pathlib import Path
import numpy as np

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QTextEdit, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QDoubleSpinBox, QSpinBox, QFileDialog,
    QMessageBox, QCheckBox, QSplitter, QScrollArea, QSlider,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QPointF, QRectF
from PyQt5.QtGui import (
    QFont, QPainter, QPen, QBrush, QColor,
    QPainterPath, QFontMetrics, QPixmap,
)

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

# ─── colours ─────────────────────────────────────────────────────────────────
BG_DEEP   = "#0d1117"
BG_PANEL  = "#161b22"
BG_CARD   = "#1c2128"
BG_INPUT  = "#0d1117"
BORDER    = "#30363d"
C1        = "#58a6ff"   # blue
C2        = "#3fb950"   # green
C3        = "#f78166"   # red
C4        = "#d2a679"   # amber
TXT       = "#e6edf3"
TXTS      = "#8b949e"

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
QToolTip{{background:{BG_CARD};color:{TXT};border:1px solid {C1};padding:6px;border-radius:4px;font-size:12px;}}
QCheckBox{{color:{TXT};spacing:8px;font-size:13px;}}
QCheckBox::indicator{{width:15px;height:15px;border:1px solid {BORDER};
  border-radius:3px;background:{BG_INPUT};}}
QCheckBox::indicator:checked{{background:{C1};border-color:{C1};}}
"""

# ─── helpers ─────────────────────────────────────────────────────────────────
def win_to_wsl(p):
    p = Path(p); drv = p.drive.rstrip(":").lower()
    rest = p.as_posix().split(":/",1)[-1]
    return f"/mnt/{drv}/{rest}"

def mkd(path): Path(path).mkdir(parents=True, exist_ok=True)

def dsb(val, lo, hi, dec=4, step=0.001, w=155, tip=""):
    sb = QDoubleSpinBox(); sb.setRange(lo,hi); sb.setDecimals(dec)
    sb.setSingleStep(step); sb.setValue(val); sb.setFixedWidth(w)
    if tip: sb.setToolTip(tip)
    return sb

def isb(val, lo, hi, w=120, tip=""):
    sb = QSpinBox(); sb.setRange(lo,hi); sb.setValue(val); sb.setFixedWidth(w)
    if tip: sb.setToolTip(tip)
    return sb

def mk_lbl(txt, kind=""):
    lb = QLabel(txt)
    if kind: lb.setObjectName(kind)
    return lb


# ─── 2D panel mesh generation ────────────────────────────────────────────────
def generate_panel_mesh(W, H, nx, ny, crack_ys):
    """
    Structured triangular mesh for a W×H panel with horizontal cracks.

    Each quad cell is split into 2 triangles.  At each crack-row, every
    node is duplicated into *below* and *above* copies so zero-length
    crack interface elements can be placed between them.

    Returns
    -------
    nodes : dict  {nid: (x, y)}
    tris  : list  [(eid, n1, n2, n3)]
    crack_pairs : list  [(nid_below, nid_above, y, x)]
    crack_rows  : set of j indices that are crack rows
    """
    dx = W / max(nx, 1)
    dy = H / max(ny, 1)

    # Snap each crack y to nearest interior grid row
    grid_ys = [j * dy for j in range(ny + 1)]
    crack_rows = set()
    for yc in crack_ys:
        best_j = min(range(1, ny), key=lambda j: abs(grid_ys[j] - yc))
        crack_rows.add(best_j)

    # Build nodes
    nodes = {}
    nid = 1
    node_grid = {}          # (i, j, side) -> nid,  side in (None, 'below', 'above')

    for j in range(ny + 1):
        for i in range(nx + 1):
            x = round(i * dx, 8)
            y = round(j * dy, 8)
            if j in crack_rows:
                nodes[nid] = (x, y)
                node_grid[(i, j, 'below')] = nid
                nid += 1
                nodes[nid] = (x, y)
                node_grid[(i, j, 'above')] = nid
                nid += 1
            else:
                nodes[nid] = (x, y)
                node_grid[(i, j, None)] = nid
                nid += 1

    def _gn(i, j, side='above'):
        if j in crack_rows:
            return node_grid[(i, j, side)]
        return node_grid[(i, j, None)]

    # Build triangles (2 per quad cell)
    tris = []
    eid = 1
    for j in range(ny):
        for i in range(nx):
            bl = _gn(i,   j,   'above')
            br = _gn(i+1, j,   'above')
            tl = _gn(i,   j+1, 'below')
            tr = _gn(i+1, j+1, 'below')
            tris.append((eid, bl, br, tr));  eid += 1
            tris.append((eid, bl, tr, tl));  eid += 1

    # Crack pairs  (zero-length connections)
    crack_pairs = []
    for j in sorted(crack_rows):
        y = round(j * dy, 8)
        for i in range(nx + 1):
            x = round(i * dx, 8)
            nb = node_grid[(i, j, 'below')]
            na = node_grid[(i, j, 'above')]
            crack_pairs.append((nb, na, y, x))

    return nodes, tris, crack_pairs, crack_rows


# ─── PanelMeshCanvas ─────────────────────────────────────────────────────────
class PanelMeshCanvas(QWidget):
    """Visualise a 2-D triangulated panel with crack lines."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(300, 400)
        self.nodes = {}
        self.tris = []
        self.crack_pairs = []
        self.crack_rows = set()
        self.panel_W = 1.0
        self.panel_H = 2.0
        self.show_nodes = True
        self.show_ids = False

    def set_mesh(self, nodes, tris, crack_pairs, crack_rows, W, H):
        self.nodes = nodes
        self.tris = tris
        self.crack_pairs = crack_pairs
        self.crack_rows = crack_rows
        self.panel_W = W
        self.panel_H = H
        self.update()

    def clear_mesh(self):
        self.nodes = {}; self.tris = []; self.crack_pairs = []
        self.crack_rows = set(); self.update()

    # ── coordinate transform ──────────────────────────────────────────────
    def _margins(self):
        return 48, 24, 24, 32

    def _to_px(self, mx, my):
        ml, mt, mr, mb = self._margins()
        dw = self.width() - ml - mr
        dh = self.height() - mt - mb
        sx = dw / max(self.panel_W, 1e-6)
        sy = dh / max(self.panel_H, 1e-6)
        sc = min(sx, sy)
        ox = ml + (dw - sc * self.panel_W) / 2
        oy = mt + (dh - sc * self.panel_H) / 2
        px = ox + mx * sc
        py = oy + (self.panel_H - my) * sc
        return int(px), int(py)

    # ── paint ─────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        p.fillRect(0, 0, W, H, QColor(BG_PANEL))

        if not self.nodes:
            p.setPen(QPen(QColor(TXTS), 1))
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(W // 2 - 80, H // 2, "Click  Generate Mesh")
            p.end(); return

        # Draw triangles
        p.setPen(QPen(QColor(BORDER), 0.8))
        for _, n1, n2, n3 in self.tris:
            x1, y1 = self._to_px(*self.nodes[n1])
            x2, y2 = self._to_px(*self.nodes[n2])
            x3, y3 = self._to_px(*self.nodes[n3])
            p.drawLine(x1, y1, x2, y2)
            p.drawLine(x2, y2, x3, y3)
            p.drawLine(x3, y3, x1, y1)

        # Draw crack lines (thick red)
        if self.crack_pairs:
            # Group by y
            by_y = {}
            for nb, na, y, x in self.crack_pairs:
                by_y.setdefault(round(y, 6), []).append(x)
            p.setPen(QPen(QColor(C3), 3))
            for y, xs in by_y.items():
                xs_sorted = sorted(xs)
                if len(xs_sorted) >= 2:
                    x0, y0 = self._to_px(xs_sorted[0], y)
                    x1, y1 = self._to_px(xs_sorted[-1], y)
                    p.drawLine(x0, y0, x1, y1)
                # crack node markers
                p.setPen(QPen(QColor(C3), 1))
                for xc in xs_sorted:
                    px, py = self._to_px(xc, y)
                    p.drawEllipse(px - 3, py - 3, 6, 6)
                p.setPen(QPen(QColor(C3), 3))

        # Draw nodes
        if self.show_nodes:
            p.setPen(QPen(QColor(C1), 1))
            p.setBrush(QBrush(QColor(C1)))
            for nid, (nx_, ny_) in self.nodes.items():
                px, py = self._to_px(nx_, ny_)
                p.drawEllipse(px - 2, py - 2, 4, 4)

        # Boundary markers
        p.setPen(QPen(QColor(TXTS), 1))
        p.setFont(QFont("Consolas", 8))
        # bottom: fixed
        bx0, by0 = self._to_px(0, 0)
        bx1, _ = self._to_px(self.panel_W, 0)
        p.drawText(bx0, by0 + 14, "fixed base")
        # top: loaded
        tx0, ty0 = self._to_px(0, self.panel_H)
        tx1, _ = self._to_px(self.panel_W, self.panel_H)
        p.setPen(QPen(QColor(C3), 1))
        for xn in range(0, int(self.panel_W * 100) + 1, max(1, int(self.panel_W * 100) // 6)):
            axp, ayp = self._to_px(xn / 100.0, self.panel_H)
            p.drawLine(axp, ayp - 16, axp, ayp - 3)

        # Dimension labels
        p.setPen(QPen(QColor(TXTS), 1))
        p.setFont(QFont("Consolas", 8))
        mx, my = self._to_px(self.panel_W / 2, 0)
        p.drawText(mx - 20, my + 26, f"W={self.panel_W:.2f}")
        lx, ly = self._to_px(0, self.panel_H / 2)
        p.save()
        p.translate(lx - 18, ly)
        p.rotate(-90)
        p.drawText(-20, 4, f"H={self.panel_H:.2f}")
        p.restore()

        # Stats
        p.setPen(QPen(QColor(C4), 1))
        p.setFont(QFont("Consolas", 8))
        nc = len(self.crack_pairs)
        nt = len(self.tris)
        nn = len(self.nodes)
        p.drawText(8, H - 8, f"nodes={nn}  tri={nt}  crack_links={nc}")
        p.end()


# =============================================================================
# Interactive Structure Drawing Canvas
# =============================================================================
class StructureCanvas(QWidget):
    """
    Interactive bar diagram.
    Left-click  = add crack interface at that Y position
    Right-click = remove nearest crack
    Load an image to trace cracks on a photo — click where cracks appear.
    """
    cracks_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setMinimumSize(220, 400)
        self.bar_L    = 5.0
        self.bar_A    = 1.0
        self.fc       = 30.0
        self.ag       = 16.0
        self.w0       = 0.10
        self.auto_k   = True
        self.cracks   = []
        self._bg_pixmap = None          # optional background photo
        self.setToolTip(
            "Left-click anywhere on the bar to place a crack interface\n"
            "Right-click to remove nearest crack\n"
            "Load an image below to trace cracks on a photo")
        self.setMouseTracking(True)
        self._hover_y = None

    # ── background image ──────────────────────────────────────────────────────
    def load_image(self, path: str):
        px = QPixmap(path)
        if not px.isNull():
            self._bg_pixmap = px
            self.update()
            return True
        return False

    def clear_image(self):
        self._bg_pixmap = None
        self.update()

    # ── coordinate helpers ────────────────────────────────────────────────────
    def _margins(self):
        return 40, 30, 40, 30   # left, top, right, bottom

    def _bar_rect(self):
        ml, mt, mr, mb = self._margins()
        W = self.width(); H = self.height()
        bw = max(24, min(44, (W - ml - mr) // 2))
        cx = W // 2
        return cx - bw//2, mt, bw, H - mt - mb

    def _y_to_px(self, y):
        _, bt, _, bb = self._margins()
        H = self.height()
        total = H - bt - bb
        # y=0 at bottom, y=L at top
        frac = y / max(self.bar_L, 1e-6)
        return int(H - bb - frac * total)

    def _px_to_y(self, px):
        _, bt, _, bb = self._margins()
        H = self.height()
        total = H - bt - bb
        frac = (H - bb - px) / max(total, 1)
        return max(0.0, min(self.bar_L, frac * self.bar_L))

    # ── events ────────────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        bx, _, bw, _ = self._bar_rect()
        mx = event.x(); my = event.y()
        # only respond if clicking near the bar
        if bx - 20 <= mx <= bx + bw + 20:
            y = self._px_to_y(my)
            if event.button() == Qt.LeftButton:
                if 0.02 * self.bar_L < y < 0.98 * self.bar_L:
                    # check not too close to existing
                    too_close = any(abs(y - yc) < 0.02 * self.bar_L for yc in self.cracks)
                    if not too_close:
                        self.cracks.append(y)
                        self.cracks.sort()
                        self.cracks_changed.emit()
                        self.update()
            elif event.button() == Qt.RightButton:
                if self.cracks:
                    nearest = min(self.cracks, key=lambda yc: abs(yc - y))
                    self.cracks.remove(nearest)
                    self.cracks_changed.emit()
                    self.update()

    def mouseMoveEvent(self, event):
        self._hover_y = self._px_to_y(event.y())
        self.update()

    def leaveEvent(self, event):
        self._hover_y = None
        self.update()

    # ── paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        W = self.width(); H = self.height()
        p.fillRect(0, 0, W, H, QColor(BG_PANEL))

        # draw background photo (semi-transparent so bar overlay stays readable)
        if self._bg_pixmap:
            scaled = self._bg_pixmap.scaled(W, H, Qt.KeepAspectRatioByExpanding,
                                             Qt.SmoothTransformation)
            ox = (scaled.width()  - W) // 2
            oy = (scaled.height() - H) // 2
            p.setOpacity(0.45)
            p.drawPixmap(0, 0, scaled, ox, oy, W, H)
            p.setOpacity(1.0)

        bx, bt, bw, bh = self._bar_rect()
        by = bt

        # ground hatch at bottom
        ground_y = self._y_to_px(0)
        hatch_pen = QPen(QColor(TXTS), 1)
        p.setPen(hatch_pen)
        for i in range(6):
            p.drawLine(bx - 10 + i*6, ground_y + 5, bx - 16 + i*6, ground_y + 14)
        p.drawLine(bx - 12, ground_y, bx + bw + 12, ground_y)

        # bar fill (concrete-grey gradient suggestion)
        bar_col = QColor(BG_CARD)
        bar_border = QColor(BORDER)
        p.setBrush(QBrush(bar_col)); p.setPen(QPen(bar_border, 1.5))
        p.drawRect(bx, by, bw, bh)

        # rebar lines inside bar
        rebar_pen = QPen(QColor(C4), 2)
        p.setPen(rebar_pen)
        for rx in [bx + bw//4, bx + 3*bw//4]:
            p.drawLine(rx, by + 4, rx, ground_y - 2)

        # load arrow at top
        top_y = self._y_to_px(self.bar_L)
        arrow_pen = QPen(QColor(C3), 2)
        p.setPen(arrow_pen)
        ax = bx + bw // 2
        p.drawLine(ax, top_y - 28, ax, top_y - 4)
        path = QPainterPath()
        path.moveTo(ax, top_y - 4)
        path.lineTo(ax - 6, top_y - 14)
        path.lineTo(ax + 6, top_y - 14)
        path.closeSubpath()
        p.fillPath(path, QBrush(QColor(C3)))

        # force label
        p.setPen(QPen(QColor(C3), 1))
        p.setFont(QFont("Consolas", 9))
        p.drawText(ax + 10, top_y - 12, "F")

        # hover guide line
        if self._hover_y is not None and 0 < self._hover_y < self.bar_L:
            hy = self._y_to_px(self._hover_y)
            hover_pen = QPen(QColor(C1), 1, Qt.DashLine)
            p.setPen(hover_pen)
            p.drawLine(bx - 5, hy, bx + bw + 5, hy)
            p.setPen(QPen(QColor(TXTS), 1))
            p.setFont(QFont("Consolas", 8))
            p.drawText(bx + bw + 6, hy + 4, f"{self._hover_y:.3f}")

        # crack interfaces
        crack_pen_open  = QPen(QColor(C1), 2)
        crack_pen_label = QPen(QColor(C1), 1)
        for i, yc in enumerate(self.cracks):
            cy = self._y_to_px(yc)
            # zigzag crack line
            p.setPen(crack_pen_open)
            pts = [bx, bx + bw//4, bx + bw//2, bx + 3*bw//4, bx + bw]
            ys  = [cy, cy - 4, cy + 4, cy - 4, cy]
            for j in range(len(pts)-1):
                p.drawLine(pts[j], ys[j], pts[j+1], ys[j+1])
            # triangle marker
            tri = QPainterPath()
            tri.moveTo(bx - 10, cy)
            tri.lineTo(bx - 3, cy - 5)
            tri.lineTo(bx - 3, cy + 5)
            tri.closeSubpath()
            p.fillPath(tri, QBrush(QColor(C1)))
            # label
            p.setPen(crack_pen_label)
            p.setFont(QFont("Consolas", 8))
            p.drawText(bx + bw + 6, cy + 4, f"C{i+1} y={yc:.2f}")

        # dimension line + label
        dim_x = bx - 22
        p.setPen(QPen(QColor(TXTS), 1))
        p.drawLine(dim_x, ground_y, dim_x, top_y)
        p.drawLine(dim_x - 4, ground_y, dim_x + 4, ground_y)
        p.drawLine(dim_x - 4, top_y, dim_x + 4, top_y)
        p.setFont(QFont("Consolas", 8))
        p.save(); p.translate(dim_x - 8, (ground_y + top_y) // 2)
        p.rotate(-90); p.drawText(-15, 4, f"L={self.bar_L:.1f}")
        p.restore()

        # instructions
        p.setPen(QPen(QColor(TXTS), 1))
        p.setFont(QFont("Segoe UI", 8))
        img_hint = "  [photo loaded]" if self._bg_pixmap else "  [load photo below]"
        p.drawText(4, H - 18, f"Left-click = add crack   Right-click = remove{img_hint}")

        p.end()

    def set_geometry(self, L, A, fc, ag, w0, auto_k):
        self.bar_L = L; self.bar_A = A
        self.fc = fc; self.ag = ag; self.w0 = w0; self.auto_k = auto_k
        self.update()

    def get_crack_data(self):
        result = []
        for yc in self.cracks:
            w = max(self.w0, 0.001); fc = self.fc
            Dts = 0.00595 * (25.4/w)**1.6148 * (fc/34.5)**0.193
            Dnw = (2.0 + w) / w
            A = self.bar_A
            kn = Dnw * A if self.auto_k else 1e7
            kt = Dts * A if self.auto_k else 1e5
            result.append({"y": yc, "kn": kn, "kt": kt})
        return result


# =============================================================================
# Tab: Geometry (with interactive drawing)
# =============================================================================
class GeometryTab(QWidget):
    def __init__(self):
        super().__init__()
        root = QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # ── left panel: controls ─────────────────────────────────────────────
        left_scroll = QScrollArea(); left_scroll.setWidgetResizable(True)
        left_scroll.setMaximumWidth(440)
        left = QWidget()
        lv   = QVBoxLayout(left); lv.setContentsMargins(16,16,8,16); lv.setSpacing(10)
        lv.addWidget(mk_lbl("Model Geometry", "heading"))

        # Component type selector
        grp_ct = QGroupBox("Component Type")
        ct_lay = QHBoxLayout(grp_ct); ct_lay.setSpacing(8)
        self.cmb_comp = QComboBox()
        self.cmb_comp.addItems(["1D Bar (legacy)", "2D Panel"])
        self.cmb_comp.setToolTip(
            "1D Bar: classic 1-D truss bar with crack interfaces (existing workflow)\n"
            "2D Panel: rectangular panel meshed with triangles, cracks inserted as horizontal lines")
        ct_lay.addWidget(mk_lbl("Mode:"))
        ct_lay.addWidget(self.cmb_comp)
        ct_lay.addStretch()
        lv.addWidget(grp_ct)

        # ── 1D Bar controls ──────────────────────────────────────────────────
        self.w_1d = QWidget()
        lv_1d = QVBoxLayout(self.w_1d); lv_1d.setContentsMargins(0,0,0,0); lv_1d.setSpacing(10)
        lv_1d.addWidget(mk_lbl("Draw cracks by clicking the bar diagram →", "sub"))

        grp = QGroupBox("Bar Geometry"); form = QFormLayout(grp); form.setSpacing(8)
        self.sb_L  = dsb(5.0,  0.01, 1e4, 3, 0.1,  tip="Bar/column length L")
        self.sb_A  = dsb(1.0,  1e-6, 1e6, 4, 0.1,  tip="Cross-sectional area A (consistent units)")
        form.addRow("Bar Length L:", self.sb_L)
        form.addRow("Area A:",       self.sb_A)
        lv_1d.addWidget(grp)
        lv.addWidget(self.w_1d)

        # ── 2D Panel controls ────────────────────────────────────────────────
        self.w_2d = QWidget(); self.w_2d.setVisible(False)
        lv_2d = QVBoxLayout(self.w_2d); lv_2d.setContentsMargins(0,0,0,0); lv_2d.setSpacing(10)
        lv_2d.addWidget(mk_lbl("Define panel dimensions, mesh density, then generate →", "sub"))

        grp_panel = QGroupBox("Panel Dimensions"); fp = QFormLayout(grp_panel); fp.setSpacing(8)
        self.sb_pW  = dsb(1.0,  0.01, 1e4, 3, 0.1,  tip="Panel width W (m)")
        self.sb_pH  = dsb(2.0,  0.01, 1e4, 3, 0.1,  tip="Panel height H (m)")
        self.sb_pt  = dsb(0.2,  0.001, 10., 3, 0.01, tip="Panel thickness t (m) — for plane stress")
        fp.addRow("Width W (m):",     self.sb_pW)
        fp.addRow("Height H (m):",    self.sb_pH)
        fp.addRow("Thickness t (m):", self.sb_pt)
        lv_2d.addWidget(grp_panel)

        grp_mesh = QGroupBox("Mesh Density"); fm = QFormLayout(grp_mesh); fm.setSpacing(8)
        self.sb_nx = isb(6, 1, 200, tip="Number of divisions in X (width)")
        self.sb_ny = isb(12, 1, 200, tip="Number of divisions in Y (height)")
        fm.addRow("nx (X divs):", self.sb_nx)
        fm.addRow("ny (Y divs):", self.sb_ny)
        self.btn_gen_mesh = QPushButton("Generate Mesh")
        self.btn_gen_mesh.setObjectName("amber")
        self.btn_gen_mesh.setToolTip("Generate the triangular mesh and insert cracks")
        fm.addRow("", self.btn_gen_mesh)
        self.lbl_mesh_info = mk_lbl("Mesh not yet generated.", "sub")
        fm.addRow("", self.lbl_mesh_info)
        lv_2d.addWidget(grp_mesh)

        grp_2d_cracks = QGroupBox("2D Crack Lines (Y positions)")
        cv2d = QVBoxLayout(grp_2d_cracks); cv2d.setSpacing(6)
        cv2d.addWidget(mk_lbl(
            "Click on the 1D bar canvas to set crack Y positions,\n"
            "or type comma-separated values below.", "sub"))
        self.txt_crack_ys = QLineEdit()
        self.txt_crack_ys.setPlaceholderText("e.g.  0.5, 1.0, 1.5  (metres from base)")
        self.txt_crack_ys.setToolTip("Comma-separated Y positions for horizontal crack lines")
        cv2d.addWidget(self.txt_crack_ys)
        self.chk_sync_cracks = QCheckBox("Sync crack Y from 1D bar canvas clicks")
        self.chk_sync_cracks.setChecked(True)
        cv2d.addWidget(self.chk_sync_cracks)
        lv_2d.addWidget(grp_2d_cracks)
        lv.addWidget(self.w_2d)

        # ── Concrete (shared) ────────────────────────────────────────────────
        grp2 = QGroupBox("Concrete"); form2 = QFormLayout(grp2); form2.setSpacing(8)
        self.sb_fc = dsb(30.0,  1.0, 200., 1, 1.,  tip="f'c (MPa)")
        self.sb_ag = dsb(16.0,  1.0,  50., 1, 1.,  tip="Max aggregate size a_g (mm)")
        self.sb_w0 = dsb(0.10, 0.001,  5., 3, 0.01,tip="Initial crack width w0 (mm)")
        self.chk_auto = QCheckBox("Auto kn/kt  (Divakar Eq.31 + Ruggiero Eq.32)")
        self.chk_auto.setChecked(True)
        self.lbl_auto = mk_lbl("", "sub")
        form2.addRow("f'c (MPa):", self.sb_fc)
        form2.addRow("a_g (mm):",  self.sb_ag)
        form2.addRow("w0 (mm):",   self.sb_w0)
        form2.addRow("",           self.chk_auto)
        form2.addRow("Stiffness:", self.lbl_auto)
        lv.addWidget(grp2)

        # ── 2D Concrete E/ν (shown only in 2D mode) ─────────────────────────
        self.grp_conc2d = QGroupBox("Concrete Elastic (2D)")
        fc2 = QFormLayout(self.grp_conc2d); fc2.setSpacing(8)
        self.sb_Ec = dsb(30000., 100., 1e6, 0, 500., tip="Elastic modulus E_c (MPa)")
        self.sb_nu = dsb(0.20, 0.0, 0.5, 2, 0.01, tip="Poisson's ratio ν")
        fc2.addRow("Ec (MPa):", self.sb_Ec)
        fc2.addRow("ν:",        self.sb_nu)
        self.grp_conc2d.setVisible(False)
        lv.addWidget(self.grp_conc2d)

        # Crack table (read-only summary)
        grp3 = QGroupBox("Crack Interfaces (from drawing)")
        gv3  = QVBoxLayout(grp3)
        self.tbl = QTableWidget(0, 3)
        self.tbl.setHorizontalHeaderLabels(["y pos", "kn", "kt"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.setMaximumHeight(150)
        gv3.addWidget(self.tbl)
        btn_clear = QPushButton("Clear All Cracks"); btn_clear.setObjectName("danger")
        btn_clear.clicked.connect(self._clear_cracks)
        gv3.addWidget(btn_clear)
        lv.addWidget(grp3)

        # Background image for tracing
        grp_img = QGroupBox("Trace Cracks on a Photo  (optional)")
        gv_img  = QVBoxLayout(grp_img); gv_img.setSpacing(6)
        gv_img.addWidget(mk_lbl(
            "Load a photo of your structure, then click on the bar diagram\n"
            "where cracks appear — the Y-position is recorded automatically.", "sub"))
        img_row = QHBoxLayout()
        btn_load_img  = QPushButton("Load Image…");  btn_load_img.setObjectName("flat")
        btn_clear_img = QPushButton("Clear Image");   btn_clear_img.setObjectName("flat")
        self.lbl_img  = mk_lbl("No image loaded", "sub")
        btn_load_img.clicked.connect(self._load_image)
        btn_clear_img.clicked.connect(self._clear_image)
        img_row.addWidget(btn_load_img)
        img_row.addWidget(btn_clear_img)
        img_row.addWidget(self.lbl_img)
        img_row.addStretch()
        gv_img.addLayout(img_row)
        lv.addWidget(grp_img)
        lv.addStretch()
        left_scroll.setWidget(left)
        root.addWidget(left_scroll)

        # ── right panel: canvases (stacked) ──────────────────────────────────
        right     = QWidget()
        right.setStyleSheet(f"background:{BG_PANEL};")
        rv        = QVBoxLayout(right); rv.setContentsMargins(8,16,16,16); rv.setSpacing(6)
        self.lbl_canvas_hint = mk_lbl(
            "Left-click on the bar to place crack interfaces", "sub")
        rv.addWidget(self.lbl_canvas_hint, alignment=Qt.AlignHCenter)
        self.canvas = StructureCanvas()
        self.mesh_canvas = PanelMeshCanvas()
        self.mesh_canvas.setVisible(False)
        rv.addWidget(self.canvas, stretch=1)
        rv.addWidget(self.mesh_canvas, stretch=1)
        root.addWidget(right, stretch=1)

        # stored mesh data for 2D mode
        self._mesh_data = None

        # wire signals
        for sb in [self.sb_L, self.sb_A, self.sb_fc, self.sb_ag, self.sb_w0]:
            sb.valueChanged.connect(self._on_geom_change)
        self.chk_auto.stateChanged.connect(self._on_geom_change)
        self.canvas.cracks_changed.connect(self._update_table)
        self.canvas.cracks_changed.connect(self._sync_crack_ys_to_text)
        self.cmb_comp.currentTextChanged.connect(self._on_comp_type_changed)
        self.btn_gen_mesh.clicked.connect(self._generate_mesh)
        self._on_geom_change()

    # ── component type toggle ────────────────────────────────────────────────
    def _on_comp_type_changed(self, text):
        is_2d = "2D" in text
        self.w_1d.setVisible(not is_2d)
        self.w_2d.setVisible(is_2d)
        self.grp_conc2d.setVisible(is_2d)
        self.canvas.setVisible(True)          # bar canvas always visible (crack Y picker)
        self.mesh_canvas.setVisible(is_2d)
        if is_2d:
            self.lbl_canvas_hint.setText(
                "Left: click bar to set crack Y positions  |  Right: 2D mesh preview")
        else:
            self.lbl_canvas_hint.setText("Left-click on the bar to place crack interfaces")
            self._mesh_data = None
            self.mesh_canvas.clear_mesh()

    def is_2d(self):
        return "2D" in self.cmb_comp.currentText()

    # ── mesh generation ──────────────────────────────────────────────────────
    def _get_crack_ys(self):
        """Get crack Y positions from text field or bar canvas."""
        ys = []
        txt = self.txt_crack_ys.text().strip()
        if txt:
            for s in txt.replace(";", ",").split(","):
                s = s.strip()
                if s:
                    try: ys.append(float(s))
                    except ValueError: pass
        if self.chk_sync_cracks.isChecked():
            for yc in self.canvas.cracks:
                if not any(abs(yc - y) < 0.01 for y in ys):
                    ys.append(yc)
        ys.sort()
        return ys

    def _sync_crack_ys_to_text(self):
        if self.chk_sync_cracks.isChecked() and self.is_2d():
            ys = [f"{y:.3f}" for y in self.canvas.cracks]
            self.txt_crack_ys.setText(", ".join(ys))

    def _generate_mesh(self):
        W = self.sb_pW.value()
        H = self.sb_pH.value()
        nx = self.sb_nx.value()
        ny = self.sb_ny.value()
        crack_ys = self._get_crack_ys()

        # Update bar canvas height to match panel height
        self.canvas.bar_L = H
        self.canvas.update()

        if not crack_ys:
            QMessageBox.warning(self, "No Cracks",
                "Add at least one crack Y position.\n"
                "Click on the bar diagram or type values in the crack Y field.")
            return

        nodes, tris, crack_pairs, crack_rows = generate_panel_mesh(W, H, nx, ny, crack_ys)
        self._mesh_data = {
            "nodes": nodes, "tris": tris, "crack_pairs": crack_pairs,
            "crack_rows": crack_rows,
            "W": W, "H": H, "nx": nx, "ny": ny, "crack_ys": crack_ys
        }
        self.mesh_canvas.set_mesh(nodes, tris, crack_pairs, crack_rows, W, H)
        nn = len(nodes); nt = len(tris); nc = len(crack_pairs)
        self.lbl_mesh_info.setText(
            f"Mesh: {nn} nodes, {nt} tri, {nc} crack links, "
            f"{len(crack_ys)} crack line(s)")
        self._update_table()

    # ── existing methods ─────────────────────────────────────────────────────
    def _on_geom_change(self):
        w = max(self.sb_w0.value(), 0.001)
        fc = self.sb_fc.value()
        Dts = 0.00595 * (25.4/w)**1.6148 * (fc/34.5)**0.193
        Dnw = (2.0 + w) / w
        self.lbl_auto.setText(f"D_ts={Dts:.4f}  D_nw={Dnw:.4f}  MPa/mm")
        self.canvas.set_geometry(
            self.sb_L.value(), self.sb_A.value(),
            fc, self.sb_ag.value(), w, self.chk_auto.isChecked()
        )
        self._update_table()

    def _update_table(self):
        if self.is_2d() and self._mesh_data:
            # Show crack pairs from 2D mesh
            pairs = self._mesh_data["crack_pairs"]
            # Group by y, show summary
            by_y = {}
            for nb, na, y, x in pairs:
                by_y.setdefault(round(y, 6), []).append((nb, na, x))
            self.tbl.setRowCount(len(by_y))
            w = max(self.sb_w0.value(), 0.001)
            fc = self.sb_fc.value()
            kn = (2.0 + w) / w if self.chk_auto.isChecked() else 1e7
            kt = 0.00595 * (25.4/w)**1.6148 * (fc/34.5)**0.193 if self.chk_auto.isChecked() else 1e5
            for i, (y, group) in enumerate(sorted(by_y.items())):
                self.tbl.setItem(i, 0, QTableWidgetItem(f"{y:.4f} ({len(group)} links)"))
                self.tbl.setItem(i, 1, QTableWidgetItem(f"{kn:.3e}"))
                self.tbl.setItem(i, 2, QTableWidgetItem(f"{kt:.3e}"))
        else:
            cracks = self.canvas.get_crack_data()
            self.tbl.setRowCount(len(cracks))
            for i, c in enumerate(cracks):
                self.tbl.setItem(i, 0, QTableWidgetItem(f"{c['y']:.4f}"))
                self.tbl.setItem(i, 1, QTableWidgetItem(f"{c['kn']:.3e}"))
                self.tbl.setItem(i, 2, QTableWidgetItem(f"{c['kt']:.3e}"))

    def _clear_cracks(self):
        self.canvas.cracks.clear()
        self.canvas.cracks_changed.emit()
        self.canvas.update()
        if self.is_2d():
            self.txt_crack_ys.clear()
            self._mesh_data = None
            self.mesh_canvas.clear_mesh()
            self.lbl_mesh_info.setText("Mesh not yet generated.")

    def _load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Background Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)")
        if path:
            ok = self.canvas.load_image(path)
            import os
            name = os.path.basename(path)
            self.lbl_img.setText(name if ok else "Failed to load image")

    def _clear_image(self):
        self.canvas.clear_image()
        self.lbl_img.setText("No image loaded")

    def validate(self):
        errs = []
        if self.is_2d():
            if self.sb_pW.value() <= 0: errs.append("Panel width must be > 0.")
            if self.sb_pH.value() <= 0: errs.append("Panel height must be > 0.")
            if not self._mesh_data:
                errs.append("Generate the 2D mesh first (click Generate Mesh).")
            elif not self._mesh_data["crack_pairs"]:
                errs.append("No crack interfaces in mesh. Add crack Y positions and regenerate.")
        else:
            if self.sb_L.value() <= 0: errs.append("Bar length must be > 0.")
            if self.sb_A.value() <= 0: errs.append("Area must be > 0.")
            if not self.canvas.cracks:  errs.append("Add at least one crack interface (click the bar).")
        return errs

    def get_params(self):
        p = {
            "component_type": "2D" if self.is_2d() else "1D",
            "bar_length": self.sb_L.value(), "bar_area": self.sb_A.value(),
            "fc": self.sb_fc.value(), "ag": self.sb_ag.value(),
            "w0": self.sb_w0.value(), "auto_stiffness": self.chk_auto.isChecked(),
            "crack_data": self.canvas.get_crack_data(),
        }
        if self.is_2d():
            p["panel_W"] = self.sb_pW.value()
            p["panel_H"] = self.sb_pH.value()
            p["panel_t"] = self.sb_pt.value()
            p["panel_Ec"] = self.sb_Ec.value()
            p["panel_nu"] = self.sb_nu.value()
            p["mesh_nx"] = self.sb_nx.value()
            p["mesh_ny"] = self.sb_ny.value()
            p["crack_ys"] = self._get_crack_ys()
            if self._mesh_data:
                # Serialize mesh data for the runner
                md = self._mesh_data
                p["mesh_nodes"] = {str(k): list(v) for k, v in md["nodes"].items()}
                p["mesh_tris"] = [[e, n1, n2, n3] for e, n1, n2, n3 in md["tris"]]
                p["mesh_crack_pairs"] = [[nb, na, y, x] for nb, na, y, x in md["crack_pairs"]]
        return p


# =============================================================================
# Tab: Material & Plasticity
# =============================================================================
class MaterialTab(QWidget):
    PRESETS = {
        "Default":      [0.30, 1.0, 0.20, 0.5, 0.18,  0.75],
        "PC9":          [0.20, 4.0, 0.15, 0.5, 0.15, -1.00],
        "R-30,0.5/2.0": [0.35, 2.0, 0.60, 0.4, 0.15,  0.75],
        "Monotonic":    [1.00, 1.0, 0.20, 0.5, 0.18,  0.75],
        "Conservative": [0.10, 1.0, 0.10, 0.0, 0.00, -1.00],
    }
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self); outer.setContentsMargins(16,16,16,16); outer.setSpacing(10)
        outer.addWidget(mk_lbl("Reinforcement & Crack Plasticity", "heading"))
        outer.addWidget(mk_lbl("6 parameters controlling crack interface cyclic behaviour", "sub"))

        # Rebar
        grp = QGroupBox("Reinforcement Material")
        form = QFormLayout(grp); form.setSpacing(8)
        self.cmb_mat = QComboBox(); self.cmb_mat.addItems(["ElasticPP","Steel02","Elastic"])
        self.sb_Es   = dsb(200000., 1., 1e9, 1, 1000., tip="Young's modulus E_s (MPa)")
        self.sb_fsy  = dsb(500.,    1., 1e6, 1,   10., tip="Yield stress f_sy (MPa)")
        self.sb_b    = dsb(0.01,   0., 1.,  4, 0.005, tip="Strain hardening ratio b (Steel02)")
        self.sb_R0   = dsb(15.0,   0., 30., 2, 1.0)
        self.sb_cR1  = dsb(0.925,  0., 1.,  4, 0.01)
        self.sb_cR2  = dsb(0.150,  0., 1.,  4, 0.01)
        for row_lbl, widget in [
            ("Type:",        self.cmb_mat), ("Es (MPa):",  self.sb_Es),
            ("fsy (MPa):",   self.sb_fsy),  ("b:",         self.sb_b),
            ("R0:",          self.sb_R0),   ("cR1:",       self.sb_cR1), ("cR2:", self.sb_cR2)
        ]:
            form.addRow(row_lbl, widget)
        outer.addWidget(grp)

        # 6 Plasticity params
        PARAMS = [
            ("rho_hat", "ρ̂  dilation",    0.30,  0.10, 1.00, 0.05, 3,
             "Interlock dilation factor ρ̂  (Eq.19)\n1.0=associative(monotonic)  0.3=typical cyclic"),
            ("rho_act", "ρᵃᶜᵗ rev.dil.",  1.00,   1.0,  5.0,  0.5, 3,
             "Activation dilation ρᵃᶜᵗ (Eq.26-27)\nControls rubble rearrangement on slip reversal"),
            ("mu_act",  "μᵃᶜᵗ friction",  0.20,  0.10, 0.60, 0.05, 4,
             "Unloading friction coefficient μᵃᶜᵗ (Eq.25)\nRange 0.1-0.6 (Fig.7b)"),
            ("zeta",    "ζ  engagement",  0.50,   0.0,  0.5, 0.05, 3,
             "Re-engagement ratio ζ (Eq.28)\ns_brk = ζ × s_max   0.5 recommended"),
            ("chi",     "χ  cohesion",    0.18,  0.00, 0.18, 0.01, 4,
             "Residual cohesion ratio χ (Eq.24)\n0.18=MCFT(rough)   0.0=smooth crack"),
            ("kappa",   "κ  roughness",   0.75, -1.00, 1.00, 0.05, 3,
             "Roughness interpolation rate κ (Eq.30)\n>0=pinched  <0=full loops"),
        ]
        grp2 = QGroupBox("Crack Plasticity Parameters")
        grid = QGridLayout(grp2); grid.setSpacing(8)
        self.spins = {}
        for i, (key, label, default, lo, hi, step, dec, tip) in enumerate(PARAMS):
            row = i // 2; col = (i % 2) * 3
            lb = QLabel(label); lb.setObjectName("param"); lb.setToolTip(tip); lb.setFixedWidth(130)
            sb = dsb(default, lo, hi, dec, step, w=110, tip=tip)
            rg = mk_lbl(f"[{lo}, {hi}]", "sub")
            grid.addWidget(lb, row, col); grid.addWidget(sb, row, col+1); grid.addWidget(rg, row, col+2)
            self.spins[key] = sb
        outer.addWidget(grp2)

        # Presets
        grp3 = QGroupBox("Presets  (paper best-fit values, Table 2)")
        pr   = QHBoxLayout(grp3)
        for name in self.PRESETS:
            btn = QPushButton(name); btn.setObjectName("flat")
            btn.clicked.connect(lambda _, n=name: self._preset(n))
            pr.addWidget(btn)
        pr.addStretch()
        outer.addWidget(grp3)

        # ── Crack Interface Material ──────────────────────────────────────────
        grp_ci = QGroupBox("Crack Interface Material")
        vci    = QVBoxLayout(grp_ci); vci.setSpacing(8)

        h_sel = QHBoxLayout()
        h_sel.addWidget(mk_lbl("Type:", "param"))
        self.cmb_crack_mat = QComboBox()
        self.cmb_crack_mat.addItems([
            "Elastic Springs (kn/kt)",
            "EPPGap Macro (4-spring shear)",
            "MultiSurfCrack2D (custom)",
        ])
        self.cmb_crack_mat.setToolTip(
            "Elastic Springs: uses kn / kt values from the crack table in Geometry tab\n"
            "MultiSurfCrack2D: custom C++ OpenSees material — requires a custom "
            "OpenSeesPy build that includes MultiSurfCrack2D.\n"
            "If the material is not found at run-time the GUI automatically falls "
            "back to Elastic Springs and shows a warning.")
        h_sel.addWidget(self.cmb_crack_mat)
        h_sel.addStretch()
        vci.addLayout(h_sel)

        # --- EPPGap Macro parameter panel (hidden until selected) ----------------
        self.grp_eppgap = QGroupBox("EPPGap Macro Parameters (4-spring shear)")
        self.grp_eppgap.setVisible(False)
        g_epp = QFormLayout(self.grp_eppgap); g_epp.setSpacing(8)
        self.sb_epp_fy = dsb(0.50, 0.01, 50., 3, 0.05,
            tip="Shear yield strength v_y (MPa) per crack link")
        self.sb_epp_gap = dsb(0.01, 0.0, 1.0, 3, 0.005,
            tip="Gap distance (mm) before shear spring engages — models crack opening clearance")
        self.sb_epp_eta = dsb(0.02, 0.0, 1.0, 3, 0.005,
            tip="Hardening ratio η for the EPP spring after gap closure")
        g_epp.addRow("v_y (MPa):", self.sb_epp_fy)
        g_epp.addRow("gap (mm):", self.sb_epp_gap)
        g_epp.addRow("η hardening:", self.sb_epp_eta)
        g_epp.addRow("", mk_lbl(
            "4 directional EPPGap springs per crack link:\n"
            "  +X, −X, +Y (opening), −Y (closing contact)\n"
            "Shear springs have gap = crack opening clearance.", "sub"))
        vci.addWidget(self.grp_eppgap)

        # --- MultiSurfCrack2D parameter panel (hidden until selected) ---------
        self.grp_msc = QGroupBox("MultiSurfCrack2D Parameters")
        self.grp_msc.setVisible(False)
        g_msc = QGridLayout(self.grp_msc); g_msc.setSpacing(8)

        MSC_PARAMS = [
            # key            label              default   lo     hi    step  dec  tooltip
            ("msc_fc",      "f\u2019c (MPa)",    30.0,   1.0,  200.0, 1.0,   1,
             "Concrete compressive strength f\u2019c (MPa)"),
            ("msc_ag",      "a\u1d67 (mm)",       16.0,   1.0,   50.0, 1.0,   1,
             "Maximum aggregate size a\u1d67 (mm)"),
            ("msc_w0",      "w\u2080 (mm)",        0.10,  0.001,  5.0, 0.01,  3,
             "Initial crack width w\u2080 (mm) — sets the reference vci\u2098\u2090\u02e3"),
            ("msc_rho_hat", "\u03c1\u0302 dilation",  0.30,  0.10,  1.0, 0.05,  3,
             "Interlock dilation factor \u03c1\u0302 (Eq.19)\n"
             "1.0 = associative / monotonic,  0.3 = typical cyclic"),
            ("msc_rho_act", "\u03c1\u1d43\u1d9c\u1d57 rev.dil.", 1.00, 1.0, 5.0, 0.5, 3,
             "Activation dilation \u03c1\u1d43\u1d9c\u1d57 (Eq.26-27)\n"
             "Controls rubble rearrangement on slip reversal"),
            ("msc_mu_act",  "\u03bc\u1d43\u1d9c\u1d57 friction", 0.20, 0.10, 0.60, 0.05, 4,
             "Unloading friction coefficient \u03bc\u1d43\u1d9c\u1d57 (Eq.25)  range 0.1-0.6"),
            ("msc_zeta",    "\u03b6 engagement",  0.50,  0.0,  0.5, 0.05,  3,
             "Re-engagement ratio \u03b6 (Eq.28)\n"
             "s_brk = \u03b6 \u00d7 s_max   (0.5 recommended)"),
            ("msc_chi",     "\u03c7 cohesion",    0.18,  0.0,  0.18, 0.01,  4,
             "Residual cohesion ratio \u03c7 (Eq.24)\n"
             "0.18 = MCFT rough,  0.0 = smooth crack"),
            ("msc_kappa",   "\u03ba roughness",   0.75, -1.0,  1.0,  0.05,  3,
             "Roughness interpolation rate \u03ba (Eq.30)\n"
             ">0 = pinched loops,  <0 = full loops"),
        ]
        self.msc_spins = {}
        for idx, (key, label, default, lo, hi, step, dec, tip) in enumerate(MSC_PARAMS):
            row = idx // 3; col = (idx % 3) * 3
            lb = mk_lbl(label, "param"); lb.setToolTip(tip)
            sb = dsb(default, lo, hi, dec, step, w=100, tip=tip)
            g_msc.addWidget(lb, row, col)
            g_msc.addWidget(sb, row, col + 1)
            self.msc_spins[key] = sb

        note = mk_lbl(
            "Note: if MultiSurfCrack2D is not found in the WSL OpenSeesPy build, "
            "the runner automatically falls back to Elastic Springs and shows a "
            "[WARNING] in the console.", "sub")
        note.setWordWrap(True)
        vci.addWidget(self.grp_msc)
        vci.addWidget(note)
        outer.addWidget(grp_ci)

        self.cmb_crack_mat.currentTextChanged.connect(self._on_crack_mat_changed)
        outer.addStretch()

    def _preset(self, name):
        keys = ["rho_hat","rho_act","mu_act","zeta","chi","kappa"]
        for k, v in zip(keys, self.PRESETS[name]):
            self.spins[k].setValue(v)

    def _on_crack_mat_changed(self, text):
        self.grp_msc.setVisible("MultiSurfCrack2D" in text)
        self.grp_eppgap.setVisible("EPPGap" in text)

    def get_params(self):
        p = {"mat_type": self.cmb_mat.currentText(), "Es": self.sb_Es.value(),
             "fsy": self.sb_fsy.value(), "hardening_ratio": self.sb_b.value(),
             "R0": self.sb_R0.value(), "cR1": self.sb_cR1.value(), "cR2": self.sb_cR2.value(),
             "crack_mat_type": self.cmb_crack_mat.currentText()}
        for k, sb in self.spins.items(): p[k] = sb.value()
        for k, sb in self.msc_spins.items(): p[k] = sb.value()
        # EPPGap params
        p["epp_fy"]  = self.sb_epp_fy.value()
        p["epp_gap"] = self.sb_epp_gap.value()
        p["epp_eta"] = self.sb_epp_eta.value()
        return p


# =============================================================================
# Tab: Analysis
# =============================================================================
class AnalysisTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self); outer.setContentsMargins(16,16,16,16); outer.setSpacing(10)
        outer.addWidget(mk_lbl("Analysis Settings", "heading"))
        grp  = QGroupBox("Configuration")
        form = QFormLayout(grp); form.setSpacing(8)

        self.cmb_ele  = QComboBox(); self.cmb_ele.addItems(["Truss","corotTruss"])
        self.cmb_type = QComboBox(); self.cmb_type.addItems(["DisplacementControl","LoadControl"])
        self.sb_di    = dsb(0.0005, 1e-6, 1e3, 6, 0.0001,
                            tip="Displacement increment per step (same units as L)")
        self.sb_tgt   = dsb(0.05,   0.0,  1e4, 6, 0.01,
                            tip="Target total displacement (DisplacementControl only)")
        self.sb_li    = dsb(0.01,   1e-6, 1.0, 6, 0.01,
                            tip="Load increment (fraction of Fy, LoadControl only)")
        self.cmb_alg  = QComboBox()
        self.cmb_alg.addItems(["NewtonLineSearch","Newton","KrylovNewton","ModifiedNewton"])
        self.sb_tol   = dsb(1e-8, 1e-14, 1e-2, 12, 1e-9, tip="Convergence tolerance")
        self.sb_iter  = isb(400, 1, 5000, tip="Max iterations per step")
        self.sb_lam   = dsb(50.0, 0.1, 1e9, 1, 5.0, tip="Stop if load factor exceeds this")

        rows = [
            ("Element type:",       self.cmb_ele),
            ("Analysis type:",      self.cmb_type),
            ("Disp. increment:",    self.sb_di),
            ("Target displacement:",self.sb_tgt),
            ("Load increment:",     self.sb_li),
            ("Algorithm:",          self.cmb_alg),
            ("Tolerance:",          self.sb_tol),
            ("Max iterations:",     self.sb_iter),
            ("Load factor cap λ:",  self.sb_lam),
        ]
        for row_txt, widget in rows:
            form.addRow(row_txt, widget)
        outer.addWidget(grp); outer.addStretch()

    def get_params(self):
        return {
            "ele_type": self.cmb_ele.currentText(),
            "analysis_type": self.cmb_type.currentText(),
            "disp_incr": self.sb_di.value(), "target_disp": self.sb_tgt.value(),
            "load_incr": self.sb_li.value(), "algorithm": self.cmb_alg.currentText(),
            "tol": self.sb_tol.value(), "max_iter": self.sb_iter.value(),
            "max_load_factor": self.sb_lam.value(),
        }


# =============================================================================
# Tab: Run
# =============================================================================
class RunTab(QWidget):
    run_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self); outer.setContentsMargins(16,16,16,16); outer.setSpacing(10)
        outer.addWidget(mk_lbl("Run Analysis  (Windows GUI → WSL OpenSeesPy)", "heading"))

        # WSL path setting
        grp_wsl = QGroupBox("WSL Environment")
        wsl_form = QFormLayout(grp_wsl); wsl_form.setSpacing(6)
        self.wsl_activate = QLineEdit("source ~/ops_env/bin/activate")
        self.wsl_activate.setToolTip(
            "WSL bash command to activate your Python env with OpenSeesPy.\n"
            "Examples:\n"
            "  source ~/ops_env/bin/activate   (virtualenv)\n"
            "  conda activate opensees          (conda)\n"
            "  true                             (if openseespy in system python)")
        wsl_form.addRow("Activate command:", self.wsl_activate)
        outer.addWidget(grp_wsl)

        # Run / clear buttons
        brow = QHBoxLayout()
        self.btn_run   = QPushButton("▶  Run Analysis")
        self.btn_run.setObjectName("success")
        self.btn_run.setMinimumHeight(38)
        self.btn_clear = QPushButton("Clear Console")
        self.btn_clear.setObjectName("flat")
        brow.addWidget(self.btn_run); brow.addWidget(self.btn_clear); brow.addStretch()
        outer.addLayout(brow)

        self.lbl_status = mk_lbl("Ready. Draw cracks on Geometry tab, then click Run Analysis.", "sub")
        outer.addWidget(self.lbl_status)

        grp = QGroupBox("Console Output")
        lay = QVBoxLayout(grp)
        self.console = QTextEdit(); self.console.setReadOnly(True)
        self.console.setMinimumHeight(300)
        lay.addWidget(self.console)
        outer.addWidget(grp, stretch=1)

        self.btn_run.clicked.connect(self.run_requested.emit)
        self.btn_clear.clicked.connect(self.console.clear)

    def get_activate(self):
        return self.wsl_activate.text().strip() or "true"

    def append(self, msg):
        self.console.append(msg)
        self.console.verticalScrollBar().setValue(
            self.console.verticalScrollBar().maximum())

    def set_status(self, msg, ok=True):
        color = C2 if ok else C3
        self.lbl_status.setStyleSheet(f"color:{color};font-weight:bold;")
        self.lbl_status.setText(msg)


# =============================================================================
# Tab: Results
# =============================================================================
class ResultsTab(QWidget):
    COLORS = [C1, C2, C3, C4, "#c9d1d9", "#8b949e"]

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self); outer.setContentsMargins(16,16,16,16); outer.setSpacing(8)
        outer.addWidget(mk_lbl("Analysis Results", "heading"))

        ctrl = QHBoxLayout()
        self.cmb_plot  = QComboBox()
        self.cmb_plot.addItems([
            "Force–Displacement", "Crack Opening History",
            "Crack Slip History",  "Normal Stress σn",
            "Shear Stress vci",    "Stress Space (σn vs vci)",
            "Shear Force vs Slip (hysteresis)",
            "Normal Force vs Opening (hysteresis)",
        ])
        self.cmb_crack = QComboBox(); self.cmb_crack.setFixedWidth(200)
        self.btn_rp   = QPushButton("Replot");      self.btn_rp.setObjectName("flat")
        self.btn_save = QPushButton("Save PNG");    self.btn_save.setObjectName("flat")
        self.btn_csv  = QPushButton("Export CSV");  self.btn_csv.setObjectName("flat")
        for w in [mk_lbl("Plot:"), self.cmb_plot,
                  mk_lbl("Crack:"), self.cmb_crack,
                  self.btn_rp, self.btn_save, self.btn_csv]:
            ctrl.addWidget(w)
        ctrl.addStretch()
        outer.addLayout(ctrl)

        self.fig = Figure(facecolor=BG_DEEP, tight_layout=True)
        self.ax  = self.fig.add_subplot(111)
        self._sty()
        self.canv = FigureCanvas(self.fig)
        self.tb   = NavigationToolbar(self.canv, self)
        self.tb.setStyleSheet(f"background:{BG_PANEL};color:{TXT};")
        outer.addWidget(self.tb)
        outer.addWidget(self.canv, stretch=1)

        self._reset()
        self.cmb_plot.currentTextChanged.connect(self.replot)
        self.cmb_crack.currentIndexChanged.connect(self.replot)
        self.btn_rp.clicked.connect(self.replot)
        self.btn_save.clicked.connect(self._save)
        self.btn_csv.clicked.connect(self._csv)

    def _sty(self):
        self.ax.set_facecolor(BG_PANEL)
        self.ax.tick_params(colors=TXTS, labelsize=9)
        self.ax.xaxis.label.set_color(TXT)
        self.ax.yaxis.label.set_color(TXT)
        self.ax.title.set_color(C1)
        for s in self.ax.spines.values(): s.set_edgecolor(BORDER)
        self.ax.grid(True, alpha=0.15, color=BORDER, linestyle="--")

    def _reset(self):
        self._d=np.array([]); self._f=np.array([]); self._fy=1.
        self._cp=np.array([]); self._co=[]; self._cs=[]; self._sn=[]; self._vci=[]

    def set_results(self, r):
        self._d=r["disp"]; self._f=r["force"]; self._fy=r.get("fy",1.)
        self._cp=r.get("crack_positions",np.array([]))
        self._co=r.get("crack_openings",[]); self._cs=r.get("crack_slips",[])
        self._sn=r.get("crack_sigma_n",[]); self._vci=r.get("crack_vci",[])
        self.cmb_crack.blockSignals(True); self.cmb_crack.clear()
        self.cmb_crack.addItem("All Cracks")
        for i,y in enumerate(self._cp): self.cmb_crack.addItem(f"Crack {i+1}  y={y:.3f}")
        self.cmb_crack.blockSignals(False); self.replot()

    def replot(self):
        if self._d.size == 0: return
        self.ax.cla(); self._sty()
        sel  = self.cmb_crack.currentIndex()
        mode = self.cmb_plot.currentText()
        C    = self.COLORS

        def series(data_list, ylabel, title):
            if not data_list: self.ax.set_title("No data"); self.canv.draw(); return
            items = list(range(len(data_list))) if sel<=0 else [sel-1]
            for i in items:
                arr = data_list[i]
                lbl_text = (f"Crack {i+1} y={self._cp[i]:.3f}" if i < len(self._cp)
                            else f"Crack {i+1}")
                self.ax.plot(np.arange(len(arr)), arr,
                             color=C[i%len(C)], lw=1.6, label=lbl_text)
            self.ax.set_xlabel("Step"); self.ax.set_ylabel(ylabel); self.ax.set_title(title)
            self.ax.legend(facecolor=BG_CARD, edgecolor=BORDER, labelcolor=TXT, fontsize=9)

        if mode == "Force–Displacement":
            self.ax.plot(self._d, self._f, color=C1, lw=1.8, label="Response")
            self.ax.axhline(self._fy, ls="--", lw=1, color=C3, label=f"Fy={self._fy:.2f}")
            self.ax.set_xlabel("Displacement"); self.ax.set_ylabel("Force")
            self.ax.set_title("Load–Displacement Response")
            self.ax.legend(facecolor=BG_CARD, edgecolor=BORDER, labelcolor=TXT, fontsize=9)
        elif mode == "Crack Opening History": series(self._co, "Opening (mm)", "Crack Opening")
        elif mode == "Crack Slip History":    series(self._cs, "Slip (mm)",    "Crack Slip")
        elif mode == "Normal Stress σn":      series(self._sn, "σn (MPa)",     "Normal Stress")
        elif mode == "Shear Stress vci":      series(self._vci,"vci (MPa)",    "Shear Stress")
        elif mode == "Stress Space (σn vs vci)":
            if not self._sn: self.ax.set_title("No data"); self.canv.draw(); return
            items = list(range(len(self._sn))) if sel<=0 else [sel-1]
            for i in items:
                n = min(len(self._sn[i]), len(self._vci[i]))
                self.ax.plot(self._sn[i][:n], self._vci[i][:n],
                             color=C[i%len(C)], lw=1.2, label=f"Crack {i+1}")
            self.ax.set_xlabel("σn (MPa)"); self.ax.set_ylabel("vci (MPa)")
            self.ax.set_title("Stress Space")
            self.ax.legend(facecolor=BG_CARD, edgecolor=BORDER, labelcolor=TXT, fontsize=9)
        elif mode == "Shear Force vs Slip (hysteresis)":
            if not self._cs or not self._vci:
                self.ax.set_title("No data"); self.canv.draw(); return
            items = list(range(len(self._cs))) if sel<=0 else [sel-1]
            for i in items:
                n = min(len(self._cs[i]), len(self._vci[i]))
                lbl_text = (f"Crack {i+1} y={self._cp[i]:.3f}" if i < len(self._cp)
                            else f"Crack {i+1}")
                self.ax.plot(self._cs[i][:n], self._vci[i][:n],
                             color=C[i%len(C)], lw=1.2, label=lbl_text)
            self.ax.set_xlabel("Slip (mm)"); self.ax.set_ylabel("vci (MPa)")
            self.ax.set_title("Shear Force vs Slip — Crack Hysteresis")
            self.ax.legend(facecolor=BG_CARD, edgecolor=BORDER, labelcolor=TXT, fontsize=9)
        elif mode == "Normal Force vs Opening (hysteresis)":
            if not self._co or not self._sn:
                self.ax.set_title("No data"); self.canv.draw(); return
            items = list(range(len(self._co))) if sel<=0 else [sel-1]
            for i in items:
                n = min(len(self._co[i]), len(self._sn[i]))
                lbl_text = (f"Crack {i+1} y={self._cp[i]:.3f}" if i < len(self._cp)
                            else f"Crack {i+1}")
                self.ax.plot(self._co[i][:n], self._sn[i][:n],
                             color=C[i%len(C)], lw=1.2, label=lbl_text)
            self.ax.set_xlabel("Opening (mm)"); self.ax.set_ylabel("σn (MPa)")
            self.ax.set_title("Normal Force vs Opening — Crack Hysteresis")
            self.ax.legend(facecolor=BG_CARD, edgecolor=BORDER, labelcolor=TXT, fontsize=9)
        self.canv.draw()

    def _save(self):
        p, _ = QFileDialog.getSaveFileName(self,"Save","response.png","PNG (*.png);;PDF (*.pdf)")
        if p: self.fig.savefig(p, dpi=150, bbox_inches="tight", facecolor=self.fig.get_facecolor())

    def _csv(self):
        if self._d.size==0: return
        p, _ = QFileDialog.getSaveFileName(self,"CSV","results.csv","CSV (*.csv)")
        if not p: return
        n=len(self._d)
        cols=[np.arange(1,n+1), self._d, self._f, self._f/(self._fy or 1.)]
        hdrs=["Step","Displacement","Force","F_Fy"]
        for i, a in enumerate(self._co):
            pad=np.zeros(n); pad[:len(a)]=a; cols.append(pad); hdrs.append(f"C{i+1}_Opening")
        for i, a in enumerate(self._cs):
            pad=np.zeros(n); pad[:len(a)]=a; cols.append(pad); hdrs.append(f"C{i+1}_Slip")
        for i, a in enumerate(self._vci):
            pad=np.zeros(n); pad[:len(a)]=a; cols.append(pad); hdrs.append(f"C{i+1}_vci")
        np.savetxt(p, np.column_stack(cols), delimiter=",", header=",".join(hdrs), comments="")


# =============================================================================
# Tab: Yield Surface Viewer
# =============================================================================
class YieldTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self); outer.setContentsMargins(16,16,16,16); outer.setSpacing(10)
        outer.addWidget(mk_lbl("Yield Surface Preview", "heading"))
        outer.addWidget(mk_lbl(
            "F^lok (parabolic interlock) + F^act (hyperbolic activation) in σn–vci space.", "sub"))

        ctrl = QHBoxLayout()
        self._fields = {}
        for txt, attr, val, lo, hi, step in [
            ("f'c (MPa):", "fc",    30.0, 1., 200., 1.),
            ("w0 (mm):",   "w0",    0.10, 0.001,5., 0.05),
            ("a_g (mm):",  "ag",    16.0, 1., 50.,  1.),
            ("κ:",         "kappa", 0.75,-1., 1.,  0.05),
            ("μᵃᶜᵗ:",      "mu",    0.20, 0.1, 0.6, 0.05),
        ]:
            ctrl.addWidget(mk_lbl(txt))
            sb = dsb(val, lo, hi, step=step, w=90)
            self._fields[attr] = sb; ctrl.addWidget(sb)
        btn = QPushButton("Update"); btn.clicked.connect(self._plot)
        ctrl.addWidget(btn); ctrl.addStretch()
        outer.addLayout(ctrl)

        self.fig = Figure(facecolor=BG_DEEP, tight_layout=True)
        self.ax  = self.fig.add_subplot(111)
        self._sty()
        self.canv = FigureCanvas(self.fig)
        tb = NavigationToolbar(self.canv, self)
        tb.setStyleSheet(f"background:{BG_PANEL};color:{TXT};")
        outer.addWidget(tb); outer.addWidget(self.canv, stretch=1)
        self._plot()

    def _sty(self):
        self.ax.set_facecolor(BG_PANEL)
        self.ax.tick_params(colors=TXTS, labelsize=9)
        self.ax.xaxis.label.set_color(TXT); self.ax.yaxis.label.set_color(TXT)
        self.ax.title.set_color(C1)
        for s in self.ax.spines.values(): s.set_edgecolor(BORDER)
        self.ax.grid(True, alpha=0.15, color=BORDER, linestyle="--")

    def _plot(self):
        self.ax.cla(); self._sty()
        fc = self._fields["fc"].value(); w = max(self._fields["w0"].value(), 0.001)
        ag = self._fields["ag"].value(); kappa = self._fields["kappa"].value()
        mu = self._fields["mu"].value()
        vmax = math.sqrt(max(fc, 0.1)) / (0.31 + 24.*w/(ag+16.))

        sn = np.linspace(-vmax*1.1, 0, 400)

        # F^lok rough r=1  (k=1, chi=0.18)
        h=-1.; k=1.; chi=0.18
        d = h*h/(4.*max(k-chi, 1e-10))
        vci_r = vmax * np.maximum(0., k - (sn/vmax-h)**2/(4.*d))
        self.ax.fill_between(sn, vci_r, -vci_r, alpha=0.07, color=C1)
        self.ax.plot(sn,  vci_r, color=C1, lw=2., label="F^lok rough (r=1)")
        self.ax.plot(sn, -vci_r, color=C1, lw=2.)

        # F^lok smooth r=0  (k=0.6, chi=0)
        ks=0.6; ds=h*h/(4.*max(ks, 1e-10))
        vci_s = vmax * np.maximum(0., ks - (sn/vmax-h)**2/(4.*ds))
        self.ax.plot(sn,  vci_s, color=TXTS, lw=1.2, ls="--", label="F^lok smooth (r=0)")
        self.ax.plot(sn, -vci_s, color=TXTS, lw=1.2, ls="--")

        # Roughness-interpolated at r=0.5
        def r_interp(s, smax, k_):
            x = min(abs(s)/max(smax,1e-10), 1.0)
            if abs(k_)<1e-10: return x
            num=x-k_*x; den=k_-2.*k_*x+1.
            return max(0., min(1., num/den)) if abs(den)>1e-12 else 1.0
        r05 = r_interp(0.5, 1.0, kappa)
        ki  = 0.6*(1-r05)+1.0*r05; ci_chi = 0.18*r05
        di  = h*h/(4.*max(ki-ci_chi, 1e-10))
        vci_i = vmax * np.maximum(0., ki - (sn/vmax-h)**2/(4.*di))
        self.ax.plot(sn,  vci_i, color=C4, lw=1.2, ls=":", label=f"F^lok κ={kappa:.2f} (r=0.5)")
        self.ax.plot(sn, -vci_i, color=C4, lw=1.2, ls=":")

        # F^act hyperbolic
        c_act = 0.18 * k * vmax
        sn2 = np.linspace(-2.*vmax, 0., 400)
        ratio = mu / max(c_act, 1e-12) * sn2
        vci_a = c_act * np.sqrt(1.+ratio**2)
        self.ax.plot(sn2,  vci_a, color=C3, lw=1.5, ls="-.", label=f"F^act μ={mu:.2f}")
        self.ax.plot(sn2, -vci_a, color=C3, lw=1.5, ls="-.")

        # Critical state point
        self.ax.plot(-vmax, vmax, "o", color=C2, ms=9, zorder=6, label="Critical state")
        self.ax.axhline(0, color=BORDER, lw=0.5); self.ax.axvline(0, color=BORDER, lw=0.5)

        self.ax.set_xlabel("σn (MPa)"); self.ax.set_ylabel("vci (MPa)")
        self.ax.set_title(f"Multi-Surface Yield Criterion  |  vcimax={vmax:.3f} MPa  (w={w:.3f}mm, f'c={fc}MPa)")
        self.ax.legend(facecolor=BG_CARD, edgecolor=BORDER, labelcolor=TXT, fontsize=9)
        self.ax.text(0.02, 0.97, f"vcimax={vmax:.3f} MPa\nw0={w:.3f} mm\nf'c={fc:.1f} MPa",
                     transform=self.ax.transAxes, va="top", color=TXTS, fontsize=9, family="monospace")
        self.canv.draw()


# =============================================================================
# Freehand Crack Drawing Canvas + Tab
# =============================================================================
class FreehandCrackCanvas(QWidget):
    """
    Freehand polyline drawing canvas (white draw area, dark surround).
    Each mouse-drag finalises as one crack stroke.
    Bar length controls the Y-axis mapping: pixel-top → bar_length, pixel-bottom → 0.
    """
    strokes_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setMinimumSize(380, 420)
        self.strokes      = []      # list[ list[(x,y)] ]
        self._cur         = None    # stroke being drawn
        self.selected_idx = -1
        self.eraser_mode  = False
        self.brush_size   = 3
        self.bar_length   = 5.0
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self._eraser_pos  = None

    # ── coordinate helpers ────────────────────────────────────────────────────
    def _margin(self):
        return 34, 14, 14, 20   # left, top, right, bottom

    def _px_to_model_y(self, py):
        _, mt, _, mb = self._margin()
        dh = self.height() - mt - mb
        frac = 1.0 - (py - mt) / max(dh, 1)
        return max(0.0, min(self.bar_length, frac * self.bar_length))

    def _model_y_to_px(self, my):
        _, mt, _, mb = self._margin()
        dh = self.height() - mt - mb
        frac = my / max(self.bar_length, 1e-6)
        return int(mt + (1.0 - frac) * dh)

    def get_crack_positions(self):
        """Return mean model-Y for each stroke."""
        out = []
        for stroke in self.strokes:
            if stroke:
                my = sum(self._px_to_model_y(pt[1]) for pt in stroke) / len(stroke)
                out.append(round(my, 4))
        return out

    # ── editing operations ────────────────────────────────────────────────────
    def undo(self):
        if self.strokes:
            self.strokes.pop()
            self.selected_idx = min(self.selected_idx, len(self.strokes) - 1)
            self.strokes_changed.emit()
            self.update()

    def clear_all(self):
        self.strokes.clear(); self._cur = None; self.selected_idx = -1
        self.strokes_changed.emit(); self.update()

    def select(self, idx):
        self.selected_idx = idx; self.update()

    def _erase_near(self, x, y):
        r = self.brush_size * 6
        to_del = []
        for i, stroke in enumerate(self.strokes):
            hit = False
            for j in range(max(1, len(stroke)) - 1):
                x1, y1 = stroke[j]; x2, y2 = stroke[j+1]
                dx = x2 - x1; dy = y2 - y1
                if dx == 0 and dy == 0:
                    if math.hypot(x - x1, y - y1) <= r: hit = True; break
                else:
                    t = max(0., min(1., ((x-x1)*dx + (y-y1)*dy) / (dx*dx + dy*dy)))
                    if math.hypot(x - (x1+t*dx), y - (y1+t*dy)) <= r: hit = True; break
            if not hit and len(stroke) == 1:
                if math.hypot(x - stroke[0][0], y - stroke[0][1]) <= r: hit = True
            if hit:
                to_del.append(i)
        if to_del:
            for i in sorted(to_del, reverse=True): self.strokes.pop(i)
            self.selected_idx = min(self.selected_idx, len(self.strokes) - 1)
            self.strokes_changed.emit(); self.update()

    # ── mouse events ──────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton: return
        x, y = e.x(), e.y()
        if self.eraser_mode:
            self._erase_near(x, y)
        else:
            self._cur = [(x, y)]; self.update()

    def mouseMoveEvent(self, e):
        x, y = e.x(), e.y()
        if self.eraser_mode:
            self._eraser_pos = (x, y)
            if e.buttons() & Qt.LeftButton: self._erase_near(x, y)
        elif self._cur is not None and e.buttons() & Qt.LeftButton:
            self._cur.append((x, y))
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._cur and not self.eraser_mode:
            self.strokes.append(self._cur)
            self.selected_idx = len(self.strokes) - 1
            self.strokes_changed.emit()
            self._cur = None
        elif self._cur:
            self._cur = None
        self.update()

    def leaveEvent(self, _):
        self._eraser_pos = None; self.update()

    # ── paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        ml, mt, mr, mb = self._margin()
        dw = W - ml - mr; dh = H - mt - mb

        # outer background
        p.fillRect(0, 0, W, H, QColor(BG_PANEL))
        # white drawing area
        p.fillRect(ml, mt, dw, dh, QColor("#f5f5f0"))
        p.setPen(QPen(QColor(BORDER), 2))
        p.drawRect(ml, mt, dw, dh)

        # Y-axis ruler (model units, left side)
        p.setPen(QPen(QColor(TXTS), 1))
        p.setFont(QFont("Consolas", 7))
        num_ticks = 10
        for i in range(num_ticks + 1):
            my = self.bar_length * i / num_ticks
            py = self._model_y_to_px(my)
            p.drawLine(ml - 8, py, ml, py)
            if i % 2 == 0 or num_ticks <= 5:
                p.setPen(QPen(QColor(TXTS), 1))
                p.drawText(1, py + 4, f"{my:.2f}")
                p.setPen(QPen(QColor(TXTS), 1))

        # Bar guide overlay (faint vertical bar in centre)
        bw = max(18, min(36, dw // 5))
        bx = ml + dw // 2 - bw // 2
        p.setBrush(QBrush(QColor(160, 160, 160, 55)))
        p.setPen(QPen(QColor(140, 140, 140, 100), 1))
        p.drawRect(bx, mt, bw, dh)
        p.setPen(QPen(QColor(100, 100, 100, 160), 1))
        p.setFont(QFont("Consolas", 7))
        p.drawText(bx + 2, mt + dh - 3, "bar")

        # Finalized strokes
        for i, stroke in enumerate(self.strokes):
            if not stroke: continue
            sel = (i == self.selected_idx)
            pen_clr = QColor(C3) if sel else QColor("#1a66cc")
            pen = QPen(pen_clr, self.brush_size + (2 if sel else 0),
                       Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            if len(stroke) == 1:
                p.drawPoint(int(stroke[0][0]), int(stroke[0][1]))
            else:
                for j in range(len(stroke) - 1):
                    p.drawLine(int(stroke[j][0]),   int(stroke[j][1]),
                               int(stroke[j+1][0]), int(stroke[j+1][1]))
            # label near mean position
            mx  = sum(pt[0] for pt in stroke) / len(stroke)
            mpy = sum(pt[1] for pt in stroke) / len(stroke)
            my_model = self._px_to_model_y(mpy)
            p.setPen(QPen(QColor(C3 if sel else "#993300"), 1))
            p.setFont(QFont("Consolas", 8))
            lx = int(mx) + 8
            if lx + 80 > W - mr: lx = int(mx) - 82
            p.drawText(lx, int(mpy) - 4, f"C{i+1}  y={my_model:.2f}")

        # In-progress stroke
        if self._cur and len(self._cur) > 1:
            pen = QPen(QColor(C2), self.brush_size,
                       Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            for j in range(len(self._cur) - 1):
                p.drawLine(int(self._cur[j][0]),   int(self._cur[j][1]),
                           int(self._cur[j+1][0]), int(self._cur[j+1][1]))

        # Eraser radius indicator
        if self.eraser_mode and self._eraser_pos:
            ex, ey = self._eraser_pos
            r = self.brush_size * 6
            p.setPen(QPen(QColor(C3), 1.5, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(int(ex - r), int(ey - r), 2*r, 2*r)

        # Instruction hint at bottom
        p.fillRect(ml, H - mb, dw, mb, QColor(BG_PANEL))
        p.setPen(QPen(QColor(TXTS), 1))
        p.setFont(QFont("Segoe UI", 8))
        hint = ("Eraser mode — click / drag to delete strokes"
                if self.eraser_mode else
                "Draw mode — drag to trace a crack  |  each stroke = one crack interface")
        p.drawText(ml + 4, H - 5, hint)
        p.end()


class DrawCracksTab(QWidget):
    """
    Freehand crack-drawing tab.
    Users drag freehand strokes on the canvas; each stroke maps to one crack interface
    via its mean Y position. kn/kt defaults are auto-computed and can be edited in the table.
    """
    def __init__(self):
        super().__init__()
        root = QHBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # ── Left: drawing canvas + toolbar ───────────────────────────────────
        left = QWidget(); left.setStyleSheet(f"background:{BG_PANEL};")
        lv = QVBoxLayout(left); lv.setContentsMargins(8, 12, 4, 8); lv.setSpacing(6)
        lv.addWidget(mk_lbl("Freehand Crack Drawing", "heading"))
        lv.addWidget(mk_lbl(
            "Drag on the canvas to draw a crack stroke.  "
            "Each stroke is mapped to a Y position on the bar.", "sub"))

        tb = QHBoxLayout(); tb.setSpacing(6)
        self.btn_undo  = QPushButton("↩  Undo");  self.btn_undo.setObjectName("flat")
        self.btn_clear = QPushButton("Clear All"); self.btn_clear.setObjectName("danger")
        self.btn_erase = QPushButton("⌫  Eraser"); self.btn_erase.setObjectName("flat")
        self.btn_erase.setCheckable(True)
        tb.addWidget(self.btn_undo)
        tb.addWidget(self.btn_clear)
        tb.addWidget(self.btn_erase)
        tb.addWidget(mk_lbl(" Thickness:"))
        self.sld_brush = QSlider(Qt.Horizontal)
        self.sld_brush.setRange(1, 10); self.sld_brush.setValue(3)
        self.sld_brush.setFixedWidth(80)
        self.sld_brush.setToolTip("Stroke / line thickness")
        tb.addWidget(self.sld_brush)
        tb.addStretch()
        lv.addLayout(tb)

        self.fcanvas = FreehandCrackCanvas()
        lv.addWidget(self.fcanvas, stretch=1)
        root.addWidget(left, stretch=2)

        # ── Right: bar params + crack table ──────────────────────────────────
        right = QWidget(); right.setMaximumWidth(360)
        rv = QVBoxLayout(right); rv.setContentsMargins(8, 12, 12, 8); rv.setSpacing(8)
        rv.addWidget(mk_lbl("Crack Table", "heading"))
        rv.addWidget(mk_lbl(
            "Rows are auto-populated from drawn strokes.\n"
            "Edit kn / kt cells to override stiffness.\n"
            "Click a row to highlight the stroke on canvas.", "sub"))

        grp_bar = QGroupBox("Bar Reference  (Y-axis mapping)")
        fb = QFormLayout(grp_bar); fb.setSpacing(6)
        self.sb_L  = dsb(5.0,   0.01, 1e4, 3, 0.1,  tip="Bar length L (synced from Geometry tab)")
        self.sb_fc = dsb(30.0,  1.0,  200., 1, 1.,   tip="f'c (MPa) — for auto kn/kt")
        self.sb_ag = dsb(16.0,  1.0,   50., 1, 1.,   tip="Max aggregate size ag (mm)")
        self.sb_w0 = dsb(0.10,  0.001,  5., 3, 0.01, tip="Initial crack width w0 (mm)")
        fb.addRow("L:",   self.sb_L)
        fb.addRow("f'c:", self.sb_fc)
        fb.addRow("ag:",  self.sb_ag)
        fb.addRow("w0:",  self.sb_w0)
        rv.addWidget(grp_bar)

        self.tbl = QTableWidget(0, 3)
        self.tbl.setHorizontalHeaderLabels(["y pos", "kn", "kt"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        rv.addWidget(self.tbl, stretch=1)
        root.addWidget(right)

        # Wire
        self.btn_undo.clicked.connect(self.fcanvas.undo)
        self.btn_clear.clicked.connect(self.fcanvas.clear_all)
        self.btn_erase.toggled.connect(self._toggle_eraser)
        self.sld_brush.valueChanged.connect(self._on_brush)
        self.fcanvas.strokes_changed.connect(self._update_table)
        self.tbl.itemSelectionChanged.connect(self._on_row_select)
        for sb in [self.sb_L, self.sb_fc, self.sb_ag, self.sb_w0]:
            sb.valueChanged.connect(self._on_bar_changed)

    def _toggle_eraser(self, on):
        self.fcanvas.eraser_mode = on
        self.fcanvas.setCursor(Qt.CrossCursor)   # circle shown in paintEvent
        self.btn_erase.setStyleSheet(
            f"background:{C3};color:{BG_DEEP};font-weight:bold;" if on else "")
        self.fcanvas.update()

    def _on_brush(self, v):
        self.fcanvas.brush_size = v; self.fcanvas.update()

    def _on_bar_changed(self):
        self.fcanvas.bar_length = self.sb_L.value()
        self.fcanvas.update(); self._update_table()

    def _auto_kn_kt(self):
        w  = max(self.sb_w0.value(), 0.001)
        fc = self.sb_fc.value()
        kt = 0.00595 * (25.4 / w)**1.6148 * (fc / 34.5)**0.193
        kn = (2.0 + w) / w
        return kn, kt

    def _update_table(self):
        positions = self.fcanvas.get_crack_positions()
        kn_d, kt_d = self._auto_kn_kt()
        # Preserve user edits for rows that still exist
        old_vals = {}
        for i in range(self.tbl.rowCount()):
            try:
                old_vals[i] = (float(self.tbl.item(i, 1).text()),
                               float(self.tbl.item(i, 2).text()))
            except Exception:
                pass
        self.tbl.blockSignals(True)
        self.tbl.setRowCount(len(positions))
        for i, y in enumerate(positions):
            kn_v, kt_v = old_vals.get(i, (kn_d, kt_d))
            self.tbl.setItem(i, 0, QTableWidgetItem(f"{y:.4f}"))
            self.tbl.setItem(i, 1, QTableWidgetItem(f"{kn_v:.3e}"))
            self.tbl.setItem(i, 2, QTableWidgetItem(f"{kt_v:.3e}"))
        self.tbl.blockSignals(False)

    def _on_row_select(self):
        rows = self.tbl.selectedIndexes()
        if rows:
            self.fcanvas.select(rows[0].row())

    def sync_from_geometry(self, L, fc, ag, w0):
        """Called by MainWindow when Geometry tab params change."""
        for sb, val in [(self.sb_L, L), (self.sb_fc, fc),
                        (self.sb_ag, ag), (self.sb_w0, w0)]:
            sb.blockSignals(True); sb.setValue(val); sb.blockSignals(False)
        self.fcanvas.bar_length = L
        self.fcanvas.update(); self._update_table()

    def get_crack_data(self):
        """Return list of {'y', 'kn', 'kt'} from the crack table."""
        data = []
        for i in range(self.tbl.rowCount()):
            try:
                y  = float(self.tbl.item(i, 0).text())
                kn = float(self.tbl.item(i, 1).text())
                kt = float(self.tbl.item(i, 2).text())
                data.append({"y": y, "kn": kn, "kt": kt})
            except Exception:
                pass
        return data


# =============================================================================
# Tab: Script
# =============================================================================
class ScriptTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self); outer.setContentsMargins(16,16,16,16); outer.setSpacing(8)
        outer.addWidget(mk_lbl("Standalone OpenSeesPy Script", "heading"))
        outer.addWidget(mk_lbl(
            "A self-contained Python script you can run anywhere OpenSeesPy is installed, "
            "share with colleagues, or submit to an HPC cluster.", "sub"))

        brow = QHBoxLayout(); brow.setSpacing(8)
        self.btn_gen  = QPushButton("📋  Generate / Refresh Script")
        self.btn_gen.setObjectName("amber")
        self.btn_gen.setToolTip(
            "Build a standalone script from the current Geometry, Material and Analysis settings.\n"
            "This is also done automatically after every Run.")
        self.btn_copy = QPushButton("Copy to Clipboard")
        self.btn_copy.setObjectName("flat")
        self.btn_copy.setToolTip("Copy entire script to clipboard.")
        self.btn_save = QPushButton("Save .py …")
        self.btn_save.setObjectName("flat")
        self.btn_save.setToolTip("Save script as a .py file.")
        for b in [self.btn_gen, self.btn_copy, self.btn_save]: brow.addWidget(b)
        brow.addStretch()

        self.lbl_hint = QLabel(
            "  Tip: Script is auto-generated after each Run. "
            "Click 📋 Generate / Refresh to create it now from current parameters.")
        self.lbl_hint.setStyleSheet(f"color:{C4};font-size:10px;")
        self.lbl_hint.setWordWrap(True)

        outer.addLayout(brow)
        outer.addWidget(self.lbl_hint)

        self.editor = QTextEdit()
        self.editor.setFont(QFont("Cascadia Code", 10))
        self.editor.setPlaceholderText(
            "# Script not yet generated.\n"
            "# Click  📋 Generate / Refresh Script  above\n"
            "# or use the toolbar button at the top of the window.\n"
            "#\n"
            "# The script is also created automatically after each Run analysis.\n")
        outer.addWidget(self.editor, stretch=1)

        self.btn_copy.clicked.connect(
            lambda: QApplication.clipboard().setText(self.editor.toPlainText()))
        self.btn_save.clicked.connect(self._save)

    def set_script(self, s):
        self.editor.setPlainText(s)
        self.lbl_hint.setText(
            "  Script ready — use Copy or Save .py to export, "
            "or paste into any Python environment with OpenSeesPy installed.")
        self.lbl_hint.setStyleSheet(f"color:{C2};font-size:10px;")

    def _save(self):
        p,_ = QFileDialog.getSaveFileName(self,"Save","opensees_crack.py","Python (*.py)")
        if p: Path(p).write_text(self.editor.toPlainText(), encoding="utf-8")


# =============================================================================
# Runner script (runs inside WSL)
# =============================================================================
RUNNER_PY = r'''
import sys, json, traceback, math
import numpy as np

def vcimax(w, ag, fc):
    w = max(w, 1e-6)
    return math.sqrt(max(fc, 0.1)) / (0.31 + 24.*w/(ag+16.))

def Dts(w, fc):
    w = max(w, 0.001)
    return 0.00595*(25.4/w)**1.6148*(fc/34.5)**0.193

def Dnw(w):
    w = max(w, 0.001)
    return (2.+w)/w

def F_lok(sn, vci, vm, h=-1., k=1., chi=0.18):
    if vm<1e-12: return 1.
    d = h*h/(4.*max(k-chi,1e-10))
    return 4.*d*(abs(vci)/vm-k)+(sn/vm-h)**2

def gF_lok(sn, vci, vm, h=-1., k=1., chi=0.18):
    if vm<1e-12: return [0.,0.]
    d = h*h/(4.*max(k-chi,1e-10))
    return [2.*(sn/vm-h)/vm,
            4.*d*(1. if vci>=0 else -1.)/vm if abs(vci)>1e-12 else 0.]

def F_act(sn, vci, vm, mu=.20, chi_a=.18, k=1.):
    ca=chi_a*k*vm
    if ca<1e-12: return abs(vci)-1e-12
    return abs(vci)/math.sqrt(1.+(mu/ca*sn)**2)-ca

def gF_act(sn, vci, vm, mu=.20, chi_a=.18, k=1.):
    ca=chi_a*k*vm
    if ca<1e-12: return [0., 1. if vci>=0 else -1.]
    r=mu/ca*sn; d3=(1.+r**2)**1.5
    return [-abs(vci)*r*(mu/ca)/d3,
            (1. if vci>=0 else -1.)/math.sqrt(1.+r**2) if abs(vci)>1e-12 else 0.]

def ret_lok(sn, vci, vm, Dn, Dt, rho, h=-1.,k=1.,chi=0.18):
    for _ in range(60):
        F=F_lok(sn,vci,vm,h,k,chi)
        if F<=1e-8: break
        gf=gF_lok(sn,vci,vm,h,k,chi); gg=[rho*gf[0],gf[1]]
        den=gf[0]*Dn*gg[0]+gf[1]*Dt*gg[1]
        if abs(den)<1e-20: break
        dl=F/den; sn-=Dn*gg[0]*dl; vci-=Dt*gg[1]*dl
    return sn, vci

def ret_act(sn, vci, vm, Dn, Dt, rho_a, mu, chi_a, k):
    for _ in range(60):
        F=F_act(sn,vci,vm,mu,chi_a,k)
        if F<=1e-8: break
        gf=gF_act(sn,vci,vm,mu,chi_a,k); gg=[-rho_a*gf[0],gf[1]]
        den=gf[0]*Dn*gg[0]+gf[1]*Dt*gg[1]
        if abs(den)<1e-20: break
        dl=F/den; sn-=Dn*gg[0]*dl; vci-=Dt*gg[1]*dl
    return sn, vci

def r_interp(s, smax, kappa):
    if smax<1e-10: return 1.
    x=min(abs(s)/smax,1.)
    if abs(kappa)<1e-10: return x
    num=x-kappa*x; den=kappa-2.*kappa*x+1.
    return max(0.,min(1.,num/den)) if abs(den)>1e-12 else 1.

class CrackSt:
    def __init__(self, w0, fc, ag, pp):
        self.w=max(w0,.001); self.s=0.; self.sn=0.; self.vci=0.
        self.sm_p=1e-10; self.sm_n=1e-10; self.fc=fc; self.ag=ag; self.pp=pp
    def step(self, dw, ds):
        pp=self.pp
        w=max(self.w+dw,.001); s=self.s+ds
        Dn=Dnw(w); Dt=Dts(w,self.fc); vm=vcimax(w,self.ag,self.fc)
        sm_dir=self.sm_p if s>=0 else self.sm_n
        r=(1. if abs(s)>=sm_dir-1e-10 else r_interp(s,sm_dir,pp['kappa']))
        k=0.6*(1-r)+1.*r; chi=0.18*r
        loading=(abs(s)>=abs(self.s)-1e-12) or (s*self.s>=-1e-12)
        sn_tr=self.sn+Dn*dw; vci_tr=self.vci+Dt*ds
        sbrk=pp['zeta']*sm_dir
        if loading:
            if F_lok(sn_tr,vci_tr,vm,k=k,chi=chi)>1e-10:
                sn_tr,vci_tr=ret_lok(sn_tr,vci_tr,vm,Dn,Dt,pp['rho_hat'],k=k,chi=chi)
            if s>0: self.sm_p=max(self.sm_p,abs(s))
            else:   self.sm_n=max(self.sm_n,abs(s))
        else:
            if F_act(sn_tr,vci_tr,vm,pp['mu_act'],pp['chi'],k)>1e-10 and abs(s)>sbrk:
                sn_o,vci_o=sn_tr,vci_tr
                sn_tr,vci_tr=ret_act(sn_tr,vci_tr,vm,Dn,Dt,pp['rho_act'],pp['mu_act'],pp['chi'],k)
                if F_lok(sn_tr,vci_tr,vm,k=k,chi=chi)>1e-10:
                    sn_tr,vci_tr=ret_lok(sn_o,vci_o,vm,Dn,Dt,pp['rho_hat'],k=k,chi=chi)
        self.w=w; self.s=s; self.sn=sn_tr; self.vci=vci_tr
        return sn_tr, vci_tr

def _try_sys(ops, name):
    try: ops.system(name); return True
    except: return False

def _build(ops, p, at, ln, dof, incr, alg):
    ops.wipeAnalysis(); ops.constraints('Plain'); ops.numberer('RCM')
    if not _try_sys(ops,'UmfPack'): ops.system('BandGeneral')
    ops.test('NormUnbalance',float(p.get('tol',1e-8)),int(p.get('max_iter',400)))
    if alg=='NewtonLineSearch':
        try: ops.algorithm('NewtonLineSearch','-type','Bisection')
        except: ops.algorithm('Newton')
    elif alg=='KrylovNewton': ops.algorithm('KrylovNewton')
    elif alg=='ModifiedNewton': ops.algorithm('ModifiedNewton')
    else: ops.algorithm('Newton')
    if at=='LoadControl': ops.integrator('LoadControl',float(incr))
    else: ops.integrator('DisplacementControl',int(ln),int(dof),float(incr))
    ops.analysis('Static')

def _step(ops, p, at, ln, dof, incr):
    for alg in ['NewtonLineSearch','KrylovNewton','ModifiedNewton','Newton']:
        _build(ops,p,at,ln,dof,incr,alg)
        if ops.analyze(1)==0: return 0,alg
    return -1,'Newton'

def cutback(ops, p, at, ln, dof, incr, mx=12):
    cur=float(incr)
    for c in range(mx+1):
        ok,alg=_step(ops,p,at,ln,dof,cur)
        if ok==0: return 0,cur,c,alg
        cur*=0.5
    return -1,cur,mx,'Newton'

def run_model(p):
    import openseespy.opensees as ops
    disp_l=[]; force_l=[]; open_l=[]; slip_l=[]; sn_l=[]; vci_l=[]; cpos=[]
    status="failed"; msg="failed"; fy=0.
    crack_mat=str(p.get('crack_mat_type','Elastic Springs') or 'Elastic Springs')
    msc2d_ok=False
    try:
        ops.wipe(); ops.model('basic','-ndm',2,'-ndf',2)
        L=float(p['bar_length']); A=float(p['bar_area'])
        Es=float(p['Es']); fsy=float(p['fsy'])
        et=p.get('ele_type','truss') or 'truss'
        if et.lower()=='truss': et='truss'
        cd=sorted(p.get('crack_data',[]),key=lambda c:c['y'])
        cd=[c for c in cd if .001*L<c['y']<.999*L]
        mt=p.get('mat_type','ElasticPP')
        if mt=='ElasticPP':
            ops.uniaxialMaterial('ElasticPP',11,Es,fsy/Es)
            ops.uniaxialMaterial('Elastic',12,max(1e-4,1e-8*Es))
            try: ops.uniaxialMaterial('Parallel',1,11,12)
            except: ops.uniaxialMaterial('Steel02',1,fsy,Es,0.001,15.,.925,.15)
        elif mt=='Steel02':
            ops.uniaxialMaterial('Steel02',1,fsy,Es,float(p.get('hardening_ratio',.01)),
                float(p.get('R0',15.)),float(p.get('cR1',.925)),float(p.get('cR2',.15)))
        else:
            ops.uniaxialMaterial('Elastic',1,Es)
        fc=float(p.get('fc',30.)); ag=float(p.get('ag',16.)); w0=float(p.get('w0',.1))
        pp={k:float(p.get(k,v)) for k,v in
            [('rho_hat',.3),('rho_act',1.),('mu_act',.2),('zeta',.5),('chi',.18),('kappa',.75)]}
        # --- crack interface material availability check ---
        # MultiSurfCrack2D is an NDMaterial (nDMaterial command, zeroLengthND element)
        # Build: bash /mnt/c/Users/himan/multi-surf-crack2D/build_msc2d.sh
        if 'multisurfcrack2d' in crack_mat.lower():
            try:
                _w0c=max(float(p.get('msc_w0',0.1)),0.001)
                _fcc=float(p.get('msc_fc',30.)); _agc=float(p.get('msc_ag',16.))
                _Dt=0.00595*(25.4/_w0c)**1.6148*(_fcc/34.5)**0.193
                _Dn=(2.+_w0c)/_w0c
                ops.nDMaterial('MultiSurfCrack2D',9999,
                    _Dt,0.,0.,_Dn, _Dt,0.,0.,_Dn,
                    _fcc,_agc,0.,1.,
                    float(p.get('msc_rho_hat',0.3)),float(p.get('msc_chi',0.18)),
                    float(p.get('msc_rho_act',1.0)),float(p.get('msc_mu_act',0.2)),
                    float(p.get('msc_chi',0.18)),
                    float(p.get('msc_zeta',0.5)),float(p.get('msc_kappa',0.75)),
                    0.0,_w0c)
                msc2d_ok=True
                ops.wipe(); ops.model('basic','-ndm',2,'-ndf',2)
            except Exception as _msc_e:
                print(f'[WARNING] MultiSurfCrack2D not available ({_msc_e}). '
                      f'Falling back to Elastic Springs (kn/kt).')
                print(f'[INFO] To compile: bash /mnt/c/Users/himan/multi-surf-crack2D/build_msc2d.sh')
                ops.wipe(); ops.model('basic','-ndm',2,'-ndf',2)
        nt=0; elt=0
        def mkn(x,y,fx=1,fy=0):
            nonlocal nt; nt+=1; ops.node(nt,x,y); ops.fix(nt,fx,fy); return nt
        def mkt(i,j):
            nonlocal elt; elt+=1; ops.element(et,elt,i,j,A,1); return elt
        def mkc(i,j,kn,kt,ci):
            nonlocal elt
            if msc2d_ok:
                # NDMaterial via zeroLengthND element
                # De = DeU = diag[Dt, Dn]  (Divakar Eq.31/32)
                mt=2000+ci
                _w0c=max(float(p.get('msc_w0',0.1)),0.001)
                _fcc=float(p.get('msc_fc',30.)); _agc=float(p.get('msc_ag',16.))
                _Ac =float(p.get('bar_area',1.0))
                _Dt =0.00595*(25.4/_w0c)**1.6148*(_fcc/34.5)**0.193
                _Dn =(2.+_w0c)/_w0c
                ops.nDMaterial('MultiSurfCrack2D',mt,
                    _Dt,0.,0.,_Dn, _Dt,0.,0.,_Dn,
                    _fcc,_agc,0.,_Ac,
                    float(p.get('msc_rho_hat',0.3)),float(p.get('msc_chi',0.18)),
                    float(p.get('msc_rho_act',1.0)),float(p.get('msc_mu_act',0.2)),
                    float(p.get('msc_chi',0.18)),
                    float(p.get('msc_zeta',0.5)),float(p.get('msc_kappa',0.75)),
                    0.0,_w0c)
                elt+=1; ops.element('zeroLengthND',elt,i,j,mt)
            else:
                km=max(1e-10*Es,1e-3)
                ops.uniaxialMaterial('Elastic',1000+ci*2,max(float(kt),km))
                ops.uniaxialMaterial('Elastic',1001+ci*2,max(float(kn),km))
                elt+=1; ops.element('zeroLength',elt,i,j,'-mat',1000+ci*2,1001+ci*2,'-dir',1,2)
        base=mkn(0.,0.,1,1); prev=base; states=[]; cnodes=[]
        for ci,crack in enumerate(cd):
            yc=float(crack['y'])
            kn=float(crack.get('kn',1e7)); kt=float(crack.get('kt',1e5))
            if p.get('auto_stiffness',True):
                kn=Dnw(w0)*A; kt=Dts(w0,fc)*A
            nb=mkn(0.,yc); mkt(prev,nb); na=mkn(0.,yc); mkc(nb,na,kn,kt,ci)
            cnodes.append((nb,na,yc)); states.append(CrackSt(w0,fc,ag,pp)); prev=na
        top=mkn(0.,L); mkt(prev,top); ln=top; dof=2; fy=fsy*A
        ops.timeSeries('Linear',1); ops.pattern('Plain',1,1)
        at=p.get('analysis_type','DisplacementControl')
        ops.load(ln,0.,fy if at=='LoadControl' else 1.)
        nc=len(cnodes)
        open_l=[[] for _ in range(nc)]; slip_l=[[] for _ in range(nc)]
        sn_l=[[] for _ in range(nc)]; vci_l=[[] for _ in range(nc)]
        cpos=[float(y) for _,_,y in cnodes]
        pw=[w0]*nc; ps=[0.]*nc
        def collect():
            disp_l.append(ops.nodeDisp(ln,dof)); ops.reactions()
            force_l.append(-ops.nodeReaction(base,dof))
            for k,(nb,na,_) in enumerate(cnodes):
                dw=ops.nodeDisp(na,2)-ops.nodeDisp(nb,2)
                ds=ops.nodeDisp(na,1)-ops.nodeDisp(nb,1)
                snr,vcir=states[k].step(dw-pw[k]+w0,ds-ps[k])
                open_l[k].append(dw); slip_l[k].append(ds)
                sn_l[k].append(snr); vci_l[k].append(vcir)
                pw[k]=dw; ps[k]=ds
        failed=False; fm=""
        ml=float(p.get('max_load_factor',50.))
        if at=='LoadControl':
            incr=float(p.get('load_incr',.01)); steps=max(1,int(1./incr))
            for st in range(steps):
                ok,cur,_,alg=cutback(ops,p,at,ln,dof,incr)
                if ok==0: collect(); incr=min(incr,cur)
                else: failed=True; fm=f"step {st} alg={alg}"; break
        else:
            tgt=float(p.get('target_disp',.05)); incr=float(p.get('disp_incr',.0005))
            steps=max(1,int(abs(tgt)/max(abs(incr),1e-12)))
            for st in range(steps):
                try:
                    if abs(ops.getTime())>ml: failed=True; fm="load factor runaway"; break
                except: pass
                ok,cur,_,alg=cutback(ops,p,at,ln,dof,incr)
                if ok==0: collect(); incr=min(incr,cur)
                else: failed=True; fm=f"step {st} alg={alg}"; break
        status=("ok" if not failed else "partial") if disp_l else "failed"
        msg=f"{len(disp_l)} steps | {nc} crack(s) | {status}"
        if fm: msg+=" | "+fm
        if 'multisurfcrack2d' in crack_mat.lower() and msc2d_ok:
            msg+=" | MultiSurfCrack2D"
        elif 'multisurfcrack2d' in crack_mat.lower() and not msc2d_ok:
            msg+=" | [!] MSC2D unavailable - used Elastic Springs"
    except Exception as e:
        tb=traceback.format_exc(); status="partial" if disp_l else "failed"
        msg=f"Exception: {e}\n{tb}"; print(msg)
    a=lambda x: np.array(x,dtype=float)
    la=lambda x: [a(v) for v in x] if x else []
    return dict(disp=a(disp_l),force=a(force_l),fy=float(fy),crack_positions=a(cpos),
                status=status,message=msg,crack_openings=la(open_l),
                crack_slips=la(slip_l),crack_sigma_n=la(sn_l),crack_vci=la(vci_l))


# ── 2D Panel runner ──────────────────────────────────────────────────────────
def run_model_2d(p):
    """Run a 2D plane-stress panel model with triangular mesh and crack interfaces."""
    import openseespy.opensees as ops
    disp_l=[]; force_l=[]; open_l=[]; slip_l=[]; sn_l=[]; vci_l=[]; cpos=[]
    status="failed"; msg="failed"; fy=0.
    crack_mat=str(p.get('crack_mat_type','Elastic Springs') or 'Elastic Springs')
    try:
        ops.wipe(); ops.model('basic','-ndm',2,'-ndf',2)
        W=float(p['panel_W']); H=float(p['panel_H']); t=float(p.get('panel_t',0.2))
        Ec=float(p.get('panel_Ec',30000.)); nu=float(p.get('panel_nu',0.2))
        fc=float(p.get('fc',30.)); ag=float(p.get('ag',16.)); w0=float(p.get('w0',0.1))
        Es=float(p['Es']); fsy=float(p['fsy'])

        # Concrete NDMaterial (ElasticIsotropic for plane stress)
        ops.nDMaterial('ElasticIsotropic', 1, Ec, nu)

        # Build nodes from serialised mesh
        mesh_nodes = p['mesh_nodes']
        for nid_str, (x, y) in mesh_nodes.items():
            ops.node(int(nid_str), float(x), float(y))

        # Fix bottom edge (y==0)
        for nid_str, (x, y) in mesh_nodes.items():
            if abs(y) < 1e-8:
                ops.fix(int(nid_str), 1, 1)

        # Triangular elements (tri31 plane stress)
        mesh_tris = p['mesh_tris']
        for e, n1, n2, n3 in mesh_tris:
            try:
                ops.element('tri31', int(e), int(n1), int(n2), int(n3), t, 'PlaneStress', 1)
            except:
                ops.element('Tri31', int(e), int(n1), int(n2), int(n3), t, 'PlaneStress', 1)

        # Crack interface elements
        crack_pairs = p.get('mesh_crack_pairs', [])
        epp_mode = 'eppgap' in crack_mat.lower()
        kn_d = Dnw(w0); kt_d = Dts(w0, fc)
        pp={k:float(p.get(k,v)) for k,v in
            [('rho_hat',.3),('rho_act',1.),('mu_act',.2),('zeta',.5),('chi',.18),('kappa',.75)]}

        elt = len(mesh_tris) + 1
        states = []; cnodes = []
        # Group crack pairs by Y for tracking
        crack_y_set = sorted(set(round(cp[2],6) for cp in crack_pairs))
        cpos = crack_y_set

        for ci, (nb, na, yc, xc) in enumerate(crack_pairs):
            nb=int(nb); na=int(na)
            mat_base = 5000 + ci * 2
            if epp_mode:
                # EPPGap macro: 4 springs (shear-x fwd, shear-x rev, normal-y open, normal-y close)
                efy = float(p.get('epp_fy', 0.5))
                egap = float(p.get('epp_gap', 0.01))
                eeta = float(p.get('epp_eta', 0.02))
                kt_v = max(kt_d * t, 1e-3)
                kn_v = max(kn_d * t, 1e-3)
                ops.uniaxialMaterial('ElasticPPGap', mat_base,   kt_v, efy, egap, eeta)
                ops.uniaxialMaterial('ElasticPPGap', mat_base+1, kn_v, efy*2, 0.0, eeta)
                elt+=1
                ops.element('zeroLength', elt, nb, na,
                    '-mat', mat_base, mat_base+1, '-dir', 1, 2)
            else:
                # Elastic springs (kn/kt)
                kn_v = max(kn_d * t, 1e-3)
                kt_v = max(kt_d * t, 1e-3)
                ops.uniaxialMaterial('Elastic', mat_base,   kt_v)
                ops.uniaxialMaterial('Elastic', mat_base+1, kn_v)
                elt+=1
                ops.element('zeroLength', elt, nb, na,
                    '-mat', mat_base, mat_base+1, '-dir', 1, 2)
            cnodes.append((nb, na, float(yc)))
            states.append(CrackSt(w0, fc, ag, pp))

        # Loading: apply uniform displacement at top edge
        top_nodes = [int(nid_str) for nid_str, (x, y) in mesh_nodes.items()
                     if abs(y - H) < 1e-8]
        if not top_nodes:
            raise RuntimeError("No top-edge nodes found")

        # Total force capacity estimate
        fy = fsy * W * t
        ln = top_nodes[0]  # reference node for displacement
        dof = 2  # Y direction

        ops.timeSeries('Linear', 1)
        ops.pattern('Plain', 1, 1)
        at = p.get('analysis_type', 'DisplacementControl')
        if at == 'LoadControl':
            fper = fy / max(len(top_nodes), 1)
            for tn in top_nodes:
                ops.load(tn, 0., fper)
        else:
            for tn in top_nodes:
                ops.load(tn, 0., 1.0)

        nc = len(crack_y_set)
        # Per crack-line aggregated histories
        open_l = [[] for _ in range(nc)]
        slip_l = [[] for _ in range(nc)]
        sn_l   = [[] for _ in range(nc)]
        vci_l  = [[] for _ in range(nc)]
        pw = [w0] * len(cnodes)
        ps = [0.0] * len(cnodes)

        def collect():
            disp_l.append(ops.nodeDisp(ln, dof))
            ops.reactions()
            tot_f = sum(-ops.nodeReaction(int(nid_str), dof)
                        for nid_str, (x, y) in mesh_nodes.items() if abs(y) < 1e-8)
            force_l.append(tot_f)
            # Per crack-line: average opening/slip across all pairs at that Y
            for yi, yv in enumerate(crack_y_set):
                dw_sum = 0.; ds_sum = 0.; cnt = 0
                for ki, (nb, na, yc) in enumerate(cnodes):
                    if abs(yc - yv) < 1e-6:
                        dw = ops.nodeDisp(na, 2) - ops.nodeDisp(nb, 2)
                        ds = ops.nodeDisp(na, 1) - ops.nodeDisp(nb, 1)
                        snr, vcir = states[ki].step(dw - pw[ki] + w0, ds - ps[ki])
                        pw[ki] = dw; ps[ki] = ds
                        dw_sum += dw; ds_sum += ds; cnt += 1
                if cnt > 0:
                    open_l[yi].append(dw_sum / cnt)
                    slip_l[yi].append(ds_sum / cnt)
                    sn_l[yi].append(0.); vci_l[yi].append(0.)
                else:
                    open_l[yi].append(0.); slip_l[yi].append(0.)
                    sn_l[yi].append(0.); vci_l[yi].append(0.)

        failed = False; fm = ""
        ml = float(p.get('max_load_factor', 50.))
        if at == 'LoadControl':
            incr = float(p.get('load_incr', .01)); steps = max(1, int(1. / incr))
            for st in range(steps):
                ok, cur, _, alg = cutback(ops, p, at, ln, dof, incr)
                if ok == 0: collect(); incr = min(incr, cur)
                else: failed = True; fm = f"step {st} alg={alg}"; break
        else:
            tgt = float(p.get('target_disp', .05))
            incr = float(p.get('disp_incr', .0005))
            steps = max(1, int(abs(tgt) / max(abs(incr), 1e-12)))
            for st in range(steps):
                try:
                    if abs(ops.getTime()) > ml: failed = True; fm = "load factor runaway"; break
                except: pass
                ok, cur, _, alg = cutback(ops, p, at, ln, dof, incr)
                if ok == 0: collect(); incr = min(incr, cur)
                else: failed = True; fm = f"step {st} alg={alg}"; break

        status = ("ok" if not failed else "partial") if disp_l else "failed"
        msg = f"{len(disp_l)} steps | {nc} crack line(s) | 2D panel {W:.2f}x{H:.2f} | {status}"
        if fm: msg += " | " + fm
    except Exception as e:
        tb = traceback.format_exc(); status = "partial" if disp_l else "failed"
        msg = f"Exception: {e}\n{tb}"; print(msg)
    a = lambda x: np.array(x, dtype=float)
    la = lambda x: [a(v) for v in x] if x else []
    return dict(disp=a(disp_l), force=a(force_l), fy=float(fy),
                crack_positions=a(cpos), status=status, message=msg,
                crack_openings=la(open_l), crack_slips=la(slip_l),
                crack_sigma_n=la(sn_l), crack_vci=la(vci_l))


def _dispatch(p):
    """Pick 1D or 2D runner based on component_type."""
    if p.get('component_type','1D') == '2D':
        return run_model_2d(p)
    return run_model(p)

def main():
    argc = len(sys.argv)
    if argc == 1:
        if 'EMBEDDED_PARAMS' not in globals():
            print("Error: EMBEDDED_PARAMS not defined. Run with: python script.py params.json results.npz")
            sys.exit(2)
        p = globals()['EMBEDDED_PARAMS']
        r = _dispatch(p)
        print(r['message'])
        sys.exit(0 if r['status']=='ok' else 1)
    elif argc == 3:
        with open(sys.argv[1]) as f: p=json.load(f)
        r = _dispatch(p)
        np.savez(sys.argv[2],
            disp=r['disp'],force=r['force'],fy=np.array([r['fy']]),
            crack_positions=r['crack_positions'],
            crack_openings=np.array(r['crack_openings'],dtype=object),
            crack_slips=np.array(r['crack_slips'],dtype=object),
            crack_sigma_n=np.array(r['crack_sigma_n'],dtype=object),
            crack_vci=np.array(r['crack_vci'],dtype=object),
            status=np.array([r['status']]),message=np.array([r['message']]))
        print(r['message'])
        sys.exit(0 if r['status']=='ok' else 1)
    else:
        print("Usage:")
        print("  python opensees_crack.py                       # run with embedded params")
        print("  python opensees_crack.py params.json results.npz")
        sys.exit(2)

if __name__=="__main__": main()
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
            pp = self.run_dir / "params.json"
            rp = self.run_dir / "runner.py"
            np_ = self.run_dir / "results.npz"
            pp.write_text(json.dumps(self.params, indent=2), encoding='utf-8')
            rp.write_text(RUNNER_PY, encoding='utf-8')

            pp_w = win_to_wsl(str(pp))
            rp_w = win_to_wsl(str(rp))
            np_w = win_to_wsl(str(np_))

            bash = f"{self.activate} && python3 {rp_w} {pp_w} {np_w}"
            cmd  = ["wsl", "bash", "-lc", bash]
            self.log.emit(f"[CMD] {bash[:120]}")
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.stdout.strip(): self.log.emit(proc.stdout.strip())
            if proc.stderr.strip(): self.log.emit("[STDERR] " + proc.stderr.strip())

            if not np_.exists():
                raise RuntimeError(
                    "results.npz was not created.\n"
                    "Possible causes:\n"
                    "  1. Wrong venv activate command in Run tab\n"
                    "  2. openseespy not installed in that env\n"
                    "  3. WSL path issues\n"
                    "Check console output above.")

            data = np.load(str(np_), allow_pickle=True)
            def arr(k): return np.array(data[k], dtype=float)
            def obj(k): return [np.array(x, dtype=float) for x in list(data[k])]
            result = dict(
                status=str(data["status"][0]), message=str(data["message"][0]),
                fy=float(data["fy"][0]),
                disp=arr("disp"), force=arr("force"),
                crack_positions=arr("crack_positions"),
                crack_openings=obj("crack_openings"), crack_slips=obj("crack_slips"),
                crack_sigma_n=obj("crack_sigma_n"),   crack_vci=obj("crack_vci"),
                returncode=proc.returncode)
            self.finished.emit(result)
        except Exception:
            self.error.emit(traceback.format_exc())


# =============================================================================
# Main Window
# =============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multi-Surface Crack Plasticity  ·  OpenSeesPy")
        self.setMinimumSize(1280, 820)
        self.RUNS_DIR = str(Path.home() / "crack_plasticity_runs")
        self._worker  = None

        root = QWidget(); self.setCentralWidget(root)
        vl   = QVBoxLayout(root); vl.setContentsMargins(0,0,0,0); vl.setSpacing(0)

        # header bar
        hdr = QWidget(); hdr.setStyleSheet(f"background:{BG_PANEL};border-bottom:1px solid {BORDER};")
        hl  = QHBoxLayout(hdr); hl.setContentsMargins(20,10,20,10)
        t1  = QLabel("CRACK PLASTICITY MODEL")
        t1.setStyleSheet(f"color:{C1};font-size:16px;font-weight:bold;letter-spacing:2px;")
        t2  = QLabel("  Multi-Surface Crack Interface  ·  OpenSeesPy")
        t2.setStyleSheet(f"color:{TXTS};font-size:12px;")
        self.lbl_wsl = QLabel("WSL: checking…")
        self.lbl_wsl.setStyleSheet(f"color:{C4};font-size:12px;font-weight:bold;")
        hl.addWidget(t1); hl.addWidget(t2); hl.addStretch(); hl.addWidget(self.lbl_wsl)
        vl.addWidget(hdr)

        # ── Quick-actions toolbar (always visible regardless of active tab) ──
        qa = QWidget()
        qa.setStyleSheet(
            f"background:{BG_CARD};border-bottom:1px solid {BORDER};"
            f"border-top:1px solid {BORDER};")
        qal = QHBoxLayout(qa); qal.setContentsMargins(16,7,16,7); qal.setSpacing(8)

        self.btn_qa_run  = QPushButton("▶  Run Analysis")
        self.btn_qa_run.setMinimumHeight(34)
        self.btn_qa_run.setStyleSheet(
            f"background:{C2};color:{BG_DEEP};font-weight:bold;font-size:13px;"
            f"padding:7px 22px;border-radius:5px;border:none;"
            f"QPushButton:hover{{background:#56d364;}}"
            f"QPushButton:disabled{{background:{BORDER};color:{TXTS};}}")
        self.btn_qa_run.setToolTip(
            "Run the OpenSeesPy analysis in WSL.\n"
            "Draw at least one crack on the Geometry tab first.")

        self.btn_qa_gen  = QPushButton("📋  Generate Script")
        self.btn_qa_gen.setMinimumHeight(34)
        self.btn_qa_gen.setStyleSheet(
            f"background:{C4};color:{BG_DEEP};font-weight:bold;font-size:12px;"
            f"padding:7px 18px;border-radius:5px;border:none;")
        self.btn_qa_gen.setToolTip(
            "Generate a self-contained OpenSeesPy Python script from current parameters.\n"
            "The script appears on the Script tab and can be saved / copied.")

        self.btn_qa_png  = QPushButton("💾  Save PNG")
        self.btn_qa_png.setObjectName("flat")
        self.btn_qa_png.setToolTip("Save the current plot as PNG/PDF.")
        self.btn_qa_png.setEnabled(False)

        self.btn_qa_csv  = QPushButton("📊  Export CSV")
        self.btn_qa_csv.setObjectName("flat")
        self.btn_qa_csv.setToolTip("Export all result data as CSV.")
        self.btn_qa_csv.setEnabled(False)

        sep_lbl = QLabel("|")
        sep_lbl.setStyleSheet(f"color:{BORDER};")

        self.lbl_workflow = QLabel(
            "  Step 1: Draw cracks on ① Geometry  →  Step 2: ② Material  →  "
            "Step 3: ③ Analysis  →  Step 4: Click ▶ Run Analysis")
        self.lbl_workflow.setStyleSheet(f"color:{TXTS};font-size:10px;")

        for w in [self.btn_qa_run, self.btn_qa_gen,
                  self.btn_qa_png, self.btn_qa_csv,
                  sep_lbl, self.lbl_workflow]:
            qal.addWidget(w)
        qal.addStretch()
        vl.addWidget(qa)

        # tabs
        body = QWidget(); body.setStyleSheet(f"background:{BG_DEEP};")
        bl   = QVBoxLayout(body); bl.setContentsMargins(12,12,12,12)
        self.tabs = QTabWidget()
        self.geo  = GeometryTab()
        self.drw  = DrawCracksTab()
        self.mat  = MaterialTab()
        self.anl  = AnalysisTab()
        self.run  = RunTab()
        self.res  = ResultsTab()
        self.yld  = YieldTab()
        self.scr  = ScriptTab()
        for name, tab in [
            ("① Geometry",           self.geo),
            ("✏ Draw Cracks",        self.drw),
            ("② Material+Plasticity",self.mat),
            ("③ Analysis",           self.anl),
            ("④ Run",                self.run),
            ("⑤ Results",            self.res),
            ("⑥ Yield Surfaces",     self.yld),
            ("⑦ Script",             self.scr),
        ]:
            self.tabs.addTab(tab, name)
        bl.addWidget(self.tabs); vl.addWidget(body, stretch=1)

        self.statusBar().showMessage("Ready — draw cracks on Geometry tab, then Run.")
        self.statusBar().setStyleSheet(
            f"background:{BG_PANEL};color:{TXTS};border-top:1px solid {BORDER};")

        # wire signals
        self.run.run_requested.connect(self.start_analysis)
        self.scr.btn_gen.clicked.connect(self.generate_script)
        # quick-actions toolbar wiring
        self.btn_qa_run.clicked.connect(self.start_analysis)
        self.btn_qa_gen.clicked.connect(self.generate_script)
        self.btn_qa_png.clicked.connect(lambda: self.res._save())
        self.btn_qa_csv.clicked.connect(lambda: self.res._csv())
        # Keep Draw Cracks tab in sync with Geometry tab bar parameters
        for sb in [self.geo.sb_L, self.geo.sb_fc, self.geo.sb_ag, self.geo.sb_w0]:
            sb.valueChanged.connect(self._sync_draw_params)
        QTimer.singleShot(800, self.check_wsl)

    def _sync_draw_params(self):
        self.drw.sync_from_geometry(
            self.geo.sb_L.value(), self.geo.sb_fc.value(),
            self.geo.sb_ag.value(), self.geo.sb_w0.value())

    def _params(self):
        p = {}
        for tab in [self.geo, self.mat, self.anl]: p.update(tab.get_params())
        # Merge freehand-drawn cracks from the Draw Cracks tab
        drawn = self.drw.get_crack_data()
        if drawn:
            combined = p.get('crack_data', []) + drawn
            combined.sort(key=lambda c: c['y'])
            deduped = []
            for c in combined:
                if not deduped or abs(c['y'] - deduped[-1]['y']) > 0.01:
                    deduped.append(c)
            p['crack_data'] = deduped
        return p

    def check_wsl(self):
        act = self.run.get_activate()
        cmd = ["wsl","bash","-lc",
               f"{act} && python3 -c \"import openseespy.opensees; print('OK')\""]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
            ok = "OK" in proc.stdout
            self.lbl_wsl.setText(f"WSL: {'✓ OK' if ok else '✗ NOT READY'}")
            self.lbl_wsl.setStyleSheet(
                f"color:{C2 if ok else C3};font-size:12px;font-weight:bold;")
            self.run.append("✓ WSL OpenSeesPy ready." if ok else
                            "✗ WSL check failed. Fix 'Activate command' in Run tab.")
            if not ok and proc.stderr.strip():
                self.run.append(proc.stderr.strip()[:500])
        except Exception as e:
            self.lbl_wsl.setText("WSL: ✗ ERROR")
            self.lbl_wsl.setStyleSheet(f"color:{C3};font-size:11px;font-weight:bold;")
            self.run.append(f"WSL error: {e}")

    def start_analysis(self):
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Busy", "Analysis already running."); return

        errs = self.geo.validate()
        # Freehand strokes on the Draw Cracks tab are also valid crack inputs
        if errs and self.drw.get_crack_data():
            errs = [e for e in errs if 'crack interface' not in e.lower()]
        if errs:
            # Navigate to Geometry tab and show inline hint instead of blocking popup
            self.tabs.setCurrentWidget(self.geo)
            self.lbl_workflow.setText(
                "  ⚠  " + "   |   ".join(errs) + "  — draw cracks on the bar diagram →")
            self.lbl_workflow.setStyleSheet(f"color:{C3};font-size:11px;font-weight:bold;")
            return

        p   = self._params()
        ts  = time.strftime("%Y%m%d_%H%M%S")
        rd  = Path(self.RUNS_DIR) / f"run_{ts}"
        act = self.run.get_activate()

        is_2d = p.get('component_type') == '2D'
        self.run.append(f"\n{'━'*60}")
        self.run.append(f"Run folder : {rd}")
        self.run.append(f"Mode       : {'2D Panel' if is_2d else '1D Bar'}")
        if is_2d:
            nt = len(p.get('mesh_tris', []))
            nn = len(p.get('mesh_nodes', {}))
            nc = len(p.get('mesh_crack_pairs', []))
            self.run.append(f"Mesh       : {nn} nodes, {nt} tri, {nc} crack links")
        else:
            self.run.append(f"Cracks     : {len(p.get('crack_data',[]))}")
        self.run.append(f"Analysis   : {p.get('analysis_type')} | target={p.get('target_disp')}")
        self.run.set_status("Running in WSL…")
        self.run.btn_run.setEnabled(False)
        self.btn_qa_run.setEnabled(False)
        self.btn_qa_run.setText("⏳  Running…")
        self.lbl_workflow.setStyleSheet(f"color:{C4};font-size:11px;")
        self.lbl_workflow.setText("  Analysis running in WSL…  check ④ Run tab console for progress.")
        self.statusBar().showMessage("Analysis running…")

        self._worker = WSLWorker(p, str(rd), act)
        self._worker.log.connect(self.run.append)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_err)
        self._worker.start()

    def _on_done(self, result):
        self.run.btn_run.setEnabled(True)
        self.btn_qa_run.setEnabled(True)
        self.btn_qa_run.setText("▶  Run Analysis")
        ok  = result["status"] == "ok"
        msg = result["message"]
        self.run.set_status(f"{'✓' if ok else '⚠'} {msg}", ok=ok)
        self.run.append(f"\n{'SUCCESS' if ok else 'PARTIAL/FAILED'}: {msg}")
        if result["disp"].size > 0:
            self.res.set_results(result)
            self.btn_qa_png.setEnabled(True)
            self.btn_qa_csv.setEnabled(True)
            self.tabs.setCurrentWidget(self.res)
            # Auto-generate the script so ⑦ Script tab is always ready
            self.generate_script()
            self.lbl_workflow.setText(
                f"  Done: {msg}  |  View ⑤ Results  or  ⑦ Script  |  "
                "Use toolbar buttons to Save PNG / Export CSV")
        else:
            self.lbl_workflow.setText(
                f"  Analysis incomplete: {msg}  |  Check ④ Run tab console for errors.")
        self.statusBar().showMessage(
            f"{result['status'].upper()}  |  {len(result['disp'])} steps converged")

    def _on_err(self, tb):
        self.run.btn_run.setEnabled(True)
        self.btn_qa_run.setEnabled(True)
        self.btn_qa_run.setText("▶  Run Analysis")
        self.run.set_status("✗ Python/WSL error (see console)", ok=False)
        self.run.append("\nERROR:\n" + tb)
        self.lbl_workflow.setText(
            "  Error in WSL — see ④ Run tab console. Check activate command & openseespy install.")
        self.statusBar().showMessage("Error — see console.")

    def generate_script(self):
        p = self._params()
        comp = p.get('component_type', '1D')
        n_cracks = len(p.get('crack_data', []))
        mat_type = p.get('crack_mat_type', 'Elastic Springs (kn/kt)')
        # Produce valid Python literals (json.dumps uses lowercase true/false/null)
        import json as _json
        py_params = _json.dumps(p, indent=2) \
            .replace(': true',  ': True') \
            .replace(': false', ': False') \
            .replace(': null',  ': None')
        mode_info = "1D Bar" if comp == "1D" else f"2D Panel {p.get('panel_W','?')}x{p.get('panel_H','?')}"
        if comp == "2D":
            nt = len(p.get('mesh_tris', []))
            nc = len(p.get('mesh_crack_pairs', []))
            mode_info += f"  tri={nt}  crack_links={nc}"
        hdr = (
            f'#!/usr/bin/env python3\n'
            f'"""\n'
            f'Multi-Surface Crack Plasticity  —  Standalone OpenSeesPy Script\n'
            f'Generated : {time.strftime("%Y-%m-%d %H:%M:%S")}\n'
            f'Mode      : {mode_info}\n'
            f'Cracks    : {n_cracks}\n'
            f'Material  : {mat_type}\n'
            f'\n'
            f'Usage:\n'
            f'  python opensees_crack.py                       # runs with EMBEDDED_PARAMS\n'
            f'  python opensees_crack.py p.json results.npz   # loads params file, saves npz\n'
            f'"""\n'
            f'import json, sys\n'
            f'\n'
            f'# ── Embedded parameters — edit these values freely ──────────────\n'
            f'EMBEDDED_PARAMS = {py_params}\n'
            f'\n'
            f'# ── Runner code (do not edit below this line) ───────────────────\n'
        )
        self.scr.set_script(hdr + RUNNER_PY.strip())
        self.tabs.setCurrentWidget(self.scr)
        self.lbl_workflow.setText(
            f"  Script generated ({mode_info}, {mat_type}).  "
            "Use  Save .py  or  Copy  buttons on the Script tab.")


def main():
    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setStyleSheet(STYLE)
        w = MainWindow()
        w.show()
        sys.exit(app.exec_())
    except Exception as e:
        import traceback as _tb
        tb_str = _tb.format_exc()
        try:
            app2 = QApplication.instance() or QApplication(sys.argv)
            from PyQt5.QtWidgets import QMessageBox
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