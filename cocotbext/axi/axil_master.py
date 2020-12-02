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

from collections import deque, namedtuple

import cocotb
from cocotb.triggers import Event
from cocotb.log import SimLog

from .version import __version__
from .constants import AxiProt, AxiResp
from .axil_channels import AxiLiteAWSource, AxiLiteWSource, AxiLiteBSink, AxiLiteARSource, AxiLiteRSink

# AXI lite master write
AxiLiteWriteCmd = namedtuple("AxiLiteWriteCmd", ["address", "data", "prot", "token"])
AxiLiteWriteRespCmd = namedtuple("AxiLiteWriteRespCmd", ["address", "length", "cycles", "prot", "token"])
AxiLiteWriteResp = namedtuple("AxiLiteWriteResp", ["address", "length", "resp", "token"])

# AXI lite master read
AxiLiteReadCmd = namedtuple("AxiLiteReadCmd", ["address", "length", "prot", "token"])
AxiLiteReadRespCmd = namedtuple("AxiLiteReadRespCmd", ["address", "length", "cycles", "prot", "token"])
AxiLiteReadResp = namedtuple("AxiLiteReadResp", ["address", "data", "resp", "token"])


class AxiLiteMasterWrite(object):
    def __init__(self, entity, name, clock, reset=None):
        self.log = SimLog("cocotb.%s.%s" % (entity._name, name))

        self.log.info("AXI lite master (write)")
        self.log.info("cocotbext-axi version %s", __version__)
        self.log.info("Copyright (c) 2020 Alex Forencich")
        self.log.info("https://github.com/alexforencich/cocotbext-axi")

        self.reset = reset

        self.aw_channel = AxiLiteAWSource(entity, name, clock, reset)
        self.w_channel = AxiLiteWSource(entity, name, clock, reset)
        self.b_channel = AxiLiteBSink(entity, name, clock, reset)

        self.active_tokens = set()

        self.write_command_queue = deque()
        self.write_command_sync = Event()
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

        self.log.info("AXI lite master configuration:")
        self.log.info("  Address width: %d bits", len(self.aw_channel.bus.awaddr))
        self.log.info("  Byte size: %d bits", self.byte_size)
        self.log.info("  Data width: %d bits (%d bytes)", self.width, self.byte_width)

        assert self.byte_width == len(self.w_channel.bus.wstrb)
        assert self.byte_width * self.byte_size == self.width

        cocotb.fork(self._process_write())
        cocotb.fork(self._process_write_resp())

    def init_write(self, address, data, prot=AxiProt.NONSECURE, token=None):
        if token is not None:
            if token in self.active_tokens:
                raise Exception("Token is not unique")
            self.active_tokens.add(token)

        self.in_flight_operations += 1

        self.write_command_queue.append(AxiLiteWriteCmd(address, bytearray(data), prot, token))
        self.write_command_sync.set()

    def idle(self):
        return not self.in_flight_operations

    async def wait(self, token=None):
        if token is None:
            while not self.idle():
                self.write_resp_sync.clear()
                await self.write_resp_sync.wait()
        else:
            if token not in self.active_tokens:
                raise ValueError("Unknown token")
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
                    if resp.token == token:
                        self.write_resp_queue.remove(resp)
                        self.active_tokens.remove(resp.token)
                        self.write_resp_set.remove(resp.token)
                        return resp
            return None
        if self.write_resp_queue:
            resp = self.write_resp_queue.popleft()
            if resp.token is not None:
                self.active_tokens.remove(resp.token)
                self.write_resp_set.remove(resp.token)
            return resp
        return None

    async def write(self, address, data, prot=AxiProt.NONSECURE):
        token = object()
        self.init_write(address, data, prot, token)
        await self.wait(token)
        return self.get_write_resp(token)

    async def write_words(self, address, data, byteorder='little', ws=2, prot=AxiProt.NONSECURE):
        words = data
        data = bytearray()
        for w in words:
            data.extend(w.to_bytes(ws, byteorder))
        await self.write(address, data, prot)

    async def write_dwords(self, address, data, byteorder='little', prot=AxiProt.NONSECURE):
        await self.write_words(address, data, byteorder, 4, prot)

    async def write_qwords(self, address, data, byteorder='little', prot=AxiProt.NONSECURE):
        await self.write_words(address, data, byteorder, 8, prot)

    async def write_byte(self, address, data, prot=AxiProt.NONSECURE):
        await self.write(address, [data], prot)

    async def write_word(self, address, data, byteorder='little', ws=2, prot=AxiProt.NONSECURE):
        await self.write_words(address, [data], byteorder, ws, prot)

    async def write_dword(self, address, data, byteorder='little', prot=AxiProt.NONSECURE):
        await self.write_dwords(address, [data], byteorder, prot)

    async def write_qword(self, address, data, byteorder='little', prot=AxiProt.NONSECURE):
        await self.write_qwords(address, [data], byteorder, prot)

    async def _process_write(self):
        while True:
            if not self.write_command_queue:
                self.write_command_sync.clear()
                await self.write_command_sync.wait()

            cmd = self.write_command_queue.popleft()

            word_addr = (cmd.address // self.byte_width) * self.byte_width

            start_offset = cmd.address % self.byte_width
            end_offset = ((cmd.address + len(cmd.data) - 1) % self.byte_width) + 1

            strb_start = (self.strb_mask << start_offset) & self.strb_mask
            strb_end = self.strb_mask >> (self.byte_width - end_offset)

            cycles = (len(cmd.data) + (cmd.address % self.byte_width) + self.byte_width-1) // self.byte_width

            resp_cmd = AxiLiteWriteRespCmd(cmd.address, len(cmd.data), cycles, cmd.prot, cmd.token)
            self.int_write_resp_command_queue.append(resp_cmd)
            self.int_write_resp_command_sync.set()

            offset = 0

            self.log.info("Write start addr: 0x%08x prot: %s data: %s",
                cmd.address, cmd.prot, ' '.join((f'{c:02x}' for c in cmd.data)))

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
                    val |= cmd.data[offset] << j*8
                    offset += 1

                aw = self.aw_channel._transaction_obj()
                aw.awaddr = word_addr + k*self.byte_width
                aw.awprot = cmd.prot

                w = self.w_channel._transaction_obj()
                w.wdata = val
                w.wstrb = strb

                await self.aw_channel.drive(aw)
                self.w_channel.send(w)

    async def _process_write_resp(self):
        while True:
            if not self.int_write_resp_command_queue:
                self.int_write_resp_command_sync.clear()
                await self.int_write_resp_command_sync.wait()

            cmd = self.int_write_resp_command_queue.popleft()

            resp = AxiResp.OKAY

            for k in range(cmd.cycles):
                await self.b_channel.wait()
                b = self.b_channel.recv()

                cycle_resp = AxiResp(b.bresp)

                if cycle_resp != AxiResp.OKAY:
                    resp = cycle_resp

            self.log.info("Write complete addr: 0x%08x prot: %s resp: %s length: %d",
                cmd.address, cmd.prot, resp, cmd.length)

            self.write_resp_queue.append(AxiLiteWriteResp(cmd.address, cmd.length, resp, cmd.token))
            self.write_resp_sync.set()
            if cmd.token is not None:
                self.write_resp_set.add(cmd.token)
            self.in_flight_operations -= 1


class AxiLiteMasterRead(object):
    def __init__(self, entity, name, clock, reset=None):
        self.log = SimLog("cocotb.%s.%s" % (entity._name, name))

        self.log.info("AXI lite master (read)")
        self.log.info("cocotbext-axi version %s", __version__)
        self.log.info("Copyright (c) 2020 Alex Forencich")
        self.log.info("https://github.com/alexforencich/cocotbext-axi")

        self.reset = reset

        self.ar_channel = AxiLiteARSource(entity, name, clock, reset)
        self.r_channel = AxiLiteRSink(entity, name, clock, reset)

        self.active_tokens = set()

        self.read_command_queue = deque()
        self.read_command_sync = Event()
        self.read_data_queue = deque()
        self.read_data_sync = Event()
        self.read_data_set = set()

        self.int_read_resp_command_queue = deque()
        self.int_read_resp_command_sync = Event()

        self.in_flight_operations = 0

        self.width = len(self.r_channel.bus.rdata)
        self.byte_size = 8
        self.byte_width = self.width // self.byte_size

        self.log.info("AXI lite master configuration:")
        self.log.info("  Address width: %d bits", len(self.ar_channel.bus.araddr))
        self.log.info("  Byte size: %d bits", self.byte_size)
        self.log.info("  Data width: %d bits (%d bytes)", self.width, self.byte_width)

        assert self.byte_width * self.byte_size == self.width

        cocotb.fork(self._process_read())
        cocotb.fork(self._process_read_resp())

    def init_read(self, address, length, prot=AxiProt.NONSECURE, token=None):
        if token is not None:
            if token in self.active_tokens:
                raise Exception("Token is not unique")
            self.active_tokens.add(token)

        self.in_flight_operations += 1

        self.read_command_queue.append(AxiLiteReadCmd(address, length, prot, token))
        self.read_command_sync.set()

    def idle(self):
        return not self.in_flight_operations

    async def wait(self, token=None):
        if token is None:
            while not self.idle():
                self.read_data_sync.clear()
                await self.read_data_sync.wait()
        else:
            if token not in self.active_tokens:
                raise ValueError("Unknown token")
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
                    if resp.token == token:
                        self.read_data_queue.remove(resp)
                        self.active_tokens.remove(resp.token)
                        self.read_data_set.remove(resp.token)
                        return resp
            return None
        if self.read_data_queue:
            resp = self.read_data_queue.popleft()
            if resp.token is not None:
                self.active_tokens.remove(resp.token)
                self.read_data_set.remove(resp.token)
            return resp
        return None

    async def read(self, address, length, prot=AxiProt.NONSECURE):
        token = object()
        self.init_read(address, length, prot, token)
        await self.wait(token)
        return self.get_read_data(token)

    async def read_words(self, address, count, byteorder='little', ws=2, prot=AxiProt.NONSECURE):
        data = await self.read(address, count*ws, prot)
        words = []
        for k in range(count):
            words.append(int.from_bytes(data.data[ws*k:ws*(k+1)], byteorder))
        return words

    async def read_dwords(self, address, count, byteorder='little', prot=AxiProt.NONSECURE):
        return await self.read_words(address, count, byteorder, 4, prot)

    async def read_qwords(self, address, count, byteorder='little', prot=AxiProt.NONSECURE):
        return await self.read_words(address, count, byteorder, 8, prot)

    async def read_byte(self, address, prot=AxiProt.NONSECURE):
        return (await self.read(address, 1, prot)).data[0]

    async def read_word(self, address, byteorder='little', ws=2, prot=AxiProt.NONSECURE):
        return (await self.read_words(address, 1, byteorder, ws, prot))[0]

    async def read_dword(self, address, byteorder='little', prot=AxiProt.NONSECURE):
        return (await self.read_dwords(address, 1, byteorder, prot))[0]

    async def read_qword(self, address, byteorder='little', prot=AxiProt.NONSECURE):
        return (await self.read_qwords(address, 1, byteorder, prot))[0]

    async def _process_read(self):
        while True:
            if not self.read_command_queue:
                self.read_command_sync.clear()
                await self.read_command_sync.wait()

            cmd = self.read_command_queue.popleft()

            word_addr = (cmd.address // self.byte_width) * self.byte_width

            cycles = (cmd.length + self.byte_width-1 + (cmd.address % self.byte_width)) // self.byte_width

            resp_cmd = AxiLiteReadRespCmd(cmd.address, cmd.length, cycles, cmd.prot, cmd.token)
            self.int_read_resp_command_queue.append(resp_cmd)
            self.int_read_resp_command_sync.set()

            self.log.info("Read start addr: 0x%08x prot: %s length: %d",
                cmd.address, cmd.prot, cmd.length)

            for k in range(cycles):
                ar = self.ar_channel._transaction_obj()
                ar.araddr = word_addr + k*self.byte_width
                ar.arprot = cmd.prot

                await self.ar_channel.drive(ar)

    async def _process_read_resp(self):
        while True:
            if not self.int_read_resp_command_queue:
                self.int_read_resp_command_sync.clear()
                await self.int_read_resp_command_sync.wait()

            cmd = self.int_read_resp_command_queue.popleft()

            start_offset = cmd.address % self.byte_width
            end_offset = ((cmd.address + cmd.length - 1) % self.byte_width) + 1

            data = bytearray()

            resp = AxiResp.OKAY

            for k in range(cmd.cycles):
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
                if k == cmd.cycles-1:
                    stop = end_offset

                for j in range(start, stop):
                    data.extend(bytearray([(cycle_data >> j*8) & 0xff]))

            self.log.info("Read complete addr: 0x%08x prot: %s resp: %s data: %s",
                cmd.address, cmd.prot, resp, ' '.join((f'{c:02x}' for c in data)))

            self.read_data_queue.append(AxiLiteReadResp(cmd.address, data, resp, cmd.token))
            self.read_data_sync.set()
            if cmd.token is not None:
                self.read_data_set.add(cmd.token)
            self.in_flight_operations -= 1


class AxiLiteMaster(object):
    def __init__(self, entity, name, clock, reset=None):
        self.write_if = None
        self.read_if = None

        self.write_if = AxiLiteMasterWrite(entity, name, clock, reset)
        self.read_if = AxiLiteMasterRead(entity, name, clock, reset)

    def init_read(self, address, length, prot=AxiProt.NONSECURE, token=None):
        self.read_if.init_read(address, length, prot, token)

    def init_write(self, address, data, prot=AxiProt.NONSECURE, token=None):
        self.write_if.init_write(address, data, prot, token)

    def idle(self):
        return (not self.read_if or self.read_if.idle()) and (not self.write_if or self.write_if.idle())

    async def wait(self, token=None):
        if token is None:
            while not self.idle():
                await self.write_if.wait()
                await self.read_if.wait()
        else:
            if token in self.write_if.active_tokens:
                await self.write_if.wait(token)
            else:
                await self.read_if.wait(token)

    async def wait_read(self, token=None):
        await self.read_if.wait(token)

    async def wait_write(self, token=None):
        await self.write_if.wait(token)

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

    async def read_words(self, address, count, byteorder='little', ws=2, prot=AxiProt.NONSECURE):
        return await self.read_if.read_words(address, count, byteorder, ws, prot)

    async def read_dwords(self, address, count, byteorder='little', prot=AxiProt.NONSECURE):
        return await self.read_if.read_dwords(address, count, byteorder, prot)

    async def read_qwords(self, address, count, byteorder='little', prot=AxiProt.NONSECURE):
        return await self.read_if.read_qwords(address, count, byteorder, prot)

    async def read_byte(self, address, prot=AxiProt.NONSECURE):
        return await self.read_if.read_byte(address, prot)

    async def read_word(self, address, byteorder='little', ws=2, prot=AxiProt.NONSECURE):
        return await self.read_if.read_word(address, byteorder, ws, prot)

    async def read_dword(self, address, byteorder='little', prot=AxiProt.NONSECURE):
        return await self.read_if.read_dword(address, byteorder, prot)

    async def read_qword(self, address, byteorder='little', prot=AxiProt.NONSECURE):
        return await self.read_if.read_qword(address, byteorder, prot)

    async def write(self, address, data, prot=AxiProt.NONSECURE):
        return await self.write_if.write(address, data, prot)

    async def write_words(self, address, data, byteorder='little', ws=2, prot=AxiProt.NONSECURE):
        return await self.write_if.write_words(address, data, byteorder, ws, prot)

    async def write_dwords(self, address, data, byteorder='little', prot=AxiProt.NONSECURE):
        return await self.write_if.write_dwords(address, data, byteorder, prot)

    async def write_qwords(self, address, data, byteorder='little', prot=AxiProt.NONSECURE):
        return await self.write_if.write_qwords(address, data, byteorder, prot)

    async def write_byte(self, address, data, prot=AxiProt.NONSECURE):
        return await self.write_if.write_byte(address, data, prot)

    async def write_word(self, address, data, byteorder='little', ws=2, prot=AxiProt.NONSECURE):
        return await self.write_if.write_word(address, data, byteorder, ws, prot)

    async def write_dword(self, address, data, byteorder='little', prot=AxiProt.NONSECURE):
        return await self.write_if.write_dword(address, data, byteorder, prot)

    async def write_qword(self, address, data, byteorder='little', prot=AxiProt.NONSECURE):
        return await self.write_if.write_qword(address, data, byteorder, prot)
