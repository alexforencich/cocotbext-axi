"""

Copyright (c) 2020 Alex Forencich

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

from .sparse_memory import SparseMemory
from .utils import hexdump, hexdump_lines, hexdump_str


class Memory:
    def __init__(self, size=2**64, mem=None, **kwargs):
        if mem is not None:
            self.mem = mem
        else:
            self.mem = SparseMemory(size)
        self.size = len(self.mem)
        super().__init__(**kwargs)

    def read(self, address, length):
        return self.mem[address:address+length]

    def write(self, address, data):
        self.mem[address:address+len(data)] = data

    def write_words(self, address, data, byteorder='little', ws=2):
        words = data
        data = bytearray()
        for w in words:
            data.extend(w.to_bytes(ws, byteorder))
        self.write(address, data)

    def write_dwords(self, address, data, byteorder='little'):
        self.write_words(address, data, byteorder, 4)

    def write_qwords(self, address, data, byteorder='little'):
        self.write_words(address, data, byteorder, 8)

    def write_byte(self, address, data):
        self.write(address, [data])

    def write_word(self, address, data, byteorder='little', ws=2):
        self.write_words(address, [data], byteorder, ws)

    def write_dword(self, address, data, byteorder='little'):
        self.write_dwords(address, [data], byteorder)

    def write_qword(self, address, data, byteorder='little'):
        self.write_qwords(address, [data], byteorder)

    def read_words(self, address, count, byteorder='little', ws=2):
        data = self.read(address, count*ws)
        words = []
        for k in range(count):
            words.append(int.from_bytes(data[ws*k:ws*(k+1)], byteorder))
        return words

    def read_dwords(self, address, count, byteorder='little'):
        return self.read_words(address, count, byteorder, 4)

    def read_qwords(self, address, count, byteorder='little'):
        return self.read_words(address, count, byteorder, 8)

    def read_byte(self, address):
        return self.read(address, 1)[0]

    def read_word(self, address, byteorder='little', ws=2):
        return self.read_words(address, 1, byteorder, ws)[0]

    def read_dword(self, address, byteorder='little'):
        return self.read_dwords(address, 1, byteorder)[0]

    def read_qword(self, address, byteorder='little'):
        return self.read_qwords(address, 1, byteorder)[0]

    def hexdump(self, address, length, prefix=""):
        hexdump(self.mem, address, length, prefix=prefix)

    def hexdump_lines(self, address, length, prefix=""):
        return hexdump_lines(self.mem, address, length, prefix=prefix)

    def hexdump_str(self, address, length, prefix=""):
        return hexdump_str(self.mem, address, length, prefix=prefix)
