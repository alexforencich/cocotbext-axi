"""

Copyright (c) 2025 Alex Forencich

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
from typing import NamedTuple

import cocotb
from cocotb.queue import Queue
from cocotb.triggers import RisingEdge, Event
from cocotb_bus.bus import Bus

from .version import __version__
from .constants import AxiResp, AxiProt
from .address_space import Region
from .reset import Reset
from .memory import Memory


# APB master write helper objects
class ApbWriteCmd(NamedTuple):
    address: int
    data: bytes
    prot: AxiProt
    event: Event


class ApbWriteResp(NamedTuple):
    address: int
    length: int
    resp: AxiResp


# APB master read helper objects
class ApbReadCmd(NamedTuple):
    address: int
    length: int
    prot: AxiProt
    event: Event


class ApbReadResp(NamedTuple):
    address: int
    data: bytes
    resp: AxiResp

    def __bytes__(self):
        return self.data


class ApbBus(Bus):

    _signals = ["paddr", "psel", "penable", "pwrite", "pwdata", "pstrb", "pready", "prdata"]
    _optional_signals = ["pprot", "pslverr"]

    def __init__(self, entity=None, prefix=None, **kwargs):
        super().__init__(entity, prefix, self._signals, optional_signals=self._optional_signals, **kwargs)

    @classmethod
    def from_entity(cls, entity, **kwargs):
        return cls(entity, **kwargs)

    @classmethod
    def from_prefix(cls, entity, prefix, **kwargs):
        return cls(entity, prefix, **kwargs)


class ApbPause:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._pause = False
        self._pause_generator = None
        self._pause_cr = None

    def _pause_update(self, val):
        pass

    @property
    def pause(self):
        return self._pause

    @pause.setter
    def pause(self, val):
        if self._pause != val:
            self._pause_update(val)
        self._pause = val

    def set_pause_generator(self, generator=None):
        if self._pause_cr is not None:
            self._pause_cr.kill()
            self._pause_cr = None

        self._pause_generator = generator

        if self._pause_generator is not None:
            self._pause_cr = cocotb.start_soon(self._run_pause())

    def clear_pause_generator(self):
        self.set_pause_generator(None)

    async def _run_pause(self):
        clock_edge_event = RisingEdge(self.clock)

        for val in self._pause_generator:
            self.pause = val
            await clock_edge_event


class ApbMaster(ApbPause, Region, Reset):
    def __init__(self, bus, clock, reset=None, reset_active_level=True, **kwargs):
        self.bus = bus
        self.clock = clock
        self.reset = reset
        if bus._name:
            self.log = logging.getLogger(f"cocotb.{bus._entity._name}.{bus._name}")
        else:
            self.log = logging.getLogger(f"cocotb.{bus._entity._name}")

        self.log.info("APB master")
        self.log.info("cocotbext-axi version %s", __version__)
        self.log.info("Copyright (c) 2025 Alex Forencich")
        self.log.info("https://github.com/alexforencich/cocotbext-axi")

        self.command_queue = Queue()
        self.command_queue.queue_occupancy_limit = 2
        self.current_command = None

        self.in_flight_operations = 0
        self._idle = Event()
        self._idle.set()

        self.address_width = len(self.bus.paddr)
        self.width = len(self.bus.pwdata)
        self.byte_size = 8
        self.byte_lanes = self.width // self.byte_size
        self.strb_mask = 2**self.byte_lanes-1

        self.pprot_present = hasattr(self.bus, "pprot")
        self.pstrb_present = hasattr(self.bus, "pstrb")
        self.pslverr_present = hasattr(self.bus, "pslverr")

        super().__init__(2**self.address_width, **kwargs)

        self.log.info("APB master configuration:")
        self.log.info("  Address width: %d bits", self.address_width)
        self.log.info("  Byte size: %d bits", self.byte_size)
        self.log.info("  Data width: %d bits (%d bytes)", self.width, self.byte_lanes)

        self.log.info("APB master signals:")
        for sig in sorted(list(set().union(self.bus._signals, self.bus._optional_signals))):
            if hasattr(bus, sig):
                self.log.info("  %s width: %d bits", sig, len(getattr(bus, sig)))
            else:
                self.log.info("  %s: not present", sig)

        if self.pstrb_present:
            assert self.byte_lanes == len(self.bus.pstrb)
        assert self.byte_lanes * self.byte_size == self.width

        self.bus.paddr.setimmediatevalue(0)
        if self.pprot_present:
            self.bus.pprot.setimmediatevalue(0)
        self.bus.psel.setimmediatevalue(False)
        self.bus.penable.setimmediatevalue(False)
        self.bus.pwrite.setimmediatevalue(False)
        self.bus.pwdata.setimmediatevalue(0)
        if self.pstrb_present:
            self.bus.pstrb.setimmediatevalue(0)

        self._run_cr = None

        self._init_reset(reset, reset_active_level)

    def init_write(self, address, data, prot=AxiProt.NONSECURE, event=None):
        if event is None:
            event = Event()

        if not isinstance(event, Event):
            raise ValueError("Expected event object")

        if address < 0 or address >= 2**self.address_width:
            raise ValueError("Address out of range")

        if isinstance(data, int):
            raise ValueError("Expected bytes or bytearray for data")

        if address+len(data) > 2**self.address_width:
            raise ValueError("Requested transfer overruns end of address space")

        if not self.pprot_present and prot != AxiProt.NONSECURE:
            raise ValueError("pprot sideband signal value specified, but signal is not connected")

        data = bytes(data)

        cocotb.start_soon(self._write_wrapper(address, bytes(data), prot, event))

        return event

    def init_read(self, address, length, prot=AxiProt.NONSECURE, event=None):
        if event is None:
            event = Event()

        if not isinstance(event, Event):
            raise ValueError("Expected event object")

        if address < 0 or address >= 2**self.address_width:
            raise ValueError("Address out of range")

        if length < 0:
            raise ValueError("Read length must be positive")

        if address+length > 2**self.address_width:
            raise ValueError("Requested transfer overruns end of address space")

        if not self.pprot_present and prot != AxiProt.NONSECURE:
            raise ValueError("arprot sideband signal value specified, but signal is not connected")

        cocotb.start_soon(self._read_wrapper(address, length, prot, event))

        return event

    def idle(self):
        return not self.in_flight_operations

    async def wait(self):
        while not self.idle():
            await self._idle.wait()

    async def write(self, address, data, prot=AxiProt.NONSECURE):
        if address < 0 or address >= 2**self.address_width:
            raise ValueError("Address out of range")

        if isinstance(data, int):
            raise ValueError("Expected bytes or bytearray for data")

        if address+len(data) > 2**self.address_width:
            raise ValueError("Requested transfer overruns end of address space")

        if not self.pprot_present and prot != AxiProt.NONSECURE:
            raise ValueError("pprot sideband signal value specified, but signal is not connected")

        event = Event()
        data = bytes(data)

        self.in_flight_operations += 1
        self._idle.clear()

        await self.command_queue.put(ApbWriteCmd(address, data, prot, event))
        await event.wait()
        return event.data

    async def _write_wrapper(self, address, data, prot, event):
        event.set(await self.write(address, data, prot))

    async def read(self, address, length, prot=AxiProt.NONSECURE):
        if address < 0 or address >= 2**self.address_width:
            raise ValueError("Address out of range")

        if length < 0:
            raise ValueError("Read length must be positive")

        if address+length > 2**self.address_width:
            raise ValueError("Requested transfer overruns end of address space")

        if not self.pprot_present and prot != AxiProt.NONSECURE:
            raise ValueError("arprot sideband signal value specified, but signal is not connected")

        event = Event()

        self.in_flight_operations += 1
        self._idle.clear()

        await self.command_queue.put(ApbReadCmd(address, length, prot, event))

        await event.wait()
        return event.data

    async def _read_wrapper(self, address, length, prot, event):
        event.set(await self.read(address, length, prot))

    def _handle_reset(self, state):
        if state:
            self.log.info("Reset asserted")

            self.bus.psel.value = False
            self.bus.penable.value = False

            if self._run_cr is not None:
                self._run_cr.kill()
                self._run_cr = None

            def flush_cmd(cmd):
                self.log.warning("Flushed write operation during reset: %s", cmd)
                if cmd.event:
                    cmd.event.set(None)

            while not self.command_queue.empty():
                cmd = self.command_queue.get_nowait()
                flush_cmd(cmd)

            if self.current_command:
                cmd = self.current_command
                self.current_command = None
                flush_cmd(cmd)

            self.in_flight_operations = 0
            self._idle.set()
        else:
            self.log.info("Reset de-asserted")
            if self._run_cr is None:
                self._run_cr = cocotb.start_soon(self._run())

    async def _run(self):
        clock_edge_event = RisingEdge(self.clock)

        while True:
            cmd = await self.command_queue.get()
            self.current_command = cmd

            length = 0
            pwrite = False

            if isinstance(cmd, ApbWriteCmd):
                length = len(cmd.data)
                pwrite = True
            else:
                length = cmd.length
                pwrite = False

            word_addr = (cmd.address // self.byte_lanes) * self.byte_lanes

            start_offset = cmd.address % self.byte_lanes
            end_offset = ((cmd.address + length - 1) % self.byte_lanes) + 1

            strb_start = (self.strb_mask << start_offset) & self.strb_mask
            strb_end = self.strb_mask >> (self.byte_lanes - end_offset)

            cycles = (length + (cmd.address % self.byte_lanes) + self.byte_lanes-1) // self.byte_lanes

            offset = 0
            read_data = bytearray()
            resp = AxiResp.OKAY

            if self.log.isEnabledFor(logging.INFO):
                if pwrite:
                    self.log.info("Write start addr: 0x%08x prot: %s data: %s",
                            cmd.address, cmd.prot, ' '.join((f'{c:02x}' for c in cmd.data)))
                else:
                    self.log.info("Read start addr: 0x%08x prot: %s length: %d",
                            cmd.address, cmd.prot, cmd.length)

            await clock_edge_event
            self.bus.psel.value = True

            for k in range(cycles):
                start = 0
                stop = self.byte_lanes
                strb = self.strb_mask

                if k == 0:
                    start = start_offset
                    strb &= strb_start
                if k == cycles-1:
                    stop = end_offset
                    strb &= strb_end

                val = 0
                if pwrite:
                    for j in range(start, stop):
                        val |= cmd.data[offset] << j*8
                        offset += 1

                    if not self.pstrb_present and strb != self.strb_mask:
                        self.log.warning("Partial operation requested with pstrb not connected, write will be zero-padded (0x%x != 0x%x)", strb, self.strb_mask)
                else:
                    strb = 0

                while self.pause:
                    await clock_edge_event

                await clock_edge_event

                if k == 0:
                    self.bus.paddr.value = cmd.address
                else:
                    self.bus.paddr.value = word_addr + k*self.byte_lanes
                self.bus.pprot.value = cmd.prot
                self.bus.penable.value = True
                self.bus.pwrite.value = pwrite
                self.bus.pwdata.value = val
                self.bus.pstrb.value = strb

                await clock_edge_event

                while not int(self.bus.pready.value):
                    await clock_edge_event

                self.bus.penable.value = False

                cycle_data = int(self.bus.prdata.value)
                if self.pslverr_present and int(self.bus.pslverr.value):
                    resp = AxiResp.SLVERR

                start = 0
                stop = self.byte_lanes

                if k == 0:
                    start = start_offset
                if k == cycles-1:
                    stop = end_offset

                for j in range(start, stop):
                    read_data.append((cycle_data >> j*8) & 0xff)

            self.bus.psel.value = False

            if pwrite:
                self.log.info("Write complete addr: 0x%08x prot: %s resp: %s length: %d",
                        cmd.address, cmd.prot, resp, length)
                write_resp = ApbWriteResp(cmd.address, length, resp)
                cmd.event.set(write_resp)
            else:
                if self.log.isEnabledFor(logging.INFO):
                    self.log.info("Read complete addr: 0x%08x prot: %s resp: %s data: %s",
                            cmd.address, cmd.prot, resp, ' '.join((f'{c:02x}' for c in read_data)))
                read_resp = ApbReadResp(cmd.address, bytes(read_data), resp)
                cmd.event.set(read_resp)

            self.current_write_command = None

            self.in_flight_operations -= 1

            if self.in_flight_operations == 0:
                self._idle.set()


class ApbSlave(ApbPause, Reset):
    def __init__(self, bus, clock, reset=None, target=None, reset_active_level=True, **kwargs):
        self.bus = bus
        self.clock = clock
        self.reset = reset
        self.target = target
        if bus._name:
            self.log = logging.getLogger(f"cocotb.{bus._entity._name}.{bus._name}")
        else:
            self.log = logging.getLogger(f"cocotb.{bus._entity._name}")

        self.log.info("APB slave model")
        self.log.info("cocotbext-axi version %s", __version__)
        self.log.info("Copyright (c) 2025 Alex Forencich")
        self.log.info("https://github.com/alexforencich/cocotbext-axi")

        super().__init__(**kwargs)

        self.address_width = len(self.bus.paddr)
        self.width = len(self.bus.pwdata)
        self.byte_size = 8
        self.byte_lanes = self.width // self.byte_size
        self.strb_mask = 2**self.byte_lanes-1

        self.pprot_present = hasattr(self.bus, "pprot")
        self.pstrb_present = hasattr(self.bus, "pstrb")
        self.pslverr_present = hasattr(self.bus, "pslverr")

        self.log.info("APB slave model configuration:")
        self.log.info("  Address width: %d bits", self.address_width)
        self.log.info("  Byte size: %d bits", self.byte_size)
        self.log.info("  Data width: %d bits (%d bytes)", self.width, self.byte_lanes)

        self.log.info("APB slave model signals:")
        for sig in sorted(list(set().union(self.bus._signals, self.bus._optional_signals))):
            if hasattr(bus, sig):
                self.log.info("  %s width: %d bits", sig, len(getattr(bus, sig)))
            else:
                self.log.info("  %s: not present", sig)

        if self.pstrb_present:
            assert self.byte_lanes == len(self.bus.pstrb)
        assert self.byte_lanes * self.byte_size == self.width

        self.bus.pready.setimmediatevalue(False)
        self.bus.prdata.setimmediatevalue(0)
        if self.pslverr_present:
            self.bus.pslverr.setimmediatevalue(0)

        self._run_cr = None

        self._init_reset(reset, reset_active_level)

    async def _write(self, address, data):
        await self.target.write(address, data)

    def _handle_reset(self, state):
        if state:
            self.log.info("Reset asserted")

            self.bus.pready.value = False

            if self._run_cr is not None:
                self._run_cr.kill()
                self._run_cr = None
        else:
            self.log.info("Reset de-asserted")
            if self._run_cr is None:
                self._run_cr = cocotb.start_soon(self._run())

    async def _run(self):
        clock_edge_event = RisingEdge(self.clock)

        self.bus.pready.value = False

        while True:
            await clock_edge_event

            if self.pause:
                continue

            if not int(self.bus.psel.value) or not int(self.bus.penable.value):
                continue

            addr = (int(self.bus.paddr.value) // self.byte_lanes) * self.byte_lanes
            if self.pprot_present:
                prot = AxiProt(int(self.bus.pprot.value))
            else:
                prot = AxiProt.NONSECURE

            pslverr = False

            if (int(self.bus.pwrite.value)):
                data = int(self.bus.pwdata.value)

                if self.pstrb_present:
                    strb = int(self.bus.pstrb.value)
                else:
                    strb = self.strb_mask

                # generate operation list
                offset = 0
                start_offset = None
                write_ops = []

                data = data.to_bytes(self.byte_lanes, 'little')

                if self.log.isEnabledFor(logging.INFO):
                    self.log.info("Write data paddr: 0x%08x pprot: %s pstrb: 0x%02x data: %s",
                            addr, prot, strb, ' '.join((f'{c:02x}' for c in data)))

                for i in range(self.byte_lanes):
                    if strb & (1 << i):
                        if start_offset is None:
                            start_offset = offset
                    else:
                        if start_offset is not None and offset != start_offset:
                            write_ops.append((addr+start_offset, data[start_offset:offset]))
                        start_offset = None

                    offset += 1

                if start_offset is not None and offset != start_offset:
                    write_ops.append((addr+start_offset, data[start_offset:offset]))

                print(write_ops)

                # perform writes
                try:
                    for addr, data in write_ops:
                        await self._write(addr, data)
                except Exception:
                    self.log.warning("Write operation failed")
                    pslverr = True
            else:
                try:
                    data = await self._read(addr, self.byte_lanes)
                except Exception:
                    self.log.warning("Read operation failed")
                    data = bytes(self.byte_lanes)
                    pslverr = True

                if self.log.isEnabledFor(logging.INFO):
                    self.log.info("Read data paddr: 0x%08x pprot: %s data: %s",
                            addr, prot, ' '.join((f'{c:02x}' for c in data)))

                self.bus.prdata.value = int.from_bytes(data, 'little')

            await clock_edge_event
            if self.pslverr_present:
                self.bus.pslverr.value = pslverr
            self.bus.pready.value = True
            await clock_edge_event
            self.bus.pready.value = False
            if self.pslverr_present:
                self.bus.pslverr.value = False


class ApbRam(ApbSlave, Memory):
    def __init__(self, bus, clock, reset=None, reset_active_level=True, size=2**64, mem=None, **kwargs):
        super().__init__(bus, clock, reset, reset_active_level=reset_active_level, size=size, mem=mem, **kwargs)

    async def _write(self, address, data):
        self.write(address % self.size, data)

    async def _read(self, address, length):
        return self.read(address % self.size, length)
