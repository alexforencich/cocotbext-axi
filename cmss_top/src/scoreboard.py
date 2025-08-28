import cocotb
from cocotbext.axi import AxiBus
from cocotb.triggers import RisingEdge, Timer
from cocotb_bus.monitors import BusMonitor
from cocotb.queue import Queue
from cocotbext.axi.memory import Memory
from cocotbext.axi.constants import *
import copy

ARCACHE_MAP = {
        ARCACHE_DEVICE_NON_BUFFERABLE: "Device Non-bufferable",
        ARCACHE_DEVICE_BUFFERABLE: "Device Bufferable",
        ARCACHE_NORMAL_NON_CACHEABLE_NON_BUFFERABLE: "Normal Non-cacheable Non-bufferable",
        ARCACHE_NORMAL_NON_CACHEABLE_BUFFERABLE: "Normal Non-cacheable Bufferable",
        ARCACHE_WRITE_THROUGH_NO_ALLOC: "Write-through, No-allocate",
        ARCACHE_WRITE_THROUGH_READ_ALLOC: "Write-through, Read-allocate",
        ARCACHE_WRITE_THROUGH_WRITE_ALLOC: "Write-through, Write-allocate",
        ARCACHE_WRITE_THROUGH_READ_AND_WRITE_ALLOC: "Write-through, Read & Write-allocate",
        ARCACHE_WRITE_BACK_NO_ALLOC: "Write-back, No-allocate",
        ARCACHE_WRITE_BACK_READ_ALLOC: "Write-back, Read-allocate",
        ARCACHE_WRITE_BACK_WRITE_ALLOC: "Write-back, Write-allocate",
        ARCACHE_WRITE_BACK_READ_AND_WRITE_ALLOC: "Write-back, Read & Write-allocate",
    }

class AxiScoreboard:
    def __init__(self, ar_queue, r_queue, aw_queue, w_queue, b_queue,
                test_mode: str = 'full_test', host_mem=None):
        self.log = cocotb.log
        # Golden memory
        if test_mode == 'cache_test':
            self.golden_memory = Memory(size=2**63-1)
        elif test_mode == 'full_test':
            self.golden_memory = copy.deepcopy(host_mem)

        self.aw_signal_queue = aw_queue
        self.w_data_queue = w_queue
        self.ar_signal_queue = ar_queue
        self.r_data_queue = r_queue
        self.b_resp_queue = b_queue

        # Temporarily store AR transactions for read verification (Key: arid)
        self.pending_reads = {}
        self.pending_writes = {}
        self.check_count = 0
        self.pass_count = 0
        self.fail_count = 0
        self.write_count = 0
        self.read_count = 0
        self.pending_arcache = {}
        
        # Internal background process
        self._write_proc = None
        self._read_ar_proc = None
        self._read_r_proc = None
        self._b_proc = None

    def start(self):
        # Start Write/Read background process
        if self._write_proc is None:
            self._write_proc = cocotb.start_soon(self._write_handler())
        
        if self._read_ar_proc is None:
            self._read_ar_proc = cocotb.start_soon(self._ar_handler())

        if self._read_r_proc is None:
            self._read_r_proc = cocotb.start_soon(self._r_handler())
        
        if self._b_proc is None:
            self._b_proc = cocotb.start_soon(self._b_handler())

    def stop(self):
        if self._write_proc is not None and not self._write_proc.done():
            self._write_proc.kill()
        if self._read_ar_proc is not None and not self._read_ar_proc.done():
            self._read_ar_proc.kill()
        if self._read_r_proc is not None and not self._read_r_proc.done():
            self._read_r_proc.kill()
        self.log.info("Scoreboard handlers stopped.")
        total_checks = self.pass_count + self.fail_count
        self.log.info("="*60)
        self.log.info("SCOREBOARD FINAL STATISTICS")
        self.log.info(f"  - Total Checks: {total_checks}")
        self.log.info(f"  - PASSED:     {self.pass_count}")
        self.log.info(f"  - FAILED:     {self.fail_count}")
        self.log.info(f"  - WRITE:     {self.write_count}")
        self.log.info(f"  - READ:     {self.read_count}")
        self.log.info("="*60)

    async def _write_handler(self):
        # Receive AW and W signals and write them to the Golden Memory
        while True:
            # Wait address/data
            aw_trans  = await self.aw_signal_queue.get()
            data = await self.w_data_queue.get()
            # Write Golden Memory
            awid = int(aw_trans['awid'])
            addr = int(aw_trans['awaddr'])
            self.log.info(f"[CORE_WRITE_COMPLETE] WDATA 0x{addr:08X}. Complete WDATA: 0x{(bytes(data)).hex().upper()}")
            if awid not in self.pending_writes:
                self.pending_writes[awid] = []
            self.pending_writes[awid].append({
                "addr": addr,
                "data": data
            })
            self.write_count += 1

    async def _b_handler(self):
        while True:
            b_trans = await self.b_resp_queue.get()
            bid = int(b_trans['bid'])
            bresp = int(b_trans['bresp'])

            if bresp == 0 and bid in self.pending_writes and self.pending_writes[bid]:
                #entry = self.pending_writes.pop(bid)
                entry = self.pending_writes[bid].pop(0)
                addr = entry["addr"]
                data = entry["data"]
                #addr = addr << 6
                self.log.info(f"[CORE_B_MONITOR] B Response for 0x{addr:08X}. Bid: {bid:08X} Complete WDATA: 0x{(bytes(data)).hex().upper()}")
                self.log.info(f"[DEBUG] GOLDEN MEMORY WRITE DATA to 0x{addr:08X} : 0x{data.hex().upper()}")
                self.golden_memory.write(addr, data)

    async def _ar_handler(self):
        # Receive AR signal and record the read request
        while True:
            # Receive the dictionary sent by the AR monitor
            ar_trans = await self.ar_signal_queue.get()
            arid = int(ar_trans['arid']) 
            addr = int(ar_trans['araddr'])
            arcache = int(ar_trans['arcache'])
            self.pending_reads[arid] = addr
            self.pending_arcache[arid] = arcache

    async def _r_handler(self):
        # Receive the R signal and match it with the AR request to verify the final read transaction.
        while True:
            # Receive the dictionary sent by the R monitor
            r_trans = await self.r_data_queue.get()
            self.read_count += 1
            rid = int(r_trans['rid'])
            read_data = bytes(r_trans['rdata'])
            
            # Use RID to find the previously stored AR transaction
            if rid in self.pending_reads:
                araddr = self.pending_reads.pop(rid)
                #araddr = araddr << 6
                expected_data = self.golden_memory.read(araddr, len(read_data))
                self.log.info(f"[DEBUG] GOLDEN MEMORY EXPECTED DATA from 0x{araddr:08X} : 0x{expected_data.hex().upper()}")
                self.check_count += 1
                arcache = self.pending_arcache.pop(rid)
                arcache_type_str = ARCACHE_MAP.get(arcache, f"Unknown ARCACHE value ({arcache})")

                # Compare the actual data with the expected data
                if read_data == expected_data:
                    self.log.info(
                    f"[Scoreboard/Verifier #{self.check_count}] "
                    f"PASSED: Read data matches for ID {rid}, "
                    f"Address: 0x{araddr:08X}, "
                    f"ARCACHE TYPE: {arcache_type_str}"
                )
                    self.log.info(f"  - Expected: 0x{expected_data.hex().upper()}")
                    self.log.info(f"  - Actual:   0x{read_data.hex().upper()}")
                    self.pass_count += 1
                else:
                    self.log.warning(
                    f"[Scoreboard/Verifier #{self.check_count}] "
                    f"FAILED: Read data mismatch for ID {rid}, "
                    f"Address: 0x{araddr:08X}, "
                    f"ARCACHE TYPE: {arcache_type_str}"
                )
                    self.log.warning(f"  - Expected: 0x{expected_data.hex().upper()}")
                    self.log.warning(f"  - Actual:   0x{read_data.hex().upper()}")
                    self.fail_count += 1
                    #assert read_data == expected_data

            else:
                self.log.error(f"[Scoreboard/ERROR] Received R-channel data for unexpected RID: {rid}")
            

class CORE_AW_Signal_Monitor(BusMonitor):
    _signals = ["awvalid", "awready", "awid", "awaddr"]

    def __init__(self, dut, name, clock, reset=None, reset_n=None, callback=None, event=None):
        """Initialization method for Monitor"""
        super().__init__(dut, name, clock, reset=reset, reset_n=reset_n, callback=callback, event=event)
    
    async def _monitor_recv(self):
        """Automatically read data from CORE AW"""
        while True:
            await RisingEdge(self.clock)

            if self.in_reset:
                continue
            
            if self.bus.awvalid.value and self.bus.awready.value:
                #self.log.info("AW Channel Activity Detected by Monitor!")
                aw_trans = {
                    'awid': self.bus.awid.value,
                    'awaddr': self.bus.awaddr.value
                }          
                self._recv(aw_trans)
                #self.log.info(f"[AW_Monitor] Complete AW : AWID : ({aw_trans['awid']}), AWADDR : 0x{aw_trans['awaddr'].hex().upper()}")

class CORE_W_Signal_Monitor(BusMonitor):
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
                wdata_value = self.bus.wdata.value
                #self.log.info(f"[CORE_W_Monitor] WDATA ({len(wdata_value)}B), 0x{wdata_value.hex().upper()}")
                data_bytes = wdata_value.buff
                self.partial_wdata.extend(data_bytes)
                
                if self.bus.wlast.value:
                    self.log.info(f"[CORE_W_Monitor] WDATA ({len(self.partial_wdata)}B), 0x{self.partial_wdata.hex().upper()}")
                    self._recv(bytes(self.partial_wdata))
                    self.partial_wdata.clear()

class CORE_AR_Signal_Monitor(BusMonitor):
    _signals = ["arvalid", "arready", "arid", "araddr", "arcache"]

    def __init__(self, dut, name, clock, reset=None, reset_n=None, callback=None, event=None):
        """Initialization method for Monitor"""
        super().__init__(dut, name, clock, reset=reset, reset_n=reset_n, callback=callback, event=event)
    
    async def _monitor_recv(self):
        """Automatically read data from AR"""
        while True:
            await RisingEdge(self.clock)

            if self.in_reset:
                continue
            
            if self.bus.arvalid.value and self.bus.arready.value:
                #self.log.info("AR Channel Activity Detected by Monitor!")
                transaction = {
                        'arid': self.bus.arid.value,
                        'araddr': self.bus.araddr.value,
                        'arcache' : self.bus.arcache.value
                    }
                self._recv(transaction)
                #self.log.info(f"[AR_Monitor]  ARID:({transaction['arid']}) : ARADDR:({transaction['araddr'].hex().upper()})")

class CORE_R_Signal_Monitor(BusMonitor):
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
                #self.log.info("R Channel Activity Detected by Monitor!")

                rdata_value = self.bus.rdata.value
                rid_value = self.bus.rid.value

                if self.current_rid is None:
                    self.current_rid = rid_value
                    #self.log.info(f"[R_Monitor] New burst started for RID: {self.current_rid}")
                
                data_bytes = rdata_value.buff
                self.partial_rdata.extend(data_bytes)
                
                if self.bus.rlast.value:
                    #self.log.info(f"R Channel Burst Transaction FINISHED for RID: {self.current_rid}")
                    transaction = {
                        'rid': self.bus.rid.value,
                        'rdata': bytes(self.partial_rdata)
                    }
                
                    self._recv(transaction)
                    #self.log.info(f"[CORE_R_Monitor] Complete RDATA ({len(transaction['rdata'])}B), RID:({transaction['rid']}) : 0x{transaction['rdata'].hex().upper()}")
                    self.partial_rdata.clear()
                    self.current_rid = None

class CORE_B_Signal_Monitor(BusMonitor):
    _signals = ["bvalid", "bready", "bid", "bresp"]

    def __init__(self, dut, name, clock, reset=None, reset_n=None, callback=None, event=None):
        """Initialization method for Monitor"""
        super().__init__(dut, name, clock, reset=reset, reset_n=reset_n, callback=callback, event=event)
    
    async def _monitor_recv(self):
        """Automatically read data from Core B"""
        while True:
            await RisingEdge(self.clock)

            if self.in_reset:
                continue
            
            if self.bus.bvalid.value and self.bus.bready.value:
                b_trans = {
                    "bid": self.bus.bid.value,
                    "bresp": self.bus.bresp.value
                    }
                self._recv(b_trans)

class Mem_W_Monitor(BusMonitor):
    _signals = ["wvalid", "wready", "wdata", "wlast"]

    def __init__(self, dut, name, clock, mem_aw_signal_queue, reset=None, reset_n=None, callback=None, event=None):
        """Initialization method for Monitor"""
        super().__init__(dut, name, clock, reset=reset, reset_n=reset_n, callback=callback, event=event)
        self.mem_aw_signal_queue = mem_aw_signal_queue
        self.partial_wdata = bytearray()
        self.collected_beats = []
    
    async def _monitor_recv(self):
        """Automatically read data from W"""
        while True:
            await RisingEdge(self.clock)

            if self.in_reset:
                continue
            
            if self.bus.wvalid.value and self.bus.wready.value:
                
                wdata_value = self.bus.wdata.value
                data_bytes = wdata_value.buff
                self.collected_beats.append(data_bytes)
                
                if self.bus.wlast.value:
                    total_beats = len(self.collected_beats)

                    if total_beats == 3:
                        final_data = b''.join(self.collected_beats[1:])
                    else:
                        final_data = b''.join(self.collected_beats)

                    if final_data:
                        self._recv(final_data)
                        aw_trans = await self.mem_aw_signal_queue.get()
                        mem_addr = int(aw_trans['awaddr'])
                        awid = int(aw_trans['awid'])
                        core_addr = mem_addr//2
                        self.log.info(f"[MEM_W] Transaction finished to 0x{core_addr:08X}. AW ID : {awid:08X} Complete WDATA: 0x{(bytes(final_data)).hex().upper()}")
                    self.collected_beats.clear()

class Mem_AW_Monitor(BusMonitor):
    _signals = ["awvalid", "awready", "awid", "awaddr"]

    def __init__(self, dut, name, clock, reset=None, reset_n=None, callback=None, event=None):
        """Initialization method for Monitor"""
        super().__init__(dut, name, clock, reset=reset, reset_n=reset_n, callback=callback, event=event)

    async def _monitor_recv(self):
        """Automatically read data from W"""
        while True:
            await RisingEdge(self.clock)

            if self.bus.awvalid.value and self.bus.awready.value:
                aw_trans = {
                    'awid': self.bus.awid.value,
                    'awaddr': self.bus.awaddr.value
                }
                core_addr = int(self.bus.awaddr.value)//2
                self.log.info(f"[MEM_AW] Addr: 0x{core_addr:08X}, AW_ID: 0x{int(self.bus.awid.value):08X}")
                self._recv(aw_trans)

class Mem_R_Monitor(BusMonitor):
    _signals = ["rvalid", "rready", "rdata", "rlast"]

    def __init__(self, dut, name, clock, reset=None, reset_n=None, callback=None, event=None):
        """Initialization method for Monitor"""
        super().__init__(dut, name, clock, reset=reset, reset_n=reset_n, callback=callback, event=event)
        self.partial_rdata = bytearray()
        self.beat_count = 0
    
    async def _monitor_recv(self):
        """Automatically read data from W"""
        await Timer(1, 'us')
        while True:
            await RisingEdge(self.clock)

            if self.in_reset:
                continue
            
            if self.bus.rvalid.value and self.bus.rready.value:
                if self.beat_count == 0:
                    #rdata_value = self.bus.rdata.value.buff
                    #self.log.info(f"[MEM_R_Monitor] TransactionRDATA: {((rdata_value)).hex().upper()}")
                    #self.log.info("MEM R Monitor: First beat (metadata) detected and ignored.")
                    pass
                else:
                    #self.log.info(f"MEM W Monitor: Capturing data beat #{self.beat_count}")
                    rdata_value = self.bus.rdata.value
                    data_bytes = rdata_value.buff
                    self.partial_rdata.extend(data_bytes)
                
                if self.bus.rlast.value:
                    #self.log.info(f"[MEM_R_Monitor] Transaction finished. Complete RDATA: {(bytes(self.partial_rdata)).hex().upper()}")
                    if self.partial_rdata:
                        self._recv(bytes(self.partial_rdata))
                    
                    self.partial_rdata.clear()
                    self.beat_count = 0
                else:
                    self.beat_count += 1