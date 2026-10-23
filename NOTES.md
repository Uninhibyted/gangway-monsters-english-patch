Notes on what parts of the game's logic has been changed.

## Battle Text

The way the monsters' names are rendered in the VS screen had to be updated for it to show up.

<img src="debug/images/battle_text_address.png" width="25%">

* `11B500` is the address location (see register `s7`) of the asset that is used to render text.
* `C1A74` is when it updates the pointer to the the Japanese character it will render.

<img src="debug/images/battle_text_change_commands.png" width="25%">

* `B1C6C` - game will jump here after loading the monster names in memory. Change it from `lbu v0, 0x0000(a0)` to `ori v0, 0x0083` 
* `B1C70` - Change it from `lbu v1, 0x0001(a0)` to `lbu v1, 0x0000(a0)`

This changes it to load only the first and current byte. The or-ing with `0x83` is to fake a shift-jis character.

<img src="debug/images/battle_text_swap_commands.png" width="25%">

* `C1A1C` - Change this to `addiu a0, s1, 0x0008`
* `C1A20` - Change this to `sll s0, s1, 0x1`

The shifting is the game's way to iterate through names at two bytes at a time. It adds 8 because that's how many "slots" each name gets in memory. By changing it to shift after the addition, it will go through each byte one at a time, but shifting later will allow the game's math to work when choosing which Japanese character to render.

Keep in mind the new rendered text is not real Japanese. It is just associating each character with an equivalent shift-jis code (e.g. `A`, which is `0x41`, becomes linked with `0x83 0x41`, which is `ア`). This is fine though, because after applying these changes, making the VS screen show English characters would just be a matter of updating the image itself.

The font is a TIM of 84 glyphs (24x24) in `BATTLE/TEX1.DAT` and `TEX2.DAT`. The translated
font (`graphics/BATTLE/TEX1.DAT/011500.png`) has English letters where the codes above land:
A-Z on glyphs 1-26, a-z (as small capitals) on 33-58, digits on 64-73.

`replace_asm` for `battle` also makes glyphs 16px wide instead of 24, so 12 characters fit
instead of 8 (`C1A2C`, `C1A58`, `C1A98`), and rewrites the lookup at `B1C6C` so digits get
their own glyphs.

#### TODO's

* Names longer than 12 characters are cut off on the VS screen.
* Punctuation and spaces show as blanks (codes below `0x40` other than digits map to the blank glyph).

## Name Input

See `replace_bytes.py`. The updates made in `replace_asm` when updating the SLPS file is all related to the name input. It basically changes it to only read/write 1 byte instead of 2, and updates the way the cursor moves so that it will hover over the character in the right spot.

#### TODO's

* The text in the input box looks kind of squished. There is a way to update the spacing of each character (located in roughly the same location as the updated input code), but it will change the spacing of characters throughout the game.

## Workflow

Workflow for finding and patching game logic

### Steps

* Use Bizhawk to filter what memory addresses are getting read/written to
* Go on Mednafen or pSX, step through disassembled code in debugger. Add read/write memory breakpoints to find where the code is.
* When found, dump memory and open it in IDA Pro. Click on the area where the code is, which IDA will find all the references to and show a nice map that makes life somewhat easier
* Dump the results to an ASM file
* Repeat above steps until it's figured out

### Tools

* [binviz](https://binvis.io) is also useful for figuring out if files are compressed, and how (e.g. like how offsets/window size is used, which affects structure of the file).
* psximager for rebuilding images
* This [documentation on how PlayStation works](http://www.raphnet.net/electronique/psx_adaptor/Playstation.txt) which was a very useful reference throughout development of the patch.




## Field Events (FDEVENT.ACB)

See `fdevent_patch.py`. Each event (`EDT`) has a table of u16 offsets at `0x0C`: entry 0 is
`0x54` (start of the event script), entries 1-30 are where each message starts, and entry 31
is where the text block ends. Messages are stored back to back, each terminated by `0x00`.
Inside a message, `0x0A` starts a new line and `0x0C` a new text box.

Because the game looks messages up through this table, translations share one byte budget per
event instead of each line needing to fit its Japanese. Messages that don't fit go into room
added after the event's chunk: FDEVENT.ACB is split into sub-files (whole sectors, each starting
with `[u32 count, u32 chunk offset * count]`), so the patcher moves the later chunks down and
updates that table. The events in a sub-file share the `0x00` padding at its end (32 to 2,028
bytes).

Each box is translated whole (`en-ja/ja.fdevent.boxes.txt` / `en.fdevent.boxes.txt`, `\n` = new
line, `\f` = new box). Lines are word-wrapped at 32, 32 and 30 bytes (the button icon covers the
end of the last line; a 4th line is drawn over the 3rd), or 24, 24 and 22 in the Garage's
window (events 250-264). A full line wraps by itself and gets no `0x0A`; a line with `<name>`
(counted as 8) is kept one short of full, since how full it is depends on the name.

The game's text printer (`forward_one_font`, 80020bec in SLPS_014.68) drew a line break right
after an odd number of letters as a character, so text ran on. `replace_asm` for `slps` fixes it.

#### TODO's

* Confirm in game that messages moved after their event show.
* More room needs whole sectors added to a sub-file, which makes FDEVENT.ACB bigger: FIELD.ACB
  follows it on the disc with no gap, so the disc image would have to be laid out again.

## Menus and other strings

In SLPS_014.68 and the BIN overlays (not BATTLE.BIN), `strings_patch.py` lets a string be longer
than the Japanese: the game reaches each string through a pointer or a `lui`/`addiu` pair, so
strings whose every reference is found are repacked back to back and their references updated
(code references stay within the same 64 KB). A string stored more than once in a file is kept
once. Anything else still has to fit where the Japanese was.

Messages of more than one line (casino, field program) are translated whole, each as one
pairing (`\n` line break, `\f` new box, no `\n` after a full line). `replace_bytes.py` applies
longer Japanese first, so a whole message is replaced before the lines inside it. Window widths
(a window holds (width - 16) / 8 characters, and the last line is 2 shorter for the button icon,
except in YES/NO prompts):

* Event window, 32: field events, the stadium front desks, the casino's entrance and prize counter.
* Casino window, 26: Pockle Stone and Pockle Card.
* Garage window, 24: the butler, Psyche and the shop owner, Pockle Race.

The opening's 27 speeches (OPENDEMO.BIN) share one room: `dialogue_patch.py` packs them back to
back and repoints them, using the space after the end of the file up to its last sector too
(5,124 bytes in all), so a speech can be longer than its Japanese if the whole opening fits.
`dialogue.py` lays out `en_raw/` into `en/` (24 per line, no `0x0A` after a full line) and
checks the total.

## Building

`build.sh` runs every patch step and writes the result into a copy of the original `.bin` with
`build_rom.py`, which patches files in place and recomputes sector EDC/ECC (no psximager needed).
A patched file must still fit in the sectors the original uses.

## Graphics

Translated images are stored as indexed PNGs in `graphics/<game file>/<offset>.png` (e.g.
`graphics/FIELD/FIELD.ACB/01dec0.png`, the Garage menu) and imported by `graphics.py` during the
build. Pixel values are palette indices, so keep the PNG's palette when editing. 16bpp (direct
colour) images, like the monster status screen, are RGBA PNGs instead. Each image is
recompressed into its original slot and must compress to the same size or smaller. The build
needs Pillow (`pip3 install -r requirements.txt`).
