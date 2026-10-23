# -*- coding: utf-8 -*-
# Puts the translated images into the game's containers (FIELD.ACB and friends).
#
# Many images are TIMs compressed with the same LZSS as MONBOOK.TIM, stored as
# (compressed size, decompressed size, data) at some offset in the container. A
# replacement is recompressed and written into the same slot, so it must compress to
# the original size or smaller; the rest of the slot is zero-filled. Others are plain
# TIMs (e.g. the VS screen font in BATTLE/TEX1.DAT), replaced byte for byte.
#
# Translated images live in the repo as indexed PNGs, at
# graphics/<file in the game>/<offset in hex>.png, e.g. graphics/FIELD/FIELD.ACB/01dec0.png.
# Some files (e.g. BATTLE/CARD.DAT) are one compressed block with plain TIMs inside; their
# images are named z<offset>.png, the offset being inside the decompressed file, and the
# whole file is recompressed once all of them are in.
# Pixel values are palette indices, so keep the PNG's palette when editing it. 16bpp
# (direct colour) images are RGBA PNGs instead, transparent where the game's pixel is 0.

from script_config import *
from lzss import compress, decompress
import glob
import os
import struct

GRAPHICS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'graphics')

# Images the game stores more than once: one PNG goes into every copy
COPIES = {
    # the stadium menu: each stadium has its own copy
    "FIELD/FIELD.ACB/041f4c.png": ["FIELD/FIELD.ACB/056b80", "FIELD/FIELD.ACB/06aedc", "FIELD/FIELD.ACB/080300",
                                   "FIELD/FIELD.ACB/094894", "FIELD/FIELD.ACB/0a97c4"],
    # the VS screen font, loaded from either file
    "BATTLE/TEX1.DAT/011500.png": ["BATTLE/TEX2.DAT/012680"],
}

TIM_MAGIC = b'\x10\x00\x00\x00'

class Tim:
    def __init__(self, data):
        assert data[:4] == TIM_MAGIC, "Not a TIM"
        self.flag = struct.unpack_from('<I', data, 4)[0]
        self.bpp = {0: 4, 1: 8, 2: 16}[self.flag & 3]
        p = 8
        self.clut_header, self.clut = b'', []
        if self.flag & 8:
            self.clut_header = data[p:p+12]
            clen, _, _, cw, ch = struct.unpack_from('<IHHHH', data, p)
            self.clut = list(struct.unpack_from(f'<{cw*ch}H', data, p + 12))
            p += clen
        self.image_header = data[p:p+12]
        ilen, _, _, iw, ih = struct.unpack_from('<IHHHH', data, p)
        self.width = iw * {4: 4, 8: 2, 16: 1}[self.bpp]
        self.height = ih
        pixels = data[p+12:p+ilen]
        self.tail = data[p+ilen:]
        if self.bpp == 4:
            self.pixels = [(b >> s) & 15 for b in pixels for s in (0, 4)]
        elif self.bpp == 8:
            self.pixels = list(pixels)
        else:  # direct colour: pixels are 15-bit colours, no palette
            self.pixels = list(struct.unpack(f'<{len(pixels) // 2}H', pixels))

    def to_bytes(self):
        if self.bpp == 4:
            pixels = bytes(self.pixels[i] | (self.pixels[i+1] << 4) for i in range(0, len(self.pixels), 2))
        elif self.bpp == 8:
            pixels = bytes(self.pixels)
        else:
            pixels = struct.pack(f'<{len(self.pixels)}H', *self.pixels)
        clut = self.clut_header + struct.pack(f'<{len(self.clut)}H', *self.clut)
        return TIM_MAGIC + struct.pack('<I', self.flag) + clut + self.image_header + pixels + self.tail

def read_compressed(data, offset):
    csize, usize = struct.unpack_from('<II', data, offset)
    return decompress(data[offset:offset + 8 + csize]), csize

def replace_compressed(data, offset, new):
    _, csize = read_compressed(data, offset)
    packed = compress(new)
    if len(packed) > 8 + csize:
        raise ValueError(f"Image at {offset:x} compresses to {len(packed) - 8} bytes; its slot holds {csize}.")
    out = bytearray(data)
    out[offset:offset + 8 + csize] = packed + b'\x00' * (8 + csize - len(packed))
    return bytes(out)

def tim_length(data, offset):
    clut = struct.unpack_from('<I', data, offset + 8)[0] if data[offset + 4] & 8 else 0
    return 8 + clut + struct.unpack_from('<I', data, offset + 8 + clut)[0]

def read_image(data, offset):
    # A TIM at offset, plain or compressed
    if data[offset:offset + 4] == TIM_MAGIC:
        return Tim(bytes(data[offset:offset + tim_length(data, offset)]))
    return Tim(bytes(read_compressed(data, offset)[0]))

def replace_image(data, offset, tim):
    if data[offset:offset + 4] != TIM_MAGIC:
        return replace_compressed(data, offset, tim.to_bytes())
    new = tim.to_bytes()
    assert len(new) == tim_length(data, offset), "A plain TIM must keep its size"
    return data[:offset] + new + data[offset + len(new):]

def from_rgb(r, g, b, a, old=None):
    # A 15-bit colour; alpha 0 is the transparent 0x0000, and opaque black gets the
    # semi-transparency bit so it isn't transparent. Unchanged pixels keep their old bits.
    if a == 0: return 0
    colour = (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)
    if old is not None and old & 0x7FFF == colour and old != 0: return old
    return colour or 0x8000

def import_png(tim, path):
    from PIL import Image
    img = Image.open(path)
    if tim.bpp == 16:
        if img.size != (tim.width, tim.height):
            raise ValueError(f"{path} is {img.size[0]}x{img.size[1]}; the game image is {tim.width}x{tim.height}.")
        tim.pixels = [from_rgb(*c, old) for c, old in zip(img.convert('RGBA').getdata(), tim.pixels)]
        return
    if img.mode != 'P':
        raise ValueError(f"{path} must be an indexed (palette) PNG; it is {img.mode}.")
    if img.size != (tim.width, tim.height):
        raise ValueError(f"{path} is {img.size[0]}x{img.size[1]}; the game image is {tim.width}x{tim.height}.")
    pixels = list(img.getdata())
    if max(pixels) >= (16 if tim.bpp == 4 else 256):
        raise ValueError(f"{path} uses palette index {max(pixels)}, too many for a {tim.bpp}bpp image.")
    tim.pixels = pixels

def translated_pngs():
    return sorted(glob.glob(os.path.join(GRAPHICS_DIR, '**', '*.png'), recursive=True))

def apply_all():
    # {game file: [(PNG, image name: <offset> or z<offset>)]}
    by_file = {}
    for path in translated_pngs():
        rel = os.path.relpath(path, GRAPHICS_DIR)
        for target in [rel[:-4]] + COPIES.get(rel, []):
            by_file.setdefault(os.path.dirname(target), []).append((path, os.path.basename(target)))
    for game_file, images in by_file.items():
        out = f"{GAME_DATA_OUT_DIR}/{game_file}"
        source = out if os.path.exists(out) else f"{GAME_DATA_IN_DIR}/{game_file}"
        with open(source, "rb") as f: data = f.read()
        inner = [(path, name) for path, name in images if name.startswith('z')]
        if inner:
            # The whole file is one compressed block
            unpacked = bytes(decompress(data))
            for path, name in inner:
                offset = int(name[1:], 16)
                tim = read_image(unpacked, offset)
                import_png(tim, path)
                unpacked = replace_image(unpacked, offset, tim)
            packed = compress(unpacked)
            if len(packed) > len(data):
                raise ValueError(f"{game_file} compresses to {len(packed)} bytes; it was {len(data)}.")
            data = packed + b'\x00' * (len(data) - len(packed))
        for path, name in images:
            if name.startswith('z'): continue
            offset = int(name, 16)
            tim = read_image(data, offset)
            import_png(tim, path)
            data = replace_image(data, offset, tim)
        for path, name in images: print(f"Imported {os.path.relpath(path, GRAPHICS_DIR)} into {game_file}/{name}")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f: f.write(data)

if __name__ == "__main__":
    apply_all()
