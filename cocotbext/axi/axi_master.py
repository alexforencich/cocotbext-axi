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

from collections import deque

from .constants import *


class AxiMasterWrite(BusDriver):

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

    def __init__(self, entity, name, clock, reset=None):
        super().__init__(entity, name, clock)

        self.active_tokens = set()

        self.write_command_queue = deque()
        self.write_command_sync = Event()
        self.write_resp_queue = deque()
        self.write_resp_sync = Event()
        self.write_resp_set = set()

        self.id_queue = deque(range(2**len(self.bus.awid)))
        self.id_sync = Event()

        self.int_write_addr_queue = deque()
        self.int_write_data_queue = deque()
        self.int_write_resp_command_queue = deque()
        self.int_write_resp_command_sync = Event()
        self.int_write_resp_queue_list = {}
        self.int_write_resp_sync_list = {}

        self.in_flight_operations = 0

        self.width = len(self.bus.wdata)
        self.byte_size = 8
        self.byte_width = self.width // self.byte_size
        self.strb_mask = 2**len(self.bus.wstrb)-1

        self.max_burst_len = 256
        self.max_burst_size = (self.byte_width-1).bit_length()

        assert self.byte_width == len(self.bus.wstrb)
        assert self.byte_width * self.byte_size == self.width

        self.reset = reset

        self.bus.awid.setimmediatevalue(0)
        self.bus.awaddr.setimmediatevalue(0)
        assert len(self.bus.awlen) == 8
        self.bus.awlen.setimmediatevalue(0)
        assert len(self.bus.awsize) == 3
        self.bus.awsize.setimmediatevalue(0)
        assert len(self.bus.awburst) == 2
        self.bus.awburst.setimmediatevalue(0)
        if hasattr(self.bus, "awlock"):
            assert len(self.bus.awlock) == 1
            self.bus.awlock.setimmediatevalue(0)
        if hasattr(self.bus, "awcache"):
            assert len(self.bus.awcache) == 4
            self.bus.awcache.setimmediatevalue(0)
        assert len(self.bus.awprot) == 3
        self.bus.awprot.setimmediatevalue(0)
        if hasattr(self.bus, "awqos"):
            assert len(self.bus.awqos) == 4
            self.bus.awqos.setimmediatevalue(0)
        if hasattr(self.bus, "awregion"):
            assert len(self.bus.awregion) == 4
            self.bus.awregion.setimmediatevalue(0)
        if hasattr(self.bus, "awuser"):
            self.bus.awuser.setimmediatevalue(0)
        assert len(self.bus.awvalid) == 1
        self.bus.awvalid.setimmediatevalue(0)
        assert len(self.bus.awready) == 1

        self.bus.wdata.setimmediatevalue(0)
        self.bus.wstrb.setimmediatevalue(0)
        assert len(self.bus.wlast) == 1
        self.bus.wlast.setimmediatevalue(0)
        if hasattr(self.bus, "wuser"):
            self.bus.wuser.setimmediatevalue(0)
        assert len(self.bus.wvalid) == 1
        self.bus.wvalid.setimmediatevalue(0)
        assert len(self.bus.wready) == 1

        assert len(self.bus.bid) == len(self.bus.awid)
        assert len(self.bus.bresp) == 2
        assert len(self.bus.bvalid) == 1
        assert len(self.bus.bready) == 1
        self.bus.bready.setimmediatevalue(0)

        cocotb.fork(self._process_write())
        cocotb.fork(self._process_write_resp())
        cocotb.fork(self._process_write_addr_if())
        cocotb.fork(self._process_write_data_if())
        cocotb.fork(self._process_write_resp_if())

    def init_write(self, address, data, burst=AxiBurstType.INCR, size=None, lock=AxiLockType.NORMAL, cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0, token=None):
        if token is not None:
            if token in self.active_tokens:
                raise Exception("Token is not unique")
            self.active_tokens.add(token)

        self.in_flight_operations += 1

        self.write_command_queue.append((address, data, burst, size, lock, cache, prot, qos, region, user, token))
        self.write_command_sync.set()

    def idle(self):
        return not self.in_flight_operations

    async def wait(self):
        while not self.idle():
            self.write_resp_sync.clear()
            await self.write_resp_sync.wait()

    async def wait_for_token(self, token):
        if token not in self.active_tokens:
            return
        while token not in self.write_resp_set:
            self.write_resp_sync.clear()
            await self.write_resp_sync.wait()

    def write_resp_ready(self, token=None):
        if token is not None:
            return token in self.write_resp_set
        return bool(self.write_resp_queue)

    def get_write_resp(self, token=None):
        if token is not None:
            if token in self.write_resp_set:
                for resp in self.write_resp_queue:
                    if resp[-1] == token:
                        self.write_resp_queue.remove(resp)
                        self.active_tokens.remove(resp[-1])
                        self.write_resp_set.remove(resp[-1])
                        return resp
            return None
        if self.write_resp_queue:
            resp = self.write_resp_queue.popleft()
            if resp[-1] is not None:
                self.active_tokens.remove(resp[-1])
                self.write_resp_set.remove(resp[-1])
            return resp
        return None

    async def write(self, address, data, burst=AxiBurstType.INCR, size=None, lock=AxiLockType.NORMAL, cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0):
        token = object()
        self.init_write(address, data, burst, size, lock, cache, prot, qos, region, user, token)
        await self.wait_for_token(token)
        return self.get_write_resp(token)

    async def _process_write(self):
        while True:
            if not self.write_command_queue:
                self.write_command_sync.clear()
                await self.write_command_sync.wait()

            address, data, burst, size, lock, cache, prot, qos, region, user, token = self.write_command_queue.popleft()

            num_bytes = self.byte_width

            if size is None:
                size = self.max_burst_size
            else:
                num_bytes = 2**size
                assert 0 < num_bytes <= self.byte_width

            aligned_addr = (address // num_bytes) * num_bytes
            word_addr = (address // self.byte_width) * self.byte_width

            start_offset = address % self.byte_width
            end_offset = ((address + len(data) - 1) % self.byte_width) + 1

            cycles = (len(data) + (address % num_bytes) + num_bytes-1) // num_bytes

            cur_addr = aligned_addr
            offset = 0
            cycle_offset = aligned_addr-word_addr
            n = 0
            transfer_count = 0

            burst_list = []
            burst_length = 0

            self.log.info(f"Write start addr: {address:#010x} prot: {prot} data: {' '.join((f'{c:02x}' for c in data))}")

            for k in range(cycles):
                start = cycle_offset
                stop = cycle_offset+num_bytes

                if k == 0:
                    start = start_offset
                if k == cycles-1:
                    stop = end_offset

                strb = (self.strb_mask << start) & self.strb_mask & (self.strb_mask >> (self.byte_width - stop))

                val = 0
                for j in range(start, stop):
                    val |= bytearray(data)[offset] << j*8
                    offset += 1

                if n >= burst_length:
                    if not self.id_queue:
                        self.id_sync.clear()
                        await self.id_sync.wait()

                    awid = self.id_queue.popleft()

                    transfer_count += 1
                    n = 0

                    burst_length = min(cycles-k, min(max(self.max_burst_len, 1), 256)) # max len
                    burst_length = (min(burst_length*num_bytes, 0x1000-(cur_addr&0xfff))+num_bytes-1)//num_bytes # 4k align

                    burst_list.append((awid, burst_length))
                    self.int_write_addr_queue.append((cur_addr, awid, burst_length-1, size, burst, lock, cache, prot, qos, region, user))

                    self.log.info(f"Write burst start awid {awid:#x} awaddr: {cur_addr:#010x} awlen: {burst_length-1} awsize: {size}")

                n += 1
                self.int_write_data_queue.append((val, strb, n >= burst_length, 0))

                cur_addr += num_bytes
                cycle_offset = (cycle_offset + num_bytes) % self.byte_width

            self.int_write_resp_command_queue.append((address, len(data), size, cycles, prot, burst_list, token))
            self.int_write_resp_command_sync.set()

    async def _process_write_resp(self):
        while True:
            if not self.int_write_resp_command_queue:
                self.int_write_resp_command_sync.clear()
                await self.int_write_resp_command_sync.wait()

            addr, length, size, cycles, prot, burst_list, token = self.int_write_resp_command_queue.popleft()

            resp = AxiResp.OKAY
            user = []

            for bid, burst_length in burst_list:
                self.int_write_resp_queue_list.setdefault(bid, deque())
                self.int_write_resp_sync_list.setdefault(bid, Event())
                if not self.int_write_resp_queue_list[bid]:
                    self.int_write_resp_sync_list[bid].clear()
                    await self.int_write_resp_sync_list[bid].wait()

                burst_id, burst_resp, burst_user = self.int_write_resp_queue_list[bid].popleft()
                burst_resp = AxiResp(burst_resp)

                if burst_resp != AxiResp.OKAY:
                    resp = burst_resp

                if burst_user is not None:
                    user.append(burst_user)

                if bid in self.id_queue:
                    raise Exception(f"Unexpected burst ID {bid}")
                self.id_queue.append(bid)
                self.id_sync.set()

                self.log.info(f"Write burst complete bid {burst_id:#x} bresp: {burst_resp!s}")

            self.log.info(f"Write complete addr: {addr:#010x} prot: {prot} resp: {resp!s} length: {length}")

            self.write_resp_queue.append((addr, length, resp, user, token))
            self.write_resp_sync.set()
            if token is not None:
                self.write_resp_set.add(token)
            self.in_flight_operations -= 1

    async def _process_write_addr_if(self):
        while True:
            await ReadOnly()

            # read handshake signals
            awready_sample = self.bus.awready.value
            awvalid_sample = self.bus.awvalid.value

            if self.reset is not None and self.reset.value:
                await RisingEdge(self.clock)
                self.bus.awvalid <= 0
                continue

            await RisingEdge(self.clock)

            if (awready_sample and awvalid_sample) or (not awvalid_sample):
                if self.int_write_addr_queue:
                    addr, awid, length, size, burst, lock, cache, prot, qos, region, user = self.int_write_addr_queue.popleft()
                    self.bus.awaddr <= addr
                    self.bus.awid <= awid
                    self.bus.awlen <= length
                    self.bus.awsize <= size
                    self.bus.awburst <= burst
                    if hasattr(self.bus, "awlock"):
                        self.bus.awlock <= lock
                    if hasattr(self.bus, "awcache"):
                        self.bus.awcache <= cache
                    self.bus.awprot <= prot
                    if hasattr(self.bus, "awqos"):
                        self.bus.awqos <= qos
                    if hasattr(self.bus, "awregion"):
                        self.bus.awregion <= region
                    if hasattr(self.bus, "awuser"):
                        self.bus.awuser <= user
                    self.bus.awvalid <= 1
                else:
                    self.bus.awvalid <= 0

    async def _process_write_data_if(self):
        while True:
            await ReadOnly()

            # read handshake signals
            wready_sample = self.bus.wready.value
            wvalid_sample = self.bus.wvalid.value

            if self.reset is not None and self.reset.value:
                await RisingEdge(self.clock)
                self.bus.wvalid <= 0
                continue

            await RisingEdge(self.clock)

            if (wready_sample and wvalid_sample) or (not wvalid_sample):
                if self.int_write_data_queue:
                    data, strb, last, user = self.int_write_data_queue.popleft()
                    self.bus.wdata <= data
                    self.bus.wstrb <= strb
                    self.bus.wlast <= last
                    if hasattr(self.bus, "awuser"):
                        self.bus.awuser <= user
                    self.bus.wvalid <= 1
                else:
                    self.bus.wvalid <= 0

    async def _process_write_resp_if(self):
        while True:
            await ReadOnly()

            # read handshake signals
            bready_sample = self.bus.bready.value
            bvalid_sample = self.bus.bvalid.value

            if self.reset is not None and self.reset.value:
                await RisingEdge(self.clock)
                self.bus.bready <= 0
                continue

            if bready_sample and bvalid_sample:
                bid = self.bus.bid.value.integer
                bresp = self.bus.bresp.value.integer
                buser = self.bus.buser.value.integer if hasattr(self.bus, "buser") else None
                self.int_write_resp_queue_list.setdefault(bid, deque())
                self.int_write_resp_queue_list[bid].append((bid, bresp, buser))
                self.int_write_resp_sync_list.setdefault(bid, Event())
                self.int_write_resp_sync_list[bid].set()

            await RisingEdge(self.clock)
            self.bus.bready <= 1


class AxiMasterRead(BusDriver):

    _signals = [
        # Read address channel
        "arid", "araddr", "arlen", "arsize", "arburst", "arprot", "arvalid", "arready",
        # Read data channel
        "rid", "rdata", "rresp", "rlast", "rvalid", "rready",
    ]

    _optional_signals = [
        # Read address channel
        "arlock", "arcache", "arqos", "arregion", "aruser",
        # Read data channel
        "ruser",
    ]

    def __init__(self, entity, name, clock, reset=None):
        super().__init__(entity, name, clock)

        self.active_tokens = set()

        self.read_command_queue = deque()
        self.read_command_sync = Event()
        self.read_data_queue = deque()
        self.read_data_sync = Event()
        self.read_data_set = set()

        self.id_queue = deque(range(2**len(self.bus.arid)))
        self.id_sync = Event()

        self.int_read_addr_queue = deque()
        self.int_read_resp_command_queue = deque()
        self.int_read_resp_command_sync = Event()
        self.int_read_resp_queue_list = {}
        self.int_read_resp_sync_list = {}

        self.in_flight_operations = 0

        self.width = len(self.bus.rdata)
        self.byte_size = 8
        self.byte_width = self.width // self.byte_size

        self.max_burst_len = 256
        self.max_burst_size = (self.byte_width-1).bit_length()

        assert self.byte_width * self.byte_size == self.width

        self.reset = reset

        self.bus.arid.setimmediatevalue(0)
        self.bus.araddr.setimmediatevalue(0)
        assert len(self.bus.arlen) == 8
        self.bus.arlen.setimmediatevalue(0)
        assert len(self.bus.arsize) == 3
        self.bus.arsize.setimmediatevalue(0)
        assert len(self.bus.arburst) == 2
        self.bus.arburst.setimmediatevalue(0)
        if hasattr(self.bus, "arlock"):
            assert len(self.bus.arlock) == 1
            self.bus.arlock.setimmediatevalue(0)
        if hasattr(self.bus, "arcache"):
            assert len(self.bus.arcache) == 4
            self.bus.arcache.setimmediatevalue(0)
        assert len(self.bus.arprot) == 3
        self.bus.arprot.setimmediatevalue(0)
        if hasattr(self.bus, "arqos"):
            assert len(self.bus.arqos) == 4
            self.bus.arqos.setimmediatevalue(0)
        if hasattr(self.bus, "arregion"):
            assert len(self.bus.arregion) == 4
            self.bus.arregion.setimmediatevalue(0)
        if hasattr(self.bus, "aruser"):
            self.bus.aruser.setimmediatevalue(0)
        assert len(self.bus.arvalid) == 1
        self.bus.arvalid.setimmediatevalue(0)
        assert len(self.bus.arready) == 1

        assert len(self.bus.rid) == len(self.bus.arid)
        assert len(self.bus.rresp) == 2
        assert len(self.bus.rlast) == 1
        assert len(self.bus.rvalid) == 1
        assert len(self.bus.rready) == 1
        self.bus.rready.setimmediatevalue(0)

        cocotb.fork(self._process_read())
        cocotb.fork(self._process_read_resp())
        cocotb.fork(self._process_read_addr_if())
        cocotb.fork(self._process_read_resp_if())

    def init_read(self, address, length, burst=AxiBurstType.INCR, size=None, lock=AxiLockType.NORMAL, cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0, token=None):
        if token is not None:
            if token in self.active_tokens:
                raise Exception("Token is not unique")
            self.active_tokens.add(token)

        self.in_flight_operations += 1

        self.read_command_queue.append((address, length, burst, size, lock, cache, prot, qos, region, user, token))
        self.read_command_sync.set()

    def idle(self):
        return not self.in_flight_operations

    async def wait(self):
        while not self.idle():
            self.read_resp_sync.clear()
            await self.read_resp_sync.wait()

    async def wait_for_token(self, token):
        if token not in self.active_tokens:
            return
        while token not in self.read_data_set:
            self.read_data_sync.clear()
            await self.read_data_sync.wait()

    def read_data_ready(self, token=None):
        if token is not None:
            return token in self.read_data_set
        return bool(self.read_data_queue)

    def get_read_data(self, token=None):
        if token is not None:
            if token in self.read_data_set:
                for resp in self.read_data_queue:
                    if resp[-1] == token:
                        self.read_data_queue.remove(resp)
                        self.active_tokens.remove(resp[-1])
                        self.read_data_set.remove(resp[-1])
                        return resp
            return None
        if self.read_data_queue:
            resp = self.read_data_queue.popleft()
            if resp[-1] is not None:
                self.active_tokens.remove(resp[-1])
                self.read_data_set.remove(resp[-1])
            return resp
        return None

    async def read(self, address, length, burst=AxiBurstType.INCR, size=None, lock=AxiLockType.NORMAL, cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0):
        token = object()
        self.init_read(address, length, burst, size, lock, cache, prot, qos, region, user, token)
        await self.wait_for_token(token)
        return self.get_read_data(token)

    async def _process_read(self):
        while True:
            if not self.read_command_queue:
                self.read_command_sync.clear()
                await self.read_command_sync.wait()

            address, length, burst, size, lock, cache, prot, qos, region, user, token = self.read_command_queue.popleft()

            num_bytes = self.byte_width

            if size is None:
                size = self.max_burst_size
            else:
                num_bytes = 2**size
                assert 0 < num_bytes <= self.byte_width

            aligned_addr = (address // num_bytes) * num_bytes
            word_addr = (address // self.byte_width) * self.byte_width

            cycles = (length + num_bytes-1 + (address % num_bytes)) // num_bytes

            burst_list = []

            cur_addr = aligned_addr
            n = 0

            burst_length = 0

            for k in range(cycles):

                n += 1
                if n >= burst_length:
                    if not self.id_queue:
                        self.id_sync.clear()
                        await self.id_sync.wait()

                    arid = self.id_queue.popleft()

                    n = 0

                    burst_length = min(cycles-k, min(max(self.max_burst_len, 1), 256)) # max len
                    burst_length = (min(burst_length*num_bytes, 0x1000-(cur_addr&0xfff))+num_bytes-1)//num_bytes # 4k align

                    burst_list.append((arid, burst_length))
                    self.int_read_addr_queue.append((cur_addr, arid, burst_length-1, size, burst, lock, cache, prot, qos, region, user))

                    self.log.info(f"Read burst start arid {arid:#x} araddr: {cur_addr:#010x} arlen: {burst_length-1} arsize: {size}")

                cur_addr += num_bytes

            self.int_read_resp_command_queue.append((address, length, size, cycles, prot, burst_list, token))
            self.int_read_resp_command_sync.set()


    async def _process_read_resp(self):
        while True:
            if not self.int_read_resp_command_queue:
                self.int_read_resp_command_sync.clear()
                await self.int_read_resp_command_sync.wait()

            addr, length, size, cycles, prot, burst_list, token = self.int_read_resp_command_queue.popleft()

            num_bytes = 2**size

            aligned_addr = (addr // num_bytes) * num_bytes
            word_addr = (addr // self.byte_width) * self.byte_width

            start_offset = addr % self.byte_width
            end_offset = ((addr + length - 1) % self.byte_width) + 1

            cycle_offset = aligned_addr - word_addr
            data = bytearray()

            resp = AxiResp.OKAY
            user = []

            first = True

            for rid, burst_length in burst_list:
                for k in range(burst_length):
                    self.int_read_resp_queue_list.setdefault(rid, deque())
                    self.int_read_resp_sync_list.setdefault(rid, Event())
                    if not self.int_read_resp_queue_list[rid]:
                        self.int_read_resp_sync_list[rid].clear()
                        await self.int_read_resp_sync_list[rid].wait()

                    cycle_id, cycle_data, cycle_resp, cycle_last, cycle_user = self.int_read_resp_queue_list[rid].popleft()
                    cycle_resp = AxiResp(cycle_resp)

                    if cycle_resp != AxiResp.OKAY:
                        resp = cycle_resp

                    if cycle_user is not None:
                        user.append(cycle_user)

                    start = cycle_offset
                    stop = cycle_offset+num_bytes

                    if first:
                        start = start_offset

                    assert cycle_last == (k == burst_length - 1)

                    for j in range(start, stop):
                        data.append((cycle_data >> j*8) & 0xff)

                    cycle_offset = (cycle_offset + num_bytes) % self.byte_width

                    first = False

                if rid in self.id_queue:
                    raise Exception(f"Unexpected burst ID {rid}")
                self.id_queue.append(rid)
                self.id_sync.set()

                self.log.info(f"Read burst complete rid {cycle_id:#x} rresp: {resp!s}")

            data = data[:length]

            self.log.info(f"Read complete addr: {addr:#010x} prot: {prot} resp: {resp!s} data: {' '.join((f'{c:02x}' for c in data))}")

            self.read_data_queue.append((addr, data, resp, user, token))
            self.read_data_sync.set()
            if token is not None:
                self.read_data_set.add(token)
            self.in_flight_operations -= 1

    async def _process_read_addr_if(self):
        while True:
            await ReadOnly()

            # read handshake signals
            arready_sample = self.bus.arready.value
            arvalid_sample = self.bus.arvalid.value

            if self.reset is not None and self.reset.value:
                await RisingEdge(self.clock)
                self.bus.arvalid <= 0
                continue

            await RisingEdge(self.clock)

            if (arready_sample and arvalid_sample) or (not arvalid_sample):
                if self.int_read_addr_queue:
                    addr, arid, length, size, burst, lock, cache, prot, qos, region, user = self.int_read_addr_queue.popleft()
                    self.bus.araddr <= addr
                    self.bus.arid <= arid
                    self.bus.arlen <= length
                    self.bus.arsize <= size
                    self.bus.arburst <= burst
                    if hasattr(self.bus, "arlock"):
                        self.bus.arlock <= lock
                    if hasattr(self.bus, "arcache"):
                        self.bus.arcache <= cache
                    self.bus.arprot <= prot
                    if hasattr(self.bus, "arqos"):
                        self.bus.arqos <= qos
                    if hasattr(self.bus, "arregion"):
                        self.bus.arregion <= region
                    if hasattr(self.bus, "aruser"):
                        self.bus.aruser <= user
                    self.bus.arvalid <= 1
                else:
                    self.bus.arvalid <= 0

    async def _process_read_resp_if(self):
        while True:
            await ReadOnly()

            # read handshake signals
            rready_sample = self.bus.rready.value
            rvalid_sample = self.bus.rvalid.value

            if self.reset is not None and self.reset.value:
                await RisingEdge(self.clock)
                self.bus.rready <= 0
                continue

            if rready_sample and rvalid_sample:
                rid = self.bus.rid.value.integer
                rdata = self.bus.rdata.value.integer
                rresp = self.bus.rresp.value.integer
                rlast = self.bus.rlast.value.integer
                ruser = self.bus.ruser.value.integer if hasattr(self.bus, "ruser") else None
                self.int_read_resp_queue_list.setdefault(rid, deque())
                self.int_read_resp_queue_list[rid].append((rid, rdata, rresp, rlast, ruser))
                self.int_read_resp_sync_list.setdefault(rid, Event())
                self.int_read_resp_sync_list[rid].set()

            await RisingEdge(self.clock)
            self.bus.rready <= 1


class AxiMaster(object):
    def __init__(self, entity, name, clock, reset=None):
        self.write_if = None
        self.read_if = None
        self.clock = clock

        self.write_if = AxiMasterWrite(entity, name, clock, reset)
        self.read_if = AxiMasterRead(entity, name, clock, reset)

    def init_read(self, address, length, burst=AxiBurstType.INCR, size=None, lock=AxiLockType.NORMAL, cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0, token=None):
        self.read_if.init_read(address, length, burst, size, lock, cache, prot, qos, region, user, token)

    def init_write(self, address, data, burst=AxiBurstType.INCR, size=None, lock=AxiLockType.NORMAL, cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0, token=None):
        self.write_if.init_write(address, data, burst, size, lock, cache, prot, qos, region, user, token)

    def idle(self):
        return (not self.read_if or self.read_if.idle()) and (not self.write_if or self.write_if.idle())

    async def wait(self):
        while not self.idle():
            await RisingEdge(self.clock)

    async def wait_read(self):
        await self.read_if.wait()

    async def wait_write(self):
        await self.write_if.wait()

    def read_data_ready(self, token=None):
        return self.read_if.read_data_ready(token)

    def get_read_data(self, token=None):
        return self.read_if.get_read_data(token)

    def write_resp_ready(self, token=None):
        return self.write_if.write_resp_ready(token)

    def get_write_resp(self, token=None):
        return self.write_if.get_write_resp(token)

    async def read(self, address, length, burst=AxiBurstType.INCR, size=None, lock=AxiLockType.NORMAL, cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0):
        return await self.read_if.read(address, length, burst, size, lock, cache, prot, qos, region, user)

    async def write(self, address, data, burst=AxiBurstType.INCR, size=None, lock=AxiLockType.NORMAL, cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0):
        return await self.write_if.write(address, data, burst, size, lock, cache, prot, qos, region, user)

