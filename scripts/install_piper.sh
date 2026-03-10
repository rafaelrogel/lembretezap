#!/bin/bash
# Standalone Piper TTS Installer for Zapista
# Usage: sudo bash scripts/install_piper.sh [DATA_DIR]
# Default DATA_DIR is ./data

set -e

DATA_DIR="${1:-./data}"
mkdir -p "$DATA_DIR/bin"
mkdir -p "$DATA_DIR/models/piper"

echo "Installing Piper TTS to $DATA_DIR"

PIPER_RELEASE="2023.11.14-2"
PIPER_ARCH=$(uname -m)
case "$PIPER_ARCH" in
  x86_64)   PIPER_TGZ="piper_linux_x86_64.tar.gz" ;;
  aarch64)  PIPER_TGZ="piper_linux_aarch64.tar.gz" ;;
  armv7l)   PIPER_TGZ="piper_linux_armv7l.tar.gz" ;;
  *)        PIPER_TGZ="" ;;
esac

HF_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main"
PIPER_VOICES="pt/pt_BR/cadu/medium:pt_BR-cadu-medium
pt/pt_PT/tug%C3%A3o/medium:pt_PT-tug%C3%A3o-medium
es/es_ES/davefx/medium:es_ES-davefx-medium
en/en_US/amy/medium:en_US-amy-medium"

if [ -z "$PIPER_TGZ" ]; then
    echo "Unsupported architecture: $PIPER_ARCH"
    exit 1
fi

PIPER_URL="https://github.com/rhasspy/piper/releases/download/${PIPER_RELEASE}/${PIPER_TGZ}"
TMP_DIR=$(mktemp -d)

echo "Downloading Piper from $PIPER_URL..."
if curl -fsSL "$PIPER_URL" -o "$TMP_DIR/piper.tar.gz"; then
    tar -xzf "$TMP_DIR/piper.tar.gz" -C "$TMP_DIR"
    BIN_PATH=$(find "$TMP_DIR" -name "piper" -type f 2>/dev/null | head -1)
    if [ -n "$BIN_PATH" ]; then
        ORIGIN_DIR=$(dirname "$BIN_PATH")
        cp "$BIN_PATH" "$DATA_DIR/bin/piper"
        chmod +x "$DATA_DIR/bin/piper"
        
        echo "Copying libraries..."
        for so in "$ORIGIN_DIR"/*.so*; do
            [ -e "$so" ] && cp "$so" "$DATA_DIR/bin/" && chmod 755 "$DATA_DIR/bin/$(basename "$so")"
        done
        
        ESPEAK_DATA=$(find "$TMP_DIR" -name "espeak-ng-data" -type d 2>/dev/null | head -1)
        if [ -n "$ESPEAK_DATA" ]; then
            cp -a "$ESPEAK_DATA" "$DATA_DIR/bin/"
            echo "Copied espeak-ng-data."
        fi
    fi
else
    echo "Failed to download Piper."
    exit 1
fi
rm -rf "$TMP_DIR"

echo "Downloading voices..."
while IFS=: read -r rel_path base_name; do
    [ -z "$rel_path" ] && continue
    VOICE_DIR="$DATA_DIR/models/piper/$rel_path"
    mkdir -p "$VOICE_DIR"
    for ext in onnx onnx.json; do
        FILE="${base_name}.${ext}"
        if [ ! -f "$VOICE_DIR/$FILE" ]; then
            echo "  Downloading $FILE..."
            curl -fsSL "$HF_BASE/$rel_path/$FILE" -o "$VOICE_DIR/$FILE" 2>/dev/null || true
        fi
    done
done << EOF
$PIPER_VOICES
EOF

echo ""
echo "Installation complete!"
echo "PIPER_BIN path for .env: $(realpath $DATA_DIR/bin/piper)"
echo "TTS_MODELS_BASE path for .env: $(realpath $DATA_DIR/models/piper)"
