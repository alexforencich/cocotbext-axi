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

import cocotb
from cocotb.queue import Queue, QueueFull
from cocotb.triggers import RisingEdge, Timer, First, Event
from cocotb.utils import get_sim_time
from cocotb_bus.bus import Bus

from .version import __version__
from .reset import Reset


class AxiStreamFrame:
    def __init__(self, tdata=b'', tkeep=None, tid=None, tdest=None, tuser=None, tx_complete=None):
        self.tdata = bytearray()
        self.tkeep = None
        self.tid = None
        self.tdest = None
        self.tuser = None
        self.sim_time_start = None
        self.sim_time_end = None
        self.tx_complete = None

        if type(tdata) is AxiStreamFrame:
            if type(tdata.tdata) is bytearray:
                self.tdata = bytearray(tdata.tdata)
            else:
                self.tdata = list(tdata.tdata)
            if tdata.tkeep is not None:
                self.tkeep = list(tdata.tkeep)
            if tdata.tid is not None:
                if type(tdata.tid) in (int, bool):
                    self.tid = tdata.tid
                else:
                    self.tid = list(tdata.tid)
            if tdata.tdest is not None:
                if type(tdata.tdest) in (int, bool):
                    self.tdest = tdata.tdest
                else:
                    self.tdest = list(tdata.tdest)
            if tdata.tuser is not None:
                if type(tdata.tuser) in (int, bool):
                    self.tuser = tdata.tuser
                else:
                    self.tuser = list(tdata.tuser)
            self.sim_time_start = tdata.sim_time_start
            self.sim_time_end = tdata.sim_time_end
            self.tx_complete = tdata.tx_complete
        elif type(tdata) in (bytes, bytearray):
            self.tdata = bytearray(tdata)
            self.tkeep = tkeep
            self.tid = tid
            self.tdest = tdest
            self.tuser = tuser
        else:
            self.tdata = list(tdata)
            self.tkeep = tkeep
            self.tid = tid
            self.tdest = tdest
            self.tuser = tuser

        if tx_complete is not None:
            self.tx_complete = tx_complete

    def normalize(self):
        # normalize all sideband signals to the same size as tdata
        n = len(self.tdata)

        if self.tkeep is not None:
            self.tkeep = self.tkeep[:n] + [self.tkeep[-1]]*(n-len(self.tkeep))
        else:
            self.tkeep = [1]*n

        if self.tid is not None:
            if type(self.tid) in (int, bool):
                self.tid = [self.tid]*n
            else:
                self.tid = self.tid[:n] + [self.tid[-1]]*(n-len(self.tid))
        else:
            self.tid = [0]*n

        if self.tdest is not None:
            if type(self.tdest) in (int, bool):
                self.tdest = [self.tdest]*n
            else:
                self.tdest = self.tdest[:n] + [self.tdest[-1]]*(n-len(self.tdest))
        else:
            self.tdest = [0]*n

        if self.tuser is not None:
            if type(self.tuser) in (int, bool):
                self.tuser = [self.tuser]*n
            else:
                self.tuser = self.tuser[:n] + [self.tuser[-1]]*(n-len(self.tuser))
        else:
            self.tuser = [0]*n

    def compact(self):
        if len(self.tkeep):
            # remove tkeep=0 bytes
            for k in range(len(self.tdata)-1, -1, -1):
                if not self.tkeep[k]:
                    if k < len(self.tdata):
                        del self.tdata[k]
                    if k < len(self.tkeep):
                        del self.tkeep[k]
                    if k < len(self.tid):
                        del self.tid[k]
                    if k < len(self.tdest):
                        del self.tdest[k]
                    if k < len(self.tuser):
                        del self.tuser[k]

        # remove tkeep
        self.tkeep = None

        # clean up other sideband signals
        # either remove or consolidate if values are identical
        if len(self.tid) == 0:
            self.tid = None
        elif all(self.tid[0] == i for i in self.tid):
            self.tid = self.tid[0]

        if len(self.tdest) == 0:
            self.tdest = None
        elif all(self.tdest[0] == i for i in self.tdest):
            self.tdest = self.tdest[0]

        if len(self.tuser) == 0:
            self.tuser = None
        elif all(self.tuser[0] == i for i in self.tuser):
            self.tuser = self.tuser[0]

    def handle_tx_complete(self):
        if isinstance(self.tx_complete, Event):
            self.tx_complete.set(self)
        elif callable(self.tx_complete):
            self.tx_complete(self)

    def __eq__(self, other):
        if not isinstance(other, AxiStreamFrame):
            return False

        if self.tdata != other.tdata:
            return False

        if self.tkeep is not None and other.tkeep is not None:
            if self.tkeep != other.tkeep:
                return False

        if self.tid is not None and other.tid is not None:
            if type(self.tid) in (int, bool) and type(other.tid) is list:
                for k in other.tid:
                    if self.tid != k:
                        return False
            elif type(other.tid) in (int, bool) and type(self.tid) is list:
                for k in self.tid:
                    if other.tid != k:
                        return False
            elif self.tid != other.tid:
                return False

        if self.tdest is not None and other.tdest is not None:
            if type(self.tdest) in (int, bool) and type(other.tdest) is list:
                for k in other.tdest:
                    if self.tdest != k:
                        return False
            elif type(other.tdest) in (int, bool) and type(self.tdest) is list:
                for k in self.tdest:
                    if other.tdest != k:
                        return False
            elif self.tdest != other.tdest:
                return False

        if self.tuser is not None and other.tuser is not None:
            if type(self.tuser) in (int, bool) and type(other.tuser) is list:
                for k in other.tuser:
                    if self.tuser != k:
                        return False
            elif type(other.tuser) in (int, bool) and type(self.tuser) is list:
                for k in self.tuser:
                    if other.tuser != k:
                        return False
            elif self.tuser != other.tuser:
                return False

        return True

    def __repr__(self):
        return (
            f"{type(self).__name__}(tdata={self.tdata!r}, "
            f"tkeep={self.tkeep!r}, "
            f"tid={self.tid!r}, "
            f"tdest={self.tdest!r}, "
            f"tuser={self.tuser!r}, "
            f"sim_time_start={self.sim_time_start!r}, "
            f"sim_time_end={self.sim_time_end!r})"
        )

    def __len__(self):
        return len(self.tdata)

    def __iter__(self):
        return self.tdata.__iter__()

    def __bytes__(self):
        return bytes(self.tdata)


class AxiStreamBus(Bus):

    _signals = ["tdata"]
    _optional_signals = ["tvalid", "tready", "tlast", "tkeep", "tid", "tdest", "tuser"]

    def __init__(self, entity=None, prefix=None, **kwargs):
        super().__init__(entity, prefix, self._signals, optional_signals=self._optional_signals, **kwargs)

    @classmethod
    def from_entity(cls, entity, **kwargs):
        return cls(entity, **kwargs)

    @classmethod
    def from_prefix(cls, entity, prefix, **kwargs):
        return cls(entity, prefix, **kwargs)


class AxiStreamBase(Reset):

    _signals = ["tdata"]
    _optional_signals = ["tvalid", "tready", "tlast", "tkeep", "tid", "tdest", "tuser"]

    _type = "base"

    _init_x = False

    _valid_init = None
    _ready_init = None

    def __init__(self, bus, clock, reset=None, reset_active_level=True,
            byte_size=None, byte_lanes=None, *args, **kwargs):

        self.bus = bus
        self.clock = clock
        self.reset = reset
        self.log = logging.getLogger(f"cocotb.{bus._entity._name}.{bus._name}")

        self.log.info("AXI stream %s", self._type)
        self.log.info("cocotbext-axi version %s", __version__)
        self.log.info("Copyright (c) 2020 Alex Forencich")
        self.log.info("https://github.com/alexforencich/cocotbext-axi")

        super().__init__(*args, **kwargs)

        self.active = False
        self.queue = Queue()
        self.dequeue_event = Event()
        self.current_frame = None
        self.idle_event = Event()
        self.idle_event.set()
        self.active_event = Event()
        self.wake_event = Event()

        self.queue_occupancy_bytes = 0
        self.queue_occupancy_frames = 0

        self.width = len(self.bus.tdata)
        self.byte_lanes = self.width // 8

        if self._valid_init is not None and hasattr(self.bus, "tvalid"):
            self.bus.tvalid.setimmediatevalue(self._valid_init)
        if self._ready_init is not None and hasattr(self.bus, "tready"):
            self.bus.tready.setimmediatevalue(self._ready_init)

        for sig in self._signals+self._optional_signals:
            if hasattr(self.bus, sig):
                if self._init_x and sig not in ("tvalid", "tready"):
                    v = getattr(self.bus, sig).value
                    v.binstr = 'x'*len(v)
                    getattr(self.bus, sig).setimmediatevalue(v)

        if hasattr(self.bus, "tkeep"):
            self.byte_lanes = len(self.bus.tkeep)
            if byte_size is not None or byte_lanes is not None:
                raise ValueError("Cannot specify byte_size or byte_lanes if tkeep is connected")
        else:
            if byte_lanes is not None:
                self.byte_lanes = byte_lanes
                if byte_size is not None:
                    raise ValueError("Cannot specify both byte_size and byte_lanes")
            elif byte_size is not None:
                self.byte_lanes = self.width // byte_size

        self.byte_size = self.width // self.byte_lanes
        self.byte_mask = 2**self.byte_size-1

        self.log.info("AXI stream %s configuration:", self._type)
        self.log.info("  Byte size: %d bits", self.byte_size)
        self.log.info("  Data width: %d bits (%d bytes)", self.width, self.byte_lanes)

        self.log.info("AXI stream %s signals:", self._type)
        for sig in sorted(list(set().union(self.bus._signals, self.bus._optional_signals))):
            if hasattr(self.bus, sig):
                self.log.info("  %s width: %d bits", sig, len(getattr(self.bus, sig)))
            else:
                self.log.info("  %s: not present", sig)

        if self.byte_lanes * self.byte_size != self.width:
            raise ValueError(f"Bus does not evenly divide into byte lanes "
                f"({self.byte_lanes} * {self.byte_size} != {self.width})")

        self._run_cr = None

        self._init_reset(reset, reset_active_level)

    def count(self):
        return self.queue.qsize()

    def empty(self):
        return self.queue.empty()

    def clear(self):
        while not self.queue.empty():
            frame = self.queue.get_nowait()
            frame.sim_time_end = None
            frame.handle_tx_complete()
        self.dequeue_event.set()
        self.idle_event.set()
        self.active_event.clear()
        self.queue_occupancy_bytes = 0
        self.queue_occupancy_frames = 0

    def _handle_reset(self, state):
        if state:
            self.log.info("Reset asserted")
            if self._run_cr is not None:
                self._run_cr.kill()
                self._run_cr = None

            self.active = False

            if self.queue.empty():
                self.idle_event.set()
        else:
            self.log.info("Reset de-asserted")
            if self._run_cr is None:
                self._run_cr = cocotb.start_soon(self._run())

    async def _run(self):
        raise NotImplementedError()


class AxiStreamPause:
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


class AxiStreamSource(AxiStreamBase, AxiStreamPause):

    _type = "source"

    _init_x = True

    _valid_init = 0
    _ready_init = None

    def __init__(self, bus, clock, reset=None, reset_active_level=True,
            byte_size=None, byte_lanes=None, *args, **kwargs):

        super().__init__(bus, clock, reset, reset_active_level, byte_size, byte_lanes, *args, **kwargs)

        self.queue_occupancy_limit_bytes = -1
        self.queue_occupancy_limit_frames = -1

    async def send(self, frame):
        while self.full():
            self.dequeue_event.clear()
            await self.dequeue_event.wait()
        frame = AxiStreamFrame(frame)
        await self.queue.put(frame)
        self.idle_event.clear()
        self.active_event.set()
        self.queue_occupancy_bytes += len(frame)
        self.queue_occupancy_frames += 1

    def send_nowait(self, frame):
        if self.full():
            raise QueueFull()
        frame = AxiStreamFrame(frame)
        self.queue.put_nowait(frame)
        self.idle_event.clear()
        self.active_event.set()
        self.queue_occupancy_bytes += len(frame)
        self.queue_occupancy_frames += 1

    async def write(self, data):
        await self.send(data)

    def write_nowait(self, data):
        self.send_nowait(data)

    def full(self):
        if self.queue_occupancy_limit_bytes > 0 and self.queue_occupancy_bytes > self.queue_occupancy_limit_bytes:
            return True
        elif self.queue_occupancy_limit_frames > 0 and self.queue_occupancy_frames > self.queue_occupancy_limit_frames:
            return True
        else:
            return False

    def idle(self):
        return self.empty() and not self.active

    async def wait(self):
        await self.idle_event.wait()

    def _handle_reset(self, state):
        super()._handle_reset(state)

        if state:
            self.bus.tdata.value = 0
            if hasattr(self.bus, "tvalid"):
                self.bus.tvalid.value = 0
            if hasattr(self.bus, "tlast"):
                self.bus.tlast.value = 0
            if hasattr(self.bus, "tkeep"):
                self.bus.tkeep.value = 0
            if hasattr(self.bus, "tid"):
                self.bus.tid.value = 0
            if hasattr(self.bus, "tdest"):
                self.bus.tdest.value = 0
            if hasattr(self.bus, "tuser"):
                self.bus.tuser.value = 0

            if self.current_frame:
                self.log.warning("Flushed transmit frame during reset: %s", self.current_frame)
                self.current_frame.handle_tx_complete()
                self.current_frame = None

    async def _run(self):
        frame = None
        frame_offset = 0
        self.active = False

        has_tready = hasattr(self.bus, "tready")
        has_tvalid = hasattr(self.bus, "tvalid")
        has_tlast = hasattr(self.bus, "tlast")
        has_tkeep = hasattr(self.bus, "tkeep")
        has_tid = hasattr(self.bus, "tid")
        has_tdest = hasattr(self.bus, "tdest")
        has_tuser = hasattr(self.bus, "tuser")

        clock_edge_event = RisingEdge(self.clock)

        while True:
            await clock_edge_event

            # read handshake signals
            tready_sample = (not has_tready) or self.bus.tready.value
            tvalid_sample = (not has_tvalid) or self.bus.tvalid.value

            if (tready_sample and tvalid_sample) or not tvalid_sample:
                if not frame and not self.queue.empty():
                    frame = self.queue.get_nowait()
                    self.dequeue_event.set()
                    self.queue_occupancy_bytes -= len(frame)
                    self.queue_occupancy_frames -= 1
                    self.current_frame = frame
                    frame.sim_time_start = get_sim_time()
                    frame.sim_time_end = None
                    self.log.info("TX frame: %s", frame)
                    frame.normalize()
                    self.active = True
                    frame_offset = 0

                if frame and not self.pause:
                    tdata_val = 0
                    tlast_val = 0
                    tkeep_val = 0
                    tid_val = 0
                    tdest_val = 0
                    tuser_val = 0

                    for offset in range(self.byte_lanes):
                        tdata_val |= (frame.tdata[frame_offset] & self.byte_mask) << (offset * self.byte_size)
                        tkeep_val |= (frame.tkeep[frame_offset] & 1) << offset
                        tid_val = frame.tid[frame_offset]
                        tdest_val = frame.tdest[frame_offset]
                        tuser_val = frame.tuser[frame_offset]
                        frame_offset += 1

                        if frame_offset >= len(frame.tdata):
                            tlast_val = 1
                            frame.sim_time_end = get_sim_time()
                            frame.handle_tx_complete()
                            frame = None
                            self.current_frame = None
                            break

                    self.bus.tdata.value = tdata_val
                    if has_tvalid:
                        self.bus.tvalid.value = 1
                    if has_tlast:
                        self.bus.tlast.value = tlast_val
                    if has_tkeep:
                        self.bus.tkeep.value = tkeep_val
                    if has_tid:
                        self.bus.tid.value = tid_val
                    if has_tdest:
                        self.bus.tdest.value = tdest_val
                    if has_tuser:
                        self.bus.tuser.value = tuser_val
                else:
                    if has_tvalid:
                        self.bus.tvalid.value = 0
                    if has_tlast:
                        self.bus.tlast.value = 0
                    self.active = bool(frame)
                    if not frame and self.queue.empty():
                        self.idle_event.set()
                        self.active_event.clear()

                        await self.active_event.wait()


class AxiStreamMonitor(AxiStreamBase):

    _type = "monitor"

    _init_x = False

    _valid_init = None
    _ready_init = None

    def __init__(self, bus, clock, reset=None, reset_active_level=True,
            byte_size=None, byte_lanes=None, *args, **kwargs):

        super().__init__(bus, clock, reset, reset_active_level, byte_size, byte_lanes, *args, **kwargs)

        self.read_queue = []

        if hasattr(self.bus, "tvalid"):
            cocotb.start_soon(self._run_tvalid_monitor())
        if hasattr(self.bus, "tready"):
            cocotb.start_soon(self._run_tready_monitor())

    def _dequeue(self, frame):
        pass

    def _recv(self, frame, compact=True):
        if self.queue.empty():
            self.active_event.clear()
        self.queue_occupancy_bytes -= len(frame)
        self.queue_occupancy_frames -= 1
        self._dequeue(frame)
        if compact:
            frame.compact()
        return frame

    async def recv(self, compact=True):
        frame = await self.queue.get()
        return self._recv(frame, compact)

    def recv_nowait(self, compact=True):
        frame = self.queue.get_nowait()
        return self._recv(frame, compact)

    async def read(self, count=-1):
        while not self.read_queue:
            frame = await self.recv(compact=True)
            self.read_queue.extend(frame.tdata)
        return self.read_nowait(count)

    def read_nowait(self, count=-1):
        while not self.empty():
            frame = self.recv_nowait(compact=True)
            self.read_queue.extend(frame.tdata)
        if count < 0:
            count = len(self.read_queue)
        data = self.read_queue[:count]
        del self.read_queue[:count]
        return data

    def idle(self):
        return not self.active

    async def wait(self, timeout=0, timeout_unit='ns'):
        if not self.empty():
            return
        if timeout:
            await First(self.active_event.wait(), Timer(timeout, timeout_unit))
        else:
            await self.active_event.wait()

    async def _run_tvalid_monitor(self):
        event = RisingEdge(self.bus.tvalid)

        while True:
            await event
            self.wake_event.set()

    async def _run_tready_monitor(self):
        event = RisingEdge(self.bus.tready)

        while True:
            await event
            self.wake_event.set()

    async def _run(self):
        frame = None
        self.active = False

        has_tready = hasattr(self.bus, "tready")
        has_tvalid = hasattr(self.bus, "tvalid")
        has_tlast = hasattr(self.bus, "tlast")
        has_tkeep = hasattr(self.bus, "tkeep")
        has_tid = hasattr(self.bus, "tid")
        has_tdest = hasattr(self.bus, "tdest")
        has_tuser = hasattr(self.bus, "tuser")

        clock_edge_event = RisingEdge(self.clock)

        wake_event = self.wake_event.wait()

        while True:
            await clock_edge_event

            # read handshake signals
            tready_sample = (not has_tready) or self.bus.tready.value
            tvalid_sample = (not has_tvalid) or self.bus.tvalid.value

            if tready_sample and tvalid_sample:
                if not frame:
                    if self.byte_size == 8:
                        frame = AxiStreamFrame(bytearray(), [], [], [], [])
                    else:
                        frame = AxiStreamFrame([], [], [], [], [])
                    frame.sim_time_start = get_sim_time()
                    self.active = True

                for offset in range(self.byte_lanes):
                    frame.tdata.append((self.bus.tdata.value.integer >> (offset * self.byte_size)) & self.byte_mask)
                    if has_tkeep:
                        frame.tkeep.append((self.bus.tkeep.value.integer >> offset) & 1)
                    if has_tid:
                        frame.tid.append(self.bus.tid.value.integer)
                    if has_tdest:
                        frame.tdest.append(self.bus.tdest.value.integer)
                    if has_tuser:
                        frame.tuser.append(self.bus.tuser.value.integer)

                if not has_tlast or self.bus.tlast.value:
                    frame.sim_time_end = get_sim_time()
                    self.log.info("RX frame: %s", frame)

                    self.queue_occupancy_bytes += len(frame)
                    self.queue_occupancy_frames += 1

                    self.queue.put_nowait(frame)
                    self.active_event.set()

                    frame = None
            else:
                self.active = bool(frame)

                self.wake_event.clear()
                await wake_event


class AxiStreamSink(AxiStreamMonitor, AxiStreamPause):

    _type = "sink"

    _init_x = False

    _valid_init = None
    _ready_init = 0

    def __init__(self, bus, clock, reset=None, reset_active_level=True,
            byte_size=None, byte_lanes=None, *args, **kwargs):

        self.queue_occupancy_limit_bytes = -1
        self.queue_occupancy_limit_frames = -1

        super().__init__(bus, clock, reset, reset_active_level, byte_size, byte_lanes, *args, **kwargs)

    def full(self):
        if self.queue_occupancy_limit_bytes > 0 and self.queue_occupancy_bytes > self.queue_occupancy_limit_bytes:
            return True
        elif self.queue_occupancy_limit_frames > 0 and self.queue_occupancy_frames > self.queue_occupancy_limit_frames:
            return True
        else:
            return False

    def _handle_reset(self, state):
        super()._handle_reset(state)

        if state:
            if hasattr(self.bus, "tready"):
                self.bus.tready.value = 0

    def _pause_update(self, val):
        self.wake_event.set()

    def _dequeue(self, frame):
        self.wake_event.set()

    async def _run(self):
        frame = None
        self.active = False

        has_tready = hasattr(self.bus, "tready")
        has_tvalid = hasattr(self.bus, "tvalid")
        has_tlast = hasattr(self.bus, "tlast")
        has_tkeep = hasattr(self.bus, "tkeep")
        has_tid = hasattr(self.bus, "tid")
        has_tdest = hasattr(self.bus, "tdest")
        has_tuser = hasattr(self.bus, "tuser")

        clock_edge_event = RisingEdge(self.clock)

        wake_event = self.wake_event.wait()

        while True:
            pause_sample = self.pause

            await clock_edge_event

            # read handshake signals
            tready_sample = (not has_tready) or self.bus.tready.value
            tvalid_sample = (not has_tvalid) or self.bus.tvalid.value

            if tready_sample and tvalid_sample:
                if not frame:
                    if self.byte_size == 8:
                        frame = AxiStreamFrame(bytearray(), [], [], [], [])
                    else:
                        frame = AxiStreamFrame([], [], [], [], [])
                    frame.sim_time_start = get_sim_time()
                    self.active = True

                for offset in range(self.byte_lanes):
                    frame.tdata.append((self.bus.tdata.value.integer >> (offset * self.byte_size)) & self.byte_mask)
                    if has_tkeep:
                        frame.tkeep.append((self.bus.tkeep.value.integer >> offset) & 1)
                    if has_tid:
                        frame.tid.append(self.bus.tid.value.integer)
                    if has_tdest:
                        frame.tdest.append(self.bus.tdest.value.integer)
                    if has_tuser:
                        frame.tuser.append(self.bus.tuser.value.integer)

                if not has_tlast or self.bus.tlast.value:
                    frame.sim_time_end = get_sim_time()
                    self.log.info("RX frame: %s", frame)

                    self.queue_occupancy_bytes += len(frame)
                    self.queue_occupancy_frames += 1

                    self.queue.put_nowait(frame)
                    self.active_event.set()

                    frame = None
            else:
                self.active = bool(frame)

            if has_tready:
                self.bus.tready.value = (not self.full() and not pause_sample)

            if not tvalid_sample or (self.pause and pause_sample) or self.full():
                self.wake_event.clear()
                await wake_event
