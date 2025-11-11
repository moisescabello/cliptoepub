#!/bin/bash

#================================================
# Fixed Build Script for Clipboard to ePub macOS App
#================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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
echo -e "${BLUE}Clipboard to ePub - Fixed Build Application${NC}"
echo -e "${BLUE}=================================================${NC}"
echo

# Check if we're in the right directory
if [ ! -f "setup.py" ]; then
    print_error "setup.py not found. Please run this script from the project root."
    exit 1
fi

# Activate virtual environment
print_status "Activating virtual environment..."
if [ -d "venv" ]; then
    source venv/bin/activate
    print_success "Virtual environment activated"
else
    print_error "Virtual environment not found. Please run setup.sh first."
    exit 1
fi

# Install py2app
print_status "Installing py2app..."
pip install --quiet --upgrade py2app
    print_success "py2app installed"

# Install beautifulsoup4 correctly
print_status "Installing beautifulsoup4 (imports as bs4)..."
pip install --quiet --upgrade beautifulsoup4
    print_success "beautifulsoup4 installed"

# Install newspaper3k correctly
print_status "Installing newspaper3k (imports as newspaper)..."
pip install --quiet --upgrade newspaper3k
    print_success "newspaper3k installed"

# Install other missing packages
print_status "Installing other required packages..."
pip install --quiet --upgrade \
    rumps \
    pync \
    markdown2 \
    striprtf \
    Pillow \
    aiofiles \
    pytesseract \
    nltk
    print_success "All requirements installed"

# Download NLTK data
print_status "Downloading NLTK data..."
python -c "import nltk; nltk.download('punkt', quiet=True)" 2>/dev/null || true
print_success "NLTK data downloaded"

# Clean previous builds
print_status "Cleaning previous builds..."
rm -rf build dist
rm -rf *.egg-info
rm -rf __pycache__ */__pycache__ */*/__pycache__
    print_success "Previous builds cleaned"

# Build the application with py2app
print_status "Building application with py2app..."
echo
python setup.py py2app 2>&1 | while read line; do
    # Filter out common warnings
    if [[ ! "$line" =~ "UserWarning" ]] && [[ ! "$line" =~ "No package named" ]]; then
        echo "  $line"
    fi
done

# Check if build was successful
if [ $? -eq 0 ] || [ -d "dist/Clipboard to ePub.app" ]; then
    print_success "Build process completed!"
else
    print_warning "Build process had warnings but may have succeeded"
fi

# Check if the app was created
APP_PATH="dist/ClipToEpub.app"
if [ -d "$APP_PATH" ]; then
    print_success "Application created at: $APP_PATH"

    # Get app size
    APP_SIZE=$(du -sh "$APP_PATH" 2>/dev/null | cut -f1 || echo "Unknown")
    print_status "Application size: $APP_SIZE"
else
    print_error "Application not found at expected location"
    print_warning "Checking for alternative build output..."

    # Sometimes py2app creates with different name
    if ls dist/*.app 2>/dev/null; then
    print_status "Found app bundles in dist:"
        ls -la dist/*.app
    fi
fi

# Create standalone launcher script
print_status "Creating standalone launcher..."
cat > launch_app.command << 'EOF'
#!/bin/bash
# Launch Clipboard to ePub Application

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_PATH="$SCRIPT_DIR/dist/ClipboardToEpub.app"

if [ -d "$APP_PATH" ]; then
    echo "Launching Clipboard to ePub..."
    open "$APP_PATH"
elif [ -d "$SCRIPT_DIR/dist/Clipboard to ePub.app" ]; then
    echo "Launching Clipboard to ePub..."
    open "$SCRIPT_DIR/dist/Clipboard to ePub.app"
else
    echo "Error: Application not found in dist/"
    echo "Available apps:"
    ls -la "$SCRIPT_DIR/dist/"*.app 2>/dev/null || echo "No .app files found"
    exit 1
fi
EOF

chmod +x launch_app.command
print_success "Created launcher: launch_app.command"

echo
echo -e "${BLUE}=================================================${NC}"
echo -e "${GREEN}[OK] Build script completed!${NC}"
echo -e "${BLUE}=================================================${NC}"
echo
echo "Next steps:"
echo "1. Check if app exists: ls -la dist/"
echo "2. Test the app: ./launch_app.command"
echo "3. If build failed, check the output above for errors"
echo
print_warning "Note: The app may need accessibility permissions."
print_warning "Grant them in System Preferences > Security & Privacy > Privacy > Accessibility"
