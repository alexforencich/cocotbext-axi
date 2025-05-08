import cocotb
from cocotb.triggers import Timer
from enum import Enum
from cocotb.queue import Queue
from dataclasses import dataclass, fields, is_dataclass
from cocotb.triggers import FallingEdge
import cocotb.utils
from cxl_pkg import *
from unpack import Unpack
from cocotb_bus.drivers import BusDriver
from typing import get_type_hints
from host import Host, RspGen, FlitGen
from cocotb.binary import BinaryValue

from pipe_driver import PIPE_RX_Driver

async def generate_clock(dut):
    """Infinite clock roop"""
    while True:
        dut.aclk.value = 0
        dut.cclk.value = 0
        await Timer(0.5, "ns")
        dut.aclk.value = 1
        dut.cclk.value = 1
        await Timer(0.5, "ns")

def get_field_bit_length(dataclass_type, field_name):
    type_hints = get_type_hints(dataclass_type)
    if field_name in type_hints:
        type_hint = type_hints[field_name]
        if isinstance(type_hint, str) and "bit" in type_hint:
            return int(type_hint.split("#")[1].strip().split("-")[0])
    raise ValueError(f"Error. Can't fine {field_name} bit length.")

def serialize_dataclass(obj):
    if obj is None:
        return 0
    elif isinstance(obj, int):  
        return obj
    elif isinstance(obj, bool):
        return int(obj)
    elif isinstance(obj, float):
        return int(obj)
    elif isinstance(obj, str):
        return int.from_bytes(obj.encode(), 'little')
    elif isinstance(obj, Enum):
        return obj.value
    elif is_dataclass(obj):
        bit_string = "".join(
            f"{serialize_dataclass(getattr(obj, field.name)):0{field.metadata.get('bits', 1)}b}"
            if getattr(obj, field.name) is not None else "0" * field.metadata.get('bits', 1)  # 🛠️ 기본값 추가
            for field in fields(obj)
        )
        return int(bit_string, 2) if bit_string else 0
    else:
        raise TypeError(f"Unsupported type: {type(obj)} - Value: {obj}") 
def xor_reduce(value: int) -> int:
    result = 0
    while value:
        result ^= value & 1
        value >>= 1
    return result
def apply_crc_weights(payload, crc_coeff):
    """Apply XOR-tree based CRC on a 512-bit payload (bytes)"""
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError(f"payload must be bytes, but got {type(payload)}")
    if len(payload) != 64:  # 512 bits = 64 bytes
        raise ValueError(f"payload must be exactly 64 bytes (512 bits), but got {len(payload)} bytes")
    if not isinstance(crc_coeff, list):
        raise TypeError("crc_coeff must be a list of 16 integers (512-bit each)")
    if len(crc_coeff) != 16:
        raise ValueError(f"crc_coeff must have exactly 16 elements, but got {len(crc_coeff)}")
    if not all(isinstance(coeff, int) and 0 <= coeff < (1 << 512) for coeff in crc_coeff):
        raise TypeError("All elements in crc_coeff must be 512-bit integers")

    payload_int = int.from_bytes(payload, byteorder="big")

    crc_bits = 0
    for i in range(16):
        xor_result = xor_reduce(payload_int & crc_coeff[i])  # XOR-tree
        crc_bits |= (xor_result << (15-i))

    final_flit = (crc_bits << 512) | payload_int  # 528-bit 데이터

    final_bytes = final_flit.to_bytes(66, byteorder="big")

    return final_bytes

def apply_crc_weights_int(payload_int, crc_coeff):
    """Apply XOR-tree based CRC on a 512-bit payload (int)"""
    if not isinstance(payload_int, int):
        raise TypeError(f"payload must be an int, but got {type(payload_int)}")
    if not (0 <= payload_int < (1 << 512)):  # 512비트 검증
        raise ValueError(f"payload must be a 512-bit integer, but got {payload_int.bit_length()} bits")
    if not isinstance(crc_coeff, list):
        raise TypeError("crc_coeff must be a list of 16 integers (512-bit each)")
    if len(crc_coeff) != 16:
        raise ValueError(f"crc_coeff must have exactly 16 elements, but got {len(crc_coeff)}")
    if not all(isinstance(coeff, int) and 0 <= coeff < (1 << 512) for coeff in crc_coeff):
        raise TypeError("All elements in crc_coeff must be 512-bit integers")

    crc_bits = 0
    for i in range(16):
        xor_result = xor_reduce(payload_int & crc_coeff[i])  # XOR-tree
        crc_bits |= (xor_result << (15 - i))  # CRC 비트를 반전하여 저장

    final_flit = (crc_bits << 512) | payload_int  # 528비트 데이터

    final_bytes = final_flit.to_bytes(66, byteorder="big")

    return final_bytes

#async def stop_simulation():
#    await Timer(300, "ns")
#    print("Stopping simulation at 500ns")
#    return


@cocotb.test()
async def pipe_driver_test(dut):
    cocotb.start_soon(generate_clock(dut))
    pipe_driver = PIPE_RX_Driver(dut, '', dut.aclk)

    flit_hdr = CXL_PROTOCOL_FLIT_HDR(
        data_crd=0,  # 4-bit
        req_crd=0,  # 4-bit
        rsp_crd=0,  # 4-bit
        rsvd2=0,  # 3-bit
        slot3=SLOT_T_G.G0.value,  # 3-bit
        slot2=SLOT_T_G.G0.value,  # 3-bit
        slot1=SLOT_T_G.G0.value,  # 3-bit
        slot0=SLOT_T_H.H1.value,  # 3-bit
        sz=1,  # 1-bit
        be=0,  # 1-bit
        ak=1,  # 1-bit
        rsvd=0,  # 1-bit
        flit_type=CXL_FLIT_TYPE.CXL_FLIT_TYPE_PROTOCOL.value  # 1-bit
    )
    protocol_flit = CXL_PROTOCOL_FLIT_PLD(
        slot3=0x1111_1234_1234_1111_1234_1234_1234_1234,
        slot2=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF,
        slot1=0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA,
        slot0=0x0000_0000_4000_0000_0000_02c3,
        flit_hdr=flit_hdr
    )
    dut.areset_n.value = 0
    dut.creset_n.value = 0
    await Timer(10, "ns")
    dut.areset_n.value = 1
    dut.creset_n.value = 1
    await Timer(1, "ns")
    d2h_req_queue  = Queue()
    d2h_rsp_queue  = Queue()
    d2h_data_queue = Queue()
    s2m_drs_queue  = Queue()
    s2m_ndr_queue  = Queue()
    h2d_rsp_queue = Queue()
    flit_input_queue = Queue()
    h2d_data_hdr_queue = Queue()
    flit_queue = Queue()
    unpacker = Unpack(flit_input_queue, d2h_req_queue)
    rspgen = RspGen(d2h_req_queue, h2d_rsp_queue, h2d_data_hdr_queue)
    flitgen = FlitGen(h2d_rsp_queue, h2d_data_hdr_queue, flit_queue)
    host = Host(unpacker)
    cocotb.start_soon(generate_clock(dut))
    cocotb.start_soon(unpacker.run_unpacker())
    cocotb.start_soon(rspgen.process_requests())
    cocotb.start_soon(flitgen.generate_flit())
    await Timer(1, "ns")
    for i in range(10):
        await Timer(10, "ns")
        await flit_input_queue.put(protocol_flit.pack())


    while True:
        await Timer(1, "ns")    
        if not flit_queue.empty():
            
            
            flit = await flit_queue.get()
            if isinstance(flit, BinaryValue):
                flit_data = BinaryValue("X"*528)
                pipe_driver.append((flit_data, 0))
            else:
                flit_data = apply_crc_weights(flit.pack_bytes(), CXL_CRC_COEFF)
                flit_data = int.from_bytes(flit_data, byteorder="big")
                print(flit_data)
                pipe_driver.append((flit_data, 1))

        else:
            return
            
            
    
    
    
    await Timer(10, "ns")
    #print(f"phy_rxdata: {dut.phy_rxdata.value}")
    #print(type(dut.phy_rxdata.value))
    #print(f"phy_rxdata_valid_i: {dut.phy_rxdata_valid.value}")
