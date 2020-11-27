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

import mmap

import cocotb
from cocotb.log import SimLog

from .version import __version__
from .constants import AxiProt, AxiResp
from .axil_channels import AxiLiteAWSink, AxiLiteWSink, AxiLiteBSource, AxiLiteARSink, AxiLiteRSource
from .utils import hexdump, hexdump_str


class AxiLiteRamWrite(object):
    def __init__(self, entity, name, clock, reset=None, size=1024, mem=None):
        self.log = SimLog("cocotb.%s.%s" % (entity._name, name))

        self.log.info("AXI lite RAM model")
        self.log.info("cocotbext-axi version %s", __version__)
        self.log.info("Copyright (c) 2020 Alex Forencich")
        self.log.info("https://github.com/alexforencich/cocotbext-axi")

        if type(mem) is mmap.mmap:
            self.mem = mem
        else:
            self.mem = mmap.mmap(-1, size)
        self.size = len(self.mem)

        self.reset = reset

        self.aw_channel = AxiLiteAWSink(entity, name, clock, reset)
        self.w_channel = AxiLiteWSink(entity, name, clock, reset)
        self.b_channel = AxiLiteBSource(entity, name, clock, reset)

        self.in_flight_operations = 0

        self.width = len(self.w_channel.bus.wdata)
        self.byte_size = 8
        self.byte_width = self.width // self.byte_size
        self.strb_mask = 2**self.byte_width-1

        assert self.byte_width == len(self.w_channel.bus.wstrb)
        assert self.byte_width * self.byte_size == self.width

        cocotb.fork(self._process_write())

    def read_mem(self, address, length):
        self.mem.seek(address)
        return self.mem.read(length)

    def write_mem(self, address, data):
        self.mem.seek(address)
        self.mem.write(bytes(data))

    def hexdump(self, address, length, prefix=""):
        hexdump(self.mem, address, length, prefix=prefix)

    def hexdump_str(self, address, length, prefix=""):
        return hexdump_str(self.mem, address, length, prefix=prefix)

    async def _process_write(self):
        while True:
            await self.aw_channel.wait()
            aw = self.aw_channel.recv()

            addr = (int(aw.awaddr) // self.byte_width) * self.byte_width
            prot = AxiProt(aw.awprot)

            await self.w_channel.wait()
            w = self.w_channel.recv()

            data = int(w.wdata)
            strb = int(w.wstrb)

            # todo latency

            self.mem.seek(addr % self.size)

            data = data.to_bytes(self.byte_width, 'little')

            self.log.info("Write data awaddr: 0x%08x awprot: %s wstrb: 0x%02x data: %s",
                addr, prot, strb, ' '.join((f'{c:02x}' for c in data)))

            for i in range(self.byte_width):
                if strb & (1 << i):
                    self.mem.write(data[i:i+1])
                else:
                    self.mem.seek(1, 1)

            b = self.b_channel._transaction_obj()
            b.bresp = AxiResp.OKAY

            self.b_channel.send(b)


class AxiLiteRamRead(object):
    def __init__(self, entity, name, clock, reset=None, size=1024, mem=None):
        self.log = SimLog("cocotb.%s.%s" % (entity._name, name))

        self.reset = reset

        self.ar_channel = AxiLiteARSink(entity, name, clock, reset)
        self.r_channel = AxiLiteRSource(entity, name, clock, reset)

        if type(mem) is mmap.mmap:
            self.mem = mem
        else:
            self.mem = mmap.mmap(-1, size)
        self.size = len(self.mem)

        self.in_flight_operations = 0

        self.width = len(self.r_channel.bus.rdata)
        self.byte_size = 8
        self.byte_width = self.width // self.byte_size

        assert self.byte_width * self.byte_size == self.width

        cocotb.fork(self._process_read())

    def read_mem(self, address, length):
        self.mem.seek(address)
        return self.mem.read(length)

    def write_mem(self, address, data):
        self.mem.seek(address)
        self.mem.write(bytes(data))

    def hexdump(self, address, length, prefix=""):
        hexdump(self.mem, address, length, prefix=prefix)

    def hexdump_str(self, address, length, prefix=""):
        return hexdump_str(self.mem, address, length, prefix=prefix)

    async def _process_read(self):
        while True:
            await self.ar_channel.wait()
            ar = self.ar_channel.recv()

            addr = (int(ar.araddr) // self.byte_width) * self.byte_width
            prot = AxiProt(ar.arprot)

            # todo latency

            self.mem.seek(addr % self.size)

            data = self.mem.read(self.byte_width)

            r = self.r_channel._transaction_obj()
            r.rdata = int.from_bytes(data, 'little')
            r.rresp = AxiResp.OKAY

            self.r_channel.send(r)

            self.log.info("Read data araddr: 0x%08x arprot: %s data: %s",
                addr, prot, ' '.join((f'{c:02x}' for c in data)))


class AxiLiteRam(object):
    def __init__(self, entity, name, clock, reset=None, size=1024, mem=None):
        self.write_if = None
        self.read_if = None

        if type(mem) is mmap.mmap:
            self.mem = mem
        else:
            self.mem = mmap.mmap(-1, size)
        self.size = len(self.mem)

        self.write_if = AxiLiteRamWrite(entity, name, clock, reset, mem=self.mem)
        self.read_if = AxiLiteRamRead(entity, name, clock, reset, mem=self.mem)

    def read_mem(self, address, length):
        self.mem.seek(address)
        return self.mem.read(length)

    def write_mem(self, address, data):
        self.mem.seek(address)
        self.mem.write(bytes(data))

    def hexdump(self, address, length, prefix=""):
        hexdump(self.mem, address, length, prefix=prefix)

    def hexdump_str(self, address, length, prefix=""):
        return hexdump_str(self.mem, address, length, prefix=prefix)
