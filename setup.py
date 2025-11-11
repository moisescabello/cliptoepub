"""
setup.py for ClipToEpub
Configures py2app for building macOS application bundle
"""

from setuptools import setup
import os
import sys

# Application metadata
APP_NAME = 'ClipToEpub'
APP_VERSION = '1.0.0'
APP_BUNDLE_ID = 'com.cliptoepub.app'
APP_AUTHOR = 'ClipToEpub Team'
APP_EMAIL = 'contact@cliptoepub.app'

# Determine the main app file based on what the user wants
# Default to menubar app which provides the full GUI experience
APP = ['src/menubar_app.py']

# Data files to include
DATA_FILES = [
    ('templates', [
        'templates/default.css',
        'templates/minimal.css',
        'templates/modern.css'
    ]),
]

# Resources
RESOURCES = []
if os.path.exists('resources/icon.icns'):
    RESOURCES.append('resources/icon.icns')

# Additional Python packages to include
PACKAGES = [
    'ebooklib',
    'pyperclip',
    'pynput',
    'rumps',
    'pync',
    'markdown2',
    'striprtf',
    'newspaper',  # Changed from newspaper3k
    'bs4',  # Changed from beautifulsoup4
    'lxml',
    'lxml_html_clean',
    'chardet',
    'requests',
    'urllib3',
    'certifi',
    'PIL',
    'aiofiles',
    'asyncio',
    'pytesseract',
    'dateutil',
    'nltk',
]

# py2app options
OPTIONS = {
    'argv_emulation': False,  # Don't use argv emulation for better performance
    'iconfile': 'resources/icon.icns' if os.path.exists('resources/icon.icns') else None,
    'plist': {
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleGetInfoString': f'{APP_NAME} {APP_VERSION}',
        'CFBundleIdentifier': APP_BUNDLE_ID,
        'CFBundleVersion': APP_VERSION,
        'CFBundleShortVersionString': APP_VERSION,
        'NSHumanReadableCopyright': f'Copyright © 2024 {APP_AUTHOR}',
        'LSUIElement': True,  # Hide from dock (menubar app)
        'NSHighResolutionCapable': True,  # Enable retina display support
        'NSRequiresAquaSystemAppearance': False,  # Support dark mode
        'LSMinimumSystemVersion': '10.15',  # Minimum macOS version

        # Privacy permissions
        'NSAppleEventsUsageDescription': 'This app needs to monitor keyboard events for global hotkeys.',
        'NSAccessibilityUsageDescription': 'This app needs accessibility permissions to capture global hotkeys.',
    },
    'packages': PACKAGES,
    'includes': [
        'tkinter',  # For config window
        'pkg_resources',  # For resource management
        'multiprocessing',  # For async processing
        'concurrent.futures',  # For thread pool
        'json',  # For config files
        'sqlite3',  # For history database
        'importlib',  # For dynamic imports
        'importlib.util',
        'importlib.machinery',
        'Foundation',  # macOS Framework
        'AppKit',  # macOS Framework
        'Cocoa',  # macOS Framework
        'CoreFoundation',  # macOS Framework
        'objc',  # PyObjC bridge
        'lxml_html_clean',  # Clean HTML module
        'src.imp_patch',  # Compatibility patch for imp
        'src.converter',
        'src.config_window',
        'src.edit_window',
        'src.history_manager',
        'content_processor',
        'src.image_handler',
        'src.update_checker',
    ],
    'excludes': [
        'matplotlib',  # Exclude unnecessary large packages
        'numpy',
        'scipy',
        'pandas',
        'pytest',
        'ipython',
    ],
    'resources': RESOURCES,
    'strip': True,  # Strip debug symbols for smaller size
    'optimize': 2,  # Optimize bytecode
    'compressed': True,  # Compress the app
    'semi_standalone': False,  # Create fully standalone app
}

# Setup configuration
setup(
    name=APP_NAME,
    app=APP,
    author=APP_AUTHOR,
    author_email=APP_EMAIL,
    version=APP_VERSION,
    description='Convert clipboard content to ePub files with a global hotkey',
    long_description='''
    Clipboard to ePub is a powerful macOS application that converts your clipboard
    content into professionally formatted ePub files with just a keyboard shortcut.

    Features:
    - Global hotkey conversion (Cmd+Shift+E)
    - Support for multiple formats (Markdown, HTML, RTF, URLs)
    - Image processing and OCR
    - Multi-clip accumulator
    - Conversion history
    - Menubar interface
    - Customizable settings
    ''',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    install_requires=[
        'ebooklib>=0.18',
        'pyperclip>=1.8.2',
        'pynput>=1.7.6',
        'rumps>=0.4.0',
        'pync>=2.0.3',
        'markdown2>=2.4.0',
        'striprtf>=0.0.22',
        'newspaper3k>=0.2.8',
        'beautifulsoup4>=4.11.0',  # This installs as 'bs4'
        'lxml>=4.9.3',
        'chardet>=5.0.0',
        'requests>=2.28.0',
        'Pillow>=9.0.0',
        'aiofiles>=22.0.0',
        'pytesseract>=0.3.10',
        'python-dateutil>=2.8.2',
        'nltk>=3.8',
    ],
    python_requires='>=3.9',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: MacOS X',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS :: MacOS X',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Office/Business',
        'Topic :: Text Processing',
        'Topic :: Utilities',
    ],
    project_urls={
        'Bug Reports': 'https://github.com/clipboardtoepub/issues',
        'Source': 'https://github.com/clipboardtoepub/clipboard-to-epub',
        'Documentation': 'https://clipboardtoepub.readthedocs.io',
    },
)
