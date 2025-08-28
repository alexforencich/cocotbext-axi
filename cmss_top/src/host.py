import cocotb
from cxl_pkg import *
from cocotb.queue import Queue, QueueEmpty
from cocotb.triggers import Timer
import random
from cocotb.binary import BinaryValue

class Counter:
    h2d_rsp_cnt = 0
    h2d_data_hdr_cnt = 0

    @classmethod
    def reset(cls):
        cls.h2d_rsp_cnt = 0
        cls.h2d_data_hdr_cnt = 0

    @classmethod
    def reset_rsp_cnt(cls):
        cls.h2d_rsp_cnt = 0  

    @classmethod
    def get_rsp_cnt(cls):
        return cls.h2d_rsp_cnt
    @classmethod
    def increment_rsp_cnt(cls, value=1):
        cls.h2d_rsp_cnt += value
    @classmethod
    def reset_data_hdr_cnt(cls):
        cls.h2d_data_hdr_cnt = 0  
    @classmethod
    def get_data_hdr_cnt(cls):
        return cls.h2d_data_hdr_cnt
    @classmethod
    def increment_data_hdr_cnt(cls, value):
        cls.h2d_data_hdr_cnt += value

class RspGen:
    def __init__(self, d2h_req_queue, d2h_data_addr_queue, h2d_rsp_queue, h2d_data_hdr_queue, h2d_data_addr_queue):
        self.d2h_req_queue = d2h_req_queue  
        self.h2d_rsp_queue = h2d_rsp_queue
        self.d2h_data_addr_queue = d2h_data_addr_queue
        self.h2d_data_hdr_queue = h2d_data_hdr_queue
        self.h2d_data_addr_queue = h2d_data_addr_queue

    async def request_handler(self):
        while True:
            req = await self.d2h_req_queue.get()
            
            rsp = {}
            data_hdr = {}
            if req.opcode == CXL_D2H_REQ_OPCODE.CXL_D2H_REQ_OPCODE_MEM_WR.value:
                rsp = CXL_FLIT_H2D_RSP_HDR(
                    valid=True,
                    opcode=CXL_H2D_RSP_OPCODE.CXL_H2D_RSP_OPCODE_GO_WRITEPULL.value,
                    rsp_data=CXL_CACHE_STATE_INVALID,
                    cqid=req.cqid,
                )
                addr = req.address
                await self.d2h_data_addr_queue.put(addr)
                await self.h2d_rsp_queue.put(rsp)

            elif req.opcode == CXL_D2H_REQ_OPCODE.CXL_D2H_REQ_OPCODE_RD_CURR.value:
                data_hdr = CXL_FLIT_H2D_DATA_HDR(
                    cqid=req.cqid,
                    valid=True
                )
                addr = req.address
                await self.h2d_data_addr_queue.put(addr)
                await self.h2d_data_hdr_queue.put(data_hdr)

            elif req.opcode == CXL_D2H_REQ_OPCODE.CXL_D2H_REQ_OPCODE_RD_SHARED.value:
                rsp = CXL_FLIT_H2D_RSP_HDR(
                    valid=True,
                    opcode=CXL_H2D_RSP_OPCODE.CXL_H2D_RSP_OPCODE_GO.value,
                    rsp_data=CXL_CACHE_STATE_SHARED,
                    cqid=req.cqid
                )
                addr = req.address
                await self.h2d_data_addr_queue.put(addr)
                await self.h2d_rsp_queue.put(rsp)

                data_hdr = CXL_FLIT_H2D_DATA_HDR(
                    cqid=req.cqid,
                    valid=True
                )
                await self.h2d_data_hdr_queue.put(data_hdr)

            elif req.opcode == CXL_D2H_REQ_OPCODE.CXL_D2H_REQ_OPCODE_CLEAN_EVICT_ND.value:
                rsp = CXL_FLIT_H2D_RSP_HDR(
                    valid=True,
                    opcode=CXL_H2D_RSP_OPCODE.CXL_H2D_RSP_OPCODE_GO.value,
                    rsp_data=CXL_CACHE_STATE_INVALID,
                    cqid=req.cqid
                )
                await self.h2d_rsp_queue.put(rsp)

            elif req.opcode == CXL_D2H_REQ_OPCODE.CXL_D2H_REQ_OPCODE_DIRTY_EVICT.value:
                rsp = CXL_FLIT_H2D_RSP_HDR(
                    valid=True,
                    opcode=CXL_H2D_RSP_OPCODE.CXL_H2D_RSP_OPCODE_GO_WRITEPULL.value,
                    rsp_data=CXL_CACHE_STATE_INVALID,
                    cqid=req.cqid
                )
                await self.h2d_rsp_queue.put(rsp)

            elif req.opcode == CXL_D2H_REQ_OPCODE.CXL_D2H_REQ_OPCODE_RD_OWN_ND.value:
                rsp = CXL_FLIT_H2D_RSP_HDR(
                    valid=True,
                    opcode=CXL_H2D_RSP_OPCODE.CXL_H2D_RSP_OPCODE_GO.value,
                    rsp_data=CXL_CACHE_STATE_EXCLUSIVE,
                    cqid=req.cqid
                )
                await self.h2d_rsp_queue.put(rsp)

            else:
                print(f"Unknown Opcode: {req.opcode}")

class ConstructFlitPayload:
    @staticmethod
    def construct_flit_payload(slot0_type, slot1_type, slot2_type, slot3_type, 
                            slot0_data, slot1_data, slot2_data, slot3_data,
                            ):

        # Generate FLIT Header
        flit_hdr = CXL_PROTOCOL_FLIT_HDR(
            slot0=slot0_type,
            slot1=slot1_type,
            slot2=slot2_type,
            slot3=slot3_type
        )

        # Generate FLIT Payload 
        payload = CXL_PROTOCOL_FLIT_PLD(
            slot0=slot0_data,
            slot1=slot1_data,
            slot2=slot2_data,
            slot3=slot3_data,
            flit_hdr=flit_hdr
        )
        return payload


class ConstructG1:
    def __init__(self, h2d_rsp_queue):
        self.h2d_rsp_queue = h2d_rsp_queue

    async def construct_g1(self):
        slot_g1 = CXL_DNFLIT_SLOT_G1(
            h2d_rsp3=CXL_FLIT_H2D_RSP_HDR(),
            h2d_rsp2=CXL_FLIT_H2D_RSP_HDR(),
            h2d_rsp1=CXL_FLIT_H2D_RSP_HDR(),
            h2d_rsp0=CXL_FLIT_H2D_RSP_HDR()
        )

        if Counter.get_rsp_cnt() < 4:
            try:
                slot_g1.h2d_rsp0 = self.h2d_rsp_queue.get_nowait()
                Counter.increment_rsp_cnt()
                if Counter.get_rsp_cnt() >= 4:
                    return slot_g1
            except QueueEmpty:
                pass

            try:
                slot_g1.h2d_rsp1 = self.h2d_rsp_queue.get_nowait()
                Counter.increment_rsp_cnt()
                if Counter.get_rsp_cnt() >= 4:
                    return slot_g1
            except QueueEmpty:
                pass

            try:
                slot_g1.h2d_rsp2 = self.h2d_rsp_queue.get_nowait()
                Counter.increment_rsp_cnt()
                if Counter.get_rsp_cnt() >= 4:
                    return slot_g1
            except QueueEmpty:
                pass

            try:
                slot_g1.h2d_rsp3 = self.h2d_rsp_queue.get_nowait()
                Counter.increment_rsp_cnt()
                if Counter.get_rsp_cnt() >= 4:
                    return slot_g1
            except QueueEmpty:
                pass

        return slot_g1

def make_data_slot(data_bytes: bytes) -> list[int]:
    value = int.from_bytes(data_bytes, byteorder='big')
    words = []
    for i in range(4):
        # little-endian: LSB first
        shift = i * 128

        word = (value >> shift) & ((1 << 128) - 1)

        words.append(word)
    return words

class ConstructH3:
    def __init__(self, h2d_data_queue, rollover_data_queue):
        self.h2d_data_queue = h2d_data_queue
        self.rollover_data_queue = rollover_data_queue

    async def construct_h3(self):
        slot_h3 = CXL_DNFLIT_SLOT_H3()

        try:
            h2d_data_hdr, h2d_data = self.h2d_data_queue.get_nowait()
            data_slot = make_data_slot(h2d_data)
            slot_h3.h2d_data0 = h2d_data_hdr
            for slot in data_slot:
                await self.rollover_data_queue.put(slot)
        except QueueEmpty:
            pass

        try:
            h2d_data_hdr, h2d_data = self.h2d_data_queue.get_nowait()
            data_slot = make_data_slot(h2d_data)
            slot_h3.h2d_data1 = h2d_data_hdr
            for slot in data_slot:
                await self.rollover_data_queue.put(slot)
        except QueueEmpty:
            pass

        try:
            h2d_data_hdr, h2d_data = self.h2d_data_queue.get_nowait()
            data_slot = make_data_slot(h2d_data)
            slot_h3.h2d_data2 = h2d_data_hdr
            for slot in data_slot:
                await self.rollover_data_queue.put(slot)
        except QueueEmpty:
            pass

        try:
            h2d_data_hdr, h2d_data = self.h2d_data_queue.get_nowait()
            data_slot = make_data_slot(h2d_data)
            slot_h3.h2d_data3 = h2d_data_hdr
            for slot in data_slot:
                await self.rollover_data_queue.put(slot)
        except QueueEmpty:
            pass

        return slot_h3

class FlitGen:
    def __init__(self, h2d_rsp_queue, h2d_data_queue, flit_output_queue):
        self.h2d_rsp_queue = h2d_rsp_queue
        self.h2d_data_queue = h2d_data_queue
        self.flit_output_queue = flit_output_queue
    
    async def generate_flit(self):
        x_flag = False
        rollover_data_queue = Queue()

        while True:
            flit_payload = None

            if not self.h2d_rsp_queue.empty() or not self.h2d_data_queue.empty():
                x_flag = False
                h2d_rsp1 = None
                flit_payload = CXL_PROTOCOL_FLIT_PLD()
                if rollover_data_queue.qsize() < 4: # No All-data-flit
                    if not self.h2d_rsp_queue.empty():
                        h2d_rsp0 = await self.h2d_rsp_queue.get()
                        Counter.increment_rsp_cnt(1)
                        if not self.h2d_rsp_queue.empty():
                            h2d_rsp1 = await self.h2d_rsp_queue.get()
                        if not self.h2d_data_queue.empty():
                            h2d_data_hdr, h2d_data = await self.h2d_data_queue.get()
                            data_slot = make_data_slot(h2d_data)

                            slot0 = CXL_DNFLIT_SLOT_H1(
                                rsvd=0,
                                h2d_rsp0=h2d_rsp0.pack(),
                                h2d_rsp1=h2d_rsp1.pack() if h2d_rsp1 is not None else 0,
                                h2d_data=h2d_data_hdr.pack() if h2d_data_hdr is not None else 0
                            )
                            flit_payload = ConstructFlitPayload.construct_flit_payload(
                                    SLOT_T_H.H1.value, SLOT_T_G.G0.value, SLOT_T_G.G0.value, SLOT_T_G.G0.value,
                                    slot0.pack(), 
                                    data_slot[0],
                                    data_slot[1],
                                    data_slot[2]
                                )
                            await rollover_data_queue.put(data_slot[3])

                        else: # No Data Header
                            slot0 = CXL_DNFLIT_SLOT_H1(
                                rsvd=0,
                                h2d_rsp0=h2d_rsp0.pack(),
                                h2d_rsp1=h2d_rsp1.pack() if h2d_rsp1 is not None else 0,
                                h2d_data=0
                            )
                            if rollover_data_queue.qsize() == 0:
                                slot1 = await ConstructG1(self.h2d_rsp_queue).construct_g1()
                                flit_payload = ConstructFlitPayload.construct_flit_payload(
                                    SLOT_T_H.H1.value, SLOT_T_G.G1.value, SLOT_T_G.G1.value, SLOT_T_G.G1.value,
                                    slot0.pack(),
                                    slot1.pack(), 
                                    0, 
                                    0
                                )
                            elif rollover_data_queue.qsize() == 1:
                                slot2 = ConstructG1(self.h2d_rsp_queue).construct_g1()
                                rollover_data0 = await rollover_data_queue.get()
                                flit_payload = ConstructFlitPayload.construct_flit_payload(
                                    SLOT_T_H.H1.value, SLOT_T_G.G0.value, SLOT_T_G.G1.value, SLOT_T_G.G1.value,
                                    slot0.pack(),
                                    rollover_data0,
                                    slot2.pack(), 
                                    bytes(16)
                                )
                            elif rollover_data_queue.qsize() == 2:
                                slot3 = ConstructG1(self.h2d_rsp_queue).construct_g1()
                                rollover_data0 = await rollover_data_queue.get()
                                rollover_data1 = await rollover_data_queue.get()
                                flit_payload = ConstructFlitPayload.construct_flit_payload(
                                    SLOT_T_H.H1.value, SLOT_T_G.G0.value, SLOT_T_G.G1.value, SLOT_T_G.G1.value,
                                    slot0.pack(),
                                    rollover_data0, 
                                    rollover_data1, 
                                    slot3.pack()
                                )
                            elif rollover_data_queue.qsize() == 3:
                                rollover_data0 = await rollover_data_queue.get()
                                rollover_data1 = await rollover_data_queue.get()
                                rollover_data2 = await rollover_data_queue.get()
                                flit_payload = ConstructFlitPayload.construct_flit_payload(
                                    SLOT_T_H.H1.value, SLOT_T_G.G0.value, SLOT_T_G.G1.value, SLOT_T_G.G1.value,
                                    slot0.pack(),
                                    rollover_data0, 
                                    rollover_data1, 
                                    rollover_data2
                                )
                    else: # No Rsp
                        if self.h2d_data_queue.qsize() > 1:
                            slot0 = CXL_DNFLIT_SLOT_H3.construct_h3(self.h2d_data_queue, rollover_data_queue)
                            rollover_data0 = await rollover_data_queue.get()
                            rollover_data1 = await rollover_data_queue.get()
                            rollover_data2 = await rollover_data_queue.get()

                            flit_payload = ConstructFlitPayload.construct_flit_payload(
                                    SLOT_T_H.H3.value, SLOT_T_G.G0.value, SLOT_T_G.G1.value, SLOT_T_G.G1.value,
                                    slot0.pack(), 
                                    rollover_data0,
                                    rollover_data1,
                                    rollover_data2
                                )
                        else: # 1 data hdr
                            h2d_data_hdr, h2d_data = await self.h2d_data_queue.get()
                            data_slot = make_data_slot(h2d_data)

                            slot0 = CXL_DNFLIT_SLOT_H1(
                                rsvd=0,
                                h2d_rsp0=0,
                                h2d_rsp1=0,
                                h2d_data=h2d_data_hdr.pack() if h2d_data_hdr is not None else 0
                            )
                            flit_payload = ConstructFlitPayload.construct_flit_payload(
                                    SLOT_T_H.H1.value, SLOT_T_G.G0.value, SLOT_T_G.G0.value, SLOT_T_G.G0.value,
                                    slot0.pack(),
                                    (data_slot[0]),
                                    (data_slot[1]),
                                    (data_slot[2])
                                )
                            await rollover_data_queue.put(data_slot[3])
                else: #All Data Flit
                    rollover_data0 = await rollover_data_queue.get()
                    rollover_data1 = await rollover_data_queue.get()
                    rollover_data2 = await rollover_data_queue.get()
                    rollover_data3 = await rollover_data_queue.get()
                    flit_payload=CXL_ALL_DATA_FLIT_PLD(
                        rollover_data0,
                        rollover_data1,
                        rollover_data2,
                        rollover_data3
                    )
            else: # No rsp, data hdr
                if (rollover_data_queue.qsize() > 3): #All Data Flit
                    rollover_data0 = await rollover_data_queue.get()
                    rollover_data1 = await rollover_data_queue.get()
                    rollover_data2 = await rollover_data_queue.get()
                    rollover_data3 = await rollover_data_queue.get()
                    flit_payload=CXL_ALL_DATA_FLIT_PLD(
                        rollover_data0,
                        rollover_data1,
                        rollover_data2,
                        rollover_data3
                    )
                elif (rollover_data_queue.qsize() == 3):
                    rollover_data0 = await rollover_data_queue.get()
                    rollover_data1 = await rollover_data_queue.get()
                    rollover_data2 = await rollover_data_queue.get()
                    flit_payload = ConstructFlitPayload.construct_flit_payload(
                                    SLOT_T_H.H1.value, SLOT_T_G.G0.value, SLOT_T_G.G0.value, SLOT_T_G.G0.value,
                                    0, # 96-bit 0
                                    rollover_data0,
                                    rollover_data1, 
                                    rollover_data2
                                )
                elif (rollover_data_queue.qsize() == 2):
                    rollover_data0 = await rollover_data_queue.get()
                    rollover_data1 = await rollover_data_queue.get()
                    flit_payload = ConstructFlitPayload.construct_flit_payload(
                                    SLOT_T_H.H1.value, SLOT_T_G.G0.value, SLOT_T_G.G0.value, SLOT_T_G.G2.value,
                                    0, # 96-bit 0
                                    rollover_data0,
                                    rollover_data1, 
                                    0 # 128-bit 0
                                )
                elif (rollover_data_queue.qsize() == 1):
                    rollover_data0 = await rollover_data_queue.get()
                    flit_payload = ConstructFlitPayload.construct_flit_payload(
                                    SLOT_T_H.H1.value, SLOT_T_G.G0.value, SLOT_T_G.G2.value, SLOT_T_G.G2.value,
                                    0, # 96-bit 0
                                    rollover_data0,
                                    0, # 128-bit 0
                                    0 # 128-bit 0
                                )
            if flit_payload is not None:
                await self.flit_output_queue.put(flit_payload)
            else:
                await Timer(1, "ns")