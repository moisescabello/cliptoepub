#!/bin/bash

# Clipboard to ePub - Installation Script
# Phase 1 Prototype Setup

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}=================================================${NC}"
    echo -e "${BLUE}Clipboard to ePub - Installation Script${NC}"
    echo -e "${BLUE}=================================================${NC}"
    echo ""
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

print_info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

check_python() {
    print_info "Checking Python installation..."

    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 9 ]; then
            print_success "Python $PYTHON_VERSION found"
            return 0
        else
            print_error "Python 3.9+ required. Found: Python $PYTHON_VERSION"
            return 1
        fi
    else
        print_error "Python 3 not found"
        return 1
    fi
}

setup_venv() {
    print_info "Setting up virtual environment..."

    if [ -d "venv" ]; then
        print_warning "Virtual environment already exists. Removing old one..."
        rm -rf venv
    fi

    python3 -m venv venv
    print_success "Virtual environment created"
}

activate_venv() {
    print_info "Activating virtual environment..."
    source venv/bin/activate
    print_success "Virtual environment activated"
}

install_dependencies() {
    print_info "Installing dependencies..."

    # Upgrade pip first
    pip install --upgrade pip > /dev/null 2>&1

    # Install requirements
    pip install -r requirements.txt

    print_success "Dependencies installed"
}

create_output_directory() {
    print_info "Creating output directory..."

    OUTPUT_DIR="$HOME/Documents/ClipboardEpubs"

    if [ ! -d "$OUTPUT_DIR" ]; then
        mkdir -p "$OUTPUT_DIR"
        print_success "Output directory created: $OUTPUT_DIR"
    else
        print_info "Output directory already exists: $OUTPUT_DIR"
    fi
}

check_permissions() {
    print_info "Checking system permissions..."

    # Check if Terminal has accessibility permissions
    # This is a simplified check - actual permission needs to be granted manually

    print_warning "IMPORTANT: Accessibility permissions required!"
    echo ""
    echo "  To use global hotkeys, you need to grant accessibility permissions:"
    echo "  1. Open System Preferences"
    echo "  2. Go to Security & Privacy → Privacy → Accessibility"
    echo "  3. Add Terminal.app (or your terminal application) to the list"
    echo "  4. Make sure it's checked/enabled"
    echo ""
    read -p "Have you granted accessibility permissions? (y/n): " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Please grant permissions before running the application"
    else
    print_success "Permissions acknowledged"
    fi
}

create_launcher() {
    print_info "Creating launcher script..."

    cat > run.sh << 'EOF'
#!/bin/bash
# Launcher script for Clipboard to ePub

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Starting Clipboard to ePub...${NC}"

# Activate virtual environment
source venv/bin/activate

# Run the application (menu bar)
python src/menubar_app.py "$@"

# Deactivate virtual environment on exit
deactivate
EOF

    chmod +x run.sh
    print_success "Launcher script created: run.sh"
}

test_installation() {
    print_info "Testing installation..."

    # Test imports
    python3 -c "
import sys
sys.path.insert(0, 'src')
try:
    import pyperclip
    import ebooklib
    import pynput
    print('[OK] All modules imported successfully')
except ImportError as e:
    print(f'[ERROR] Import error: {e}')
    sys.exit(1)
"

    if [ $? -eq 0 ]; then
    print_success "Installation test passed"
        return 0
    else
        print_error "Installation test failed"
        return 1
    fi
}

print_instructions() {
    echo ""
    echo -e "${GREEN}=================================================${NC}"
    echo -e "${GREEN}[OK] Installation Complete!${NC}"
    echo -e "${GREEN}=================================================${NC}"
    echo ""
    echo "How to use:"
    echo ""
    echo "  1. Start the application:"
    echo "     ${BLUE}./run.sh${NC}"
    echo ""
    echo "  2. Copy any text to your clipboard"
    echo ""
    echo "  3. Press ${BLUE}Cmd + Shift + E${NC} to convert"
    echo ""
    echo "  4. Find your ePub files in:"
    echo "     ${BLUE}~/Documents/ClipboardEpubs/${NC}"
    echo ""
    echo "  5. Press ${BLUE}ESC${NC} to quit"
    echo ""
    echo "For more information, see README.md"
    echo ""
}

main() {
    print_header

    # Check Python installation
    if ! check_python; then
        print_error "Please install Python 3.9 or later"
        exit 1
    fi

    # Setup virtual environment
    setup_venv

    # Activate virtual environment
    activate_venv

    # Install dependencies
    install_dependencies

    # Create output directory
    create_output_directory

    # Create launcher script
    create_launcher

    # Test installation
    if ! test_installation; then
        print_error "Installation failed. Please check the errors above."
        exit 1
    fi

    # Check permissions
    check_permissions

    # Print instructions
    print_instructions
}

# Run main function
main
