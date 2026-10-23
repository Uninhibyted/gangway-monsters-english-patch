# Lays out the opening's dialogue: en-ja/dialogue/opendemo/en_raw/<n>.txt (one speech each,
# 0x0C between boxes) into en/<n>.txt, which dialogue_patch.py builds from. Give speech
# numbers to redo only those.
#
# Boxes are 3 lines of 24. Lines are wrapped at 24; a full line wraps by itself, so it gets
# no line break (one would leave a blank line, as seen in game). The speeches share one
# room (see dialogue_patch.py), so this checks the whole opening still fits.
from script_config import *
import sys
import textwrap
import dialogue_patch

LINE_LENGTH = 24

w = textwrap.TextWrapper(width=LINE_LENGTH, drop_whitespace=True, break_on_hyphens=False)

def lay_out(text):
    boxes = []
    for box in text.split('\x0c'):
        lines = [line for part in box.split('\n') for line in (w.wrap(part) or [''])]
        boxes.append(''.join(line + ('' if k == len(lines) - 1 or len(line.encode('shift-jis')) >= LINE_LENGTH else '\n')
                             for k, line in enumerate(lines)))
    return '\x0c'.join(boxes)

if __name__ == "__main__":
    only = {int(a) for a in sys.argv[1:]}
    for i in range(dialogue_patch.SPEECHES):
        if only and i not in only: continue
        with open(f'{dialogue_patch.FOLDER}/en_raw/{i}.txt') as f: en = lay_out(f.read())
        en.encode('shift-jis')
        with open(f'{dialogue_patch.FOLDER}/en/{i}.txt', 'w') as f: f.write(en)

    with open(f"{GAME_DATA_IN_DIR}/BIN/OPENDEMO.BIN", "rb") as f: filedata = f.read()
    speeches = dialogue_patch.load_en()
    need, room = sum(dialogue_patch.size(en) for en in speeches.values()), dialogue_patch.room(filedata)
    if need > room: print(f"Error: the opening's dialogue is {need - room} bytes over its room ({need} of {room})")
    else: print(f"Opening dialogue: {need} of {room} bytes")
