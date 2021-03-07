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
from collections import deque

import cocotb
from cocotb.triggers import RisingEdge, Timer, First, Event
from cocotb.utils import get_sim_time
from cocotb.bus import Bus

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
        self.queue = deque()
        self.queue_sync = Event()

        self.queue_occupancy_bytes = 0
        self.queue_occupancy_frames = 0

        self.width = len(self.bus.tdata)
        self.byte_lanes = 1

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
        self.log.info("  tvalid: %s", "present" if hasattr(self.bus, "tvalid") else "not present")
        self.log.info("  tready: %s", "present" if hasattr(self.bus, "tready") else "not present")
        self.log.info("  tlast: %s", "present" if hasattr(self.bus, "tlast") else "not present")
        if hasattr(self.bus, "tkeep"):
            self.log.info("  tkeep width: %d bits", len(self.bus.tkeep))
        else:
            self.log.info("  tkeep: not present")
        if hasattr(self.bus, "tid"):
            self.log.info("  tid width: %d bits", len(self.bus.tid))
        else:
            self.log.info("  tid: not present")
        if hasattr(self.bus, "tdest"):
            self.log.info("  tdest width: %d bits", len(self.bus.tdest))
        else:
            self.log.info("  tdest: not present")
        if hasattr(self.bus, "tuser"):
            self.log.info("  tuser width: %d bits", len(self.bus.tuser))
        else:
            self.log.info("  tuser: not present")

        if self.byte_lanes * self.byte_size != self.width:
            raise ValueError(f"Bus does not evenly divide into byte lanes "
                f"({self.byte_lanes} * {self.byte_size} != {self.width})")

        self._run_cr = None

        self._init_reset(reset, reset_active_level)

    def count(self):
        return len(self.queue)

    def empty(self):
        return not self.queue

    def clear(self):
        self.queue.clear()
        self.queue_occupancy_bytes = 0
        self.queue_occupancy_frames = 0

    def _handle_reset(self, state):
        if state:
            self.log.info("Reset asserted")
            if self._run_cr is not None:
                self._run_cr.kill()
                self._run_cr = None
        else:
            self.log.info("Reset de-asserted")
            if self._run_cr is None:
                self._run_cr = cocotb.fork(self._run())

        self.active = False

    async def _run(self):
        raise NotImplementedError()


class AxiStreamPause:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.pause = False
        self._pause_generator = None
        self._pause_cr = None

    def set_pause_generator(self, generator=None):
        if self._pause_cr is not None:
            self._pause_cr.kill()
            self._pause_cr = None

        self._pause_generator = generator

        if self._pause_generator is not None:
            self._pause_cr = cocotb.fork(self._run_pause())

    def clear_pause_generator(self):
        self.set_pause_generator(None)

    async def _run_pause(self):
        for val in self._pause_generator:
            self.pause = val
            await RisingEdge(self.clock)


class AxiStreamSource(AxiStreamBase, AxiStreamPause):

    _type = "source"

    _init_x = True

    _valid_init = 0
    _ready_init = None

    async def send(self, frame):
        self.send_nowait(frame)

    def send_nowait(self, frame):
        frame = AxiStreamFrame(frame)
        self.queue_occupancy_bytes += len(frame)
        self.queue_occupancy_frames += 1
        self.queue.append(frame)

    async def write(self, data):
        await self.send(data)

    def write_nowait(self, data):
        self.send_nowait(data)

    def idle(self):
        return self.empty() and not self.active

    async def wait(self):
        while not self.idle():
            await RisingEdge(self.clock)

    def _handle_reset(self, state):
        super()._handle_reset(state)

        self.bus.tdata <= 0
        if hasattr(self.bus, "tvalid"):
            self.bus.tvalid <= 0
        if hasattr(self.bus, "tlast"):
            self.bus.tlast <= 0
        if hasattr(self.bus, "tkeep"):
            self.bus.tkeep <= 0
        if hasattr(self.bus, "tid"):
            self.bus.tid <= 0
        if hasattr(self.bus, "tdest"):
            self.bus.tdest <= 0
        if hasattr(self.bus, "tuser"):
            self.bus.tuser <= 0

    async def _run(self):
        frame = None
        self.active = False

        while True:
            await RisingEdge(self.clock)

            # read handshake signals
            tready_sample = (not hasattr(self.bus, "tready")) or self.bus.tready.value
            tvalid_sample = (not hasattr(self.bus, "tvalid")) or self.bus.tvalid.value

            if (tready_sample and tvalid_sample) or not tvalid_sample:
                if frame is None and self.queue:
                    frame = self.queue.popleft()
                    self.queue_occupancy_bytes -= len(frame)
                    self.queue_occupancy_frames -= 1
                    frame.sim_time_start = get_sim_time()
                    frame.sim_time_end = None
                    self.log.info("TX frame: %s", frame)
                    frame.normalize()
                    self.active = True

                if frame and not self.pause:
                    tdata_val = 0
                    tlast_val = 0
                    tkeep_val = 0
                    tid_val = 0
                    tdest_val = 0
                    tuser_val = 0

                    for offset in range(self.byte_lanes):
                        tdata_val |= (frame.tdata.pop(0) & self.byte_mask) << (offset * self.byte_size)
                        tkeep_val |= (frame.tkeep.pop(0) & 1) << offset
                        tid_val = frame.tid.pop(0)
                        tdest_val = frame.tdest.pop(0)
                        tuser_val = frame.tuser.pop(0)

                        if len(frame.tdata) == 0:
                            tlast_val = 1
                            frame.sim_time_end = get_sim_time()
                            frame.handle_tx_complete()
                            frame = None
                            break

                    self.bus.tdata <= tdata_val
                    if hasattr(self.bus, "tvalid"):
                        self.bus.tvalid <= 1
                    if hasattr(self.bus, "tlast"):
                        self.bus.tlast <= tlast_val
                    if hasattr(self.bus, "tkeep"):
                        self.bus.tkeep <= tkeep_val
                    if hasattr(self.bus, "tid"):
                        self.bus.tid <= tid_val
                    if hasattr(self.bus, "tdest"):
                        self.bus.tdest <= tdest_val
                    if hasattr(self.bus, "tuser"):
                        self.bus.tuser <= tuser_val
                else:
                    if hasattr(self.bus, "tvalid"):
                        self.bus.tvalid <= 0
                    if hasattr(self.bus, "tlast"):
                        self.bus.tlast <= 0
                    self.active = bool(frame)


class AxiStreamMonitor(AxiStreamBase):

    _type = "monitor"

    _init_x = False

    _valid_init = None
    _ready_init = None

    def __init__(self, bus, clock, reset=None, reset_active_level=True,
            byte_size=None, byte_lanes=None, *args, **kwargs):

        super().__init__(bus, clock, reset, reset_active_level, byte_size, byte_lanes, *args, **kwargs)

        self.read_queue = []

    async def recv(self, compact=True):
        while self.empty():
            self.queue_sync.clear()
            await self.queue_sync.wait()
        return self.recv_nowait(compact)

    def recv_nowait(self, compact=True):
        if self.queue:
            frame = self.queue.popleft()
            self.queue_occupancy_bytes -= len(frame)
            self.queue_occupancy_frames -= 1
            if compact:
                frame.compact()
            return frame
        return None

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
        self.queue_sync.clear()
        if timeout:
            await First(self.queue_sync.wait(), Timer(timeout, timeout_unit))
        else:
            await self.queue_sync.wait()

    async def _run(self):
        frame = None
        self.active = False

        while True:
            await RisingEdge(self.clock)

            # read handshake signals
            tready_sample = (not hasattr(self.bus, "tready")) or self.bus.tready.value
            tvalid_sample = (not hasattr(self.bus, "tvalid")) or self.bus.tvalid.value

            if tready_sample and tvalid_sample:
                if frame is None:
                    if self.byte_size == 8:
                        frame = AxiStreamFrame(bytearray(), [], [], [], [])
                    else:
                        frame = AxiStreamFrame([], [], [], [], [])
                    frame.sim_time_start = get_sim_time()

                for offset in range(self.byte_lanes):

                    frame.tdata.append((self.bus.tdata.value.integer >> (offset * self.byte_size)) & self.byte_mask)
                    if hasattr(self.bus, "tkeep"):
                        frame.tkeep.append((self.bus.tkeep.value.integer >> offset) & 1)
                    if hasattr(self.bus, "tid"):
                        frame.tid.append(self.bus.tid.value.integer)
                    if hasattr(self.bus, "tdest"):
                        frame.tdest.append(self.bus.tdest.value.integer)
                    if hasattr(self.bus, "tuser"):
                        frame.tuser.append(self.bus.tuser.value.integer)

                if not hasattr(self.bus, "tlast") or self.bus.tlast.value:
                    frame.sim_time_end = get_sim_time()
                    self.log.info("RX frame: %s", frame)

                    self.queue_occupancy_bytes += len(frame)
                    self.queue_occupancy_frames += 1

                    self.queue.append(frame)
                    self.queue_sync.set()

                    frame = None


class AxiStreamSink(AxiStreamMonitor, AxiStreamPause):

    _type = "sink"

    _init_x = False

    _valid_init = None
    _ready_init = 0

    def __init__(self, bus, clock, reset=None, reset_active_level=True,
            byte_size=None, byte_lanes=None, *args, **kwargs):

        super().__init__(bus, clock, reset, reset_active_level, byte_size, byte_lanes, *args, **kwargs)

        self.queue_occupancy_limit_bytes = -1
        self.queue_occupancy_limit_frames = -1

    def full(self):
        if self.queue_occupancy_limit_bytes > 0 and self.queue_occupancy_bytes > self.queue_occupancy_limit_bytes:
            return True
        elif self.queue_occupancy_limit_frames > 0 and self.queue_occupancy_frames > self.queue_occupancy_limit_frames:
            return True
        else:
            return False

    def _handle_reset(self, state):
        super()._handle_reset(state)

        if hasattr(self.bus, "tready"):
            self.bus.tready <= 0

    async def _run(self):
        frame = None
        self.active = False

        while True:
            await RisingEdge(self.clock)

            # read handshake signals
            tready_sample = (not hasattr(self.bus, "tready")) or self.bus.tready.value
            tvalid_sample = (not hasattr(self.bus, "tvalid")) or self.bus.tvalid.value

            if tready_sample and tvalid_sample:
                if frame is None:
                    if self.byte_size == 8:
                        frame = AxiStreamFrame(bytearray(), [], [], [], [])
                    else:
                        frame = AxiStreamFrame([], [], [], [], [])
                    frame.sim_time_start = get_sim_time()

                for offset in range(self.byte_lanes):

                    frame.tdata.append((self.bus.tdata.value.integer >> (offset * self.byte_size)) & self.byte_mask)
                    if hasattr(self.bus, "tkeep"):
                        frame.tkeep.append((self.bus.tkeep.value.integer >> offset) & 1)
                    if hasattr(self.bus, "tid"):
                        frame.tid.append(self.bus.tid.value.integer)
                    if hasattr(self.bus, "tdest"):
                        frame.tdest.append(self.bus.tdest.value.integer)
                    if hasattr(self.bus, "tuser"):
                        frame.tuser.append(self.bus.tuser.value.integer)

                if not hasattr(self.bus, "tlast") or self.bus.tlast.value:
                    frame.sim_time_end = get_sim_time()
                    self.log.info("RX frame: %s", frame)

                    self.queue_occupancy_bytes += len(frame)
                    self.queue_occupancy_frames += 1

                    self.queue.append(frame)
                    self.queue_sync.set()

                    frame = None

            if hasattr(self.bus, "tready"):
                self.bus.tready <= (not self.full() and not self.pause)
