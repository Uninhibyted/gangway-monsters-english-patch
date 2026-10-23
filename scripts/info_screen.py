# -*- coding: utf-8 -*-
# Adds a screen after the Sony Music logo, before the opening movie: the butler, with his
# portrait, says who made the translation in one of the game's message boxes, and its version
# (from the top of CHANGELOG.md) is at the bottom right.
#
# The logo is the SMELogo scene (BIN/SMELOGO.BIN). Its main function runs one state per
# frame from a table: load the logo, fade in, wait, fade out, then (state 8) wait for the fade
# to finish and switch to the TitleMenu scene, which plays the movie. State 8 now points at
# code added to the end of the overlay, with its own steps:
#   0  wait for the logo to fade out, load the images, make the logo's two sprites the
#      portrait and the version, open the windows and print their lines, fade in
#   1  wait for the fade in
#   2  wait for a face button (the butler's box shows the button icon), then fade out
#   3  wait for the fade out, close the windows and go on to state 8's original ending (which
#      clears the sprites)
# Each frame the sprites go in the layer at 0x10 of the frame's drawing context and the windows
# (8001cfec) in the one at 0x14, as in the opening, so the portrait shows over its frame.
#
# Three images are copied, compressed, to the end of FIELD/SMELOGO.DAT, which the scene loads
# whole to 80190000: the window parts (the boxes' corners and the button icon; the title
# screen loads those from TITLE.DAT and they stay in VRAM, but the logo comes before it), the
# butler's portrait in the Garage (FIELD.ACB), and the version, drawn here in a font smaller
# than the windows' (VERSION_FONT).

from script_config import *
from lzss import compress
import os
import re
import struct

BASE = 0x800963f8          # where overlays load
STATE_TABLE = 0x80096414   # SMELogo's state table (9 entries)
EPILOGUE = 0x80096630      # draws the scene's sprites and returns
RETURN = 0x80096640        # the epilogue after drawing
FINISH = 0x800965f4        # state 8 after its fade: clean up and switch to TitleMenu
LOGO_FILE = 0x80190000     # where the scene loads SMELOGO.DAT
UNPACKED = 0x801e0000      # where it unpacks the logo, free again by now

FADE_STATE, FADE_IN, FADE_OUT = 0x800143e4, 0x80014330, 0x8001438c
DECOMPRESS, LOAD_TIM, SPRITE, DRAW_SPRITES = 0x800144d4, 0x80021f1c, 0x80021794, 0x8002195c
WINDOW_INIT, WINDOW_OPEN, WINDOW_PRINT = 0x8001e29c, 0x8001c498, 0x8001e578
WINDOW_DRAW, WINDOW_CLOSE_ALL = 0x8001cfec, 0x8001e2c0
WINDOW_WAIT = 0x8001e4e0   # shows a window's button icon, as when a message waits for a press
PAD_PRESSED = 0x8006ed54   # buttons pressed this frame
FACE_BUTTONS = 0x00f0      # Triangle, Circle, Cross, Square

# The butler's portrait: an 8bpp 48x48 TIM, its image at (448, 256) in VRAM, its palette
# at (0, 481); the logo's are elsewhere
PORTRAIT = ("FIELD/FIELD.ACB", 0x1eadc)
WINDOW_PARTS = ("FIELD/TITLE.DAT", 0x13180)
PORTRAIT_W = PORTRAIT_H = 48
PORTRAIT_VRAM = (0x1c0, 0x100)
PORTRAIT_CLUT = (0, 0x1e1)
PORTRAIT_XY = (0x14, 0x10)

# The version: a 4bpp image of it at (448, 304) in VRAM, under the portrait, its palette at
# (0, 482), drawn at the bottom right, its right edge lined up with the box's text
VERSION_VRAM = (0x1c0, 0x130)
VERSION_CLUT = (0, 0x1e2)
VERSION_RIGHT, VERSION_Y = 0x0c + 0x128 - 8, 0xdc
VERSION_COLOURS = [0, 0x7fff, 0x0c63]  # transparent, white, a dark shadow
VERSION_FONT = {  # 7 rows high
    'v': [".....", ".....", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    '.': ["..", "..", "..", "..", "..", "##", "##"],
    '-': ["....", "....", "....", "####", "....", "....", "...."],
    '0': [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    '1': ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    '2': [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    '3': ["####.", "....#", "....#", ".###.", "....#", "....#", "####."],
    '4': ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    '5': ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    '6': ["..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
    '7': ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    '8': [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    '9': [".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."],
}

def version_image(version):
    # Glyphs 1px apart, each lit pixel with a shadow below right; the width a multiple of 4
    glyphs = [VERSION_FONT[c] for c in version]
    width = (sum(len(g[0]) + 1 for g in glyphs) + 3) & ~3
    height = len(glyphs[0]) + 1
    pixels = [[0] * width for _ in range(height)]
    x = 0
    for g in glyphs:
        for y, row in enumerate(g):
            for dx, c in enumerate(row):
                if c == '#':
                    pixels[y][x + dx] = 1
                    if not pixels[y + 1][x + dx + 1]: pixels[y + 1][x + dx + 1] = 2
        x += len(g[0]) + 1
    return width, height, [p for row in pixels for p in row]

def version_tim(version):
    width, height, pixels = version_image(version)
    clut = struct.pack('<16H', *(VERSION_COLOURS + [0] * (16 - len(VERSION_COLOURS))))
    image = bytes(pixels[i] | (pixels[i + 1] << 4) for i in range(0, len(pixels), 2))
    tim = (b'\x10\x00\x00\x00' + struct.pack('<I', 8)
           + struct.pack('<IHHHH', 12 + len(clut), *VERSION_CLUT, 16, 1) + clut
           + struct.pack('<IHHHH', 12 + len(image), *VERSION_VRAM, width // 4, height) + image)
    return bytes(compress(tim)), width, height

# Windows: style (0: the game's message box, 2: text only), x, y, width, height. A window
# holds (width - 16) / 8 half-width characters per line and (height - 8) / 16 lines. The
# portrait's frame sits above the butler's box (his lines are too long to fit both side by
# side).
WINDOWS = [(0, 0x0c, 0x4c, 0x128, 0x88),  # the butler's box: 35 x 8
           (0, 0x0c, 0x08, 0x40, 0x40)]   # the portrait's frame

# [(window, text)]
LINES = [(0, "Ah, young master. This English"),
         (0, "translation began with Stephwag"),
         (0, "and continued with Uninhibyted."),
         (0, "As for my contribution..."),
         (0, "I oversaw the entire affair."),
         (0, "From a respectable distance."),
         (0, "Someone had to maintain"),
         (0, "a degree of dignity, after all.")]

# A small MIPS assembler for the code below
REGS = {n: i for i, n in enumerate('zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split())}
I_OPS = {'addiu': 9, 'slti': 10, 'andi': 12, 'ori': 13}
MEM_OPS = {'lbu': 0x24, 'lhu': 0x25, 'lw': 0x23, 'sb': 0x28, 'sh': 0x29, 'sw': 0x2b}

def assemble(source, origin, symbols):
    code = [l.split(';')[0].strip() for l in source.strip().split('\n')]
    code = [l for l in code if l]
    labels, address = {}, origin
    for l in code:
        if l.endswith(':'): labels[l[:-1]] = address
        else: address += 4
    symbols = {**symbols, **labels}
    def value(s):
        if s.startswith('%hi('): return ((value(s[4:-1]) + 0x8000) >> 16) & 0xffff
        if s.startswith('%lo('): return value(s[4:-1]) & 0xffff
        return int(s, 0) if re.match(r'-?(0x)?[0-9]', s) else symbols[s]
    words, address = [], origin
    for l in code:
        if l.endswith(':'): continue
        op, _, rest = l.partition(' ')
        args = [a.strip() for a in rest.split(',')] if rest else []
        r = lambda i: REGS[args[i]]
        if op == 'nop': w = 0
        elif op == 'move': w = (r(1) << 21) | (r(0) << 11) | 0x21
        elif op == 'addu': w = (r(1) << 21) | (r(2) << 16) | (r(0) << 11) | 0x21
        elif op == 'sll': w = (r(1) << 16) | (r(0) << 11) | (value(args[2]) << 6)
        elif op == 'jr': w = (r(0) << 21) | 8
        elif op in ('j', 'jal'): w = ((2 if op == 'j' else 3) << 26) | ((value(args[0]) >> 2) & 0x3ffffff)
        elif op in ('beq', 'bne', 'beqz', 'bnez'):
            if op in ('beqz', 'bnez'): args = [args[0], 'zero', args[1]]
            offset = (value(args[2]) - address - 4) >> 2
            w = ((4 if op.startswith('beq') else 5) << 26) | (r(0) << 21) | (r(1) << 16) | (offset & 0xffff)
        elif op == 'lui': w = (0x0f << 26) | (r(0) << 16) | value(args[1])
        elif op in I_OPS:
            w = (I_OPS[op] << 26) | (r(1) << 21) | (r(0) << 16) | (value(args[2]) & 0xffff)
        elif op in MEM_OPS:
            m = re.match(r'(.+)\((\w+)\)$', args[1])
            w = (MEM_OPS[op] << 26) | (REGS[m.group(2)] << 21) | (r(0) << 16) | (value(m.group(1)) & 0xffff)
        else: raise ValueError(f"Can't assemble: {l}")
        words.append(w); address += 4
    return struct.pack(f'<{len(words)}I', *words)

# s4 points at the variables: the step (byte), window ids
# (words from 4). Calls take their 5th and later arguments at 0x10(sp) on, which the
# scene's function leaves free.
# The sprite's 5th to 12th arguments, from words 4 to 11 of its entry in SPRITES (two
# registers in turn, as a load's result isn't ready for the next instruction)
def sprite_args():
    reg = lambda k: ('v0', 'v1')[k % 2]
    code = ''
    for k in range(8):
        code += f"    lw    {reg(k)}, {16 + 4 * k}(s1)\n"
        if k: code += f"    sw    {reg(k - 1)}, {0x10 + 4 * (k - 1)}(sp)\n"
    return code + f"    sw    {reg(7)}, {0x10 + 4 * 7}(sp)\n"
SPRITE_ARGS = sprite_args()

CODE = f"""
info:
    lui   s4, %hi(VARS)
    addiu s4, s4, %lo(VARS)
    lbu   v0, 0(s4)          ; step
    nop
    bnez  v0, step1
    nop
    jal   FADE_STATE         ; 0: wait for the logo to fade out
    nop
    addiu v1, zero, 1
    bne   v0, v1, EPILOGUE
    nop
    lui   s1, %hi(TIMS)          ; the images, unpacked into VRAM
    addiu s1, s1, %lo(TIMS)
    move  s0, zero
load:
    lw    a0, 0(s1)
    jal   DECOMPRESS
    lui   a1, %hi(UNPACKED)
    jal   LOAD_TIM
    lui   a0, %hi(UNPACKED)
    addiu s0, s0, 1
    slti  v0, s0, NTIMS
    bnez  v0, load
    addiu s1, s1, 4
    lui   s1, %hi(SPRITES)       ; sprites 0 and 1, the logo's halves, become ours
    addiu s1, s1, %lo(SPRITES)
    move  s0, zero
sprite:
{SPRITE_ARGS}    lw    a0, 0(s1)
    lw    a1, 4(s1)
    lw    a2, 8(s1)
    jal   SPRITE
    lw    a3, 12(s1)
    addiu s0, s0, 1
    slti  v0, s0, NSPRITES
    bnez  v0, sprite
    addiu s1, s1, 48
    lui   a0, 0x800d
    jal   WINDOW_INIT
    ori   a0, a0, 0xb000
    lui   s1, %hi(RECTS)
    addiu s1, s1, %lo(RECTS)
    move  s0, zero
open:
    jal   WINDOW_OPEN
    move  a0, s1
    sll   v1, s0, 2
    addu  v1, v1, s4
    sw    v0, 4(v1)
    addiu s0, s0, 1
    slti  v0, s0, NWINDOWS
    bnez  v0, open
    addiu s1, s1, 10
    lui   s1, %hi(LINES)
    addiu s1, s1, %lo(LINES)
    move  s0, zero
print:
    lbu   v1, 0(s1)          ; window
    lbu   a1, 1(s1)          ; line
    sll   v1, v1, 2
    addu  v1, v1, s4
    lw    a0, 4(v1)
    lw    a2, 4(s1)          ; text
    jal   WINDOW_PRINT
    nop
    addiu s0, s0, 1
    slti  v0, s0, NLINES
    bnez  v0, print
    addiu s1, s1, 8
    lw    a0, 4(s4)          ; the butler's box (WINDOW_WAIT reads a0 straight away)
    jal   WINDOW_WAIT
    nop
    jal   FADE_IN
    addiu a0, zero, 0x1e
    addiu v0, zero, 1
    j     draw
    sb    v0, 0(s4)
step1:
    addiu v1, zero, 1
    bne   v0, v1, step2
    nop
    jal   FADE_STATE         ; 1: wait for the fade in
    nop
    bnez  v0, draw
    nop
    addiu v0, zero, 2
    j     draw
    sb    v0, 0(s4)
step2:
    addiu v1, zero, 2
    bne   v0, v1, step3
    nop
    lui   v1, %hi(PAD_PRESSED)  ; 2: wait for a face button
    lhu   v1, %lo(PAD_PRESSED)(v1)
    nop
    andi  v1, v1, FACE_BUTTONS
    beqz  v1, draw
    nop
    jal   FADE_OUT
    addiu a0, zero, 0x1e
    addiu v0, zero, 3
    j     draw
    sb    v0, 0(s4)
step3:
    jal   FADE_STATE         ; 3: wait for the fade out, then go on to the title
    nop
    addiu v1, zero, 1
    bne   v0, v1, draw
    nop
    jal   WINDOW_CLOSE_ALL
    nop
    j     FINISH
    nop
draw:
    lui   s0, 0x8006
    lw    a0, -0x16d0(s0)    ; the frame's drawing context, as the scene's epilogue uses
    jal   DRAW_SPRITES
    addiu a0, a0, 0x10
    lw    a0, -0x16d0(s0)
    jal   WINDOW_DRAW
    addiu a0, a0, 0x14
    j     RETURN
    nop
"""

def check_text(windows, texts):
    for w, t in texts:
        _, _, _, width, height = windows[w]
        if len(t) > (width - 16) // 8: raise ValueError(f"'{t}' is too long for its window")
    for w, (_, _, _, _, height) in enumerate(windows):
        if sum(1 for x, _ in texts if x == w) > (height - 8) // 16:
            raise ValueError(f"Too many lines for window {w}")

def append(data, block):
    at = (len(data) + 3) & ~3
    return data + bytes(at - len(data)) + block, at

def patch(overlay, logo_file, parts, portrait, version):
    # parts, portrait: compressed TIMs (with their size header). They and the version's image
    # go at the end of SMELOGO.DAT.
    version_packed, version_w, version_h = version_tim(version)
    tims = []
    for block in (parts, portrait, version_packed):
        logo_file, at = append(logo_file, block)
        tims.append(LOGO_FILE + at)
    sprites = [(0, *PORTRAIT_XY, PORTRAIT_W, PORTRAIT_H, 1, *PORTRAIT_VRAM, *PORTRAIT_CLUT, 0, 1),
               (1, VERSION_RIGHT - version_w, VERSION_Y, version_w, version_h, 0, *VERSION_VRAM, *VERSION_CLUT, 0, 1)]

    texts = [(w, t.rstrip().encode('ascii')) for w, t in LINES]
    check_text(WINDOWS, texts)
    start = (len(overlay) + 3) & ~3
    origin = BASE + start
    symbols = {k: v for k, v in globals().items() if isinstance(v, int)}
    symbols.update(NTIMS=len(tims), NSPRITES=len(sprites), NWINDOWS=len(WINDOWS), NLINES=len(texts))
    # The code, then its data: each part at the address its label names
    size = len(assemble(CODE, origin, {**symbols, **dict.fromkeys(['VARS', 'TIMS', 'SPRITES', 'RECTS', 'LINES'], 0)}))
    parts_of_data = [('VARS', bytes(4 + 4 * len(WINDOWS))),
                     ('TIMS', struct.pack(f'<{len(tims)}I', *tims)),
                     ('SPRITES', b''.join(struct.pack('<12I', *e) for e in sprites)),
                     ('RECTS', b''.join(struct.pack('<5H', *r) for r in WINDOWS)),
                     ('LINES', None)]
    data, address = b'', origin + size
    for name, block in parts_of_data:
        pad = (-len(data)) % 4
        data += bytes(pad)
        symbols[name] = address + len(data)
        if block is None:  # the line table, then the strings
            strings_at = symbols[name] + 8 * len(texts)
            table, strings, row = b'', b'', {}
            for w, t in texts:
                table += struct.pack('<BBHI', w, row.get(w, 0), 0, strings_at + len(strings))
                row[w] = row.get(w, 0) + 1
                strings += t + b'\x00'
            block = table + strings
        data += block
    code = assemble(CODE, origin, symbols)
    out = bytearray(overlay) + bytes(start - len(overlay)) + code + data
    # State 8 of the table goes to the new code
    struct.pack_into('<I', out, STATE_TABLE + 8 * 4 - BASE, origin)
    return bytes(out), logo_file

def compressed_tim(path, offset):
    with open(f"{GAME_DATA_IN_DIR}/{path}", "rb") as f: data = f.read()
    return data[offset:offset + 8 + struct.unpack_from('<I', data, offset)[0]]

def changelog_version():
    with open(os.path.join(ROOT, "CHANGELOG.md")) as f:
        return re.search(r'^## \[(v[^]]+)\]', f.read(), re.M).group(1)

if __name__ == "__main__":
    with open(f"{GAME_DATA_IN_DIR}/BIN/SMELOGO.BIN", "rb") as f: overlay = f.read()
    with open(f"{GAME_DATA_IN_DIR}/FIELD/SMELOGO.DAT", "rb") as f: logo_file = f.read()
    version = changelog_version()
    overlay, logo_file = patch(overlay, logo_file, compressed_tim(*WINDOW_PARTS), compressed_tim(*PORTRAIT), version)
    os.makedirs(f"{GAME_DATA_OUT_DIR}/FIELD", exist_ok=True)
    with open(f"{GAME_DATA_OUT_DIR}/BIN/SMELOGO.BIN", "wb") as f: f.write(overlay)
    with open(f"{GAME_DATA_OUT_DIR}/FIELD/SMELOGO.DAT", "wb") as f: f.write(logo_file)
    print(f"Written the info screen ({version}): BIN/SMELOGO.BIN ({len(overlay)} bytes), "
          f"FIELD/SMELOGO.DAT ({len(logo_file)} bytes)")
