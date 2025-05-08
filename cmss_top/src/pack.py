from enum import Enum
from dataclasses import dataclass, fields, is_dataclass
from cxl_pkg import *

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
            if getattr(obj, field.name) is not None else "0" * field.metadata.get('bits', 1)
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

def apply_crc(payload_int: int, crc_coeff) -> int:
    """Apply XOR-tree based CRC on a 512-bit integer payload and return 528-bit integer result"""
    if not isinstance(payload_int, int):
        raise TypeError(f"payload must be int, but got {type(payload_int)}")
    if not (0 <= payload_int < (1 << 512)):
        raise ValueError("payload must be a 512-bit integer (0 <= x < 2^512)")

    if not isinstance(crc_coeff, list):
        raise TypeError("crc_coeff must be a list of 16 integers (512-bit each)")
    if len(crc_coeff) != 16:
        raise ValueError(f"crc_coeff must have exactly 16 elements, but got {len(crc_coeff)}")
    if not all(isinstance(coeff, int) and 0 <= coeff < (1 << 512) for coeff in crc_coeff):
        raise TypeError("All elements in crc_coeff must be 512-bit integers")

    crc_bits = 0
    for i in range(16):
        xor_result = xor_reduce(payload_int & crc_coeff[i])  # XOR-tree
        crc_bits |= (xor_result << (15 - i))

    final_flit = (crc_bits << 512) | payload_int  # 528-bit result as int
    return final_flit
