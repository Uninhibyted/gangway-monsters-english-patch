MIN_REF_LEN = 2
MAX_REF_LEN = 0xf
HEADER_SIZE = 8
WINDOW_SIZE = 0xfff
MAX_WINDOW_SIZE = 0x1000
count = 0

def correct_offset(raw_offset, tail):
    return tail - ((tail - raw_offset) & WINDOW_SIZE)

def byte_header_size(total_size):
    chunk = bytearray()
    chunk.append((total_size & 0x000000ff))
    chunk.append((total_size & 0x0000ff00) >> 8)
    chunk.append((total_size & 0x00ff0000) >> 16)
    chunk.append((total_size & 0xff000000) >> 24)
    return chunk

MAX_MATCH = MAX_REF_LEN + MIN_REF_LEN
# The game's own compressed data never references further back than this, and never
# uses an offset field of 0 (a source position just before a 4096-byte boundary).
# Its decompressor breaks on either, so the compressor avoids them too.
MAX_DISTANCE = 4079

def find_data(data, i, positions):
    # Longest match starting at most MAX_DISTANCE bytes back. It may run past i, since the
    # decompressor copies byte by byte (that's how runs get encoded).
    best = None
    end = min(len(data), i + MAX_MATCH)
    for start in reversed(positions.get(bytes(data[i:i+MIN_REF_LEN]), ())):
        if start < i - MAX_DISTANCE: break
        if (start + 1) & WINDOW_SIZE == 0: continue
        length = MIN_REF_LEN
        while i + length < end and data[start + length] == data[i + length]:
            length += 1
        if best is None or length > best[1]:
            best = (start, length)
            if i + length == end: break
    return best

def decompress(data, remove_header=True):
    size = None
    if remove_header:
        # MONBOOK.TIM has 1A 2B 01 00 30 AB 03 00 (compressed size, decompressed size)
        size = int.from_bytes(data[4:8], 'little')
        data = data[HEADER_SIZE:]

    result = bytearray()
    idx = 0

    while idx < len(data)-7 or (size is not None and idx < len(data) and len(result) < size):
        flags = data[idx]
        idx += 1

        for t in range(8):
            if size is not None and len(result) >= size: break
            flag = flags & 1
            flags = flags >> 1

            if flag > 0:
                result.append(data[idx])
                idx += 1

            else:
                byte1, byte2 = data[idx:idx+2]
                idx += 2

                offset = (((byte1 << 8) | byte2) >> 4) & WINDOW_SIZE
                length = ((byte1 << 8) | byte2) & 0xf
                offset = correct_offset(offset, len(result))

                if length == 0:
                    result.append(result[offset-1])
                    result.append(result[offset])

                else:
                    for k in range(length+2):
                        result.append(result[offset-1+k])
    return result

def compress(data):
    total_size = byte_header_size(len(data))
    result = bytearray()
    idx = 0
    max_len = len(data)
    positions = {}
    indexed = 0
    while idx < max_len:
        flag = 0
        chunk = bytearray()

        for bit in range(8):
            while indexed < idx:
                positions.setdefault(bytes(data[indexed:indexed+MIN_REF_LEN]), []).append(indexed)
                indexed += 1

            match = find_data(data, idx, positions)
            if match and match[1] < MAX_MATCH:
                # Lazy matching: if a longer match starts at the next byte, emit this
                # byte as a literal and take that one instead
                while indexed <= idx:
                    positions.setdefault(bytes(data[indexed:indexed+MIN_REF_LEN]), []).append(indexed)
                    indexed += 1
                following = find_data(data, idx + 1, positions)
                if following and following[1] > match[1] + 1:
                    match = None
            if match:
                offset, length = match
                l = (length-2)
                o = (offset + 1) & WINDOW_SIZE

                chunk.append(((o & 0xff0) >> 4))
                chunk.append(((o & 0xf) << 4) | ((l & 0xf)))
                idx += length
            else:
                if idx < max_len:
                    flag |= (1 << bit)
                    chunk.append(data[idx])
                    idx += 1
                else:
                    break

        result.append(flag)
        result += chunk
        chunk = bytearray()

    total_size_result = byte_header_size(len(result))

    return (total_size_result + total_size + result)

if __name__ == "__main__":
    compressit = False

    if not compressit:
        with open("MONBOOK.TIM", "rb") as f: d = f.read()
        data = d[HEADER_SIZE:]
        res = decompress(bytearray(data))
        print(f"Decompressed {len(res)} bytes")
        with open("MONBOOK.TIM.OUT", "wb") as f: f.write(res)
    else:
        with open("MONBOOK.TRANSLATED.TIM", "rb") as f: d = f.read()

        #total_size = byte_header_size(len(d))
        res = compress(d)
        print(f"Compressed {len(res)} bytes")
        #total_size_res = byte_header_size(len(res))
        #res = total_size_res + total_size + res

        with open("MONBOOK.MINE.TIM", "wb") as f: f.write(res)




