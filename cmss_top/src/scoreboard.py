import cocotb
from cocotbext.axi import AxiBus
from cocotb.triggers import RisingEdge
from cocotb_bus.monitors import BusMonitor
from cocotb.queue import Queue
from cocotbext.axi.memory import Memory



class AxiScoreboard:
    def __init__(self, ar_queue, r_queue, aw_queue, w_queue, mem):
        self.log = cocotb.log
        
        # Golden memory
        #self.golden_memory = Memory(size=2**20)
        self.golden_memory = mem

        self.aw_signal_queue = aw_queue
        self.w_data_queue = w_queue
        self.ar_signal_queue = ar_queue
        self.r_data_queue = r_queue

        # Temporarily store AR transactions for read verification (Key: arid)
        self.pending_reads = {}
        
        # Internal background process
        self._write_proc = None
        self._read_ar_proc = None
        self._read_r_proc = None

    def start(self):
        # Start Write/Read background process
        if self._write_proc is None:
            self._write_proc = cocotb.start_soon(self._write_handler())
        
        if self._read_ar_proc is None:
            self._read_ar_proc = cocotb.start_soon(self._ar_handler())

        if self._read_r_proc is None:
            self._read_r_proc = cocotb.start_soon(self._r_handler())

    def stop(self):
        if self._write_proc is not None and not self._write_proc.done():
            self._write_proc.kill()
        if self._read_ar_proc is not None and not self._read_ar_proc.done():
            self._read_ar_proc.kill()
        if self._read_r_proc is not None and not self._read_r_proc.done():
            self._read_r_proc.kill()
        self.log.info("Scoreboard handlers stopped.")

    async def _write_handler(self):
        # Receive AW and W signals and write them to the Golden Memory
        while True:
            # Wait address/data
            address = await self.aw_signal_queue.get()
            data = await self.w_data_queue.get()
            # Write Golden Memory
            # self.golden_memory.write(address, data)
    
    async def _ar_handler(self):
        # Receive AR signal and record the read request
        while True:
            # Receive the dictionary sent by the AR monitor
            ar_trans = await self.ar_signal_queue.get()
            arid = int(ar_trans['arid']) 
            araddr = ar_trans['araddr']
            
            # Store the address to match with R channel data later
            self.pending_reads[arid] = araddr
            self.log.info(f"[Scoreboard/AR] Pending Read Request logged for ARID: {arid} at Addr: 0x{araddr.hex().upper()}")

    async def _r_handler(self):
        # Receive the R signal and match it with the AR request to verify the final read transaction.
        while True:
            # Receive the dictionary sent by the R monitor
            r_trans = await self.r_data_queue.get()
            rid = int(r_trans['rid'])
            rdata = r_trans['rdata']
            actual_data = bytes(r_trans['rdata'])
            
            # Use RID to find the previously stored AR transaction
            if rid in self.pending_reads:
                araddr = self.pending_reads.pop(rid)
                self.log.info(f"[Scoreboard/Read Matched] Read from Addr 0x{araddr.hex().upper()} (ID: {rid}) returned {(rdata.hex().upper())}.")
                read_data = self.golden_memory.read(araddr, len(actual_data))

                first = read_data[0:32]
                second = read_data[32:64]

                expected_data = first[::-1] + second[::-1]

                # Compare the actual data with the expected data
                if actual_data == expected_data:
                    self.log.info(f"  - Expected: 0x{expected_data.hex().upper()}")
                    self.log.info(f"  - Actual:   0x{actual_data.hex().upper()}")
                    self.log.info(f"[Scoreboard/Verifier] PASSED: Read data matches for ID {rid}.")
                else:
                    self.log.warning(f"[Scoreboard/Verifier] FAILED: Read data mismatch for ID {rid}.")
                    self.log.warning(f"  - Expected: 0x{expected_data.hex().upper()}")
                    self.log.warning(f"  - Actual:   0x{actual_data.hex().upper()}")
                    # assert actual_data == expected_data

            else:
                self.log.error(f"[Scoreboard/ERROR] Received R-channel data for unexpected RID: {rid}")
            

class AW_Signal_Monitor(BusMonitor):
    _signals = ["awvalid", "awid", "awaddr"]

    def __init__(self, dut, name, clock, reset=None, reset_n=None, callback=None, event=None):
        """Initialization method for Monitor"""
        super().__init__(dut, name, clock, reset=reset, reset_n=reset_n, callback=callback, event=event)
    
    async def _monitor_recv(self):
        """Automatically read data from CORE AW"""
        while True:
            await RisingEdge(self.clock)

            if self.in_reset:
                continue
            
            if self.bus.awvalid.value:
                self.log.info("AW Channel Activity Detected by Monitor!")
                awid = self.bus.awid.value
                awaddr = self.bus.awaddr.value            
                self._recv(self.bus.awaddr.value)
                self.log.info(f"[AW_Monitor] Complete AW : AWID : ({awid}), AWADDR : 0x{awaddr.hex().upper()}")

class W_Signal_Monitor(BusMonitor):
    _signals = ["wvalid", "wready", "wdata", "wlast"]

    def __init__(self, dut, name, clock, reset=None, reset_n=None, callback=None, event=None):
        """Initialization method for Monitor"""
        super().__init__(dut, name, clock, reset=reset, reset_n=reset_n, callback=callback, event=event)
        self.partial_wdata = bytearray()
    
    async def _monitor_recv(self):
        """Automatically read data from W"""
        while True:
            await RisingEdge(self.clock)

            if self.in_reset:
                continue
            
            if self.bus.wvalid.value and self.bus.wready.value:
                self.log.info("W Channel Activity Detected by Monitor!")

                wdata_value = self.bus.wdata.value
                
                data_bytes = wdata_value.buff
                self.partial_wdata.extend(data_bytes)
                
                if self.bus.wlast.value:
                
                    self._recv(bytes(self.partial_wdata))
                    self.log.info(f"[W_Monitor] Complete WDATA {(bytes(self.partial_wdata)).hex().upper()}")
                    self.partial_wdata.clear()

class AR_Signal_Monitor(BusMonitor):
    _signals = ["arvalid", "arid", "araddr"]

    def __init__(self, dut, name, clock, reset=None, reset_n=None, callback=None, event=None):
        """Initialization method for Monitor"""
        super().__init__(dut, name, clock, reset=reset, reset_n=reset_n, callback=callback, event=event)
    
    async def _monitor_recv(self):
        """Automatically read data from AR"""
        while True:
            await RisingEdge(self.clock)

            if self.in_reset:
                continue
            
            if self.bus.arvalid.value:
                self.log.info("AR Channel Activity Detected by Monitor!")
                transaction = {
                        'arid': self.bus.arid.value,
                        'araddr': self.bus.araddr.value
                    }          
                self._recv(transaction)
                self.log.info(f"[AR_Monitor]  ARID:({transaction['arid']}) : ARADDR:({transaction['araddr'].hex().upper()}")

class R_Signal_Monitor(BusMonitor):
    _signals = ["rvalid", "rid", "rdata", "rresp", "rlast"]

    def __init__(self, dut, name, clock, reset=None, reset_n=None, callback=None, event=None):
        """Initialization method for Monitor"""
        super().__init__(dut, name, clock, reset=reset, reset_n=reset_n, callback=callback, event=event)
        self.partial_rdata = bytearray()
        self.current_rid = None
    
    async def _monitor_recv(self):
        """Automatically read data output from CORE R"""
        while True:
            await RisingEdge(self.clock)

            if self.in_reset:
                continue
            
            if self.bus.rvalid.value:
                self.log.info("R Channel Activity Detected by Monitor!")

                rdata_value = self.bus.rdata.value
                rid_value = self.bus.rid.value

                if self.current_rid is None:
                    self.current_rid = rid_value
                    self.log.info(f"[R_Monitor] New burst started for RID: {self.current_rid}")
                
                data_bytes = rdata_value.buff
                self.partial_rdata.extend(data_bytes)
                
                if self.bus.rlast.value:
                    self.log.info(f"R Channel Burst Transaction FINISHED for RID: {self.current_rid}")
                    transaction = {
                        'rid': self.bus.rid.value,
                        'rdata': bytes(self.partial_rdata)
                    }
                
                    self._recv(transaction)
                    self.log.info(f"[R_Monitor] Complete RDATA ({len(transaction['rdata'])}B), RID:({transaction['rid']}) : 0x{transaction['rdata'].hex().upper()}")
                    self.partial_rdata.clear()
                    self.current_rid = None
