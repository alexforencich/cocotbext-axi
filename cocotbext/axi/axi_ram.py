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
from collections import deque

from .constants import *


class AxiRamWrite(BusDriver):

    _signals = [
        # Write address channel
        "awid", "awaddr", "awlen", "awsize", "awburst", "awprot", "awvalid", "awready",
        # Write data channel
        "wdata", "wstrb", "wlast", "wvalid", "wready",
        # Write response channel
        "bid", "bresp", "bvalid", "bready",
    ]

    _optional_signals = [
        # Write address channel
        "awlock", "awcache", "awqos", "awregion", "awuser",
        # Write data channel
        "wuser",
        # Write response channel
        "buser",
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

        assert len(self.bus.awlen) == 8
        assert len(self.bus.awsize) == 3
        assert len(self.bus.awburst) == 2
        if hasattr(self.bus, "awlock"):
            assert len(self.bus.awlock) == 1
        if hasattr(self.bus, "awcache"):
            assert len(self.bus.awcache) == 4
        assert len(self.bus.awprot) == 3
        if hasattr(self.bus, "awqos"):
            assert len(self.bus.awqos) == 4
        if hasattr(self.bus, "awregion"):
            assert len(self.bus.awregion) == 4
        assert len(self.bus.awvalid) == 1
        assert len(self.bus.awready) == 1
        self.bus.awready.setimmediatevalue(0)

        assert len(self.bus.wlast) == 1
        assert len(self.bus.wvalid) == 1
        assert len(self.bus.wready) == 1
        self.bus.wready.setimmediatevalue(0)

        assert len(self.bus.bid) == len(self.bus.awid)
        self.bus.bid.setimmediatevalue(0)
        assert len(self.bus.bresp) == 2
        self.bus.bresp.setimmediatevalue(0)
        assert len(self.bus.bvalid) == 1
        if hasattr(self.bus, "buser"):
            self.bus.buser.setimmediatevalue(0)
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

            awid, addr, length, size, burst, prot = self.int_write_addr_queue.popleft()
            prot = AxiProt(prot)

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

                if not self.int_write_data_queue:
                    self.int_write_data_sync.clear()
                    await self.int_write_data_sync.wait()

                data, strb, last = self.int_write_data_queue.popleft()

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

            self.int_write_resp_queue.append((awid, AxiResp.OKAY))
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
                awid = self.bus.awid.value.integer
                awaddr = self.bus.awaddr.value.integer
                awlen = self.bus.awlen.value.integer
                awsize = self.bus.awsize.value.integer
                awburst = self.bus.awburst.value.integer
                awprot = self.bus.awprot.value.integer
                self.int_write_addr_queue.append((awid, awaddr, awlen, awsize, awburst, awprot))
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
                wlast = self.bus.wlast.value.integer
                self.int_write_data_queue.append((wdata, wstrb, wlast))
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
                    bid, bresp = self.int_write_resp_queue.popleft()
                    self.bus.bid <= bid
                    self.bus.bresp <= bresp
                    self.bus.bvalid <= 1
                else:
                    self.bus.bvalid <= 0


class AxiRamRead(BusDriver):

    _signals = [
        # Read address channel
        "arid", "araddr", "arlen", "arsize", "arburst", "arprot", "arvalid", "arready",
        # Read data channel
        "rid", "rdata", "rresp", "rlast", "rvalid", "rready",
    ]

    _optional_signals = [
        # Read address channel
        "arlock", "arcache", "arqos", "arregion",  "aruser",
        # Read data channel
        "ruser",
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

        assert len(self.bus.arlen) == 8
        assert len(self.bus.arsize) == 3
        assert len(self.bus.arburst) == 2
        if hasattr(self.bus, "arlock"):
            assert len(self.bus.arlock) == 1
        if hasattr(self.bus, "arcache"):
            assert len(self.bus.arcache) == 4
        assert len(self.bus.arprot) == 3
        if hasattr(self.bus, "arqos"):
            assert len(self.bus.arqos) == 4
        if hasattr(self.bus, "arregion"):
            assert len(self.bus.arregion) == 4
        assert len(self.bus.arvalid) == 1
        assert len(self.bus.arready) == 1
        self.bus.arready.setimmediatevalue(0)

        assert len(self.bus.rid) == len(self.bus.arid)
        self.bus.rid.setimmediatevalue(0)
        self.bus.rdata.setimmediatevalue(0)
        assert len(self.bus.rresp) == 2
        self.bus.rresp.setimmediatevalue(0)
        assert len(self.bus.rlast) == 1
        self.bus.rlast.setimmediatevalue(0)
        if hasattr(self.bus, "ruser"):
            self.bus.ruser.setimmediatevalue(0)
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

            arid, addr, length, size, burst, prot = self.int_read_addr_queue.popleft()
            prot = AxiProt(prot)

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

                self.int_read_resp_queue.append((arid, int.from_bytes(data, 'little'), AxiResp.OKAY, n == length-1))
                self.int_read_resp_sync.set()

                self.log.info(f"Read word arid: {arid:#x} addr: {cur_addr:#010x} data: {' '.join((f'{c:02x}' for c in data))}")

                if burst != AxiBurstType.FIXED:
                    cur_addr += num_bytes

                    if burst == AxiBurstType.WRAP:
                        if cur_addr == upper_wrap_boundary:
                            cur_addr = lower_wrap_boundary

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
                arid = self.bus.arid.value.integer
                araddr = self.bus.araddr.value.integer
                arlen = self.bus.arlen.value.integer
                arsize = self.bus.arsize.value.integer
                arburst = self.bus.arburst.value.integer
                arprot = self.bus.arprot.value.integer
                self.int_read_addr_queue.append((arid, araddr, arlen, arsize, arburst, arprot))
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
                    rid, rdata, rresp, rlast = self.int_read_resp_queue.popleft()
                    self.bus.rid <= rid
                    self.bus.rdata <= rdata
                    self.bus.rresp <= rresp
                    self.bus.rlast <= rlast
                    self.bus.rvalid <= 1
                else:
                    self.bus.rvalid <= 0


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

