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

import itertools
import logging
import os
import random

import cocotb_test.simulator
import pytest

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotb.regression import TestFactory

from cocotbext.axi import AxiBus, AxiMaster, AxiRam


class TB:
    def __init__(self, dut):
        self.dut = dut

        self.log = logging.getLogger("cocotb.tb")
        self.log.setLevel(logging.DEBUG)

        cocotb.start_soon(Clock(dut.clk, 2, units="ns").start())

        self.axi_master = AxiMaster(AxiBus.from_prefix(dut, "axi"), dut.clk, dut.rst)
        self.axi_ram = AxiRam(AxiBus.from_prefix(dut, "axi"), dut.clk, dut.rst, size=2**16)

        self.axi_ram.write_if.log.setLevel(logging.DEBUG)
        self.axi_ram.read_if.log.setLevel(logging.DEBUG)

    def set_idle_generator(self, generator=None):
        if generator:
            self.axi_master.write_if.aw_channel.set_pause_generator(generator())
            self.axi_master.write_if.w_channel.set_pause_generator(generator())
            self.axi_master.read_if.ar_channel.set_pause_generator(generator())
            self.axi_ram.write_if.b_channel.set_pause_generator(generator())
            self.axi_ram.read_if.r_channel.set_pause_generator(generator())

    def set_backpressure_generator(self, generator=None):
        if generator:
            self.axi_master.write_if.b_channel.set_pause_generator(generator())
            self.axi_master.read_if.r_channel.set_pause_generator(generator())
            self.axi_ram.write_if.aw_channel.set_pause_generator(generator())
            self.axi_ram.write_if.w_channel.set_pause_generator(generator())
            self.axi_ram.read_if.ar_channel.set_pause_generator(generator())

    async def cycle_reset(self):
        self.dut.rst.setimmediatevalue(0)
        await RisingEdge(self.dut.clk)
        await RisingEdge(self.dut.clk)
        self.dut.rst.value = 1
        await RisingEdge(self.dut.clk)
        await RisingEdge(self.dut.clk)
        self.dut.rst.value = 0
        await RisingEdge(self.dut.clk)
        await RisingEdge(self.dut.clk)


async def run_test_write(dut, idle_inserter=None, backpressure_inserter=None, size=None):

    tb = TB(dut)

    byte_lanes = tb.axi_master.write_if.byte_lanes
    max_burst_size = tb.axi_master.write_if.max_burst_size

    if size is None:
        size = max_burst_size

    await tb.cycle_reset()

    tb.set_idle_generator(idle_inserter)
    tb.set_backpressure_generator(backpressure_inserter)

    for length in list(range(1, byte_lanes*2))+[1024]:
        for offset in list(range(byte_lanes))+list(range(4096-byte_lanes, 4096)):
            tb.log.info("length %d, offset %d", length, offset)
            addr = offset+0x1000
            test_data = bytearray([x % 256 for x in range(length)])

            tb.axi_ram.write(addr-128, b'\xaa'*(length+256))

            await tb.axi_master.write(addr, test_data, size=size)

            tb.log.debug("%s", tb.axi_ram.hexdump_str((addr & ~0xf)-16, (((addr & 0xf)+length-1) & ~0xf)+48))

            assert tb.axi_ram.read(addr, length) == test_data
            assert tb.axi_ram.read(addr-1, 1) == b'\xaa'
            assert tb.axi_ram.read(addr+length, 1) == b'\xaa'

    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)


async def run_test_read(dut, idle_inserter=None, backpressure_inserter=None, size=None):

    tb = TB(dut)

    byte_lanes = tb.axi_master.write_if.byte_lanes
    max_burst_size = tb.axi_master.write_if.max_burst_size

    if size is None:
        size = max_burst_size

    await tb.cycle_reset()

    tb.set_idle_generator(idle_inserter)
    tb.set_backpressure_generator(backpressure_inserter)

    for length in list(range(1, byte_lanes*2))+[1024]:
        for offset in list(range(byte_lanes))+list(range(4096-byte_lanes, 4096)):
            tb.log.info("length %d, offset %d", length, offset)
            addr = offset+0x1000
            test_data = bytearray([x % 256 for x in range(length)])

            tb.axi_ram.write(addr, test_data)

            data = await tb.axi_master.read(addr, length, size=size)

            assert data.data == test_data

    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)


async def run_test_write_words(dut):

    tb = TB(dut)

    byte_lanes = tb.axi_master.write_if.byte_lanes

    await tb.cycle_reset()

    for length in list(range(1, 4)):
        for offset in list(range(byte_lanes)):
            tb.log.info("length %d, offset %d", length, offset)
            addr = offset+0x1000

            test_data = bytearray([x % 256 for x in range(length)])
            event = tb.axi_master.init_write(addr, test_data)
            await event.wait()
            assert tb.axi_ram.read(addr, length) == test_data

            test_data = bytearray([x % 256 for x in range(length)])
            await tb.axi_master.write(addr, test_data)
            assert tb.axi_ram.read(addr, length) == test_data

            test_data = [x * 0x1001 for x in range(length)]
            await tb.axi_master.write_words(addr, test_data)
            assert tb.axi_ram.read_words(addr, length) == test_data

            test_data = [x * 0x10200201 for x in range(length)]
            await tb.axi_master.write_dwords(addr, test_data)
            assert tb.axi_ram.read_dwords(addr, length) == test_data

            test_data = [x * 0x1020304004030201 for x in range(length)]
            await tb.axi_master.write_qwords(addr, test_data)
            assert tb.axi_ram.read_qwords(addr, length) == test_data

            test_data = 0x01*length
            await tb.axi_master.write_byte(addr, test_data)
            assert tb.axi_ram.read_byte(addr) == test_data

            test_data = 0x1001*length
            await tb.axi_master.write_word(addr, test_data)
            assert tb.axi_ram.read_word(addr) == test_data

            test_data = 0x10200201*length
            await tb.axi_master.write_dword(addr, test_data)
            assert tb.axi_ram.read_dword(addr) == test_data

            test_data = 0x1020304004030201*length
            await tb.axi_master.write_qword(addr, test_data)
            assert tb.axi_ram.read_qword(addr) == test_data

    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)


async def run_test_read_words(dut):

    tb = TB(dut)

    byte_lanes = tb.axi_master.write_if.byte_lanes

    await tb.cycle_reset()

    for length in list(range(1, 4)):
        for offset in list(range(byte_lanes)):
            tb.log.info("length %d, offset %d", length, offset)
            addr = offset+0x1000

            test_data = bytearray([x % 256 for x in range(length)])
            tb.axi_ram.write(addr, test_data)
            event = tb.axi_master.init_read(addr, length)
            await event.wait()
            assert event.data.data == test_data

            test_data = bytearray([x % 256 for x in range(length)])
            tb.axi_ram.write(addr, test_data)
            assert (await tb.axi_master.read(addr, length)).data == test_data

            test_data = [x * 0x1001 for x in range(length)]
            tb.axi_ram.write_words(addr, test_data)
            assert await tb.axi_master.read_words(addr, length) == test_data

            test_data = [x * 0x10200201 for x in range(length)]
            tb.axi_ram.write_dwords(addr, test_data)
            assert await tb.axi_master.read_dwords(addr, length) == test_data

            test_data = [x * 0x1020304004030201 for x in range(length)]
            tb.axi_ram.write_qwords(addr, test_data)
            assert await tb.axi_master.read_qwords(addr, length) == test_data

            test_data = 0x01*length
            tb.axi_ram.write_byte(addr, test_data)
            assert await tb.axi_master.read_byte(addr) == test_data

            test_data = 0x1001*length
            tb.axi_ram.write_word(addr, test_data)
            assert await tb.axi_master.read_word(addr) == test_data

            test_data = 0x10200201*length
            tb.axi_ram.write_dword(addr, test_data)
            assert await tb.axi_master.read_dword(addr) == test_data

            test_data = 0x1020304004030201*length
            tb.axi_ram.write_qword(addr, test_data)
            assert await tb.axi_master.read_qword(addr) == test_data

    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)


async def run_stress_test(dut, idle_inserter=None, backpressure_inserter=None):

    tb = TB(dut)

    await tb.cycle_reset()

    tb.set_idle_generator(idle_inserter)
    tb.set_backpressure_generator(backpressure_inserter)

    async def worker(master, offset, aperture, count=16):
        for k in range(count):
            length = random.randint(1, min(512, aperture))
            addr = offset+random.randint(0, aperture-length)
            test_data = bytearray([x % 256 for x in range(length)])

            await Timer(random.randint(1, 100), 'ns')

            await master.write(addr, test_data)

            await Timer(random.randint(1, 100), 'ns')

            data = await master.read(addr, length)
            assert data.data == test_data

    workers = []

    for k in range(16):
        workers.append(cocotb.start_soon(worker(tb.axi_master, k*0x1000, 0x1000, count=16)))

    while workers:
        await workers.pop(0).join()

    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)


def cycle_pause():
    return itertools.cycle([1, 1, 1, 0])


if cocotb.SIM_NAME:

    data_width = len(cocotb.top.axi_wdata)
    byte_lanes = data_width // 8
    max_burst_size = (byte_lanes-1).bit_length()

    for test in [run_test_write, run_test_read]:

        factory = TestFactory(test)
        factory.add_option("idle_inserter", [None, cycle_pause])
        factory.add_option("backpressure_inserter", [None, cycle_pause])
        factory.add_option("size", [None]+list(range(max_burst_size)))
        factory.generate_tests()

    for test in [run_test_write_words, run_test_read_words]:

        factory = TestFactory(test)
        factory.generate_tests()

    factory = TestFactory(run_stress_test)
    factory.generate_tests()


# cocotb-test

tests_dir = os.path.dirname(__file__)


@pytest.mark.parametrize("data_width", [8, 16, 32])
def test_axi(request, data_width):
    dut = "test_axi"
    module = os.path.splitext(os.path.basename(__file__))[0]
    toplevel = dut

    verilog_sources = [
        os.path.join(tests_dir, f"{dut}.v"),
    ]

    parameters = {}

    parameters['DATA_WIDTH'] = data_width
    parameters['ADDR_WIDTH'] = 32
    parameters['STRB_WIDTH'] = parameters['DATA_WIDTH'] // 8
    parameters['ID_WIDTH'] = 8
    parameters['AWUSER_WIDTH'] = 1
    parameters['WUSER_WIDTH'] = 1
    parameters['BUSER_WIDTH'] = 1
    parameters['ARUSER_WIDTH'] = 1
    parameters['RUSER_WIDTH'] = 1

    extra_env = {f'PARAM_{k}': str(v) for k, v in parameters.items()}

    sim_build = os.path.join(tests_dir, "sim_build",
        request.node.name.replace('[', '-').replace(']', ''))

    cocotb_test.simulator.run(
        python_search=[tests_dir],
        verilog_sources=verilog_sources,
        toplevel=toplevel,
        module=module,
        parameters=parameters,
        sim_build=sim_build,
        extra_env=extra_env,
    )
