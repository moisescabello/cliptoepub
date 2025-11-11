#!/usr/bin/env python3
"""
Update Checker for Clipboard to ePub
Checks for new versions and manages updates
"""

import requests
import json
import os
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Callable
import webbrowser
# Robust import for paths whether run from repo root or src/
try:
    from src import paths as paths  # type: ignore
except Exception:
    import paths  # type: ignore
import tempfile

# Configure logging
logger = logging.getLogger(__name__)

class UpdateChecker:
    """Manages application updates"""

    # Version configuration
    CURRENT_VERSION = "1.0.0"
    APP_NAME = "Clipboard to ePub"

    # Update URLs
    GITHUB_API_URL = "https://api.github.com/repos/clipboardtoepub/clipboard-to-epub/releases/latest"
    RELEASES_PAGE = "https://github.com/clipboardtoepub/clipboard-to-epub/releases"

    # Configuration
    CHECK_INTERVAL_HOURS = 24  # Check for updates every 24 hours
    UPDATE_CHECK_FILE = paths.get_update_check_path()

    def __init__(self, auto_check: bool = True):
        """
        Initialize update checker

        Args:
            auto_check: Whether to automatically check for updates
        """
        self.auto_check = auto_check
        self.last_check_data = self._load_check_data()

    def _load_check_data(self) -> Dict:
        """Load last update check data"""
        try:
            if self.UPDATE_CHECK_FILE.exists():
                with open(self.UPDATE_CHECK_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading update check data: {e}")

        return {
            'last_check': None,
            'available_version': None,
            'dismissed_version': None
        }

    def _save_check_data(self):
        """Save update check data"""
        try:
            self.UPDATE_CHECK_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.UPDATE_CHECK_FILE, 'w') as f:
                json.dump(self.last_check_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving update check data: {e}")

    def should_check_for_updates(self) -> bool:
        """Determine if we should check for updates"""
        if not self.auto_check:
            return False

        last_check = self.last_check_data.get('last_check')
        if not last_check:
            return True

        try:
            last_check_time = datetime.fromisoformat(last_check)
            time_since_check = datetime.now() - last_check_time
            return time_since_check > timedelta(hours=self.CHECK_INTERVAL_HOURS)
        except (ValueError, TypeError) as e:
            logger.debug(f"Invalid last_check timestamp: {e}")
            return True

    def parse_version(self, version_string: str) -> tuple:
        """
        Parse version string to tuple for comparison

        Args:
            version_string: Version like "1.0.0" or "v1.0.0"

        Returns:
            Tuple of (major, minor, patch)
        """
        version = version_string.lstrip('v')
        parts = version.split('.')
        try:
            return tuple(int(p) for p in parts[:3])
        except (ValueError, IndexError, AttributeError) as e:
            logger.debug(f"Invalid version string '{version_string}': {e}")
            return (0, 0, 0)

    def check_for_updates(self, force: bool = False) -> Optional[Dict]:
        """
        Check if updates are available

        Args:
            force: Force check even if recently checked

        Returns:
            Update info dict or None if no updates
        """
        if not force and not self.should_check_for_updates():
            # Return cached result if available
            if self.last_check_data.get('available_version'):
                return self._format_update_info()
            return None

        logger.info("Checking for updates...")

        try:
            # Make API request
            headers = {'Accept': 'application/vnd.github.v3+json'}
            response = requests.get(self.GITHUB_API_URL, headers=headers, timeout=5)

            if response.status_code == 200:
                data = response.json()
                latest_version = data.get('tag_name', '').lstrip('v')

                # Update check data
                self.last_check_data['last_check'] = datetime.now().isoformat()

                # Compare versions
                current = self.parse_version(self.CURRENT_VERSION)
                latest = self.parse_version(latest_version)

                if latest > current:
                    # New version available
                    self.last_check_data['available_version'] = latest_version

                    # Get download URL for DMG
                    download_url = None
                    for asset in data.get('assets', []):
                        if asset['name'].endswith('.dmg'):
                            download_url = asset['browser_download_url']
                            break

                    update_info = {
                        'available': True,
                        'current_version': self.CURRENT_VERSION,
                        'latest_version': latest_version,
                        'release_name': data.get('name', ''),
                        'release_notes': data.get('body', ''),
                        'download_url': download_url,
                        'release_url': data.get('html_url', self.RELEASES_PAGE),
                        'published_at': data.get('published_at', '')
                    }

                    self._save_check_data()
                    logger.info(f"Update available: {latest_version}")
                    return update_info
                else:
                    # No update available
                    self.last_check_data['available_version'] = None
                    self._save_check_data()
                    logger.info("No updates available")
                    return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error checking for updates: {e}")
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")

        return None

    def _format_update_info(self) -> Optional[Dict]:
        """Format cached update info"""
        if not self.last_check_data.get('available_version'):
            return None

        return {
            'available': True,
            'current_version': self.CURRENT_VERSION,
            'latest_version': self.last_check_data['available_version'],
            'cached': True
        }

    def dismiss_update(self, version: str):
        """
        Dismiss a specific update version

        Args:
            version: Version to dismiss
        """
        self.last_check_data['dismissed_version'] = version
        self.last_check_data['available_version'] = None
        self._save_check_data()
        logger.info(f"Dismissed update {version}")

    def is_dismissed(self, version: str) -> bool:
        """
        Check if a version was dismissed

        Args:
            version: Version to check

        Returns:
            True if dismissed
        """
        return self.last_check_data.get('dismissed_version') == version

    def download_update(self, download_url: str,
                       progress_callback: Optional[Callable] = None) -> Optional[Path]:
        """
        Download update DMG file

        Args:
            download_url: URL to download from
            progress_callback: Callback for progress (bytes_downloaded, total_bytes)

        Returns:
            Path to downloaded file or None on error
        """
        try:
            # Download to temporary location (cross-platform temp dir)
            download_path = Path(tempfile.gettempdir()) / (
                f"ClipboardToEpub-update-{datetime.now().strftime('%Y%m%d%H%M%S')}.dmg"
            )

            logger.info(f"Downloading update from {download_url}")

            response = requests.get(download_url, stream=True, timeout=20)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0) or 0)

            downloaded = 0
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_callback:
                            progress_callback(downloaded, total_size)

            logger.info(f"Download complete: {download_path}")
            return download_path

        except Exception as e:
            logger.error(f"Error downloading update: {e}")
            return None

    def open_download_page(self, url: Optional[str] = None):
        """
        Open download page in browser

        Args:
            url: URL to open (defaults to releases page)
        """
        url = url or self.RELEASES_PAGE
        logger.info(f"Opening download page: {url}")
        webbrowser.open(url)

    def install_update(self, dmg_path: Path) -> bool:
        """
        Open DMG file for installation

        Args:
            dmg_path: Path to DMG file

        Returns:
            True if successful
        """
        try:
            logger.info(f"Opening DMG for installation: {dmg_path}")
            subprocess.run(['open', str(dmg_path)], check=True)
            return True
        except Exception as e:
            logger.error(f"Error opening DMG: {e}")
            return False

    def get_update_message(self, update_info: Dict) -> str:
        """
        Generate user-friendly update message

        Args:
            update_info: Update information dict

        Returns:
            Formatted message string
        """
        if not update_info or not update_info.get('available'):
            return "You're running the latest version!"

        current = update_info.get('current_version', self.CURRENT_VERSION)
        latest = update_info.get('latest_version', 'unknown')

        message = f"""
Clipboard to ePub Update Available!

Current version: {current}
New version: {latest}

What's new:
{update_info.get('release_notes', 'Bug fixes and improvements')[:500]}

Would you like to download the update?
"""
        return message.strip()


class AutoUpdater:
    """Manages automatic update checks in background"""

    def __init__(self, update_checker: UpdateChecker,
                 notification_callback: Optional[Callable] = None):
        """
        Initialize auto updater

        Args:
            update_checker: UpdateChecker instance
            notification_callback: Callback when update is available
        """
        self.update_checker = update_checker
        self.notification_callback = notification_callback
        self.checking = False

    def check_in_background(self):
        """Check for updates in background thread"""
        if self.checking:
            return

        import threading

        def _check():
            self.checking = True
            try:
                update_info = self.update_checker.check_for_updates()
                if update_info and update_info.get('available'):
                    version = update_info.get('latest_version')

                    # Don't notify about dismissed versions
                    if not self.update_checker.is_dismissed(version):
                        if self.notification_callback:
                            self.notification_callback(update_info)
            finally:
                self.checking = False

        thread = threading.Thread(target=_check, daemon=True)
        thread.start()


def main():
    """Test update checker"""
    import sys

    # Setup logging
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    checker = UpdateChecker(auto_check=True)

    print("Clipboard to ePub - Update Checker")
    print("=" * 40)
    print(f"Current version: {checker.CURRENT_VERSION}")
    print("Checking for updates...")

    update_info = checker.check_for_updates(force=True)

    if update_info and update_info.get('available'):
        print("\n" + checker.get_update_message(update_info))

        response = input("\nDownload update? (y/n): ")
        if response.lower() == 'y':
            if update_info.get('download_url'):
                print("Opening download page...")
                checker.open_download_page(update_info['download_url'])
            else:
                print("Opening releases page...")
                checker.open_download_page()
    else:
        print("\n[OK] You're running the latest version!")

    print("\nUpdate check complete.")


if __name__ == "__main__":
    main()
