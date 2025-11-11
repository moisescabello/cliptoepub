#!/bin/bash

#================================================
# Build completo para ClipToEpub
#================================================

set -e

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=================================================${NC}"
echo -e "${BLUE}Construcción completa de ClipToEpub${NC}"
echo -e "${BLUE}=================================================${NC}"

# 1. Limpiar builds anteriores
echo -e "\n${YELLOW}1. Limpiando builds anteriores...${NC}"
rm -rf build dist *.app 2>/dev/null || true
echo -e "${GREEN}[OK] Limpieza completada${NC}"

# 2. Configurar entorno virtual
echo -e "\n${YELLOW}2. Configurando entorno virtual...${NC}"
if [ ! -d "venv" ]; then
    arch -arm64 python3 -m venv venv
fi
source venv/bin/activate
echo -e "${GREEN}[OK] Entorno virtual activado${NC}"

# 3. Instalar dependencias
echo -e "\n${YELLOW}3. Instalando dependencias...${NC}"
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install py2app chardet pytesseract lxml_html_clean
echo -e "${GREEN}[OK] Dependencias instaladas${NC}"

# 4. Construir aplicación con py2app
echo -e "\n${YELLOW}4. Construyendo aplicación con py2app...${NC}"
python setup.py py2app

# Verificar que se creó la app
if [ -d "dist/ClipToEpub.app" ]; then
    echo -e "${GREEN}[OK] Aplicación construida exitosamente${NC}"

    # 5. Copiar a Aplicaciones (opcional)
    echo -e "\n${YELLOW}5. ¿Deseas instalar la app en /Applications? (s/n)${NC}"
    read -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        rm -rf "/Applications/ClipToEpub.app" 2>/dev/null || true
        # Usar rsync para copiar sin errores de archivos .pyo
        rsync -a --exclude='*.pyo' "dist/ClipToEpub.app" /Applications/ 2>/dev/null || \
        cp -R "dist/ClipToEpub.app" /Applications/ 2>/dev/null
        echo -e "${GREEN}[OK] App instalada en /Applications${NC}"
    fi

    # 6. Crear DMG (opcional)
    echo -e "\n${YELLOW}6. ¿Deseas crear un DMG instalador? (s/n)${NC}"
    read -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        ./build_dmg.sh
        echo -e "${GREEN}[OK] DMG creado en dist/ClipToEpub.dmg${NC}"
    fi

    echo -e "\n${BLUE}=================================================${NC}"
    echo -e "${GREEN}[OK] Construcción completada exitosamente!${NC}"
    echo -e "\nUbicaciones:"
    echo -e "   App: dist/ClipToEpub.app"
    [ -f "dist/ClipToEpub.dmg" ] && echo -e "   DMG: dist/ClipToEpub.dmg"
    [ -d "/Applications/ClipToEpub.app" ] && echo -e "   Instalada en: /Applications/ClipToEpub.app"
    echo -e "\n${BLUE}=================================================${NC}"
else
    echo -e "${RED}[ERROR] No se pudo construir la aplicación${NC}"
    exit 1
fi
