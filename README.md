# ClipToEpub

One simple step: press a global hotkey and it automatically converts the clipboard content to ePub and saves it to the designated folder. It detects images, rich text formatting, and markup. Optionally, process the clipboard text with an LLM and convert the model output to ePub in one go.

One more thing! If the clipboard content is just a a YouTube video URL, it will download the subtitles, process them with the LLM, and convert them to ePub.

<img src="https://github.com/user-attachments/assets/110bd335-ce09-4f62-88bb-3b983eebfb3d" width="200"/>
<img src="https://github.com/user-attachments/assets/693ac407-e29b-44b9-9620-3337876027fb" width="400"/>
<br>
<img src="https://github.com/user-attachments/assets/fa5fce91-19d5-4ca7-a4fc-00e07bad3849" width="400"/>

## Prerequisites

- macOS 10.15 or later
- Python 3.9 or later
- pip (Python package manager)
 - yt-dlp (only required for the YouTube subtitles feature)

## Installation

### Option 1: Automatic Installation (Recommended)

```bash
# Clone or download this repository, then run:
chmod +x setup.sh
./setup.sh
```

### Option 2: Manual Installation

1. **Create a virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
# Or for a more reproducible install (pinned versions):
pip install -r requirements.txt -c constraints.txt
# Optional: YouTube subtitles support
pip install yt-dlp
```

Note on dependencies:
- The package to install via pip is `newspaper3k`, but the Python import name is `newspaper`. This is expected and already handled by `requirements.txt`.

3. **Grant necessary permissions (macOS):**
   - Go to System Settings → Privacy & Security → Accessibility
   - Add Terminal (or your Python interpreter) to the allowed apps

## Usage

### macOS (Menu Bar)

```bash
source venv/bin/activate
./run_menubar.sh
# or
python -m cliptoepub.menubar_app
```

- Default hotkey: Cmd + Shift + E
- Output: `~/Documents/ClipboardEpubs/`
- Quick toggles in the menu: Auto-open, Notifications, Recent Conversions, Settings

LLM capture:
- Menu: first-level actions "LLM - <Name>" for up to 5 defined prompts.
- The LLM hotkey (Cmd + Shift + L) uses the active prompt from Settings.
- Before first use, configure the API, model, and prompts in Settings.

YouTube subtitles capture:
- Copy a YouTube URL (youtube.com or youtu.be) to the clipboard, then use "Convert Now" or the convert hotkey.
- The app fetches subtitles via yt-dlp (native first, then auto-generated) following your preferred language order (see Settings), processes them through the LLM prompt, and creates the ePub.

### Windows (Tray App)

```bat
run_tray_windows.bat
:: or
python -m cliptoepub.tray_app_windows
```

- Default hotkey: Ctrl + Shift + E
- Output: `C:\Users\<you>\Documents\ClipboardEpubs\`
- Click the tray icon for menu: Convert Now, Recent, Settings, toggles

LLM capture:
- Menu: first-level actions "LLM - <Name>" (up to 5).
- The LLM hotkey (Ctrl + Shift + L) uses the active prompt.
- Configure API, model, and prompts in Settings.

YouTube subtitles capture:
- Copy a YouTube URL to the clipboard, then use "Convert Now" or the convert hotkey.
- Requires `yt-dlp` installed and available on PATH: `pip install yt-dlp`.

## Configuration & Paths

- macOS config: `~/Library/Preferences/clipboard-to-epub.json`
- Windows config: `%APPDATA%\ClipToEpub\config.json` (auto-migration from legacy paths)
- History (if enabled): `~/.clipboard_to_epub/history.json` (macOS) or `%APPDATA%\ClipToEpub\history.json` (Windows)
- Output directory (default): `~/Documents/ClipboardEpubs/` or `C:\Users\<you>\Documents\ClipboardEpubs\`

Hotkeys are configurable from Settings (Qt or Tk):
- Primary capture hotkey (default: Cmd+Shift+E on macOS, Ctrl+Shift+E on Windows)
- LLM capture hotkey (default: Cmd+Shift+L / Ctrl+Shift+L)

LLM settings (persisted in the same config):
- Global:
  - `anthropic_api_key`
  - `anthropic_model` (default: `anthropic/claude-sonnet-4.5`)
  - `anthropic_max_tokens`, `anthropic_temperature`, `anthropic_timeout_seconds`, `anthropic_retry_count`
  - `llm_provider` (`anthropic` | `openrouter`), `openrouter_api_key`
  - `llm_store_keys_in_config` (bool; if `false`, API keys are not persisted to disk)
  - `anthropic_prompt` (legacy; kept in sync with the active prompt)
- Multi-prompt:
  - `llm_prompts` (list of 5): each element `{ name, text, overrides? }`
  - `llm_prompt_active` (0..4) — used by the LLM hotkey
  - `llm_per_prompt_overrides` (bool) — if true, per-prompt overrides are applied

You can also set `OPENROUTER_API_KEY` (default provider) or `ANTHROPIC_API_KEY` as environment variables; they override any keys stored in the config file and are the recommended way to provide secrets.

LLM API key handling:
- At runtime, the app always prefers environment variables (`ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`) and only uses `anthropic_api_key` / `openrouter_api_key` from the config as a fallback.
- In the LLM Settings (Tk/Qt), you can choose whether to store API keys in the config file using the “Store API keys in config file (plaintext)” option.
- For better security, leave that option disabled and keep the key fields empty, using only environment variables so that no API keys are written to the JSON config.

YouTube subtitles settings:
- Preferred language 1, 2, 3 (from a curated list of top YouTube languages including `en`, `es`, `pt`, `hi`, `id`, `ar`, `ru`, `ja`, `ko`, `fr`, `de`, `tr`).
- Prefer native subtitles; fallback to auto-generated (enabled by default).
- Defaults: `en` → `es` → `pt`.

## Project Structure

```
ClipToEpub/
├── src/
│   ├── cliptoepub/
│   │   ├── menubar_app.py           # macOS menu bar app
│   │   ├── tray_app_windows.py      # Windows tray app (PySide6)
│   ├── converter.py             # Unified converter module
│   ├── llm_anthropic.py         # Anthropic LLM integration (SDK + REST fallback)
│   ├── config_window_qt.py      # Settings (Qt, preferred)
│   ├── config_window.py         # Settings (Tkinter, fallback)
│   ├── edit_window.py           # Editor UI (Tkinter)
│   ├── history_manager.py       # Conversion history
│   ├── image_handler.py         # Image processing
│   ├── update_checker.py        # Update management
│   ├── paths.py                 # Cross-platform config/history paths
│   └── imp_patch.py             # Compatibility patch
├── templates/                   # CSS templates (default, minimal, modern)
├── resources/                   # Icons
├── build scripts/               # PyInstaller specs (Windows)
│   ├── file_version.txt
│   ├── pyinstaller_onefile.spec
│   ├── pyinstaller_onefolder.spec
│   └── pyinstaller_tray_windows.spec
├── build_app_fixed.sh           # macOS py2app build
├── build_complete.sh            # macOS full build
├── build_dmg.sh                 # macOS DMG creation
├── create_app_bundle.sh         # macOS lightweight bundle
├── run_menubar.sh               # macOS runner
├── run_tray_windows.bat         # Windows runner
├── requirements.txt             # Dependencies
└── README.md                    # This file
```

## Keyboard Shortcuts

- macOS: Cmd + Shift + E (convert now), Cmd + Shift + L (LLM capture)
- Windows: Ctrl + Shift + E (convert now), Ctrl + Shift + L (LLM capture)

## Features

### Current
- Global hotkey capture (platform-specific)
- Smart content detection (Markdown, HTML, RTF, URLs)
- Chapter splitting and Table of Contents
- CSS styling (default, minimal, modern)
- Custom CSS: place additional `.css` files in `templates/` and select by name in Settings
- Recent conversions menu and notifications
- Settings window (Qt preferred; Tk fallback)
- Windows tray app (QSystemTrayIcon)
- LLM processing: process clipboard text with Claude Sonnet 4.5 and convert the Markdown result to ePub
 - YouTube subtitles: if the clipboard contains only a YouTube URL, downloads subtitles (native first, then auto-generated), sends them through the configured LLM prompt, and converts the result to ePub. Requires `yt-dlp` installed.

### Optional / Advanced
- Advanced features (images/OCR, URL extraction, accumulator, cache, history) are built into the unified converter and can be enabled via flags.

### LLM Workflow
1) Open Settings → LLM tab/section.
2) Configure provider and API: `OPENROUTER_API_KEY` (default) or `ANTHROPIC_API_KEY`.
3) Confirm the global model (e.g., `anthropic/claude-sonnet-4.5`).
4) In "Custom Prompts", fill in up to 5 prompts with name and text. Mark one as "Use with Hotkey".
5) If you need different parameters per prompt, enable "Enable per-prompt overrides" and fill in that prompt's fields.
6) Adjust global "Max Tokens" if you're not using overrides or as a default value.
7) Click "Test Connection" (uses the active prompt) and verify.
8) Trigger the LLM: click "LLM - <Name>" or use the hotkey (Cmd/Ctrl+Shift+L, uses the active one).

Notes:
- Timeout auto-adjusts with Max Tokens: approximately `tokens/50 + 30 s` (clamped 30–300 s). You can override it manually, and reset to the recommended value with the provided button.
- If you request more tokens than allowed, the API returns a validation error; reduce “Max Tokens”.

Using Sonnet 4.5 (1M context) via OpenRouter
- Model id: `anthropic/claude-sonnet-4.5`.
- Set `llm_provider` to `openrouter` in Settings.
- Export `OPENROUTER_API_KEY` or enter it in Settings. The app routes to OpenRouter automatically.
- “Max Tokens” controls output length only; the 1M input context is provided by the model/provider.

Per-prompt overrides
- If `llm_per_prompt_overrides` is active, each prompt can define `model`, `max_tokens`, `temperature`, `timeout_seconds`, `retry_count`.
- Empty values in overrides inherit from the global ones.
- The YouTube flow uses the selected prompt (by click) or the active one (by hotkey) and applies its overrides.

Using Mistral Medium 3.1 via OpenRouter
- Model id: `mistralai/mistral-medium-3.1` (128k context).
- Set `llm_provider` to `openrouter` and choose the preset in Settings or paste the id.

## Troubleshooting

### "Permission denied" error
- Ensure Terminal has accessibility permissions in System Preferences

### Keyboard shortcut not working
- Make sure no other app is using Cmd+Shift+E
- Try restarting the application
- Check that the app has focus

### Empty ePub files
- Ensure clipboard has text content
- Try copying text again before pressing the hotkey

### Module not found errors
- Make sure virtual environment is activated
- Reinstall requirements: `pip install -r requirements.txt` (or `pip install -r requirements.txt -c constraints.txt` for a reproducible setup)
- If you see "lxml.html.clean is now a separate project": `pip install lxml_html_clean`
- If you see Anthropic auth errors (401/403): check your API key in Settings or `ANTHROPIC_API_KEY`.
- If you target Sonnet 4.5 and get model not found: use OpenRouter with model `anthropic/claude-sonnet-4.5` and set `OPENROUTER_API_KEY`.
- If you see validation errors for `max_tokens`: lower the configured value.
 - If YouTube subtitles are not fetched: ensure `yt-dlp` is installed and on PATH (`pip install yt-dlp`; macOS: `brew install yt-dlp`).

### py2app launch error (macOS)
- "ModuleNotFoundError: No module named 'imp'" → prefer the lightweight bundle (`./create_app_bundle.sh`).

### Tray icon not visible (Windows)
- Check the hidden icons chevron and ensure the app is running.

## System Requirements

- **OS:** macOS 10.15+
- **Python:** 3.9+
- **RAM:** 50MB
- **Disk Space:** 10MB + space for ePub files

## Contributing

This project is in active development.

## License

MIT License - Feel free to use and modify as needed.

## Support

For issues or questions:
- Check the troubleshooting section above
- Review the development plan in `plan.md`
- Create an issue in the repository

---

**Current Version:** 1.0.0 (Menubar + Windows Tray)
**Last Updated:** November 2025
