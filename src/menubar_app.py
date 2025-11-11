#!/usr/bin/env python3
"""
ClipToEpub - Menu Bar Application
Unified converter backend
"""

# Import compatibility patch for 'imp' module first
try:
    from . import imp_patch
except ImportError:
    try:
        import imp_patch
    except ImportError:
        # Patch not available - this is acceptable as it's for Python 3.12+ compatibility
        pass

import rumps
import os
import sys
import json
import threading
import subprocess
from pathlib import Path
from datetime import datetime
import pync

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.converter import ClipboardToEpubConverter
# Robust import for paths module whether run from repo root or src/
try:
    from src import paths as paths  # type: ignore
except Exception:
    import paths  # type: ignore


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
            "chapter_words": 5000
        }

        # Load existing configuration
        self.load_config()

        # Initialize converter
        self.converter = None
        self.init_converter()

        # Setup menu items
        self.setup_menu()

        # Start converter in background thread
        self.converter_thread = None
        self.start_converter()

    def load_config(self):
        """Load configuration from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
            except Exception as e:
                print(f"Error loading config: {e}")

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
            def parse_hotkey_string(text):
                try:
                    from pynput import keyboard
                except Exception:
                    return None
                if not text:
                    return None
                parts = [p.strip().lower() for p in str(text).split('+') if p.strip()]
                combo = set()
                for p in parts:
                    if p in ("ctrl", "control"):
                        combo.add(keyboard.Key.ctrl)
                    elif p in ("cmd", "command", "meta"):
                        combo.add(keyboard.Key.cmd)
                    elif p == "shift":
                        combo.add(keyboard.Key.shift)
                    elif len(p) == 1:
                        combo.add(keyboard.KeyCode.from_char(p))
                return combo or None

            hotkey_combo = parse_hotkey_string(self.config.get("hotkey"))

            self.converter = ClipboardToEpubConverter(
                output_dir=self.config["output_directory"],
                default_author=self.config["author"],
                default_language=self.config["language"],
                default_style=self.config["style"],
                chapter_words=self.config["chapter_words"],
                hotkey_combo=hotkey_combo,
            )
        except Exception as e:
            print(f"Error initializing converter: {e}")
            self.notify("Error", f"Failed to initialize converter: {e}")

    def setup_menu(self):
        """Setup menu items"""
        # Convert now button
        self.menu = [
            rumps.MenuItem("Convert Now", callback=self.convert_now),
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
                            # Update recent menu regardless
                            rumps.Timer(lambda _: self.update_recent_menu(), 0.1).start()
                            # Auto-open if configured
                            if self.config["auto_open"]:
                                subprocess.run(["open", filepath])

                    # Start the converter listener
                    self.converter.conversion_callback = on_conversion
                    self.converter.start_listening()

                except Exception as e:
                    print(f"Converter thread error: {e}")

            self.converter_thread = threading.Thread(target=run_converter, daemon=True)
            self.converter_thread.start()

            if self.config["show_notifications"]:
                self.notify("Converter Started", f"Listening for {self.config['hotkey'].upper()}")

    def restart_converter(self, sender):
        """Restart the converter with new settings"""
        try:
            # Stop current converter if running
            if self.converter:
                self.converter.stop_listening()

            # Reinitialize with new config
            self.init_converter()

            # Start new converter thread
            self.converter_thread = None
            self.start_converter()

            self.notify("Converter Restarted", "Settings applied successfully")
        except Exception as e:
            print(f"Error restarting converter: {e}")
            self.notify("Error", f"Failed to restart converter: {e}")

    def quit_app(self, sender):
        """Quit the application"""
        try:
            if self.converter:
                self.converter.stop_listening()
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
                print(f"Notification error: {e}")
                # Fallback to rumps notification
                rumps.notification(title, "", message)


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
