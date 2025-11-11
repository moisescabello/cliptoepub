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
# Robust import for paths whether run from repo root or src/
try:
    from src import paths as paths  # type: ignore
except Exception:
    import paths  # type: ignore


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
            "chapter_words": 5000
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
                    return config
            except Exception as e:
                print(f"Error loading config: {e}")
                return self.default_config.copy()
        return self.default_config.copy()

    def save_config(self):
        """Save configuration to file"""
        try:
            # Update config from GUI elements
            self.config["output_directory"] = self.output_var.get()
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

            # Create preferences directory if needed
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Write config file
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)

            messagebox.showinfo("Success", "Configuration saved successfully!\n\nRestart the menu bar app to apply changes.")
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

        # Author
        ttk.Label(main_frame, text="Default Author:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.author_var = tk.StringVar(value=self.config["author"])
        ttk.Entry(main_frame, textvariable=self.author_var, width=30).grid(row=3, column=1, sticky=tk.W, pady=5)

        # Language
        ttk.Label(main_frame, text="Language:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.language_var = tk.StringVar(value=self.config["language"])
        language_combo = ttk.Combobox(
            main_frame,
            textvariable=self.language_var,
            values=["en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh", "ko"],
            width=27,
            state="readonly"
        )
        language_combo.grid(row=4, column=1, sticky=tk.W, pady=5)

        # Style (populate from templates dir if present)
        ttk.Label(main_frame, text="CSS Style:").grid(row=5, column=0, sticky=tk.W, pady=5)
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
        style_combo.grid(row=5, column=1, sticky=tk.W, pady=5)

        # Chapter Words
        ttk.Label(main_frame, text="Words per Chapter:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.chapter_words_var = tk.StringVar(value=str(self.config["chapter_words"]))
        chapter_frame = ttk.Frame(main_frame)
        chapter_frame.grid(row=6, column=1, sticky=tk.W, pady=5)
        ttk.Entry(chapter_frame, textvariable=self.chapter_words_var, width=10).pack(side=tk.LEFT)
        ttk.Label(chapter_frame, text="(100-50000)").pack(side=tk.LEFT, padx=(5, 0))

        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=15)

        # Checkboxes
        self.auto_open_var = tk.BooleanVar(value=self.config["auto_open"])
        ttk.Checkbutton(
            main_frame,
            text="Auto-open ePub files after creation",
            variable=self.auto_open_var
        ).grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=5)

        self.notifications_var = tk.BooleanVar(value=self.config["show_notifications"])
        ttk.Checkbutton(
            main_frame,
            text="Show notifications",
            variable=self.notifications_var
        ).grid(row=9, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(row=10, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=15)

        # Info section
        info_frame = ttk.LabelFrame(main_frame, text="Info", padding="10")
        info_frame.grid(row=11, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

        hotkey_text = "Ctrl+Shift+E" if sys.platform.startswith("win") else "Cmd+Shift+E"
        info_text = f"Hotkey: {hotkey_text} (not configurable yet)\n"
        info_text += f"Config Location: {self.config_path}\n"
        info_text += f"ePubs Saved To: {self.config['output_directory']}"

        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor=tk.W)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=12, column=0, columnspan=2, pady=(20, 0))

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
            self.author_var.set(self.default_config["author"])
            self.language_var.set(self.default_config["language"])
            self.style_var.set(self.default_config["style"])
            self.auto_open_var.set(self.default_config["auto_open"])
            self.notifications_var.set(self.default_config["show_notifications"])
            self.chapter_words_var.set(str(self.default_config["chapter_words"]))

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
