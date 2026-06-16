#!/bin/bash
#
# Build script for Moqui IoT Firmware (ESP-IDF 6.2)
# Supports: Docker (recommended) or local ESP-IDF installation
#
# Usage:
#   ./build.sh esp32             # Build for ESP32 hardware target (DEFAULT)
#   ./build.sh esp32 build       # Explicit build command
#   ./build.sh esp32 clean       # Clean build artifacts
#   ./build.sh linux             # Build for Linux/POSIX target (preview, limited support)
#

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
TARGET="${1:-esp32}"
ACTION="${2:-build}"
DOCKER_IMAGE="espressif/idf:latest"

# Validate target
if [[ "$TARGET" != "esp32" && "$TARGET" != "linux" ]]; then
    echo -e "${RED}✗ Invalid target '$TARGET'${NC}"
    echo "Supported targets: esp32 (default), linux"
    exit 1
fi

# Warn about linux target limitations
if [[ "$TARGET" == "linux" ]]; then
    echo -e "${YELLOW}⚠ WARNING: Linux target is still in preview mode${NC}"
    echo -e "${YELLOW}Some hardware-specific components may not be available${NC}"
fi

# Detect if Docker is available
HAS_DOCKER=false
if command -v docker &> /dev/null; then
    HAS_DOCKER=true
fi

# Determine build method
if $HAS_DOCKER; then
    BUILD_METHOD="Docker"
    echo -e "${GREEN}✓ Using Docker${NC}"
else
    if [[ -z "$IDF_PATH" ]]; then
        echo -e "${RED}✗ Error: Docker not found and IDF_PATH not set${NC}"
        echo "Install Docker or set: export IDF_PATH=/path/to/esp-idf"
        exit 1
    fi
    BUILD_METHOD="Local ESP-IDF"
    echo -e "${GREEN}✓ Using local ESP-IDF: $IDF_PATH${NC}"
fi

# Function: Run build with Docker
build_with_docker() {
    local target=$1
    local action=$2
    
    # Use --preview flag for linux target
    local preview_flag=""
    if [[ "$target" == "linux" ]]; then
        preview_flag="--preview"
    fi
    
    case "$action" in
        build)
            echo -e "${BLUE}Building firmware for $target...${NC}"
            docker run --rm -v "$PWD":/project -w /project $DOCKER_IMAGE \
                /bin/bash -lc "idf.py $preview_flag set-target $target && idf.py build" \
                2>&1 | tee build.log
            ;;
        clean)
            echo -e "${BLUE}Cleaning build artifacts...${NC}"
            docker run --rm -v "$PWD":/project -w /project $DOCKER_IMAGE \
                /bin/bash -lc "rm -rf build sdkconfig sdkconfig.old"
            ;;
        *)
            echo -e "${RED}✗ Unknown action: $action${NC}"
            exit 1
            ;;
    esac
}

# Function: Run build with local ESP-IDF
build_with_local() {
    local target=$1
    local action=$2
    
    source "$IDF_PATH/export.sh" > /dev/null 2>&1
    
    case "$action" in
        build)
            echo -e "${BLUE}Building firmware for $target...${NC}"
            idf.py set-target $target
            idf.py build 2>&1 | tee build.log
            ;;
        clean)
            echo -e "${BLUE}Cleaning build artifacts...${NC}"
            if [[ -d build ]]; then
                idf.py fullclean || rm -rf build sdkconfig sdkconfig.old
            fi
            ;;
        *)
            echo -e "${RED}✗ Unknown action: $action${NC}"
            exit 1
            ;;
    esac
}

# Execute build
echo -e "${BLUE}Target: $TARGET | Action: $ACTION | Method: $BUILD_METHOD${NC}"
echo ""

if $HAS_DOCKER; then
    build_with_docker "$TARGET" "$ACTION"
else
    build_with_local "$TARGET" "$ACTION"
fi

# Print summary
if [[ $? -eq 0 ]]; then
    case "$ACTION" in
        build)
            echo ""
            echo -e "${GREEN}✓ Build completed successfully!${NC}"
            if [[ -f "build/moqui_iot_firmware.elf" ]]; then
                echo -e "${GREEN}  Firmware: build/moqui_iot_firmware.elf${NC}"
            fi
            ;;
        clean)
            echo ""
            echo -e "${GREEN}✓ Build cleanup completed${NC}"
            ;;
    esac
fi
