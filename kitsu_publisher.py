"""
Kitsu Shot Publisher
A desktop tool for publishing shot previews to Kitsu/Zou.

Requirements:
    pip install PySide6 requests keyring

Run:
    python kitsu_publisher.py
"""

import sys
import os
import json
import threading
import keyring
import requests

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit,
    QFrame, QStackedWidget, QFileDialog, QProgressBar,
    QMessageBox, QSizePolicy, QSpacerItem, QCheckBox
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QObject, QMimeData, QUrl, QSettings,
    QPropertyAnimation, QEasingCurve, QSize
)
from PySide6.QtGui import (
    QFont, QColor, QPalette, QIcon, QPixmap, QPainter, QBrush,
    QPen, QLinearGradient, QDragEnterEvent, QDropEvent, QFontDatabase
)

# ─────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────
APP_NAME    = "Kitsu Publisher"
APP_VERSION = "1.0.0"
KEYRING_SVC = "KitsuPublisher"
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".kitsu_publisher.json")

SUPPORTED_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
    ".png", ".jpg", ".jpeg", ".gif", ".exr", ".tiff", ".tif"
}

# ─────────────────────────────────────────────
#  Stylesheet  (dark industrial / pipeline tool)
# ─────────────────────────────────────────────
STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1a1c22;
    color: #d4d8e2;
    font-family: 'Segoe UI', 'SF Pro Display', 'Helvetica Neue', sans-serif;
    font-size: 13px;
}

/* ── Cards ── */
QFrame#card {
    background-color: #22252e;
    border: 1px solid #2e3240;
    border-radius: 10px;
}

/* ── Section labels ── */
QLabel#section {
    color: #6e7a9a;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}

QLabel#title {
    color: #ffffff;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.5px;
}

QLabel#subtitle {
    color: #5a6480;
    font-size: 12px;
}

QLabel#accent {
    color: #4f8ef7;
    font-size: 12px;
    font-weight: 600;
}

/* ── Inputs ── */
QLineEdit, QComboBox, QTextEdit {
    background-color: #1a1c22;
    border: 1px solid #2e3240;
    border-radius: 6px;
    color: #d4d8e2;
    padding: 8px 12px;
    selection-background-color: #4f8ef7;
}

QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
    border: 1px solid #4f8ef7;
    background-color: #1e2028;
}

QLineEdit::placeholder, QTextEdit::placeholder {
    color: #404660;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #6e7a9a;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #22252e;
    border: 1px solid #2e3240;
    selection-background-color: #2d3550;
    color: #d4d8e2;
    padding: 4px;
}

/* ── Buttons ── */
QPushButton {
    background-color: #2e3240;
    color: #d4d8e2;
    border: 1px solid #3a3f55;
    border-radius: 6px;
    padding: 9px 18px;
    font-weight: 500;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #363b52;
    border-color: #4f8ef7;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #2a2f45;
}

QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #3a6ff7, stop:1 #5a4fcf);
    color: #ffffff;
    border: none;
    font-weight: 600;
    font-size: 14px;
    padding: 11px 28px;
}

QPushButton#primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4a7fff, stop:1 #6a5fdf);
}

QPushButton#primary:disabled {
    background: #2e3240;
    color: #404660;
}

QPushButton#danger {
    background-color: transparent;
    color: #e05a6a;
    border: 1px solid #4a2535;
    font-size: 12px;
    padding: 6px 14px;
}

QPushButton#danger:hover {
    background-color: #2a1520;
    border-color: #e05a6a;
}

QPushButton#link {
    background: transparent;
    border: none;
    color: #4f8ef7;
    font-size: 12px;
    padding: 4px 0;
    text-align: left;
}

QPushButton#link:hover {
    color: #7aabff;
    text-decoration: underline;
}

/* ── Progress ── */
QProgressBar {
    background-color: #1a1c22;
    border: 1px solid #2e3240;
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #3a6ff7, stop:1 #5a4fcf);
    border-radius: 4px;
}

/* ── Scrollbar ── */
QScrollBar:vertical {
    background: #1a1c22;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #2e3240;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

/* ── Status bar ── */
QStatusBar {
    background-color: #14161c;
    color: #5a6480;
    font-size: 11px;
    border-top: 1px solid #1e2028;
}

QCheckBox {
    spacing: 8px;
    color: #9098b4;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #3a3f55;
    background: #1a1c22;
}
QCheckBox::indicator:checked {
    background: #4f8ef7;
    border-color: #4f8ef7;
}
"""

# ─────────────────────────────────────────────
#  Settings helpers
# ─────────────────────────────────────────────

def load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
        return data
    except Exception:
        return {}

def save_settings(data: dict):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[settings saved] {list(data.keys())}")
    except Exception as e:
        print(f"[settings save error] {e}")

# ─────────────────────────────────────────────
#  Kitsu API client (uses gazu — the official Kitsu Python client)
# ─────────────────────────────────────────────

class KitsuClient:
    """Thin wrapper around gazu that matches our existing interface."""

    def __init__(self, server_url: str):
        import gazu
        self.gazu = gazu
        self.base = server_url.rstrip("/")
        gazu.set_host(f"{self.base}/api")

    def login(self, email: str, password: str) -> dict:
        return self.gazu.log_in(email, password)

    # ── Data fetching ──────────────────────────

    def get_projects(self) -> list:
        return self.gazu.project.all_open_projects()

    def get_sequences(self, project_id: str) -> list:
        project = {"id": project_id}
        return self.gazu.shot.all_sequences_for_project(project)

    def get_shots(self, sequence_id: str) -> list:
        sequence = {"id": sequence_id}
        return self.gazu.shot.all_shots_for_sequence(sequence)

    def get_task_types(self) -> list:
        return self.gazu.task.all_task_types()

    def get_shot_tasks(self, shot_id: str) -> list:
        shot = {"id": shot_id}
        return self.gazu.task.all_tasks_for_shot(shot)

    def get_task_statuses(self) -> list:
        return self.gazu.task.all_task_statuses()

    # ── Publishing ─────────────────────────────

    def upload_preview_with_status(self, task_id: str, file_path: str,
                                   comment: str, task_status_id: str) -> dict:
        """Post comment with status change, upload preview, set as main."""
        task        = {"id": task_id, "type": "Task"}
        task_status = {"id": task_status_id} if task_status_id else None

        # If no status selected, get the current task status to keep it unchanged
        if task_status is None:
            task_data   = self.gazu.task.get_task(task_id)
            task_status = {"id": task_data["task_status_id"]}

        # 1. Post comment (changes status)
        comment_obj = self.gazu.task.add_comment(
            task, task_status, comment=comment or ""
        )
        print(f"[comment posted] id={comment_obj.get('id')}")

        # 2. Upload preview file attached to that comment
        # Note: nginx may 504 on large uploads but the file still lands on Kitsu.
        # We treat a JSONDecodeError after upload as a soft success.
        preview_obj = None
        try:
            preview_obj = self.gazu.task.add_preview(
                task, comment_obj, file_path
            )
            print(f"[preview uploaded] id={preview_obj.get('id')} is_movie={preview_obj.get('is_movie')}")
        except Exception as upload_err:
            err_str = str(upload_err)
            # 504 / empty body = nginx timed out but upload likely succeeded
            if "504" in err_str or "JSONDecodeError" in err_str or "Expecting value" in err_str:
                print(f"[preview upload] nginx 504 — file likely received by Kitsu, continuing.")
            else:
                raise  # real error, propagate it

        # 3. Set as main preview if we got a preview object back
        if preview_obj and preview_obj.get("id"):
            try:
                self.gazu.task.set_main_preview(preview_obj)
                print(f"[main preview set]")
            except Exception as e:
                print(f"[set_main_preview] {e} — non-fatal")

        return {"comment": comment_obj, "preview": preview_obj}


# ─────────────────────────────────────────────
#  Worker thread
# ─────────────────────────────────────────────

class PublishWorker(QObject):
    finished = Signal(bool, str)
    progress = Signal(int)

    def __init__(self, client: KitsuClient, task_id: str, file_path: str,
                 comment: str, status_id: str):
        super().__init__()
        self.client    = client
        self.task_id   = task_id
        self.file_path = file_path
        self.comment   = comment
        self.status_id = status_id

    def run(self):
        try:
            self.progress.emit(20)
            self.client.upload_preview_with_status(
                self.task_id, self.file_path,
                self.comment, self.status_id
            )
            self.progress.emit(100)
            self.finished.emit(True, "Published successfully!")
        except Exception as e:
            self.finished.emit(False, str(e))


class FetchWorker(QObject):
    """Generic background fetch — runs in a QThread, emits results via signal."""
    done = Signal(object, str)   # data (any type), error string

    def __init__(self, fn, *args):
        super().__init__()
        self.fn   = fn
        self.args = args

    def run(self):
        try:
            data = self.fn(*self.args)
            self.done.emit(data, "")
        except Exception as e:
            self.done.emit([], str(e))




# ─────────────────────────────────────────────
#  Thread result bridge (safely cross Qt thread boundary)
# ─────────────────────────────────────────────

class ResultBridge(QObject):
    """Lives on the main thread. Worker threads emit into it to safely
    deliver callbacks back to Qt-land."""
    result = Signal(object, object, str)   # callback, data, error

    def __init__(self, parent=None):
        super().__init__(parent)
        self.result.connect(self._dispatch)

    def _dispatch(self, callback, data, err):
        callback(data, err)

# ─────────────────────────────────────────────
#  Drop Zone widget
# ─────────────────────────────────────────────

class DropZone(QFrame):
    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(140)
        self.setObjectName("card")
        self.file_path = None
        self._hovering = False

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        self.icon_lbl = QLabel("⬆", self)
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_lbl.setStyleSheet("color: #3a3f55; background: transparent; font-size: 28px;")

        self.msg_lbl = QLabel("Drag & drop a clip here", self)
        self.msg_lbl.setAlignment(Qt.AlignCenter)
        self.msg_lbl.setStyleSheet("color: #5a6480; background: transparent; font-size: 13px;")

        self.sub_lbl = QLabel("or", self)
        self.sub_lbl.setAlignment(Qt.AlignCenter)
        self.sub_lbl.setStyleSheet("color: #3a3f55; background: transparent; font-size: 11px;")

        self.browse_btn = QPushButton("Browse file…")
        self.browse_btn.setObjectName("link")
        self.browse_btn.setFixedWidth(120)
        self.browse_btn.clicked.connect(self._browse)

        self.file_lbl = QLabel()
        self.file_lbl.setAlignment(Qt.AlignCenter)
        self.file_lbl.setStyleSheet("color: #4f8ef7; background: transparent; font-size: 12px;")
        self.file_lbl.setWordWrap(True)
        self.file_lbl.hide()

        layout.addWidget(self.icon_lbl)
        layout.addWidget(self.msg_lbl)
        layout.addWidget(self.sub_lbl)
        layout.addWidget(self.browse_btn, alignment=Qt.AlignCenter)
        layout.addWidget(self.file_lbl)

    def _browse(self):
        exts = " ".join(f"*{e}" for e in SUPPORTED_EXTS)
        path, _ = QFileDialog.getOpenFileName(
            self, "Select clip", "", f"Media files ({exts})")
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self.file_path = path
        fname = os.path.basename(path)
        self.msg_lbl.setText("File ready")
        self.msg_lbl.setStyleSheet("color: #4f8ef7; background: transparent; font-size: 13px;")
        self.icon_lbl.setText("✓")
        self.icon_lbl.setStyleSheet("color: #4f8ef7; background: transparent;")
        self.file_lbl.setText(fname)
        self.file_lbl.show()
        self.file_dropped.emit(path)

    def clear(self):
        self.file_path = None
        self.msg_lbl.setText("Drag & drop a clip here")
        self.msg_lbl.setStyleSheet("color: #5a6480; background: transparent; font-size: 13px;")
        self.icon_lbl.setText("⬆")
        self.icon_lbl.setStyleSheet("color: #3a3f55; background: transparent;")
        self.file_lbl.hide()
        self._update_style(False)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and os.path.splitext(urls[0].toLocalFile())[1].lower() in SUPPORTED_EXTS:
                event.acceptProposedAction()
                self._update_style(True)
                return
        event.ignore()

    def dragLeaveEvent(self, _):
        self._update_style(False)

    def dropEvent(self, event: QDropEvent):
        self._update_style(False)
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.splitext(path)[1].lower() in SUPPORTED_EXTS:
                self._set_file(path)
                event.acceptProposedAction()

    def _update_style(self, active: bool):
        if active:
            self.setStyleSheet("""
                QFrame#card {
                    background-color: #1e2535;
                    border: 1px dashed #4f8ef7;
                    border-radius: 10px;
                }
            """)
        else:
            self.setStyleSheet("")


# ─────────────────────────────────────────────
#  Login page
# ─────────────────────────────────────────────

class LoginPage(QWidget):
    login_success = Signal(object)  # emits KitsuClient

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_saved()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(420)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(36, 36, 36, 36)
        lay.setSpacing(16)

        # Logo / title
        title = QLabel(APP_NAME)
        title.setObjectName("title")
        sub = QLabel("Shot preview publisher")
        sub.setObjectName("subtitle")
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addSpacing(12)

        # Server URL
        srv_lbl = QLabel("KITSU SERVER URL")
        srv_lbl.setObjectName("section")
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("https://kitsu.mystudio.com")
        lay.addWidget(srv_lbl)
        lay.addWidget(self.server_input)

        # Email
        email_lbl = QLabel("EMAIL")
        email_lbl.setObjectName("section")
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("artist@mystudio.com")
        lay.addWidget(email_lbl)
        lay.addWidget(self.email_input)

        # Password
        pwd_lbl = QLabel("PASSWORD")
        pwd_lbl.setObjectName("section")
        self.pwd_input = QLineEdit()
        self.pwd_input.setPlaceholderText("••••••••••")
        self.pwd_input.setEchoMode(QLineEdit.Password)
        lay.addWidget(pwd_lbl)
        lay.addWidget(self.pwd_input)

        # Remember me
        self.remember_cb = QCheckBox("Remember me")
        lay.addWidget(self.remember_cb)
        lay.addSpacing(4)

        # Login button
        self.login_btn = QPushButton("Sign in")
        self.login_btn.setObjectName("primary")
        self.login_btn.clicked.connect(self._do_login)
        self.pwd_input.returnPressed.connect(self._do_login)
        lay.addWidget(self.login_btn)

        # Error label
        self.err_lbl = QLabel()
        self.err_lbl.setStyleSheet("color: #e05a6a; font-size: 12px;")
        self.err_lbl.setWordWrap(True)
        self.err_lbl.hide()
        lay.addWidget(self.err_lbl)

        root.addWidget(card, alignment=Qt.AlignCenter)

    def _load_saved(self):
        s = load_settings()
        if s.get("server"):
            self.server_input.setText(s["server"])
        if s.get("email"):
            self.email_input.setText(s["email"])
        if s.get("remember"):
            self.remember_cb.setChecked(True)
            pwd = keyring.get_password(KEYRING_SVC, s.get("email", ""))
            if pwd:
                self.pwd_input.setText(pwd)

    def _do_login(self):
        server = self.server_input.text().strip()
        email  = self.email_input.text().strip()
        pwd    = self.pwd_input.text()
        if not all([server, email, pwd]):
            self._show_error("Please fill in all fields.")
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("Signing in…")
        self.err_lbl.hide()

        def _worker():
            try:
                client = KitsuClient(server)
                client.login(email, pwd)
                return client, None
            except Exception as e:
                return None, str(e)

        def _done(result):
            client, err = result
            self.login_btn.setEnabled(True)
            self.login_btn.setText("Sign in")
            if err:
                self._show_error(f"Login failed: {err}")
            else:
                # Save credentials
                if self.remember_cb.isChecked():
                    s = load_settings()
                    s.update({"server": server, "email": email, "remember": True})
                    save_settings(s)
                    keyring.set_password(KEYRING_SVC, email, pwd)
                else:
                    # Clear credentials but keep last selections
                    s = load_settings()
                    s.pop("server", None)
                    s.pop("email", None)
                    s.pop("remember", None)
                    save_settings(s)
                self.login_success.emit(client)

        t = threading.Thread(target=lambda: _done(_worker()), daemon=True)
        t.start()

    def _show_error(self, msg: str):
        self.err_lbl.setText(msg)
        self.err_lbl.show()


# ─────────────────────────────────────────────
#  Publish page
# ─────────────────────────────────────────────

class PublishPage(QWidget):
    logout_requested = Signal()

    def __init__(self, client: KitsuClient, parent=None):
        super().__init__(parent)
        self.client = client
        self._projects      = []
        self._sequences     = []
        self._shots         = []
        self._task_types    = []
        self._shot_tasks    = []
        self._task_statuses = []
        self._publish_thread = None
        self._publish_worker = None
        self._bridge = ResultBridge(self)  # thread-safe callback bridge
        self._build_ui()
        self._load_initial_data()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── Header ───────────────────────────────
        header = QHBoxLayout()
        title = QLabel(APP_NAME)
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()

        self.user_lbl = QLabel()
        self.user_lbl.setObjectName("subtitle")
        header.addWidget(self.user_lbl)

        logout_btn = QPushButton("Sign out")
        logout_btn.setObjectName("danger")
        logout_btn.clicked.connect(self.logout_requested.emit)
        header.addWidget(logout_btn)
        root.addLayout(header)

        # ── Main row ─────────────────────────────
        main_row = QHBoxLayout()
        main_row.setSpacing(16)

        # Left: selectors card
        left_card = QFrame()
        left_card.setObjectName("card")
        left_lay = QVBoxLayout(left_card)
        left_lay.setContentsMargins(20, 20, 20, 20)
        left_lay.setSpacing(12)

        def _section(text):
            l = QLabel(text)
            l.setObjectName("section")
            return l

        # Project
        left_lay.addWidget(_section("PROJECT"))
        self.project_cb = QComboBox()
        self.project_cb.setPlaceholderText("Select project…")
        self.project_cb.currentIndexChanged.connect(self._on_project_changed)
        left_lay.addWidget(self.project_cb)

        # Sequence
        left_lay.addWidget(_section("SEQUENCE / EPISODE"))
        self.seq_cb = QComboBox()
        self.seq_cb.setPlaceholderText("Select sequence…")
        self.seq_cb.setEnabled(False)
        self.seq_cb.currentIndexChanged.connect(self._on_seq_changed)
        left_lay.addWidget(self.seq_cb)

        # Shot
        left_lay.addWidget(_section("SHOT"))
        self.shot_cb = QComboBox()
        self.shot_cb.setPlaceholderText("Select shot…")
        self.shot_cb.setEnabled(False)
        self.shot_cb.currentIndexChanged.connect(self._on_shot_changed)
        left_lay.addWidget(self.shot_cb)

        # Task type
        left_lay.addWidget(_section("TASK TYPE"))
        self.task_type_cb = QComboBox()
        self.task_type_cb.setPlaceholderText("Select task type…")
        self.task_type_cb.setEnabled(False)
        self.task_type_cb.currentIndexChanged.connect(lambda _: self._update_publish_btn())
        left_lay.addWidget(self.task_type_cb)

        # Status after publish
        left_lay.addWidget(_section("SET STATUS AFTER PUBLISH"))
        self.status_cb = QComboBox()
        self.status_cb.setPlaceholderText("Select status…")
        self.status_cb.setEnabled(False)
        left_lay.addWidget(self.status_cb)

        left_lay.addStretch()
        main_row.addWidget(left_card, stretch=1)

        # Right: drop zone + comment card
        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        # Drop zone
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(lambda _: self._update_publish_btn())
        right_col.addWidget(self.drop_zone)

        # Comment
        self.comment_edit = QTextEdit()
        self.comment_edit.setPlaceholderText("Optional comment for this revision…")
        self.comment_edit.setFixedHeight(90)
        self.comment_edit.setStyleSheet("""
            QTextEdit {
                background-color: #22252e;
                border: 1px solid #2e3240;
                border-radius: 8px;
                color: #d4d8e2;
                padding: 10px 14px;
            }
            QTextEdit:focus { border-color: #4f8ef7; }
        """)
        right_col.addWidget(self.comment_edit)

        # Publish button
        self.publish_btn = QPushButton("Publish to Kitsu")
        self.publish_btn.setObjectName("primary")
        self.publish_btn.setEnabled(False)
        self.publish_btn.clicked.connect(self._do_publish)
        right_col.addWidget(self.publish_btn)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        right_col.addWidget(self.progress)

        # Status label
        self.status_lbl = QLabel("Connecting…")
        self.status_lbl.setObjectName("accent")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        right_col.addWidget(self.status_lbl)

        main_row.addLayout(right_col, stretch=1)
        root.addLayout(main_row, stretch=1)

    # ── Data loading ──────────────────────────────

    def _run_in_thread(self, fn, *args, on_done=None):
        """Run fn in a background thread; safely post result back to main thread."""
        import threading
        def _worker():
            try:
                result = fn(*args)
                err = ""
            except Exception as e:
                result = []
                err = str(e)
            if on_done:
                self._bridge.result.emit(on_done, result, err)
        threading.Thread(target=_worker, daemon=True).start()

    def _load_initial_data(self):
        self._show_status("Loading projects…", error=False)
        # Load task types + statuses in parallel
        self._run_in_thread(self.client.get_task_types, on_done=self._on_task_types_loaded)
        self._run_in_thread(self.client.get_task_statuses, on_done=self._on_statuses_loaded)

        def done(data, err):
            if err:
                self._show_status(f"Error loading projects: {err}", error=True)
                return
            if not data:
                self._show_status("No projects found — check your Kitsu permissions.", error=True)
                return
            self._projects = data
            self.project_cb.blockSignals(True)
            self.project_cb.clear()
            self.project_cb.addItem("— select project —", None)
            for p in data:
                self.project_cb.addItem(p["name"], p["id"])
            self.project_cb.blockSignals(False)
            self._show_status(f"Loaded {len(data)} project(s) — select one to begin.", error=False)

            # Restore last selections — pass saved IDs through the cascade
            s = load_settings()
            print(f"[restore] settings keys: {list(s.keys())}")
            print(f"[restore] last_project={s.get('last_project')} last_sequence={s.get('last_sequence')} last_shot={s.get('last_shot')}")
            last_proj = s.get("last_project")
            if last_proj:
                for i in range(self.project_cb.count()):
                    if self.project_cb.itemData(i) == last_proj:
                        # Block signals so _on_project_changed doesn't fire yet
                        self.project_cb.blockSignals(True)
                        self.project_cb.setCurrentIndex(i)
                        self.project_cb.blockSignals(False)
                        # Manually kick off sequence load with restore context
                        self._restore_sequences(last_proj,
                                                s.get("last_sequence"),
                                                s.get("last_shot"))
                        break

        self._run_in_thread(self.client.get_projects, on_done=done)

    def _restore_sequences(self, project_id, last_seq_id, last_shot_id):
        """Load sequences for project, then restore sequence + shot silently."""
        self.seq_cb.clear()
        self.seq_cb.addItem("Loading…", None)
        self.seq_cb.setEnabled(False)

        def done(data, err):
            self.seq_cb.clear()
            if err or not data:
                self.seq_cb.setEnabled(False)
                return
            self._sequences = data
            self.seq_cb.addItem("— select sequence —", None)
            for s in data:
                self.seq_cb.addItem(s["name"], s["id"])
            self.seq_cb.setEnabled(True)

            if last_seq_id:
                for i in range(self.seq_cb.count()):
                    if self.seq_cb.itemData(i) == last_seq_id:
                        self.seq_cb.blockSignals(True)
                        self.seq_cb.setCurrentIndex(i)
                        self.seq_cb.blockSignals(False)
                        self._restore_shots(last_seq_id, last_shot_id)
                        break

        self._run_in_thread(self.client.get_sequences, project_id, on_done=done)

    def _restore_shots(self, seq_id, last_shot_id):
        """Load shots for sequence, then restore shot silently."""
        self.shot_cb.clear()
        self.shot_cb.addItem("Loading…", None)
        self.shot_cb.setEnabled(False)

        def done(data, err):
            self.shot_cb.clear()
            if err or not data:
                self.shot_cb.setEnabled(False)
                return
            self._shots = data
            self.shot_cb.addItem("— select shot —", None)
            for s in data:
                self.shot_cb.addItem(s["name"], s["id"])
            self.shot_cb.setEnabled(True)

            if last_shot_id:
                for i in range(self.shot_cb.count()):
                    if self.shot_cb.itemData(i) == last_shot_id:
                        self.shot_cb.blockSignals(True)
                        self.shot_cb.setCurrentIndex(i)
                        self.shot_cb.blockSignals(False)
                        # Now load tasks for this shot normally (triggers task dropdown)
                        self._load_tasks_for_shot(last_shot_id)
                        break

        self._run_in_thread(self.client.get_shots, seq_id, on_done=done)

    def _load_tasks_for_shot(self, shot_id):
        self.task_type_cb.clear()
        self.task_type_cb.addItem("Loading…", None)
        self.task_type_cb.setEnabled(False)
        self._run_in_thread(
            self.client.get_shot_tasks, shot_id,
            on_done=self._on_shot_tasks_loaded
        )

    def _on_task_types_loaded(self, data, err):
        if not err:
            self._task_types = data

    def _on_statuses_loaded(self, data, err):
        if not err:
            self._task_statuses = data
            self.status_cb.clear()
            self.status_cb.addItem("— no change —", None)
            for s in data:
                self.status_cb.addItem(s["name"], s["id"])
            # Preselect "WFA" if found
            for i, s in enumerate(data):
                if s.get("short_name", "").upper() in ("WFA", "WAITING FOR APPROVAL"):
                    self.status_cb.setCurrentIndex(i + 1)
                    break
            self.status_cb.setEnabled(True)

    def _on_project_changed(self, idx):
        project_id = self.project_cb.currentData()
        self.seq_cb.clear()
        self.shot_cb.clear()
        self.task_type_cb.clear()
        self.seq_cb.setEnabled(False)
        self.shot_cb.setEnabled(False)
        self.task_type_cb.setEnabled(False)
        self._update_publish_btn()
        if not project_id:
            return
        # Save selection
        s = load_settings()
        s["last_project"] = project_id
        save_settings(s)

        self.seq_cb.addItem("Loading…", None)
        self._run_in_thread(
            self.client.get_sequences, project_id,
            on_done=self._on_sequences_loaded
        )

    def _on_sequences_loaded(self, data, err):
        self.seq_cb.clear()
        if err:
            self._show_status(f"Error: {err}", error=True)
            return
        self._sequences = data
        self.seq_cb.addItem("— select sequence —", None)
        for s in data:
            self.seq_cb.addItem(s["name"], s["id"])
        self.seq_cb.setEnabled(True)

    def _on_seq_changed(self, idx):
        seq_id = self.seq_cb.currentData()
        self.shot_cb.clear()
        self.shot_cb.setEnabled(False)
        self.task_type_cb.clear()
        self.task_type_cb.setEnabled(False)
        self._update_publish_btn()
        if not seq_id:
            return
        s = load_settings()
        s["last_sequence"] = seq_id
        save_settings(s)

        self.shot_cb.addItem("Loading…", None)
        self._run_in_thread(
            self.client.get_shots, seq_id,
            on_done=self._on_shots_loaded
        )

    def _on_shots_loaded(self, data, err):
        self.shot_cb.clear()
        if err:
            self._show_status(f"Error: {err}", error=True)
            return
        self._shots = data
        self.shot_cb.addItem("— select shot —", None)
        for s in data:
            self.shot_cb.addItem(s["name"], s["id"])
        self.shot_cb.setEnabled(True)

    def _on_shot_changed(self, idx):
        shot_id = self.shot_cb.currentData()
        self.task_type_cb.clear()
        self.task_type_cb.setEnabled(False)
        self._update_publish_btn()
        if not shot_id:
            return
        s = load_settings()
        s["last_shot"] = shot_id
        save_settings(s)

        self._load_tasks_for_shot(shot_id)

    def _on_shot_tasks_loaded(self, data, err):
        self.task_type_cb.clear()
        if err:
            self._show_status(f"Error loading tasks: {err}", error=True)
            return
        self._shot_tasks = data
        if not data:
            self.task_type_cb.addItem("No tasks found", None)
            return
        self.task_type_cb.addItem("— select task type —", None)
        # Enrich with task type name
        tt_map = {t["id"]: t["name"] for t in self._task_types}
        for task in data:
            tt_name = tt_map.get(task.get("task_type_id"), "Unknown")
            self.task_type_cb.addItem(tt_name, task["id"])
        self.task_type_cb.setEnabled(True)
        self._update_publish_btn()

    # ── Publish ────────────────────────────────────

    def _update_publish_btn(self):
        ok = bool(
            self.shot_cb.currentData()
            and self.task_type_cb.currentData()
            and self.drop_zone.file_path
        )
        self.publish_btn.setEnabled(ok)

    def _do_publish(self):
        task_id   = self.task_type_cb.currentData()
        file_path = self.drop_zone.file_path
        comment   = self.comment_edit.toPlainText().strip()
        status_id = self.status_cb.currentData()

        if not task_id or not file_path:
            return

        self.publish_btn.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()
        self._show_status("Uploading…", error=False)

        import threading

        def _upload():
            try:
                self._bridge.result.emit(
                    lambda d, e: self.progress.setValue(20), [], "")
                result = self.client.upload_preview_with_status(
                    task_id, file_path, comment, status_id
                )
                print(f"[Publish OK] {result}")
                self._bridge.result.emit(
                    lambda d, e: self._on_publish_done(True, "Published successfully!"), [], "")
            except Exception as ex:
                import traceback
                traceback.print_exc()
                msg = str(ex)
                self._bridge.result.emit(
                    lambda d, e, m=msg: self._on_publish_done(False, m), [], "")

        threading.Thread(target=_upload, daemon=True).start()

    def _on_publish_done(self, ok: bool, msg: str):
        self.progress.hide()
        if ok:
            self._show_status("✓  " + msg, error=False)
            self.drop_zone.clear()
            self.comment_edit.clear()
            self._update_publish_btn()
        else:
            self._show_status("✗  " + msg, error=True)
        self.publish_btn.setEnabled(True)

    def _show_status(self, msg: str, error: bool = False):
        color = "#e05a6a" if error else "#4f8ef7"
        self.status_lbl.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.status_lbl.setText(msg)




# ─────────────────────────────────────────────
#  Main window
# ─────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(860, 600)
        self.resize(960, 680)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.login_page = LoginPage()
        self.login_page.login_success.connect(self._on_login)
        self.stack.addWidget(self.login_page)

        self.statusBar().showMessage(f"{APP_NAME} v{APP_VERSION}")

    def _on_login(self, client: KitsuClient):
        publish_page = PublishPage(client)
        publish_page.logout_requested.connect(self._on_logout)
        self.stack.addWidget(publish_page)
        self.stack.setCurrentWidget(publish_page)
        self.statusBar().showMessage("Connected")

    def _on_logout(self):
        # Remove publish page, back to login
        if self.stack.count() > 1:
            w = self.stack.widget(1)
            self.stack.removeWidget(w)
            w.deleteLater()
        self.stack.setCurrentIndex(0)
        self.statusBar().showMessage("Signed out")


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    # Fix Qt font warning — set a valid default font before any widgets are created
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    app.setStyleSheet(STYLESHEET)

    # High-DPI
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
