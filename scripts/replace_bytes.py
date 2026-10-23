# -*- coding: utf-8 -*-

from script_config import *
from lzss import compress, decompress
import argparse
import sys
import os
import struct
import strings_patch

# strings where the English version should end with term, then padded with spaces
term_strings = [
    "レックス",
    "オークス",
    "リーダー",
    "メリック",
    "マイヤー",
    "プラーグ",
    "ピラミン",
    "ジョニー",
    "ポックル",

    "パイディア",
    "クエッキー",
    "ペリーニン",
    "スクリーム",
    "フランキー",
    "マシンガン",

    "バッドバット",

    "エンジェルマニア",
    "マシンガンジョー",
    "スピードマスター",

    "ブラー",
    "スカル",
    "エッヂ",

    "カムカムクロー",
]

MONBOOK_PARAGRAPH_LENGTH = 308
MONBOOK_LINE_LENGTH = 36

filename = "slps"

space = b'\x20'
blank = b'\xFF'
space = b'\x20'
term = b'\x00'
endline = b'\x0C'
jadash = b'\x81\x5B' # This: ー

ja_keyboard = b'\x83\x52\x00\x00\x83\x50\x00\x00\x83\x4E\x00\x00\x83\x4C\x00\x00\x83\x4A\x00\x00\x81\x40\x00\x00\x83\x49\x00\x00\x83\x47\x00\x00\x83\x45\x00\x00\x83\x43\x00\x00\x83\x41\x00\x00\x83\x67\x00\x00\x83\x65\x00\x00\x83\x63\x00\x00\x83\x60\x00\x00\x83\x5E\x00\x00\x83\x5C\x00\x00\x83\x5A\x00\x00\x83\x58\x00\x00\x83\x56\x00\x00\x83\x54\x00\x00\x83\x7A\x00\x00\x83\x77\x00\x00\x83\x74\x00\x00\x83\x71\x00\x00\x83\x6E\x00\x00\x83\x6D\x00\x00\x83\x6C\x00\x00\x83\x6B\x00\x00\x83\x6A\x00\x00\x83\x69\x00\x00\x83\x88\x00\x00\x83\x86\x00\x00\x83\x84\x00\x00\x83\x82\x00\x00\x83\x81\x00\x00\x83\x80\x00\x00\x83\x7E\x00\x00\x83\x7D\x00\x00\x83\x94\x00\x00\x83\x93\x00\x00\x83\x92\x00\x00\x83\x8F\x00\x00\x83\x8D\x00\x00\x83\x8C\x00\x00\x83\x8B\x00\x00\x83\x8A\x00\x00\x83\x89\x00\x00\x83\x5D\x00\x00\x83\x5B\x00\x00\x83\x59\x00\x00\x83\x57\x00\x00\x83\x55\x00\x00\x83\x53\x00\x00\x83\x51\x00\x00\x83\x4F\x00\x00\x83\x4D\x00\x00\x83\x4B\x00\x00\x83\x7B\x00\x00\x83\x78\x00\x00\x83\x75\x00\x00\x83\x72\x00\x00\x83\x6F\x00\x00\x83\x68\x00\x00\x83\x66\x00\x00\x83\x64\x00\x00\x83\x61\x00\x00\x83\x5F\x00\x00\x83\x48\x00\x00\x83\x46\x00\x00\x83\x44\x00\x00\x83\x42\x00\x00\x83\x40\x00\x00\x83\x7C\x00\x00\x83\x79\x00\x00\x83\x76\x00\x00\x83\x73\x00\x00\x83\x70\x00\x00\x81\x5B\x00\x00\x83\x62\x00\x00\x83\x87\x00\x00\x83\x85\x00\x00\x83\x83'
en_keyboard = b'\x65\x00\x00\x00\x64\x00\x00\x00\x63\x00\x00\x00\x62\x00\x00\x00\x61\x00\x00\x00\x20\x00\x00\x00\x45\x00\x00\x00\x44\x00\x00\x00\x43\x00\x00\x00\x42\x00\x00\x00\x41\x00\x00\x00\x6A\x00\x00\x00\x69\x00\x00\x00\x68\x00\x00\x00\x67\x00\x00\x00\x66\x00\x00\x00\x4A\x00\x00\x00\x49\x00\x00\x00\x48\x00\x00\x00\x47\x00\x00\x00\x46\x00\x00\x00\x6F\x00\x00\x00\x6E\x00\x00\x00\x6D\x00\x00\x00\x6C\x00\x00\x00\x6B\x00\x00\x00\x4F\x00\x00\x00\x4E\x00\x00\x00\x4D\x00\x00\x00\x4C\x00\x00\x00\x4B\x00\x00\x00\x72\x00\x00\x00\x71\x00\x00\x00\x70\x00\x00\x00\x54\x00\x00\x00\x53\x00\x00\x00\x52\x00\x00\x00\x51\x00\x00\x00\x50\x00\x00\x00\x76\x00\x00\x00\x75\x00\x00\x00\x74\x00\x00\x00\x73\x00\x00\x00\x59\x00\x00\x00\x58\x00\x00\x00\x57\x00\x00\x00\x56\x00\x00\x00\x55\x00\x00\x00\x20\x00\x00\x00\x7A\x00\x00\x00\x79\x00\x00\x00\x78\x00\x00\x00\x77\x00\x00\x00\x21\x00\x00\x00\x3F\x00\x00\x00\x23\x00\x00\x00\x3E\x00\x00\x00\x3C\x00\x00\x00\x26\x00\x00\x00\x25\x00\x00\x00\x2A\x00\x00\x00\x24\x00\x00\x00\x5C\x00\x00\x00\x40\x00\x00\x00\x2B\x00\x00\x00\x2D\x00\x00\x00\x27\x00\x00\x00\x22\x00\x00\x00\x39\x00\x00\x00\x38\x00\x00\x00\x37\x00\x00\x00\x36\x00\x00\x00\x35\x00\x00\x00\x34\x00\x00\x00\x33\x00\x00\x00\x32\x00\x00\x00\x31\x00\x00\x00\x30\x00\x00\x00\x5F\x00\x00\x00\x2E\x00\x00\x00\x2C\x00\x00\x00\x29\x00\x00\x00\x28\x00'

# The name input grid draws each row by joining its keys' strings, so each key's 4-byte slot
# shows a full-width character like the Japanese, then holds the 1-byte one it types
FULL_WIDTH = {' ': '　', '\\': '￥', '"': '”', "'": '’', '-': '−'}

def name_keyboard():
    keys = en_keyboard[0::4]
    show = lambda c: FULL_WIDTH.get(c, chr(ord(c) + 0xFEE0)).encode('shift-jis')
    return b''.join(show(chr(c)) + b'\x00' + bytes([c]) for c in keys)

allowedbuffer = 0
too_many_bytes = False

# Memory card save header in SLPS: the save's file name, then its title as shown on memory
# card screens. The title is full-width Shift-JIS (what the BIOS can display) and has the
# original title's 26 bytes plus 8 bytes of zero padding to use.
SAVE_FILE_NAME = b'BISLPS-01468GAMON\x00\x00\x00'
SAVE_TITLE = "ＧＡＮＧＷＡＹ　ＭＯＮＳＴＥＲＳ".encode('shift-jis')
SAVE_TITLE_BYTES = 34

def set_save_title(data):
    start = data.index(SAVE_FILE_NAME) + len(SAVE_FILE_NAME)
    if len(SAVE_TITLE) + 1 > SAVE_TITLE_BYTES:
        raise ValueError("Save title is too long")
    return data[:start] + SAVE_TITLE.ljust(SAVE_TITLE_BYTES, b'\x00') + data[start + SAVE_TITLE_BYTES:]

# Coin bets in CASINO.BIN. The game loads each of these strings by its own address, and the
# compiler padded each to a 4-byte boundary, so a translation may also use that padding.
# Plain spaces line the amounts up (full-width spaces are wider than full-width digits).
CASINO_BETS = [("　　５枚", "  5 coins"), ("　２０枚", " 20 coins"), ("１００枚", "100 coins"),
               ("２００枚", "200 coins"), ("４００枚", "400 coins"),
               ("５枚", " 5"), ("１０枚", "10"), ("２０枚", "20"), ("５０枚", "50")]

# Files whose strings strings_patch.py may repack
RELOCATE = {"field", "casino", "title", "vsmode", "ending", "slps", "opendemo"}

def replace_in_slot(data, old, new):
    # Replace the whole string old (between end markers) with new, using the zero padding
    # after it, up to the next string
    old, new = old.encode('shift-jis'), new.encode('shift-jis')
    match = b'\x00' + old + b'\x00'
    if data.count(match) != 1:
        raise ValueError(f"Expected one {old.decode('shift-jis')}, found {data.count(match)}")
    start = data.index(match) + 1
    end = start + len(old)
    while end < len(data) and data[end] == 0: end += 1
    if len(new) + 1 > end - start:
        raise ValueError(f"'{new.decode()}' needs {len(new) + 1} bytes; the slot has {end - start}.")
    return data[:start] + new.ljust(end - start, b'\x00') + data[end:]

def replace_once(data, old, new):
    if data.count(old) != 1:
        raise ValueError(f"Expected one match for {old.hex()}, found {data.count(old)}")
    return data.replace(old, new)

def replace_asm(filename, data):
    if filename == "slps":
        data = set_save_title(data)

        # Delete only one byte at a time during input mode
        data = data.replace(
                b'\x21\x10\x62\x00\xFE\xFF\x40\xA0',
                b'\x21\x10\x62\x00\xFF\xFF\x40\xA0'
                )

        # Name input, adding a key (80020658, a0 = the key's slot): the game appended the
        # slot's string to the name, the same string the grid shows. Each slot now holds a
        # full-width character to show and, in its last byte, the letter to type (see
        # name_keyboard), so append just that byte, up to 8 letters. strlen is a BIOS call that
        # doesn't read a0 straight away, so a0 can load in its delay slot:
        #   addiu sp, sp, -0x18        addiu sp, sp, -0x18
        #   sw    s0, 0x10(sp)         sw    s0, 0x10(sp)
        #   move  s0, a0               move  s0, a0
        #   lw    a0, 0x310(gp)        sw    ra, 0x14(sp)
        #   sw    ra, 0x14(sp)         jal   strlen
        #   jal   strlen               lw    a0, 0x310(gp)
        #   nop                        slti  v1, v0, 8
        #   slti  v0, v0, 0x10         beqz  v1, 8002068c
        #   beqz  v0, 8002068c         lw    a0, 0x310(gp)
        #   nop                        lbu   a1, 3(s0)
        #   lw    a0, 0x310(gp)        addu  a0, a0, v0
        #   jal   strcat               sb    a1, 0(a0)
        #   move  a1, s0               sb    zero, 1(a0)
        #   lw    ra, 0x14(sp)         lw    ra, 0x14(sp)
        #   ...                        ...
        data = replace_once(data,
                bytes.fromhex('e8ffbd27' '1000b0af' '21808000' '1003848f' '1400bfaf' '1130010c'
                              '00000000' '10004228' '04004010' '00000000' '1003848f' 'fd2f010c'
                              '21280002' '1400bf8f'),
                bytes.fromhex('e8ffbd27' '1000b0af' '21808000' '1400bfaf' '1130010c' '1003848f'
                              '08004328' '05006010' '1003848f' '03000592' '21208200' '000085a0'
                              '010080a0' '1400bf8f'))

        # Start deletion at the first byte instead of second
        data = data.replace(
                b'\x21\x18\x40\x00\x02\x00\x62\x28',
                b'\x21\x18\x40\x00\x01\x00\x62\x28',
            )

        # Field messages (forward_one_font, 80020bec): after a 1-byte character the game draws
        # the next byte in the same step if it's below 0x81, without checking for a line or box
        # break, so a break right after an odd number of letters was drawn as a character. A
        # player name of odd length shifts every line it's in that way. Only pair printable
        # bytes (0x20-0x80), so breaks are always seen:
        #   80020cac  lbu   v0, 1(a0)        lbu   v0, 1(a0)
        #   80020cb0  nop                    lhu   v1, 0x33c(gp)  (moved up)
        #   80020cb4  sltiu v0, v0, 0x81     addiu v0, v0, -0x20
        #   80020cb8  beqz  v0, 80020d38     sltiu v0, v0, 0x61
        #   80020cbc  andi  v0, a1, 0xffff   beqz  v0, 80020d38
        #   80020cc0  lhu   v1, 0x33c(gp)    andi  v0, a1, 0xffff
        #   80020cc4  nop                    nop
        data = replace_once(data,
                bytes.fromhex('01008290' '00000000' '8100422c' '1f004010' 'ffffa230' '3c038397' '00000000'),
                bytes.fromhex('01008290' '3c038397' 'e0ff4224' '6100422c' '1e004010' 'ffffa230' '00000000'))

    if filename == "casino":
        for old, new in CASINO_BETS:
            data = replace_in_slot(data, old, new)

    if filename == "battle":
        # 01 00 83 90 -> 00 00 83 90
        # 00 00 82 90 -> 83 00 02 34 (change command to ori with 0x83)
        # set first register with 0x83 and load the first byte of text, instead of loading two bytes
        # this will cause the text to draw again on the VS screen
        # Note that it isn't real Japanese, it is just associating characters based on ascii characters with 0x83 prepended to it
        data = data.replace(
            b'\x08\x00\xE0\x03\x60\x00\xBD\x27\x0D\x80\x02\x3C\xDC\x81\x42\x8C\x00\x00\x00\x00\x03\x00\x82\x14\x00\x00\x00\x00\x0D\x80\x02\x3C\xD8\x81\x42\x8C\x08\x00\xE0\x03\x00\x00\x00\x00\x00\x00\x82\x90\x01\x00\x83\x90\x00\x12\x02\x00\x21\x18\x62\x00\xFF\xFF\x64\x30\x5B\x81\x02\x34\x02\x00\x82\x14\x50\x00\x05\x24\x4F\x00\x05\x24\x3F\x83\x02\x34\x2B\x10\x44\x00\x0A\x00\x40\x10\x7E\x83\x02\x34\x2B\x10\x44\x00\x03\x00\x40\x14\x94\x83\x02\x34\x31\xC7\x02\x08',
            b'\x08\x00\xE0\x03\x60\x00\xBD\x27\x0D\x80\x02\x3C\xDC\x81\x42\x8C\x00\x00\x00\x00\x03\x00\x82\x14\x00\x00\x00\x00\x0D\x80\x02\x3C\xD8\x81\x42\x8C\x08\x00\xE0\x03\x00\x00\x00\x00\x83\x00\x02\x34\x00\x00\x83\x90\x00\x12\x02\x00\x21\x18\x62\x00\xFF\xFF\x64\x30\x5B\x81\x02\x34\x02\x00\x82\x14\x50\x00\x05\x24\x4F\x00\x05\x24\x3F\x83\x02\x34\x2B\x10\x44\x00\x0A\x00\x40\x10\x7E\x83\x02\x34\x2B\x10\x44\x00\x03\x00\x40\x14\x94\x83\x02\x34\x31\xC7\x02\x08'
            )
        # swap the bit shift with the command that adds 8, so it won't skip every 2nd letter when drawing battle text
        data = data.replace(
            b'\x21\x28\xA3\x00\x00\x8C\x14\x00\x03\x8C\x11\x00\x40\x80\x11\x00\x08\x00\x04\x26\x1B\xC7\x02\x0C\x21\x20\xA4\x00\x21\x80\x11\x02\x40\x80\x10\x00\x80\x02\x10\x26\x00\x84\x10\x00\x03\x24\x10\x00',
            b'\x21\x28\xA3\x00\x00\x8C\x14\x00\x03\x8C\x11\x00\x08\x00\x24\x26\x40\x80\x11\x00\x1B\xC7\x02\x0C\x21\x20\xA4\x00\x21\x80\x11\x02\x40\x80\x10\x00\x80\x02\x10\x26\x00\x84\x10\x00\x03\x24\x10\x00'
            )

        # Narrower VS screen letters, so names of up to 12 characters fit: each glyph is
        # copied into the name strip 16px wide instead of 24 (vs_font.py draws them that
        # way), the strip position advances 16px per character, and 12 characters are
        # drawn instead of 8. The strip stays 192px wide, and name fields are 16 bytes.
        data = replace_once(data,
            b'\x1b\xc7\x02\x0c\x21\x20\xa4\x00\x21\x80\x11\x02\x40\x80\x10\x00\x80\x02\x10\x26',
            b'\x1b\xc7\x02\x0c\x21\x20\xa4\x00\x00\x00\x00\x00\x40\x80\x10\x00\x80\x02\x10\x26')  # x = 4*i, not 6*i
        data = replace_once(data,
            b'\x06\x00\x06\x24\x18\x00\x07\x24',
            b'\x04\x00\x06\x24\x18\x00\x07\x24')  # glyph width 4 halfwords (16px), height 24
        data = replace_once(data,
            b'\x08\x00\x42\x28\xcd\xff\x40\x14',
            b'\x0c\x00\x42\x28\xcd\xff\x40\x14')  # 12 characters per name

        # Digits on the VS screen. The lookup above (B1C6C, after the edit at its start)
        # turns a name byte into a glyph number: 0x40-0x7e to glyphs 0-62, anything below
        # to the blank glyph 80. Rewritten so digits go to glyphs 64-73 (katakana slots
        # English names never reach; vs_font.py draws the digits there):
        #   lbu v1,0(a0); addiu v0,v1,-0x30; sltiu a0,v0,10; beq a0,zero,+3
        #   addiu a1,v1,-0x40; jr ra; addiu v0,v0,64              (digit: 64 + d)
        #   sltiu a0,a1,0x3f; bne a0,zero,+2; nop; addiu a1,zero,80 (else blank)
        #   jr ra; andi v0,a1,0xffff
        lookup = [0x90830000, 0x2462ffd0, 0x2c44000a, 0x10800003, 0x2465ffc0, 0x03e00008, 0x24420040,
                  0x2ca4003f, 0x14800002, 0x00000000, 0x24050050, 0x03e00008, 0x30a2ffff]
        data = replace_once(data,
            bytes.fromhex('83000234000083900012020021186200ffff64305b81023402008214500005244f000524'
                          '3f8302342b1044000a0040107e8302342b104400030040149483023431c70208c07c6524'
                          '2b1044000200401400000000bf7c65240800e003ffffa230'),
            struct.pack('<24I', *(lookup + [0] * 11)))

    return data

def load_monbook_ja(filename):
    with open(filename, "rb") as f: data = decompress(f.read())
    idx = data.find(b'\x10\x00\x00\x00')
    data = data[:idx]
    results = []
    
    while len(data) > 0:
        results.append(data[:MONBOOK_PARAGRAPH_LENGTH])
        data = data[MONBOOK_PARAGRAPH_LENGTH:]

    return results

def load_monbook_translations(filename):
    with open(filename, "r") as f:
        paragraphs = f.read().strip().encode('shift-jis').split(b'\n\n\n\n')

    results = []

    for p in paragraphs:
        lines = p.split(b'\n')
        if len(lines) < 8:
            raise ValueError("Paragraph has less than 8 lines (starts with {})"
                .format(final_p[:20]))

        for i in range(len(lines)):
            line = lines[i]
            if len(line) > MONBOOK_LINE_LENGTH:
                raise ValueError(f"Line {line} is too long by {len(line)-MONBOOK_LINE_LENGTH} bytes")
            diff = 36 - len(line)
            line += (b'\x20' * diff)
            lines[i] = line

        final_p = b'\r\n'.join(lines)
        diff = (MONBOOK_PARAGRAPH_LENGTH - len(final_p)) // 2
        final_p += (b'\r\n' * diff)

        if len(final_p) > MONBOOK_PARAGRAPH_LENGTH:
            raise ValueError("Final paragraph is too long by {} bytes (starts with {})"
                .format(len(final_p)-MONBOOK_PARAGRAPH_LENGTH, final_p[:20]))

        results.append(final_p)

    return results

def fix_line(line):
    line = line.replace("\\n", "\n")
    temp = ''
    d_length = 0

    for chunk in line.split(' '):
        if (d_length + len(chunk)) > 24:
            temp += '\n' + chunk
            d_length = len(chunk)
        else:
            temp += " " + chunk
            d_length += len(chunk) + 1

    return temp.strip()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Script to translate Gangway Monsters.')
    parser.add_argument('filename', help='Name of game file to modify (e.g. "slps" or "battle")')
    parser.add_argument('--sort', action='store_true',
                   help='Sort the translation pairing for the relevant game file. Use when translations have been modified. Default is false.')
    parser.add_argument('--export', action='store_false',
                   help='Build and export new game binary. Default is true.')

    args = parser.parse_args(sys.argv[1:])


    if args.filename == "monbook":
        monbook_ja = load_monbook_ja(f"{GAME_DATA_IN_DIR}/BATTLE/MONBOOK.TIM")

        try:
            monbook_en = load_monbook_translations(f"{TRANSLATIONS_PATH}/en.{args.filename}.txt")
        except ValueError as e:
            too_many_bytes = True
            too_many_bytes_reason = str(e)

        if too_many_bytes:
            print(too_many_bytes_reason)
        else:
            with open(f"{GAME_DATA_IN_DIR}/BATTLE/MONBOOK.TIM", "rb") as f:
                data = decompress(f.read())

            for i in range(len(monbook_en)):
                data = data.replace(monbook_ja[i], monbook_en[i])

            compressed_data = compress(data)
            with open(f"{GAME_DATA_OUT_DIR}/BATTLE/MONBOOK.TIM", "wb") as f: f.write(compressed_data)

    else:
        if args.filename == "slps":
            with open(f"{GAME_DATA_IN_DIR}/SLPS_014.68", "rb") as f: rawdata = f.read()
        elif args.filename == "fdevent":
            with open(f"{GAME_DATA_IN_DIR}/FIELD/FDEVENT.ACB", "rb") as f: rawdata = f.read()
        elif args.filename == "opendemo":
            # Run this after running dialogue scripts. This will translate mostly menu items.
            with open(f"{GAME_DATA_IN_DIALOGUE_DIR}/{args.filename}.BIN", "rb") as f: rawdata = f.read()
        else:
            with open(f"{GAME_DATA_IN_DIR}/BIN/{args.filename.upper()}.BIN", "rb") as f: rawdata = f.read()

        with open(f"{TRANSLATIONS_PATH}/ja.{args.filename}.txt", "r") as f: dataja = f.read()
        with open(f"{TRANSLATIONS_PATH}/en.{args.filename}.txt", "r") as f: dataen = f.read()

        linesja = dataja.split("\n")
        linesen = dataen.split("\n")

        if args.sort:
            temp_lines = []
            all_lines = []
            finalja = []
            finalen = []
            for i in range(len(linesja)):
                temp_lines.append(linesja[i] + "\t" + linesen[i])
            all_lines = sorted(temp_lines, key=len, reverse=True)
            for line in all_lines:
                parts = line.split("\t")
                finalja.append(parts[0])
                finalen.append(parts[1])
            with open(f"{TRANSLATIONS_PATH}/ja.{args.filename}.txt", "w") as f: f.write("\n".join(finalja))
            with open(f"{TRANSLATIONS_PATH}/en.{args.filename}.txt", "w") as f: f.write("\n".join(finalen))
            print(f"Sorted {args.filename} translation pairings.")
            sys.exit(0)

        dataresult = rawdata

        # Strings that can be repacked (see strings_patch.py) may be longer than the Japanese
        relocate = args.filename in RELOCATE
        # "\\n" and "\\f" stand for a line break and a new box, for strings that span them. Longer
        # Japanese goes first, so a whole message is replaced before the lines inside it (a stable
        # sort: of two translations of one string, the first still wins)
        unescape = lambda t: t.replace("\\n", "\n").replace("\\f", "\x0c")
        order = sorted(range(len(linesja)), key=lambda i: -len(unescape(linesja[i]).encode('shift-jis')))
        pairs = [(unescape(linesja[i]).encode('shift-jis'), unescape(linesen[i]).encode('shift-jis'))
                 for i in order if linesja[i]]
        if relocate:
            _, movable = strings_patch.movable_strings(rawdata, [a for a, _ in pairs])
            def only_movable(ja):
                i = rawdata.find(ja)
                while i >= 0:
                    if not any(s <= i < e for s, e in movable.items()): return False
                    i = rawdata.find(ja, i + 1)
                return True

        for i in order:
            b1 = unescape(linesja[i]).encode('shift-jis')
            b2 = unescape(linesen[i]).encode('shift-jis')

            if len(b2) <= len(b1):
                l = len(b1) - len(b2)

                if (b1.decode('shift-jis') in term_strings) and args.filename in ["slps"]:
                    padding = (term * l)
                else:
                    padding = (space * l)

                b2 += padding
                dataresult = dataresult.replace(b1, b2)
            elif relocate and b1 and only_movable(b1):
                pass  # strings_patch puts the longer English in
            else:
                too_many_bytes = True
                print(b1.decode('shift-jis'))
                print(b2.decode('shift-jis'))
                print()

        if too_many_bytes:
            print("ERROR: Fix above issues first.")
        else:
            dataresult = replace_asm(args.filename, dataresult)
            if relocate:
                dataresult, _ = strings_patch.patch(rawdata, dataresult, pairs, verbose=True)
            if args.filename == "slps":
                dataresult = replace_once(dataresult, ja_keyboard + b'\x00\x00', name_keyboard())
                binname = f"{GAME_DATA_OUT_DIR}/SLPS_014.68"
                with open(binname, "wb") as f: f.write(dataresult)
            elif args.filename == "fdevent":
                binname = f"{GAME_DATA_OUT_DIR}/FIELD/FDEVENT.ACB"
                with open(binname, "wb") as f: f.write(dataresult)
            else:
                fname = args.filename.upper()
                binname = f"{GAME_DATA_OUT_DIR}/BIN/{fname}.BIN"
                with open(binname, "wb") as f: f.write(dataresult)

            print(f"Written data to {binname}")

    if args.export and not too_many_bytes:
        os.system(f"/bin/bash -c \"cd {GAME_IMAGE_DIR} && psxbuild g.cat && rm {GAME_IMAGE_EMU_BIN} && cp g.bin {GAME_IMAGE_EMU_BIN}\"")
        print(f"Built and imported game binary")








