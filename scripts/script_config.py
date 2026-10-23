# Where the scripts find things. Everything is inside the repo, so there's nothing to set up:
# put the original Japanese .bin at rom/Gangway Monsters (Japan).bin, or name it when building
# (scripts/build.sh <Japanese .bin> [<English .bin>], which sets GAME_BIN and GAME_BIN_OUT).
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSLATIONS_PATH = os.path.join(ROOT, "en-ja")
GAME_BIN = os.path.abspath(os.environ.get("GAME_BIN") or os.path.join(ROOT, "rom", "Gangway Monsters (Japan).bin"))
# (the English .bin goes beside the Japanese one)
GAME_BIN_OUT = os.path.abspath(os.environ.get("GAME_BIN_OUT") or os.path.join(os.path.dirname(GAME_BIN), "Gangway Monsters (English).bin"))
# The game files: extracted from GAME_BIN, then patched before going back into the .bin
GAME_DATA_IN_DIR = os.path.join(ROOT, "work", "original")
GAME_DATA_OUT_DIR = os.path.join(ROOT, "work", "patched")
GAME_DATA_IN_DIALOGUE_DIR = os.path.join(GAME_DATA_OUT_DIR, "BIN")  # OPENDEMO.BIN once its dialogue is in
# The old psximager build (replace_bytes.py without --export); build.sh doesn't use these
GAME_IMAGE_DIR = os.environ.get("GAME_IMAGE_DIR", "")
GAME_IMAGE_EMU_BIN = os.environ.get("GAME_IMAGE_EMU_BIN", "")
