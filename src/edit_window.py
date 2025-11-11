#!/usr/bin/env python3
"""
Pre-conversion Edit Window for Clipboard to ePub
Provides a GUI for editing and previewing content before conversion
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import logging
import sys
from typing import Optional, Dict, Any, Callable
from pathlib import Path
import json
import webbrowser
import tempfile

logger = logging.getLogger('EditWindow')


class PreConversionEditor:
    """Window for editing content before converting to ePub"""

    def __init__(self, content: str, metadata: Optional[Dict[str, Any]] = None,
                 on_convert: Optional[Callable] = None,
                 on_cancel: Optional[Callable] = None):
        """
        Initialize the editor window

        Args:
            content: Initial content to edit
            metadata: Initial metadata
            on_convert: Callback when user clicks Convert (receives edited content and metadata)
            on_cancel: Callback when user cancels
        """
        self.content = content
        self.metadata = metadata or {}
        self.on_convert = on_convert
        self.on_cancel = on_cancel
        self.preview_file = None

        # Create main window
        self.window = tk.Tk()
        self.window.title("Edit Before Converting to ePub")
        self.window.geometry("900x700")

        # Set minimum size
        self.window.minsize(700, 500)

        # Configure grid weights for resizing
        self.window.grid_rowconfigure(0, weight=1)
        self.window.grid_columnconfigure(0, weight=1)

        # Try to use macOS-friendly theme and set icon
        try:
            style = ttk.Style()
            try:
                style.theme_use('aqua')
            except tk.TclError:
                try:
                    style.theme_use('clam')
                except tk.TclError:
                    # Use default theme
                    pass
            icon_png = (Path(__file__).resolve().parent.parent / "resources" / "icon_64.png")
            if icon_png.exists():
                self.window.iconphoto(True, tk.PhotoImage(file=str(icon_png)))
        except (tk.TclError, OSError) as e:
            logger.debug(f"Could not set theme or icon: {e}")

        self.setup_ui()
        self.load_content()

        # Center window on screen
        self.center_window()

        # Bind keyboard shortcuts
        self.setup_shortcuts()

    def setup_ui(self):
        """Set up the user interface"""
        # Create main container
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Title and metadata section
        self.setup_metadata_section(main_frame)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))

        # Content editor tab
        self.setup_editor_tab()

        # Preview tab
        self.setup_preview_tab()

        # Settings tab
        self.setup_settings_tab()

        # Buttons
        self.setup_buttons(main_frame)

    def setup_metadata_section(self, parent):
        """Set up metadata input fields"""
        metadata_frame = ttk.LabelFrame(parent, text="Metadata", padding="10")
        metadata_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        metadata_frame.grid_columnconfigure(1, weight=1)
        metadata_frame.grid_columnconfigure(3, weight=1)

        # Title
        ttk.Label(metadata_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.title_var = tk.StringVar(value=self.metadata.get('title', 'Untitled'))
        self.title_entry = ttk.Entry(metadata_frame, textvariable=self.title_var, width=40)
        self.title_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))

        # Author
        ttk.Label(metadata_frame, text="Author:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.author_var = tk.StringVar(value=self.metadata.get('author', 'Unknown Author'))
        self.author_entry = ttk.Entry(metadata_frame, textvariable=self.author_var, width=30)
        self.author_entry.grid(row=0, column=3, sticky=(tk.W, tk.E))

        # Description
        ttk.Label(metadata_frame, text="Description:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        self.description_var = tk.StringVar(value=self.metadata.get('description', ''))
        self.description_entry = ttk.Entry(metadata_frame, textvariable=self.description_var)
        self.description_entry.grid(row=1, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))

        # Tags
        ttk.Label(metadata_frame, text="Tags:").grid(row=2, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        self.tags_var = tk.StringVar(value=', '.join(self.metadata.get('tags', [])))
        self.tags_entry = ttk.Entry(metadata_frame, textvariable=self.tags_var)
        self.tags_entry.grid(row=2, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))

    def setup_editor_tab(self):
        """Set up the content editor tab"""
        editor_frame = ttk.Frame(self.notebook)
        self.notebook.add(editor_frame, text="Edit Content")
        editor_frame.grid_rowconfigure(0, weight=1)
        editor_frame.grid_columnconfigure(0, weight=1)

        # Toolbar
        toolbar = ttk.Frame(editor_frame)
        toolbar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(5, 5))

        ttk.Label(toolbar, text="Format:").pack(side=tk.LEFT, padx=(0, 5))
        self.format_var = tk.StringVar(value=self.metadata.get('format', 'auto'))
        format_menu = ttk.Combobox(toolbar, textvariable=self.format_var,
                                  values=['auto', 'markdown', 'html', 'plain', 'rtf'],
                                  width=15, state='readonly')
        format_menu.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(toolbar, text="Clear", command=self.clear_content).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Restore Original", command=self.restore_original).pack(side=tk.LEFT, padx=(0, 5))

        # Word count label
        self.word_count_label = ttk.Label(toolbar, text="Words: 0 | Characters: 0")
        self.word_count_label.pack(side=tk.RIGHT)

        # Text editor
        text_frame = ttk.Frame(editor_frame)
        text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(5, 0))
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        self.text_editor = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            width=80,
            height=25,
            font=('Courier', 12),
            undo=True
        )
        self.text_editor.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Bind text change event
        self.text_editor.bind('<<Modified>>', self.on_text_change)
        self.text_editor.bind('<KeyRelease>', self.update_word_count)

    def setup_preview_tab(self):
        """Set up the preview tab"""
        preview_frame = ttk.Frame(self.notebook)
        self.notebook.add(preview_frame, text="Preview")
        preview_frame.grid_rowconfigure(1, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)

        # Preview toolbar
        preview_toolbar = ttk.Frame(preview_frame)
        preview_toolbar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(5, 5))

        ttk.Button(preview_toolbar, text="Generate Preview",
                  command=self.generate_preview).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(preview_toolbar, text="Open in Browser",
                  command=self.open_preview_browser).pack(side=tk.LEFT, padx=(0, 5))

        self.preview_label = ttk.Label(preview_toolbar, text="Click 'Generate Preview' to see formatted content")
        self.preview_label.pack(side=tk.LEFT, padx=(10, 0))

        # Preview text area
        self.preview_text = scrolledtext.ScrolledText(
            preview_frame,
            wrap=tk.WORD,
            width=80,
            height=25,
            state=tk.DISABLED,
            bg='#f9f9f9'
        )
        self.preview_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(5, 0))

    def setup_settings_tab(self):
        """Set up the settings tab"""
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="Settings")

        # Style selection
        style_frame = ttk.LabelFrame(settings_frame, text="Style", padding="10")
        style_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)

        ttk.Label(style_frame, text="CSS Style:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.style_var = tk.StringVar(value=self.metadata.get('style', 'default'))
        style_menu = ttk.Combobox(style_frame, textvariable=self.style_var,
                                 values=['default', 'minimal', 'modern'],
                                 width=20, state='readonly')
        style_menu.grid(row=0, column=1, sticky=tk.W)

        # Chapter settings
        chapter_frame = ttk.LabelFrame(settings_frame, text="Chapter Settings", padding="10")
        chapter_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)

        ttk.Label(chapter_frame, text="Words per Chapter:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.chapter_words_var = tk.IntVar(value=self.metadata.get('chapter_words', 5000))
        chapter_spinbox = ttk.Spinbox(chapter_frame, from_=1000, to=20000,
                                     textvariable=self.chapter_words_var,
                                     increment=1000, width=10)
        chapter_spinbox.grid(row=0, column=1, sticky=tk.W)

        # Language
        lang_frame = ttk.LabelFrame(settings_frame, text="Language", padding="10")
        lang_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)

        ttk.Label(lang_frame, text="Language Code:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.language_var = tk.StringVar(value=self.metadata.get('language', 'en'))
        lang_entry = ttk.Entry(lang_frame, textvariable=self.language_var, width=10)
        lang_entry.grid(row=0, column=1, sticky=tk.W)

        # Options
        options_frame = ttk.LabelFrame(settings_frame, text="Options", padding="10")
        options_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), padx=10, pady=10)

        self.include_toc_var = tk.BooleanVar(value=self.metadata.get('include_toc', True))
        ttk.Checkbutton(options_frame, text="Include Table of Contents",
                       variable=self.include_toc_var).grid(row=0, column=0, sticky=tk.W)

        self.auto_open_var = tk.BooleanVar(value=self.metadata.get('auto_open', False))
        ttk.Checkbutton(options_frame, text="Auto-open after conversion",
                       variable=self.auto_open_var).grid(row=1, column=0, sticky=tk.W)

    def setup_buttons(self, parent):
        """Set up action buttons"""
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(10, 0))

        # Left side - info (platform-aware)
        shortcut_convert = "Cmd+Enter" if sys.platform == "darwin" else "Ctrl+Enter"
        info_label = ttk.Label(button_frame, text=f"Press {shortcut_convert} to convert, Esc to cancel")
        info_label.pack(side=tk.LEFT)

        # Right side - buttons
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Convert to ePub", command=self.convert,
                  style="Accent.TButton").pack(side=tk.RIGHT)

    def setup_shortcuts(self):
        """Set up keyboard shortcuts"""
        # Convert / Preview shortcuts (platform-aware)
        if sys.platform == 'darwin':
            self.window.bind('<Command-Return>', lambda e: self.convert())
            self.window.bind('<Command-p>', lambda e: self.generate_preview())
        else:
            self.window.bind('<Control-Return>', lambda e: self.convert())
            self.window.bind('<Control-p>', lambda e: self.generate_preview())
        # Cancel: Escape
        self.window.bind('<Escape>', lambda e: self.cancel())

    def load_content(self):
        """Load initial content into editor"""
        self.original_content = self.content
        self.text_editor.insert('1.0', self.content)
        self.text_editor.edit_modified(False)
        self.update_word_count()

    def clear_content(self):
        """Clear the editor content"""
        if messagebox.askyesno("Clear Content", "Are you sure you want to clear all content?"):
            self.text_editor.delete('1.0', tk.END)

    def restore_original(self):
        """Restore original content"""
        if messagebox.askyesno("Restore Original", "Restore original content? Current changes will be lost."):
            self.text_editor.delete('1.0', tk.END)
            self.text_editor.insert('1.0', self.original_content)

    def on_text_change(self, event):
        """Handle text change event"""
        if self.text_editor.edit_modified():
            self.text_editor.edit_modified(False)
            # Could trigger auto-save or other actions here

    def update_word_count(self, event=None):
        """Update word and character count"""
        content = self.text_editor.get('1.0', tk.END)
        words = len(content.split())
        chars = len(content)
        self.word_count_label.config(text=f"Words: {words:,} | Characters: {chars:,}")

    def generate_preview(self):
        """Generate and display preview"""
        try:
            content = self.text_editor.get('1.0', tk.END).strip()

            # Simple HTML preview
            html_content = self.generate_preview_html(content)

            # Update preview text
            self.preview_text.config(state=tk.NORMAL)
            self.preview_text.delete('1.0', tk.END)
            self.preview_text.insert('1.0', html_content)
            self.preview_text.config(state=tk.DISABLED)

            # Save preview to temp file
            self.preview_file = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False)
            self.preview_file.write(html_content)
            self.preview_file.close()

            self.preview_label.config(text="Preview generated successfully")

            # Switch to preview tab
            self.notebook.select(1)

        except Exception as e:
            logger.error(f"Error generating preview: {e}")
            messagebox.showerror("Preview Error", f"Failed to generate preview: {str(e)}")

    def generate_preview_html(self, content: str) -> str:
        """Generate HTML preview of content"""
        # Escape HTML characters
        import html
        content = html.escape(content)

        # Convert line breaks to <br>
        content = content.replace('\n', '<br>\n')

        # Load CSS from templates if available according to selected style
        css_snippet = None
        try:
            style_name = getattr(self, 'style_var', None).get() if hasattr(self, 'style_var') else 'default'
            templates_dir = Path(__file__).resolve().parent.parent / 'templates'
            css_path = templates_dir / f"{style_name}.css"
            if css_path.exists():
                css_snippet = css_path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError, AttributeError) as e:
            logger.debug(f"Could not load CSS template: {e}")
            css_snippet = None

        # Basic HTML template
        html_template = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{self.title_var.get()}</title>
    <style>
        {css_snippet if css_snippet else ''}
        /* Fallback minimal styles for preview container */
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            max-width: 820px;
            margin: 0 auto;
            padding: 24px;
            background-color: #f7f7f7;
        }}
        h1 {{
            color: #333;
            border-bottom: 1px solid #ddd;
            padding-bottom: 8px;
            margin-bottom: 16px;
        }}
        .metadata {{
            background-color: #efefef;
            padding: 12px 14px;
            margin-bottom: 16px;
            border-radius: 8px;
        }}
        .content {{
            background-color: #fff;
            padding: 18px 20px;
            border-radius: 10px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}
    </style>
</head>
<body>
    <h1>{self.title_var.get()}</h1>
    <div class="metadata">
        <p><strong>Author:</strong> {self.author_var.get()}</p>
        <p><strong>Description:</strong> {self.description_var.get() or 'No description'}</p>
        <p><strong>Tags:</strong> {self.tags_var.get() or 'No tags'}</p>
        <p><strong>Format:</strong> {self.format_var.get()}</p>
    </div>
    <div class="content">
        <p>{content}</p>
    </div>
</body>
</html>'''

        return html_template

    def open_preview_browser(self):
        """Open preview in web browser"""
        if self.preview_file and Path(self.preview_file.name).exists():
            webbrowser.open(f'file://{self.preview_file.name}')
        else:
            messagebox.showinfo("No Preview", "Generate a preview first")

    def get_edited_content(self) -> str:
        """Get the edited content"""
        return self.text_editor.get('1.0', tk.END).strip()

    def get_metadata(self) -> Dict[str, Any]:
        """Get the edited metadata"""
        # Parse tags
        tags = [tag.strip() for tag in self.tags_var.get().split(',') if tag.strip()]

        return {
            'title': self.title_var.get(),
            'author': self.author_var.get(),
            'description': self.description_var.get(),
            'tags': tags,
            'format': self.format_var.get(),
            'style': self.style_var.get(),
            'chapter_words': self.chapter_words_var.get(),
            'language': self.language_var.get(),
            'include_toc': self.include_toc_var.get(),
            'auto_open': self.auto_open_var.get()
        }

    def convert(self):
        """Handle convert button click"""
        content = self.get_edited_content()
        metadata = self.get_metadata()

        if not content:
            messagebox.showwarning("No Content", "Please enter some content to convert")
            return

        # Clean up preview file if exists
        if self.preview_file and Path(self.preview_file.name).exists():
            try:
                Path(self.preview_file.name).unlink()
            except (OSError, IOError) as e:
                logger.warning(f"Could not delete preview file: {e}")

        # Call callback if provided
        if self.on_convert:
            self.on_convert(content, metadata)

        self.window.destroy()

    def cancel(self):
        """Handle cancel button click"""
        # Clean up preview file if exists
        if self.preview_file and Path(self.preview_file.name).exists():
            try:
                Path(self.preview_file.name).unlink()
            except (OSError, IOError) as e:
                logger.warning(f"Could not delete preview file: {e}")

        if self.on_cancel:
            self.on_cancel()

        self.window.destroy()

    def center_window(self):
        """Center the window on screen"""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')

    def run(self):
        """Run the editor window"""
        self.window.mainloop()


def test_editor():
    """Test the editor window"""
    sample_content = """# Sample Content

This is a test of the pre-conversion editor window.

## Features
- Edit content before conversion
- Preview formatted output
- Customize metadata
- Configure conversion settings

This editor provides a user-friendly interface for reviewing and editing
clipboard content before converting it to ePub format."""

    sample_metadata = {
        'title': 'Sample Document',
        'author': 'Test Author',
        'description': 'A sample document for testing the editor',
        'tags': ['test', 'sample', 'demo'],
        'format': 'markdown'
    }

    def on_convert(content, metadata):
        print("Converting with:")
        print(f"  Title: {metadata['title']}")
        print(f"  Author: {metadata['author']}")
        print(f"  Content length: {len(content)} chars")
        print(f"  Metadata: {json.dumps(metadata, indent=2)}")

    def on_cancel():
        print("Conversion cancelled")

    editor = PreConversionEditor(
        content=sample_content,
        metadata=sample_metadata,
        on_convert=on_convert,
        on_cancel=on_cancel
    )
    editor.run()


if __name__ == '__main__':
    test_editor()
