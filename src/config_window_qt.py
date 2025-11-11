#!/usr/bin/env python3
"""
Modern Settings Window (Qt) for Clipboard to ePub
Falls back to Tkinter settings if PySide6 is not available.
Cross-platform friendly. Kept as a separate module to avoid impacting
current flows; menubar prefers this window when present.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
# Robust import for paths whether run from repo root or src/
try:
    from src import paths as paths  # type: ignore
except Exception:
    import paths  # type: ignore


def load_config(defaults: dict) -> dict:
    path = paths.get_config_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Ensure all defaults are present
            for k, v in defaults.items():
                data.setdefault(k, v)
            return data
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            print(f"Warning: Could not load config from {path}: {e}")
            return defaults.copy()
    return defaults.copy()


def save_config(config: dict) -> bool:
    try:
        path = paths.get_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return True
    except (OSError, IOError, PermissionError) as e:
        print(f"Error: Could not save config to {path}: {e}")
        return False


# Try importing PySide6; fallback to Tkinter module if missing
try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSpinBox,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
    HAVE_QT = True
except ImportError as e:
    # PySide6 not installed - will fall back to Tkinter
    print(f"PySide6 not available: {e}")
    HAVE_QT = False


DEFAULT_HOTKEY = "ctrl+shift+e" if sys.platform.startswith("win") else "cmd+shift+e"
DEFAULTS = {
    "output_directory": str(paths.get_default_output_dir()),
    "hotkey": DEFAULT_HOTKEY,
    "author": "Unknown Author",
    "language": "en",
    "style": "default",
    "auto_open": False,
    "show_notifications": True,
    "chapter_words": 5000,
}


def list_available_styles() -> list[str]:
    styles = {"default", "minimal", "modern"}
    try:
        templates_dir = Path(__file__).resolve().parent.parent / "templates"
        if templates_dir.exists():
            for p in templates_dir.glob("*.css"):
                styles.add(p.stem)
    except (OSError, RuntimeError) as e:
        print(f"Warning: Could not scan templates directory: {e}")
        # Return default styles only
    return sorted(styles)


if HAVE_QT:

    class SettingsDialog(QDialog):
        def __init__(self, config: dict, parent: QWidget | None = None):
            super().__init__(parent)
            self.setWindowTitle("Clipboard to ePub – Settings")
            self.setMinimumSize(640, 520)
            self.config = config

            # Window icon (optional)
            try:
                icon_path = Path(__file__).resolve().parent.parent / "resources" / "icon.png"
                if icon_path.exists():
                    self.setWindowIcon(QIcon(str(icon_path)))
            except (OSError, RuntimeError) as e:
                # Icon loading failed - not critical
                print(f"Warning: Could not load window icon: {e}")

            # Main layout with tabs inside a scroll area per tab if needed
            layout = QVBoxLayout(self)
            self.tabs = QTabWidget(self)
            layout.addWidget(self.tabs)

            # Tabs (wrapped in scroll areas to avoid clipping on small screens)
            self._setup_general_tab()
            self._setup_appearance_tab()
            self._setup_advanced_tab()

            # Buttons
            self.button_box = QDialogButtonBox(
                QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self
            )
            self.button_box.accepted.connect(self.on_save)
            self.button_box.rejected.connect(self.reject)
            layout.addWidget(self.button_box)

        # ---- Tabs ----
        def _setup_general_tab(self):
            container = QWidget()
            form = QFormLayout(container)

            # Output directory (line edit + browse)
            row = QWidget()
            row_layout = QHBoxLayout(row)
            self.output_edit = QLineEdit(self.config["output_directory"])
            browse_btn = QPushButton("Browse…")
            browse_btn.clicked.connect(self._browse_output)
            row_layout.addWidget(self.output_edit)
            row_layout.addWidget(browse_btn)
            form.addRow("Output Directory:", row)

            # Author
            self.author_edit = QLineEdit(self.config["author"])
            form.addRow("Default Author:", self.author_edit)

            # Language
            self.language_combo = QComboBox()
            self.language_combo.addItems(["en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh", "ko"])
            current_lang = self.config.get("language", "en")
            idx = self.language_combo.findText(current_lang)
            if idx >= 0:
                self.language_combo.setCurrentIndex(idx)
            form.addRow("Language:", self.language_combo)

            # Toggles
            self.auto_open_chk = QCheckBox("Auto-open ePub files after creation")
            self.auto_open_chk.setChecked(bool(self.config.get("auto_open", False)))
            self.notifications_chk = QCheckBox("Show notifications")
            self.notifications_chk.setChecked(bool(self.config.get("show_notifications", True)))
            form.addRow(self.auto_open_chk)
            form.addRow(self.notifications_chk)

            # Wrap in scroll area
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(container)
            self.tabs.addTab(scroll, "General")

        def _setup_appearance_tab(self):
            container = QWidget()
            form = QFormLayout(container)

            # CSS Style
            self.style_combo = QComboBox()
            for s in list_available_styles():
                self.style_combo.addItem(s)
            cur_style = self.config.get("style", "default")
            idx = self.style_combo.findText(cur_style)
            if idx >= 0:
                self.style_combo.setCurrentIndex(idx)
            form.addRow("CSS Style:", self.style_combo)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(container)
            self.tabs.addTab(scroll, "Appearance")

        def _setup_advanced_tab(self):
            container = QWidget()
            form = QFormLayout(container)

            # Chapter words
            self.chapter_spin = QSpinBox()
            self.chapter_spin.setRange(100, 50000)
            self.chapter_spin.setSingleStep(500)
            self.chapter_spin.setValue(int(self.config.get("chapter_words", 5000)))
            form.addRow("Words per Chapter:", self.chapter_spin)

            # Info
            cfg_path_text = str(paths.get_config_path())
            default_hotkey_text = "Ctrl+Shift+E" if sys.platform.startswith("win") else "Cmd+Shift+E"
            info = QLabel(
                f"Config Location: {cfg_path_text}\n"
                f"Hotkey: {default_hotkey_text} (not configurable yet)"
            )
            info.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(info)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(container)
            self.tabs.addTab(scroll, "Advanced")

        # ---- Actions ----
        def _browse_output(self):
            initial = self.output_edit.text() or str(Path.home())
            folder = QFileDialog.getExistingDirectory(self, "Select Output Directory", initial)
            if folder:
                self.output_edit.setText(folder)

        def on_save(self):
            # Gather values and persist
            cfg = {
                "output_directory": self.output_edit.text().strip() or DEFAULTS["output_directory"],
                "hotkey": self.config.get("hotkey", DEFAULTS["hotkey"]),
                "author": self.author_edit.text().strip() or DEFAULTS["author"],
                "language": self.language_combo.currentText(),
                "style": self.style_combo.currentText(),
                "auto_open": self.auto_open_chk.isChecked(),
                "show_notifications": self.notifications_chk.isChecked(),
                "chapter_words": int(self.chapter_spin.value()),
            }

            ok = save_config(cfg)
            if ok:
                QMessageBox.information(self, "Settings Saved", "Configuration saved successfully!\n\nRestart the menu bar app to apply changes.")
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to save configuration.")


def run_qt_dialog():
    # If Qt is available, show Qt dialog; otherwise fallback to Tkinter
    if HAVE_QT:
        app = QApplication.instance() or QApplication(sys.argv)
        cfg = load_config(DEFAULTS)
        dlg = SettingsDialog(cfg)
        dlg.exec()
        return 0
    else:
        # Fallback to Tkinter settings window
        import config_window as tk_settings  # type: ignore

        tk_settings.main()
        return 0


def main():
    sys.exit(run_qt_dialog())


if __name__ == "__main__":
    main()
