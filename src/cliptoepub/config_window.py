#!/usr/bin/env python3
"""
Configuration Window for Clipboard to ePub
Uses tkinter for cross-platform GUI
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
from pathlib import Path
import sys
import os
from . import paths as paths
from .llm_config import ensure_llm_config, sync_legacy_prompt
import tempfile


class ConfigWindow:
    """Configuration window for Clipboard to ePub settings"""

    def __init__(self, config_path=None):
        """Initialize the configuration window"""
        self.config_path = config_path or paths.get_config_path()

        # Default configuration
        default_hotkey = "ctrl+shift+e" if sys.platform.startswith("win") else "cmd+shift+e"
        self.default_config = {
            "output_directory": str(paths.get_default_output_dir()),
            "hotkey": default_hotkey,
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
            # Default model for OpenRouter (Sonnet 4.5 – 1M)
            "anthropic_model": "anthropic/claude-sonnet-4.5",
            "anthropic_prompt": "",
            "anthropic_max_tokens": 2048,
            "anthropic_temperature": 0.2,
            "anthropic_timeout_seconds": 60,
            "anthropic_retry_count": 10,
            "anthropic_hotkey": ("ctrl+shift+l" if not sys.platform.startswith("darwin") else "cmd+shift+l"),
            # Provider selection and OpenRouter key
            "llm_provider": "openrouter",
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

        # Load current configuration
        self.config = self.load_config()

        # Create the window
        self.create_window()

    def load_config(self):
        """Load configuration from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    for key, value in self.default_config.items():
                        if key not in config:
                            config[key] = value
                    # Normalize multi-prompt schema
                    ensure_llm_config(config)
                    return config
            except Exception as e:
                print(f"Error loading config: {e}")
                cfg = self.default_config.copy()
                ensure_llm_config(cfg)
                return cfg
        cfg = self.default_config.copy()
        ensure_llm_config(cfg)
        return cfg

    def save_config(self):
        """Save configuration to file"""
        try:
            warnings = []

            # Update config from GUI elements
            self.config["output_directory"] = self.output_var.get()
            # Normalize hotkey string
            self.config["hotkey"] = self._normalize_hotkey(self.hotkey_var.get())
            self.config["author"] = self.author_var.get()
            self.config["language"] = self.language_var.get()
            self.config["style"] = self.style_var.get()
            self.config["auto_open"] = self.auto_open_var.get()
            self.config["show_notifications"] = self.notifications_var.get()

            # Parse chapter words
            try:
                chapter_words = int(self.chapter_words_var.get())
                if chapter_words < 100:
                    chapter_words = 100
                elif chapter_words > 50000:
                    chapter_words = 50000
                self.config["chapter_words"] = chapter_words
            except ValueError:
                self.config["chapter_words"] = 5000

            # LLM settings
            self.config["llm_provider"] = (self.llm_provider_var.get() or self.default_config["llm_provider"]).strip()
            self.config["anthropic_api_key"] = self.anthropic_api_key_var.get().strip()
            self.config["openrouter_api_key"] = self.openrouter_api_key_var.get().strip()
            self.config["anthropic_model"] = self.anthropic_model_var.get().strip() or self.default_config["anthropic_model"]
            # Multi-prompt from UI
            prompts = []
            for i in range(5):
                name = self.llm_name_vars[i].get().strip()
                text = self.llm_text_widgets[i].get("1.0", tk.END).strip()
                overrides = {}
                if bool(self.llm_overrides_var.get()):
                    model = self.llm_over_model_vars[i].get().strip()
                    if model:
                        overrides["model"] = model
                    prompt_label = name or f"Prompt {i + 1}"

                    raw_max = self.llm_over_maxtok_vars[i].get().strip()
                    if raw_max:
                        try:
                            overrides["max_tokens"] = int(raw_max)
                        except ValueError:
                            warnings.append(f"{prompt_label}: max_tokens override is not a valid integer; value ignored.")

                    raw_temp = self.llm_over_temp_vars[i].get().strip()
                    if raw_temp:
                        try:
                            overrides["temperature"] = float(raw_temp)
                        except ValueError:
                            warnings.append(f"{prompt_label}: temperature override is not a valid number; value ignored.")

                    raw_timeout = self.llm_over_timeout_vars[i].get().strip()
                    if raw_timeout:
                        try:
                            overrides["timeout_seconds"] = int(raw_timeout)
                        except ValueError:
                            warnings.append(f"{prompt_label}: timeout_seconds override is not a valid integer; value ignored.")

                    raw_retry = self.llm_over_retry_vars[i].get().strip()
                    if raw_retry:
                        try:
                            overrides["retry_count"] = int(raw_retry)
                        except ValueError:
                            warnings.append(f"{prompt_label}: retry_count override is not a valid integer; value ignored.")

                prompts.append({"name": name, "text": text, "overrides": overrides})
            self.config["llm_prompts"] = prompts
            self.config["llm_prompt_active"] = int(self.llm_active_var.get())
            self.config["llm_per_prompt_overrides"] = bool(self.llm_overrides_var.get())
            sync_legacy_prompt(self.config)
            try:
                self.config["anthropic_max_tokens"] = int(self.anthropic_max_tokens_var.get())
            except ValueError:
                self.config["anthropic_max_tokens"] = 2048
            try:
                self.config["anthropic_temperature"] = float(self.anthropic_temperature_var.get())
            except ValueError:
                self.config["anthropic_temperature"] = 0.2
            try:
                self.config["anthropic_timeout_seconds"] = int(self.anthropic_timeout_seconds_var.get())
            except ValueError:
                self.config["anthropic_timeout_seconds"] = 60
            try:
                self.config["anthropic_retry_count"] = int(self.anthropic_retry_count_var.get())
            except ValueError:
                self.config["anthropic_retry_count"] = 10
            self.config["anthropic_hotkey"] = (self.anthropic_hotkey_var.get().strip() or self.default_config["anthropic_hotkey"]).lower()

            # Normalize model/provider coherence to avoid auth/API mismatch
            try:
                provider = (self.config.get("llm_provider", "openrouter") or "").strip().lower()
                model = (self.config.get("anthropic_model", "") or "").strip()
                if provider == "anthropic":
                    if "/" in model:
                        if model.lower() == "anthropic/claude-sonnet-4.5":
                            self.config["anthropic_model"] = "claude-4.5-sonnet"
                        else:
                            self.config["anthropic_model"] = "claude-4.5-sonnet"
                elif provider == "openrouter":
                    if "/" not in model:
                        ml = model.lower()
                        if ml in {"claude-4.5-sonnet", "sonnet-4.5", "claude-sonnet-4.5"}:
                            self.config["anthropic_model"] = "anthropic/claude-sonnet-4.5"
            except Exception:
                pass

            # YouTube settings
            def _to_code(val: str, default: str) -> str:
                s = (val or "").strip()
                if "–" in s:
                    s = s.split("–", 1)[0].strip()
                elif "-" in s:
                    s = s.split("-", 1)[0].strip()
                return s or default

            self.config["youtube_lang_1"] = _to_code(self.yt_lang1_var.get(), "en")
            self.config["youtube_lang_2"] = _to_code(self.yt_lang2_var.get(), "es")
            self.config["youtube_lang_3"] = _to_code(self.yt_lang3_var.get(), "pt")
            self.config["youtube_prefer_native"] = bool(self.yt_prefer_native_var.get())

            # Create preferences directory if needed
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Write config file
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)

            # Surface non-blocking warnings relevant to runtime behavior
            try:
                provider = (self.config.get("llm_provider", "openrouter") or "").strip().lower()
                if provider == "anthropic":
                    if not (self.config.get("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")):
                        warnings.append("Anthropic provider selected but no API key configured.")
                elif provider == "openrouter":
                    if not (self.config.get("openrouter_api_key") or os.getenv("OPENROUTER_API_KEY")):
                        warnings.append("OpenRouter provider selected but no API key configured.")
            except Exception:
                pass

            # Output directory write check
            try:
                out_dir = Path(self.config.get("output_directory") or "").expanduser()
                out_dir.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=str(out_dir), prefix="cte_chk_", delete=True):
                    pass
            except Exception:
                warnings.append("Output directory may not be writable. ePubs could fail to save.")

            if warnings:
                try:
                    messagebox.showwarning("Settings — Warnings", "\n".join(warnings))
                except Exception:
                    pass

            messagebox.showinfo("Success", "Configuration saved successfully.")
            return True

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration:\n{e}")
            return False

    def browse_folder(self):
        """Open folder browser dialog"""
        folder = filedialog.askdirectory(
            initialdir=self.output_var.get(),
            title="Select Output Directory"
        )
        if folder:
            self.output_var.set(folder)

    def create_window(self):
        """Create the configuration window UI"""
        self.root = tk.Tk()
        self.root.title("Clipboard to ePub - Settings")
        self.root.geometry("640x720")
        self.root.resizable(True, True)

        # Try to use macOS-friendly theme and set window icon
        try:
            icon_png = (Path(__file__).resolve().parent.parent / "resources" / "icon_64.png")
            if icon_png.exists():
                self.root.iconphoto(True, tk.PhotoImage(file=str(icon_png)))
        except (tk.TclError, OSError) as e:
            # Icon loading failed - not critical
            pass

        # Configure style
        style = ttk.Style()
        try:
            # Prefer native macOS look if available
            style.theme_use('aqua')
        except tk.TclError:
            try:
                style.theme_use('clam')
            except tk.TclError:
                style.theme_use('default')

        # Create a scrollable content area to avoid clipping on small screens
        class ScrollableFrame(ttk.Frame):
            def __init__(self, container, *args, **kwargs):
                super().__init__(container, *args, **kwargs)
                self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
                self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
                self.canvas.configure(yscrollcommand=self.vsb.set)
                self.inner = ttk.Frame(self.canvas)
                self.inner.bind(
                    "<Configure>",
                    lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
                )
                self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
                self.canvas.pack(side="left", fill="both", expand=True)
                self.vsb.pack(side="right", fill="y")

        scroll = ScrollableFrame(self.root)
        scroll.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Main frame inside the scrollable area
        main_frame = ttk.Frame(scroll.inner, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Clipboard to ePub Settings",
            font=('System', 18, 'bold')
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # Output Directory
        ttk.Label(main_frame, text="Output Directory:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.output_var = tk.StringVar(value=self.config["output_directory"])
        output_frame = ttk.Frame(main_frame)
        output_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        ttk.Entry(output_frame, textvariable=self.output_var, width=40).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(output_frame, text="Browse...", command=self.browse_folder).pack(side=tk.LEFT)

        # Hotkey
        ttk.Label(main_frame, text="Capture Hotkey:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.hotkey_var = tk.StringVar(value=self.config.get("hotkey", self.default_config["hotkey"]))
        hotkey_frame = ttk.Frame(main_frame)
        hotkey_frame.grid(row=3, column=1, sticky=(tk.W), pady=5)
        self.hotkey_entry = ttk.Entry(hotkey_frame, textvariable=self.hotkey_var, width=30)
        self.hotkey_entry.pack(side=tk.LEFT)
        self._recording_hotkey = False
        def _toggle_record():
            if not self._recording_hotkey:
                self._start_hotkey_record()
                record_btn.configure(text="Stop")
            else:
                self._stop_hotkey_record()
                record_btn.configure(text="Record")
        record_btn = ttk.Button(hotkey_frame, text="Record", command=_toggle_record)
        record_btn.pack(side=tk.LEFT, padx=(5, 0))
        def _reset_hotkey():
            self.hotkey_var.set(self.default_config["hotkey"])
        ttk.Button(hotkey_frame, text="Reset", command=_reset_hotkey).pack(side=tk.LEFT, padx=(5, 0))

        # Author
        ttk.Label(main_frame, text="Default Author:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.author_var = tk.StringVar(value=self.config["author"])
        ttk.Entry(main_frame, textvariable=self.author_var, width=30).grid(row=4, column=1, sticky=tk.W, pady=5)

        # Language
        ttk.Label(main_frame, text="Language:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.language_var = tk.StringVar(value=self.config["language"])
        language_combo = ttk.Combobox(
            main_frame,
            textvariable=self.language_var,
            values=["en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh", "ko"],
            width=27,
            state="readonly"
        )
        language_combo.grid(row=5, column=1, sticky=tk.W, pady=5)

        # Style (populate from templates dir if present)
        ttk.Label(main_frame, text="CSS Style:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.style_var = tk.StringVar(value=self.config["style"])
        styles = ["default", "minimal", "modern"]
        try:
            templates_dir = Path(__file__).resolve().parent.parent / "templates"
            if templates_dir.exists():
                found = [p.stem for p in templates_dir.glob("*.css")]
                if found:
                    styles = sorted(list({*styles, *found}))
        except (OSError, RuntimeError) as e:
            # Template directory not accessible - use defaults
            pass
        style_combo = ttk.Combobox(
            main_frame,
            textvariable=self.style_var,
            values=styles,
            width=27,
            state="readonly"
        )
        style_combo.grid(row=6, column=1, sticky=tk.W, pady=5)

        # Chapter Words
        ttk.Label(main_frame, text="Words per Chapter:").grid(row=7, column=0, sticky=tk.W, pady=5)
        self.chapter_words_var = tk.StringVar(value=str(self.config["chapter_words"]))
        chapter_frame = ttk.Frame(main_frame)
        chapter_frame.grid(row=7, column=1, sticky=tk.W, pady=5)
        ttk.Entry(chapter_frame, textvariable=self.chapter_words_var, width=10).pack(side=tk.LEFT)
        ttk.Label(chapter_frame, text="(100-50000)").pack(side=tk.LEFT, padx=(5, 0))

        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=15)

        # Checkboxes
        self.auto_open_var = tk.BooleanVar(value=self.config["auto_open"])
        ttk.Checkbutton(
            main_frame,
            text="Auto-open ePub files after creation",
            variable=self.auto_open_var
        ).grid(row=9, column=0, columnspan=2, sticky=tk.W, pady=5)

        self.notifications_var = tk.BooleanVar(value=self.config["show_notifications"])
        ttk.Checkbutton(
            main_frame,
            text="Show notifications",
            variable=self.notifications_var
        ).grid(row=10, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(row=11, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=15)

        # YouTube subtitles
        yt_frame = ttk.LabelFrame(main_frame, text="YouTube Subtitles", padding="10")
        yt_frame.grid(row=12, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        langs = [
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
        def _lang_values():
            return [f"{c} – {n}" for c, n in langs]
        # Helper to map display -> code
        disp_to_code = {f"{c} – {n}": c for c, n in langs}
        ttk.Label(yt_frame, text="Preferred language 1:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.yt_lang1_var = tk.StringVar()
        yt1 = ttk.Combobox(yt_frame, textvariable=self.yt_lang1_var, values=_lang_values(), width=32, state="readonly")
        yt1.grid(row=0, column=1, sticky=tk.W, pady=5)
        ttk.Label(yt_frame, text="Preferred language 2:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.yt_lang2_var = tk.StringVar()
        yt2 = ttk.Combobox(yt_frame, textvariable=self.yt_lang2_var, values=_lang_values(), width=32, state="readonly")
        yt2.grid(row=1, column=1, sticky=tk.W, pady=5)
        ttk.Label(yt_frame, text="Preferred language 3:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.yt_lang3_var = tk.StringVar()
        yt3 = ttk.Combobox(yt_frame, textvariable=self.yt_lang3_var, values=_lang_values(), width=32, state="readonly")
        yt3.grid(row=2, column=1, sticky=tk.W, pady=5)
        # Initialize selections
        def _set_lang(var: tk.StringVar, code: str):
            for disp, c in disp_to_code.items():
                if c == (code or "").strip().lower():
                    var.set(disp)
                    return
        _set_lang(self.yt_lang1_var, self.config.get("youtube_lang_1", "en"))
        _set_lang(self.yt_lang2_var, self.config.get("youtube_lang_2", "es"))
        _set_lang(self.yt_lang3_var, self.config.get("youtube_lang_3", "pt"))
        self.yt_prefer_native_var = tk.BooleanVar(value=bool(self.config.get("youtube_prefer_native", True)))
        ttk.Checkbutton(yt_frame, text="Prefer native subtitles; fallback to auto-generated", variable=self.yt_prefer_native_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)

        # LLM settings
        llm_frame = ttk.LabelFrame(main_frame, text="LLM", padding="10")
        llm_frame.grid(row=14, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

        ttk.Label(llm_frame, text="API Key:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.anthropic_api_key_var = tk.StringVar(value=self.config.get("anthropic_api_key", ""))
        ttk.Entry(llm_frame, textvariable=self.anthropic_api_key_var, show="*", width=40).grid(row=0, column=1, sticky=tk.W)

        # OpenRouter key (optional; used if provider=openrouter)
        ttk.Label(llm_frame, text="OpenRouter Key:").grid(row=0, column=2, sticky=tk.W, pady=5, padx=(10, 0))
        self.openrouter_api_key_var = tk.StringVar(value=self.config.get("openrouter_api_key", ""))
        ttk.Entry(llm_frame, textvariable=self.openrouter_api_key_var, show="*", width=30).grid(row=0, column=3, sticky=tk.W)

        ttk.Label(llm_frame, text="Model:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.anthropic_model_var = tk.StringVar(value=self.config.get("anthropic_model", self.default_config["anthropic_model"]))
        ttk.Entry(llm_frame, textvariable=self.anthropic_model_var, width=40).grid(row=1, column=1, sticky=tk.W)
        ttk.Label(llm_frame, text="e.g., claude-4.5-sonnet or anthropic/claude-sonnet-4.5", foreground="#555").grid(row=1, column=1, sticky=tk.E, padx=(0,4))

        # Model preset (common ids); updates model and provider
        ttk.Label(llm_frame, text="Preset:").grid(row=1, column=2, sticky=tk.W, padx=(10, 0))
        self.model_preset_var = tk.StringVar(value="")
        preset_combo = ttk.Combobox(
            llm_frame,
            textvariable=self.model_preset_var,
            values=[
                "— Select preset —",
                "Sonnet 4.5 – OpenRouter (1M)",
                "Sonnet 4.5 – Anthropic",
                "Mistral Medium 3.1 – OpenRouter (128k)",
            ],
            width=32,
            state="readonly",
        )
        preset_combo.grid(row=1, column=3, sticky=tk.W)

        def _on_preset_change(*_):
            label = (self.model_preset_var.get() or "").lower()
            if "mistral" in label:
                self.anthropic_model_var.set("mistralai/mistral-medium-3.1")
                self.llm_provider_var.set("openrouter")
            elif "openrouter" in label and "sonnet" in label:
                self.anthropic_model_var.set("anthropic/claude-sonnet-4.5")
                self.llm_provider_var.set("openrouter")
            elif "anthropic" in label and "sonnet" in label:
                self.anthropic_model_var.set("claude-4.5-sonnet")
                self.llm_provider_var.set("anthropic")
            else:
                return
        try:
            if hasattr(self.model_preset_var, 'trace_add'):
                self.model_preset_var.trace_add('write', _on_preset_change)
            else:
                self.model_preset_var.trace('w', _on_preset_change)
        except Exception:
            pass

        ttk.Label(llm_frame, text="LLM Hotkey:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.anthropic_hotkey_var = tk.StringVar(value=self.config.get("anthropic_hotkey", self.default_config["anthropic_hotkey"]))
        ttk.Entry(llm_frame, textvariable=self.anthropic_hotkey_var, width=20).grid(row=2, column=1, sticky=tk.W)

        # Custom prompts group
        prompts_group = ttk.LabelFrame(llm_frame, text="Custom Prompts", padding="6")
        prompts_group.grid(row=3, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=6)

        # Toggle per-prompt overrides
        self.llm_overrides_var = tk.IntVar(value=1 if self.config.get("llm_per_prompt_overrides", False) else 0)
        ttk.Checkbutton(prompts_group, text="Enable per-prompt overrides", variable=self.llm_overrides_var, command=self._sync_prompt_overrides_state).grid(row=0, column=0, columnspan=4, sticky=tk.W)

        # Active prompt radio and editors
        self.llm_active_var = tk.IntVar(value=int(self.config.get("llm_prompt_active", 0)))
        self.llm_name_vars = []
        self.llm_text_widgets = []
        self.llm_over_model_vars = []
        self.llm_over_maxtok_vars = []
        self.llm_over_temp_vars = []
        self.llm_over_timeout_vars = []
        self.llm_over_retry_vars = []

        prompts = self.config.get("llm_prompts", [])
        for i in range(5):
            row_base = 1 + i * 3
            item = prompts[i] if i < len(prompts) else {"name": "", "text": "", "overrides": {}}
            # Row: radio + name
            ttk.Radiobutton(prompts_group, text=f"Use with Hotkey", variable=self.llm_active_var, value=i).grid(row=row_base, column=0, sticky=tk.W)
            name_var = tk.StringVar(value=item.get("name", ""))
            self.llm_name_vars.append(name_var)
            ttk.Label(prompts_group, text="Name:").grid(row=row_base, column=1, sticky=tk.W)
            ttk.Entry(prompts_group, textvariable=name_var, width=24).grid(row=row_base, column=2, sticky=tk.W)

            # Prompt text
            ttk.Label(prompts_group, text="Prompt:").grid(row=row_base+1, column=1, sticky=tk.NW)
            text_widget = tk.Text(prompts_group, height=4, width=48)
            text_widget.insert("1.0", item.get("text", ""))
            text_widget.grid(row=row_base+1, column=2, sticky=tk.W)
            self.llm_text_widgets.append(text_widget)

            # Overrides
            ov = item.get("overrides", {}) or {}
            ttk.Label(prompts_group, text="Overrides:").grid(row=row_base+2, column=1, sticky=tk.W)
            over_frame = ttk.Frame(prompts_group)
            over_frame.grid(row=row_base+2, column=2, sticky=tk.W)
            # Model
            ttk.Label(over_frame, text="Model").grid(row=0, column=0, sticky=tk.W)
            over_model_var = tk.StringVar(value=ov.get("model", ""))
            ttk.Entry(over_frame, textvariable=over_model_var, width=28).grid(row=0, column=1, sticky=tk.W)
            # Max tokens
            ttk.Label(over_frame, text="Max tokens").grid(row=0, column=2, sticky=tk.W, padx=(8,0))
            over_maxtok_var = tk.StringVar(value=str(ov.get("max_tokens", "")))
            ttk.Entry(over_frame, textvariable=over_maxtok_var, width=8).grid(row=0, column=3, sticky=tk.W)
            # Temperature
            ttk.Label(over_frame, text="Temp").grid(row=0, column=4, sticky=tk.W, padx=(8,0))
            over_temp_var = tk.StringVar(value=str(ov.get("temperature", "")))
            ttk.Entry(over_frame, textvariable=over_temp_var, width=6).grid(row=0, column=5, sticky=tk.W)
            # Timeout
            ttk.Label(over_frame, text="Timeout(s)").grid(row=0, column=6, sticky=tk.W, padx=(8,0))
            over_timeout_var = tk.StringVar(value=str(ov.get("timeout_seconds", "")))
            ttk.Entry(over_frame, textvariable=over_timeout_var, width=6).grid(row=0, column=7, sticky=tk.W)
            # Retry
            ttk.Label(over_frame, text="Retries").grid(row=0, column=8, sticky=tk.W, padx=(8,0))
            over_retry_var = tk.StringVar(value=str(ov.get("retry_count", "")))
            ttk.Entry(over_frame, textvariable=over_retry_var, width=6).grid(row=0, column=9, sticky=tk.W)

            self.llm_over_model_vars.append(over_model_var)
            self.llm_over_maxtok_vars.append(over_maxtok_var)
            self.llm_over_temp_vars.append(over_temp_var)
            self.llm_over_timeout_vars.append(over_timeout_var)
            self.llm_over_retry_vars.append(over_retry_var)

        self._sync_prompt_overrides_state()

        # Numeric params
        ttk.Label(llm_frame, text="Max Tokens:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.anthropic_max_tokens_var = tk.StringVar(value=str(self.config.get("anthropic_max_tokens", 2048)))
        ttk.Entry(llm_frame, textvariable=self.anthropic_max_tokens_var, width=10).grid(row=4, column=1, sticky=tk.W)
        ttk.Label(llm_frame, text="Output token cap; not context window", foreground="#555").grid(row=4, column=1, sticky=tk.E, padx=(0,4))

        # Provider hint for Sonnet 4.5 (OpenRouter)
        ttk.Label(llm_frame, text="For Sonnet 4.5 (1M context) use OpenRouter id 'anthropic/claude-sonnet-4.5' and set OPENROUTER_API_KEY.", foreground="#555").grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(2, 2))

        ttk.Label(llm_frame, text="Temperature:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.anthropic_temperature_var = tk.StringVar(value=str(self.config.get("anthropic_temperature", 0.2)))
        ttk.Entry(llm_frame, textvariable=self.anthropic_temperature_var, width=10).grid(row=5, column=1, sticky=tk.W)

        ttk.Label(llm_frame, text="Timeout (s):").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.anthropic_timeout_seconds_var = tk.StringVar(value=str(self.config.get("anthropic_timeout_seconds", 60)))
        ttk.Entry(llm_frame, textvariable=self.anthropic_timeout_seconds_var, width=10).grid(row=6, column=1, sticky=tk.W)

        ttk.Label(llm_frame, text="Retries:").grid(row=7, column=0, sticky=tk.W, pady=5)
        self.anthropic_retry_count_var = tk.StringVar(value=str(self.config.get("anthropic_retry_count", 10)))
        ttk.Entry(llm_frame, textvariable=self.anthropic_retry_count_var, width=10).grid(row=7, column=1, sticky=tk.W)

        # Provider selection
        ttk.Label(llm_frame, text="Provider:").grid(row=9, column=0, sticky=tk.W, pady=5)
        self.llm_provider_var = tk.StringVar(value=self.config.get("llm_provider", self.default_config.get("llm_provider", "anthropic")))
        provider_combo = ttk.Combobox(
            llm_frame,
            textvariable=self.llm_provider_var,
            values=["anthropic", "openrouter"],
            width=20,
            state="readonly"
        )
        provider_combo.grid(row=9, column=1, sticky=tk.W)

        def _test_llm():
            try:
                from .llm.base import LLMRequest
                from .llm.anthropic import AnthropicProvider
                from .llm.openrouter import OpenRouterProvider

                provider = (self.llm_provider_var.get() or "anthropic").strip().lower()
                if provider == "openrouter":
                    api_key = self.openrouter_api_key_var.get().strip() or os.environ.get("OPENROUTER_API_KEY", "")
                    model = self.anthropic_model_var.get().strip() or "anthropic/claude-sonnet-4.5"
                    llm_provider = OpenRouterProvider()
                else:
                    api_key = self.anthropic_api_key_var.get().strip() or os.environ.get("ANTHROPIC_API_KEY", "")
                    model = self.anthropic_model_var.get().strip() or self.default_config["anthropic_model"]
                    llm_provider = AnthropicProvider()

                # Use active prompt text
                idx = int(self.llm_active_var.get() or 0)
                if 0 <= idx < len(self.llm_text_widgets):
                    prompt = self.llm_text_widgets[idx].get("1.0", tk.END).strip() or "Return the input as Markdown."
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
                preview = "\n".join((md or "").strip().splitlines()[0:3])
                messagebox.showinfo("LLM OK", preview or "Received response")
            except Exception as e:
                messagebox.showerror("LLM Error", str(e))

        ttk.Button(llm_frame, text="Test Connection", command=_test_llm).grid(row=8, column=0, pady=6, sticky=tk.W)

        # Auto-timeout from tokens with manual override support
        self._timeout_user_edited = False
        self._updating_timeout_programmatically = False
        self._initial_tokens_value = self.anthropic_max_tokens_var.get()

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

        def _on_timeout_user_change(*_):
            if self._updating_timeout_programmatically:
                return
            self._timeout_user_edited = True

        def _on_tokens_change(*_):
            # Only auto-adjust when user actually changed tokens after opening
            new_val = self.anthropic_max_tokens_var.get()
            if new_val == self._initial_tokens_value:
                return
            if self._timeout_user_edited:
                return
            try:
                rec = _recommended_timeout(int(new_val))
            except Exception:
                return
            self._updating_timeout_programmatically = True
            try:
                self.anthropic_timeout_seconds_var.set(str(rec))
            finally:
                self._updating_timeout_programmatically = False
            # Update baseline so subsequent changes keep auto-adjusting
            self._initial_tokens_value = new_val

        def _reset_timeout():
            try:
                tokens = int(self.anthropic_max_tokens_var.get())
            except Exception:
                tokens = 0
            rec = _recommended_timeout(tokens)
            self._updating_timeout_programmatically = True
            try:
                self.anthropic_timeout_seconds_var.set(str(rec))
            finally:
                self._updating_timeout_programmatically = False
            # Re-enable auto updates on future token changes
            self._timeout_user_edited = False

        ttk.Button(llm_frame, text="Reset Timeout (Recommended)", command=_reset_timeout).grid(row=8, column=1, pady=6, sticky=tk.W)

        try:
            # Trace user edits on timeout
            if hasattr(self.anthropic_timeout_seconds_var, 'trace_add'):
                self.anthropic_timeout_seconds_var.trace_add('write', _on_timeout_user_change)
            else:
                self.anthropic_timeout_seconds_var.trace('w', _on_timeout_user_change)
            # Trace token changes
            if hasattr(self.anthropic_max_tokens_var, 'trace_add'):
                self.anthropic_max_tokens_var.trace_add('write', _on_tokens_change)
            else:
                self.anthropic_max_tokens_var.trace('w', _on_tokens_change)
        except Exception:
            pass

        # Info section
        info_frame = ttk.LabelFrame(main_frame, text="Info", padding="10")
        info_frame.grid(row=13, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

        info_text = f"Current Hotkey: {self.config.get('hotkey', self.default_config['hotkey']).upper()}\n"
        info_text += f"Config Location: {self.config_path}\n"
        info_text += f"ePubs Saved To: {self.config['output_directory']}"

        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor=tk.W)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=14, column=0, columnspan=2, pady=(20, 0))

        ttk.Button(
            button_frame,
            text="Save",
            command=self.save_and_close,
            width=15
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.root.quit,
            width=15
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Reset Defaults",
            command=self.reset_defaults,
            width=15
        ).pack(side=tk.LEFT, padx=5)

    def save_and_close(self):
        """Save configuration and close window"""
        if self.save_config():
            self.root.quit()

    def reset_defaults(self):
        """Reset all settings to defaults"""
        if messagebox.askyesno("Reset Defaults", "Are you sure you want to reset all settings to defaults?"):
            self.output_var.set(self.default_config["output_directory"])
            self.hotkey_var.set(self.default_config["hotkey"])
            self.author_var.set(self.default_config["author"])
            self.language_var.set(self.default_config["language"])
            self.style_var.set(self.default_config["style"])
            self.auto_open_var.set(self.default_config["auto_open"])
            self.notifications_var.set(self.default_config["show_notifications"])
            self.chapter_words_var.set(str(self.default_config["chapter_words"]))
            self.anthropic_api_key_var.set("")
            try:
                self.llm_provider_var.set(self.default_config.get("llm_provider", "anthropic"))
                self.openrouter_api_key_var.set("")
            except Exception:
                pass
            self.anthropic_model_var.set(self.default_config["anthropic_model"])
            # Reset prompts
            for i in range(5):
                try:
                    self.llm_name_vars[i].set("")
                    self.llm_text_widgets[i].delete("1.0", tk.END)
                    self.llm_over_model_vars[i].set("")
                    self.llm_over_maxtok_vars[i].set("")
                    self.llm_over_temp_vars[i].set("")
                    self.llm_over_timeout_vars[i].set("")
                    self.llm_over_retry_vars[i].set("")
                except Exception:
                    pass
            self.llm_active_var.set(0)
            self.llm_overrides_var.set(0)
            self.anthropic_max_tokens_var.set(str(self.default_config["anthropic_max_tokens"]))
            self.anthropic_temperature_var.set(str(self.default_config["anthropic_temperature"]))
            self.anthropic_timeout_seconds_var.set(str(self.default_config["anthropic_timeout_seconds"]))
            self.anthropic_retry_count_var.set(str(self.default_config["anthropic_retry_count"]))
            self.anthropic_hotkey_var.set(self.default_config["anthropic_hotkey"]) 

    # ---- Hotkey capture helpers ----
    def _start_hotkey_record(self):
        self._recording_hotkey = True
        # Bind on the toplevel so it catches modifiers too
        self.root.bind("<KeyPress>", self._on_hotkey_keypress)
        self.root.bind("<KeyRelease>", self._on_hotkey_keyrelease)
        # Visual cue
        try:
            self.hotkey_entry.configure(foreground="#004085")
        except Exception:
            pass

    def _stop_hotkey_record(self):
        self._recording_hotkey = False
        try:
            self.root.unbind("<KeyPress>")
            self.root.unbind("<KeyRelease>")
            self.hotkey_entry.configure(foreground="black")
        except Exception:
            pass

    def _on_hotkey_keyrelease(self, event):
        # No-op; we compute on press
        pass

    def _on_hotkey_keypress(self, event):
        if not self._recording_hotkey:
            return
        # Build modifiers from state
        state = int(getattr(event, 'state', 0))
        mods = []
        # Shift
        if state & 0x0001:
            mods.append("shift")
        # Control
        if state & 0x0004:
            mods.append("ctrl")
        # Alt/Option
        if state & 0x0008:
            mods.append("alt")
        # Meta/Command – best-effort masks used by Tk across platforms
        if sys.platform == 'darwin':
            if state & 0x0010 or state & 0x0040:
                mods.append("cmd")
        else:
            # On other platforms, Meta may map to 0x0040
            if state & 0x0040:
                mods.append("cmd")

        # Determine main key
        keysym = getattr(event, 'keysym', '')
        key = None
        if len(keysym) == 1 and keysym.isprintable():
            key = keysym.lower()
        elif keysym and keysym.upper().startswith('F') and keysym[1:].isdigit():
            key = keysym.lower()  # e.g., 'f5'
        elif keysym in ("space", "tab", "return", "enter", "backspace", "minus", "equal", "bracketleft", "bracketright", "semicolon", "apostrophe", "comma", "period", "slash"):
            key = keysym.lower()

        if key is None:
            # Update entry with modifiers while waiting for a main key
            self.hotkey_var.set("+".join(mods))
            return

        parts = mods + [key]
        # Ensure at least one modifier
        if not mods:
            # Default to ctrl on non-mac, cmd on mac if none pressed
            if sys.platform == 'darwin':
                parts = ["cmd", key]
            else:
                parts = ["ctrl", key]
        self.hotkey_var.set("+".join(parts))
        # Stop recording after a complete sequence
        self._stop_hotkey_record()

    def _normalize_hotkey(self, text: str) -> str:
        if not text:
            return self.default_config["hotkey"]
        parts = [p.strip().lower() for p in text.split("+") if p.strip()]
        out = []
        for p in parts:
            if p in ("control", "ctrl"):
                out.append("ctrl")
            elif p in ("command", "meta", "cmd"):
                out.append("cmd")
            elif p in ("shift",):
                out.append("shift")
            elif p in ("alt", "option"):
                out.append("alt")
            else:
                out.append(p)
        return "+".join(out)

    # LLM prompt normalization is centralized in llm_config.ensure_llm_config

    def _sync_prompt_overrides_state(self):
        # Tk simple UI: fields remain editable; checkbox acts as logical toggle captured on save
        pass

    def run(self):
        """Run the configuration window"""
        self.root.mainloop()


def main():
    """Main entry point"""
    # Check if config path is provided
    config_path = None
    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1])

    # Create and run configuration window
    window = ConfigWindow(config_path)
    window.run()


if __name__ == "__main__":
    main()
