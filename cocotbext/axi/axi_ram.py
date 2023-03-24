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

from .axi_slave import AxiSlaveWrite, AxiSlaveRead
from .memory import Memory


class AxiRamWrite(AxiSlaveWrite, Memory):
    def __init__(self, bus, clock, reset=None, reset_active_level=True, size=2**64, mem=None, **kwargs):
        super().__init__(bus, clock, reset, reset_active_level=reset_active_level, size=size, mem=mem, **kwargs)

    async def _write(self, address, data):
        self.write(address % self.size, data)


class AxiRamRead(AxiSlaveRead, Memory):
    def __init__(self, bus, clock, reset=None, reset_active_level=True, size=2**64, mem=None, **kwargs):
        super().__init__(bus, clock, reset, reset_active_level=reset_active_level, size=size, mem=mem, **kwargs)

    async def _read(self, address, length):
        return self.read(address % self.size, length)


class AxiRam(Memory):
    def __init__(self, bus, clock, reset=None, reset_active_level=True, size=2**64, mem=None, **kwargs):
        self.write_if = None
        self.read_if = None

        super().__init__(size, mem, **kwargs)

        self.write_if = AxiRamWrite(bus.write, clock, reset, reset_active_level, mem=self.mem)
        self.read_if = AxiRamRead(bus.read, clock, reset, reset_active_level, mem=self.mem)
