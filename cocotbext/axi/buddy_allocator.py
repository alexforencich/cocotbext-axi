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


class BuddyAllocator:
    def __init__(self, size, min_alloc=1):
        self.size = size
        self.min_alloc = min_alloc

        self.free_lists = [[] for x in range((self.size-1).bit_length())]
        self.free_lists.append([0])
        self.allocations = {}

    def alloc(self, size):
        if size < 1 or size > self.size:
            raise ValueError("size out of range")

        size = max(size, self.min_alloc)

        bucket = (size-1).bit_length()
        orig_bucket = bucket

        while bucket < len(self.free_lists):
            if not self.free_lists[bucket]:
                # find free block
                bucket += 1
                continue

            while bucket > orig_bucket:
                # split block
                block = self.free_lists[bucket].pop(0)
                bucket -= 1
                self.free_lists[bucket].append(block)
                self.free_lists[bucket].append(block+2**bucket)

            if self.free_lists[bucket]:
                # allocate
                block = self.free_lists[bucket].pop(0)
                self.allocations[block] = bucket
                return block

            break

        raise Exception("out of memory")

    def free(self, addr):
        if addr not in self.allocations:
            raise ValueError("unknown allocation")

        bucket = self.allocations.pop(addr)

        while bucket < len(self.free_lists):
            size = 2**bucket

            # find buddy
            if (addr // size) % 2:
                buddy = addr - size
            else:
                buddy = addr + size

            if buddy in self.free_lists[bucket]:
                # buddy is free, merge
                self.free_lists[bucket].remove(buddy)
                addr = min(addr, buddy)
                bucket += 1
            else:
                # buddy is not free, so add to free list
                self.free_lists[bucket].append(addr)
                return

        raise Exception("failed to free memory")
