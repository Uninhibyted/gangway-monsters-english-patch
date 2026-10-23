# -*- coding: utf-8 -*-
# Translates FIELD/FDEVENT.ACB one event at a time instead of one line at a time.
#
# Each event ("EDT") starts with a table of u16 offsets (relative to the event) at 0x0C:
#   [0]      0x54, where the event's script starts
#   [1..30]  where each message starts; unused slots repeat the first message's offset
#   [31..34] where the text block ends (other script lists start there)
#   [35]     end + 2 or end + 4
# Messages are stored back to back, each terminated by 0x00, and the last one ends at [31].
#
# Because the game finds messages through this table, a translated message can be any
# length and sit anywhere up to 64 KB after its event: each message stays where the Japanese
# was if it fits there (the rest of that space padded with 0x00), and any that don't go into
# room added at the end of the event, after everything else in it.
#
# The ACB is split into sub-files (a whole number of 2048-byte sectors each, listed in the
# ACB's header), each starting with a table of where its chunks start: [u32 count, u32
# offset * count]. A chunk is one event with its pictures, or an empty one at the end. Room
# added at the end of an event moves every later chunk down, so this table is updated; the
# events after it in the sub-file then share the zeros that pad the sub-file to its sectors.
# Nothing inside an event moves, so its own offsets stay right.
#
# Inside a message, 0x0C starts a new text box and 0x0A a new line. Each box is translated
# whole in ja.fdevent.boxes.txt / en.fdevent.boxes.txt, where \n in the English ends a line
# and \f starts another box. The game wraps by byte count (mid-word in English), so a line
# over its limit is wrapped here at word boundaries, and lines past BOX_LINES continue in
# another box.

from script_config import *
import struct
import sys

EVENT_MAGIC = b'EDT\x00'
SECTOR = 2048
TABLE_OFFSET = 0x0C
SCRIPT_START = 0x54
MESSAGE_SLOTS = 30
END_SLOT = 1 + MESSAGE_SLOTS

NEWLINE = b'\x0A'
NEWBOX = b'\x0C'
BOX_LINES = 3    # measured in game: a 4th line is drawn over the 3rd
# Width allowed on each line of a box: a line holds 32 bytes before it wraps by itself, and
# the "press a button" icon covers the last two characters of the bottom line (measured in
# game). The Garage's window has a border and holds 24 (make_EventMain_window2).
LINE_LIMITS = [32, 32, 30]
GARAGE_LIMITS = [24, 24, 22]
GARAGE_EVENTS = range(250, 265)  # event numbers, from 1: the butler's scenes in the Garage
NAME = b'<name>'
NAME_BYTES = 8  # the longest name the player can enter

def sub_files(data):
    # An ACB's sub-files: (start, end), from [u16 sectors, u16 start sector, u32 0] entries
    count = struct.unpack_from('<H', data, 0x2e)[0]
    return [(start * SECTOR, (start + size) * SECTOR)
            for size, start in (struct.unpack_from('<HH', data, 0x32 + 8 * i) for i in range(count))]

def chunk_table(data, sub):
    count = struct.unpack_from('<I', data, sub[0])[0]
    return list(struct.unpack_from(f'<{count}I', data, sub[0] + 4))

def data_end(data, sub):
    # Where a sub-file's data ends (the rest is 0x00 padding), from its start, on 4 bytes
    used = len(data[sub[0]:sub[1]].rstrip(b'\x00'))
    return max(used + 3 & ~3, max(chunk_table(data, sub)))

def find_events(data):
    events = []
    i = data.find(EVENT_MAGIC)
    while i >= 0:
        table = list(struct.unpack_from('<36H', data, i + TABLE_OFFSET))
        if table[0] == SCRIPT_START:
            events.append(i)
        i = data.find(EVENT_MAGIC, i + 4)
    return events

def read_event(data, event):
    table = list(struct.unpack_from('<36H', data, event + TABLE_OFFSET))
    slots = table[1:END_SLOT]
    end = table[END_SLOT]
    starts = [slots[0]]
    for s in slots[1:]:
        if s == slots[0]: break
        starts.append(s)
    messages = []
    for a, b in zip(starts, starts[1:] + [end]):
        msg = data[event + a:event + b]
        text, _, rest = msg.partition(b'\x00')
        # Only the 0x00 padding we add after the last message may follow the terminator
        assert msg.endswith(b'\x00') and rest.strip(b'\x00') == b'', f"Unexpected message at {event + a:x}"
        messages.append(text)
    return table, messages

def width(b):
    return len(b) + b.count(NAME) * (NAME_BYTES - len(NAME))

def fits(line, limit):
    # A line that fills its limit wraps by itself (so needs no NEWLINE), but with <name> in it
    # that depends on the name's length, so those lines are kept one short of full
    return width(line) + (NAME in line) <= limit

def sjis_chars(b):
    i = 0
    while i < len(b):
        n = 2 if (0x81 <= b[i] <= 0x9F or 0xE0 <= b[i] <= 0xFC) else 1
        yield b[i:i+n]
        i += n

def word_chars(word):
    # Characters of a word, with <name> kept as one unit
    for k, part in enumerate(word.split(NAME)):
        if k: yield NAME
        yield from sjis_chars(part)

def wrap(text, first=0, limits=LINE_LIMITS):
    # Word-wraps text into lines; first is the position in its box of the first line,
    # since each line of a box has its own limit
    lines, line = [], b''
    limit = lambda: limits[(first + len(lines)) % BOX_LINES]
    for word in text.split(b' '):
        if not word: continue
        candidate = line + b' ' + word if line else word
        if fits(candidate, limit()):
            line = candidate
            continue
        if line: lines.append(line)
        line = b''
        # A word longer than a whole line gets split between characters (never inside <name>)
        for ch in word_chars(word):
            if not fits(line + ch, limit()):
                lines.append(line)
                line = b''
            line += ch
    if line: lines.append(line)
    return lines

def layout(lines, limits=LINE_LIMITS):
    boxes = []
    for i in range(0, len(lines), BOX_LINES):
        out = b''
        previous = None
        for line in lines[i:i+BOX_LINES]:
            if previous is not None and width(previous) < limits[0]:
                out += NEWLINE  # a full line already wraps on its own
            out += line
            previous = line
        boxes.append(out)
    return NEWBOX.join(boxes)

def layout_box(text, limits=LINE_LIMITS):
    # A box laid out by hand: NEWLINE ends a line, NEWBOX starts another box
    pages = []
    for page in text.split(NEWBOX):
        lines = []
        for line in page.split(NEWLINE):
            lines += wrap(line, len(lines), limits) or [b'']
        pages.append(layout(lines, limits))
    return NEWBOX.join(pages)

def event_limits(number):
    # Line limits for the event with this number (from 1)
    return GARAGE_LIMITS if number in GARAGE_EVENTS else LINE_LIMITS

def translate_message(msg, boxes, limits=LINE_LIMITS):
    # A box whose English is empty is left out, with its box break (its words
    # having gone into the box before it), unless that would leave the message empty
    parts = [box for box in msg.split(NEWBOX) if boxes.get(box, None) != b""] or msg.split(NEWBOX)[:1]
    return NEWBOX.join(layout_box(boxes[box], limits) if box in boxes else box
                       for box in parts)

def load_boxes():
    with open(f"{TRANSLATIONS_PATH}/ja.fdevent.boxes.txt", "r") as f: boxesja = f.read().split("\n")
    with open(f"{TRANSLATIONS_PATH}/en.fdevent.boxes.txt", "r") as f: boxesen = f.read().split("\n")
    unescape = lambda t: t.replace('\\n', '\n').replace('\\f', '\f').encode('shift-jis')
    return {unescape(ja): unescape(en) for ja, en in zip(boxesja, boxesen) if ja}

def place(messages, budget):
    # Lays out an event's messages: each one where the Japanese was if it fits there, the rest
    # in the extra room. Returns the block kept in place, the extra room's bytes, and for each
    # message ("in", offset into the block) or ("extra", offset into the extra room).
    block, extra, where = b'', b'', []
    for m in messages:
        m += b'\x00'
        if len(block) + len(m) > budget:
            where.append(("extra", len(extra))); extra += m
        else:
            where.append(("in", len(block))); block += m
    return block, extra + b'\x00' * (-len(extra) % 4), where

def patch(data, boxes):
    # Returns the patched ACB and [(sub-file start, bytes over the room its events share)]
    out = bytearray(data)
    over = []
    events = find_events(data)
    for sub in sub_files(data):
        sub_events = [e for e in events if sub[0] <= e < sub[1]]
        if not sub_events: continue
        table = chunk_table(data, sub)
        bounds = sorted(set(table) | {data_end(data, sub)})
        spare = sub[1] - sub[0] - bounds[-1]
        added = {}  # chunk end (offset in the sub-file) -> bytes added there
        for event in sub_events:
            table_e, messages = read_event(data, event)
            start, end = table_e[1], table_e[END_SLOT]
            limits = event_limits(events.index(event) + 1)
            new_messages = [translate_message(m, boxes, limits) for m in messages]
            block, extra, where = place(new_messages, end - start)
            chunk_end = next(x for x in bounds if x > event - sub[0])
            at = chunk_end - (event - sub[0])  # where the extra room starts, from the event
            if at + len(extra) > 0xFFFF:
                sys.exit(f"ERROR: event {event:06x}'s extra room would be past 64 KB")
            if extra: added[chunk_end] = extra
            out[event + start:event + end] = block + b'\x00' * (end - start - len(block))
            slots = [start + o if kind == "in" else at + o for kind, o in where]
            slots += [slots[0]] * (MESSAGE_SLOTS - len(slots))  # unused slots repeat the first
            struct.pack_into(f'<{MESSAGE_SLOTS}H', out, event + TABLE_OFFSET + 2, *slots)

        grow = sum(len(x) for x in added.values())
        if grow > spare:
            over.append((sub[0], grow - spare)); continue
        if not grow: continue
        # Rebuild the sub-file with the extra room after each event, and update its chunk table
        pieces, moved, shift = [bytes(out[sub[0]:sub[0] + bounds[0]])], {}, 0
        for x, y in zip(bounds, bounds[1:] + [None]):
            moved[x] = x + shift
            if y is None: break
            pieces.append(bytes(out[sub[0] + x:sub[0] + y]))
            if y in added: pieces.append(added[y]); shift += len(added[y])
        body = b''.join(pieces)
        out[sub[0]:sub[1]] = body + b'\x00' * (sub[1] - sub[0] - len(body))
        struct.pack_into(f'<{len(table)}I', out, sub[0] + 4, *[moved[t] for t in table])
    return bytes(out), over

if __name__ == "__main__":
    with open(f"{GAME_DATA_IN_DIR}/FIELD/FDEVENT.ACB", "rb") as f: data = f.read()
    result, over = patch(data, load_boxes())

    if over:
        events, subs = find_events(data), dict(sub_files(data))
        for sub, extra in over:
            numbers = [n + 1 for n, e in enumerate(events) if sub <= e < subs[sub]]
            print(f"Events {numbers[0]}-{numbers[-1]} are {extra} bytes over the room they share.")
        print("ERROR: Shorten some of their messages first.")
        sys.exit(1)

    binname = f"{GAME_DATA_OUT_DIR}/FIELD/FDEVENT.ACB"
    with open(binname, "wb") as f: f.write(result)
    print(f"Written data to {binname}")
