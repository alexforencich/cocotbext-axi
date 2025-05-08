#!/usr/bin/env python
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from cocotb.triggers import Timer
import cocotb
from cocotbext.axi.constants import *

from cocotb.queue import Queue
from pipe_driver import PIPE_RX_Driver, PIPE_TX_Monitor, process_flit_queue
from host import RspGen, FlitGen
from unpack import Unpack
from pack import *
from cxl_pkg import *
from cmss_axi_sequence import *

from host_master import HostMemoryInterface, HostWriteData, HostReadData
from cocotbext.axi.memory import Memory

@cocotb.test()
async def test_wrapper(dut):
    pipe_driver = PIPE_RX_Driver(dut, '', dut.aclk)
    d2h_req_queue  = Queue()
    d2h_rsp_queue  = Queue()
    d2h_data_queue = Queue()
    d2h_data_slot_queue = Queue()
    d2h_data_addr_queue = Queue()
    s2m_drs_queue  = Queue()
    s2m_ndr_queue  = Queue()
    h2d_rsp_queue = Queue()
    h2d_data_queue = Queue()
    h2d_data_addr_queue = Queue()
    flit_input_queue = Queue()
    h2d_data_hdr_queue = Queue()
    flit_queue = Queue()
    unpacker = Unpack(flit_input_queue, d2h_req_queue, d2h_data_queue, d2h_data_slot_queue)
    rspgen = RspGen(d2h_req_queue, d2h_data_addr_queue, h2d_rsp_queue, h2d_data_hdr_queue, h2d_data_addr_queue)
    flitgen = FlitGen(h2d_rsp_queue, h2d_data_queue, flit_queue)
    monitor = PIPE_TX_Monitor(dut, "", dut.aclk)
    def monitor_callback(transaction):
        flit_input_queue.put_nowait(transaction)

    mem = Memory(size=2**20)
    for addr in range(0, 2**20, 64):
        rand_data = bytearray([random.randint(0, 255) for _ in range(64)])
        mem.write(addr, rand_data)

    host_interface = HostMemoryInterface(mem)

    HostWriteAdapter = HostWriteData(
        d2h_data_queue=d2h_data_queue,
        d2h_data_addr_queue=d2h_data_addr_queue,
        d2h_data_slot_queue=d2h_data_slot_queue,
        host_interface=host_interface
    )
    HostReadAdapter = HostReadData(
        h2d_data_hdr_queue = h2d_data_hdr_queue,
        h2d_data_queue = h2d_data_queue,
        h2d_data_addr_queue = h2d_data_addr_queue,
        host_interface = host_interface
    )
    monitor.add_callback(monitor_callback)
    cocotb.start_soon(HostWriteAdapter.process())
    cocotb.start_soon(HostReadAdapter.process())
    cocotb.start_soon(unpacker.run_unpacker())
    cocotb.start_soon(rspgen.request_handler())
    cocotb.start_soon(flitgen.generate_flit())
    cocotb.start_soon(process_flit_queue(pipe_driver, flit_queue))

    await Timer(1, "ns")

    """RANDOM AXI"""
    golden_value = await axi_random_access(dut)

    await Timer(300, "ns")
    # for addr, expected_data in golden_value.items():
    #     read_data = await host_interface.read(addr, len(expected_data))
    #     assert read_data == expected_data, \
    #         f"[ERROR] Mismatch at addr=0x{addr:08X}\nExpected: {expected_data.hex()}\nRead: {read_data.hex()}"
    #     cocotb.log.info(f"[PASS] Addr 0x{addr:08X}\nExpected: {expected_data.hex()}\nRead: {read_data.hex()} ")
