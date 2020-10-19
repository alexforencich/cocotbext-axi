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
from cocotb.triggers import RisingEdge, ReadOnly, Event
from cocotb.drivers import BusDriver

import mmap
import queue
from collections import deque

from .constants import *


class AxiLiteRamWrite(BusDriver):

    _signals = [
        # Write address channel
        "awaddr", "awprot", "awvalid", "awready",
        # Write data channel
        "wdata", "wstrb", "wvalid", "wready",
        # Write response channel
        "bresp", "bvalid", "bready",
    ]

    def __init__(self, entity, name, clock, reset=None, size=1024, mem=None):
        super().__init__(entity, name, clock)

        if type(mem) is mmap.mmap:
            self.mem = mem
        else:
            self.mem = mmap.mmap(-1, size)
        self.size = len(self.mem)

        self.int_write_addr_queue = deque()
        self.int_write_addr_sync = Event()
        self.int_write_data_queue = deque()
        self.int_write_data_sync = Event()
        self.int_write_resp_queue = deque()
        self.int_write_resp_sync = Event()

        self.in_flight_operations = 0

        self.width = len(self.bus.wdata)
        self.byte_size = 8
        self.byte_width = self.width // self.byte_size
        self.strb_mask = 2**len(self.bus.wstrb)-1

        assert self.byte_width == len(self.bus.wstrb)
        assert self.byte_width * self.byte_size == self.width

        self.reset = reset

        assert len(self.bus.awprot) == 3
        assert len(self.bus.awvalid) == 1
        assert len(self.bus.awready) == 1
        self.bus.awready.setimmediatevalue(0)

        assert len(self.bus.wvalid) == 1
        assert len(self.bus.wready) == 1
        self.bus.wready.setimmediatevalue(0)

        assert len(self.bus.bresp) == 2
        self.bus.bresp.setimmediatevalue(0)
        assert len(self.bus.bvalid) == 1
        self.bus.bvalid.setimmediatevalue(0)
        assert len(self.bus.bready) == 1

        cocotb.fork(self._process_write())
        cocotb.fork(self._process_write_addr_if())
        cocotb.fork(self._process_write_data_if())
        cocotb.fork(self._process_write_resp_if())

    def read_mem(self, address, length):
        self.mem.seek(address)
        return self.mem.read(length)

    def write_mem(self, address, data):
        self.mem.seek(address)
        self.mem.write(bytes(data))

    async def _process_write(self):
        while True:
            if not self.int_write_addr_queue:
                self.int_write_addr_sync.clear()
                await self.int_write_addr_sync.wait()

            addr, prot = self.int_write_addr_queue.popleft()
            addr = (addr // self.byte_width) * self.byte_width
            prot = AxiProt(prot)

            if not self.int_write_data_queue:
                self.int_write_data_sync.clear()
                await self.int_write_data_sync.wait()

            data, strb = self.int_write_data_queue.popleft()

            # todo latency

            self.mem.seek(addr % self.size)

            data = data.to_bytes(self.byte_width, 'little')

            self.log.info(f"Write data addr: {addr:#010x} prot: {prot} wstrb: {strb:#04x} data: {' '.join((f'{c:02x}' for c in data))}")

            for i in range(self.byte_width):
                if strb & (1 << i):
                    self.mem.write(data[i:i+1])
                else:
                    self.mem.seek(1, 1)

            self.int_write_resp_queue.append(AxiResp.OKAY)
            self.int_write_resp_sync.set()

    async def _process_write_addr_if(self):
        while True:
            await ReadOnly()

            # read handshake signals
            awready_sample = self.bus.awready.value
            awvalid_sample = self.bus.awvalid.value

            if self.reset is not None and self.reset.value:
                await RisingEdge(self.clock)
                self.bus.awready <= 0
                continue

            if awready_sample and awvalid_sample:
                awaddr = self.bus.awaddr.value.integer
                awprot = self.bus.awprot.value.integer
                self.int_write_addr_queue.append((awaddr, awprot))
                self.int_write_addr_sync.set()

            await RisingEdge(self.clock)
            self.bus.awready <= 1

    async def _process_write_data_if(self):
        while True:
            await ReadOnly()

            # read handshake signals
            wready_sample = self.bus.wready.value
            wvalid_sample = self.bus.wvalid.value

            if self.reset is not None and self.reset.value:
                await RisingEdge(self.clock)
                self.bus.wready <= 0
                continue

            if wready_sample and wvalid_sample:
                wdata = self.bus.wdata.value.integer
                wstrb = self.bus.wstrb.value.integer
                self.int_write_data_queue.append((wdata, wstrb))
                self.int_write_data_sync.set()

            await RisingEdge(self.clock)
            self.bus.wready <= 1

    async def _process_write_resp_if(self):
        while True:
            await ReadOnly()

            # read handshake signals
            bready_sample = self.bus.bready.value
            bvalid_sample = self.bus.bvalid.value

            if self.reset is not None and self.reset.value:
                await RisingEdge(self.clock)
                self.bus.bvalid <= 0
                continue

            await RisingEdge(self.clock)

            if (bready_sample and bvalid_sample) or (not bvalid_sample):
                if self.int_write_resp_queue:
                    bresp = self.int_write_resp_queue.popleft()
                    self.bus.bresp <= bresp
                    self.bus.bvalid <= 1
                else:
                    self.bus.bvalid <= 0


class AxiLiteRamRead(BusDriver):

    _signals = [
        # Read address channel
        "araddr", "arprot", "arvalid", "arready",
        # Read data channel
        "rdata", "rresp", "rvalid", "rready",
    ]

    def __init__(self, entity, name, clock, reset=None, size=1024, mem=None):
        super().__init__(entity, name, clock)

        if type(mem) is mmap.mmap:
            self.mem = mem
        else:
            self.mem = mmap.mmap(-1, size)
        self.size = len(self.mem)

        self.int_read_addr_queue = deque()
        self.int_read_addr_sync = Event()
        self.int_read_resp_command_queue = deque()
        self.int_read_resp_command_sync = Event()
        self.int_read_resp_queue = deque()
        self.int_read_resp_sync = Event()

        self.in_flight_operations = 0

        self.width = len(self.bus.rdata)
        self.byte_size = 8
        self.byte_width = self.width // self.byte_size

        assert self.byte_width * self.byte_size == self.width

        self.reset = reset

        assert len(self.bus.arprot) == 3
        assert len(self.bus.arvalid) == 1
        assert len(self.bus.arready) == 1
        self.bus.arready.setimmediatevalue(0)

        self.bus.rdata.setimmediatevalue(0)
        assert len(self.bus.rresp) == 2
        self.bus.rresp.setimmediatevalue(0)
        assert len(self.bus.rvalid) == 1
        self.bus.rvalid.setimmediatevalue(0)
        assert len(self.bus.rready) == 1

        cocotb.fork(self._process_read())
        cocotb.fork(self._process_read_addr_if())
        cocotb.fork(self._process_read_resp_if())

    def read_mem(self, address, length):
        self.mem.seek(address)
        return self.mem.read(length)

    def write_mem(self, address, data):
        self.mem.seek(address)
        self.mem.write(bytes(data))

    async def _process_read(self):
        while True:
            if not self.int_read_addr_queue:
                self.int_read_addr_sync.clear()
                await self.int_read_addr_sync.wait()

            addr, prot = self.int_read_addr_queue.popleft()
            addr = (addr // self.byte_width) * self.byte_width
            prot = AxiProt(prot)

            # todo latency

            self.mem.seek(addr % self.size)

            data = self.mem.read(self.byte_width)

            self.int_read_resp_queue.append((int.from_bytes(data, 'little'), AxiResp.OKAY))
            self.int_read_resp_sync.set()

            self.log.info(f"Read data addr: {addr:#010x} prot: {prot} data: {' '.join((f'{c:02x}' for c in data))}")

    async def _process_read_addr_if(self):
        while True:
            await ReadOnly()

            # read handshake signals
            arready_sample = self.bus.arready.value
            arvalid_sample = self.bus.arvalid.value

            if self.reset is not None and self.reset.value:
                await RisingEdge(self.clock)
                self.bus.arready <= 0
                continue

            if arready_sample and arvalid_sample:
                araddr = self.bus.araddr.value.integer
                arprot = self.bus.arprot.value.integer
                self.int_read_addr_queue.append((araddr, arprot))
                self.int_read_addr_sync.set()

            await RisingEdge(self.clock)
            self.bus.arready <= 1

    async def _process_read_resp_if(self):
        while True:
            await ReadOnly()

            # read handshake signals
            rready_sample = self.bus.rready.value
            rvalid_sample = self.bus.rvalid.value

            if self.reset is not None and self.reset.value:
                await RisingEdge(self.clock)
                self.bus.rvalid <= 0
                continue

            await RisingEdge(self.clock)

            if (rready_sample and rvalid_sample) or (not rvalid_sample):
                if self.int_read_resp_queue:
                    rdata, rresp = self.int_read_resp_queue.popleft()
                    self.bus.rdata <= rdata
                    self.bus.rresp <= rresp
                    self.bus.rvalid <= 1
                else:
                    self.bus.rvalid <= 0


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

