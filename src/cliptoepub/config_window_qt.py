#!/usr/bin/env python3
"""
Modern Settings Window (Qt) for Clipboard to ePub
Falls back to Tkinter settings if PySide6 is not available.
Cross-platform friendly. Kept as a separate module to avoid impacting
current flows; menubar prefers this window when present.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional, Union

try:
    # Normal package import (when run as cliptoepub.config_window_qt)
    from . import paths as paths
    from .llm_config import ensure_llm_config, sync_legacy_prompt
except ImportError:
    # Allow running as a standalone script (subprocess call with no package context)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    import cliptoepub.paths as paths  # type: ignore
    from cliptoepub.llm_config import ensure_llm_config, sync_legacy_prompt  # type: ignore

import tempfile


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
    from PySide6.QtGui import QIcon, QKeySequence
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
        QKeySequenceEdit,
        QScrollArea,
        QSpinBox,
        QDoubleSpinBox,
        QTextEdit,
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
    "output_format": "both",  # "epub", "markdown", or "both"
    "output_format": "both",  # "epub", "markdown", or "both"
    "hotkey": DEFAULT_HOTKEY,
    "author": "Unknown Author",
    "language": "en",
    "style": "default",
    "auto_open": False,
    "show_notifications": True,
    "chapter_words": 5000,
    # YouTube subtitles
    "youtube_lang_1": "en",
    "youtube_lang_2": "es",
    "youtube_lang_3": "pt",
    "youtube_prefer_native": True,
    # LLM defaults
    "anthropic_api_key": "",
    # Control whether API keys are persisted in config (plaintext)
    "llm_store_keys_in_config": True,
    # Default model for OpenRouter (Sonnet 4.5 – 1M)
    "anthropic_model": "anthropic/claude-sonnet-4.5",
    "anthropic_prompt": "",
    "anthropic_max_tokens": 2048,
    "anthropic_temperature": 0.2,
    "anthropic_timeout_seconds": 60,
    "anthropic_retry_count": 10,
    "anthropic_hotkey": "ctrl+shift+l" if sys.platform.startswith("win") else "cmd+shift+l",
    # Provider selection and OpenRouter key
    "llm_provider": "openrouter",  # 'anthropic' | 'openrouter'
    "openrouter_api_key": "",
    # Multi-prompt configuration
    "llm_prompts": [
        {"name": "", "text": "", "overrides": {}},
        {"name": "", "text": "", "overrides": {}},
        {"name": "", "text": "", "overrides": {}},
        {"name": "", "text": "", "overrides": {}},
        {"name": "", "text": "", "overrides": {}},
    ],
    "llm_prompt_active": 0,
    "llm_per_prompt_overrides": False,
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

    def _normalize_for_qt(seq_text: str) -> str:
        # Convert stored format like 'cmd+shift+e' to Qt-friendly 'Meta+Shift+E'
        if not seq_text:
            return ""
        parts = [p.strip().lower() for p in seq_text.split("+") if p.strip()]
        out: list[str] = []
        for p in parts:
            if p in ("cmd", "command", "meta"):
                out.append("Meta")
            elif p in ("ctrl", "control"):
                out.append("Ctrl")
            elif p == "shift":
                out.append("Shift")
            elif p in ("alt", "option"):
                out.append("Alt")
            else:
                out.append(p.upper())
        return "+".join(out)

    def _normalize_from_qt(seq: QKeySequence) -> str:
        # Convert Qt sequence to portable lower-case like 'cmd+shift+e' on mac, 'ctrl+shift+e' otherwise
        if not seq or seq.isEmpty():
            return DEFAULTS["hotkey"]
        text = seq.toString(QKeySequence.PortableText)  # e.g., 'Meta+Shift+E'
        parts = [p.strip().lower() for p in text.split("+") if p.strip()]
        out: list[str] = []
        for p in parts:
            if p == "meta":
                out.append("cmd")
            else:
                out.append(p)
        return "+".join(out)

    class SettingsDialog(QDialog):
        def __init__(self, config: dict, parent: Optional[QWidget] = None):
            super().__init__(parent)
            self.setWindowTitle("Clipboard to ePub – Settings")
            self.setMinimumSize(640, 520)
            self.config = config
            # Ensure new schema keys
            ensure_llm_config(self.config)

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
            self._setup_llm_tab()

            # Buttons
            self.button_box = QDialogButtonBox(
                QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self
            )
            self.button_box.accepted.connect(self.on_save)
            self.button_box.rejected.connect(self.reject)
            layout.addWidget(self.button_box)

        # ---- Validation helpers ----
        def _validate_before_save(self, cfg: dict) -> list[str]:
            warnings: list[str] = []
            # Provider/API key presence
            try:
                provider = (cfg.get("llm_provider", "openrouter") or "").strip().lower()
                store_keys = bool(cfg.get("llm_store_keys_in_config", True))
                if provider == "anthropic":
                    if not (os.getenv("ANTHROPIC_API_KEY") or (store_keys and cfg.get("anthropic_api_key"))):
                        warnings.append("Anthropic provider selected but no API key configured (env or config).")
                elif provider == "openrouter":
                    if not (os.getenv("OPENROUTER_API_KEY") or (store_keys and cfg.get("openrouter_api_key"))):
                        warnings.append("OpenRouter provider selected but no API key configured (env or config).")
            except Exception:
                pass

            # Output directory write check (best-effort)
            try:
                out_dir = Path(cfg.get("output_directory") or "").expanduser()
                out_dir.mkdir(parents=True, exist_ok=True)
                # try temp creation to verify writability
                with tempfile.NamedTemporaryFile(dir=str(out_dir), prefix="cte_chk_", delete=True):
                    pass
            except Exception:
                warnings.append("Output directory may not be writable. ePubs could fail to save.")

            # Active prompt content (optional)
            try:
                if bool(cfg.get("llm_prompts")):
                    active = int(cfg.get("llm_prompt_active", 0))
                    prompts = list(cfg.get("llm_prompts", []))
                    if 0 <= active < len(prompts):
                        if not (prompts[active].get("text") or "").strip():
                            warnings.append("Active LLM prompt is empty.")
            except Exception:
                pass

            return warnings

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

            # Output format (epub / markdown / both)
            self.output_format_combo = QComboBox()
            self.output_format_combo.addItems(["epub", "markdown", "both"])
            fmt = str(self.config.get("output_format", DEFAULTS["output_format"]))
            idx = self.output_format_combo.findText(fmt)
            if idx < 0:
                idx = self.output_format_combo.findText(DEFAULTS["output_format"])
            if idx >= 0:
                self.output_format_combo.setCurrentIndex(idx)
            form.addRow("Output Format:", self.output_format_combo)

            # Output format (epub / markdown / both)
            self.output_format_combo = QComboBox()
            self.output_format_combo.addItems(["epub", "markdown", "both"])
            fmt = str(self.config.get("output_format", DEFAULTS["output_format"]))
            idx = self.output_format_combo.findText(fmt)
            if idx < 0:
                idx = self.output_format_combo.findText(DEFAULTS["output_format"])
            if idx >= 0:
                self.output_format_combo.setCurrentIndex(idx)
            form.addRow("Output Format:", self.output_format_combo)

            # Hotkey (capture)
            hotkey_row = QWidget()
            hotkey_layout = QHBoxLayout(hotkey_row)
            self.hotkey_edit = QKeySequenceEdit()
            try:
                qt_seq = QKeySequence(_normalize_for_qt(self.config.get("hotkey", DEFAULTS["hotkey"])) )
                self.hotkey_edit.setKeySequence(qt_seq)
            except Exception:
                # Fallback to default
                self.hotkey_edit.setKeySequence(QKeySequence(_normalize_for_qt(DEFAULTS["hotkey"])) )
            reset_hotkey_btn = QPushButton("Reset")
            def _reset_hotkey():
                self.hotkey_edit.setKeySequence(QKeySequence(_normalize_for_qt(DEFAULTS["hotkey"])) )
            reset_hotkey_btn.clicked.connect(_reset_hotkey)
            hotkey_layout.addWidget(self.hotkey_edit, stretch=1)
            hotkey_layout.addWidget(reset_hotkey_btn)
            form.addRow("Capture Hotkey:", hotkey_row)

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

            # YouTube subtitles preferences
            yt_group = QGroupBox("YouTube Subtitles")
            yt_layout = QGridLayout(yt_group)
            yt_langs = [
                ("en", "English"),
                ("es", "Spanish"),
                ("pt", "Portuguese"),
                ("hi", "Hindi"),
                ("id", "Indonesian"),
                ("ar", "Arabic"),
                ("ru", "Russian"),
                ("ja", "Japanese"),
                ("ko", "Korean"),
                ("fr", "French"),
                ("de", "German"),
                ("tr", "Turkish"),
            ]
            self.yt_lang1 = QComboBox(); self.yt_lang2 = QComboBox(); self.yt_lang3 = QComboBox()
            for code, label in yt_langs:
                disp = f"{code} – {label}"
                self.yt_lang1.addItem(disp, userData=code)
                self.yt_lang2.addItem(disp, userData=code)
                self.yt_lang3.addItem(disp, userData=code)
            # Set current selections
            def _set_combo(combo: QComboBox, code: str):
                for i in range(combo.count()):
                    if str(combo.itemData(i)) == str(code):
                        combo.setCurrentIndex(i)
                        return
            _set_combo(self.yt_lang1, str(self.config.get("youtube_lang_1", "en")))
            _set_combo(self.yt_lang2, str(self.config.get("youtube_lang_2", "es")))
            _set_combo(self.yt_lang3, str(self.config.get("youtube_lang_3", "pt")))
            self.yt_prefer_native = QCheckBox("Prefer native subtitles; fallback to auto-generated")
            self.yt_prefer_native.setChecked(bool(self.config.get("youtube_prefer_native", True)))

            yt_layout.addWidget(QLabel("Preferred language 1:"), 0, 0)
            yt_layout.addWidget(self.yt_lang1, 0, 1)
            yt_layout.addWidget(QLabel("Preferred language 2:"), 1, 0)
            yt_layout.addWidget(self.yt_lang2, 1, 1)
            yt_layout.addWidget(QLabel("Preferred language 3:"), 2, 0)
            yt_layout.addWidget(self.yt_lang3, 2, 1)
            yt_layout.addWidget(self.yt_prefer_native, 3, 0, 1, 2)
            form.addRow(yt_group)

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
            info = QLabel(
                f"Config Location: {cfg_path_text}\n"
                f"Current Hotkey: {self.config.get('hotkey', DEFAULTS['hotkey']).upper()}"
            )
            info.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(info)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(container)
            self.tabs.addTab(scroll, "Advanced")

        def _setup_llm_tab(self):
            container = QWidget()
            form = QFormLayout(container)

            # Provider selection
            self.provider_combo = QComboBox()
            self.provider_combo.addItem("Anthropic (Sonnet 4.5)", userData="anthropic")
            self.provider_combo.addItem("OpenRouter (Sonnet 4.5 – 1M)", userData="openrouter")
            try:
                # Set initial provider
                cur = str(self.config.get("llm_provider", DEFAULTS["llm_provider"]))
                for i in range(self.provider_combo.count()):
                    if self.provider_combo.itemData(i) == cur:
                        self.provider_combo.setCurrentIndex(i)
                        break
            except Exception:
                pass
            form.addRow("Provider:", self.provider_combo)

            # API Key (masked)
            self.anthropic_key_edit = QLineEdit(self.config.get("anthropic_api_key", ""))
            self.anthropic_key_edit.setEchoMode(QLineEdit.Password)
            form.addRow("Anthropic API Key:", self.anthropic_key_edit)

            # OpenRouter API Key (masked)
            self.openrouter_key_edit = QLineEdit(self.config.get("openrouter_api_key", ""))
            self.openrouter_key_edit.setEchoMode(QLineEdit.Password)
            form.addRow("OpenRouter API Key:", self.openrouter_key_edit)

            # Store-keys toggle and hint about environment variables vs. stored keys
            try:
                self.store_keys_chk = QCheckBox("Store API keys in config file (plaintext)")
                self.store_keys_chk.setChecked(bool(self.config.get("llm_store_keys_in_config", True)))
                form.addRow(self.store_keys_chk)

                hint = QLabel(
                    "Environment variables ANTHROPIC_API_KEY / OPENROUTER_API_KEY take precedence over these fields.\n"
                    "Leave keys empty and/or disable storing to avoid plaintext in the config file."
                )
                hint.setWordWrap(True)
                form.addRow("", hint)
            except Exception:
                pass

            # Model
            self.anthropic_model_edit = QLineEdit(self.config.get("anthropic_model", DEFAULTS["anthropic_model"]))
            try:
                self.anthropic_model_edit.setPlaceholderText("e.g., claude-4.5-sonnet or anthropic/claude-sonnet-4.5")
            except Exception:
                pass
            form.addRow("Model:", self.anthropic_model_edit)

            # Model preset (helps set common ids and provider)
            try:
                self.model_preset_combo = QComboBox()
                self.model_preset_combo.addItem("— Select preset —", userData="")
                self.model_preset_combo.addItem("Sonnet 4.5 – OpenRouter (1M)", userData="anthropic/claude-sonnet-4.5")
                self.model_preset_combo.addItem("Sonnet 4.5 – Anthropic", userData="claude-4.5-sonnet")
                self.model_preset_combo.addItem("Mistral Medium 3.1 – OpenRouter (128k)", userData="mistralai/mistral-medium-3.1")
                def _apply_preset(idx: int):
                    val = self.model_preset_combo.itemData(idx)
                    if not val:
                        return
                    try:
                        self.anthropic_model_edit.setText(str(val))
                        # Auto-switch provider based on id format
                        if "/" in str(val):
                            # OpenRouter-style id
                            for i in range(self.provider_combo.count()):
                                if self.provider_combo.itemData(i) == "openrouter":
                                    self.provider_combo.setCurrentIndex(i)
                                    break
                        else:
                            for i in range(self.provider_combo.count()):
                                if self.provider_combo.itemData(i) == "anthropic":
                                    self.provider_combo.setCurrentIndex(i)
                                    break
                    except Exception:
                        pass
                self.model_preset_combo.currentIndexChanged.connect(_apply_preset)
                form.addRow("Preset:", self.model_preset_combo)
            except Exception:
                pass

            # Provider hint for Sonnet 4.5 (1M context via OpenRouter)
            try:
                hint = QLabel("Tip: For Sonnet 4.5 (1M context), switch Provider to OpenRouter, set model 'anthropic/claude-sonnet-4.5' and configure OPENROUTER_API_KEY.")
                hint.setWordWrap(True)
                form.addRow("", hint)
            except Exception:
                pass

            # Hotkey
            self.anthropic_hotkey_edit = QLineEdit(self.config.get("anthropic_hotkey", DEFAULTS["anthropic_hotkey"]))
            form.addRow("LLM Hotkey:", self.anthropic_hotkey_edit)

            # Multi-prompt editor
            prompts_group = QGroupBox("Custom Prompts")
            prompts_layout = QVBoxLayout(prompts_group)
            # Toggle for per-prompt overrides
            self.llm_overrides_chk = QCheckBox("Enable per-prompt overrides")
            self.llm_overrides_chk.setChecked(bool(self.config.get("llm_per_prompt_overrides", False)))
            prompts_layout.addWidget(self.llm_overrides_chk)

            # Radio group for active prompt selection
            from PySide6.QtWidgets import QButtonGroup
            self.prompt_radio_group = QButtonGroup(prompts_group)
            self.prompt_radio_group.setExclusive(True)
            self.prompt_widgets = []  # store widgets per prompt

            prompts = list(self.config.get("llm_prompts", []))
            try:
                active_idx = int(self.config.get("llm_prompt_active", 0))
            except Exception:
                active_idx = 0

            for i in range(5):
                item = prompts[i] if i < len(prompts) else {"name": "", "text": "", "overrides": {}}
                box = QGroupBox(f"Prompt {i+1}")
                box_layout = QFormLayout(box)
                name_edit = QLineEdit(str(item.get("name", "")))
                radio = QCheckBox("Use with Hotkey")
                # We simulate radio with a checkbox wired to a button group for consistent UI size
                # but enforce exclusivity manually
                # Better: use QRadioButton; keep checkbox API minimal change
                try:
                    from PySide6.QtWidgets import QRadioButton
                    radio_btn = QRadioButton("Use with Hotkey")
                    radio_btn.setChecked(i == active_idx)
                    self.prompt_radio_group.addButton(radio_btn, i)
                    box_layout.addRow(radio_btn)
                    radio_widget = radio_btn
                except Exception:
                    radio.setChecked(i == active_idx)
                    box_layout.addRow(radio)
                    radio_widget = radio
                box_layout.addRow("Name:", name_edit)
                text_edit = QTextEdit(str(item.get("text", "")))
                text_edit.setPlaceholderText("System prompt to guide the model output (Markdown)")
                box_layout.addRow("Prompt:", text_edit)

                # Overrides
                overrides = item.get("overrides", {}) or {}
                over_model = QLineEdit(str(overrides.get("model", "")))
                over_maxtok = QSpinBox(); over_maxtok.setRange(1, 200000)
                if "max_tokens" in overrides:
                    over_maxtok.setValue(int(overrides.get("max_tokens", 2048)))
                else:
                    over_maxtok.setSpecialValueText("")
                    over_maxtok.setValue(1)
                    over_maxtok.clear()
                over_temp = QDoubleSpinBox(); over_temp.setRange(0.0, 2.0); over_temp.setSingleStep(0.05)
                if "temperature" in overrides:
                    over_temp.setValue(float(overrides.get("temperature", 0.2)))
                else:
                    over_temp.setSpecialValueText("")
                    over_temp.setValue(0.0)
                    over_temp.clear()
                over_timeout = QSpinBox(); over_timeout.setRange(1, 600)
                if "timeout_seconds" in overrides:
                    over_timeout.setValue(int(overrides.get("timeout_seconds", 60)))
                else:
                    over_timeout.setSpecialValueText("")
                    over_timeout.setValue(1)
                    over_timeout.clear()
                over_retry = QSpinBox(); over_retry.setRange(0, 50)
                if "retry_count" in overrides:
                    over_retry.setValue(int(overrides.get("retry_count", 10)))
                else:
                    over_retry.setSpecialValueText("")
                    over_retry.setValue(0)
                    over_retry.clear()

                # Group overrides in a small grid
                over_row = QWidget(); over_layout = QGridLayout(over_row)
                over_layout.addWidget(QLabel("Model:"), 0, 0); over_layout.addWidget(over_model, 0, 1)
                over_layout.addWidget(QLabel("Max tokens:"), 1, 0); over_layout.addWidget(over_maxtok, 1, 1)
                over_layout.addWidget(QLabel("Temperature:"), 2, 0); over_layout.addWidget(over_temp, 2, 1)
                over_layout.addWidget(QLabel("Timeout (s):"), 3, 0); over_layout.addWidget(over_timeout, 3, 1)
                over_layout.addWidget(QLabel("Retry count:"), 4, 0); over_layout.addWidget(over_retry, 4, 1)
                box_layout.addRow(QLabel("Overrides (optional):"))
                box_layout.addRow(over_row)

                self.prompt_widgets.append({
                    "name": name_edit,
                    "text": text_edit,
                    "radio": radio_widget,
                    "over_model": over_model,
                    "over_maxtok": over_maxtok,
                    "over_temp": over_temp,
                    "over_timeout": over_timeout,
                    "over_retry": over_retry,
                })
                prompts_layout.addWidget(box)

            def _sync_overrides_enabled(state: Union[bool, int]):
                enabled = bool(state)
                for w in self.prompt_widgets:
                    for key in ("over_model", "over_maxtok", "over_temp", "over_timeout", "over_retry"):
                        try:
                            w[key].setEnabled(enabled)
                        except Exception:
                            pass

            self.llm_overrides_chk.toggled.connect(lambda checked: _sync_overrides_enabled(checked))
            # initialize enabled state
            _sync_overrides_enabled(self.llm_overrides_chk.isChecked())

            form.addRow(prompts_group)

            # Numeric params
            self.anthropic_max_tokens_spin = QSpinBox()
            self.anthropic_max_tokens_spin.setRange(1, 200000)
            self.anthropic_max_tokens_spin.setValue(int(self.config.get("anthropic_max_tokens", 2048)))
            form.addRow("Max Tokens:", self.anthropic_max_tokens_spin)

            # Clarification: max_tokens controls output length, not context window
            try:
                note = QLabel("Note: Max Tokens limits output tokens. Context window (input size) depends on the selected model and your account access.")
                note.setWordWrap(True)
                form.addRow("", note)
            except Exception:
                pass

            self.anthropic_temperature_spin = QDoubleSpinBox()
            self.anthropic_temperature_spin.setRange(0.0, 2.0)
            self.anthropic_temperature_spin.setSingleStep(0.1)
            self.anthropic_temperature_spin.setDecimals(2)
            self.anthropic_temperature_spin.setValue(float(self.config.get("anthropic_temperature", 0.2)))
            form.addRow("Temperature:", self.anthropic_temperature_spin)

            self.anthropic_timeout_spin = QSpinBox()
            self.anthropic_timeout_spin.setRange(5, 600)
            self.anthropic_timeout_spin.setValue(int(self.config.get("anthropic_timeout_seconds", 60)))
            form.addRow("Timeout (s):", self.anthropic_timeout_spin)

            self.anthropic_retry_spin = QSpinBox()
            self.anthropic_retry_spin.setRange(0, 20)
            self.anthropic_retry_spin.setValue(int(self.config.get("anthropic_retry_count", 10)))
            form.addRow("Retries:", self.anthropic_retry_spin)

            # Auto-timeout from tokens, preserving manual override
            self._timeout_user_override = False

            def _mark_timeout_override():
                # User edited timeout directly; stop auto-adjusting
                self._timeout_user_override = True

            self.anthropic_timeout_spin.editingFinished.connect(_mark_timeout_override)

            def _recommended_timeout(tokens: int) -> int:
                # Heuristic: ~50 tok/s + 30s buffer; clamp 30..300
                try:
                    v = int(tokens)
                except Exception:
                    v = 0
                rec = int(round(v / 50.0)) + 30
                if rec < 30:
                    rec = 30
                if rec > 300:
                    rec = 300
                return rec

            def _on_tokens_changed(val: int):
                if self._timeout_user_override:
                    return
                # Update timeout programmatically without toggling user intent
                new_timeout = _recommended_timeout(val)
                try:
                    self.anthropic_timeout_spin.blockSignals(True)
                    self.anthropic_timeout_spin.setValue(new_timeout)
                finally:
                    self.anthropic_timeout_spin.blockSignals(False)

            self.anthropic_max_tokens_spin.valueChanged.connect(_on_tokens_changed)

            # Test & Reset buttons
            test_btn = QPushButton("Test Connection")
            def _test():
                try:
                    from .llm.base import LLMRequest
                    from .llm.anthropic import AnthropicProvider
                    from .llm.openrouter import OpenRouterProvider

                    provider = str(self.provider_combo.currentData() or "anthropic").strip().lower()
                    if provider == "openrouter":
                        # Prefer environment variable, fall back to stored value
                        api_key = os.environ.get("OPENROUTER_API_KEY", "") or self.openrouter_key_edit.text().strip()
                        model = self.anthropic_model_edit.text().strip() or "anthropic/claude-sonnet-4.5"
                        llm_provider = OpenRouterProvider()
                    else:
                        # Prefer environment variable, fall back to stored value
                        api_key = os.environ.get("ANTHROPIC_API_KEY", "") or self.anthropic_key_edit.text().strip()
                        model = self.anthropic_model_edit.text().strip() or DEFAULTS["anthropic_model"]
                        llm_provider = AnthropicProvider()

                    # Use active prompt text for test
                    active = 0
                    try:
                        cid = int(self.prompt_radio_group.checkedId())
                        active = cid if cid >= 0 else int(self.config.get("llm_prompt_active", 0))
                    except Exception:
                        try:
                            active = int(self.config.get("llm_prompt_active", 0))
                        except Exception:
                            active = 0
                    if 0 <= active < len(self.prompt_widgets):
                        prompt = self.prompt_widgets[active]["text"].toPlainText().strip() or "Return the input as Markdown."
                    else:
                        prompt = "Return the input as Markdown."

                    sample = "Test message from Clipboard to ePub"
                    request = LLMRequest(
                        text=sample,
                        api_key=api_key,
                        model=model,
                        system_prompt=prompt,
                        max_tokens=128,
                        temperature=0.0,
                        timeout_s=30,
                        retries=2,
                    )
                    md = llm_provider.process(request)
                    preview = (md or "").strip().splitlines()[0:3]
                    QMessageBox.information(self, "LLM OK", "\n".join(preview) or "Received response")
                except Exception as e:
                    QMessageBox.critical(self, "LLM Error", str(e))
            test_btn.clicked.connect(_test)

            reset_btn = QPushButton("Reset Timeout to Recommended")
            def _reset_timeout():
                try:
                    tokens = int(self.anthropic_max_tokens_spin.value())
                except Exception:
                    tokens = 0
                rec = _recommended_timeout(tokens)
                try:
                    self.anthropic_timeout_spin.blockSignals(True)
                    self.anthropic_timeout_spin.setValue(rec)
                finally:
                    self.anthropic_timeout_spin.blockSignals(False)
                # Re-enable auto adjustments for future token changes
                self._timeout_user_override = False

            reset_btn.clicked.connect(_reset_timeout)

            btn_row = QWidget()
            btn_layout = QHBoxLayout(btn_row)
            btn_layout.addWidget(test_btn)
            btn_layout.addWidget(reset_btn)
            form.addRow(btn_row)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(container)
            self.tabs.addTab(scroll, "LLM")

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
                "output_format": str(getattr(self, "output_format_combo", None).currentText() if getattr(self, "output_format_combo", None) else DEFAULTS["output_format"]),
                "hotkey": _normalize_from_qt(self.hotkey_edit.keySequence()),
                "author": self.author_edit.text().strip() or DEFAULTS["author"],
                "language": self.language_combo.currentText(),
                "style": self.style_combo.currentText(),
                "auto_open": self.auto_open_chk.isChecked(),
                "show_notifications": self.notifications_chk.isChecked(),
                "chapter_words": int(self.chapter_spin.value()),
                # YouTube
                "youtube_lang_1": str(self.yt_lang1.currentData() or "en"),
                "youtube_lang_2": str(self.yt_lang2.currentData() or "es"),
                "youtube_lang_3": str(self.yt_lang3.currentData() or "pt"),
                "youtube_prefer_native": bool(self.yt_prefer_native.isChecked()),
                # LLM
                "llm_provider": str(self.provider_combo.currentData() or DEFAULTS["llm_provider"]),
                "anthropic_model": self.anthropic_model_edit.text().strip() or DEFAULTS["anthropic_model"],
                "anthropic_max_tokens": int(self.anthropic_max_tokens_spin.value()),
                "anthropic_temperature": float(self.anthropic_temperature_spin.value()),
                "anthropic_timeout_seconds": int(self.anthropic_timeout_spin.value()),
                "anthropic_retry_count": int(self.anthropic_retry_spin.value()),
                "anthropic_hotkey": self.anthropic_hotkey_edit.text().strip() or DEFAULTS["anthropic_hotkey"],
            }

            # API key persistence policy
            store_keys = True
            try:
                store_keys = bool(self.store_keys_chk.isChecked())
            except Exception:
                store_keys = True
            cfg["llm_store_keys_in_config"] = store_keys
            if store_keys:
                cfg["anthropic_api_key"] = self.anthropic_key_edit.text().strip()
                cfg["openrouter_api_key"] = self.openrouter_key_edit.text().strip()
            else:
                # Do not persist API keys in config when disabled
                cfg["anthropic_api_key"] = ""
                cfg["openrouter_api_key"] = ""

            # Normalize model/provider coherence to avoid auth/API mismatch
            try:
                provider = (cfg.get("llm_provider", "openrouter") or "").strip().lower()
                model = (cfg.get("anthropic_model", "") or "").strip()
                if provider == "anthropic":
                    # Anthropic provider expects Anthropic model ids without slash
                    if "/" in model:
                        # Map common OpenRouter id to Anthropic alias; fallback to default alias
                        if model.lower() == "anthropic/claude-sonnet-4.5":
                            cfg["anthropic_model"] = "claude-4.5-sonnet"
                        else:
                            cfg["anthropic_model"] = "claude-4.5-sonnet"
                elif provider == "openrouter":
                    # OpenRouter expects provider/model format
                    if "/" not in model:
                        ml = model.lower()
                        if ml in {"claude-4.5-sonnet", "sonnet-4.5", "claude-sonnet-4.5"}:
                            cfg["anthropic_model"] = "anthropic/claude-sonnet-4.5"
            except Exception:
                pass

            # Collect prompts
            prompts: list[dict] = []
            active_idx = 0
            # Determine active from button group if possible
            try:
                active_idx = int(self.prompt_radio_group.checkedId())
            except Exception:
                # Fallback: keep previous
                active_idx = int(self.config.get("llm_prompt_active", 0))
            for i, w in enumerate(self.prompt_widgets):
                name = w["name"].text().strip()
                text = w["text"].toPlainText().strip()
                overrides: dict = {}
                if self.llm_overrides_chk.isChecked():
                    if w["over_model"].text().strip():
                        overrides["model"] = w["over_model"].text().strip()
                    # Always include numeric overrides when toggle is active
                    try:
                        val = int(w["over_maxtok"].value())
                        overrides["max_tokens"] = val
                    except Exception:
                        pass
                    try:
                        overrides["temperature"] = float(w["over_temp"].value())
                    except Exception:
                        pass
                    try:
                        val = int(w["over_timeout"].value())
                        overrides["timeout_seconds"] = val
                    except Exception:
                        pass
                    try:
                        val = int(w["over_retry"].value())
                        overrides["retry_count"] = val
                    except Exception:
                        pass
                prompts.append({"name": name, "text": text, "overrides": overrides})

            cfg["llm_prompts"] = prompts
            cfg["llm_prompt_active"] = max(0, min(4, active_idx))
            cfg["llm_per_prompt_overrides"] = bool(self.llm_overrides_chk.isChecked())
            # Keep legacy single prompt in sync with active prompt (centralized)
            sync_legacy_prompt(cfg)

            # Pre-save validation with surfaced warnings
            warns = self._validate_before_save(cfg)
            if warns:
                try:
                    QMessageBox.warning(self, "Settings — Warnings", "\n".join(warns))
                except Exception:
                    pass

            ok = save_config(cfg)
            if ok:
                QMessageBox.information(self, "Settings Saved", "Configuration saved successfully.")
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
