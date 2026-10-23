#!/bin/bash
# Makes the patch players apply: builds the English .bin, then writes its difference from the
# original Japanese .bin as an xdelta file, next to the English .bin, named with the version at
# the top of CHANGELOG.md. Needs xdelta3
# (macOS: brew install xdelta; Linux: apt install xdelta3).
#   scripts/make_patch.sh [--no-info-screen] [<Japanese .bin>]
# --no-info-screen builds without the credits screen (see build.sh) and adds
# "(no info screen)" to the patch's name.
set -euo pipefail
FLAGS=()
SUFFIX=""
args=()
for arg in "$@"; do
    case "$arg" in
        --no-info-screen) FLAGS+=("$arg"); SUFFIX=" (no info screen)" ;;
        *) args+=("$arg") ;;
    esac
done
set -- ${args[@]+"${args[@]}"}
command -v xdelta3 > /dev/null || { echo "xdelta3 not found: install it first (brew install xdelta / apt install xdelta3)" >&2; exit 1; }
[ $# -ge 1 ] && export GAME_BIN="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
cd "$(dirname "$0")"

bash build.sh ${FLAGS[@]+"${FLAGS[@]}"}

conf() { python3 -c "from script_config import *; print($1)"; }
JA="$(conf GAME_BIN)"
EN="$(conf GAME_BIN_OUT)"
VERSION="$(sed -n 's/^## \[\(v[^]]*\)\].*/\1/p' ../CHANGELOG.md | head -1)"
[ -n "$VERSION" ] || { echo "No version heading (## [v...]) in CHANGELOG.md" >&2; exit 1; }
PATCH="$(dirname "$EN")/Gangway Monsters (English) $VERSION$SUFFIX.xdelta"

# No secondary compression, so every xdelta patcher (Rom Patcher JS, Delta Patcher) can apply it
xdelta3 -e -f -9 -S none -s "$JA" "$EN" "$PATCH"

# Check it: applying the patch to the original must give the English .bin
CHECK="$(mktemp)"
trap 'rm -f "$CHECK"' EXIT
xdelta3 -d -f -s "$JA" "$PATCH" "$CHECK"
cmp -s "$CHECK" "$EN" || { echo "ERROR: the patch doesn't reproduce the English .bin" >&2; exit 1; }

echo "Written $PATCH ($(du -h "$PATCH" | cut -f1 | tr -d ' '))"
echo "  for the Japanese .bin with SHA-1 $(shasum -a 1 "$JA" | cut -d' ' -f1)"
echo "  makes the English .bin with SHA-1 $(shasum -a 1 "$EN" | cut -d' ' -f1)"
