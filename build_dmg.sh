#!/bin/bash

#================================================
# DMG Builder for ClipToEpub
#================================================

set -e  # Exit on error

# Configuration
APP_NAME="ClipToEpub"
APP_PATH="dist/ClipToEpub.app"
DMG_NAME="ClipToEpub-1.0.0"
DMG_VOLUME_NAME="ClipToEpub"
DMG_BACKGROUND="resources/dmg_background.png"
WINDOW_WIDTH=600
WINDOW_HEIGHT=400
ICON_SIZE=128

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

print_success() {
    echo -e "${GREEN}[OK] $1${NC}"
}

print_error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}Creating DMG for ClipToEpub${NC}"
echo -e "${BLUE}=================================================${NC}"
echo

# Check if app exists
if [ ! -d "$APP_PATH" ]; then
    print_error "Application not found at $APP_PATH"
    print_error "Please run build_app.sh first"
    exit 1
fi

# Clean up any existing DMG
print_status "Cleaning up previous DMG files..."
rm -f "${DMG_NAME}.dmg"
rm -f "${DMG_NAME}-temp.dmg"
rm -rf dmg-content
print_success "Cleanup complete"

# Create DMG content directory
print_status "Creating DMG content directory..."
mkdir -p dmg-content
print_success "Created dmg-content directory"

# Copy application
print_status "Copying application..."
cp -R "$APP_PATH" "dmg-content/"
print_success "Application copied"

# Create Applications symlink
print_status "Creating Applications symlink..."
ln -s /Applications "dmg-content/Applications"
print_success "Applications symlink created"

# Copy documentation files
print_status "Copying documentation..."
cp README.md "dmg-content/README.md" 2>/dev/null || true
cp QUICK_START.md "dmg-content/Quick Start.md" 2>/dev/null || true
print_success "Documentation copied"

# Create DMG background image if it doesn't exist
if [ ! -f "$DMG_BACKGROUND" ]; then
    print_warning "DMG background not found, creating one..."
    python3 << 'PYTHON_END'
from PIL import Image, ImageDraw, ImageFont
import os

def create_dmg_background():
    """Create a simple DMG background image"""
    width, height = 600, 400
    img = Image.new('RGBA', (width, height), (245, 245, 247, 255))
    draw = ImageDraw.Draw(img)

    # Draw gradient
    for i in range(height):
        color_value = 245 - int(i / height * 20)
        color = (color_value, color_value, color_value + 2, 255)
        draw.rectangle([0, i, width, i+1], fill=color)

    # Draw title area
    draw.rounded_rectangle([20, 20, width-20, 80], radius=10,
                          fill=(70, 130, 180, 200), outline=(50, 100, 150, 255), width=2)

    # Add text
    try:
        font_size = 32
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except:
        font = ImageFont.load_default()

    text = "ClipToEpub"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_x = (width - text_width) // 2
    draw.text((text_x, 35), text, fill=(255, 255, 255, 255), font=font)

    # Add instruction text
    try:
        font_size = 14
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except:
        font_small = ImageFont.load_default()

    instruction = "Drag app to Applications folder to install"
    bbox = draw.textbbox((0, 0), instruction, font=font_small)
    text_width = bbox[2] - bbox[0]
    text_x = (width - text_width) // 2
    draw.text((text_x, height - 40), instruction, fill=(100, 100, 100, 255), font=font_small)

    # Add arrow
    arrow_y = height // 2
    arrow_start_x = width // 2 - 100
    arrow_end_x = width // 2 + 100

    # Arrow shaft
    draw.rectangle([arrow_start_x, arrow_y - 2, arrow_end_x, arrow_y + 2],
                  fill=(100, 100, 100, 150))

    # Arrow head
    draw.polygon([(arrow_end_x, arrow_y - 10),
                 (arrow_end_x + 20, arrow_y),
                 (arrow_end_x, arrow_y + 10)],
                fill=(100, 100, 100, 150))

    # Save image
    os.makedirs('resources', exist_ok=True)
    img.save('resources/dmg_background.png')
    print("[OK] Created DMG background image")

create_dmg_background()
PYTHON_END
fi

# Create temporary DMG
print_status "Creating temporary DMG..."
hdiutil create -volname "${DMG_VOLUME_NAME}" \
    -srcfolder dmg-content \
    -ov -format UDRW \
    -size 100m \
    "${DMG_NAME}-temp.dmg"
print_success "Temporary DMG created"

# Mount temporary DMG
print_status "Mounting temporary DMG..."
device=$(hdiutil attach -readwrite -noverify -noautoopen "${DMG_NAME}-temp.dmg" | \
         egrep '^/dev/' | sed 1q | awk '{print $1}')
print_success "DMG mounted at ${device}"

# Wait for mount to complete
sleep 2

# Set custom icon positions and window properties using AppleScript
print_status "Configuring DMG window..."
osascript << EOF
tell application "Finder"
    tell disk "${DMG_VOLUME_NAME}"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {100, 100, ${WINDOW_WIDTH}, ${WINDOW_HEIGHT}}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to ${ICON_SIZE}

        -- Position the app icon
        set position of item "ClipToEpub.app" of container window to {150, 180}

        -- Position the Applications symlink
        set position of item "Applications" of container window to {450, 180}

        -- Position documentation if exists
        try
            set position of item "README.md" of container window to {150, 320}
        end try
        try
            set position of item "Quick Start.md" of container window to {450, 320}
        end try

        update without registering applications
        delay 5
    end tell
end tell
EOF
print_success "DMG window configured"

# Set background image if it exists
if [ -f "$DMG_BACKGROUND" ]; then
    print_status "Setting background image..."
    cp "$DMG_BACKGROUND" "/Volumes/${DMG_VOLUME_NAME}/.background.png"

    osascript << EOF
tell application "Finder"
    tell disk "${DMG_VOLUME_NAME}"
        set viewOptions to the icon view options of container window
        set background picture of viewOptions to file ".background.png"
    end tell
end tell
EOF
    print_success "Background image set"
fi

# Hide background file
SetFile -a V "/Volumes/${DMG_VOLUME_NAME}/.background.png" 2>/dev/null || true

# Sync and unmount
print_status "Syncing and unmounting..."
sync
hdiutil detach "${device}"
print_success "DMG unmounted"

# Convert to compressed read-only DMG
print_status "Creating final compressed DMG..."
hdiutil convert "${DMG_NAME}-temp.dmg" \
    -format UDZO \
    -imagekey zlib-level=9 \
    -o "${DMG_NAME}.dmg"
print_success "Final DMG created"

# Clean up temporary files
print_status "Cleaning up temporary files..."
rm -f "${DMG_NAME}-temp.dmg"
rm -rf dmg-content
print_success "Cleanup complete"

# Get final DMG size
DMG_SIZE=$(du -h "${DMG_NAME}.dmg" | cut -f1)

echo
echo -e "${BLUE}=================================================${NC}"
echo -e "${GREEN}[OK] DMG created successfully!${NC}"
echo -e "${BLUE}=================================================${NC}"
echo
echo "DMG Details:"
echo "  Name: ${DMG_NAME}.dmg"
echo "  Size: ${DMG_SIZE}"
echo "  Location: $(pwd)/${DMG_NAME}.dmg"
echo
echo "To distribute:"
echo "1. Test the DMG by opening it"
echo "2. Sign it with your Developer ID (optional)"
echo "3. Notarize it for Gatekeeper (optional)"
echo "4. Upload to your distribution platform"
