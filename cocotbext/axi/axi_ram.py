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

import cocotb
from cocotb.triggers import Event
from cocotb.log import SimLog

import mmap
from collections import deque

from .constants import *
from .axi_channels import *
from .utils import hexdump, hexdump_str


class AxiRamWrite(object):
    def __init__(self, entity, name, clock, reset=None, size=1024, mem=None):
        self.log = SimLog("cocotb.%s.%s" % (entity._name, name))

        if type(mem) is mmap.mmap:
            self.mem = mem
        else:
            self.mem = mmap.mmap(-1, size)
        self.size = len(self.mem)

        self.reset = reset

        self.aw_channel = AxiAWSink(entity, name, clock, reset)
        self.w_channel = AxiWSink(entity, name, clock, reset)
        self.b_channel = AxiBSource(entity, name, clock, reset)

        self.in_flight_operations = 0

        self.width = len(self.w_channel.bus.wdata)
        self.byte_size = 8
        self.byte_width = self.width // self.byte_size
        self.strb_mask = 2**self.byte_width-1

        assert self.byte_width == len(self.w_channel.bus.wstrb)
        assert self.byte_width * self.byte_size == self.width

        assert len(self.b_channel.bus.bid) == len(self.aw_channel.bus.awid)

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

            awid = int(aw.awid)
            addr = int(aw.awaddr)
            length = int(aw.awlen)
            size = int(aw.awsize)
            burst = int(aw.awburst)
            prot = AxiProt(int(aw.awprot))

            self.log.info(f"Write burst awid: {awid:#x} awaddr: {addr:#010x} awlen: {length} awsize: {size} awprot: {prot}")

            num_bytes = 2**size
            assert 0 < num_bytes <= self.byte_width

            aligned_addr = (addr // num_bytes) * num_bytes
            length += 1

            transfer_size = num_bytes*length

            if burst == AxiBurstType.WRAP:
                lower_wrap_boundary = (addr // transfer_size) * transfer_size
                upper_wrap_boundary = lower_wrap_boundary + transfer_size

            if burst == AxiBurstType.INCR:
                # check 4k boundary crossing
                assert 0x1000-(aligned_addr&0xfff) >= transfer_size

            cur_addr = aligned_addr

            for n in range(length):
                cur_word_addr = (cur_addr // self.byte_width) * self.byte_width

                await self.w_channel.wait()
                w = self.w_channel.recv()

                data = int(w.wdata)
                strb = int(w.wstrb)
                last = int(w.wlast)

                # todo latency

                self.mem.seek(cur_word_addr % self.size)

                data = data.to_bytes(self.byte_width, 'little')

                self.log.info(f"Write word awid: {awid:#x} addr: {cur_addr:#010x} wstrb: {strb:#04x} data: {' '.join((f'{c:02x}' for c in data))}")

                for i in range(self.byte_width):
                    if strb & (1 << i):
                        self.mem.write(data[i:i+1])
                    else:
                        self.mem.seek(1, 1)

                assert last == (n == length-1)

                if burst != AxiBurstType.FIXED:
                    cur_addr += num_bytes

                    if burst == AxiBurstType.WRAP:
                        if cur_addr == upper_wrap_boundary:
                            cur_addr = lower_wrap_boundary

            b = self.b_channel._transaction_obj()
            b.bid = awid
            b.bresp = AxiResp.OKAY

            self.b_channel.send(b)


class AxiRamRead(object):
    def __init__(self, entity, name, clock, reset=None, size=1024, mem=None):
        self.log = SimLog("cocotb.%s.%s" % (entity._name, name))

        if type(mem) is mmap.mmap:
            self.mem = mem
        else:
            self.mem = mmap.mmap(-1, size)
        self.size = len(self.mem)

        self.reset = reset

        self.ar_channel = AxiARSink(entity, name, clock, reset)
        self.r_channel = AxiRSource(entity, name, clock, reset)

        self.int_read_resp_command_queue = deque()
        self.int_read_resp_command_sync = Event()

        self.in_flight_operations = 0

        self.width = len(self.r_channel.bus.rdata)
        self.byte_size = 8
        self.byte_width = self.width // self.byte_size

        assert self.byte_width * self.byte_size == self.width

        assert len(self.r_channel.bus.rid) == len(self.ar_channel.bus.arid)

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

            arid = int(ar.arid)
            addr = int(ar.araddr)
            length = int(ar.arlen)
            size = int(ar.arsize)
            burst = int(ar.arburst)
            prot = AxiProt(ar.arprot)

            self.log.info(f"Read burst arid: {arid:#x} araddr: {addr:#010x} arlen: {length} arsize: {size} arprot: {prot}")

            num_bytes = 2**size
            assert 0 < num_bytes <= self.byte_width

            aligned_addr = (addr // num_bytes) * num_bytes
            length += 1

            transfer_size = num_bytes*length

            if burst == AxiBurstType.WRAP:
                lower_wrap_boundary = (addr // transfer_size) * transfer_size
                upper_wrap_boundary = lower_wrap_boundary + transfer_size

            if burst == AxiBurstType.INCR:
                # check 4k boundary crossing
                assert 0x1000-(aligned_addr&0xfff) >= transfer_size

            cur_addr = aligned_addr

            for n in range(length):
                cur_word_addr = (cur_addr // self.byte_width) * self.byte_width

                self.mem.seek(cur_word_addr % self.size)

                data = self.mem.read(self.byte_width)

                r = self.r_channel._transaction_obj()
                r.rid = arid
                r.rdata = int.from_bytes(data, 'little')
                r.rlast = n == length-1
                r.rresp = AxiResp.OKAY

                self.r_channel.send(r)

                self.log.info(f"Read word arid: {arid:#x} addr: {cur_addr:#010x} data: {' '.join((f'{c:02x}' for c in data))}")

                if burst != AxiBurstType.FIXED:
                    cur_addr += num_bytes

                    if burst == AxiBurstType.WRAP:
                        if cur_addr == upper_wrap_boundary:
                            cur_addr = lower_wrap_boundary


class AxiRam(object):
    def __init__(self, entity, name, clock, reset=None, size=1024, mem=None):
        self.write_if = None
        self.read_if = None

        if type(mem) is mmap.mmap:
            self.mem = mem
        else:
            self.mem = mmap.mmap(-1, size)
        self.size = len(self.mem)

        self.write_if = AxiRamWrite(entity, name, clock, reset, mem=self.mem)
        self.read_if = AxiRamRead(entity, name, clock, reset, mem=self.mem)

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

