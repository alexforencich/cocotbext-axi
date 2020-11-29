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

from collections import deque

import cocotb
from cocotb.triggers import RisingEdge, ReadOnly, Timer, First, Event
from cocotb.bus import Bus
from cocotb.log import SimLog

from .version import __version__


class AxiStreamFrame(object):
    def __init__(self, tdata=b'', tkeep=None, tid=None, tdest=None, tuser=None):
        self.tdata = bytearray()
        self.tkeep = None
        self.tid = None
        self.tdest = None
        self.tuser = None

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
            f"{type(self).__name__}(tdata={repr(self.tdata)}, "
            f"tkeep={repr(self.tkeep)}, "
            f"tid={repr(self.tid)}, "
            f"tdest={repr(self.tdest)}, "
            f"tuser={repr(self.tuser)})"
        )

    def __len__(self):
        return len(self.tdata)

    def __iter__(self):
        return self.tdata.__iter__()


class AxiStreamSource(object):

    _signals = ["tdata"]
    _optional_signals = ["tvalid", "tready", "tlast", "tkeep", "tid", "tdest", "tuser"]

    def __init__(self, entity, name, clock, reset=None, *args, **kwargs):
        self.log = SimLog("cocotb.%s.%s" % (entity._name, name))
        self.entity = entity
        self.clock = clock
        self.reset = reset
        self.bus = Bus(self.entity, name, self._signals, optional_signals=self._optional_signals, **kwargs)

        self.log.info("AXI stream source")
        self.log.info("cocotbext-axi version %s", __version__)
        self.log.info("Copyright (c) 2020 Alex Forencich")
        self.log.info("https://github.com/alexforencich/cocotbext-axi")

        super().__init__(*args, **kwargs)

        self.active = False
        self.queue = deque()

        self.pause = False
        self._pause_generator = None
        self._pause_cr = None

        self.queue_occupancy_bytes = 0
        self.queue_occupancy_frames = 0

        self.width = len(self.bus.tdata)
        self.byte_width = 1

        self.reset = reset

        self.bus.tdata.setimmediatevalue(0)
        if hasattr(self.bus, "tvalid"):
            self.bus.tvalid.setimmediatevalue(0)
        if hasattr(self.bus, "tlast"):
            self.bus.tlast.setimmediatevalue(0)
        if hasattr(self.bus, "tkeep"):
            self.byte_width = len(self.bus.tkeep)
            self.bus.tkeep.setimmediatevalue(0)
        if hasattr(self.bus, "tid"):
            self.bus.tid.setimmediatevalue(0)
        if hasattr(self.bus, "tdest"):
            self.bus.tdest.setimmediatevalue(0)
        if hasattr(self.bus, "tuser"):
            self.bus.tuser.setimmediatevalue(0)

        self.byte_size = self.width // self.byte_width
        self.byte_mask = 2**self.byte_size-1

        self.log.info("AXI stream source configuration:")
        self.log.info("  Byte size: %d bits", self.byte_size)
        self.log.info("  Data width: %d bits (%d bytes)", self.width, self.byte_width)
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

        cocotb.fork(self._run())

    def send(self, frame):
        frame = AxiStreamFrame(frame)
        self.queue_occupancy_bytes += len(frame)
        self.queue_occupancy_frames += 1
        self.queue.append(frame)

    def write(self, data):
        self.send(data)

    def count(self):
        return len(self.queue)

    def empty(self):
        return not self.queue

    def idle(self):
        return self.empty() and not self.active

    async def wait(self):
        while not self.idle():
            await RisingEdge(self.clock)

    def set_pause_generator(self, generator=None):
        if self._pause_cr is not None:
            self._pause_cr.kill()
            self._pause_cr = None

        self._pause_generator = generator

        if self._pause_generator is not None:
            self._pause_cr = cocotb.fork(self._run_pause())

    def clear_pause_generator(self):
        self.set_pause_generator(None)

    async def _run(self):
        frame = None
        self.active = False

        while True:
            await ReadOnly()

            # read handshake signals
            tready_sample = (not hasattr(self.bus, "tready")) or self.bus.tready.value
            tvalid_sample = (not hasattr(self.bus, "tvalid")) or self.bus.tvalid.value

            if self.reset is not None and self.reset.value:
                await RisingEdge(self.clock)
                frame = None
                self.active = False
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
                continue

            await RisingEdge(self.clock)

            if (tready_sample and tvalid_sample) or not tvalid_sample:
                if frame is None and self.queue:
                    frame = self.queue.popleft()
                    self.queue_occupancy_bytes -= len(frame)
                    self.queue_occupancy_frames -= 1
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

                    for offset in range(self.byte_width):
                        tdata_val |= (frame.tdata.pop(0) & self.byte_mask) << (offset * self.byte_size)
                        tkeep_val |= (frame.tkeep.pop(0) & 1) << offset
                        tid_val = frame.tid.pop(0)
                        tdest_val = frame.tdest.pop(0)
                        tuser_val = frame.tuser.pop(0)

                        if len(frame.tdata) == 0:
                            tlast_val = 1
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

    async def _run_pause(self):
        for val in self._pause_generator:
            self.pause = val
            await RisingEdge(self.clock)


class AxiStreamSink(object):

    _signals = ["tdata"]
    _optional_signals = ["tvalid", "tready", "tlast", "tkeep", "tid", "tdest", "tuser"]

    def __init__(self, entity, name, clock, reset=None, *args, **kwargs):
        self.log = SimLog("cocotb.%s.%s" % (entity._name, name))
        self.entity = entity
        self.clock = clock
        self.reset = reset
        self.bus = Bus(self.entity, name, self._signals, optional_signals=self._optional_signals, **kwargs)

        self.log.info("AXI stream sink")
        self.log.info("cocotbext-axi version %s", __version__)
        self.log.info("Copyright (c) 2020 Alex Forencich")
        self.log.info("https://github.com/alexforencich/cocotbext-axi")

        super().__init__(*args, **kwargs)

        self.active = False
        self.queue = deque()
        self.sync = Event()
        self.read_queue = []

        self.pause = False
        self._pause_generator = None
        self._pause_cr = None

        self.queue_occupancy_bytes = 0
        self.queue_occupancy_frames = 0
        self.queue_occupancy_limit_bytes = None
        self.queue_occupancy_limit_frames = None

        self.width = len(self.bus.tdata)
        self.byte_width = 1

        self.reset = reset

        if hasattr(self.bus, "tready"):
            self.bus.tready.setimmediatevalue(0)
        if hasattr(self.bus, "tkeep"):
            self.byte_width = len(self.bus.tkeep)

        self.byte_size = self.width // self.byte_width
        self.byte_mask = 2**self.byte_size-1

        self.log.info("AXI stream sink configuration:")
        self.log.info("  Byte size: %d bits", self.byte_size)
        self.log.info("  Data width: %d bits (%d bytes)", self.width, self.byte_width)
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

        cocotb.fork(self._run())

    def recv(self, compact=True):
        if self.queue:
            frame = self.queue.popleft()
            self.queue_occupancy_bytes -= len(frame)
            self.queue_occupancy_frames -= 1
            if compact:
                frame.compact()
            return frame
        return None

    def read(self, count=-1):
        while True:
            frame = self.recv(compact=True)
            if frame is None:
                break
            self.read_queue.extend(frame.tdata)
        if count < 0:
            count = len(self.read_queue)
        data = self.read_queue[:count]
        del self.read_queue[:count]
        return data

    def count(self):
        return len(self.queue)

    def empty(self):
        return not self.queue

    def full(self):
        if self.queue_occupancy_limit_bytes and self.queue_occupancy_bytes > self.queue_occupancy_limit_bytes:
            return True
        elif self.queue_occupancy_limit_frames and self.queue_occupancy_frames > self.queue_occupancy_limit_frames:
            return True
        else:
            return False

    def idle(self):
        return not self.active

    async def wait(self, timeout=0, timeout_unit='ns'):
        if not self.empty():
            return
        self.sync.clear()
        if timeout:
            await First(self.sync.wait(), Timer(timeout, timeout_unit))
        else:
            await self.sync.wait()

    def set_pause_generator(self, generator=None):
        if self._pause_cr is not None:
            self._pause_cr.kill()
            self._pause_cr = None

        self._pause_generator = generator

        if self._pause_generator is not None:
            self._pause_cr = cocotb.fork(self._run_pause())

    def clear_pause_generator(self):
        self.set_pause_generator(None)

    async def _run(self):
        frame = AxiStreamFrame([], [], [], [], [])
        self.active = False

        while True:
            await ReadOnly()

            # read handshake signals
            tready_sample = (not hasattr(self.bus, "tready")) or self.bus.tready.value
            tvalid_sample = (not hasattr(self.bus, "tvalid")) or self.bus.tvalid.value

            if self.reset is not None and self.reset.value:
                await RisingEdge(self.clock)
                frame = AxiStreamFrame([], [], [], [], [])
                self.active = False
                if hasattr(self.bus, "tready"):
                    self.bus.tready <= 0
                continue

            if tready_sample and tvalid_sample:
                for offset in range(self.byte_width):

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
                    if self.byte_size == 8:
                        frame.tdata = bytearray(frame.tdata)

                    self.log.info("RX frame: %s", frame)

                    self.queue_occupancy_bytes += len(frame)
                    self.queue_occupancy_frames += 1

                    self.queue.append(frame)
                    self.sync.set()

                    frame = AxiStreamFrame([], [], [], [], [])

            await RisingEdge(self.clock)

            if hasattr(self.bus, "tready"):
                self.bus.tready <= (not self.full() and not self.pause)

    async def _run_pause(self):
        for val in self._pause_generator:
            self.pause = val
            await RisingEdge(self.clock)


class AxiStreamMonitor(object):

    _signals = ["tdata"]
    _optional_signals = ["tvalid", "tready", "tlast", "tkeep", "tid", "tdest", "tuser"]

    def __init__(self, entity, name, clock, reset=None, *args, **kwargs):
        self.log = SimLog("cocotb.%s.%s" % (entity._name, name))
        self.entity = entity
        self.clock = clock
        self.reset = reset
        self.bus = Bus(self.entity, name, self._signals, optional_signals=self._optional_signals, **kwargs)

        self.log.info("AXI stream monitor")
        self.log.info("cocotbext-axi version %s", __version__)
        self.log.info("Copyright (c) 2020 Alex Forencich")
        self.log.info("https://github.com/alexforencich/cocotbext-axi")

        super().__init__(*args, **kwargs)

        self.active = False
        self.queue = deque()
        self.sync = Event()
        self.read_queue = []

        self.queue_occupancy_bytes = 0
        self.queue_occupancy_frames = 0

        self.width = len(self.bus.tdata)
        self.byte_width = 1

        self.reset = reset

        if hasattr(self.bus, "tkeep"):
            self.byte_width = len(self.bus.tkeep)

        self.byte_size = self.width // self.byte_width
        self.byte_mask = 2**self.byte_size-1

        self.log.info("AXI stream monitor configuration:")
        self.log.info("  Byte size: %d bits", self.byte_size)
        self.log.info("  Data width: %d bits (%d bytes)", self.width, self.byte_width)
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

        cocotb.fork(self._run())

    def recv(self, compact=True):
        if self.queue:
            frame = self.queue.popleft()
            self.queue_occupancy_bytes -= len(frame)
            self.queue_occupancy_frames -= 1
            if compact:
                frame.compact()
            return frame
        return None

    def read(self, count=-1):
        while True:
            frame = self.recv(compact=True)
            if frame is None:
                break
            self.read_queue.extend(frame.tdata)
        if count < 0:
            count = len(self.read_queue)
        data = self.read_queue[:count]
        del self.read_queue[:count]
        return data

    def count(self):
        return len(self.queue)

    def empty(self):
        return not self.queue

    def idle(self):
        return not self.active

    async def wait(self, timeout=0, timeout_unit='ns'):
        if not self.empty():
            return
        self.sync.clear()
        if timeout:
            await First(self.sync.wait(), Timer(timeout, timeout_unit))
        else:
            await self.sync.wait()

    async def _run(self):
        frame = AxiStreamFrame([], [], [], [], [])
        self.active = False

        while True:
            await ReadOnly()

            # read handshake signals
            tready_sample = (not hasattr(self.bus, "tready")) or self.bus.tready.value
            tvalid_sample = (not hasattr(self.bus, "tvalid")) or self.bus.tvalid.value

            if self.reset is not None and self.reset.value:
                await RisingEdge(self.clock)
                frame = AxiStreamFrame([], [], [], [], [])
                self.active = False
                continue

            if tready_sample and tvalid_sample:
                for offset in range(self.byte_width):

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
                    if self.byte_size == 8:
                        frame.tdata = bytearray(frame.tdata)

                    self.log.info("RX frame: %s", frame)

                    self.queue.append(frame)
                    self.sync.set()

                    frame = AxiStreamFrame([], [], [], [], [])

            await RisingEdge(self.clock)
