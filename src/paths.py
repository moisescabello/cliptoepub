#!/usr/bin/env python3
"""
Cross‑platform paths and light migration helpers for ClipToEpub.

Centralizes locations for configuration, history and update-check files.
On Windows, stores data under %APPDATA%\ClipToEpub. On macOS, keeps the
existing locations for compatibility.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def is_windows() -> bool:
    return sys.platform.startswith("win")


def _appdata_dir() -> Path:
    """Return %APPDATA% directory on Windows, with a sensible fallback."""
    env = os.environ.get("APPDATA")
    if env:
        return Path(env)
    # Fallback for unusual environments
    return Path.home() / "AppData" / "Roaming"


def get_default_output_dir() -> Path:
    """Default output directory for generated ePubs."""
    # Align with project docs and scripts: ~/Documents/ClipboardEpubs
    return Path.home() / "Documents" / "ClipboardEpubs"


def get_config_path() -> Path:
    """Return platform-appropriate configuration file path."""
    if is_windows():
        return _appdata_dir() / "ClipToEpub" / "config.json"
    # macOS: align with project docs: clipboard-to-epub.json
    return Path.home() / "Library" / "Preferences" / "clipboard-to-epub.json"


def get_history_path() -> Path:
    """Return platform-appropriate history file path."""
    if is_windows():
        return _appdata_dir() / "ClipToEpub" / "history.json"
    # macOS: align with docs: ~/.clipboard_to_epub/history.json
    return Path.home() / ".clipboard_to_epub" / "history.json"


def get_cache_dir() -> Path:
    """Return platform-appropriate cache directory path."""
    if is_windows():
        return _appdata_dir() / "ClipToEpub" / "cache"
    # macOS/Linux: keep alongside history under ~/.clipboard_to_epub
    return Path.home() / ".clipboard_to_epub" / "cache"


def get_update_check_path() -> Path:
    """Return file used to cache update-check metadata."""
    if is_windows():
        return _appdata_dir() / "ClipToEpub" / "cliptoepub-update.json"
    # macOS: use clipboard-to-epub-update.json
    return Path.home() / "Library" / "Preferences" / "clipboard-to-epub-update.json"


def _safe_move(src: Path, dst: Path) -> bool:
    """Move file from src to dst creating parent directories. Returns True if moved."""
    try:
        if not src.exists() or dst.exists():
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return True
    except (OSError, IOError, PermissionError) as e:
        # Log but don't raise - migration is not critical
        print(f"Warning: Could not move {src} to {dst}: {e}")
        return False


def migrate_legacy_paths() -> dict:
    """
    On Windows, migrate files that older versions may have created under Unix-like
    paths in the user profile to the proper %APPDATA% locations.

    Returns a dict with migration results for observability.
    """
    results = {
        "config_migrated": False,
        "history_migrated": False,
        "update_migrated": False,
        "cache_migrated": False,
    }

    # Windows: migrate from Unix-like paths to %APPDATA%
    if is_windows():
        legacy_config = Path.home() / "Library" / "Preferences" / "clipboard-to-epub.json"
        legacy_history = Path.home() / ".clipboard_to_epub" / "history.json"
        legacy_update = Path.home() / "Library" / "Preferences" / "clipboard-to-epub-update.json"
        legacy_cache_dir = Path.home() / ".clipboard_to_epub" / "cache"

        new_config = get_config_path()
        new_history = get_history_path()
        new_update = get_update_check_path()
        new_cache_dir = get_cache_dir()

        if _safe_move(legacy_config, new_config):
            results["config_migrated"] = True
        if _safe_move(legacy_history, new_history):
            results["history_migrated"] = True
        if _safe_move(legacy_update, new_update):
            results["update_migrated"] = True

        # Migrate cache directory if present (move entire folder)
        try:
            if legacy_cache_dir.exists() and not new_cache_dir.exists():
                new_cache_dir.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.move(str(legacy_cache_dir), str(new_cache_dir))
                results["cache_migrated"] = True
        except (OSError, IOError, PermissionError) as e:
            print(f"Warning: Could not migrate cache directory: {e}")

        for p in (new_config, new_history, new_update, new_cache_dir):
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
            except (OSError, IOError, PermissionError) as e:
                print(f"Warning: Could not create directory {p.parent}: {e}")
                # Continue - app may still work with defaults
        return results

    # macOS: migrate legacy names used previously
    try:
        # Preferences files renamed from cliptoepub*.json to clipboard-to-epub*.json
        legacy_cfg = Path.home() / "Library" / "Preferences" / "cliptoepub.json"
        legacy_upd = Path.home() / "Library" / "Preferences" / "cliptoepub-update.json"
        target_cfg = get_config_path()
        target_upd = get_update_check_path()
        if _safe_move(legacy_cfg, target_cfg):
            results["config_migrated"] = True
        if _safe_move(legacy_upd, target_upd):
            results["update_migrated"] = True

        # History dir renamed from ~/.cliptoepub to ~/.clipboard_to_epub
        legacy_hist = Path.home() / ".cliptoepub" / "history.json"
        target_hist = get_history_path()
        if _safe_move(legacy_hist, target_hist):
            results["history_migrated"] = True

        # Cache dir renamed from ~/.cliptoepub/cache to ~/.clipboard_to_epub/cache
        legacy_cache_dir = Path.home() / ".cliptoepub" / "cache"
        target_cache_dir = get_cache_dir()
        try:
            if legacy_cache_dir.exists() and not target_cache_dir.exists():
                target_cache_dir.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.move(str(legacy_cache_dir), str(target_cache_dir))
                results["cache_migrated"] = True
        except (OSError, IOError, PermissionError) as e:
            print(f"Warning: Could not migrate cache directory: {e}")

        for p in (target_cfg, target_upd, target_hist, target_cache_dir):
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
            except (OSError, IOError, PermissionError) as e:
                print(f"Warning: Could not create directory {p.parent}: {e}")
    except (OSError, AttributeError) as e:
        # Migration failed - not critical
        print(f"Warning: Legacy migration failed: {e}")

    # Ensure default output directory exists lazily (created by app modules as needed)
    return results
