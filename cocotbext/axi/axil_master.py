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
from cocotb.triggers import RisingEdge, Event
from cocotb.log import SimLog

from collections import deque

from .constants import *
from .axil_channels import *


class AxiLiteMasterWrite(object):
    def __init__(self, entity, name, clock, reset=None):
        self.log = SimLog("cocotb.%s.%s" % (entity._name, name))

        self.reset = reset

        self.aw_channel = AxiLiteAWSource(entity, name, clock, reset)
        self.w_channel = AxiLiteWSource(entity, name, clock, reset)
        self.b_channel = AxiLiteBSink(entity, name, clock, reset)

        self.active_tokens = set()

        self.write_resp_queue = deque()
        self.write_resp_sync = Event()
        self.write_resp_set = set()

        self.int_write_resp_command_queue = deque()
        self.int_write_resp_command_sync = Event()

        self.in_flight_operations = 0

        self.width = len(self.w_channel.bus.wdata)
        self.byte_size = 8
        self.byte_width = self.width // self.byte_size
        self.strb_mask = 2**self.byte_width-1

        assert self.byte_width == len(self.w_channel.bus.wstrb)
        assert self.byte_width * self.byte_size == self.width

        cocotb.fork(self._process_write_resp())

    def init_write(self, address, data, prot=AxiProt.NONSECURE, token=None):
        if token is not None:
            if token in self.active_tokens:
                raise Exception("Token is not unique")
            self.active_tokens.add(token)

        self.in_flight_operations += 1

        word_addr = (address // self.byte_width) * self.byte_width

        start_offset = address % self.byte_width
        end_offset = ((address + len(data) - 1) % self.byte_width) + 1

        strb_start = (self.strb_mask << start_offset) & self.strb_mask
        strb_end = self.strb_mask >> (self.byte_width - end_offset)

        cycles = (len(data) + (address % self.byte_width) + self.byte_width-1) // self.byte_width

        self.int_write_resp_command_queue.append((address, len(data), cycles, prot, token))
        self.int_write_resp_command_sync.set()

        offset = 0

        self.log.info(f"Write start addr: {address:#010x} prot: {prot} data: {' '.join((f'{c:02x}' for c in data))}")

        for k in range(cycles):
            start = 0
            stop = self.byte_width
            strb = self.strb_mask

            if k == 0:
                start = start_offset
                strb &= strb_start
            if k == cycles-1:
                stop = end_offset
                strb &= strb_end

            val = 0
            for j in range(start, stop):
                val |= bytearray(data)[offset] << j*8
                offset += 1

            aw = self.aw_channel._transaction_obj()
            aw.awaddr = word_addr + k*self.byte_width
            aw.awprot = prot

            w = self.w_channel._transaction_obj()
            w.wdata = val
            w.wstrb = strb

            self.aw_channel.send(aw)
            self.w_channel.send(w)

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

    async def write(self, address, data, prot=AxiProt.NONSECURE):
        token = object()
        self.init_write(address, data, prot, token)
        await self.wait_for_token(token)
        return self.get_write_resp(token)

    async def _process_write_resp(self):
        while True:
            if not self.int_write_resp_command_queue:
                self.int_write_resp_command_sync.clear()
                await self.int_write_resp_command_sync.wait()

            addr, length, cycles, prot, token = self.int_write_resp_command_queue.popleft()

            resp = AxiResp.OKAY

            for k in range(cycles):
                await self.b_channel.wait()
                b = self.b_channel.recv()

                cycle_resp = AxiResp(b.bresp)

                if cycle_resp != AxiResp.OKAY:
                    resp = cycle_resp

            self.log.info(f"Write complete addr: {addr:#010x} prot: {prot} resp: {resp!s} length: {length}")

            self.write_resp_queue.append((addr, length, resp, token))
            self.write_resp_sync.set()
            if token is not None:
                self.write_resp_set.add(token)
            self.in_flight_operations -= 1


class AxiLiteMasterRead(object):
    def __init__(self, entity, name, clock, reset=None):
        self.log = SimLog("cocotb.%s.%s" % (entity._name, name))

        self.reset = reset

        self.ar_channel = AxiLiteARSource(entity, name, clock, reset)
        self.r_channel = AxiLiteRSink(entity, name, clock, reset)

        self.active_tokens = set()

        self.read_data_queue = deque()
        self.read_data_sync = Event()
        self.read_data_set = set()

        self.int_read_resp_command_queue = deque()
        self.int_read_resp_command_sync = Event()

        self.in_flight_operations = 0

        self.width = len(self.r_channel.bus.rdata)
        self.byte_size = 8
        self.byte_width = self.width // self.byte_size

        assert self.byte_width * self.byte_size == self.width

        cocotb.fork(self._process_read_resp())

    def init_read(self, address, length, prot=AxiProt.NONSECURE, token=None):
        if token is not None:
            if token in self.active_tokens:
                raise Exception("Token is not unique")
            self.active_tokens.add(token)

        self.in_flight_operations += 1

        word_addr = (address // self.byte_width) * self.byte_width

        cycles = (length + self.byte_width-1 + (address % self.byte_width)) // self.byte_width

        self.int_read_resp_command_queue.append((address, length, cycles, prot, token))
        self.int_read_resp_command_sync.set()

        self.log.info(f"Read start addr: {address:#010x} prot: {prot} length: {length}")

        for k in range(cycles):
            ar = self.ar_channel._transaction_obj()
            ar.araddr = word_addr + k*self.byte_width
            ar.arprot = prot

            self.ar_channel.send(ar)

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

    async def read(self, address, length, prot=AxiProt.NONSECURE):
        token = object()
        self.init_read(address, length, prot, token)
        await self.wait_for_token(token)
        return self.get_read_data(token)

    async def _process_read_resp(self):
        while True:
            if not self.int_read_resp_command_queue:
                self.int_read_resp_command_sync.clear()
                await self.int_read_resp_command_sync.wait()

            addr, length, cycles, prot, token = self.int_read_resp_command_queue.popleft()

            word_addr = (addr // self.byte_width) * self.byte_width

            start_offset = addr % self.byte_width
            end_offset = ((addr + length - 1) % self.byte_width) + 1

            data = bytearray()

            resp = AxiResp.OKAY

            for k in range(cycles):
                await self.r_channel.wait()
                r = self.r_channel.recv()

                cycle_data = int(r.rdata)
                cycle_resp = AxiResp(r.rresp)

                if cycle_resp != AxiResp.OKAY:
                    resp = cycle_resp

                start = 0
                stop = self.byte_width

                if k == 0:
                    start = start_offset
                if k == cycles-1:
                    stop = end_offset

                for j in range(start, stop):
                    data.extend(bytearray([(cycle_data >> j*8) & 0xff]))

            self.log.info(f"Read complete addr: {addr:#010x} prot: {prot} resp: {resp!s} data: {' '.join((f'{c:02x}' for c in data))}")

            self.read_data_queue.append((addr, data, resp, token))
            self.read_data_sync.set()
            if token is not None:
                self.read_data_set.add(token)
            self.in_flight_operations -= 1


class AxiLiteMaster(object):
    def __init__(self, entity, name, clock, reset=None):
        self.write_if = None
        self.read_if = None
        self.clock = clock

        self.write_if = AxiLiteMasterWrite(entity, name, clock, reset)
        self.read_if = AxiLiteMasterRead(entity, name, clock, reset)

    def init_read(self, address, length, prot=AxiProt.NONSECURE, token=None):
        self.read_if.init_read(address, length, prot, token)

    def init_write(self, address, data, prot=AxiProt.NONSECURE, token=None):
        self.write_if.init_write(address, data, prot, token)

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

    async def read(self, address, length, prot=AxiProt.NONSECURE):
        return await self.read_if.read(address, length, prot)

    async def write(self, address, data, prot=AxiProt.NONSECURE):
        return await self.write_if.write(address, data, prot)

