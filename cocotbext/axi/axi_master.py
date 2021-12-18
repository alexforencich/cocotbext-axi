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

import logging
from collections import Counter
from typing import List, NamedTuple, Union

import cocotb
from cocotb.queue import Queue
from cocotb.triggers import Event

from .version import __version__
from .constants import AxiBurstType, AxiLockType, AxiProt, AxiResp
from .axi_channels import AxiAWSource, AxiWSource, AxiBSink, AxiARSource, AxiRSink
from .address_space import Region
from .reset import Reset


# AXI master write helper objects
class AxiWriteCmd(NamedTuple):
    address: int
    data: bytes
    awid: int
    burst: AxiBurstType
    size: int
    lock: AxiLockType
    cache: int
    prot: AxiProt
    qos: int
    region: int
    user: int
    wuser: Union[list, int, None]
    event: Event


class AxiWriteRespCmd(NamedTuple):
    address: int
    length: int
    size: int
    cycles: int
    prot: AxiProt
    burst_list: List[int]
    event: Event


class AxiWriteResp(NamedTuple):
    address: int
    length: int
    resp: AxiResp
    user: Union[list, None]


# AXI master read helper objects
class AxiReadCmd(NamedTuple):
    address: int
    length: int
    arid: int
    burst: AxiBurstType
    size: int
    lock: AxiLockType
    cache: int
    prot: AxiProt
    qos: int
    region: int
    user: int
    event: Event


class AxiReadRespCmd(NamedTuple):
    address: int
    length: int
    size: int
    cycles: int
    prot: AxiProt
    burst_list: List[int]
    event: Event


class AxiReadResp(NamedTuple):
    address: int
    data: bytes
    resp: AxiResp
    user: Union[list, None]

    def __bytes__(self):
        return self.data


class TagContext:
    def __init__(self, manager):
        self.current_tag = 0
        self._cmd_queue = Queue()
        self._current_cmd = None
        self._resp_queue = Queue()
        self._cr = None
        self._manager = manager

    async def get_resp(self):
        return await self._resp_queue.get()

    def get_resp_nowait(self):
        return self._resp_queue.get_nowait()

    def _start(self):
        if self._cr is None:
            self._cr = cocotb.start_soon(self._process_queue())

    def _flush(self):
        flushed_cmds = []
        if self._cr is not None:
            self._cr.kill()
            self._cr = None
        self._manager._set_idle(self)
        if self._current_cmd is not None:
            flushed_cmds.append(self._current_cmd)
            self._current_cmd = None
        while not self._cmd_queue.empty():
            flushed_cmds.append(self._cmd_queue.get_nowait())
        while not self._resp_queue.empty():
            self._resp_queue.get_nowait()
        return flushed_cmds

    async def _process_queue(self):
        while True:
            cmd = await self._cmd_queue.get()
            self._current_cmd = cmd
            await self._manager._process(self, cmd)
            self._current_cmd = None

            if self._cmd_queue.empty() and self._resp_queue.empty():
                self._manager._set_idle(self)


class TagContextManager:
    def __init__(self, process):
        self._context_list = []
        self._context_idle_list = []
        self._context_mapping = {}
        self._process = process

    def _get_context(self, tag):
        if tag in self._context_mapping:
            return self._context_mapping[tag]
        elif self._context_idle_list:
            context = self._context_idle_list.pop()
        else:
            context = TagContext(self)
            self._context_list.append(context)
        context._start()
        context.current_tag = tag
        self._context_mapping[tag] = context
        return context

    def start_cmd(self, tag, cmd):
        context = self._get_context(tag)
        context._cmd_queue.put_nowait(cmd)

    def put_resp(self, tag, resp):
        context = self._get_context(tag)
        context._resp_queue.put_nowait(resp)

    def _set_idle(self, context):
        if context.current_tag in self._context_mapping:
            del self._context_mapping[context.current_tag]
            self._context_idle_list.append(context)
        context.current_tag = None

    def flush(self):
        flushed_cmds = []
        for c in self._context_list:
            flushed_cmds.extend(c._flush())
        return flushed_cmds


class AxiMasterWrite(Region, Reset):
    def __init__(self, bus, clock, reset=None, reset_active_level=True, max_burst_len=256, **kwargs):
        self.bus = bus
        self.clock = clock
        self.reset = reset
        self.log = logging.getLogger(f"cocotb.{bus.aw._entity._name}.{bus.aw._name}")

        self.log.info("AXI master (write)")
        self.log.info("cocotbext-axi version %s", __version__)
        self.log.info("Copyright (c) 2020 Alex Forencich")
        self.log.info("https://github.com/alexforencich/cocotbext-axi")

        self.aw_channel = AxiAWSource(bus.aw, clock, reset, reset_active_level)
        self.aw_channel.queue_occupancy_limit = 2
        self.w_channel = AxiWSource(bus.w, clock, reset, reset_active_level)
        self.w_channel.queue_occupancy_limit = 2
        self.b_channel = AxiBSink(bus.b, clock, reset, reset_active_level)
        self.b_channel.queue_occupancy_limit = 2

        self.write_command_queue = Queue()
        self.generator = None
        self.generator_done_cb = None
        self.command_available = Event()
        self.current_write_command = None

        self.id_count = 2**len(self.aw_channel.bus.awid)
        self.cur_id = 0
        self.active_id = Counter()

        self.tag_context_manager = TagContextManager(self._process_write_resp_id)

        self.in_flight_operations = 0
        self._idle = Event()
        self._idle.set()

        self.address_width = len(self.aw_channel.bus.awaddr)
        self.id_width = len(self.aw_channel.bus.awid)
        self.width = len(self.w_channel.bus.wdata)
        self.byte_size = 8
        self.byte_lanes = self.width // self.byte_size
        self.strb_mask = 2**self.byte_lanes-1

        self.max_burst_len = max(min(max_burst_len, 256), 1)
        self.max_burst_size = (self.byte_lanes-1).bit_length()

        self.awlock_present = hasattr(self.bus.aw, "awlock")
        self.awcache_present = hasattr(self.bus.aw, "awcache")
        self.awprot_present = hasattr(self.bus.aw, "awprot")
        self.awqos_present = hasattr(self.bus.aw, "awqos")
        self.awregion_present = hasattr(self.bus.aw, "awregion")
        self.awuser_present = hasattr(self.bus.aw, "awuser")
        self.wuser_present = hasattr(self.bus.w, "wuser")
        self.buser_present = hasattr(self.bus.b, "buser")

        super().__init__(2**self.address_width, **kwargs)

        self.log.info("AXI master configuration:")
        self.log.info("  Address width: %d bits", self.address_width)
        self.log.info("  ID width: %d bits", self.id_width)
        self.log.info("  Byte size: %d bits", self.byte_size)
        self.log.info("  Data width: %d bits (%d bytes)", self.width, self.byte_lanes)
        self.log.info("  Max burst size: %d (%d bytes)", self.max_burst_size, 2**self.max_burst_size)
        self.log.info("  Max burst length: %d cycles (%d bytes)",
            self.max_burst_len, self.max_burst_len*self.byte_lanes)

        self.log.info("AXI master signals:")
        for bus in (self.bus.aw, self.bus.w, self.bus.b):
            for sig in sorted(list(set().union(bus._signals, bus._optional_signals))):
                if hasattr(bus, sig):
                    self.log.info("  %s width: %d bits", sig, len(getattr(bus, sig)))
                else:
                    self.log.info("  %s: not present", sig)

        assert self.byte_lanes == len(self.w_channel.bus.wstrb)
        assert self.byte_lanes * self.byte_size == self.width

        assert len(self.b_channel.bus.bid) == len(self.aw_channel.bus.awid)

        self._process_write_cr = None
        self._process_write_resp_cr = None

        self._init_reset(reset, reset_active_level)

    def _prepare_write(self, address, data, awid=None, burst=AxiBurstType.INCR, size=None,
            lock=AxiLockType.NORMAL, cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0,
            wuser=0, event=None):
        '''Validate a write request from init_write() or generator, and return AxiWriteCmd object'''

        if event is None:
            event = Event()

        if not isinstance(event, Event):
            raise ValueError("Expected event object")

        if address < 0 or address >= 2**self.address_width:
            raise ValueError("Address out of range")

        if isinstance(data, int):
            raise ValueError("Expected bytes or bytearray for data")

        if awid is None or awid < 0:
            awid = None
        elif awid > self.id_count:
            raise ValueError("Requested ID exceeds maximum ID allowed for ID signal width")

        burst = AxiBurstType(burst)

        if size is None or size < 0:
            size = self.max_burst_size
        elif size > self.max_burst_size:
            raise ValueError("Requested burst size exceeds maximum burst size allowed for bus width")

        lock = AxiLockType(lock)
        prot = AxiProt(prot)

        if not self.awlock_present and lock != AxiLockType.NORMAL:
            raise ValueError("awlock sideband signal value specified, but signal is not connected")

        if not self.awcache_present and cache != 0b0011:
            raise ValueError("awcache sideband signal value specified, but signal is not connected")

        if not self.awprot_present and prot != AxiProt.NONSECURE:
            raise ValueError("awprot sideband signal value specified, but signal is not connected")

        if not self.awqos_present and qos != 0:
            raise ValueError("awqos sideband signal value specified, but signal is not connected")

        if not self.awregion_present and region != 0:
            raise ValueError("awregion sideband signal value specified, but signal is not connected")

        if not self.awuser_present and user != 0:
            raise ValueError("awuser sideband signal value specified, but signal is not connected")

        if not self.wuser_present and wuser != 0:
            raise ValueError("wuser sideband signal value specified, but signal is not connected")

        if wuser is None:
            wuser = 0
        elif isinstance(wuser, int):
            pass
        else:
            wuser = list(wuser)

        cmd = AxiWriteCmd(address, bytes(data), awid, burst, size, lock,
            cache, prot, qos, region, user, wuser, event)

        return cmd

    def generate_writes(self, generator, done_callback=None):
        '''Supplied generator will be used for write requests until it is exhausted, at which
        time done_callback (if any) will be called.
        Any discrete writes from init_write() and co. will be sent before the next generator write.
        The generator must yield a tuple (address, data) or (address, data, params)
        where params is a dict with keys and values mapping to optional arguments to init_write()
        '''
        self.generator = generator
        self.generator_done_cb = done_callback
        self.command_available.set()
        self._idle.clear()

    def init_write(self, address, data, awid=None, burst=AxiBurstType.INCR, size=None, lock=AxiLockType.NORMAL,
            cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0, wuser=0, event=None):

        cmd = self._prepare_write(address, data, awid, burst, size, lock,
            cache, prot, qos, region, user, wuser, event)

        self.write_command_queue.put_nowait(cmd)
        self.command_available.set()
        self._idle.clear()

        return cmd.event

    def idle(self):
        if (self.write_command_queue.qsize() == 0
                and self.generator is None
                and self.in_flight_operations == 0):
            return True
        else:
            return False

    async def wait(self):
        while not self.idle():
            await self._idle.wait()

    async def write(self, address, data, awid=None, burst=AxiBurstType.INCR, size=None,
            lock=AxiLockType.NORMAL, cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0, wuser=0):
        event = self.init_write(address, data, awid, burst, size, lock, cache, prot, qos, region, user, wuser)
        await event.wait()
        return event.data

    def _handle_reset(self, state):
        if state:
            self.log.info("Reset asserted")
            if self._process_write_cr is not None:
                self._process_write_cr.kill()
                self._process_write_cr = None
            if self._process_write_resp_cr is not None:
                self._process_write_resp_cr.kill()
                self._process_write_resp_cr = None

            self.aw_channel.clear()
            self.w_channel.clear()
            self.b_channel.clear()

            def flush_cmd(cmd):
                self.log.warning("Flushed write operation during reset: %s", cmd)
                if cmd.event:
                    cmd.event.set(None)

            while not self.write_command_queue.empty():
                cmd = self.write_command_queue.get_nowait()
                flush_cmd(cmd)

            if self.current_write_command:
                cmd = self.current_write_command
                self.current_write_command = None
                flush_cmd(cmd)

            for cmd in self.tag_context_manager.flush():
                flush_cmd(cmd)

            self.cur_id = 0
            self.active_id = Counter()

            self.generator = None
            self.generator_done_cb = None # Should this be called?
            self.in_flight_operations = 0
            self.command_available.clear()
            self._idle.set()
        else:
            self.log.info("Reset de-asserted")
            if self._process_write_cr is None:
                self._process_write_cr = cocotb.start_soon(self._process_write())
            if self._process_write_resp_cr is None:
                self._process_write_resp_cr = cocotb.start_soon(self._process_write_resp())

    async def _get_next_write(self):
        cmd = None
        while cmd is None:
            callback = None

            # prioritise queued writes over generated
            if not self.write_command_queue.empty():
                cmd = self.write_command_queue.get_nowait()
            elif self.generator is not None:
                args = next(self.generator, None)
                if args is None:
                    # generator exhausted
                    self.generator = None
                    callback = self.generator_done_cb
                    self.generator_done_cb = None
                else:
                    address, data = args[:2]
                    kwargs = args[2] if len(args) > 2 else {}
                    cmd = self._prepare_write(address, data, **kwargs)

            if cmd is None:
                # empty queue and no generator or it's exhausted. wait for command source
                self.command_available.clear()

                # callback may set new generator or queue writes causing immediate wakeup
                # is it possible to transition into the idle state here?
                if callback is not None:
                    callback()

                await self.command_available.wait()

        return cmd

    async def _process_write(self):
        while True:
            cmd = await self._get_next_write()
            self.current_write_command = cmd
            self.in_flight_operations += 1

            num_bytes = 2**cmd.size

            aligned_addr = (cmd.address // num_bytes) * num_bytes
            word_addr = (cmd.address // self.byte_lanes) * self.byte_lanes

            start_offset = cmd.address % self.byte_lanes
            end_offset = ((cmd.address + len(cmd.data) - 1) % self.byte_lanes) + 1

            cycles = (len(cmd.data) + (cmd.address % num_bytes) + num_bytes-1) // num_bytes

            cur_addr = aligned_addr
            offset = 0
            cycle_offset = aligned_addr-word_addr
            n = 0
            transfer_count = 0

            burst_list = []
            burst_length = 0

            if cmd.awid is not None:
                awid = cmd.awid
            else:
                awid = self.cur_id
                self.cur_id = (self.cur_id+1) % self.id_count

            wuser = cmd.wuser

            if self.log.isEnabledFor(logging.INFO):
                self.log.info("Write start addr: 0x%08x awid: 0x%x prot: %s data: %s",
                        cmd.address, awid, cmd.prot, ' '.join((f'{c:02x}' for c in cmd.data)))

            for k in range(cycles):
                start = cycle_offset
                stop = cycle_offset+num_bytes

                if k == 0:
                    start = start_offset
                if k == cycles-1:
                    stop = end_offset

                strb = (self.strb_mask << start) & self.strb_mask & (self.strb_mask >> (self.byte_lanes - stop))

                val = 0
                for j in range(start, stop):
                    val |= cmd.data[offset] << j*8
                    offset += 1

                if n >= burst_length:
                    transfer_count += 1
                    n = 0

                    # split on burst length
                    burst_length = min(cycles-k, min(max(self.max_burst_len, 1), 256))
                    # split on 4k address boundary
                    burst_length = (min(burst_length*num_bytes, 0x1000-(cur_addr & 0xfff))+num_bytes-1)//num_bytes

                    burst_list.append(burst_length)

                    aw = self.aw_channel._transaction_obj()
                    aw.awid = awid
                    aw.awaddr = cur_addr
                    aw.awlen = burst_length-1
                    aw.awsize = cmd.size
                    aw.awburst = cmd.burst
                    aw.awlock = cmd.lock
                    aw.awcache = cmd.cache
                    aw.awprot = cmd.prot
                    aw.awqos = cmd.qos
                    aw.awregion = cmd.region
                    aw.awuser = cmd.user

                    self.active_id[awid] += 1
                    await self.aw_channel.send(aw)

                    self.log.info("Write burst start awid: 0x%x awaddr: 0x%08x awlen: %d awsize: %d awprot: %s",
                            awid, cur_addr, burst_length-1, cmd.size, cmd.prot)

                n += 1

                w = self.w_channel._transaction_obj()
                w.wdata = val
                w.wstrb = strb
                w.wlast = n >= burst_length

                if isinstance(wuser, int):
                    w.wuser = wuser
                else:
                    if wuser and k < len(wuser):
                        w.wuser = wuser[k]
                    else:
                        w.wuser = 0

                await self.w_channel.send(w)

                cur_addr += num_bytes
                cycle_offset = (cycle_offset + num_bytes) % self.byte_lanes

            resp_cmd = AxiWriteRespCmd(cmd.address, len(cmd.data), cmd.size, cycles, cmd.prot, burst_list, cmd.event)
            self.tag_context_manager.start_cmd(awid, resp_cmd)

            self.current_write_command = None

    async def _process_write_resp(self):
        while True:
            b = await self.b_channel.recv()

            bid = int(getattr(b, 'bid', 0))

            if self.active_id[bid] <= 0:
                raise Exception(f"Unexpected burst ID {bid}")

            self.tag_context_manager.put_resp(bid, b)

    async def _process_write_resp_id(self, context, cmd):
        bid = context.current_tag

        resp = AxiResp.OKAY
        user = []

        for burst_length in cmd.burst_list:
            b = await context.get_resp()

            burst_resp = AxiResp(getattr(b, 'bresp', AxiResp.OKAY))
            burst_user = int(getattr(b, 'buser', 0))

            if burst_resp != AxiResp.OKAY:
                resp = burst_resp

            if burst_user is not None:
                user.append(burst_user)

            if self.active_id[bid] <= 0:
                raise Exception(f"Unexpected burst ID {bid}")

            self.active_id[bid] -= 1

            self.log.info("Write burst complete bid: 0x%x bresp: %s", bid, burst_resp)

        if not self.buser_present:
            user = None

        self.log.info("Write complete addr: 0x%08x prot: %s resp: %s length: %d",
                cmd.address, cmd.prot, resp, cmd.length)

        write_resp = AxiWriteResp(cmd.address, cmd.length, resp, user)

        cmd.event.set(write_resp)

        self.in_flight_operations -= 1

        if self.idle():
            self._idle.set()


class AxiMasterRead(Region, Reset):
    def __init__(self, bus, clock, reset=None, reset_active_level=True, max_burst_len=256, **kwargs):
        self.bus = bus
        self.clock = clock
        self.reset = reset
        self.log = logging.getLogger(f"cocotb.{bus.ar._entity._name}.{bus.ar._name}")

        self.log.info("AXI master (read)")
        self.log.info("cocotbext-axi version %s", __version__)
        self.log.info("Copyright (c) 2020 Alex Forencich")
        self.log.info("https://github.com/alexforencich/cocotbext-axi")

        self.ar_channel = AxiARSource(bus.ar, clock, reset, reset_active_level)
        self.ar_channel.queue_occupancy_limit = 2
        self.r_channel = AxiRSink(bus.r, clock, reset, reset_active_level)
        self.r_channel.queue_occupancy_limit = 2

        self.read_command_queue = Queue()
        self.generator = None
        self.generator_done_cb = None
        self.command_available = Event()
        self.current_read_command = None

        self.id_count = 2**len(self.ar_channel.bus.arid)
        self.cur_id = 0
        self.active_id = Counter()

        self.tag_context_manager = TagContextManager(self._process_read_resp_id)

        self.in_flight_operations = 0
        self._idle = Event()
        self._idle.set()

        self.address_width = len(self.ar_channel.bus.araddr)
        self.id_width = len(self.ar_channel.bus.arid)
        self.width = len(self.r_channel.bus.rdata)
        self.byte_size = 8
        self.byte_lanes = self.width // self.byte_size

        self.max_burst_len = max(min(max_burst_len, 256), 1)
        self.max_burst_size = (self.byte_lanes-1).bit_length()

        self.arlock_present = hasattr(self.bus.ar, "arlock")
        self.arcache_present = hasattr(self.bus.ar, "arcache")
        self.arprot_present = hasattr(self.bus.ar, "arprot")
        self.arqos_present = hasattr(self.bus.ar, "arqos")
        self.arregion_present = hasattr(self.bus.ar, "arregion")
        self.aruser_present = hasattr(self.bus.ar, "aruser")
        self.ruser_present = hasattr(self.bus.r, "ruser")

        super().__init__(2**self.address_width, **kwargs)

        self.log.info("AXI master configuration:")
        self.log.info("  Address width: %d bits", self.address_width)
        self.log.info("  ID width: %d bits", self.id_width)
        self.log.info("  Byte size: %d bits", self.byte_size)
        self.log.info("  Data width: %d bits (%d bytes)", self.width, self.byte_lanes)
        self.log.info("  Max burst size: %d (%d bytes)", self.max_burst_size, 2**self.max_burst_size)
        self.log.info("  Max burst length: %d cycles (%d bytes)",
            self.max_burst_len, self.max_burst_len*self.byte_lanes)

        self.log.info("AXI master signals:")
        for bus in (self.bus.ar, self.bus.r):
            for sig in sorted(list(set().union(bus._signals, bus._optional_signals))):
                if hasattr(bus, sig):
                    self.log.info("  %s width: %d bits", sig, len(getattr(bus, sig)))
                else:
                    self.log.info("  %s: not present", sig)

        assert self.byte_lanes * self.byte_size == self.width

        assert len(self.r_channel.bus.rid) == len(self.ar_channel.bus.arid)

        self._process_read_cr = None
        self._process_read_resp_cr = None

        self._init_reset(reset, reset_active_level)

    def _prepare_read(self, address, length, arid=None, burst=AxiBurstType.INCR, size=None,
            lock=AxiLockType.NORMAL, cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0, event=None):

        if event is None:
            event = Event()

        if not isinstance(event, Event):
            raise ValueError("Expected event object")

        if address < 0 or address >= 2**self.address_width:
            raise ValueError("Address out of range")

        if length < 0:
            raise ValueError("Read length must be positive")

        if arid is None or arid < 0:
            arid = None
        elif arid > self.id_count:
            raise ValueError("Requested ID exceeds maximum ID allowed for ID signal width")

        burst = AxiBurstType(burst)

        if size is None or size < 0:
            size = self.max_burst_size
        elif size > self.max_burst_size:
            raise ValueError("Requested burst size exceeds maximum burst size allowed for bus width")

        lock = AxiLockType(lock)
        prot = AxiProt(prot)

        if not self.arlock_present and lock != AxiLockType.NORMAL:
            raise ValueError("arlock sideband signal value specified, but signal is not connected")

        if not self.arcache_present and cache != 0b0011:
            raise ValueError("arcache sideband signal value specified, but signal is not connected")

        if not self.arprot_present and prot != AxiProt.NONSECURE:
            raise ValueError("arprot sideband signal value specified, but signal is not connected")

        if not self.arqos_present and qos != 0:
            raise ValueError("arqos sideband signal value specified, but signal is not connected")

        if not self.arregion_present and region != 0:
            raise ValueError("arregion sideband signal value specified, but signal is not connected")

        if not self.aruser_present and user != 0:
            raise ValueError("aruser sideband signal value specified, but signal is not connected")

        cmd = AxiReadCmd(address, length, arid, burst, size, lock, cache, prot, qos, region, user, event)

        return cmd

    def generate_reads(self, generator, done_callback=None):
        self.generator = generator
        self.generator_done_cb = done_callback
        self.command_available.set()
        self._idle.clear()

    def init_read(self, address, length, arid=None, burst=AxiBurstType.INCR, size=None,
            lock=AxiLockType.NORMAL, cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0, event=None):

        cmd = self._prepare_read(address, length, arid, burst, size,
                lock, cache, prot, qos, region, user, event)

        self.read_command_queue.put_nowait(cmd)
        self.command_available.set()
        self._idle.clear()

        return cmd.event

    def idle(self):
        if (self.read_command_queue.qsize() == 0
                and self.generator is None
                and self.in_flight_operations == 0):
            return True
        else:
            return False

    async def wait(self):
        while not self.idle():
            await self._idle.wait()

    async def read(self, address, length, arid=None, burst=AxiBurstType.INCR, size=None,
            lock=AxiLockType.NORMAL, cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0):
        event = self.init_read(address, length, arid, burst, size, lock, cache, prot, qos, region, user)
        await event.wait()
        return event.data

    def _handle_reset(self, state):
        if state:
            self.log.info("Reset asserted")
            if self._process_read_cr is not None:
                self._process_read_cr.kill()
                self._process_read_cr = None
            if self._process_read_resp_cr is not None:
                self._process_read_resp_cr.kill()
                self._process_read_resp_cr = None

            self.ar_channel.clear()
            self.r_channel.clear()

            def flush_cmd(cmd):
                self.log.warning("Flushed read operation during reset: %s", cmd)
                if cmd.event:
                    cmd.event.set(None)

            while not self.read_command_queue.empty():
                cmd = self.read_command_queue.get_nowait()
                flush_cmd(cmd)

            if self.current_read_command:
                cmd = self.current_read_command
                self.current_read_command = None
                flush_cmd(cmd)

            for cmd in self.tag_context_manager.flush():
                flush_cmd(cmd)

            self.cur_id = 0
            self.active_id = Counter()

            self.generator = None
            self.generator_done_cb = None # Should this be called?
            self.in_flight_operations = 0
            self.command_available.clear()
            self._idle.set()
        else:
            self.log.info("Reset de-asserted")
            if self._process_read_cr is None:
                self._process_read_cr = cocotb.start_soon(self._process_read())
            if self._process_read_resp_cr is None:
                self._process_read_resp_cr = cocotb.start_soon(self._process_read_resp())

    async def _get_next_read(self):
        cmd = None
        while cmd is None:
            callback = None

            # prioritise queued requests over generated
            if not self.read_command_queue.empty():
                cmd = self.read_command_queue.get_nowait()
            elif self.generator is not None:
                args = next(self.generator, None)
                if args is None:
                    # generator exhausted
                    self.generator = None
                    callback = self.generator_done_cb
                    self.generator_done_cb = None
                else:
                    address, length = args[:2]
                    kwargs = args[2] if len(args) > 2 else {}
                    cmd = self._prepare_read(address, length, **kwargs)

            if cmd is None:
                # empty queue and no generator or it's exhausted. wait for command source
                self.command_available.clear()

                # callback may set new generator or queue writes causing immediate wakeup
                # is it possible to transition into the idle state here?
                if callback is not None:
                    callback()

                await self.command_available.wait()

        return cmd

    async def _process_read(self):
        while True:
            cmd = await self._get_next_read()
            self.current_read_command = cmd
            self.in_flight_operations += 1

            num_bytes = 2**cmd.size

            aligned_addr = (cmd.address // num_bytes) * num_bytes

            cycles = (cmd.length + num_bytes-1 + (cmd.address % num_bytes)) // num_bytes

            burst_list = []

            cur_addr = aligned_addr
            n = 0

            burst_length = 0

            if cmd.arid is not None:
                arid = cmd.arid
            else:
                arid = self.cur_id
                self.cur_id = (self.cur_id+1) % self.id_count

            self.log.info("Read start addr: 0x%08x arid: 0x%x prot: %s", cmd.address, arid, cmd.prot)

            for k in range(cycles):

                n += 1
                if n >= burst_length:
                    n = 0

                    # split on burst length
                    burst_length = min(cycles-k, min(max(self.max_burst_len, 1), 256))
                    # split on 4k address boundary
                    burst_length = (min(burst_length*num_bytes, 0x1000-(cur_addr & 0xfff))+num_bytes-1)//num_bytes

                    burst_list.append(burst_length)

                    ar = self.ar_channel._transaction_obj()
                    ar.arid = arid
                    ar.araddr = cur_addr
                    ar.arlen = burst_length-1
                    ar.arsize = cmd.size
                    ar.arburst = cmd.burst
                    ar.arlock = cmd.lock
                    ar.arcache = cmd.cache
                    ar.arprot = cmd.prot
                    ar.arqos = cmd.qos
                    ar.arregion = cmd.region
                    ar.aruser = cmd.user

                    self.active_id[arid] += 1
                    await self.ar_channel.send(ar)

                    self.log.info("Read burst start arid: 0x%x araddr: 0x%08x arlen: %d arsize: %d arprot: %s",
                            arid, cur_addr, burst_length-1, cmd.size, cmd.prot)

                cur_addr += num_bytes

            resp_cmd = AxiReadRespCmd(cmd.address, cmd.length, cmd.size, cycles, cmd.prot, burst_list, cmd.event)
            self.tag_context_manager.start_cmd(arid, resp_cmd)

            self.current_read_command = None

    async def _process_read_resp(self):
        burst = []
        cur_rid = None

        while True:
            r = await self.r_channel.recv()

            rid = int(getattr(r, 'rid', 0))

            if cur_rid is not None and cur_rid != rid:
                raise Exception(f"ID not constant within burst (expected {cur_rid}, got {rid})")

            if self.active_id[rid] <= 0:
                raise Exception(f"Unexpected burst ID {rid}")

            burst.append(r)
            cur_rid = rid

            if int(r.rlast):
                self.tag_context_manager.put_resp(rid, burst)
                burst = []
                cur_rid = None

    async def _process_read_resp_id(self, context, cmd):
        rid = context.current_tag

        num_bytes = 2**cmd.size

        aligned_addr = (cmd.address // num_bytes) * num_bytes
        word_addr = (cmd.address // self.byte_lanes) * self.byte_lanes

        start_offset = cmd.address % self.byte_lanes

        cycle_offset = aligned_addr - word_addr
        data = bytearray()

        resp = AxiResp.OKAY
        user = []

        first = True

        for burst_length in cmd.burst_list:
            burst = await context.get_resp()

            if len(burst) != burst_length:
                raise Exception(f"Burst length incorrect (ID {rid}, expected {burst_length}, got {len(burst)}")

            for r in burst:
                cycle_data = int(r.rdata)
                cycle_resp = AxiResp(getattr(r, "rresp", AxiResp.OKAY))
                cycle_user = int(getattr(r, "ruser", 0))

                if cycle_resp != AxiResp.OKAY:
                    resp = cycle_resp

                if cycle_user is not None:
                    user.append(cycle_user)

                start = cycle_offset
                stop = cycle_offset+num_bytes

                if first:
                    start = start_offset

                for j in range(start, stop):
                    data.append((cycle_data >> j*8) & 0xff)

                cycle_offset = (cycle_offset + num_bytes) % self.byte_lanes

                first = False

            self.active_id[rid] -= 1

            self.log.info("Read burst complete rid: 0x%x rresp: %s", rid, resp)

        data = data[:cmd.length]

        if not self.ruser_present:
            user = None

        if self.log.isEnabledFor(logging.INFO):
            self.log.info("Read complete addr: 0x%08x prot: %s resp: %s data: %s",
                    cmd.address, cmd.prot, resp, ' '.join((f'{c:02x}' for c in data)))

        read_resp = AxiReadResp(cmd.address, bytes(data), resp, user)

        cmd.event.set(read_resp)

        self.in_flight_operations -= 1

        if self.idle():
            self._idle.set()


class AxiMaster(Region):
    def __init__(self, bus, clock, reset=None, reset_active_level=True, max_burst_len=256, **kwargs):
        self.write_if = None
        self.read_if = None

        self.write_if = AxiMasterWrite(bus.write, clock, reset, reset_active_level, max_burst_len, **kwargs)
        self.read_if = AxiMasterRead(bus.read, clock, reset, reset_active_level, max_burst_len, **kwargs)

        super().__init__(max(self.write_if.size, self.read_if.size), **kwargs)

    def init_read(self, address, length, arid=None, burst=AxiBurstType.INCR, size=None,
            lock=AxiLockType.NORMAL, cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0, event=None):
        return self.read_if.init_read(address, length, arid, burst, size, lock, cache, prot, qos, region, user, event)

    def init_write(self, address, data, awid=None, burst=AxiBurstType.INCR, size=None, lock=AxiLockType.NORMAL,
            cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0, wuser=0, event=None):
        return self.write_if.init_write(address, data, awid, burst, size, lock, cache, prot, qos, region, user, wuser, event)

    def generate_reads(self, generator, done_callback=None):
        return self.read_if.generate_reads(generator, done_callback)

    def generate_writes(self, generator, done_callback=None):
        return self.write_if.generate_writes(generator, done_callback)

    def idle(self):
        return (not self.read_if or self.read_if.idle()) and (not self.write_if or self.write_if.idle())

    async def wait(self):
        while not self.idle():
            await self.write_if.wait()
            await self.read_if.wait()

    async def wait_read(self):
        await self.read_if.wait()

    async def wait_write(self):
        await self.write_if.wait()

    async def read(self, address, length, arid=None, burst=AxiBurstType.INCR, size=None,
            lock=AxiLockType.NORMAL, cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0):
        return await self.read_if.read(address, length, arid,
            burst, size, lock, cache, prot, qos, region, user)

    async def write(self, address, data, awid=None, burst=AxiBurstType.INCR, size=None,
            lock=AxiLockType.NORMAL, cache=0b0011, prot=AxiProt.NONSECURE, qos=0, region=0, user=0, wuser=0):
        return await self.write_if.write(address, data, awid,
            burst, size, lock, cache, prot, qos, region, user, wuser)
