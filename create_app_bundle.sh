#!/bin/bash

#================================================
# Create macOS App Bundle for ClipToEpub
# Alternative solution without py2app
#================================================

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}Creating ClipToEpub App Bundle${NC}"
echo -e "${BLUE}=================================================${NC}"

# App name and paths
APP_NAME="ClipToEpub"
APP_DIR="$APP_NAME.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

# Remove old app if exists
rm -rf "$APP_DIR"

# Create app bundle structure
echo "Creating app bundle structure..."
mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"

# Copy Python scripts and dependencies
echo "Copying application files..."
cp -r src "$RESOURCES_DIR/"
cp -r templates "$RESOURCES_DIR/" 2>/dev/null || true
cp -r resources "$RESOURCES_DIR/" 2>/dev/null || true
cp content_processor.py "$RESOURCES_DIR/" 2>/dev/null || true

# Copy icon
if [ -f "resources/icon.icns" ]; then
    cp "resources/icon.icns" "$RESOURCES_DIR/app.icns"
    echo -e "${GREEN}[OK] Icon copied${NC}"
fi

# Create the main executable script
cat > "$MACOS_DIR/ClipToEpub" << 'EOF'
#!/bin/bash

# Get the Resources directory
RESOURCES_DIR="$(dirname "$0")/../Resources"
PROJECT_DIR="$(dirname "$0")/../../.."

# Setup Python path
export PYTHONPATH="$RESOURCES_DIR:$PYTHONPATH"

# Check for Python installation
if ! command -v python3 &> /dev/null; then
    osascript -e 'display dialog "Python 3 is not installed. Please install Python from python.org" buttons {"OK"} default button "OK"'
    exit 1
fi

# Create virtual environment if needed (first run)
VENV_DIR="$HOME/.cliptoepub-venv"
if [ ! -d "$VENV_DIR" ]; then
    osascript -e 'display notification "Setting up ClipToEpub..." with title "First Run"'
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"

    # Install dependencies (include Qt for modern settings)
    pip install --quiet ebooklib pyperclip pynput rumps pync markdown2 striprtf beautifulsoup4 lxml requests Pillow PySide6 2>/dev/null || {
        osascript -e 'display dialog "Failed to install dependencies. Please check your internet connection." buttons {"OK"} default button "OK"'
        exit 1
    }
else
    source "$VENV_DIR/bin/activate"
fi

# Launch the application
cd "$RESOURCES_DIR"

# Try menubar app first
if [ -f "src/menubar_app.py" ]; then
    python src/menubar_app.py
else
    osascript -e 'display dialog "Application files not found!" buttons {"OK"} default button "OK"'
    exit 1
fi
EOF

# Make executable
chmod +x "$MACOS_DIR/ClipToEpub"

# Create Info.plist
cat > "$CONTENTS_DIR/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>ClipToEpub</string>
    <key>CFBundleDisplayName</key>
    <string>ClipToEpub</string>
    <key>CFBundleIdentifier</key>
    <string>com.cliptoepub.app</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>CFBundleExecutable</key>
    <string>ClipToEpub</string>
    <key>CFBundleIconFile</key>
    <string>app.icns</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSUIElement</key>
    <true/>
    <key>NSAppleEventsUsageDescription</key>
    <string>This app needs to monitor keyboard events for global hotkeys.</string>
    <key>NSAccessibilityUsageDescription</key>
    <string>This app needs accessibility permissions to capture global hotkeys.</string>
</dict>
</plist>
EOF

echo -e "${GREEN}[OK] App bundle created successfully!${NC}"
echo
echo "Application created: $APP_DIR"
echo
echo "To use the app:"
echo "1. Move it to Applications folder:"
echo "   mv '$APP_DIR' /Applications/"
echo "2. Right-click and select 'Open' on first launch"
echo "3. Grant accessibility permissions when prompted"
echo
echo "Or test it now:"
echo "   open '$APP_DIR'"
echo
echo -e "${BLUE}=================================================${NC}"
