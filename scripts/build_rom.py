# -*- coding: utf-8 -*-
# Extracts game files from the original .bin, and writes patched files back into a copy
# of it in place, so no ISO rebuilding tool (psximager) is needed.
#
# A patched file must fit in the sectors the original file uses. Its size in the ISO
# directory is updated if it changed. Every rewritten sector gets its EDC/ECC
# recomputed (Mode 2 Form 1).
#
#   python3 build_rom.py extract              # GAME_BIN -> GAME_DATA_IN_DIR
#   python3 build_rom.py inject               # GAME_BIN + GAME_DATA_OUT_DIR -> GAME_BIN_OUT

from script_config import *
import argparse
import os
import shutil
import struct
import sys

SECTOR = 2352
USER_DATA = 24      # sync (12) + header (4) + subheader (8)
DATA_SIZE = 2048

# EDC/ECC tables (CD-ROM ECMA-130)
ECC_F = [0] * 256
ECC_B = [0] * 256
EDC = [0] * 256
for i in range(256):
    j = ((i << 1) ^ (0x11D if i & 0x80 else 0)) & 0xFF
    ECC_F[i] = j
    ECC_B[i ^ j] = i
    e = i
    for _ in range(8):
        e = (e >> 1) ^ (0xD8018001 if e & 1 else 0)
    EDC[i] = e

def edc(data):
    e = 0
    for b in data:
        e = (e >> 8) ^ EDC[(e ^ b) & 0xFF]
    return e

def ecc_block(src, major_count, minor_count, major_mult, minor_inc):
    size = major_count * minor_count
    out = bytearray(major_count * 2)
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            t = src[index]
            index += minor_inc
            if index >= size: index -= size
            a ^= t
            b ^= t
            a = ECC_F[a]
        a = ECC_B[ECC_F[a] ^ b]
        out[major] = a
        out[major + major_count] = a ^ b
    return out

def fix_sector(sector):
    # Mode 2 Form 1: EDC over subheader + data, ECC computed with the header zeroed
    s = bytearray(sector)
    struct.pack_into('<I', s, 0x818, edc(s[0x10:0x818]))
    header = s[0x0C:0x10]
    s[0x0C:0x10] = b'\x00' * 4
    s[0x81C:0x8C8] = ecc_block(s[0x0C:], 86, 24, 2, 86)
    s[0x8C8:0x930] = ecc_block(s[0x0C:], 52, 43, 86, 88)
    s[0x0C:0x10] = header
    return bytes(s)

class Disc:
    def __init__(self, f):
        self.f = f

    def read(self, lba):
        self.f.seek(lba * SECTOR)
        return self.f.read(SECTOR)

    def data(self, lba):
        return self.read(lba)[USER_DATA:USER_DATA + DATA_SIZE]

    def write_data(self, lba, data):
        s = bytearray(self.read(lba))
        if s[USER_DATA:USER_DATA + DATA_SIZE] == data: return False
        s[USER_DATA:USER_DATA + DATA_SIZE] = data
        self.f.seek(lba * SECTOR)
        self.f.write(fix_sector(s))
        return True

    def files(self):
        pvd = self.data(16)
        assert pvd[1:6] == b'CD001', "Not an ISO 9660 disc"
        root = pvd[156:156 + 34]
        yield from self.walk(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0], '')

    def walk(self, lba, size, path):
        for n in range((size + DATA_SIZE - 1) // DATA_SIZE):
            sector = self.data(lba + n)
            i = 0
            while i < DATA_SIZE and sector[i]:
                rec = sector[i:i + sector[i]]
                name = rec[33:33 + rec[32]]
                if name not in (b'\x00', b'\x01'):
                    name = name.decode().split(';')[0]
                    elba, esize = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]
                    sys_use = rec[33 + rec[32] + (1 - rec[32] % 2):]
                    is_form2 = len(sys_use) >= 8 and sys_use[6:8] == b'XA' and sys_use[4] & 0x10
                    if rec[25] & 2:
                        yield from self.walk(elba, esize, path + name + '/')
                    else:
                        yield {"path": path + name, "lba": elba, "size": esize, "form2": bool(is_form2),
                               "record_lba": lba + n, "record_offset": i}
                i += sector[i]

def extract(bin_path, out_dir):
    with open(bin_path, 'rb') as f:
        disc = Disc(f)
        for entry in disc.files():
            if entry["form2"]: continue  # streamed audio/video, never patched
            data = b''.join(disc.data(entry["lba"] + n) for n in range((entry["size"] + DATA_SIZE - 1) // DATA_SIZE))
            dest = os.path.join(out_dir, entry["path"])
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, 'wb') as out: out.write(data[:entry["size"]])
            print(f"Extracted {entry['path']}")

def inject(bin_path, in_dir, patched_dir, out_path):
    shutil.copyfile(bin_path, out_path)
    with open(out_path, 'r+b') as f:
        disc = Disc(f)
        for entry in list(disc.files()):
            patched = os.path.join(patched_dir, entry["path"])
            if entry["form2"] or not os.path.exists(patched): continue
            with open(patched, 'rb') as p: data = p.read()
            with open(os.path.join(in_dir, entry["path"]), 'rb') as o:
                if o.read() == data: continue

            sectors = (entry["size"] + DATA_SIZE - 1) // DATA_SIZE
            if len(data) > sectors * DATA_SIZE:
                sys.exit(f"ERROR: {entry['path']} is {len(data)} bytes but only {sectors * DATA_SIZE} fit in place.")

            padded = data + b'\x00' * (sectors * DATA_SIZE - len(data))
            changed = sum(disc.write_data(entry["lba"] + n, padded[n * DATA_SIZE:(n + 1) * DATA_SIZE]) for n in range(sectors))

            if len(data) != entry["size"]:
                record = bytearray(disc.data(entry["record_lba"]))
                struct.pack_into('<I', record, entry["record_offset"] + 10, len(data))
                struct.pack_into('>I', record, entry["record_offset"] + 14, len(data))
                disc.write_data(entry["record_lba"], bytes(record))
            print(f"Patched {entry['path']} ({changed} sectors)")
    print(f"Written {out_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract files from, or patch files into, the game .bin.')
    parser.add_argument('command', choices=['extract', 'inject'])
    args = parser.parse_args(sys.argv[1:])

    if args.command == 'extract':
        extract(GAME_BIN, GAME_DATA_IN_DIR)
    else:
        inject(GAME_BIN, GAME_DATA_IN_DIR, GAME_DATA_OUT_DIR, GAME_BIN_OUT)
