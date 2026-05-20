#!/bin/bash

GREEN='\033[1;32m'
CYAN='\033[1;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄${NC}"
echo ""
echo -e "${GREEN}Phase 1: Definition of package manager${NC}"

if command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
elif command -v apt &>/dev/null; then
    PKG_MANAGER="apt"
elif command -v dnf &>/dev/null; then
    PKG_MANAGER="dnf"
elif command -v zypper &>/dev/null; then
    PKG_MANAGER="zypper"
elif command -v xbps &>/dev/null; then
    PKG_MANAGER="xbps"
else
    echo "Unknown package manager. Exiting."
    exit 1
fi

echo -e "Package manager: ${CYAN}$PKG_MANAGER${NC}"

echo ""
echo -e "${GREEN}Phase 2: Installing figlet${NC}"

case $PKG_MANAGER in
    pacman) sudo pacman -S --noconfirm figlet ;;
    apt)    sudo apt install -y figlet ;;
    dnf)    sudo dnf install -y figlet ;;
    zypper) sudo zypper install -y figlet ;;
    xbps)   sudo xbps-install -y figlet ;;
esac

echo ""
echo -e "${GREEN}Phase 3: Logotype${NC}"
echo ""

figlet "lyrix"

echo ""
echo -e "${GREEN}Phase 4: Installing dependencies${NC}"

case $PKG_MANAGER in
    pacman) sudo pacman -S --noconfirm python python-pip playerctl curl ;;
    apt)    sudo apt install -y python3 python3-pip playerctl curl ;;
    dnf)    sudo dnf install -y python3 python3-pip playerctl curl ;;
    zypper) sudo zypper install -y python3 python3-pip playerctl curl ;;
    xbps)   sudo xbps-install -y python3 python3-pip playerctl curl ;;
esac

echo ""
echo -e "${GREEN}Phase 5: Installing Python dependencies${NC}"

pip install --quiet requests 2>/dev/null || pip3 install --quiet requests 2>/dev/null

echo ""
echo -e "${GREEN}Phase 6: Installing lyrix to /usr/bin${NC}"

sudo cp lyrix.py /usr/bin/lyrix
sudo chmod +x /usr/bin/lyrix

echo ""
echo -e "${GREEN}Phase 7: Installation complete${NC}"

echo -e "Run ${CYAN}lyrix${NC} to start."
