#!/bin/bash
# Builds a patched .bin from the original, without psximager.
#   scripts/build.sh [--no-info-screen] [<Japanese .bin> [<English .bin>]]
# With no arguments the Japanese .bin is rom/Gangway Monsters (Japan).bin; the English one is
# written beside it (see script_config.py). --no-info-screen leaves out the screen with the
# translation's credits and version after the Sony Music logo.
set -euo pipefail
INFO_SCREEN=1
args=()
for arg in "$@"; do
    case "$arg" in
        --no-info-screen) INFO_SCREEN=0 ;;
        *) args+=("$arg") ;;
    esac
done
set -- ${args[@]+"${args[@]}"}
[ $# -ge 1 ] && export GAME_BIN="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
[ $# -ge 2 ] && export GAME_BIN_OUT="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
cd "$(dirname "$0")"

conf() { python3 -c "from script_config import *; print($1)"; }
GAME_BIN="$(conf GAME_BIN)"
if [ ! -f "$GAME_BIN" ]; then
    echo "No Japanese .bin at $GAME_BIN: put it there, or run scripts/build.sh <Japanese .bin>" >&2
    exit 1
fi
IN_DIR="$(conf GAME_DATA_IN_DIR)"
OUT_DIR="$(conf GAME_DATA_OUT_DIR)"

[ -f "$IN_DIR/SLPS_014.68" ] || python3 build_rom.py extract > /dev/null
rm -rf "$OUT_DIR" && mkdir -p "$OUT_DIR/BIN" "$OUT_DIR/BATTLE" "$OUT_DIR/FIELD"

for name in slps battle casino ending field title vsmode monbook; do
    python3 replace_bytes.py "$name" --export   # --export turns exporting *off*
done

# Opening: dialogue first, then the menu text on top of it
(cd "$(conf TRANSLATIONS_PATH)/dialogue" && python3 ../../scripts/dialogue_patch.py > /dev/null)
python3 replace_bytes.py opendemo --export

# A screen with the version and credits after the Sony Music logo (see info_screen.py)
if [ "$INFO_SCREEN" = 1 ]; then python3 info_screen.py; fi

# Field events share a byte budget per event (see fdevent_patch.py)
python3 fdevent_patch.py

# Translated graphics from graphics/ (needs Pillow: pip3 install -r requirements.txt)
python3 graphics.py

python3 build_rom.py inject
