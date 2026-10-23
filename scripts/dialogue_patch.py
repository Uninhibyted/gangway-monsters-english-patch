# Puts the opening's dialogue (en-ja/dialogue/opendemo/en/<n>.txt, laid out by dialogue.py)
# into OPENDEMO.BIN.
#
# The 27 speeches are strings stored back to back, each reached through one 32-bit pointer,
# so they share their room: they're packed in file order (each on a 4-byte boundary, as the
# compiler left them) and every pointer is updated. A speech can be longer than its
# Japanese as long as the whole opening fits.
#
# There's more room after the end of the file, up to the end of its last sector: the game
# looks the file up by name (so the build's new size in the ISO directory is what it loads),
# CD reads are whole sectors anyway, and nothing else uses that memory (the overlay loads at
# 0x800963f8; the next address the opening or the main program uses is 0x8009bc30). The
# next file on the disc starts in the following sector, so that's the limit. Speeches fill
# the original room first and the rest go there.
from script_config import *
import os
import struct
import sys
import strings_patch

SPEECHES = 27
FOLDER = os.path.join(TRANSLATIONS_PATH, "dialogue", "opendemo")

def size(en):
    # Bytes a speech takes: its text, its 0x00, rounded up to 4
    return (len(en) + 1 + 3) & ~3

def slots(data):
    # [(file offset, speech number, offset of its pointer)] in file order, and where the
    # speeches' room ends
    refs = strings_patch.Refs(data)
    found = []
    for i in range(SPEECHES):
        with open(f'{FOLDER}/ja/{i}.txt') as f: ja = f.read().encode('shift-jis')
        s = data.find(ja)
        ptrs = refs.pointers.get(refs.address(s), []) if s >= 0 else []
        if len(ptrs) != 1: sys.exit(f"Error: can't find speech {i} or the pointer to it")
        found.append((s, i, ptrs[0]))
    found.sort()
    for (s, _, _), (n, _, _) in zip(found, found[1:]):
        if strings_patch.slot_end(data, data.index(b'\0', s)) != n: sys.exit("Error: the speeches aren't back to back")
    return found, strings_patch.slot_end(data, data.index(b'\0', found[-1][0]))

SECTOR = 2048

def tail(data):
    # (start, end) of the room after the file: from the end, on a 4-byte boundary, to the end
    # of its last sector
    return (len(data) + 3) & ~3, (len(data) + SECTOR - 1) // SECTOR * SECTOR

def room(data):
    found, end = slots(data)
    t0, t1 = tail(data)
    return end - found[0][0] + t1 - t0

def patch(data, speeches):
    # speeches: {number: English bytes}; returns the file and the bytes left over
    found, end = slots(data)
    t0, t1 = tail(data)
    need = sum(size(en) for en in speeches.values())
    if need > room(data):
        sys.exit(f"Error: the opening's dialogue is {need - room(data)} bytes over its room")
    base = strings_patch.layout(data)[0]
    out = bytearray(data) + bytes(t1 - len(data))
    out[found[0][0]:end] = bytes(end - found[0][0])
    at, after = found[0][0], t0
    for _, i, pointer in found:
        if at + size(speeches[i]) <= end:
            place, at = at, at + size(speeches[i])
        else:
            place, after = after, after + size(speeches[i])
            if after > t1: sys.exit("Error: the opening's dialogue doesn't fit (it can't be split up any other way)")
        out[place:place + len(speeches[i])] = speeches[i]
        struct.pack_into('<I', out, pointer, base + place)
    # The file only grows as far as it has to
    used = max(len(data), after if after > t0 else len(data))
    return bytes(out[:used]), room(data) - need

def load_en():
    speeches = {}
    for i in range(SPEECHES):
        with open(f'{FOLDER}/en/{i}.txt') as f: speeches[i] = f.read().encode('shift-jis')
    return speeches

if __name__ == "__main__":
    with open(f"{GAME_DATA_IN_DIR}/BIN/OPENDEMO.BIN", "rb") as f: filedata = f.read()
    filedata, spare = patch(filedata, load_en())
    print(f"Opening dialogue: {spare} bytes to spare")
    with open(f"{GAME_DATA_OUT_DIR}/BIN/OPENDEMO.BIN", "wb") as f: f.write(filedata)
