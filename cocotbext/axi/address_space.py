"""

Copyright (c) 2021 Alex Forencich

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

import mmap

from .buddy_allocator import BuddyAllocator
from .sparse_memory import SparseMemory
from .utils import hexdump, hexdump_lines, hexdump_str


class MemoryInterface:
    def __init__(self, size, base=0, parent=None, **kwargs):
        self._parent = parent
        self._size = size
        self._base = base
        self.window_type = Window
        self.window_pool_type = WindowPool
        super().__init__(**kwargs)

    @property
    def parent(self):
        return self._parent

    @property
    def size(self):
        return self._size

    @property
    def base(self):
        return self._base

    def check_range(self, address, length=0):
        if address < 0 or address >= self.size:
            raise ValueError("address out of range")
        if length < 0:
            raise ValueError("invalid length")
        if address+length > self.size:
            raise ValueError("operation out of range")

    def get_absolute_address(self, address):
        if self.base is None:
            return None
        self.check_range(address)
        return address+self.base

    async def _read(self, address, length, **kwargs):
        raise NotImplementedError()

    async def read(self, address, length, **kwargs):
        self.check_range(address, length)
        return await self._read(address, length, **kwargs)

    async def read_words(self, address, count, byteorder='little', ws=2, **kwargs):
        data = bytes(await self.read(address, count*ws, **kwargs))
        words = []
        for k in range(count):
            words.append(int.from_bytes(data[ws*k:ws*(k+1)], byteorder))
        return words

    async def read_dwords(self, address, count, byteorder='little', **kwargs):
        return await self.read_words(address, count, byteorder, 4, **kwargs)

    async def read_qwords(self, address, count, byteorder='little', **kwargs):
        return await self.read_words(address, count, byteorder, 8, **kwargs)

    async def read_byte(self, address, **kwargs):
        return (await self.read(address, 1, **kwargs)).data[0]

    async def read_word(self, address, byteorder='little', ws=2, **kwargs):
        return (await self.read_words(address, 1, byteorder, ws, **kwargs))[0]

    async def read_dword(self, address, byteorder='little', **kwargs):
        return (await self.read_dwords(address, 1, byteorder, **kwargs))[0]

    async def read_qword(self, address, byteorder='little', **kwargs):
        return (await self.read_qwords(address, 1, byteorder, **kwargs))[0]

    async def _write(self, address, data, **kwargs):
        raise NotImplementedError()

    async def write(self, address, data, **kwargs):
        self.check_range(address, len(data))
        await self._write(address, data, **kwargs)

    async def write_words(self, address, data, byteorder='little', ws=2, **kwargs):
        words = data
        data = bytearray()
        for w in words:
            data.extend(w.to_bytes(ws, byteorder))
        await self.write(address, data, **kwargs)

    async def write_dwords(self, address, data, byteorder='little', **kwargs):
        await self.write_words(address, data, byteorder, 4, **kwargs)

    async def write_qwords(self, address, data, byteorder='little', **kwargs):
        await self.write_words(address, data, byteorder, 8, **kwargs)

    async def write_byte(self, address, data, **kwargs):
        await self.write(address, [data], **kwargs)

    async def write_word(self, address, data, byteorder='little', ws=2, **kwargs):
        await self.write_words(address, [data], byteorder, ws, **kwargs)

    async def write_dword(self, address, data, byteorder='little', **kwargs):
        await self.write_dwords(address, [data], byteorder, **kwargs)

    async def write_qword(self, address, data, byteorder='little', **kwargs):
        await self.write_qwords(address, [data], byteorder, **kwargs)

    def create_window(self, offset, size=None, window_type=None):
        if not size or size < 0:
            size = self.size - offset
        window_type = window_type or self.window_type or Window
        self.check_range(offset, size)
        return window_type(self, offset, size, base=self.get_absolute_address(offset))

    def create_window_pool(self, offset=None, size=None, window_pool_type=None, window_type=None):
        if offset is None:
            offset = 0
        if size is None:
            size = self.size - offset
        window_pool_type = window_pool_type or self.window_pool_type or WindowPool
        window_type = window_type or self.window_type
        self.check_range(offset, size)
        return window_pool_type(self, offset, size, base=self.get_absolute_address(offset), window_type=window_type)

    def __len__(self):
        return self._size


class Window(MemoryInterface):
    def __init__(self, parent, offset, size, base=0, **kwargs):
        super().__init__(size, base=base, parent=parent, **kwargs)
        self._offset = offset

    @property
    def offset(self):
        return self._offset

    def get_parent_address(self, address):
        if address < 0 or address >= self.size:
            raise ValueError("address out of range")
        return address+self.offset

    async def _read(self, address, length, **kwargs):
        return await self.parent.read(self.get_parent_address(address), length, **kwargs)

    async def _write(self, address, data, **kwargs):
        await self.parent.write(self.get_parent_address(address), data, **kwargs)


class WindowPool(Window):
    def __init__(self, parent, offset, size, base=None, window_type=None, **kwargs):
        super().__init__(parent, offset, size, base=base, **kwargs)
        self.window_type = window_type or Window
        self.allocator = BuddyAllocator(size)

    def alloc_window(self, size, window_type=None):
        return self.create_window(self.allocator.alloc(size), size, window_type)


class Region(MemoryInterface):
    def __init__(self, size, **kwargs):
        super().__init__(size, **kwargs)


class MemoryRegion(Region):
    def __init__(self, size=4096, mem=None, **kwargs):
        super().__init__(size, **kwargs)
        if mem is None:
            mem = mmap.mmap(-1, size)
        self.mem = mem

    async def _read(self, address, length, **kwargs):
        return self.mem[address:address+length]

    async def _write(self, address, data, **kwargs):
        self.mem[address:address+len(data)] = data

    def hexdump(self, address, length, prefix=""):
        hexdump(self.mem[address:address+length], prefix=prefix, offset=address)

    def hexdump_lines(self, address, length, prefix=""):
        return hexdump_lines(self.mem[address:address+length], prefix=prefix, offset=address)

    def hexdump_str(self, address, length, prefix=""):
        return hexdump_str(self.mem[address:address+length], prefix=prefix, offset=address)

    def __getitem__(self, key):
        return self.mem[key]

    def __setitem__(self, key, value):
        self.mem[key] = value

    def __bytes__(self):
        return bytes(self.mem)


class SparseMemoryRegion(Region):
    def __init__(self, size=2**64, mem=None, **kwargs):
        super().__init__(size, **kwargs)
        if mem is None:
            mem = SparseMemory(size)
        self.mem = mem

    async def _read(self, address, length, **kwargs):
        return self.mem.read(address, length)

    async def _write(self, address, data, **kwargs):
        self.mem.write(address, data)

    def hexdump(self, address, length, prefix=""):
        self.mem.hexdump(address, length, prefix=prefix)

    def hexdump_lines(self, address, length, prefix=""):
        return self.mem.hexdump_lines(address, length, prefix=prefix)

    def hexdump_str(self, address, length, prefix=""):
        return self.mem.hexdump_str(address, length, prefix=prefix)

    def __getitem__(self, key):
        return self.mem[key]

    def __setitem__(self, key, value):
        self.mem[key] = value


class PeripheralRegion(Region):
    def __init__(self, obj, size, **kwargs):
        super().__init__(size, **kwargs)
        self.obj = obj

    async def _read(self, address, length, **kwargs):
        try:
            return await self.obj.read(address, length, **kwargs)
        except TypeError:
            return self.obj.read(address, length, **kwargs)

    async def _write(self, address, data, **kwargs):
        try:
            await self.obj.write(address, data, **kwargs)
        except TypeError:
            self.obj.write(address, data, **kwargs)


class AddressSpace(Region):
    def __init__(self, size=2**64, base=0, parent=None, **kwargs):
        super().__init__(size=size, base=base, parent=parent, **kwargs)
        self.pool_type = Pool
        self.regions = []

    def find_regions(self, address, length=1):
        regions = []
        if address < 0 or address >= self.size:
            raise ValueError("address out of range")
        if length < 0:
            raise ValueError("invalid length")
        length = max(length, 1)
        for (base, size, translate, region) in self.regions:
            if address < base+size and base < address+length:
                regions.append((base, size, translate, region))
        regions.sort()
        return regions

    def register_region(self, region, base, size=None, offset=0):
        if size is None:
            size = region.size
        if self.find_regions(base, size):
            raise ValueError("overlaps existing region")
        region._parent = self
        if offset == 0:
            region._base = self.get_absolute_address(base)
        else:
            region._base = None
        self.regions.append((base, size, offset, region))

    async def read(self, address, length, **kwargs):
        regions = self.find_regions(address, length)
        data = bytearray()
        if not regions:
            raise Exception("Invalid address")
        for base, size, offset, region in regions:
            if base > address:
                raise Exception("Invalid address")
            seg_addr = address - base
            seg_len = min(size-seg_addr, length)
            if offset is None:
                seg_addr = address
                offset = 0
            data.extend(bytes(await region.read(seg_addr+offset, seg_len, **kwargs)))
            address += seg_len
            length -= seg_len
        if length > 0:
            raise Exception("Invalid address")
        return bytes(data)

    async def write(self, address, data, **kwargs):
        start = 0
        length = len(data)
        regions = self.find_regions(address, length)
        if not regions:
            raise Exception("Invalid address")
        for base, size, offset, region in regions:
            if base > address:
                raise Exception("Invalid address")
            seg_addr = address - base
            seg_len = min(size-seg_addr, length)
            if offset is None:
                seg_addr = address
                offset = 0
            await region.write(seg_addr+offset, data[start:start+seg_len], **kwargs)
            address += seg_len
            start += seg_len
            length -= seg_len
        if length > 0:
            raise Exception("Invalid address")

    def create_pool(self, base=None, size=None, pool_type=None, region_type=None):
        if base is None:
            base = 0
        if size is None:
            size = self.size - base
        pool_type = pool_type or self.pool_type or Pool
        self.check_range(base, size)
        pool = pool_type(self, base, size, region_type=region_type)
        self.register_region(pool, base, size)
        return pool


class Pool(AddressSpace):
    def __init__(self, parent, base, size, region_type=None, **kwargs):
        super().__init__(parent=parent, base=base, size=size, **kwargs)
        self.region_type = region_type or MemoryRegion
        self.allocator = BuddyAllocator(size)

    def alloc_region(self, size, region_type=None):
        region_type = region_type or self.region_type or MemoryRegion
        base = self.allocator.alloc(size)
        region = region_type(size)
        self.register_region(region, base)
        return region
