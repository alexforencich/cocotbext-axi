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
from cocotb.triggers import RisingEdge, Event, First, Timer
from cocotb_bus.bus import Bus

from .reset import Reset


class StreamBus(Bus):

    _signals = ["data"]
    _optional_signals = []

    def __init__(self, entity=None, prefix=None, **kwargs):
        super().__init__(entity, prefix, self._signals, optional_signals=self._optional_signals, **kwargs)

    @classmethod
    def from_entity(cls, entity, **kwargs):
        return cls(entity, **kwargs)

    @classmethod
    def from_prefix(cls, entity, prefix, **kwargs):
        return cls(entity, prefix, **kwargs)


class StreamTransaction:

    _signals = ["data"]

    def __init__(self, *args, **kwargs):
        for sig in self._signals:
            if sig in kwargs:
                setattr(self, sig, kwargs[sig])
                del kwargs[sig]
            else:
                setattr(self, sig, 0)

        super().__init__(*args, **kwargs)

    def __repr__(self):
        return f"{type(self).__name__}({', '.join(f'{s}={int(getattr(self, s))}' for s in self._signals)})"


class StreamBase(Reset):

    _signals = ["data", "valid", "ready"]
    _optional_signals = []

    _signal_widths = {"valid": 1, "ready": 1}

    _init_x = False

    _valid_signal = "valid"
    _valid_init = None
    _ready_signal = "ready"
    _ready_init = None

    _transaction_obj = StreamTransaction
    _bus_obj = StreamBus

    def __init__(self, bus, clock, reset=None, reset_active_level=True, *args, **kwargs):
        self.bus = bus
        self.clock = clock
        self.reset = reset
        self.log = logging.getLogger(f"cocotb.{bus._entity._name}.{bus._name}")

        super().__init__(*args, **kwargs)

        self.active = False

        self.queue = Queue()
        self.dequeue_event = Event()
        self.idle_event = Event()
        self.idle_event.set()
        self.active_event = Event()
        self.wake_event = Event()

        self.ready = None
        self.valid = None

        if self._ready_signal is not None and hasattr(self.bus, self._ready_signal):
            self.ready = getattr(self.bus, self._ready_signal)
            if self._ready_init is not None:
                self.ready.setimmediatevalue(self._ready_init)

        if self._valid_signal is not None and hasattr(self.bus, self._valid_signal):
            self.valid = getattr(self.bus, self._valid_signal)
            if self._valid_init is not None:
                self.valid.setimmediatevalue(self._valid_init)

        for sig in self._signals+self._optional_signals:
            if hasattr(self.bus, sig):
                if sig in self._signal_widths:
                    assert len(getattr(self.bus, sig)) == self._signal_widths[sig]
                if self._init_x and sig not in (self._valid_signal, self._ready_signal):
                    v = getattr(self.bus, sig).value
                    v.binstr = 'x'*len(v)
                    getattr(self.bus, sig).setimmediatevalue(v)

        self._run_cr = None

        self._init_reset(reset, reset_active_level)

    def count(self):
        return self.queue.qsize()

    def empty(self):
        return self.queue.empty()

    def clear(self):
        while not self.queue.empty():
            self.queue.get_nowait()
        self.dequeue_event.set()
        self.idle_event.set()
        self.active_event.clear()

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


class StreamPause:
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


class StreamSource(StreamBase, StreamPause):

    _init_x = True

    _valid_init = 0
    _ready_init = None

    def __init__(self, bus, clock, reset=None, reset_active_level=True, *args, **kwargs):
        super().__init__(bus, clock, reset, reset_active_level, *args, **kwargs)

        self.queue_occupancy_limit = -1

    async def send(self, obj):
        while self.full():
            self.dequeue_event.clear()
            await self.dequeue_event.wait()
        await self.queue.put(obj)
        self.idle_event.clear()
        self.active_event.set()

    def send_nowait(self, obj):
        if self.full():
            raise QueueFull()
        self.queue.put_nowait(obj)
        self.idle_event.clear()
        self.active_event.set()

    def full(self):
        if self.queue_occupancy_limit > 0 and self.count() >= self.queue_occupancy_limit:
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
            if self.valid is not None:
                self.valid.value = 0

    async def _run(self):
        clock_edge_event = RisingEdge(self.clock)

        while True:
            await clock_edge_event

            # read handshake signals
            ready_sample = self.ready is None or self.ready.value
            valid_sample = self.valid is None or self.valid.value

            if (ready_sample and valid_sample) or (not valid_sample):
                if not self.queue.empty() and not self.pause:
                    self.bus.drive(self.queue.get_nowait())
                    self.dequeue_event.set()
                    if self.valid is not None:
                        self.valid.value = 1
                    self.active = True
                else:
                    if self.valid is not None:
                        self.valid.value = 0
                    self.active = not self.queue.empty()
                    if self.queue.empty():
                        self.idle_event.set()
                        self.active_event.clear()

                        await self.active_event.wait()


class StreamMonitor(StreamBase):

    _init_x = False

    _valid_init = None
    _ready_init = None

    def __init__(self, bus, clock, reset=None, reset_active_level=True, *args, **kwargs):
        super().__init__(bus, clock, reset, reset_active_level, *args, **kwargs)

        if self.valid is not None:
            cocotb.start_soon(self._run_valid_monitor())
        if self.ready is not None:
            cocotb.start_soon(self._run_ready_monitor())

    def _dequeue(self, item):
        pass

    def _recv(self, item):
        if self.queue.empty():
            self.active_event.clear()
        self._dequeue(item)
        return item

    async def recv(self):
        item = await self.queue.get()
        return self._recv(item)

    def recv_nowait(self):
        item = self.queue.get_nowait()
        return self._recv(item)

    async def wait(self, timeout=0, timeout_unit=None):
        if not self.empty():
            return
        if timeout:
            await First(self.active_event.wait(), Timer(timeout, timeout_unit))
        else:
            await self.active_event.wait()

    async def _run_valid_monitor(self):
        event = RisingEdge(self.valid)

        while True:
            await event
            self.wake_event.set()

    async def _run_ready_monitor(self):
        event = RisingEdge(self.ready)

        while True:
            await event
            self.wake_event.set()

    async def _run(self):
        clock_edge_event = RisingEdge(self.clock)

        wake_event = self.wake_event.wait()

        while True:
            await clock_edge_event

            # read handshake signals
            ready_sample = self.ready is None or self.ready.value
            valid_sample = self.valid is None or self.valid.value

            if ready_sample and valid_sample:
                obj = self._transaction_obj()
                self.bus.sample(obj)
                self.queue.put_nowait(obj)
                self.active_event.set()
            else:
                self.wake_event.clear()
                await wake_event


class StreamSink(StreamMonitor, StreamPause):

    _init_x = False

    _valid_init = None
    _ready_init = 0

    def __init__(self, bus, clock, reset=None, reset_active_level=True, *args, **kwargs):
        super().__init__(bus, clock, reset, reset_active_level, *args, **kwargs)

        self.queue_occupancy_limit = -1

    def full(self):
        if self.queue_occupancy_limit > 0 and self.count() >= self.queue_occupancy_limit:
            return True
        else:
            return False

    def _handle_reset(self, state):
        super()._handle_reset(state)

        if state:
            if self.ready is not None:
                self.ready.value = 0

    def _pause_update(self, val):
        self.wake_event.set()

    def _dequeue(self, item):
        self.wake_event.set()

    async def _run(self):
        clock_edge_event = RisingEdge(self.clock)

        wake_event = self.wake_event.wait()

        while True:
            pause_sample = self.pause

            await clock_edge_event

            # read handshake signals
            ready_sample = self.ready is None or self.ready.value
            valid_sample = self.valid is None or self.valid.value

            if ready_sample and valid_sample:
                obj = self._transaction_obj()
                self.bus.sample(obj)
                self.queue.put_nowait(obj)
                self.active_event.set()

            if self.ready is not None:
                self.ready.value = (not self.full() and not pause_sample)

            if not valid_sample or (self.pause and pause_sample) or self.full():
                self.wake_event.clear()
                await wake_event


def define_stream(name, signals, optional_signals=None, valid_signal=None, ready_signal=None, signal_widths=None):
    all_signals = signals.copy()

    if optional_signals is None:
        optional_signals = []
    else:
        all_signals += optional_signals

    if valid_signal is None:
        for s in all_signals:
            if s.lower().endswith('valid'):
                valid_signal = s
    if valid_signal not in all_signals:
        signals += valid_signal

    if ready_signal is None:
        for s in all_signals:
            if s.lower().endswith('ready'):
                ready_signal = s
    else:
        if ready_signal not in all_signals:
            signals += ready_signal

    if signal_widths is None:
        signal_widths = {}

    if valid_signal not in signal_widths:
        signal_widths[valid_signal] = 1

    if ready_signal not in signal_widths:
        signal_widths[ready_signal] = 1

    filtered_signals = []

    for s in all_signals:
        if s not in (ready_signal, valid_signal):
            filtered_signals.append(s)

    attrib = {}
    attrib['_signals'] = signals
    attrib['_optional_signals'] = optional_signals
    bus = type(name+"Bus", (StreamBus,), attrib)

    attrib = {s: 0 for s in filtered_signals}
    attrib['_signals'] = filtered_signals

    transaction = type(name+"Transaction", (StreamTransaction,), attrib)

    attrib = {}
    attrib['_signals'] = signals
    attrib['_optional_signals'] = optional_signals
    attrib['_signal_widths'] = signal_widths
    attrib['_ready_signal'] = ready_signal
    attrib['_valid_signal'] = valid_signal
    attrib['_transaction_obj'] = transaction
    attrib['_bus_obj'] = bus

    source = type(name+"Source", (StreamSource,), attrib)
    sink = type(name+"Sink", (StreamSink,), attrib)
    monitor = type(name+"Monitor", (StreamMonitor,), attrib)

    return bus, transaction, source, sink, monitor
