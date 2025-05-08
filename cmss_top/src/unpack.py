from cocotb.queue import Queue
from cxl_pkg import *

class Unpack:
    def __init__(self, flit_input_queue, d2h_req_queue, d2h_data_queue, d2h_data_slot_queue):
        self.d2h_req_queue          = d2h_req_queue
        self.d2h_rsp_queue          = Queue()
        self.d2h_data_queue         = d2h_data_queue
        self.s2m_drs_queue          = Queue()
        self.s2m_ndr_queue          = Queue()
        self.d2h_data_slot_queue    = d2h_data_slot_queue
        self.flit_input_queue       = flit_input_queue
        self.rollover_cnt           = {"value": 0}
        

        self.flit_parser    = CXLFlitParser(
            self.d2h_req_queue, self.d2h_rsp_queue, self.d2h_data_queue, self.s2m_drs_queue, self.s2m_ndr_queue,
            self.d2h_data_slot_queue
        )
        self.unpack_slot_h  = UnpackSlotH(
            self.d2h_req_queue, self.d2h_rsp_queue, self.d2h_data_queue, self.s2m_drs_queue, self.s2m_ndr_queue,
            self.rollover_cnt
        )
        self.unpack_slot_g  = UnpackSlotG(
            self.d2h_req_queue, self.d2h_rsp_queue, self.d2h_data_queue, self.s2m_drs_queue, self.s2m_ndr_queue,
            self.d2h_data_slot_queue, self.rollover_cnt
        )

    async def run_unpacker(self):
        while True:
            flit_data = await self.flit_input_queue.get()
            if self.rollover_cnt["value"] < 4:
                await self.unpack_flit(flit_data)
            else:
                # All-data-flit
                for i in range(4):
                    shift = (3 - i) * 128  # big-endian 순서
                    word = (flit_data >> shift) & ((1 << 128) - 1)
                    await self.d2h_data_slot_queue.put(word)

    async def unpack_flit(self, flit_data:bytes):
        slots = await self.flit_parser.parse_flit(flit_data)
        if slots["flit_hdr"].flit_type == 1:
            return
        for i in range(4):
            slot_type = slots[f"slot{i}"]["type"]
            slot_data = slots[f"slot{i}"]["data"]
            unpack_slot = self.unpack_slot_h if i == 0 else self.unpack_slot_g

            await unpack_slot.unpack_slot(slot_type, slot_data)


class CXLFlitParser:
    def __init__(self, d2h_req_queue, d2h_rsp_queue, d2h_data_queue,
                d2h_data_slot_queue, s2m_drs_queue, s2m_ndr_queue):
        self.d2h_req_queue          = d2h_req_queue
        self.d2h_rsp_queue          = d2h_rsp_queue
        self.d2h_data_queue         = d2h_data_queue
        self.d2h_data_slot_queue    = d2h_data_slot_queue
        self.s2m_drs_queue          = s2m_drs_queue
        self.s2m_ndr_queue          = s2m_ndr_queue

    async def parse_flit(self, flit_data:bytes):
        payload                     = CXL_FLIT.unpack(flit_data)
        payload_unpack              = CXL_PROTOCOL_FLIT_PLD.unpack(payload)
        flit_hdr = payload_unpack.flit_hdr
        slots = {
            "flit_hdr": flit_hdr,
            "slot0": {"type": flit_hdr.slot0, "data": payload_unpack.slot0},
            "slot1": {"type": flit_hdr.slot1, "data": payload_unpack.slot1},
            "slot2": {"type": flit_hdr.slot2, "data": payload_unpack.slot2},
            "slot3": {"type": flit_hdr.slot3, "data": payload_unpack.slot3}
        }
        return slots

class UnpackSlotH:
    def __init__(self, d2h_req_queue, d2h_rsp_queue, d2h_data_queue, s2m_drs_queue, s2m_ndr_queue, rollover_cnt):
        self.d2h_req_queue      = d2h_req_queue
        self.d2h_rsp_queue      = d2h_rsp_queue
        self.d2h_data_queue     = d2h_data_queue
        self.s2m_drs_queue      = s2m_drs_queue
        self.s2m_ndr_queue      = s2m_ndr_queue
        self.rollover_cnt       = rollover_cnt

    async def unpack_slot(self, slot_type, slot_data):
        if slot_type == 0:  # H0
            slot        = CXL_UPFLIT_SLOT_H0.unpack(slot_data)
            s2m_ndr     = CXL_FLIT_S2M_NDR_HDR.unpack(slot.s2m_ndr)
            d2h_rsp1    = CXL_FLIT_D2H_RSP_HDR.unpack(slot.d2h_rsp1)
            d2h_rsp0    = CXL_FLIT_D2H_RSP_HDR.unpack(slot.d2h_rsp0)
            d2h_data    = CXL_FLIT_D2H_DATA_HDR.unpack(slot.d2h_data)

            if s2m_ndr.valid:
                await self.s2m_ndr_queue.put(s2m_ndr)
            if d2h_rsp1.valid:
                await self.d2h_rsp_queue.put(d2h_rsp1)
            if d2h_rsp0.valid:
                await self.d2h_rsp_queue.put(d2h_rsp0)
            if d2h_data.valid:
                self.rollover_cnt["value"] += 4
                await self.d2h_data_queue.put(d2h_data)

        elif slot_type == 1:  # H1
            slot        = CXL_UPFLIT_SLOT_H1.unpack(slot_data)
            d2h_data    = CXL_FLIT_D2H_DATA_HDR.unpack(slot.d2h_data)
            d2h_req     = CXL_FLIT_D2H_REQ_HDR.unpack(slot.d2h_req)
            if d2h_data.valid:
                self.rollover_cnt["value"] += 4
                await self.d2h_data_queue.put(d2h_data)
            if d2h_req.valid:
                await self.d2h_req_queue.put(d2h_req)

        elif slot_type == 2:  # H2
            slot        = CXL_UPFLIT_SLOT_H2.unpack(slot_data)
            d2h_rsp     = CXL_FLIT_D2H_RSP_HDR.unpack(slot.d2h_rsp)
            d2h_data3   = CXL_FLIT_D2H_DATA_HDR.unpack(slot.d2h_data0)
            d2h_data2   = CXL_FLIT_D2H_DATA_HDR.unpack(slot.d2h_data1)
            d2h_data1   = CXL_FLIT_D2H_DATA_HDR.unpack(slot.d2h_data2)
            d2h_data0   = CXL_FLIT_D2H_DATA_HDR.unpack(slot.d2h_data3)

            if d2h_rsp.valid:
                await self.d2h_rsp_queue.put(d2h_rsp)
            if d2h_data3.valid:
                await self.d2h_data_queue.put(d2h_data3)
            if d2h_data2.valid:
                await self.d2h_data_queue.put(d2h_data2)
            if d2h_data1.valid:
                await self.d2h_data_queue.put(d2h_data1)
            if d2h_data0.valid:
                await self.d2h_data_queue.put(d2h_data0)

        elif slot_type == 3:  # H3
            slot        = CXL_UPFLIT_SLOT_H3.unpack(slot_data)
            s2m_ndr     = CXL_FLIT_S2M_NDR_HDR.unpack(slot.s2m_ndr)
            s2m_drs     = CXL_FLIT_S2M_DRS_HDR.unpack(slot.s2m_drs)

            if s2m_ndr.valid:
                await self.s2m_ndr_queue.put(s2m_ndr)
            if s2m_drs.valid:
                await self.s2m_drs_queue.put(s2m_drs)

        elif slot_type == 4:  # H4
            slot = CXL_DNFLIT_SLOT_H4.unpack(slot_data)
            assert(0)

        elif slot_type == 5:  # H5
            slot        = CXL_UPFLIT_SLOT_H5.unpack(slot_data)
            s2m_drs1    = CXL_FLIT_S2M_DRS_HDR.unpack(slot.s2m_drs1)
            s2m_drs0    = CXL_FLIT_S2M_DRS_HDR.unpack(slot.s2m_drs0)

            if s2m_drs1.valid:
                await self.s2m_drs_queue.put(s2m_drs1)
            if s2m_drs0.valid:
                await self.s2m_drs_queue.put(s2m_drs0)

        elif slot_type == 6:  # H6
            slot        = CXL_UPFLIT_SLOT_H6.unpack(slot_data)
            assert(0)
        else:
            assert(0)
            
class UnpackSlotG:
    def __init__(self, d2h_req_queue, d2h_rsp_queue, d2h_data_queue, s2m_drs_queue, s2m_ndr_queue, d2h_data_slot_queue
                , rollover_cnt):
        self.d2h_req_queue          = d2h_req_queue
        self.d2h_rsp_queue          = d2h_rsp_queue
        self.d2h_data_queue         = d2h_data_queue
        self.s2m_drs_queue          = s2m_drs_queue
        self.s2m_ndr_queue          = s2m_ndr_queue
        self.d2h_data_slot_queue    = d2h_data_slot_queue
        self.rollover_cnt           = rollover_cnt

    async def unpack_slot(self, slot_type, slot_data):
        if slot_type == 0:  # G00
            d2h_data_slot = slot_data
            self.rollover_cnt["value"] -= 1
            await self.d2h_data_slot_queue.put(d2h_data_slot)

        elif slot_type == 1:  # G1
            slot        = CXL_UPFLIT_SLOT_G1.unpack(slot_data)
            d2h_rsp1    = CXL_FLIT_D2H_RSP_HDR.unpack(slot.d2h_rsp1)
            d2h_rsp0    = CXL_FLIT_D2H_RSP_HDR.unpack(slot.d2h_rsp0)
            d2h_req     = CXL_FLIT_D2H_REQ_HDR.unpack(slot.d2h_req)

            if d2h_rsp1.valid:
                await self.d2h_rsp_queue.put(d2h_rsp1)
            if d2h_rsp0.valid:
                await self.d2h_rsp_queue.put(d2h_rsp0)
            if d2h_req.valid:
                await self.d2h_req_queue.put(d2h_req)

        elif slot_type == 2:  # G2
            slot        = CXL_UPFLIT_SLOT_G2.unpack(slot_data)
            d2h_rsp     = CXL_FLIT_D2H_RSP_HDR.unpack(slot.d2h_rsp)
            d2h_data    = CXL_FLIT_D2H_DATA_HDR.unpack(slot.d2h_data)
            d2h_req     = CXL_FLIT_D2H_REQ_HDR.unpack(slot.d2h_req)

            if d2h_rsp.valid:
                await self.d2h_rsp_queue.put(d2h_rsp)
            if d2h_data.valid:
                self.rollover_cnt["value"] += 4
                await self.d2h_data_queue.put(d2h_data)
            if d2h_req.valid:
                await self.d2h_req_queue.put(d2h_req)

        elif slot_type == 3:  # G3
            slot        = CXL_UPFLIT_SLOT_G3.unpack(slot_data)
            d2h_data3   = CXL_FLIT_D2H_DATA_HDR.unpack(slot.d2h_data0)
            d2h_data2   = CXL_FLIT_D2H_DATA_HDR.unpack(slot.d2h_data1)
            d2h_data1   = CXL_FLIT_D2H_DATA_HDR.unpack(slot.d2h_data2)
            d2h_data0   = CXL_FLIT_D2H_DATA_HDR.unpack(slot.d2h_data3)

            if d2h_data3.valid:
                await self.d2h_data_queue.put(d2h_data3)
            if d2h_data2.valid:
                await self.d2h_data_queue.put(d2h_data2)
            if d2h_data1.valid:
                await self.d2h_data_queue.put(d2h_data1)
            if d2h_data0.valid:
                await self.d2h_data_queue.put(d2h_data0)

        elif slot_type == 4:  # G4
            pass

        elif slot_type == 5:  # G5
            pass

        elif slot_type == 6:  # G6
            slot        = CXL_UPFLIT_SLOT_G6.unpack(slot_data)
            s2m_drs2    = CXL_FLIT_S2M_DRS_HDR.unpack(slot.s2m_drs2)
            s2m_drs1    = CXL_FLIT_S2M_DRS_HDR.unpack(slot.s2m_drs1)
            s2m_drs0    = CXL_FLIT_S2M_DRS_HDR.unpack(slot.s2m_drs0)

            if s2m_drs2.valid:
                await self.s2m_drs_queue.put(s2m_drs2)
            if s2m_drs1.valid:
                await self.s2m_drs_queue.put(s2m_drs1)
            if s2m_drs0.valid:
                await self.s2m_drs_queue.put(s2m_drs0)
        else:
            assert(0)

