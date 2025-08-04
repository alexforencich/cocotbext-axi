from cocotb.triggers import RisingEdge, Timer
from cocotb_bus.drivers import BusDriver
from cocotb_bus.monitors import BusMonitor
from queue import Queue
from cocotb.binary import BinaryValue
from pack import apply_crc
from cxl_pkg import *


# Driver: Send FLIT to DUT via 'phy_rx_if'
class PIPE_RX_Driver(BusDriver):
    """Cocotb Driver for PIPE_IF RX Interface (Sending FLITs to DUT)"""

    _signals = ["phy_rxdata", "phy_rxdata_valid"]

    def __init__(self, dut, name , aclk):
        BusDriver.__init__(self, dut, name, aclk)
        self.aclk = aclk

    
    async def _driver_send(self, value, sync=True):
        """Send FLIT data through PIPE RX interface"""
        if sync:
            await RisingEdge(self.aclk)
        
        data, valid = value

        self.bus.phy_rxdata.value = data
        self.bus.phy_rxdata_valid.value = valid

        await RisingEdge(self.aclk) # Hold for 1 clock cycle then release


class PIPE_TX_Monitor(BusMonitor):
    """Monitor that automatically detects data from DUT"""
    _signals = ["phy_txdata", "phy_txdata_valid"]

    def __init__(self, dut, name, clock, reset=None, reset_n=None, callback=None, event=None):
        """Initialization method for Monitor"""
        super().__init__(dut, name, clock, reset=reset, reset_n=reset_n, callback=callback, event=event)

    async def _monitor_recv(self):
        """Automatically read data output from DUT"""
        while True:
            await RisingEdge(self.clock) 

            if self.in_reset:
                continue
            txvalid     = self.bus.phy_txdata_valid.value
            txdata      = self.bus.phy_txdata.value

            txvalid_str = txvalid.binstr 
            txdata_str  = txdata.binstr 

            if "X" in txvalid_str or "Z" in txvalid_str or "U" in txvalid_str or txvalid_str == "0000":
                continue
            if "x" in txdata_str or "Z" in txdata_str or "U" in txdata_str:
                continue

            if self.bus.phy_txdata_valid.value:
                self._recv(self.bus.phy_txdata.value.buff)

async def process_flit_queue(pipe_driver, flit_queue):
    """Background coroutine that fetches FLITs from flit_queue and sends them via pipe_driver"""
    dummy_sent = False
    while True:
        await Timer(1, "ns") 
        
        if not flit_queue.empty():
            flit = await flit_queue.get()
            
            if isinstance(flit, BinaryValue):
                flit_data = BinaryValue("X" * 528)
                pipe_driver.append((flit_data, 0))
            else:
                flit_data = apply_crc(flit.pack(), CXL_CRC_COEFF)
                pipe_driver.append((flit_data, 1))
            dummy_sent = False
        elif not dummy_sent:
            dummy_flit = BinaryValue("X" * 528, n_bits=528)
            pipe_driver.append((dummy_flit, 0))
            dummy_sent = True