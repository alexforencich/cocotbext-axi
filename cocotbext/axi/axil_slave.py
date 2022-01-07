"""

Copyright (c) 2021 Alex Forencich

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

from .version import __version__
from .constants import AxiProt, AxiResp
from .axil_channels import AxiLiteAWSink, AxiLiteWSink, AxiLiteBSource, AxiLiteARSink, AxiLiteRSource
from .reset import Reset


class AxiLiteSlaveWrite(Reset):
    def __init__(self, bus, clock, reset=None, target=None, reset_active_level=True, **kwargs):
        self.bus = bus
        self.clock = clock
        self.reset = reset
        self.target = target
        self.log = logging.getLogger(f"cocotb.{bus.aw._entity._name}.{bus.aw._name}")

        self.log.info("AXI lite slave model (write)")
        self.log.info("cocotbext-axi version %s", __version__)
        self.log.info("Copyright (c) 2021 Alex Forencich")
        self.log.info("https://github.com/alexforencich/cocotbext-axi")

        super().__init__(**kwargs)

        self.aw_channel = AxiLiteAWSink(bus.aw, clock, reset, reset_active_level)
        self.aw_channel.queue_occupancy_limit = 2
        self.w_channel = AxiLiteWSink(bus.w, clock, reset, reset_active_level)
        self.w_channel.queue_occupancy_limit = 2
        self.b_channel = AxiLiteBSource(bus.b, clock, reset, reset_active_level)
        self.b_channel.queue_occupancy_limit = 2

        self.address_width = len(self.aw_channel.bus.awaddr)
        self.width = len(self.w_channel.bus.wdata)
        self.byte_size = 8
        self.byte_lanes = self.width // self.byte_size
        self.strb_mask = 2**self.byte_lanes-1

        self.wstrb_present = hasattr(self.bus.w, "wstrb")

        self.log.info("AXI lite slave model configuration:")
        self.log.info("  Address width: %d bits", self.address_width)
        self.log.info("  Byte size: %d bits", self.byte_size)
        self.log.info("  Data width: %d bits (%d bytes)", self.width, self.byte_lanes)

        self.log.info("AXI lite slave model signals:")
        for bus in (self.bus.aw, self.bus.w, self.bus.b):
            for sig in sorted(list(set().union(bus._signals, bus._optional_signals))):
                if hasattr(bus, sig):
                    self.log.info("  %s width: %d bits", sig, len(getattr(bus, sig)))
                else:
                    self.log.info("  %s: not present", sig)

        if self.wstrb_present:
            assert self.byte_lanes == len(self.w_channel.bus.wstrb)
        assert self.byte_lanes * self.byte_size == self.width

        self._process_write_cr = None

        self._init_reset(reset, reset_active_level)

    async def _write(self, address, data):
        await self.target.write(address, data)

    def _handle_reset(self, state):
        if state:
            self.log.info("Reset asserted")
            if self._process_write_cr is not None:
                self._process_write_cr.kill()
                self._process_write_cr = None

            self.aw_channel.clear()
            self.w_channel.clear()
            self.b_channel.clear()
        else:
            self.log.info("Reset de-asserted")
            if self._process_write_cr is None:
                self._process_write_cr = cocotb.start_soon(self._process_write())

    async def _process_write(self):
        while True:
            aw = await self.aw_channel.recv()

            addr = (int(aw.awaddr) // self.byte_lanes) * self.byte_lanes
            prot = AxiProt(int(getattr(aw, 'awprot', AxiProt.NONSECURE)))

            w = await self.w_channel.recv()

            data = int(w.wdata)
            if self.wstrb_present:
                strb = int(getattr(w, 'wstrb', self.strb_mask))
            else:
                strb = self.strb_mask

            # generate operation list
            offset = 0
            start_offset = None
            write_ops = []

            data = data.to_bytes(self.byte_lanes, 'little')

            b = self.b_channel._transaction_obj()
            b.bresp = AxiResp.OKAY

            if self.log.isEnabledFor(logging.INFO):
                self.log.info("Write data awaddr: 0x%08x awprot: %s wstrb: 0x%02x data: %s",
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

            # perform writes
            try:
                for addr, data in write_ops:
                    await self._write(addr, data)
            except Exception:
                self.log.warning("Write operation failed")
                b.bresp = AxiResp.SLVERR

            await self.b_channel.send(b)


class AxiLiteSlaveRead(Reset):
    def __init__(self, bus, clock, reset=None, target=None, reset_active_level=True, **kwargs):
        self.bus = bus
        self.clock = clock
        self.reset = reset
        self.target = target
        self.log = logging.getLogger(f"cocotb.{bus.ar._entity._name}.{bus.ar._name}")

        self.log.info("AXI lite slave model (read)")
        self.log.info("cocotbext-axi version %s", __version__)
        self.log.info("Copyright (c) 2021 Alex Forencich")
        self.log.info("https://github.com/alexforencich/cocotbext-axi")

        super().__init__(**kwargs)

        self.ar_channel = AxiLiteARSink(bus.ar, clock, reset, reset_active_level)
        self.ar_channel.queue_occupancy_limit = 2
        self.r_channel = AxiLiteRSource(bus.r, clock, reset, reset_active_level)
        self.r_channel.queue_occupancy_limit = 2

        self.address_width = len(self.ar_channel.bus.araddr)
        self.width = len(self.r_channel.bus.rdata)
        self.byte_size = 8
        self.byte_lanes = self.width // self.byte_size

        self.log.info("AXI lite slave model configuration:")
        self.log.info("  Address width: %d bits", self.address_width)
        self.log.info("  Byte size: %d bits", self.byte_size)
        self.log.info("  Data width: %d bits (%d bytes)", self.width, self.byte_lanes)

        self.log.info("AXI lite slave model signals:")
        for bus in (self.bus.ar, self.bus.r):
            for sig in sorted(list(set().union(bus._signals, bus._optional_signals))):
                if hasattr(bus, sig):
                    self.log.info("  %s width: %d bits", sig, len(getattr(bus, sig)))
                else:
                    self.log.info("  %s: not present", sig)

        assert self.byte_lanes * self.byte_size == self.width

        self._process_read_cr = None

        self._init_reset(reset, reset_active_level)

    async def _read(self, address, length):
        return await self.target.read(address, length)

    def _handle_reset(self, state):
        if state:
            self.log.info("Reset asserted")
            if self._process_read_cr is not None:
                self._process_read_cr.kill()
                self._process_read_cr = None

            self.ar_channel.clear()
            self.r_channel.clear()
        else:
            self.log.info("Reset de-asserted")
            if self._process_read_cr is None:
                self._process_read_cr = cocotb.start_soon(self._process_read())

    async def _process_read(self):
        while True:
            ar = await self.ar_channel.recv()

            addr = (int(ar.araddr) // self.byte_lanes) * self.byte_lanes
            prot = AxiProt(int(getattr(ar, 'arprot', AxiProt.NONSECURE)))

            r = self.r_channel._transaction_obj()
            r.rresp = AxiResp.OKAY

            try:
                data = await self._read(addr, self.byte_lanes)
            except Exception:
                self.log.warning("Read operation failed")
                data = bytes(self.byte_lanes)
                r.rresp = AxiResp.SLVERR

            r.rdata = int.from_bytes(data, 'little')

            await self.r_channel.send(r)

            if self.log.isEnabledFor(logging.INFO):
                self.log.info("Read data araddr: 0x%08x arprot: %s data: %s",
                        addr, prot, ' '.join((f'{c:02x}' for c in data)))


class AxiLiteSlave:
    def __init__(self, bus, clock, reset=None, target=None, reset_active_level=True, **kwargs):
        self.write_if = None
        self.read_if = None

        super().__init__(**kwargs)

        self.write_if = AxiLiteSlaveWrite(bus.write, clock, reset, target, reset_active_level)
        self.read_if = AxiLiteSlaveRead(bus.read, clock, reset, target, reset_active_level)
