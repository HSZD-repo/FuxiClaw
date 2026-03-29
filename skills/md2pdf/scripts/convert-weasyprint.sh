#!/bin/bash
#
# Markdown to PDF Converter using WeasyPrint
# 使用 WeasyPrint 将 Markdown 转换为 PDF
#
# Usage: bash convert-weasyprint.sh <input.md> [output.pdf]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Input validation
if [ $# -lt 1 ]; then
    echo -e "${RED}Error: Missing input file${NC}"
    echo "Usage: bash convert-weasyprint.sh <input.md> [output.pdf]"
    exit 1
fi

INPUT_FILE="$1"

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo -e "${RED}Error: Input file not found: $INPUT_FILE${NC}"
    exit 1
fi

# Determine output filename
if [ $# -ge 2 ]; then
    OUTPUT_FILE="$2"
else
    OUTPUT_FILE="${INPUT_FILE%.md}.pdf"
fi

echo -e "${YELLOW}Converting: $INPUT_FILE -> $OUTPUT_FILE${NC}"

# Check and install Python dependencies
check_python_deps() {
    if ! python3 -c "import markdown" 2>/dev/null; then
        echo -e "${YELLOW}Installing Python package: markdown...${NC}"
        python3 -m pip install markdown -q
    fi
    
    if ! python3 -c "import weasyprint" 2>/dev/null; then
        echo -e "${YELLOW}Installing Python package: weasyprint...${NC}"
        python3 -m pip install weasyprint -q
    fi
}

# Check and install fonts (macOS)
check_macos_fonts() {
    if ! fc-list | grep -q "Noto Sans CJK"; then
        echo -e "${YELLOW}Installing Noto CJK fonts...${NC}"
        if command -v brew &> /dev/null; then
            brew install --cask font-noto-sans-cjk-sc &>/dev/null || true
        fi
    fi
}

# Check and install fonts (Linux)
check_linux_fonts() {
    if ! fc-list | grep -q "Noto Sans CJK"; then
        echo -e "${YELLOW}Installing Noto CJK fonts...${NC}"
        if command -v yum &> /dev/null; then
            sudo yum install -y google-noto-sans-cjk-fonts &>/dev/null || true
        elif command -v apt-get &> /dev/null; then
            sudo apt-get update &>/dev/null
            sudo apt-get install -y fonts-noto-cjk &>/dev/null || true
        fi
    fi
}

# Check dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"
check_python_deps

# Check OS and fonts
if [[ "$OSTYPE" == "darwin"* ]]; then
    check_macos_fonts
else
    check_linux_fonts
fi

# Run Python conversion script
python3 "${SCRIPT_DIR}/convert-weasyprint.py" "$INPUT_FILE" "$OUTPUT_FILE"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Successfully converted: $OUTPUT_FILE${NC}"
    ls -lh "$OUTPUT_FILE"
else
    echo -e "${RED}✗ Conversion failed${NC}"
    exit 1
fi
