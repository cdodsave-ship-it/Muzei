import sys
import os

# ФИКС ДЛЯ PANDA3D В EXE - настройки графики прямо в коде
from panda3d.core import loadPrcFileData
if getattr(sys, 'frozen', False):
    # Работаем в exe
    base_dir = os.path.dirname(sys.executable)
    dll_dir = os.path.join(base_dir, 'panda3d')
    if os.path.exists(dll_dir):
        os.environ['PATH'] = dll_dir + ';' + os.environ.get('PATH', '')
        os.environ['PANDA3D_LIB_DIR'] = dll_dir
# Эти строки заменяют Config.prc и говорят Panda3D, какую графику использовать
loadPrcFileData('', 'load-display pandagl')   # OpenGL
loadPrcFileData('', 'aux-display pandadx9')   # DirectX 9
loadPrcFileData('', 'aux-display pandadx11')  # DirectX 11
loadPrcFileData('', 'window-type none')       # Разрешаем безоконный режим

# Остальные импорты
import re
import traceback
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QListWidget, QListWidgetItem, QLabel, QPushButton, QFrame, QCheckBox,
    QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QFont

from panda3d.core import WindowProperties, Filename, Vec2
from direct.showbase.ShowBase import ShowBase


# =========================
# ENGINE
# =========================
class Engine(ShowBase):
    def __init__(self):
        super().__init__(windowType='none')
        self.disableMouse()
        self.model = None

        self.exitFunc = None
        self.accept('window-event', self._on_window_event)

        self.h = 0
        self.p = 90
        self.r = 0

        self.dragging = False
        self.last_mouse = None

        self.inertia_h = 0
        self.inertia_p = 0
        self.inertia_strength = 0.92

        self.mouse_enabled = True

        self.zoom    = -7
        self.zoom_min = -20
        self.zoom_max = -1

        self.pan_x = 0.0
        self.pan_z = 0.0

    def _on_window_event(self, window):
        pass

    def attach(self, win_id):
        props = WindowProperties()
        props.setParentWindow(int(win_id))
        props.setOrigin(0, 0)
        props.setSize(1000, 800)
        self.openDefaultWindow(props=props)
        self._apply_camera()

    def resize_window(self, w, h):
        if self.win:
            props = WindowProperties()
            props.setOrigin(0, 0)
            props.setSize(w, h)
            self.win.requestProperties(props)

    def _apply_camera(self):
        self.camera.setPos(self.pan_x, self.zoom, self.pan_z)
        self.camera.lookAt(self.pan_x, 0, self.pan_z)

    def load_model(self, path):
        if self.model:
            self.model.removeNode()

        m = self.loader.loadModel(Filename.fromOsSpecific(str(path)))
        if m.isEmpty():
            print("LOAD ERROR:", path)
            return

        m.reparentTo(self.render)

        bounds = m.getTightBounds()
        if bounds:
            mn, mx = bounds
            center = (mn + mx) * 0.5
            m.setPos(-center)
            size = (mx - mn).length()
            m.setScale(2.5 / max(size, 1))

        m.setH(self.h)
        m.setP(self.p)
        m.setR(self.r)
        self.model = m

    def do_zoom(self, delta):
        self.zoom += delta
        self.zoom = max(self.zoom_min, min(self.zoom_max, self.zoom))
        self._apply_camera()

    def do_pan(self, dx, dz):
        self.pan_x += dx
        self.pan_z += dz
        self._apply_camera()

    def reset_pan(self):
        self.pan_x = 0.0
        self.pan_z = 0.0
        self._apply_camera()

    def reset_zoom(self):
        self.zoom = -7
        self._apply_camera()

    def mouse_down(self):
        self.dragging = True
        self.last_mouse = None

    def mouse_up(self):
        self.dragging = False
        self.last_mouse = None

    def update_mouse(self):
        if not self.mouse_enabled:
            return

        if self.dragging and self.mouseWatcherNode.hasMouse():
            m = self.mouseWatcherNode.getMouse()
            if self.last_mouse is None:
                self.last_mouse = Vec2(m)
                return
            delta = m - self.last_mouse
            self.last_mouse = Vec2(m)
            self.inertia_h = delta.x * 140
            self.inertia_p = delta.y * 140
            self.h += self.inertia_h
            self.p -= self.inertia_p
        else:
            self.inertia_h *= self.inertia_strength
            self.inertia_p *= self.inertia_strength
            self.h += self.inertia_h
            self.p -= self.inertia_p

        self.p = max(10, min(170, self.p))
        if self.model:
            self.model.setH(self.h)
            self.model.setP(self.p)

    def auto_rotate(self, speed=0.5):
        self.h += speed
        if self.model:
            self.model.setH(self.h)


# =========================
# DESCRIPTION DIALOG
# =========================
class DescriptionDialog(QWidget):
    """Плавающее окно с описанием экспоната. Подстраивается под размер текста."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Tool | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_pos = None

        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Контейнер с фоном
        self.card = QFrame()
        self.card.setObjectName("desc_card")
        self.card.setStyleSheet("""
            QFrame#desc_card {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0f1e35, stop:1 #0a1422);
                border: 1px solid #2a4a70;
                border-radius: 12px;
            }
        """)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(16, 14, 16, 16)
        card_layout.setSpacing(10)

        # ── Заголовок + кнопка закрыть ──────────
        header = QHBoxLayout()
        header.setSpacing(8)

        icon_lbl = QLabel("📋")
        icon_lbl.setStyleSheet("font-size: 16px;")

        self.title_lbl = QLabel("Описание")
        self.title_lbl.setStyleSheet("""
            color: #7ab3ff;
            font-size: 14px;
            font-weight: bold;
            letter-spacing: 0.5px;
        """)

        header.addWidget(icon_lbl)
        header.addWidget(self.title_lbl)
        header.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(26, 26)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #2a3558;
                color: #aabbcc;
                border-radius: 6px;
                font-size: 12px;
                border: none;
            }
            QPushButton:hover {
                background: #c0392b;
                color: white;
            }
        """)
        btn_close.clicked.connect(self.hide)
        header.addWidget(btn_close)

        card_layout.addLayout(header)

        # ── Разделитель ─────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #1e3550; background: #1e3550; max-height: 1px;")
        card_layout.addWidget(sep)

        # ── Текст (с прокруткой если очень длинный) ──
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #0d1b2a; width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #2a4a70; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self.text_lbl = QLabel()
        self.text_lbl.setObjectName("desc_text")
        self.text_lbl.setWordWrap(True)
        self.text_lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.text_lbl.setStyleSheet("""
            QLabel#desc_text {
                color: #ccd9ee;
                font-size: 13px;
                line-height: 1.6;
                background: transparent;
                padding: 4px 2px;
            }
        """)
        self.text_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        inner_widget = QWidget()
        inner_widget.setStyleSheet("background: transparent;")
        inner_layout = QVBoxLayout(inner_widget)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.addWidget(self.text_lbl)

        self.scroll.setWidget(inner_widget)
        card_layout.addWidget(self.scroll)

        # ── Подсказка перетаскивания ─────────────
        hint = QLabel("· · ·  перетащите окно")
        hint.setStyleSheet("color: #2a4a70; font-size: 10px;")
        hint.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(hint)

        outer.addWidget(self.card)

    # ── Обновление содержимого ───────────────────
    def set_content(self, title, text):
        self.title_lbl.setText(title)
        if text:
            self.text_lbl.setText(text)
        else:
            self.text_lbl.setText(
                "<i style='color:#3a5070'>Описание для этого экспоната не найдено.<br>"
                "Создайте файл <b>text/{name}.txt</b> рядом с программой.</i>".format(name=title)
            )
        self._adjust_size()

    def _adjust_size(self):
        """Подстраивает высоту окна под длину текста (макс 500px)."""
        self.text_lbl.adjustSize()
        text_h = self.text_lbl.sizeHint().height()
        scroll_h = min(text_h + 10, 450)
        self.scroll.setFixedHeight(scroll_h)
        self.setFixedWidth(380)
        self.adjustSize()

    # ── Перетаскивание окна ──────────────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


# =========================
# VIEW WIDGET
# =========================
class ViewWidget(QWidget):
    def __init__(self, on_wheel, on_resize=None, parent=None):
        super().__init__(parent)
        self.on_wheel = on_wheel
        self.on_resize = on_resize
        self.setFocusPolicy(Qt.WheelFocus)

    def wheelEvent(self, event):
        self.on_wheel(event.angleDelta().y() / 120 * 0.5)
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.on_resize:
            self.on_resize(event.size().width(), event.size().height())


# =========================
# PATHS
# =========================
def get_models_path():
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return Path(os.path.join(base_path, "models"))


def get_text_path():
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return Path(os.path.join(base_path, "text"))


def load_description(name: str) -> str | None:
    """Загружает текст описания для экспоната по его имени."""
    txt_dir = get_text_path()
    txt_file = txt_dir / f"{name}.txt"
    if txt_file.exists():
        try:
            return txt_file.read_text(encoding="utf-8").strip()
        except Exception as e:
            print(f"Ошибка чтения {txt_file}: {e}")
    return None


# =========================
# UI
# =========================
class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Museum Viewer PRO")
        self.resize(1500, 850)

        self.dir = get_models_path()
        self.data = []
        self.i = 0
        self.engine = Engine()

        # ── слайдшоу ──────────────────────────────
        self.slideshow_active  = False
        self.slideshow_elapsed = 0
        self.SLIDESHOW_DURATION = 10000  # 10 секунд

        # ── окно описания ─────────────────────────
        self.desc_dialog = DescriptionDialog(self)
        self.desc_dialog.hide()

        self.ui()
        self.load_models()
        QTimer.singleShot(100, self.init_engine)

    # ── styles ────────────────────────────────────
    def ui(self):
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #050814, stop:0.5 #0d1b2a, stop:1 #1b263b);
            }
            QListWidget {
                background-color: rgba(20,25,40,200);
                color: white; border-radius: 10px; padding: 10px;
            }
            QPushButton {
                background-color: #2a3558;
                color: white; border-radius: 8px; padding: 6px;
            }
            QPushButton:hover { background-color: #3b4a7a; }
            QPushButton#pan_btn {
                background-color: #1e2a45;
                font-size: 18px; border-radius: 10px;
                min-width: 44px; min-height: 44px;
                max-width: 44px; max-height: 44px;
            }
            QPushButton#pan_btn:hover { background-color: #2e3f6a; }
            QPushButton#pan_center {
                background-color: #12213a;
                color: #4a6fa5; font-size: 14px; border-radius: 10px;
                min-width: 44px; min-height: 44px;
                max-width: 44px; max-height: 44px;
            }
            QPushButton#pan_center:hover { background-color: #1e2e50; }
            QPushButton#slideshow_btn {
                background-color: #1a4a2e;
                color: #7fffb0; border-radius: 8px;
                padding: 6px 14px; font-weight: bold;
            }
            QPushButton#slideshow_btn:hover { background-color: #276040; }
            QPushButton#slideshow_btn[active="true"] {
                background-color: #4a1a1a;
                color: #ffaaaa;
            }
            QPushButton#slideshow_btn[active="true"]:hover { background-color: #602020; }
            QPushButton#desc_btn {
                background-color: #1a3348;
                color: #88ccff;
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #2a5070;
                text-align: left;
            }
            QPushButton#desc_btn:hover {
                background-color: #224060;
                color: #aaddff;
            }
            QPushButton#desc_btn[open="true"] {
                background-color: #0f2a40;
                color: #55aaee;
                border: 1px solid #3a7ab0;
            }
            QLabel { color: white; }
            QCheckBox { color: white; }
        """)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)

        # ── LEFT PANEL ────────────────────────────
        left = QFrame()
        left.setFixedWidth(300)
        lv = QVBoxLayout(left)
        lv.setSpacing(8)

        self.listw = QListWidget()
        self.listw.itemClicked.connect(self.click)
        lv.addWidget(self.listw)

        # ── Кнопка "Описание" ─────────────────────
        self.btn_desc = QPushButton("📋  Описание экспоната")
        self.btn_desc.setObjectName("desc_btn")
        self.btn_desc.setProperty("open", "false")
        self.btn_desc.setCursor(Qt.PointingHandCursor)
        self.btn_desc.clicked.connect(self.toggle_description)
        lv.addWidget(self.btn_desc)

        self.label = QLabel()
        self.label.setStyleSheet(
            "color: #4a7aaa; font-size: 11px; padding: 2px 4px;"
        )
        lv.addWidget(self.label)

        layout.addWidget(left)

        # ── RIGHT COLUMN ──────────────────────────
        right = QVBoxLayout()

        top_bar = QHBoxLayout()

        self.mode = QCheckBox("🎮 Режим мыши")
        self.mode.setChecked(True)
        self.mode.stateChanged.connect(self.toggle_mode)
        top_bar.addWidget(self.mode)

        top_bar.addStretch()

        self.lbl_timer = QLabel("")
        self.lbl_timer.setStyleSheet("color: #7fffb0; font-size: 12px; padding-right: 8px;")
        top_bar.addWidget(self.lbl_timer)

        self.btn_slideshow = QPushButton("▶  Авто-показ")
        self.btn_slideshow.setObjectName("slideshow_btn")
        self.btn_slideshow.clicked.connect(self.toggle_slideshow)
        top_bar.addWidget(self.btn_slideshow)

        right.addLayout(top_bar)

        nav = QHBoxLayout()
        btn_prev = QPushButton("⬅ Предыдущий экспонат")
        btn_next = QPushButton("Следующий экспонат ➡")
        btn_prev.clicked.connect(lambda: self.change(-1))
        btn_next.clicked.connect(lambda: self.change(1))
        nav.addWidget(btn_prev)
        nav.addWidget(btn_next)
        right.addLayout(nav)

        zoom_bar = QHBoxLayout()
        btn_zi = QPushButton("＋  Приблизить")
        btn_zo = QPushButton("－  Отдалить")
        btn_zr = QPushButton("↺  Сброс зума")
        btn_zi.clicked.connect(lambda: self.do_zoom(0.5))
        btn_zo.clicked.connect(lambda: self.do_zoom(-0.5))
        btn_zr.clicked.connect(self.engine.reset_zoom)
        zoom_bar.addWidget(btn_zi)
        zoom_bar.addWidget(btn_zo)
        zoom_bar.addWidget(btn_zr)
        right.addLayout(zoom_bar)

        view_row = QHBoxLayout()

        self.view = ViewWidget(on_wheel=self.do_zoom, on_resize=self.engine.resize_window)
        view_row.addWidget(self.view, 1)
        view_row.addWidget(self._make_pan_panel())

        right.addLayout(view_row, 1)
        layout.addLayout(right)

    # ── pan panel ─────────────────────────────────
    def _make_pan_panel(self):
        PAD = 0.25

        panel = QFrame()
        panel.setFixedWidth(130)
        panel.setStyleSheet("background: rgba(10,15,30,180); border-radius: 14px;")

        grid = QGridLayout(panel)
        grid.setSpacing(6)
        grid.setContentsMargins(16, 16, 16, 16)

        def btn(label, dx, dz, tip=""):
            b = QPushButton(label)
            b.setObjectName("pan_btn")
            b.setToolTip(tip)
            b.clicked.connect(lambda: self.engine.do_pan(dx, dz))
            return b

        center = QPushButton("⊙")
        center.setObjectName("pan_center")
        center.setToolTip("Сброс позиции")
        center.clicked.connect(self.engine.reset_pan)

        lbl = QLabel("Позиция")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: #4a6fa5; font-size: 11px;")

        grid.addWidget(lbl,                              0, 0, 1, 3)
        grid.addWidget(btn("↑", 0,   PAD, "Вверх"),     1, 1)
        grid.addWidget(btn("←", -PAD, 0,  "Влево"),     2, 0)
        grid.addWidget(center,                           2, 1)
        grid.addWidget(btn("→",  PAD, 0,  "Вправо"),    2, 2)
        grid.addWidget(btn("↓", 0,  -PAD, "Вниз"),      3, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #2a3558;")
        grid.addWidget(sep, 4, 0, 1, 3)

        diag_lbl = QLabel("Диагональ")
        diag_lbl.setAlignment(Qt.AlignCenter)
        diag_lbl.setStyleSheet("color: #4a6fa5; font-size: 11px;")
        grid.addWidget(diag_lbl,                                5, 0, 1, 3)
        grid.addWidget(btn("↖", -PAD,  PAD, "Лево-вверх"),    6, 0)
        grid.addWidget(btn("↗",  PAD,  PAD, "Право-вверх"),   6, 2)
        grid.addWidget(btn("↙", -PAD, -PAD, "Лево-вниз"),     7, 0)
        grid.addWidget(btn("↘",  PAD, -PAD, "Право-вниз"),    7, 2)

        return panel

    # ── zoom ──────────────────────────────────────
    def do_zoom(self, delta):
        self.engine.do_zoom(delta)

    # ── mode ──────────────────────────────────────
    def toggle_mode(self):
        self.engine.mouse_enabled = self.mode.isChecked()
        self.engine.dragging = False
        self.engine.last_mouse = None

    # ── description ───────────────────────────────
    def toggle_description(self):
        if self.desc_dialog.isVisible():
            self.desc_dialog.hide()
            self._set_desc_btn_state(False)
        else:
            self._open_description()

    def _open_description(self):
        """Открывает/обновляет окно описания для текущего экспоната."""
        if not self.data:
            return
        _, name, _ = self.data[self.i]
        text = load_description(name)
        self.desc_dialog.set_content(name, text)

        # Позиционируем рядом с кнопкой "Описание" если диалог ещё не двигали
        if not self.desc_dialog.isVisible():
            btn_pos = self.btn_desc.mapToGlobal(QPoint(0, 0))
            dlg_x = btn_pos.x() + self.btn_desc.width() + 10
            dlg_y = btn_pos.y()
            # Не выходим за правый край экрана
            screen = QApplication.primaryScreen().availableGeometry()
            if dlg_x + 390 > screen.right():
                dlg_x = btn_pos.x() - 390
            self.desc_dialog.move(dlg_x, dlg_y)

        self.desc_dialog.show()
        self.desc_dialog.raise_()
        self._set_desc_btn_state(True)

    def _set_desc_btn_state(self, is_open: bool):
        self.btn_desc.setProperty("open", "true" if is_open else "false")
        self.style().unpolish(self.btn_desc)
        self.style().polish(self.btn_desc)

    # ── slideshow ─────────────────────────────────
    def toggle_slideshow(self):
        self.slideshow_active = not self.slideshow_active
        self.slideshow_elapsed = 0

        if self.slideshow_active:
            self.btn_slideshow.setText("⏹  Остановить")
            self.btn_slideshow.setProperty("active", "true")
            # При старте авто-показа сразу открываем описание текущего
            self._open_description()
        else:
            self.btn_slideshow.setText("▶  Авто-показ")
            self.btn_slideshow.setProperty("active", "false")
            self.lbl_timer.setText("")

        self.btn_slideshow.style().unpolish(self.btn_slideshow)
        self.btn_slideshow.style().polish(self.btn_slideshow)

    def slideshow_tick(self):
        self.engine.auto_rotate(speed=0.5)

        self.slideshow_elapsed += 16
        remaining = max(0, (self.SLIDESHOW_DURATION - self.slideshow_elapsed) // 1000)
        self.lbl_timer.setText(f"⏱ {remaining} сек.")

        if self.slideshow_elapsed >= self.SLIDESHOW_DURATION:
            self.slideshow_elapsed = 0
            next_i = (self.i + 1) % len(self.data)
            self.show_model(next_i)
            # Автоматически показываем описание следующего экспоната
            self._open_description()

    # ── init engine ───────────────────────────────
    def init_engine(self):
        self.engine.attach(self.view.winId())
        self.engine.accept("mouse1",    self.engine.mouse_down)
        self.engine.accept("mouse1-up", self.engine.mouse_up)

        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)

        if self.data:
            self.show_model(0)

    def tick(self):
        self.engine.taskMgr.step()
        if self.slideshow_active and self.data:
            self.slideshow_tick()
        else:
            self.engine.update_mouse()

    # ── models ────────────────────────────────────
    def load_models(self):
        self.dir.mkdir(exist_ok=True)
        self.data.clear()
        self.listw.clear()

        for f in self.dir.glob("*.glb"):
            m = re.match(r"(\d+)[_. ]*(.+)", f.stem)
            if m:
                self.data.append((int(m.group(1)), m.group(2), f))
            else:
                self.data.append((9999, f.stem, f))

        self.data.sort()
        for _, n, _ in self.data:
            self.listw.addItem(QListWidgetItem(n))

    def show_model(self, i):
        self.i = i
        _, name, path = self.data[i]
        self.label.setText(name)
        self.engine.load_model(path)
        self.listw.setCurrentRow(i)
        self.engine.resize_window(self.view.width(), self.view.height())

        # Если описание открыто — обновляем его под новый экспонат
        if self.desc_dialog.isVisible():
            text = load_description(name)
            self.desc_dialog.set_content(name, text)

    def click(self, item):
        if self.slideshow_active:
            self.toggle_slideshow()
        self.show_model(self.listw.row(item))

    def change(self, step):
        if self.slideshow_active:
            self.toggle_slideshow()
        self.i = max(0, min(len(self.data) - 1, self.i + step))
        self.show_model(self.i)

    def closeEvent(self, event):
        self.desc_dialog.close()
        super().closeEvent(event)


# =========================
# RUN
# =========================
if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        w = Window()
        w.show()
        sys.exit(app.exec())
    except Exception:
        traceback.print_exc()
        input("Нажмите Enter для выхода...")