#!/usr/bin/env python3
from __future__ import annotations
"""
ClipToEpub - Menu Bar Application
Unified converter backend
"""

# Import compatibility patch for 'imp' module first
from . import imp_patch  # noqa: F401

import rumps
import asyncio
import os
import sys
import json
import threading
import subprocess
from pathlib import Path
from datetime import datetime
import pync

from .converter import ClipboardToEpubConverter
from . import paths as paths
from .hotkeys import parse_hotkey_string
from .llm_config import (
    ensure_llm_config,
    get_prompt_menu_items,
    resolve_prompt_params,
    build_overrides_for_prompt,
)
from .errors import ErrorEvent


def _warm_mac_keyboard_apis():
    if sys.platform != "darwin":
        return
    try:
        import HIServices
        _ = HIServices.AXIsProcessTrusted
    except Exception:
        pass
    try:
        import Quartz
        _ = Quartz.CFRunLoopAddSource
    except Exception:
        pass


class ClipToEpubApp(rumps.App):
    """Menu bar application for ClipToEpub"""

    def __init__(self):
        # Prefer app icon over emoji to look more native
        try:
            icon_path = (Path(__file__).resolve().parent.parent / "resources" / "icon.png")
        except (OSError, RuntimeError) as e:
            print(f"Warning: Could not resolve icon path: {e}")
            icon_path = None

        super(ClipToEpubApp, self).__init__(
            "ClipToEpub",
            icon=str(icon_path) if icon_path and icon_path.exists() else None,
            title=None,  # No inline text, icon only
            quit_button=None  # Custom quit button
        )

        # Configuration file path (cross-platform)
        # Also triggers Windows legacy migrations if applicable
        try:
            paths.migrate_legacy_paths()
        except (OSError, IOError) as e:
            print(f"Warning: Could not migrate legacy paths: {e}")
            # Non-critical error - continue with defaults
        self.config_path = paths.get_config_path()

        # Default configuration
        self.config = {
            "output_directory": str(paths.get_default_output_dir()),
            "hotkey": "cmd+shift+e",
            "author": "Unknown Author",
            "language": "en",
            "style": "default",
            "auto_open": False,
            "show_notifications": True,
            "chapter_words": 5000,
            # Concurrency
            "max_async_workers": 3,
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
            "anthropic_hotkey": "cmd+shift+l",
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

        # Load existing configuration
        self.load_config()
        ensure_llm_config(self.config)

        _warm_mac_keyboard_apis()

        # Initialize converter
        self.converter = None
        self.init_converter()

        # Setup menu items
        self.setup_menu()

        # Start converter in background thread (deferred to avoid early event taps)
        self.converter_thread = None
        try:
            self._call_on_main_thread_once(0.2, self.start_converter)
        except Exception as e:
            print(f"Converter schedule error: {e}")

        # Setup LLM hotkey listener
        self.llm_listener = None
        self.llm_current_keys = set()
        # Defer LLM hotkey creation until the app event loop is running
        # to avoid macOS Abort trap crashes from early event taps.
        try:
            self._call_on_main_thread_once(0.3, self._setup_llm_hotkey)
        except Exception as e:
            print(f"LLM hotkey schedule error: {e}")

        # Spinner/activity in menubar
        self._spinner_frames = ['|', '/', '-', '\\']
        self._spinner_idx = 0
        self._activity_timer = rumps.Timer(self._activity_tick, 0.3)
        try:
            self._activity_timer.start()
        except Exception as e:
            print(f"Activity timer error: {e}")

    def _call_on_main_thread_once(self, delay_seconds, func):
        """Schedule a one-shot call on the rumps main loop thread."""
        try:
            def _wrapper(timer):
                try:
                    func()
                finally:
                    try:
                        timer.stop()
                    except Exception:
                        pass
            rumps.Timer(_wrapper, delay_seconds).start()
        except Exception as e:
            print(f"One-shot schedule error: {e}")

    def load_config(self):
        """Load configuration from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
            except Exception as e:
                print(f"Error loading config: {e}")
        # Normalize new keys
        ensure_llm_config(self.config)

    # LLM prompt normalization is centralized in llm_config.ensure_llm_config

    def save_config(self):
        """Save configuration to file"""
        try:
            # Create preferences directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)

            if self.config["show_notifications"]:
                self.notify("Configuration Saved", "Settings have been updated")
        except Exception as e:
            print(f"Error saving config: {e}")
            self.notify("Error", f"Failed to save configuration: {e}")

    def init_converter(self):
        """Initialize the converter with current configuration"""
        try:
            # Parse hotkey string into pynput combo for accuracy
            hotkey_combo = parse_hotkey_string(self.config.get("hotkey"))

            self.converter = ClipboardToEpubConverter(
                output_dir=self.config["output_directory"],
                default_author=self.config["author"],
                default_language=self.config["language"],
                default_style=self.config["style"],
                chapter_words=self.config["chapter_words"],
                max_async_workers=int(self.config.get("max_async_workers", 3)),
                hotkey_combo=hotkey_combo,
                # YouTube + LLM config
                youtube_langs=[
                    str(self.config.get("youtube_lang_1", "en")),
                    str(self.config.get("youtube_lang_2", "es")),
                    str(self.config.get("youtube_lang_3", "pt")),
                ],
                youtube_prefer_native=bool(self.config.get("youtube_prefer_native", True)),
                llm_provider=str(self.config.get("llm_provider", "openrouter")),
                anthropic_api_key=str(self.config.get("anthropic_api_key", "")),
                openrouter_api_key=str(self.config.get("openrouter_api_key", "")),
                anthropic_model=str(self.config.get("anthropic_model", "anthropic/claude-sonnet-4.5")),
                anthropic_prompt=str(self.config.get("anthropic_prompt", "")),
                anthropic_max_tokens=int(self.config.get("anthropic_max_tokens", 2048)),
                anthropic_temperature=float(self.config.get("anthropic_temperature", 0.2)),
                anthropic_timeout_seconds=int(self.config.get("anthropic_timeout_seconds", 60)),
                anthropic_retry_count=int(self.config.get("anthropic_retry_count", 10)),
            )
        except Exception as e:
            print(f"Error initializing converter: {e}")
            self.notify("Error", f"Failed to initialize converter: {e}")

    def setup_menu(self):
        """Setup menu items"""
        # Convert now button
        self.activity_item = rumps.MenuItem("Activity: Idle", callback=None)
        # Build LLM items as first-level entries
        llm_items: list = []
        try:
            for idx, label in get_prompt_menu_items(self.config):
                item = rumps.MenuItem(f"LLM - {label}", callback=(lambda sender, i=idx: self.convert_with_llm(None, i)))
                llm_items.append(item)
        except Exception as e:
            print(f"LLM menu build error: {e}")

        self.menu = [
            rumps.MenuItem("Convert Now", callback=self.convert_now),
            *llm_items,
            self.activity_item,
            None,  # Separator
            rumps.MenuItem("Open ePubs Folder", callback=self.open_folder),
            rumps.MenuItem("Recent Conversions", callback=None),
            None,  # Separator
            # Quick toggles
            rumps.MenuItem("Auto-open after creation", callback=self.toggle_auto_open),
            rumps.MenuItem("Show notifications", callback=self.toggle_notifications),
            None,  # Separator
            rumps.MenuItem("Settings...", callback=self.show_settings),
            rumps.MenuItem("Reveal Config File", callback=self.reveal_config_file),
            rumps.MenuItem("About", callback=self.show_about),
            None,  # Separator
            rumps.MenuItem("Restart Converter", callback=self.restart_converter),
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        # Add recent conversions submenu
        self.update_recent_menu()

        # Initialize toggle states to reflect config
        try:
            self.menu["Auto-open after creation"].state = int(bool(self.config.get("auto_open", False)))
            self.menu["Show notifications"].state = int(bool(self.config.get("show_notifications", True)))
        except (KeyError, AttributeError) as e:
            print(f"Warning: Could not set menu item states: {e}")
            # Menu items may not exist in all configurations

    def update_recent_menu(self):
        """Update the recent conversions menu"""
        recent_menu = self.menu["Recent Conversions"]
        if recent_menu:
            # Clear submenu robustly across rumps versions
            try:
                recent_menu.clear()
            except Exception:
                try:
                    recent_menu.menu = []  # reset submenu
                except Exception:
                    pass

            # Get recent ePub files
            output_dir = Path(self.config["output_directory"])
            if output_dir.exists():
                epub_files = sorted(
                    output_dir.glob("*.epub"),
                    key=lambda x: x.stat().st_mtime,
                    reverse=True
                )[:10]  # Last 10 files

                if epub_files:
                    for epub_file in epub_files:
                        item = rumps.MenuItem(
                            epub_file.name,
                            callback=lambda sender, path=str(epub_file): self.open_file(path)
                        )
                        recent_menu.add(item)
                else:
                    recent_menu.add(rumps.MenuItem("No recent conversions", callback=None))
            else:
                # If the output directory doesn't exist yet, show a helpful placeholder
                recent_menu.add(rumps.MenuItem("No recent conversions", callback=None))

    def convert_now(self, sender=None):
        """Manually trigger conversion"""
        try:
            if self.converter:
                # Trigger conversion in the converter
                result = self.converter.convert_clipboard_content()

                if result:
                    # Notify optionally
                    if self.config["show_notifications"]:
                        self.notify(
                            "ePub Created",
                            f"File saved: {os.path.basename(result)}"
                        )
                    # Update recent menu regardless of notifications
                    self.update_recent_menu()
                    # Auto-open if configured
                    if self.config["auto_open"]:
                        self.open_file(result)
                elif self.config["show_notifications"]:
                    self.notify("No Content", "Clipboard is empty or contains no text")
            else:
                self.notify("Error", "Converter not initialized")
        except Exception as e:
            print(f"Error during conversion: {e}")
            self.notify("Conversion Error", str(e))

    def convert_with_llm(self, sender=None, prompt_index=None):
        """Send clipboard text through LLM and convert returned Markdown to ePub."""
        try:
            try:
                import pyperclip
                clip_text = pyperclip.paste()
            except Exception as e:
                clip_text = ""
                print(f"Clipboard error: {e}")

            # If clipboard is a YouTube URL, delegate to converter's YouTube flow
            if clip_text and ClipboardToEpubConverter._looks_like_youtube_url(str(clip_text)):
                # Run via converter to reuse yt-dlp + LLM pipeline, passing the captured URL
                captured_url = str(clip_text)

                # Build selected prompt overrides (centralized)
                def _selected_prompt_and_overrides() -> tuple[str, dict]:
                    try:
                        idx = int(self.config.get("llm_prompt_active", 0)) if prompt_index is None else int(prompt_index)
                    except Exception:
                        idx = 0
                    ov = build_overrides_for_prompt(self.config, idx)
                    prompt_text = str(ov.get("system_prompt", ""))
                    return prompt_text, ov

                def run_youtube():
                    try:
                        if not self.converter:
                            self.notify("Error", "Converter not initialized")
                            return
                        # Ejecutar la ruta asíncrona con overrides del prompt seleccionado
                        _prompt_text, overrides = _selected_prompt_and_overrides()
                        path = asyncio.run(self.converter.convert_clipboard_content_async(clipboard_content=captured_url, llm_overrides=overrides))
                        if path:
                            if self.config["show_notifications"]:
                                self.notify("ePub Created", f"File saved: {os.path.basename(path)}")
                            self._call_on_main_thread_once(0.1, self.update_recent_menu)
                            if self.config["auto_open"]:
                                subprocess.run(["open", path])
                        else:
                            self.notify("Conversion Error", "Could not create ePub from YouTube subtitles")
                    except Exception as e:
                        print(f"YouTube LLM conversion error: {e}")
                        self.notify("LLM Error", str(e))

                t = threading.Thread(target=run_youtube, daemon=True)
                t.start()
                return

            # Resolve provider/model/prompt and numeric params (centralized)
            params = resolve_prompt_params(self.config, prompt_index)
            provider = params.get("provider", "openrouter")
            api_key = params.get("api_key", "")
            model = params.get("model", "anthropic/claude-sonnet-4.5")
            prompt = params.get("system_prompt", "")
            max_tokens = int(params.get("max_tokens", 2048))
            temperature = float(params.get("temperature", 0.2))
            timeout_s = int(params.get("timeout_seconds", 60))
            retries = int(params.get("retry_count", 10))

            if not api_key or not prompt:
                provider_label = params.get("provider_label", "LLM")
                self.notify(provider_label, "Configure API Key and Prompt in Settings")
                return

            if not clip_text or not str(clip_text).strip():
                self.notify("No Content", "Clipboard is empty or contains no text")
                return

            # Run LLM and conversion on a worker thread
            def run():
                try:
                    from .llm.base import LLMRequest
                    from .llm.anthropic import AnthropicProvider
                    from .llm.openrouter import OpenRouterProvider
                    from .llm_anthropic import sanitize_first_line  # type: ignore

                    provider_name = str(provider or "openrouter").strip().lower()
                    if provider_name == "openrouter":
                        llm_provider = OpenRouterProvider()
                    else:
                        llm_provider = AnthropicProvider()

                    request = LLMRequest(
                        text=str(clip_text),
                        api_key=str(api_key),
                        model=str(model),
                        system_prompt=str(prompt),
                        max_tokens=int(max_tokens),
                        temperature=float(temperature),
                        timeout_s=int(timeout_s),
                        retries=int(retries),
                    )

                    md = llm_provider.process(request)

                    title = sanitize_first_line(md)
                    tags = ["anthropic"] if provider_name != "openrouter" else ["openrouter"]
                    path = self.converter.convert_text_to_epub(md, suggested_title=title, tags=tags) if self.converter else None

                    if path:
                        if self.config["show_notifications"]:
                            self.notify("ePub Created", f"File saved: {os.path.basename(path)}")
                        self._call_on_main_thread_once(0.1, self.update_recent_menu)
                        if self.config["auto_open"]:
                            subprocess.run(["open", path])
                    else:
                        self.notify("Conversion Error", "Could not create ePub from LLM output")
                except Exception as e:
                    print(f"LLM conversion error: {e}")
                    self.notify("LLM Error", str(e))

            t = threading.Thread(target=run, daemon=True)
            t.start()
        except Exception as e:
            print(f"Error in convert_with_llm: {e}")
            self.notify("Error", f"Failed to run LLM conversion: {e}")

    def open_folder(self, sender):
        """Open the ePubs output folder"""
        output_dir = self.config["output_directory"]
        if os.path.exists(output_dir):
            subprocess.run(["open", output_dir])
        else:
            self.notify("Folder Not Found", f"Creating folder: {output_dir}")
            os.makedirs(output_dir, exist_ok=True)
            subprocess.run(["open", output_dir])

    def open_file(self, file_path):
        """Open a specific ePub file"""
        if os.path.exists(file_path):
            subprocess.run(["open", file_path])
        else:
            self.notify("File Not Found", f"File no longer exists: {os.path.basename(file_path)}")

    def reveal_config_file(self, sender):
        """Reveal the JSON config in Finder"""
        try:
            # Ensure file exists so reveal works
            if not self.config_path.exists():
                self.save_config()
            subprocess.run(["open", "-R", str(self.config_path)])
        except Exception as e:
            self.notify("Error", f"Could not reveal config: {e}")

    def toggle_auto_open(self, sender):
        """Toggle auto-open preference from the menu"""
        try:
            new_state = not bool(self.config.get("auto_open", False))
            self.config["auto_open"] = new_state
            self.save_config()
            # Reflect state in checkmark
            try:
                self.menu["Auto-open after creation"].state = int(new_state)
            except (KeyError, AttributeError) as e:
                print(f"Warning: Could not update menu state: {e}")
            self.notify("Preference Updated", f"Auto-open is {'On' if new_state else 'Off'}")
        except Exception as e:
            self.notify("Error", f"Failed to update preference: {e}")

    def toggle_notifications(self, sender):
        """Toggle notifications preference from the menu"""
        try:
            new_state = not bool(self.config.get("show_notifications", True))
            self.config["show_notifications"] = new_state
            self.save_config()
            try:
                self.menu["Show notifications"].state = int(new_state)
            except (KeyError, AttributeError) as e:
                print(f"Warning: Could not update menu state: {e}")
            # Avoid spamming a notification if just turned off
            if new_state:
                self.notify("Preference Updated", "Notifications are On")
        except Exception as e:
            # If notifications are off, fall back to print
            print(f"Failed to update notifications preference: {e}")

    def show_settings(self, sender):
        """Show settings window"""
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))

            # Prefer modern Qt window if available; fall back to Tk
            qt_script = os.path.join(base_dir, "config_window_qt.py")
            tk_script = os.path.join(base_dir, "config_window.py")

            def run_script(path):
                return subprocess.run([sys.executable, path], capture_output=True, text=True)

            result = None
            if os.path.exists(qt_script):
                result = run_script(qt_script)
                if result.returncode != 0:
                    print(f"Qt settings failed, falling back to Tk. Stderr: {result.stderr}")
                    if os.path.exists(tk_script):
                        result = run_script(tk_script)
            elif os.path.exists(tk_script):
                result = run_script(tk_script)

            if result and result.returncode == 0:
                # Reload configuration after window closes
                self.load_config()
                # Restart converter with new settings
                self.restart_converter(None)
                # Rebuild menu to reflect LLM prompt changes
                try:
                    self.setup_menu()
                except Exception as e:
                    print(f"Warning: could not rebuild menu: {e}")
            else:
                if result:
                    print(f"Config window error: {result.stderr}")
                # Fallback to simple notification
                self.notify(
                    "Settings",
                    f"To change settings, edit:\n{self.config_path}"
                )
        except Exception as e:
            print(f"Error opening settings: {e}")
            self.notify("Error", f"Failed to open settings: {e}")

    def show_about(self, sender):
        """Show about dialog"""
        rumps.alert(
            "Clipboard to ePub",
            "Version 1.0.0\n\n"
            "Convert clipboard content to ePub format with a single hotkey.\n\n"
            f"Hotkey: {self.config['hotkey'].upper()}\n"
            f"Output: {self.config['output_directory']}\n\n"
            "© 2024 - Made with Python & rumps"
        )

    def start_converter(self):
        """Start the converter in a background thread"""
        if self.converter and not self.converter_thread:
            def run_converter():
                try:
                    # Set up the conversion callback
                    def on_conversion(filepath):
                        if filepath:
                            # Notify optionally
                            if self.config["show_notifications"]:
                                self.notify(
                                    "ePub Created",
                                    f"File saved: {os.path.basename(filepath)}"
                                )
                            # Update recent menu once on the main thread
                            self._call_on_main_thread_once(0.1, self.update_recent_menu)
                            # Auto-open if configured
                            if self.config["auto_open"]:
                                subprocess.run(["open", filepath])

                    # Start the converter listener
                    self.converter.conversion_callback = on_conversion
                    # Surface converter errors to the user as notifications
                    def on_error(event):
                        try:
                            if isinstance(event, ErrorEvent):
                                self.notify(event.title, event.message)
                            else:
                                self.notify("Error", str(event))
                        except Exception:
                            pass
                    self.converter.error_callback = on_error
                    self.converter.start_listening()

                except Exception as e:
                    print(f"Converter thread error: {e}")

            self.converter_thread = threading.Thread(target=run_converter, daemon=True)
            self.converter_thread.start()

            if self.config["show_notifications"]:
                self.notify("Converter Started", f"Listening for {self.config['hotkey'].upper()}")

        # Attach activity callback for immediate UI refresh
        try:
            if self.converter:
                self.converter.activity_callback = lambda snap: self._call_on_main_thread_once(0.05, self._refresh_activity)
        except Exception:
            pass

    def _setup_llm_hotkey(self):
        try:
            from pynput import keyboard
        except Exception as e:
            print(f"Hotkey setup skipped (pynput missing): {e}")
            return

        # Guard against macOS constant missing in some PyObjC versions
        try:
            from Quartz import (  # type: ignore
                CGEventKeyboardGetUnicodeString,
                CFRunLoopAddSource,
            )
            _ = CGEventKeyboardGetUnicodeString, CFRunLoopAddSource
        except Exception:
            if self.config.get("show_notifications", True):
                self.notify("LLM Hotkey Disabled", "macOS keyboard API not available; use the menu item")
            print("Quartz keyboard APIs missing; disabling LLM hotkey listener")
            return

        self.llm_hotkey = parse_hotkey_string(self.config.get("anthropic_hotkey", "cmd+shift+l")) or set()

        def on_press(key):
            self.llm_current_keys.add(key)
            if self.llm_hotkey and self.llm_hotkey.issubset(self.llm_current_keys):
                self.convert_with_llm()

        def on_release(key):
            try:
                self.llm_current_keys.remove(key)
            except KeyError:
                pass

        try:
            if self.llm_listener:
                self.llm_listener.stop()
            self.llm_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self.llm_listener.start()
            if self.config.get("show_notifications", True):
                try:
                    label = self.config.get("anthropic_hotkey", "cmd+shift+l").upper()
                    self.notify("LLM Hotkey", f"Listening for {label}")
                except Exception:
                    pass
        except Exception as e:
            print(f"LLM hotkey listener error: {e}")

    def restart_converter(self, sender):
        """Restart the converter with new settings"""
        try:
            # Stop current converter if running
            if self.converter:
                try:
                    self.converter.cleanup()
                except Exception as e:
                    print(f"Warning: Converter cleanup on restart failed: {e}")

            # Reinitialize with new config
            self.init_converter()

            # Start new converter thread
            self.converter_thread = None
            self.start_converter()

            # Restart LLM hotkey listener to apply any changes
            try:
                if self.llm_listener:
                    self.llm_listener.stop()
                    self.llm_listener = None
                self.llm_current_keys = set()
                self._setup_llm_hotkey()
            except Exception as e:
                print(f"Warning: Could not restart LLM hotkey: {e}")

            self.notify("Converter Restarted", "Settings applied successfully")
        except Exception as e:
            print(f"Error restarting converter: {e}")
            self.notify("Error", f"Failed to restart converter: {e}")

    def quit_app(self, sender):
        """Quit the application"""
        try:
            if self.converter:
                try:
                    self.converter.cleanup()
                except Exception as e:
                    print(f"Warning: Converter cleanup on quit failed: {e}")
            if self.llm_listener:
                try:
                    self.llm_listener.stop()
                except Exception:
                    pass
        except Exception as e:
            print(f"Warning: Error stopping converter on quit: {e}")
            # Continue with quit even if converter cleanup fails
        rumps.quit_application()

    def notify(self, title, message):
        """Send a macOS notification"""
        if self.config.get("show_notifications", True):
            try:
                pync.notify(
                    message,
                    title=title,
                    appIcon=None,  # Use default icon
                    sound="default"
                )
            except Exception as e:
                # Avoid using rumps.notification before the NSApp loop starts,
                # since triggering Cocoa notifications too early can crash
                # (Abort trap: 6) on some macOS/PyObjC combos.
                print(f"Notification error (suppressed fallback): {e}")

    # ---- Activity UI ----
    def _activity_tick(self, _=None):
        try:
            if not self.converter:
                self.title = None
                if hasattr(self, 'activity_item') and self.activity_item:
                    self.activity_item.title = "Activity: Idle"
                return
            counts = self.converter.get_activity()
            active = int(counts.get('active', 0))
            queued = int(counts.get('queued', 0))
            if active > 0 or queued > 0:
                frame = self._spinner_frames[self._spinner_idx % len(self._spinner_frames)]
                self._spinner_idx = (self._spinner_idx + 1) % 1000000
                # Show spinner next to icon for feedback during long LLM/subtitle runs
                self.title = frame
                if self.activity_item:
                    self.activity_item.title = f"Activity: {active} running, {queued} queued"
            else:
                # Clear spinner/title when idle
                self.title = None
                if self.activity_item:
                    self.activity_item.title = "Activity: Idle"
        except Exception as e:
            # Avoid crashing timer on minor errors
            print(f"Activity tick error: {e}")

    def _refresh_activity(self):
        # One-shot refresh triggered from converter callback
        self._activity_tick()


if __name__ == "__main__":
    # In development we prefer a venv, but don't hard-exit for bundled apps
    is_venv = (
        hasattr(sys, 'real_prefix') or
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    )
    is_frozen = bool(getattr(sys, 'frozen', False))
    if not is_venv and not is_frozen:
        print("Warning: Not running in a virtual environment.")
        print("It's recommended to: source venv/bin/activate")
        # Continue without exiting to support non-venv runs

    # Create and run the app
    app = ClipToEpubApp()
    app.run()
