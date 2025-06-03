#!/usr/bin/env python

import cocotb_test.simulator
import cocotb
import random
import itertools
import logging
import os
import pytest
import asyncio
from cocotb.triggers import RisingEdge, Timer
from cocotb.binary import BinaryValue
from cocotb.regression import TestFactory
from cocotbext.axi.constants import *
from cocotb.clock import Clock

from cocotbext.axi import AxiBus, AxiMaster, AxiRam
from cocotb.result import TestFailure

class TB_CMSS:
    def __init__(self, dut):
        self.dut = dut

        self.log = logging.getLogger("cocotb.tb")
        self.log.setLevel(logging.DEBUG)

        self.tb_axi  = TB_AXI(dut)
        self.tb_apb  = TB_APB(dut)

    async def timeout_watchdog(self, dut, timeout, unit):
        await Timer(timeout, unit)
        self.log.error("Test timed out")
        raise TestFailure("Test failed due to timeout")

    async def cycle_reset(self):
        self.dut.areset.setimmediatevalue(0)
        self.dut.preset.setimmediatevalue(0)
        self.dut.creset.setimmediatevalue(0)
        await RisingEdge(self.dut.aclk)
        await RisingEdge(self.dut.aclk)
        self.dut.areset.value = 1
        self.dut.creset.value = 1
        self.dut.preset.value = 1
        await RisingEdge(self.dut.aclk)
        await RisingEdge(self.dut.aclk)
        self.dut.areset.value = 0
        self.dut.creset.value = 0
        self.dut.preset.value = 0
        for i in range(10):
            await RisingEdge(self.dut.aclk)

class TB_AXI:
    def __init__(self, dut):
        self.dut = dut

        self.log = logging.getLogger("cocotb.tb")
        self.log.setLevel(logging.DEBUG)

        cocotb.start_soon(Clock(dut.aclk, 2, units="ns").start())
        cocotb.start_soon(Clock(dut.cclk, 2, units="ns").start())
        #TODO:cocotb.start_soon(Clock(dut.pclk, 2, units="ns").start())

        self.axi_master = AxiMaster(AxiBus.from_prefix(dut, "core"), dut.aclk, dut.areset)
        self.axi_ram1 = AxiRam(AxiBus.from_prefix(dut, "mem"), dut.aclk, dut.areset, size=2**16)
        self.axi_ram2 = AxiRam(AxiBus.from_prefix(dut, "mem2"), dut.aclk, dut.areset, size=2**16)

        self.axi_ram1.write_if.log.setLevel(logging.DEBUG)
        self.axi_ram1.read_if.log.setLevel(logging.DEBUG)
        self.axi_ram2.write_if.log.setLevel(logging.DEBUG)
        self.axi_ram2.read_if.log.setLevel(logging.DEBUG)

    def set_idle_generator(self, generator=None):
        if generator:
            self.axi_master.write_if.aw_channel.set_pause_generator(generator())
            self.axi_master.write_if.w_channel.set_pause_generator(generator())
            self.axi_master.read_if.ar_channel.set_pause_generator(generator())
            self.axi_ram1.write_if.b_channel.set_pause_generator(generator())
            self.axi_ram1.read_if.r_channel.set_pause_generator(generator())
            self.axi_ram2.write_if.b_channel.set_pause_generator(generator())
            self.axi_ram2.read_if.r_channel.set_pause_generator(generator())

    def set_backpressure_generator(self, generator=None):
        if generator:
            self.axi_master.write_if.b_channel.set_pause_generator(generator())
            self.axi_master.read_if.r_channel.set_pause_generator(generator())
            self.axi_ram1.write_if.aw_channel.set_pause_generator(generator())
            self.axi_ram1.write_if.w_channel.set_pause_generator(generator())
            self.axi_ram1.read_if.ar_channel.set_pause_generator(generator())
            self.axi_ram2.write_if.aw_channel.set_pause_generator(generator())
            self.axi_ram2.write_if.w_channel.set_pause_generator(generator())
            self.axi_ram2.read_if.ar_channel.set_pause_generator(generator())

    async def cycle_reset(self):
        self.dut.areset.setimmediatevalue(0)
        self.dut.preset.setimmediatevalue(0)
        self.dut.creset.setimmediatevalue(0)
        await RisingEdge(self.dut.aclk)
        await RisingEdge(self.dut.aclk)
        self.dut.areset.value = 1
        self.dut.creset.value = 1
        self.dut.preset.value = 1
        await RisingEdge(self.dut.aclk)
        await RisingEdge(self.dut.aclk)
        self.dut.areset.value = 0
        self.dut.creset.value = 0
        self.dut.preset.value = 0
        for i in range(10):
            await RisingEdge(self.dut.aclk)
    def init(self):
        #self.set_idle_generator(idle_inserter)
        #self.set_backpressure_generator(backpressure_inserter)
        None

from cocotbext.apb import ApbMaster
from cocotbext.apb import Apb3Bus
from cocotbext.apb import ApbMonitor
def returned_val(read_op):
    return int.from_bytes(read_op, byteorder='little')

class reg_map_c:
    def __init__(self):
        self.reg_map = {}
        self.reg_map["cache_apb"] = {}
        self.reg_map["cache_apb"][0x0000] = {"name":"VERSION", "addr":0x0000, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x0100] = {"name":"START_ADDR_L", "addr":0x0100, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x0104] = {"name":"START_ADDR_H", "addr":0x0104, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x0108] = {"name":"END_ADDR_L", "addr":0x0108, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x010c] = {"name":"END_ADDR_H", "addr":0x010c, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x0200] = {"name":"CMD", "addr":0x0200, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x0204] = {"name":"STATUS", "addr":0x0204, "reset_val":0x0, "value":0x0, "mask":0xffffffff}

        self.reg_map["cache_apb"][0x1000] = {"name":"DBG_FIFO[0]", "addr":0x1000, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x1004] = {"name":"DBG_FIFO[1]", "addr":0x1004, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x1008] = {"name":"DBG_FIFO[2]", "addr":0x1008, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x100c] = {"name":"DBG_FIFO[3]", "addr":0x100c, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x1010] = {"name":"DBG_FIFO[4]", "addr":0x1010, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x1014] = {"name":"DBG_FIFO[5]", "addr":0x1014, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x1018] = {"name":"DBG_FIFO[6]", "addr":0x1018, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x101c] = {"name":"DBG_FIFO[7]", "addr":0x101c, "reset_val":0x0, "value":0x0, "mask":0xffffffff}

        self.reg_map["cache_apb"][0x1400] = {"name":"DBG_NORMAL_CNT[0]", "addr":0x1400, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x1404] = {"name":"DBG_NORMAL_CNT[1]", "addr":0x1404, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x1408] = {"name":"DBG_NORMAL_CNT[2]", "addr":0x1408, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x140c] = {"name":"DBG_NORMAL_CNT[3]", "addr":0x140c, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x1410] = {"name":"DBG_NORMAL_CNT[4]", "addr":0x1410, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x1414] = {"name":"DBG_NORMAL_CNT[5]", "addr":0x1414, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x1418] = {"name":"DBG_NORMAL_CNT[6]", "addr":0x1418, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x141c] = {"name":"DBG_NORMAL_CNT[7]", "addr":0x141c, "reset_val":0x0, "value":0x0, "mask":0xffffffff}

        self.reg_map["cache_apb"][0x1800] = {"name":"DBG_SATUR_CNT[0]", "addr":0x1800, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x1804] = {"name":"DBG_SATUR_CNT[1]", "addr":0x1804, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x1808] = {"name":"DBG_SATUR_CNT[2]", "addr":0x1808, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x180c] = {"name":"DBG_SATUR_CNT[3]", "addr":0x180c, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x1810] = {"name":"DBG_SATUR_CNT[4]", "addr":0x1810, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x1814] = {"name":"DBG_SATUR_CNT[5]", "addr":0x1814, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x1818] = {"name":"DBG_SATUR_CNT[6]", "addr":0x1818, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
        self.reg_map["cache_apb"][0x181c] = {"name":"DBG_SATUR_CNT[7]", "addr":0x181c, "reset_val":0x0, "value":0x0, "mask":0xffffffff}
#TODO:    def __reset_reg(self, reg):
#TODO:
#TODO:    def __reset_reg_blk(self, reg_blk):
#TODO:        regs = self.reg_map[reg_blk]
#TODO:        for i in regs:
#TODO:            __reset_reg(i)

def reg_cmp(reg_blk, addr, data):
    if addr not in reg_blk:
        return True
    if (reg_blk[addr]["value"] & reg_blk[addr]["mask"]) == (data & reg_blk[addr]["mask"]):
        return True
    else:
        return False


class TB_APB:
    def __init__(self, dut):
        self.log = logging.getLogger("cocotb.tb")
        self.log.setLevel(logging.DEBUG)
        #yhyang:self.regwidth = int(dut.REGWIDTH)
        #yhyang:self.n_regs   = int(dut.N_REGS)
        self.regwidth = 32
        self.n_regs   = 32
        self.mask = (2 ** self.regwidth) - 1
        self.incr = int(self.regwidth/8)
        #yhyang:self.cr = ClkReset(dut, period, reset_sense=reset_sense, resetname="preset")
        self.dut = dut
        cocotb.start_soon(Clock(dut.pclk, 2, units="ns").start())
        
        clk_name="pclk"

        cache_apb_prefix="cache"
        self.cache_apb_bus = Apb3Bus.from_prefix(dut, cache_apb_prefix)
        self.cache_apb_intf = ApbMaster(self.cache_apb_bus, getattr(dut, clk_name))
        self.cache_apb_mon = ApbMonitor(self.cache_apb_bus, getattr(dut, clk_name))
        self.cache_apb_mon.enable_logging()

        mem_apb_prefix="mem"
        self.mem_apb_bus = Apb3Bus.from_prefix(dut, mem_apb_prefix)
        self.mem_apb_intf = ApbMaster(self.mem_apb_bus, getattr(dut, clk_name))
        self.mem_apb_mon = ApbMonitor(self.mem_apb_bus, getattr(dut, clk_name))
        self.mem_apb_mon.enable_logging()

        cxl_apb_prefix="cxl"
        self.cxl_apb_bus = Apb3Bus.from_prefix(dut, cxl_apb_prefix)
        self.cxl_apb_intf = ApbMaster(self.cxl_apb_bus, getattr(dut, clk_name))
        self.cxl_apb_mon = ApbMonitor(self.cxl_apb_bus, getattr(dut, clk_name))
        self.cxl_apb_mon.enable_logging()

        reg_map_inst = reg_map_c()
        self.cache_apb_reg_blk = reg_map_inst.reg_map["cache_apb"]

    async def cycle_reset(self):
        self.dut.preset.setimmediatevalue(0)
        await RisingEdge(self.dut.pclk)
        await RisingEdge(self.dut.pclk)
        self.dut.preset.value = 1
        await RisingEdge(self.dut.pclk)
        await RisingEdge(self.dut.pclk)
        self.dut.preset.value = 0
        await RisingEdge(self.dut.pclk)
        await RisingEdge(self.dut.pclk)

    def init(self):
        None

async def axi_random_access(dut, idle_inserter=None, backpressure_inserter=None, size=None):
    #yhyang:tb = TB_APB(dut, reset_sense=1)
    tb = TB_CMSS(dut)
    tb_apb = tb.tb_apb
    tb_axi = tb.tb_axi

    tb.tb_axi.init()
    tb.tb_apb.init()

    cocotb.start_soon(tb.timeout_watchdog(dut, 50, 'us'))

    cache_apb_reg_blk = tb_apb.cache_apb_reg_blk

    byte_lanes = tb_axi.axi_master.write_if.byte_lanes
    max_burst_size = tb_axi.axi_master.write_if.max_burst_size


    if size is None:
        size = max_burst_size

    await tb.cycle_reset()
    await RisingEdge(dut.pclk)
    #check Version register
    read_op = await tb_apb.cache_apb_intf.read(0x0000)
    ret = returned_val(read_op)

    # Write START command
    await tb_apb.cache_apb_intf.write(0x0200, 0x1)
    await RisingEdge(dut.pclk)

    # Read STATUS command until 0
    ret = 1
    while(ret == 1):
        read_op = await tb_apb.cache_apb_intf.read(0x0204)
        ret = returned_val(read_op)
        await Timer(100, 'ns')

    await Timer(10, 'us')

    # sequential write to random addr/data. save data in dict
    await RisingEdge(dut.aclk)
    golden_value = {}
    addr_list = [0x1000 * i for i in range(1, 17)]  # 0x1000, 0x2000, ..., 0x10000

    for iter in range(16):
        length = 64 # fixed
        #addr = random.randint(0, 0x1000000000)
        addr = addr_list[iter]
        #TEST:addr = random.randint(0, 0)
        addr = addr >> 6
        addr = addr << 6
        test_data = bytearray([random.randint(0,255) for x in range(length)])
        tb_axi.log.info("addr = 0x%x", addr)

        golden_value[addr] = test_data
        random_awcache = random.choice(AWCACHE_VALUES)
        #await tb_axi.axi_master.write(addr, test_data, size=size, cache=random_awcache)
        await tb_axi.axi_master.write(addr, test_data, size=size, cache=AWCACHE_DEVICE_NON_BUFFERABLE)
        # await Timer(1, 'ns')
    
    await Timer(100, 'ns')
    for iter in range(16):
        await RisingEdge(dut.aclk)
        length = 64 # fixed
        # addr = random.randint(0, 0x1000000000)
        addr = addr_list[iter]
        #TEST:addr = random.randint(0, 0)
        addr = addr >> 6
        addr = addr << 6
        #test_data = bytearray([random.randint(0,255) for x in range(length)])
        tb_axi.log.info("addr = 0x%x", addr)


        #golden_value[addr] = test_data
        random_arcache = random.choice(ARCACHE_VALUES)
        #await tb_axi.axi_master.read(addr, length, size=size, cache=random_arcache)
        await tb_axi.axi_master.read(addr, length, size=size, cache=ARCACHE_DEVICE_NON_BUFFERABLE)
        #await tb_axi.axi_master.read(addr, length, size=size, cache=ARCACHE_WRITE_BACK_READ_AND_WRITE_ALLOC)
        # await Timer(1, 'ns')

        #await Timer(12, 'ns')

    await RisingEdge(dut.aclk)
    await Timer(random.randint(1, 2), 'us')

    await Timer(100, 'ns')
    return golden_value

async def axi_random_access_stress (dut, idle_inserter=None, backpressure_inserter=None, size=None):
    #yhyang:tb = TB_APB(dut, reset_sense=1)
    tb = TB_CMSS(dut)
    tb_apb = tb.tb_apb
    tb_axi = tb.tb_axi

    tb.tb_axi.init()
    tb.tb_apb.init()

    cocotb.start_soon(tb.timeout_watchdog(dut, 50, 'us'))

    cache_apb_reg_blk = tb_apb.cache_apb_reg_blk

    byte_lanes = tb_axi.axi_master.write_if.byte_lanes
    max_burst_size = tb_axi.axi_master.write_if.max_burst_size


    if size is None:
        size = max_burst_size

    await tb.cycle_reset()
    await RisingEdge(dut.pclk)
    #check Version register
    read_op = await tb_apb.cache_apb_intf.read(0x0000)
    ret = returned_val(read_op)

    # Write START command
    await tb_apb.cache_apb_intf.write(0x0200, 0x1)
    await RisingEdge(dut.pclk)

    # Read STATUS command until 0
    ret = 1
    while(ret == 1):
        read_op = await tb_apb.cache_apb_intf.read(0x0204)
        ret = returned_val(read_op)
        await Timer(100, 'ns')

    await Timer(10, 'us')

    # sequential write to random addr/data. save data in dict
    await RisingEdge(dut.aclk)
    golden_value = {}
    addr_list = [0x1000 * i for i in range(1, 5001)]  # 0x1000, 0x2000, ..., 0x10000

    for iter in range(100):
        print(f"Write : {iter}")
        length = 64 # fixed
        #addr = random.randint(0, 0x1000000000)
        addr = addr_list[iter]
        #TEST:addr = random.randint(0, 0)
        addr = addr >> 6
        addr = addr << 6
        test_data = bytearray([random.randint(0,255) for x in range(length)])
        tb_axi.log.info("addr = 0x%x", addr)

        golden_value[addr] = test_data
        random_awcache = random.choice(AWCACHE_VALUES)
        await tb_axi.axi_master.write(addr, test_data, size=size, cache=random_awcache)
        # await tb_axi.axi_master.write(addr, test_data, size=size, cache=AWCACHE_DEVICE_NON_BUFFERABLE)
        await Timer(1, 'ns')
    
    await Timer(100, 'ns')
    for iter in range(100):
        print(f"Read : {iter}")
        await RisingEdge(dut.aclk)
        length = 64 # fixed
        # addr = random.randint(0, 0x1000000000)
        addr = addr_list[iter]
        #TEST:addr = random.randint(0, 0)
        addr = addr >> 6
        addr = addr << 6
        #test_data = bytearray([random.randint(0,255) for x in range(length)])
        tb_axi.log.info("addr = 0x%x", addr)
        await Timer(1, 'ns')


        #golden_value[addr] = test_data
        random_arcache = random.choice(ARCACHE_VALUES)
        await tb_axi.axi_master.read(addr, length, size=size, cache=random_arcache)
        # await tb_axi.axi_master.read(addr, length, size=size, cache=ARCACHE_DEVICE_NON_BUFFERABLE)
        #await tb_axi.axi_master.read(addr, length, size=size, cache=ARCACHE_WRITE_BACK_READ_AND_WRITE_ALLOC)

        #await Timer(12, 'ns')

    await RisingEdge(dut.aclk)
    await Timer(random.randint(1, 2), 'us')

    await Timer(100, 'ns')
    return golden_value

async def run_test_write_read(dut, idle_inserter=None, backpressure_inserter=None, size=None):

    tb = TB_AXI(dut)

    byte_lanes = tb.axi_master.write_if.byte_lanes
    max_burst_size = tb.axi_master.write_if.max_burst_size

    if size is None:
        size = max_burst_size

    await tb.cycle_reset()

    tb.set_idle_generator(idle_inserter)
    tb.set_backpressure_generator(backpressure_inserter)

    #yhyang:for length in list(range(1, byte_lanes*2))+[1024]:
    for iter in range(0):
        length = 64 # fixed
        addr = random.randint(0, 0x1000000000)
        addr = addr >> 6
        addr = addr << 6
        test_data = bytearray([random.randint(0,255) for x in range(length)])
        tb.log.info("addr = 0x%x", addr)

        await tb.axi_master.write(addr, test_data, size=size)
        rresp = await tb.axi_master.read(addr, length, size=size)
        print("[YH_DEBUG] write_data: 0x%x", test_data)
        print("[YH_DEBUG] read_data: 0x%x", rresp.data)
        assert test_data == rresp.data

    # sequential write to random addr/data. save data in dict
    golden_value = {}
    for iter in range(256):
        length = 64 # fixed
        addr = random.randint(0, 0x1000000000)
        addr = addr >> 6
        addr = addr << 6
        test_data = bytearray([random.randint(0,255) for x in range(length)])
        tb.log.info("addr = 0x%x", addr)


        golden_value[addr] = test_data
        await tb.axi_master.write(addr, test_data, size=size)

    for addr, wdata in golden_value.items():
        rresp = await tb.axi_master.read(addr, length, size=size)
        if wdata != rresp.data:
            print("[YH_DEBUG][UVM_ERROR] data mismatch. addr: 0x{:x}".format(addr))
            print("[YH_DEBUG][UVM_ERROR] wdata: 0x{}".format(wdata.hex()))
            print("[YH_DEBUG][UVM_ERROR] rdata: 0x{}".format(rresp.data.hex()))
        assert wdata == rresp.data

    await RisingEdge(dut.aclk)
    await RisingEdge(dut.aclk)



async def run_test_write(dut, idle_inserter=None, backpressure_inserter=None, size=None):

    tb = TB_AXI(dut)

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

            tb.axi_ram2.write(addr-128, b'\xaa'*(length+256))
            tb.axi_ram2.write(addr-128, b'\xaa'*(length+256))

            await tb.axi_master.write(addr, test_data, size=size)

            tb.log.debug("%s", tb.axi_ram1.hexdump_str((addr & ~0xf)-16, (((addr & 0xf)+length-1) & ~0xf)+48))
            tb.log.debug("%s", tb.axi_ram2.hexdump_str((addr & ~0xf)-16, (((addr & 0xf)+length-1) & ~0xf)+48))

            assert tb.axi_ram1.read(addr, length) == test_data
            assert tb.axi_ram1.read(addr-1, 1) == b'\xaa'
            assert tb.axi_ram1.read(addr+length, 1) == b'\xaa'
            assert tb.axi_ram2.read(addr, length) == test_data
            assert tb.axi_ram2.read(addr-1, 1) == b'\xaa'
            assert tb.axi_ram2.read(addr+length, 1) == b'\xaa'

    await RisingEdge(dut.aclk)
    await RisingEdge(dut.aclk)


async def run_test_read(dut, idle_inserter=None, backpressure_inserter=None, size=None):

    tb = TB_AXI(dut)

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

            tb.axi_ram1.write(addr, test_data)
            tb.axi_ram2.write(addr, test_data)

            data = await tb.axi_master.read(addr, length, size=size)

            assert data.data == test_data

    await RisingEdge(dut.aclk)
    await RisingEdge(dut.aclk)


async def run_test_write_words(dut):

    tb = TB_AXI(dut)

    byte_lanes = tb.axi_master.write_if.byte_lanes

    await tb.cycle_reset()

    for length in list(range(1, 4)):
        for offset in list(range(byte_lanes)):
            tb.log.info("length %d, offset %d", length, offset)
            addr = offset+0x1000

            test_data = bytearray([x % 256 for x in range(length)])
            event = tb.axi_master.init_write(addr, test_data)
            await event.wait()
            assert tb.axi_ram1.read(addr, length) == test_data
            assert tb.axi_ram2.read(addr, length) == test_data

            test_data = bytearray([x % 256 for x in range(length)])
            await tb.axi_master.write(addr, test_data)
            assert tb.axi_ram1.read(addr, length) == test_data
            assert tb.axi_ram2.read(addr, length) == test_data

            test_data = [x * 0x1001 for x in range(length)]
            await tb.axi_master.write_words(addr, test_data)
            assert tb.axi_ram1.read_words(addr, length) == test_data
            assert tb.axi_ram2.read_words(addr, length) == test_data

            test_data = [x * 0x10200201 for x in range(length)]
            await tb.axi_master.write_dwords(addr, test_data)
            assert tb.axi_ram1.read_dwords(addr, length) == test_data
            assert tb.axi_ram2.read_dwords(addr, length) == test_data

            test_data = [x * 0x1020304004030201 for x in range(length)]
            await tb.axi_master.write_qwords(addr, test_data)
            assert tb.axi_ram1.read_qwords(addr, length) == test_data
            assert tb.axi_ram2.read_qwords(addr, length) == test_data

            test_data = 0x01*length
            await tb.axi_master.write_byte(addr, test_data)
            assert tb.axi_ram1.read_byte(addr) == test_data
            assert tb.axi_ram2.read_byte(addr) == test_data

            test_data = 0x1001*length
            await tb.axi_master.write_word(addr, test_data)
            assert tb.axi_ram1.read_word(addr) == test_data
            assert tb.axi_ram2.read_word(addr) == test_data

            test_data = 0x10200201*length
            await tb.axi_master.write_dword(addr, test_data)
            assert tb.axi_ram1.read_dword(addr) == test_data
            assert tb.axi_ram2.read_dword(addr) == test_data

            test_data = 0x1020304004030201*length
            await tb.axi_master.write_qword(addr, test_data)
            assert tb.axi_ram1.read_qword(addr) == test_data
            assert tb.axi_ram2.read_qword(addr) == test_data

    await RisingEdge(dut.aclk)
    await RisingEdge(dut.aclk)


async def run_test_read_words(dut):

    tb = TB_AXI(dut)

    byte_lanes = tb.axi_master.write_if.byte_lanes

    await tb.cycle_reset()

    for length in list(range(1, 4)):
        #length=96
        length=64
        tb.log.info("[YH_DEBUG] length %d", length)
        for offset in list(range(byte_lanes)):
            tb.log.info("length %d, offset %d", length, offset)
            addr = offset+0x1000
            mem1_addr = addr * 2

            test_data = bytearray([x % 256 for x in range(length)])
            tb.axi_ram1.write(mem1_addr, test_data)
            tb.axi_ram2.write(addr, test_data)
            event = tb.axi_master.init_read(addr, length)
            await event.wait()
            assert event.data.data == test_data

            test_data = bytearray([x % 256 for x in range(length)])
            tb.axi_ram1.write(mem1_addr, test_data)
            tb.axi_ram2.write(addr, test_data)
            assert (await tb.axi_master.read(addr, length)).data == test_data

            test_data = [x * 0x1001 for x in range(length)]
            tb.axi_ram1.write_words(mem1_addr, test_data)
            tb.axi_ram2.write_words(addr, test_data)
            assert await tb.axi_master.read_words(addr, length) == test_data

            test_data = [x * 0x10200201 for x in range(length)]
            tb.axi_ram1.write_dwords(mem1_addr, test_data)
            tb.axi_ram2.write_dwords(addr, test_data)
            assert await tb.axi_master.read_dwords(addr, length) == test_data

            test_data = [x * 0x1020304004030201 for x in range(length)]
            tb.axi_ram1.write_qwords(mem1_addr, test_data)
            tb.axi_ram2.write_qwords(addr, test_data)
            assert await tb.axi_master.read_qwords(addr, length) == test_data

            test_data = 0x01*length
            tb.axi_ram1.write_byte(mem1_addr, test_data)
            tb.axi_ram2.write_byte(addr, test_data)
            assert await tb.axi_master.read_byte(addr) == test_data

            test_data = 0x1001*length
            tb.axi_ram1.write_word(mem1_addr, test_data)
            tb.axi_ram2.write_word(addr, test_data)
            assert await tb.axi_master.read_word(addr) == test_data

            test_data = 0x10200201*length
            tb.axi_ram1.write_dword(mem1_addr, test_data)
            tb.axi_ram2.write_dword(addr, test_data)
            assert await tb.axi_master.read_dword(addr) == test_data

            test_data = 0x1020304004030201*length
            tb.axi_ram1.write_qword(mem1_addr, test_data)
            tb.axi_ram2.write_qword(addr, test_data)
            assert await tb.axi_master.read_qword(addr) == test_data

    await RisingEdge(dut.aclk)
    await RisingEdge(dut.aclk)


async def run_stress_test(dut, idle_inserter=None, backpressure_inserter=None):

    tb = TB_AXI(dut)

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

    await RisingEdge(dut.aclk)
    await RisingEdge(dut.aclk)


def cycle_pause():
    return itertools.cycle([1, 1, 1, 0])

from random import randint     
from cocotb import test

#yhyang:from interfaces.clkrst import ClkReset


async def test_apb_basic(dut):
    #yhyang:tb = TB_APB(dut, reset_sense=1)
    tb = TB_APB(dut)

    #yhyang:await tb.cr.wait_clkn(200)
    await tb.cycle_reset()

    addr = 0x0000
    read_op = await tb.cache_apb_intf.read(addr)
    ret = returned_val(read_op)
    #assert 0x0 == ret
    tb.log.info("cache_apb addr: 0x%08x, data: 0x08x", addr, ret)
    
    x = 0x12345678
    bytesdata = x.to_bytes(len(tb.cache_apb_bus.pwdata), 'little')
    await tb.cache_apb_intf.write(0x0000, bytesdata)

    read_op = await tb.cache_apb_intf.read(0x0000)
    ret = returned_val(read_op)
    assert x == ret
    
    await tb.cache_apb_intf.read(0x0000, bytesdata)
    await tb.cache_apb_intf.read(0x0000, x)

    x = 0x12345679
    bytesdata = x.to_bytes(len(tb.cache_apb_bus.pwdata), 'little')
    await tb.cache_apb_intf.write(0x0000, x)

    await tb.cache_apb_intf.read(0x0000, x)
    await tb.cache_apb_intf.read(0x0000, 0x12345679)

    await tb.cache_apb_intf.write(0x0000, 0x12)
    await tb.cache_apb_intf.read(0x0000, 0x12)
    
    await tb.cache_apb_intf.write(0x0000, 0x0)
    await tb.cache_apb_intf.write(0x0000, 0x87654321, 0x8)
    await tb.cache_apb_intf.read(0x0000, 0x87000000)
    await tb.cache_apb_intf.write(0x0000, 0x56346456, 0x4)
    await tb.cache_apb_intf.read(0x0000, 0x87340000)
    await tb.cache_apb_intf.write(0x0000, 0x69754233, 0x2)
    await tb.cache_apb_intf.read(0x0000, 0x87344200)
    await tb.cache_apb_intf.write(0x0000, 0x21454568, 0x1)
    await tb.cache_apb_intf.read(0x0000, 0x87344268)
    await tb.cache_apb_intf.write(0x0000, 0x0)
    await tb.cache_apb_intf.read(0x0000, 0x0)

    await tb.cache_apb_intf.write(0x0002, 0x87654321)
    await tb.cache_apb_intf.read(0x0000, 0x87654321)

    await tb.cache_apb_intf.write(0x0004, 0x97654321)
    await tb.cr.wait_clkn(2)
    await tb.cache_apb_intf.read(0x0006, 0x97654321)

    await tb.cache_apb_intf.write(0x0014, 0x77654321)
    await tb.cache_apb_intf.read(0x0016, 0x77654321)

    x = []
    for i in range(tb.n_regs):
        x.append(randint(0, (2**32)-1))
    
    for i in range(tb.n_regs):
        bytesdata = x[i].to_bytes(len(tb.cache_apb_bus.pwdata), 'little')
        await tb.cache_apb_intf.write(0x0000 + (i*tb.incr), bytesdata)
    
    for i in range(tb.n_regs):
        z = randint(0, tb.n_regs-1)
        y = x[z] & tb.mask
        read_op = await tb.cache_apb_intf.read(0x0000 + (z*tb.incr))
        ret = returned_val(read_op)
        assert y == ret
    for i in range(tb.n_regs):
        z = randint(0, tb.n_regs-1)
        y = x[z] & tb.mask
        read_op = await tb.cache_apb_intf.read(0x0000 + (z*tb.incr), y.to_bytes(len(tb.cache_apb_bus.prdata), "little"))
    for i in range(tb.n_regs):
        z = randint(0, tb.n_regs-1)
        y = x[z] & tb.mask
        tb.cache_apb_intf.read_nowait(0x0000 + (z*tb.incr), y.to_bytes(len(tb.cache_apb_bus.prdata), "little"))

#     print('break')
#     await tb.cr.wait_clkn(20)
    for i in range(tb.n_regs):
#         print(i)
        y = x[i] & tb.mask
        read_op = await tb.cache_apb_intf.read(0x0000 + (i*tb.incr))
        ret = returned_val(read_op)
        assert y == ret


    await tb.cr.end_test(200)

async def test_apb_init(dut):
    #yhyang:tb = TB_APB(dut, reset_sense=1)
    tb = TB_APB(dut)

    #yhyang:await tb.cr.wait_clkn(200)
    await tb.cycle_reset()

    addr = 0x0000
    read_op = await tb.cache_apb_intf.read(addr)
    ret = returned_val(read_op)
    #assert 0x0 == ret
    tb.log.info("cache_apb addr: 0x%08x, data: 0x08x", addr, ret)

async def test_apb_sfr_rw_test(dut):
    tb = TB_APB(dut)
    await tb.cycle_reset()

    cache_apb_reg_blk = tb.cache_apb_reg_blk
    for addr, info in cache_apb_reg_blk.items():
        rand_val = randint(0, (2**32)-1)
        if addr in cache_apb_reg_blk:
            cache_apb_reg_blk[addr]["value"] = rand_val
        await tb.cache_apb_intf.write(addr, rand_val)

    for addr, info in cache_apb_reg_blk.items():
        read_op = await tb.cache_apb_intf.read(addr)
        ret = returned_val(read_op)
        if reg_cmp(cache_apb_reg_blk, addr, ret):
            tb.log.info("cache_apb addr: 0x{:08x}, data: 0x{:08x}, golden_val: 0x{:08x}".format(addr, ret, cache_apb_reg_blk[addr]["value"]))
        else:
            tb.log.error("cache_apb addr: 0x{:08x}, data: 0x{:08x}, golden_val: 0x{:08x}".format(addr, ret, cache_apb_reg_blk[addr]["value"]))

async def test_apb_sfr_reset_test(dut):
    tb = TB_APB(dut)
    await tb.cycle_reset()

    cache_apb_reg_blk = tb.cache_apb_reg_blk
    for addr, info in cache_apb_reg_blk.items():
        read_op = await tb.cache_apb_intf.read(addr)
        ret = returned_val(read_op)
        if reg_cmp(cache_apb_reg_blk, addr, ret):
            tb.log.info("cache_apb addr: 0x{:08x}, data: 0x{:08x}, golden_val: 0x{:08x}".format(addr, ret, cache_apb_reg_blk[addr]["value"]))
        else:
            tb.log.error("cache_apb addr: 0x{:08x}, data: 0x{:08x}, golden_val: 0x{:08x}".format(addr, ret, cache_apb_reg_blk[addr]["value"]))
    await Timer(20, 'us')

