# -*- coding: utf-8 -*-
# Lets translated strings in the program and its overlays (SLPS_014.68, BIN/*.BIN) be longer
# than the Japanese, by repacking them and updating everything that points at them.
#
# The game reaches a string through its address: a 32-bit pointer (in a table) or a pair of
# instructions in the code, "lui r, hi" then "addiu/ori x, r, lo". Each string whose address
# shows up only like that, and that nothing points into the middle of, is "movable". Movable
# strings that sit back to back form a run; each run is repacked in order (every string on a
# 4-byte boundary, as the compiler left them), so a longer string pushes the ones after it
# along. A string stored more than once (the same Japanese, e.g. a shop line each shop has
# its own copy of) is kept once, with every reference pointed at that copy. A run that overflows moves its biggest strings into another run's spare room. Then
# every pointer gets the new address. In code only the "lo" instruction is changed, since the
# "lui" may be shared with other addresses: a string reached from code stays within reach of
# its "hi" (the same 64 KB).
#
# Strings that aren't movable keep the old rule: the English replaces the Japanese in place,
# padded to the same length (see replace_bytes.py).
#
# Overlays (BIN/*.BIN) all load at OVERLAY_BASE and have no header; SLPS_014.68 is a PS-X EXE.

import collections
import struct

OVERLAY_BASE = 0x800963f8
EXE_HEADER = 0x800
LUI, ADDIU, ORI = 0x0f, 0x09, 0x0d
LOADS_STORES = {0x20, 0x21, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2b}
PAIR_REACH = 24  # instructions after a lui to look for the instruction that uses it

def layout(data):
    # (address of file offset 0, first offset that is program data)
    if data[:8] == b'PS-X EXE':
        return struct.unpack_from('<I', data, 0x18)[0] - EXE_HEADER, EXE_HEADER
    return OVERLAY_BASE, 0

class Refs:
    # Everything in a file that holds an address: pointers, lui/lo pairs, and loads/stores
    def __init__(self, data):
        self.base, start = layout(data)
        n = (len(data) - start) // 4
        words = struct.unpack_from(f'<{n}I', data, start)
        self.pointers = collections.defaultdict(list)  # address -> [offset of the word]
        self.code = collections.defaultdict(list)      # address -> [(offset of lo, hi)]
        self.memory = set()                            # addresses read or written as data
        for k, w in enumerate(words):
            self.pointers[w].append(start + 4 * k)
            if w >> 26 != LUI: continue
            r, hi = (w >> 16) & 31, w & 0xffff
            for j in range(k + 1, min(k + 1 + PAIR_REACH, n)):
                v = words[j]; op = v >> 26
                if op == LUI and (v >> 16) & 31 == r: break  # r loaded again
                if (v >> 21) & 31 != r: continue
                lo = v & 0xffff
                a = ((hi << 16) + (lo - 0x10000 if op != ORI and lo & 0x8000 else lo)) & 0xffffffff
                if op in (ADDIU, ORI): self.code[a].append((start + 4 * j, hi))
                elif op in LOADS_STORES: self.memory.add(a)

    def address(self, offset): return self.base + offset
    def any(self, a): return a in self.pointers or a in self.code or a in self.memory

def lo_for(op, hi, address):
    # The immediate an addiu/ori needs to reach address from hi, or None if it can't
    rel = address - (hi << 16)
    if op == ADDIU: return rel & 0xffff if -0x8000 <= rel < 0x8000 else None
    return rel if 0 <= rel <= 0xffff else None

def is_text(b):
    try: t = b.decode('shift-jis')
    except UnicodeDecodeError: return False
    return all(c.isprintable() or c in '\n\x0c\u3000' for c in t)

def whole_strings(data, jas):
    # {start: end} of every null-terminated string holding one of the Japanese pieces (a piece
    # can also turn up in code or numbers: those aren't strings)
    out = {}
    for ja in jas:
        i = data.find(ja)
        while i >= 0:
            s = data.rfind(b'\0', 0, i) + 1
            e = data.index(b'\0', i)
            # A string right after a table of pointers has no 0x00 before it: it starts at the
            # first 4-byte boundary from which it's all text
            s = next((t for t in [s] + list(range((s + 3) & ~3, i + 1, 4)) if is_text(data[t:e])), None)
            if s is not None: out[s] = e
            i = data.find(ja, i + 1)
    return out

def translate(text, pairs):
    for ja, en in pairs: text = text.replace(ja, en)
    return text

def movable_strings(original, jas, refs=None):
    # ({start: end} of the strings holding a Japanese piece, {start: end} of the movable ones)
    refs = refs or Refs(original)
    strings = whole_strings(original, jas)
    movable = {}
    for s, e in strings.items():
        a = refs.address(s)
        inside = any(refs.any(refs.address(x)) for x in range(s + 1, e + 1))
        if (a in refs.pointers or a in refs.code) and a not in refs.memory and not inside:
            movable[s] = e
    return strings, movable

def slot_end(original, end):
    # Where a string ending at end (its 0x00) leaves room up to: the zero padding after it
    # to the next 4-byte boundary
    e = end + 1
    aligned = (e + 3) & ~3
    return aligned if not any(original[e:aligned]) else e

def find_runs(original, movable):
    # Movable strings that sit back to back, as lists of their starts
    runs = []
    for s in sorted(movable):
        if runs and slot_end(original, movable[runs[-1][-1]]) == s: runs[-1].append(s)
        else: runs.append([s])
    return runs

def duplicates(original, spans, refs):
    # {start: start of the copy it shares} for movable strings with the same Japanese as one
    # before them. A copy reached from code is only shared if its code can reach anywhere in
    # the run the kept copy is in, so wherever that copy is repacked to it can still reach it.
    runs = find_runs(original, spans)
    run_of = {s: r for r in runs for s in r}
    first, dups = {}, {}
    for s in sorted(spans):
        text = original[s:spans[s]]
        if text not in first: first[text] = s; continue
        r = run_of[first[text]]
        ends = (refs.address(r[0]), refs.address(slot_end(original, spans[r[-1]]) - 4))
        if all(lo_for(struct.unpack_from('<I', original, p)[0] >> 26, hi, a) is not None
               for p, hi in refs.code.get(refs.address(s), []) for a in ends):
            dups[s] = first[text]
    return dups

def patch(original, patched, pairs, verbose=False):
    # original: the Japanese file; patched: it with the old in-place replacements done;
    # pairs: [(ja, en)] in the order replace_bytes.py applies them. Returns the file with every
    # movable string rebuilt from the Japanese without padding and repacked.
    refs = Refs(original)
    strings, spans = movable_strings(original, [ja for ja, _ in pairs], refs)
    movable = {s: translate(original[s:e], pairs) + b'\0' for s, e in spans.items()}
    if not movable: return patched, {}

    runs = find_runs(original, spans)
    dups = duplicates(original, spans, refs)
    end = lambda run: slot_end(original, spans[run[-1]])
    run_room = lambda run, members: end(run) - run[0] - sum((len(movable[s]) + 3) & ~3 for s in members)
    members = [[s for s in r if s not in dups] for r in runs]
    # Move the biggest strings out of overflowing runs, each into another run with room for it
    # where its code (if any) can still reach it
    used = lambda ms: sum((len(movable[x]) + 3) & ~3 for x in ms)
    def reachable(s, address):
        # (the copies sharing s go with it)
        return all(lo_for(struct.unpack_from('<I', original, p)[0] >> 26, hi, refs.address(address)) is not None
                   for x in [s] + [d for d, c in dups.items() if c == s]
                   for p, hi in refs.code.get(refs.address(x), []))
    for k, run in enumerate(runs):
        while run_room(run, members[k]) < 0:
            moved = False
            for s in sorted(members[k], key=lambda x: -len(movable[x])):
                need = (len(movable[s]) + 3) & ~3
                dests = [j for j in range(len(runs)) if j != k and run_room(runs[j], members[j]) >= need
                         and reachable(s, runs[j][0] + used(members[j]))]
                if dests:
                    dest = max(dests, key=lambda j: run_room(runs[j], members[j]))
                    members[k].remove(s); members[dest].append(s); moved = True
                    break
            if not moved:
                raise ValueError(f"Out of room: the strings at {run[0]:x} are {-run_room(run, members[k])} bytes over")

    out = bytearray(patched)
    placed = {}
    for run, ms in zip(runs, members):
        out[run[0]:end(run)] = bytes(end(run) - run[0])
        at = run[0]
        for s in ms:
            out[at:at + len(movable[s])] = movable[s]
            placed[s] = at
            at += (len(movable[s]) + 3) & ~3
    for d, c in dups.items(): placed[d] = placed[c]
    # Point everything at the new places
    for s, new in placed.items():
        old_a, new_a = refs.address(s), refs.address(new)
        if old_a == new_a: continue
        for p in refs.pointers.get(old_a, []): struct.pack_into('<I', out, p, new_a)
        for p, hi in refs.code.get(old_a, []):
            w = struct.unpack_from('<I', out, p)[0]
            lo = lo_for(w >> 26, hi, new_a)
            if lo is None: raise ValueError(f"String at {s:x} moved out of reach of its code")
            struct.pack_into('<I', out, p, (w & 0xffff0000) | lo)
    if verbose:
        moved = sum(1 for s in placed if placed[s] != s and s not in dups)
        room = sum(run_room(r, m) for r, m in zip(runs, members))
        print(f"  {len(movable)} of {len(strings)} strings movable, {moved} moved, {len(dups)} copies shared, {room} bytes to spare")
    return bytes(out), placed
