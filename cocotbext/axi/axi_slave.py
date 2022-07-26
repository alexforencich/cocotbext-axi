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
from .constants import AxiBurstType, AxiProt, AxiResp
from .axi_channels import AxiAWSink, AxiWSink, AxiBSource, AxiARSink, AxiRSource
from .reset import Reset


class AxiSlaveWrite(Reset):
    def __init__(self, bus, clock, reset=None, target=None, reset_active_level=True, **kwargs):
        self.bus = bus
        self.clock = clock
        self.reset = reset
        self.target = target
        self.log = logging.getLogger(f"cocotb.{bus.aw._entity._name}.{bus.aw._name}")

        self.log.info("AXI slave model (write)")
        self.log.info("cocotbext-axi version %s", __version__)
        self.log.info("Copyright (c) 2021 Alex Forencich")
        self.log.info("https://github.com/alexforencich/cocotbext-axi")

        super().__init__(**kwargs)

        self.aw_channel = AxiAWSink(bus.aw, clock, reset, reset_active_level)
        self.aw_channel.queue_occupancy_limit = 2
        self.w_channel = AxiWSink(bus.w, clock, reset, reset_active_level)
        self.w_channel.queue_occupancy_limit = 2
        self.b_channel = AxiBSource(bus.b, clock, reset, reset_active_level)
        self.b_channel.queue_occupancy_limit = 2

        self.address_width = len(self.aw_channel.bus.awaddr)
        self.id_width = len(self.aw_channel.bus.awid)
        self.width = len(self.w_channel.bus.wdata)
        self.byte_size = 8
        self.byte_lanes = self.width // self.byte_size
        self.strb_mask = 2**self.byte_lanes-1

        self.max_burst_size = (self.byte_lanes-1).bit_length()

        self.wstrb_present = hasattr(self.bus.w, "wstrb")

        self.log.info("AXI slave model configuration:")
        self.log.info("  Address width: %d bits", self.address_width)
        self.log.info("  ID width: %d bits", self.id_width)
        self.log.info("  Byte size: %d bits", self.byte_size)
        self.log.info("  Data width: %d bits (%d bytes)", self.width, self.byte_lanes)

        self.log.info("AXI slave model signals:")
        for bus in (self.bus.aw, self.bus.w, self.bus.b):
            for sig in sorted(list(set().union(bus._signals, bus._optional_signals))):
                if hasattr(bus, sig):
                    self.log.info("  %s width: %d bits", sig, len(getattr(bus, sig)))
                else:
                    self.log.info("  %s: not present", sig)

        if self.wstrb_present:
            assert self.byte_lanes == len(self.w_channel.bus.wstrb)
        assert self.byte_lanes * self.byte_size == self.width

        assert len(self.b_channel.bus.bid) == len(self.aw_channel.bus.awid)

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

            awid = int(getattr(aw, 'awid', 0))
            addr = int(aw.awaddr)
            length = int(getattr(aw, 'awlen', 0))
            size = int(getattr(aw, 'awsize', self.max_burst_size))
            burst = AxiBurstType(int(getattr(aw, 'awburst', AxiBurstType.INCR)))
            prot = AxiProt(int(getattr(aw, 'awprot', AxiProt.NONSECURE)))

            self.log.info("Write burst awid: 0x%x awaddr: 0x%08x awlen: %d awsize: %d awprot: %s",
                    awid, addr, length, size, prot)

            num_bytes = 2**size
            assert 0 < num_bytes <= self.byte_lanes

            aligned_addr = (addr // num_bytes) * num_bytes
            length += 1

            transfer_size = num_bytes*length

            if burst == AxiBurstType.WRAP:
                lower_wrap_boundary = (addr // transfer_size) * transfer_size
                upper_wrap_boundary = lower_wrap_boundary + transfer_size

            if burst == AxiBurstType.INCR:
                # check 4k boundary crossing
                assert 0x1000-(aligned_addr & 0xfff) >= transfer_size

            cur_addr = aligned_addr

            b = self.b_channel._transaction_obj()
            b.bid = awid
            b.bresp = AxiResp.OKAY

            for n in range(length):
                cur_word_addr = (cur_addr // self.byte_lanes) * self.byte_lanes

                w = await self.w_channel.recv()

                data = int(w.wdata)
                if self.wstrb_present:
                    strb = int(getattr(w, 'wstrb', self.strb_mask))
                else:
                    strb = self.strb_mask
                last = int(w.wlast)

                # generate operation list
                offset = 0
                start_offset = None
                write_ops = []

                data = data.to_bytes(self.byte_lanes, 'little')

                if self.log.isEnabledFor(logging.DEBUG):
                    self.log.debug("Write word awid: 0x%x addr: 0x%08x wstrb: 0x%02x data: %s",
                            awid, cur_addr, strb, ' '.join((f'{c:02x}' for c in data)))

                for i in range(self.byte_lanes):
                    if strb & (1 << i):
                        if start_offset is None:
                            start_offset = offset
                    else:
                        if start_offset is not None and offset != start_offset:
                            write_ops.append((cur_word_addr+start_offset, data[start_offset:offset]))
                        start_offset = None

                    offset += 1

                if start_offset is not None and offset != start_offset:
                    write_ops.append((cur_word_addr+start_offset, data[start_offset:offset]))

                # perform writes
                try:
                    for addr, data in write_ops:
                        await self._write(addr, data)
                except Exception:
                    self.log.warning("Write operation failed")
                    b.bresp = AxiResp.SLVERR

                assert last == (n == length-1)

                if burst != AxiBurstType.FIXED:
                    cur_addr += num_bytes

                    if burst == AxiBurstType.WRAP:
                        if cur_addr == upper_wrap_boundary:
                            cur_addr = lower_wrap_boundary

            await self.b_channel.send(b)


class AxiSlaveRead(Reset):
    def __init__(self, bus, clock, reset=None, target=None, reset_active_level=True, **kwargs):
        self.bus = bus
        self.clock = clock
        self.reset = reset
        self.target = target
        self.log = logging.getLogger(f"cocotb.{bus.ar._entity._name}.{bus.ar._name}")

        self.log.info("AXI slave model (read)")
        self.log.info("cocotbext-axi version %s", __version__)
        self.log.info("Copyright (c) 2021 Alex Forencich")
        self.log.info("https://github.com/alexforencich/cocotbext-axi")

        super().__init__(**kwargs)

        self.ar_channel = AxiARSink(bus.ar, clock, reset, reset_active_level)
        self.ar_channel.queue_occupancy_limit = 2
        self.r_channel = AxiRSource(bus.r, clock, reset, reset_active_level)
        self.r_channel.queue_occupancy_limit = 2

        self.address_width = len(self.ar_channel.bus.araddr)
        self.id_width = len(self.ar_channel.bus.arid)
        self.width = len(self.r_channel.bus.rdata)
        self.byte_size = 8
        self.byte_lanes = self.width // self.byte_size

        self.max_burst_size = (self.byte_lanes-1).bit_length()

        self.log.info("AXI slave model configuration:")
        self.log.info("  Address width: %d bits", self.address_width)
        self.log.info("  ID width: %d bits", self.id_width)
        self.log.info("  Byte size: %d bits", self.byte_size)
        self.log.info("  Data width: %d bits (%d bytes)", self.width, self.byte_lanes)

        self.log.info("AXI slave model signals:")
        for bus in (self.bus.ar, self.bus.r):
            for sig in sorted(list(set().union(bus._signals, bus._optional_signals))):
                if hasattr(bus, sig):
                    self.log.info("  %s width: %d bits", sig, len(getattr(bus, sig)))
                else:
                    self.log.info("  %s: not present", sig)

        assert self.byte_lanes * self.byte_size == self.width

        assert len(self.r_channel.bus.rid) == len(self.ar_channel.bus.arid)

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

            arid = int(getattr(ar, 'arid', 0))
            addr = int(ar.araddr)
            length = int(getattr(ar, 'arlen', 0))
            size = int(getattr(ar, 'arsize', self.max_burst_size))
            burst = AxiBurstType(int(getattr(ar, 'arburst', AxiBurstType.INCR)))
            prot = AxiProt(int(getattr(ar, 'arprot', AxiProt.NONSECURE)))

            self.log.info("Read burst arid: 0x%x araddr: 0x%08x arlen: %d arsize: %d arprot: %s",
                    arid, addr, length, size, prot)

            num_bytes = 2**size
            assert 0 < num_bytes <= self.byte_lanes

            aligned_addr = (addr // num_bytes) * num_bytes
            length += 1

            transfer_size = num_bytes*length

            if burst == AxiBurstType.WRAP:
                lower_wrap_boundary = (addr // transfer_size) * transfer_size
                upper_wrap_boundary = lower_wrap_boundary + transfer_size

            if burst == AxiBurstType.INCR:
                # check 4k boundary crossing
                assert 0x1000-(aligned_addr & 0xfff) >= transfer_size

            cur_addr = aligned_addr

            for n in range(length):
                cur_word_addr = (cur_addr // self.byte_lanes) * self.byte_lanes

                r = self.r_channel._transaction_obj()
                r.rid = arid
                r.rlast = n == length-1
                r.rresp = AxiResp.OKAY

                try:
                    data = await self._read(cur_word_addr, self.byte_lanes)
                except Exception:
                    self.log.warning("Read operation failed")
                    data = bytes(self.byte_lanes)
                    r.rresp = AxiResp.SLVERR

                r.rdata = int.from_bytes(data, 'little')

                await self.r_channel.send(r)

                if self.log.isEnabledFor(logging.DEBUG):
                    self.log.debug("Read word awid: 0x%x addr: 0x%08x data: %s",
                            arid, cur_addr, ' '.join((f'{c:02x}' for c in data)))

                if burst != AxiBurstType.FIXED:
                    cur_addr += num_bytes

                    if burst == AxiBurstType.WRAP:
                        if cur_addr == upper_wrap_boundary:
                            cur_addr = lower_wrap_boundary


class AxiSlave:
    def __init__(self, bus, clock, reset=None, target=None, reset_active_level=True, **kwargs):
        self.write_if = None
        self.read_if = None

        super().__init__(**kwargs)

        self.write_if = AxiSlaveWrite(bus.write, clock, reset, target, reset_active_level)
        self.read_if = AxiSlaveRead(bus.read, clock, reset, target, reset_active_level)
