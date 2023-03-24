"""

Copyright (c) 2023 Alex Forencich

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

"""

from .utils import hexdump, hexdump_lines, hexdump_str


class SparseMemory:
    def __init__(self, size):
        self.size = size
        self.segs = {}

    def read(self, address, length, **kwargs):
        if address < 0 or address >= self.size:
            raise ValueError("address out of range")
        if length < 0:
            raise ValueError("invalid length")
        if address+length > self.size:
            raise ValueError("operation out of range")
        data = bytearray()
        while length > 0:
            block_offset = address & 0xfff
            block_addr = address - block_offset
            block_len = min(4096 - block_offset, length)
            try:
                block = self.segs[block_addr]
            except KeyError:
                block = b'\x00'*4096
            data.extend(block[block_offset:block_offset+block_len])
            address += block_len
            length -= block_len
        return bytes(data)

    def write(self, address, data, **kwargs):
        if address < 0 or address >= self.size:
            raise ValueError("address out of range")
        if address+len(data) > self.size:
            raise ValueError("operation out of range")
        offset = 0
        length = len(data)
        while length > 0:
            block_offset = address & 0xfff
            block_addr = address - block_offset
            block_len = min(4096 - block_offset, length)
            try:
                block = self.segs[block_addr]
            except KeyError:
                block = bytearray(4096)
                self.segs[block_addr] = block
            block[block_offset:block_offset+block_len] = data[offset:offset+block_len]
            address += block_len
            offset += block_len
            length -= block_len

    def clear(self):
        self.segs.clear()

    def hexdump(self, address, length, prefix=""):
        hexdump(self.read(address, length), prefix=prefix, offset=address)

    def hexdump_lines(self, address, length, prefix=""):
        return hexdump_lines(self.read(address, length), prefix=prefix, offset=address)

    def hexdump_str(self, address, length, prefix=""):
        return hexdump_str(self.read(address, length), prefix=prefix, offset=address)

    def __len__(self):
        return self.size

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.read(key, 1)[0]
        elif isinstance(key, slice):
            start, stop, step = key.indices(self.size)
            if step == 1:
                return self.read(start, stop-start)
            else:
                raise IndexError("specified step size is not supported")

    def __setitem__(self, key, value):
        if isinstance(key, int):
            self.write(key, [value])
        elif isinstance(key, slice):
            start, stop, step = key.indices(self.size)
            if step == 1:
                value = bytes(value)
                if stop-start != len(value):
                    raise IndexError("slice assignment is wrong size")
                return self.write(start, value)
            else:
                raise IndexError("specified step size is not supported")
