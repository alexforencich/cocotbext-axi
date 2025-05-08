from enum import Enum
import struct
from dataclasses import dataclass, field

class CXL_D2H_REQ_OPCODE(Enum):
    CXL_D2H_REQ_OPCODE_RD_CURR = 0b00001
    CXL_D2H_REQ_OPCODE_RD_OWN = 0b00010
    CXL_D2H_REQ_OPCODE_RD_SHARED = 0b00011
    CXL_D2H_REQ_OPCODE_RD_ANY = 0b00100
    CXL_D2H_REQ_OPCODE_RD_OWN_ND = 0b00101
    CXL_D2H_REQ_OPCODE_ITOM_WR = 0b00110
    CXL_D2H_REQ_OPCODE_MEM_WR = 0b00111
    CXL_D2H_REQ_OPCODE_CL_FLUSH = 0b01000
    CXL_D2H_REQ_OPCODE_CLEAN_EVICT = 0b01001
    CXL_D2H_REQ_OPCODE_DIRTY_EVICT = 0b01010
    CXL_D2H_REQ_OPCODE_CLEAN_EVICT_ND = 0b01011
    CXL_D2H_REQ_OPCODE_WO_WR_INV = 0b01100
    CXL_D2H_REQ_OPCODE_WR_WR_INVF = 0b01101
    CXL_D2H_REQ_OPCODE_WR_INV = 0b01110
    CXL_D2H_REQ_OPCODE_CACHE_FLUSHED = 0b10000

class CXL_H2D_RSP_OPCODE(Enum):
    CXL_H2D_RSP_OPCODE_WRITEPULL = 0b0001
    CXL_H2D_RSP_OPCODE_GO = 0b0100
    CXL_H2D_RSP_OPCODE_GO_WRITEPULL = 0b0101
    CXL_H2D_RSP_OPCODE_EXT_CMP = 0b0110
    CXL_H2D_RSP_OPCODE_GO_WRITEPULL_DROP = 0b1000
    CXL_H2D_RSP_OPCODE_FAST_GO = 0b1100
    CXL_H2D_RSP_OPCODE_FAST_GO_WRITEPULL = 0b1101
    CXL_H2D_RSP_OPCODE_GO_ERR_WRITEPULL = 0b1111

class CXL_H2D_REQ_OPCODE(Enum):
    CXL_H2D_REQ_OPCODE_SNP_DATA = 0b001
    CXL_H2D_REQ_OPCODE_SNP_INV = 0b010
    CXL_H2D_REQ_OPCODE_SNP_CURR = 0b011

class CXL_D2H_RSP_OPCODE(Enum):
    CXL_D2H_RSP_OPCODE_I_HIT_I = 0b00100
    CXL_D2H_RSP_OPCODE_V_HIT_V = 0b00110
    CXL_D2H_RSP_OPCODE_I_HIT_SE = 0b00101
    CXL_D2H_RSP_OPCODE_S_HIT_SE = 0b00001
    CXL_D2H_RSP_OPCODE_S_FWD_M = 0b00111
    CXL_D2H_RSP_OPCODE_I_FWD_M = 0b01111
    CXL_D2H_RSP_OPCODE_V_FWD_V = 0b10110

class CXL_M2S_REQ_OPCODE(Enum):
    CXL_M2S_REQ_OPCODE_MEM_INV = 0b0000
    CXL_M2S_REQ_OPCODE_MEM_RD = 0b0001
    CXL_M2S_REQ_OPCODE_MEM_RD_DATA = 0b0010
    CXL_M2S_REQ_OPCODE_MEM_RD_FWD = 0b0011
    CXL_M2S_REQ_OPCODE_MEM_WR_FWD = 0b0100
    CXL_M2S_REQ_OPCODE_MEM_SPEC_RD = 0b1000
    CXL_M2S_REQ_OPCODE_MEM_INV_NT = 0b1001

class CXL_M2S_RWD_OPCODE(Enum):
    CXL_M2S_RWD_OPCODE_MEM_WR = 0b0001
    CXL_M2S_RWD_OPCODE_MEM_WR_PTL = 0b0010

class CXL_S2M_NDR_OPCODE(Enum):
    CXL_S2M_NDR_OPCODE_CMP = 0b000
    CXL_S2M_NDR_OPCODE_CMP_S = 0b001
    CXL_S2M_NDR_OPCODE_CMP_E = 0b010

class CXL_S2M_DRS_OPCODE(Enum):
    CXL_S2M_DRS_OPCODE_MEM_DATA = 0b000

class SLOT_T_H(Enum):
    H0 = 0b000
    H1 = 0b001
    H2 = 0b010
    H3 = 0b011
    H4 = 0b100
    H5 = 0b101

class SLOT_T_G(Enum):
    G0 = 0b000
    G1 = 0b001
    G2 = 0b010
    G3 = 0b011
    G4 = 0b100
    G5 = 0b101
    G6 = 0b110

# Constants
CXL_META_META_STATE = 0b00
CXL_META_NO_OP = 0b11

CXL_SNPTYPE_NO_OP = 0b000
CXL_SNPTYPE_SNP_DATA = 0b001
CXL_SNPTYPE_SNP_CUR = 0b010
CXL_SNPTYPE_SNP_INV = 0b011

CXL_RSP_PRE_LOCAL_MISS = 0b00
CXL_RSP_PRE_HIT = 0b01
CXL_RSP_PRE_REMOTE_MISS = 0b10

CXL_CACHE_STATE_INVALID = 0b0011
CXL_CACHE_STATE_SHARED = 0b0001
CXL_CACHE_STATE_EXCLUSIVE = 0b0010
CXL_CACHE_STATE_MODIFIED = 0b0110
CXL_CACHE_STATE_ERROR = 0b0100

@dataclass
class CXL_FLIT_H2D_REQ_HDR:
    rsvd: int  # [63:62]
    uqid: int  # [61:50]
    address: int  # [49:4]
    opcode: CXL_H2D_REQ_OPCODE  # [3:1]
    valid: bool  # [0]

    @classmethod
    def unpack(cls, data):
        value, = struct.unpack(">Q", data)
        return cls(
            rsvd=(value >> 62) & 0x3,
            uqid=(value >> 50) & 0xFFF,
            address=(value >> 4) & 0xFFFFFFFFFFFF,  # 46-bit
            opcode=(value >> 1) & 0xF,
            valid=bool(value & 0x1)
        )

@dataclass
class CXL_FLIT_H2D_RSP_HDR:
    def __init__(self, rsvd=0,cqid=0,rsp_pre=0,rsp_data=0,opcode=0,valid=0):
        self.rsvd=rsvd  # [31]
        self.cqid=cqid  # [30:19]
        self.rsp_pre=rsp_pre  # [18:17]
        self.rsp_data=rsp_data  # [16:5]
        self.opcode=opcode  # [4:1]
        self.valid=valid  # [0]

    # def pack(self):
    #     value = (
    #         (self.rsvd & 0x1) << 31 |
    #         (self.cqid & 0xFFF) << 19 |
    #         (self.rsp_pre & 0x3) << 17 |
    #         (self.rsp_data & 0xFFF) << 5 |
    #         (self.opcode & 0xF) << 1 |
    #         (self.valid)
    #     )
    #     return struct.pack(">I", value)
    
    def pack(self):
        value = (
            (self.rsvd & 0x1) << 31 |
            (self.cqid & 0xFFF) << 19 |
            (self.rsp_pre & 0x3) << 17 |
            (self.rsp_data & 0xFFF) << 5 |
            (self.opcode & 0xF) << 1 |
            (self.valid)
        )
        return value & 0xFFFF_FFFF

    @classmethod
    def unpack(cls, data):
        value, = struct.unpack(">I", data)  # 32-bit integer
        return cls(
            rsvd=(value >> 31) & 0x1,
            cqid=(value >> 19) & 0xFFF,
            rsp_pre=(value >> 17) & 0x3,
            rsp_data=(value >> 5) & 0xFFF,
            opcode=(value >> 1) & 0xF,
            valid=bool(value & 0x1)
        )
    def __repr__(self):
        return (f"CXL_FLIT_H2D_RSP_HDR("
                f"rsvd={self.rsvd}, cqid={self.cqid}, rsp_pre={self.rsp_pre}, "
                f"rsp_data={self.rsp_data}, opcode={self.opcode}, valid={self.valid})")


@dataclass
class CXL_FLIT_H2D_DATA_HDR:
    def __init__(self, rsvd=0,go_err=0,poison=0,chunk_valid=0,cqid=0,valid=0):
        self.rsvd=rsvd  # [23:16]
        self.go_err=go_err  # [15]
        self.poison=poison  # [14]
        self.chunk_valid=chunk_valid  # [13]
        self.cqid=cqid  # [12:1]
        self.valid=valid  # [0]

    # def pack(self):
    #     value = (
    #         (self.rsvd & 0xFF) << 16 |
    #         (self.go_err & 0x1) << 19 |
    #         (self.poison & 0x1) << 17 |
    #         (self.chunk_valid & 0x1) << 5 |
    #         (self.cqid & 0xFFF) << 1 |
    #         (self.valid)
    #     )
    #     packed = struct.pack(">I", value)
    #     return packed[1:]

    def pack(self):
        value = (
            (self.rsvd & 0xFF) << 16 |
            (self.go_err & 0x1) << 19 |
            (self.poison & 0x1) << 17 |
            (self.chunk_valid & 0x1) << 5 |
            (self.cqid & 0xFFF) << 1 |
            (self.valid)
        )
        return value & 0xFFFFFF

    @classmethod
    def unpack(cls, data):
        h_upper, h_lower = struct.unpack(">HB", data[:3])  # 16-bit + 8-bit = 24-bit
        value = (h_upper << 8) | h_lower
        return cls(
            rsvd=(value >> 16) & 0xFF,
            go_err=bool(value & (1 << 15)),
            poison=bool(value & (1 << 14)),
            chunk_valid=bool(value & (1 << 13)),
            cqid=(value >> 1) & 0xFFF,
            valid=bool(value & 0x1)
        )
    
    def __repr__(self):
        return (
            f"CXL_FLIT_H2D_DATA_HDR("
            f"rsvd={self.rsvd}, "
            f"go_err={self.go_err}, "
            f"poison={self.poison}, "
            f"chunk_valid={self.chunk_valid}, "
            f"cqid={self.cqid}, "
            f"valid={self.valid})"
        )
    

@dataclass
class CXL_FLIT_M2S_REQ_HDR:
    rsvd: int  # [86:81]
    ldid: int  # [80:77]
    tc: int  # [76:75]
    address: int  # [74:28]
    tag: int  # [27:12]
    meta_value: int  # [11:10]
    meta_field: int  # [9:8]
    snp_type: int  # [7:5]
    mem_opcode: CXL_M2S_REQ_OPCODE  # [4:1]
    valid: bool  # [0]

    @classmethod
    def unpack(cls, data):
        value = data
        
        return cls(
            rsvd=(value >> 81) & 0x3F,
            ldid=(value >> 77) & 0xF,
            tc=(value >> 75) & 0x3,
            address=(value >> 28) & 0x7FFFFFFFFFFF,  # 47-bit
            tag=(value >> 12) & 0xFFFF,
            meta_value=(value >> 10) & 0x3,
            meta_field=(value >> 8) & 0x3,
            snp_type=(value >> 5) & 0x7,
            mem_opcode=(value >> 1) & 0xF,
            valid=(value & 0x1)
        )

@dataclass
class CXL_FLIT_M2S_RWD_HDR:
    rsvd: int  # [86:81]
    ldid: int  # [80:77]
    tc: int  # [76:75]
    poison: bool  # [74]
    address: int  # [73:28]
    tag: int  # [27:12]
    meta_value: int  # [11:10]
    meta_field: int  # [9:8]
    snp_type: int  # [7:5]
    mem_opcode: CXL_M2S_RWD_OPCODE  # [4:1]
    valid: bool  # [0]

    @classmethod
    def unpack(cls, data):
        value = data
        return cls(
            rsvd=(value >> 81) & 0x3F,
            ldid=(value >> 77) & 0xF,
            tc=(value >> 75) & 0x3,
            poison=(value >> 74) & 0x1,
            address=(value >> 28) & 0x3FFFFFFFFFFF,
            tag=(value >> 12) & 0xFFFF,
            meta_value=(value >> 10) & 0x3,
            meta_field=(value >> 8) & 0x3,
            snp_type=(value >> 5) & 0x7,
            mem_opcode=(value >> 1) & 0xF,
            valid=(value & 0x1)
        )

@dataclass
class CXL_FLIT_D2H_REQ_HDR:
    rsvd2: int  # [78:72]
    address: int  # [71:26]
    rsvd: int  # [25:19]
    nt: bool  # [18]
    cqid: int  # [17:6]
    opcode: CXL_D2H_REQ_OPCODE  # [5:1]
    valid: bool  # [0]

    @classmethod
    def unpack(cls, data):
        value = data
        return cls(
            rsvd2=(value >> 72) & 0x7F,
            address=(value >> 26) & 0x3FFFFFFFFFFF,
            rsvd=(value >> 19) & 0x7F,
            nt=(value >> 18) & 0x1,
            cqid=(value >> 6) & 0xFFF,
            opcode=(value >> 1) & 0x1F,
            valid=(value) & 0x1
        )

@dataclass
class CXL_FLIT_D2H_RSP_HDR:
    rsvd: int  # [19:18]
    uqid: int  # [17:6]
    opcode: CXL_D2H_RSP_OPCODE  # [5:1]
    valid: bool  # [0]

    @classmethod
    def unpack(cls, data):
        value = data
        return cls(
            rsvd=(value >> 18) & 0x3,
            uqid=(value >> 6) & 0xFFF,
            opcode=(value >> 1) & 0x1F,
            valid=(value & 0x1)
        )

@dataclass
class CXL_FLIT_D2H_DATA_HDR:
    rsvd: bool  # [16]
    poison: bool  # [15]
    bogus: bool  # [14]
    chunk_valid: bool  # [13]
    uqid: int  # [12:1]
    valid: bool  # [0]

    @classmethod
    def unpack(cls, data):
        value= data  # 17-bit treated as 32-bit
        return cls(
            rsvd=(value >> 16) & 0x1,
            poison=(value >> 15) & 0x1,
            bogus=(value >> 14) & 0x1,
            chunk_valid=(value >> 13) & 0x1,
            uqid=(value >> 1) & 0xFFF,
            valid=(value) & 0x1
        )

@dataclass
class CXL_FLIT_D2H_DATA:
    data: int  # 512-bit

@dataclass
class CXL_FLIT_H2D_DATA:
    data: int  # 128-bit

@dataclass
class CXL_FLIT_S2M_DRS_HDR:
    rsvd: int  # [39:31]
    dev_load: int  # [30:29]
    ldid: int  # [28:25]
    poison: bool  # [24]
    tag: int  # [23:8]
    meta_value: int  # [7:6]
    meta_field: int  # [5:4]
    mem_opcode: CXL_S2M_DRS_OPCODE  # [3:1]
    valid: bool  # [0]

    @classmethod
    def unpack(cls, data):
        value = data
        return cls(
            rsvd=(value >> 31) & 0x1FF,
            dev_load=(value >> 29) & 0x7,
            ldid=(value >> 25) & 0xF,
            poison=(value >> 24) & 0x1,
            tag=(value >> 8) & 0xFFFF,
            meta_value=(value >> 6) & 0x3,
            meta_field=(value >> 4) & 0x3,
            mem_opcode=(value >> 1) & 0x7,
            valid=(value) & 0x1
        )

@dataclass
class CXL_FLIT_S2M_DRS:
    data: int  # 512-bit

@dataclass
class CXL_FLIT_M2S_RWD:
    data: int  # 128-bit

@dataclass
class CXL_FLIT_S2M_NDR_HDR:
    dev_load: int  # [29:28]
    ldid: int  # [27:24]
    tag: int  # [23:8]
    meta_value: int  # [7:6]
    meta_field: int  # [5:4]
    mem_opcode: CXL_S2M_NDR_OPCODE  # [3:1]
    valid: bool  # [0]

    @classmethod
    def unpack(cls, data):
        value = data
        return cls(
            dev_load=(value >> 28) & 0x3,
            ldid=(value >> 24) & 0xF,
            tag=(value >> 8) & 0xFFFF,
            meta_value=(value >> 6) & 0x3,
            meta_field=(value >> 4) & 0x3,
            mem_opcode=(value >> 1) & 0x7,
            valid=(value) & 0x1
        )

@dataclass
class CXL_DNFLIT_SLOT_H0:
    def __init__(self, h2d_rsp=CXL_FLIT_H2D_RSP_HDR, h2d_req=CXL_FLIT_H2D_REQ_HDR):
        self.h2d_rsp = h2d_rsp # 32-bit
        self.h2d_req = h2d_req # 64-bit
    
    def pack(self):
        value = (
            (self.h2d_rsp & 0xFFFFFFFF) << 64 |
            (self.h2d_req & 0xFFFFFFFFFFFFFFFF)
        )
        return value

@dataclass
class CXL_DNFLIT_SLOT_H1:
    def __init__(self, rsvd=0, h2d_rsp1=CXL_FLIT_H2D_RSP_HDR, h2d_rsp0=CXL_FLIT_H2D_RSP_HDR
                , h2d_data=CXL_FLIT_H2D_DATA_HDR):
        self.rsvd = rsvd  # 8-bit
        self.h2d_rsp1 = h2d_rsp1  # 32-bit
        self.h2d_rsp0 = h2d_rsp0  # 32-bit
        self.h2d_data = h2d_data  # 24-bit

    # def pack(self):
    #     value = (
    #         (self.rsvd & 0xFF) << 88 |   # 8-bit
    #         (self.h2d_rsp1 & 0xFFFFFFFF) << 56 |  # 32-bit
    #         (self.h2d_rsp0 & 0xFFFFFFFF) << 24 |  # 32-bit
    #         (self.h2d_data & 0xFFFFFF)  # 24-bit
    #     )
    #     return struct.pack(">QI", (value >> 32) & 0xFFFFFFFFFFFFFFFF, value & 0xFFFFFFFF)
    
    def pack(self):
        value = (
            (self.rsvd & 0xFF) << 88 |   # 8-bit
            (self.h2d_rsp1 & 0xFFFFFFFF) << 56 |  # 32-bit
            (self.h2d_rsp0 & 0xFFFFFFFF) << 24 |  # 32-bit
            (self.h2d_data & 0xFFFFFF)  # 24-bit
        )
        return value & 0xFFFF_FFFF_FFFF_FFFF_FFFF_FFFF
    
    def pack_bytes(self):
        rsvd = struct.pack(">B", self.rsvd)
        packed_h2d_rsp1 = self.h2d_rsp1.pack() if hasattr(self.h2d_rsp1, "pack") else struct.pack(">I", self.h2d_rsp1)
        packed_h2d_rsp0 = self.h2d_rsp0.pack() if hasattr(self.h2d_rsp0, "pack") else struct.pack(">I", self.h2d_rsp0)
        packed_h2d_data = self.h2d_data.pack() if hasattr(self.h2d_data, "pack") else struct.pack(">I", self.h2d_data)[1:]
        packed_data = rsvd + packed_h2d_rsp1 + packed_h2d_rsp0 + packed_h2d_data
        return packed_data

@dataclass
class CXL_DNFLIT_SLOT_H2:
    rsvd: int  # 8-bit
    h2d_data: CXL_FLIT_H2D_DATA_HDR  # 24-bit
    h2d_req: CXL_FLIT_H2D_REQ_HDR  # 64-bit

@dataclass
class CXL_DNFLIT_SLOT_H3:
    def __init__(
        self,
        h2d_data3 = CXL_FLIT_H2D_DATA_HDR(),
        h2d_data2 = CXL_FLIT_H2D_DATA_HDR(),
        h2d_data1 = CXL_FLIT_H2D_DATA_HDR(),
        h2d_data0 = CXL_FLIT_H2D_DATA_HDR()
    ):
        self.h2d_data3 = h2d_data3 # 24-bit
        self.h2d_data2 = h2d_data2 # 24-bit
        self.h2d_data1 = h2d_data1 # 24-bit
        self.h2d_data0 = h2d_data0 # 24-bit

    # def pack(self):
    #     packed_h2d_data3 = self.h2d_data3.pack_int()
    #     packed_h2d_data2 = self.h2d_data2.pack_int()
    #     packed_h2d_data1 = self.h2d_data1.pack_int()
    #     packed_h2d_data0 = self.h2d_data0.pack_int()
        
    #     packed_data = packed_h2d_data3 + packed_h2d_data2 + packed_h2d_data1 + packed_h2d_data0
    #     return packed_data
    
    def pack(self):
        value = (
            (self.h2d_data3.pack() & 0xFFFFFF) << 72 |
            (self.h2d_data2.pack() & 0xFFFFFF) << 48 |
            (self.h2d_data1.pack() & 0xFFFFFF) << 24 |
            (self.h2d_data0.pack() & 0xFFFFFF)
        )
        return value & 0xFFFFFFFFFFFFFFFFFFFFFFFF

@dataclass
class CXL_DNFLIT_SLOT_H4:
    rsvd: int  # 9-bit
    m2s_rwd: CXL_FLIT_M2S_RWD_HDR  # 87-bit

@dataclass
class CXL_DNFLIT_SLOT_H5:
    rsvd: int  # 9-bit
    m2s_req: CXL_FLIT_M2S_REQ_HDR  # 87-bit

@dataclass
class CXL_DNFLIT_SLOT_H6:
    mac: int  # 96-bit

@dataclass
class CXL_DNFLIT_SLOT_G00:
    data: int  # 128-bit

@dataclass
class CXL_DNFLIT_SLOT_G01:
    rsvd: int  # 64-bit
    data: int  # 64-bit

@dataclass
class CXL_DNFLIT_SLOT_G1:
    def __init__(
        self,
        h2d_rsp3 = CXL_FLIT_H2D_RSP_HDR(),
        h2d_rsp2 = CXL_FLIT_H2D_RSP_HDR(),
        h2d_rsp1 = CXL_FLIT_H2D_RSP_HDR(),
        h2d_rsp0 = CXL_FLIT_H2D_RSP_HDR()
    ):
        self.h2d_rsp3 = h2d_rsp3 # 32-bit
        self.h2d_rsp2 = h2d_rsp2 # 32-bit
        self.h2d_rsp1 = h2d_rsp1 # 32-bit
        self.h2d_rsp0 = h2d_rsp0 # 32-bit

    # def pack(self):
    #     packed_h2d_rsp3 = self.h2d_rsp3.pack()
    #     packed_h2d_rsp2 = self.h2d_rsp2.pack()
    #     packed_h2d_rsp1 = self.h2d_rsp1.pack()
    #     packed_h2d_rsp0 = self.h2d_rsp0.pack()

    #     packed_data = packed_h2d_rsp3 + packed_h2d_rsp2 + packed_h2d_rsp1 + packed_h2d_rsp0
    #     return packed_data
    
    def pack(self):
        value = (
            (self.h2d_rsp3.pack() & 0xFFFFFFFF) << 96 |
            (self.h2d_rsp2.pack() & 0xFFFFFFFF) << 64 |
            (self.h2d_rsp1.pack() & 0xFFFFFFFF) << 32 |
            (self.h2d_rsp0.pack() & 0xFFFFFFFF)
        )
        return value & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF

@dataclass
class CXL_DNFLIT_SLOT_G2:
    rsvd: int  # 8-bit
    h2d_rsp: CXL_FLIT_H2D_RSP_HDR  # 32-bit
    h2d_data: CXL_FLIT_H2D_DATA_HDR  # 24-bit
    h2d_req: CXL_FLIT_H2D_REQ_HDR  # 64-bit

@dataclass
class CXL_DNFLIT_SLOT_G3:
    h2d_rsp: CXL_FLIT_H2D_RSP_HDR  # 32-bit
    h2d_data3: CXL_FLIT_H2D_DATA_HDR  # 24-bit
    h2d_data2: CXL_FLIT_H2D_DATA_HDR  # 24-bit
    h2d_data1: CXL_FLIT_H2D_DATA_HDR  # 24-bit
    h2d_data0: CXL_FLIT_H2D_DATA_HDR  # 24-bit

@dataclass
class CXL_DNFLIT_SLOT_G4:
    rsvd2: int  # 16-bit
    h2d_data: CXL_FLIT_H2D_DATA_HDR  # 24-bit
    rsvd: int  # 1-bit
    m2s_req: CXL_FLIT_M2S_REQ_HDR  # 87-bit

@dataclass
class CXL_DNFLIT_SLOT_G5:
    rsvd2: int  # 8-bit
    h2d_rsp: CXL_FLIT_H2D_RSP_HDR  # 32-bit
    rsvd: int  # 1-bit
    m2s_rwd: CXL_FLIT_M2S_RWD_HDR  # 87-bit

@dataclass
class CXL_UPFLIT_SLOT_H0:
    def __init__(self, rsvd=0, s2m_ndr=CXL_FLIT_S2M_NDR_HDR,d2h_rsp1=CXL_FLIT_D2H_RSP_HDR,
                d2h_rsp0=CXL_FLIT_D2H_RSP_HDR, d2h_data=CXL_FLIT_D2H_DATA_HDR):
        self.rsvd=rsvd # 9-bit
        self.s2m_ndr=s2m_ndr # 30-bit
        self.d2h_rsp1=d2h_rsp1  # 20-bit
        self.d2h_rsp0=d2h_rsp0  # 20-bit
        self.d2h_data=d2h_data  # 17-bit

    @classmethod
    def unpack(cls, data):
        value = data
        rsvd = (value >> 87) & 0x1FF
        s2m_ndr   = (value >> 57) & 0x3FFFFFFF  # 30비트
        d2h_rsp1  = (value >> 37) & 0xFFFFF     # 20비트
        d2h_rsp0  = (value >> 17) & 0xFFFFF     # 20비트
        d2h_data  = value & 0x1FFFF             # 17비트

        return cls(
            rsvd=rsvd,
            s2m_ndr=s2m_ndr,
            d2h_rsp1=d2h_rsp1,
            d2h_rsp0=d2h_rsp0,
            d2h_data=d2h_data
        )

@dataclass
class CXL_UPFLIT_SLOT_H1:
    def __init__(self, d2h_data=CXL_FLIT_D2H_DATA_HDR, d2h_req=CXL_FLIT_D2H_REQ_HDR):
        self.d2h_data=d2h_data # 17bit
        self.d2h_req=d2h_req # 79bit

    @classmethod
    def unpack(cls, data):
        value = data
        d2h_data = (value >> 79) & 0x1FFFF  # 17비트
        d2h_req  = value & 0x7FFFFFFFFFFFFFFF  # 79비트
        return cls(
            d2h_data=d2h_data,
            d2h_req=d2h_req
        )

@dataclass
class CXL_UPFLIT_SLOT_H2:
    def __init__(self, rsvd=0, d2h_rsp=CXL_FLIT_D2H_RSP_HDR,d2h_data3=CXL_FLIT_D2H_DATA_HDR,
                d2h_data2=CXL_FLIT_D2H_DATA_HDR, d2h_data1=CXL_FLIT_D2H_DATA_HDR, d2h_data0=CXL_FLIT_D2H_DATA_HDR):
        self.rsvd=rsvd            # 8-bit
        self.d2h_rsp=d2h_rsp      # 20-bit
        self.d2h_data3=d2h_data3  # 17-bit
        self.d2h_data2=d2h_data2  # 17-bit
        self.d2h_data1=d2h_data1  # 17-bit
        self.d2h_data0=d2h_data0  # 17-bit

    @classmethod
    def unpack(cls, data):
        value = data
        rsvd = (value >> 88) & 0xFF
        d2h_rsp = (value >> 68) & 0xFFFFF
        d2h_data3 = (value >> 51) & 0x1FFFF
        d2h_data2 = (value >> 34) & 0x1FFFF
        d2h_data1 = (value >> 17) & 0x1FFFF
        d2h_data0 = (value) & 0x1FFFF

        return cls(
            rsvd=rsvd,
            d2h_rsp=d2h_rsp,
            d2h_data3=d2h_data3,
            d2h_data2=d2h_data2,
            d2h_data1=d2h_data1,
            d2h_data0=d2h_data0
        )

@dataclass
class CXL_UPFLIT_SLOT_H3:
    def __init__(self, rsvd=0, s2m_ndr=CXL_FLIT_S2M_NDR_HDR, s2m_drs=CXL_FLIT_S2M_DRS_HDR):
        self.rsvd=rsvd   # 26-bit
        self.s2m_ndr=s2m_ndr   # 30-bit
        self.s2m_drs=s2m_drs   # 40-bit

    @classmethod
    def unpack(cls, data):
        value = data
        rsvd = (value >> 70) & 0x3FFFFFF
        s2m_ndr = (value >> 40) & 0x3FFFFFFFF
        s2m_drs = (value) & 0xFFFFFFFFFF

        return cls(
            value=value,
            rsvd=rsvd,
            s2m_ndr=s2m_ndr,
            s2m_drs=s2m_drs
        )

@dataclass
class CXL_UPFLIT_SLOT_H4:
    def __init__(self, rsvd=0, s2m_ndr0_dev_load=0,s2m_ndr1=CXL_FLIT_S2M_NDR_HDR,
                s2m_ndr0_ldid=0, s2m_ndr0_tag=0, s2m_ndr0_meta_value=0,
                s2m_ndr0_meta_field=0, s2m_ndr0_mem_opcode=CXL_S2M_NDR_OPCODE,
                s2m_ndr0_valid=0):
        self.rsvd=rsvd # 36-bit
        self.s2m_ndr0_dev_load=s2m_ndr0_dev_load # 2-bit
        self.s2m_ndr1=s2m_ndr1 # 30-bit
        self.s2m_ndr0_ldid=s2m_ndr0_ldid # [27:24]
        self.s2m_ndr0_tag=s2m_ndr0_tag # [23:8]
        self.s2m_ndr0_meta_value=s2m_ndr0_meta_value # [7:6]
        self.s2m_ndr0_meta_field=s2m_ndr0_meta_field # [5:4]
        self.s2m_ndr0_mem_opcode=s2m_ndr0_mem_opcode # [3:1]
        self.s2m_ndr0_valid=s2m_ndr0_valid # [0]

    @classmethod
    def unpack(cls, data):
        value = data 
        rsvd = (value >> 60) & 0xFFFFFFFFF  # 36-bit
        s2m_ndr0_dev_load = (value >> 58) & 0x3  # 2-bit
        s2m_ndr1_value = (value >> 28) & 0x3FFFFFFF  # 30-bit
        s2m_ndr0_ldid = (value >> 24) & 0xF  # 4-bit
        s2m_ndr0_tag = (value >> 8) & 0xFFFF  # 16-bit
        s2m_ndr0_meta_value = (value >> 6) & 0x3  # 2-bit
        s2m_ndr0_meta_field = (value >> 4) & 0x3  # 2-bit
        s2m_ndr0_mem_opcode_value = (value >> 1) & 0x7  # 3-bit
        s2m_ndr0_valid = value & 0x1  # 1-bit

        return cls(
            rsvd=rsvd,
            s2m_ndr0_dev_load=s2m_ndr0_dev_load,
            s2m_ndr1_value=s2m_ndr1_value,
            s2m_ndr0_ldid=s2m_ndr0_ldid,
            s2m_ndr0_tag=s2m_ndr0_tag,
            s2m_ndr0_meta_value=s2m_ndr0_meta_value,
            s2m_ndr0_meta_field=s2m_ndr0_meta_field,
            s2m_ndr0_mem_opcode_value=s2m_ndr0_mem_opcode_value,
            s2m_ndr0_valid=s2m_ndr0_valid
        )
    
@dataclass
class CXL_UPFLIT_SLOT_H5:
    def __init__(self, rsvd=0, s2m_drs1=CXL_FLIT_S2M_DRS_HDR, s2m_drs0=CXL_FLIT_S2M_DRS_HDR):
        self.rsvd=rsvd # 16-bit
        self.s2m_drs1=s2m_drs1 # 40-bit
        self.s2m_drs0=s2m_drs0 # 40-bit

    @classmethod
    def unpack(cls, data):
        value = data
        rsvd = (value >> 80) & 0xFFFF
        s2m_drs1 = (value >> 40) & 0xFFFFFFFFFF
        s2m_drs0 = (value) & 0xFFFFFFFFFF

        return cls(
            rsvd=rsvd,
            s2m_drs1=s2m_drs1,
            s2m_drs0=s2m_drs0
        )

@dataclass
class CXL_UPFLIT_SLOT_H6:
    mac: int  # 96-bit

@dataclass
class CXL_UPFLIT_SLOT_G00:
    data: int  # 128-bit

@dataclass
class CXL_UPFLIT_SLOT_G01:
    def __init__(self, rsvd=0, data=0):
        self.rsvd=rsvd # 64-bit
        self.data=data # 64-bit
    
    @classmethod
    def unpack(cls, _data_):
        value = _data_
        rsvd = (value >> 64) & 0xFFFFFFFFFFFFFFFF
        data = (value) & 0xFFFFFFFFFFFFFFFF
        return cls(
            rsvd=rsvd,
            data=data
        )

@dataclass
class CXL_UPFLIT_SLOT_G1:
    def __init__(self, rsvd=0, d2h_rsp1=CXL_FLIT_D2H_RSP_HDR, d2h_rsp0=CXL_FLIT_D2H_RSP_HDR,
                d2h_req=CXL_FLIT_D2H_REQ_HDR):
        self.rsvd=rsvd  # 9-bit
        self.d2h_rsp1=d2h_rsp1 # 20-bit
        self.d2h_rsp0=d2h_rsp0 # 20-bit
        self.d2h_req=d2h_req # 79-bit
    
    @classmethod
    def unpack(cls, data):
        value = data
        rsvd = (value >> 119) & 0x1FF
        d2h_rsp1 = (value >> 99) & 0xFFFFF
        d2h_rsp0 = (value >> 79) & 0xFFFFF
        d2h_req = (value) & 0x7FFFFFFFFFFFFFFFFFFF
        return cls(
            rsvd=rsvd,
            d2h_rsp1=d2h_rsp1,
            d2h_rsp0=d2h_rsp0,
            d2h_req=d2h_req
        )

@dataclass
class CXL_UPFLIT_SLOT_G2:
    def __init__(self, rsvd=0, d2h_rsp=CXL_FLIT_D2H_RSP_HDR, d2h_data=CXL_FLIT_D2H_DATA_HDR,
                d2h_req=CXL_FLIT_D2H_REQ_HDR):
        self.rsvd=rsvd  # 12-bit
        self.d2h_rsp=d2h_rsp  # 20-bit
        self.d2h_data=d2h_data  # 17-bit
        self.d2h_req=d2h_req  # 79-bit
    
    @classmethod
    def unpack(cls, data):
        value = data
        rsvd = (value >> 116) & 0xFFF
        d2h_rsp = (value >> 96) & 0xFFFFF
        d2h_data = (value >> 19) & 0x1FFFF
        d2h_req = (value) & 0x7FFFFFFFFFFFFFFFFFFF
        return cls(
            rsvd=rsvd,
            d2h_rsp=d2h_rsp,
            d2h_data=d2h_data,
            d2h_req=d2h_req
        )

@dataclass
class CXL_UPFLIT_SLOT_G3:
    def __init__(self, rsvd=0, d2h_data3=CXL_FLIT_D2H_DATA_HDR, d2h_data2=CXL_FLIT_D2H_DATA_HDR,
                d2h_data1=CXL_FLIT_D2H_DATA_HDR, d2h_data0=CXL_FLIT_D2H_DATA_HDR):
        self.rsvd=rsvd  # 60-bit
        self.d2h_data3=d2h_data3  # 17-bit
        self.d2h_data2=d2h_data2  # 17-bit
        self.d2h_data1=d2h_data1  # 17-bit
        self.d2h_data0=d2h_data0  # 17-bit

    @classmethod
    def unpack(cls, data):
        value = data
        rsvd = (value >> 68) & 0xFFFFFFFFFFFFFFF
        d2h_data3 = (value >> 51) & 0x1FFFF
        d2h_data2 = (value >> 34) & 0x1FFFF
        d2h_data1 = (value >> 17) & 0x1FFFF
        d2h_data0 = (value) & 0x1FFFF
        
        return cls(
            rsvd=rsvd,
            d2h_data3=d2h_data3,
            d2h_data2=d2h_data2,
            d2h_data1=d2h_data1,
            d2h_data0=d2h_data0
        )

@dataclass
class CXL_UPFLIT_SLOT_G4:
    rsvd: int  # 28-bit
    s2m_ndr0_dev_load: int  # 2-bit
    s2m_ndr1: CXL_FLIT_S2M_NDR_HDR  # 30-bit
    s2m_ndr0_ldid: int  # 4-bit
    s2m_ndr0_tag: int  # 16-bit
    s2m_ndr0_meta_value: int  # 2-bit
    s2m_ndr0_meta_field: int  # 2-bit
    s2m_ndr0_mem_opcode: CXL_S2M_NDR_OPCODE  # 3-bit
    s2m_ndr0_valid: bool  # 1-bit
    s2m_drs: CXL_FLIT_S2M_DRS_HDR  # 40-bit

@dataclass
class CXL_UPFLIT_SLOT_G5:
    rsvd: int  # 68-bit
    s2m_ndr0_dev_load: int  # 2-bit
    s2m_ndr1: CXL_FLIT_S2M_NDR_HDR  # 30-bit
    s2m_ndr0_ldid: int  # 4-bit
    s2m_ndr0_tag: int  # 16-bit
    s2m_ndr0_meta_value: int  # 2-bit
    s2m_ndr0_meta_field: int  # 2-bit
    s2m_ndr0_mem_opcode: CXL_S2M_NDR_OPCODE  # 3-bit
    s2m_ndr0_valid: bool  # 1-bit

@dataclass
class CXL_UPFLIT_SLOT_G6:
    def __init__(self, rsvd=0, s2m_drs2=CXL_FLIT_S2M_DRS_HDR, s2m_drs1=CXL_FLIT_S2M_DRS_HDR,
                s2m_drs0=CXL_FLIT_S2M_DRS_HDR):
        self.rsvd=rsvd  # 8-bit
        self.s2m_drs2=s2m_drs2  # 40-bit
        self.s2m_drs1=s2m_drs1  # 40-bit
        self.s2m_drs0=s2m_drs0  # 40-bit

    @classmethod
    def unpack(cls, data):
        value = data
        rsvd = (value >> 120) & 0xFF
        s2m_drs2 = (value >> 80) & 0xFFFFFFFFFF
        s2m_drs1 = (value >> 40) & 0xFFFFFFFFFF
        s2m_drs0 = (value) & 0xFFFFFFFFFF
        return cls(
            rsvd=rsvd,
            s2m_drs2=s2m_drs2,
            s2m_drs1=s2m_drs1,
            s2m_drs0=s2m_drs0
        )

# Constants
CXL_FLIT_PLD_SIZE = 512  # 64B payload
CXL_FLIT_SIZE = 528  # payload + CRC16
CXL_FLIT_MAX_D2H_REQ = 4
CXL_FLIT_MAX_D2H_DATA = 4
CXL_FLIT_MAX_D2H_RSP = 2
CXL_FLIT_MAX_S2M_DRS = 3
CXL_FLIT_MAX_S2M_NDR = 2
CXL_FLIT_MAX_H2D_REQ = 2
CXL_FLIT_MAX_H2D_DATA = 4
CXL_FLIT_MAX_H2D_RSP = 4
CXL_FLIT_MAX_M2S_REQ = 2
CXL_FLIT_MAX_M2S_RWD = 1
CXL_FLIT_HDR_CNT_WIDTH = 3

class CXL_FLIT_TYPE(Enum):
    CXL_FLIT_TYPE_PROTOCOL = 0x0
    CXL_FLIT_TYPE_CONTROL = 0x1

@dataclass
class CXL_FLIT:
    crc: int  # 16-bit
    payload: int  # CXL_FLIT_PLD_SIZE-bit

@dataclass
class CXL_PROTOCOL_FLIT_HDR:
    def __init__(self, data_crd=0, req_crd=0, rsp_crd=0, rsvd2=0,
                slot3=0, slot2=0, slot1=0, slot0=0, sz=0, be=0, ak=0, rsvd=0,
                flit_type=0):
        self.data_crd = data_crd  # [31:28]
        self.req_crd = req_crd    # [27:24]
        self.rsp_crd = rsp_crd    # [23:20]
        self.rsvd2 = rsvd2        # [19:17]
        self.slot3 = slot3        # [16:14]
        self.slot2 = slot2        # [13:11]
        self.slot1 = slot1        # [10:8]
        self.slot0 = slot0        # [7:5]
        self.sz = sz              # [4]
        self.be = be              # [3]
        self.ak = ak              # [2]
        self.rsvd = rsvd          # [1]
        self.flit_type = flit_type  # [0]

    # def pack(self):
    #     value = (
    #         (self.data_crd & 0xF) << 28 |
    #         (self.req_crd & 0xF) << 24 |
    #         (self.rsp_crd & 0xF) << 20 |
    #         (self.rsvd2 & 0x7) << 17 |
    #         (self.slot3 & 0x7) << 14 |
    #         (self.slot2 & 0x7) << 11 |
    #         (self.slot1 & 0x7) << 8 |
    #         (self.slot0 & 0x7) << 5 |
    #         (self.sz & 0x1) << 4 |
    #         (self.be & 0x1) << 3 |
    #         (self.ak & 0x1) << 2 |
    #         (self.rsvd & 0x1) << 1 |
    #         (self.flit_type & 0x1) << 0
    #     )
    #     return struct.pack(">I", value)
    
    def pack(self):
        value = (
            (self.data_crd & 0xF) << 28 |
            (self.req_crd & 0xF) << 24 |
            (self.rsp_crd & 0xF) << 20 |
            (self.rsvd2 & 0x7) << 17 |
            (self.slot3 & 0x7) << 14 |
            (self.slot2 & 0x7) << 11 |
            (self.slot1 & 0x7) << 8 |
            (self.slot0 & 0x7) << 5 |
            (self.sz & 0x1) << 4 |
            (self.be & 0x1) << 3 |
            (self.ak & 0x1) << 2 |
            (self.rsvd & 0x1) << 1 |
            (self.flit_type & 0x1) << 0
        )
        return value & 0xFFFF_FFFF

    @classmethod
    def unpack(cls, data):
        """Unpack a 32-bit binary format into a CxlProtocolFlitHdr object"""
        value, = struct.unpack(">I", data)
        return cls(
            data_crd=(value >> 28) & 0xF,
            req_crd=(value >> 24) & 0xF,
            rsp_crd=(value >> 20) & 0xF,
            rsvd2=(value >> 17) & 0x7,
            slot3=(value >> 14) & 0x7,
            slot2=(value >> 11) & 0x7,
            slot1=(value >> 8) & 0x7,
            slot0=(value >> 5) & 0x7,
            sz=(value >> 4) & 0x1,
            be=(value >> 3) & 0x1,
            ak=(value >> 2) & 0x1,
            rsvd=(value >> 1) & 0x1,
            flit_type=(value >> 0) & 0x1,
        )

    def __repr__(self):
        return (
            f"CxlProtocolFlitHdr(data_crd={self.data_crd}, req_crd={self.req_crd}, "
            f"rsp_crd={self.rsp_crd}, rsvd2={self.rsvd2}, slot3={self.slot3}, slot2={self.slot2}, "
            f"slot1={self.slot1}, slot0={self.slot0}, sz={self.sz}, be={self.be}, "
            f"ak={self.ak}, rsvd={self.rsvd}, flit_type={self.flit_type})"
        )

@dataclass
class CXL_PROTOCOL_FLIT_PLD:
    def __init__(self, slot3=0, slot2=0, slot1=0, slot0=0, flit_hdr=None):
        self.slot3 = slot3  # 128-bit
        self.slot2 = slot2  # 128-bit
        self.slot1 = slot1  # 128-bit
        self.slot0 = slot0  # 96-bit
        self.flit_hdr = flit_hdr if flit_hdr else CXL_PROTOCOL_FLIT_HDR()  # 32-bit header

    # def pack(self):
    #     """Pack the structure into a binary format"""
    #     return (
    #         struct.pack(">QQ", (self.slot3 >> 64) & 0xFFFFFFFFFFFFFFFF, self.slot3 & 0xFFFFFFFFFFFFFFFF) +  # 128-bit
    #         struct.pack(">QQ", (self.slot2 >> 64) & 0xFFFFFFFFFFFFFFFF, self.slot2 & 0xFFFFFFFFFFFFFFFF) +  # 128-bit
    #         struct.pack(">QQ", (self.slot1 >> 64) & 0xFFFFFFFFFFFFFFFF, self.slot1 & 0xFFFFFFFFFFFFFFFF) +  # 128-bit
    #         struct.pack(">I", (self.slot0 >> 64) & 0xFFFFFFFF) + struct.pack(">Q", self.slot0 & 0xFFFFFFFFFFFFFFFF) +  # 96-bit
    #         self.flit_hdr.pack()  # 32-bit
    #     )
    
    def pack(self):
        value = (
            (self.slot3 & 0xFFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF) << 384 |
            (self.slot2 & 0xFFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF) << 256 |
            (self.slot1 & 0xFFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF_FFFF) << 128 |
            (self.slot0 & 0xFFFF_FFFF_FFFF_FFFF_FFFF_FFFF) << 32 |
            (self.flit_hdr.pack())  # 32-bit
        )
        return value
    
    def pack_bytes(self):
        return self.slot3 + self.slot2 + self.slot1 + self.slot0 + self.flit_hdr.pack()

    @classmethod
    def unpack(cls, data):
        """Unpack a binary format into a CxlProtocolFlitPld object"""
        slot3_high, slot3_low = struct.unpack_from(">QQ", data, 0)
        slot2_high, slot2_low = struct.unpack_from(">QQ", data, 16)
        slot1_high, slot1_low = struct.unpack_from(">QQ", data, 32)
        slot0_low, slot0_high = struct.unpack_from(">QI", data, 48)
        flit_hdr = CXL_PROTOCOL_FLIT_HDR.unpack(data[60:64])

        return cls(
            slot3=(slot3_low << 64) | slot3_high,
            slot2=(slot2_low << 64) | slot2_high,
            slot1=(slot1_low << 64) | slot1_high,
            slot0=(slot0_low << 64) | slot0_high,
            flit_hdr=flit_hdr
        )

@dataclass
class CXL_ALL_DATA_FLIT_PLD:
    slot0: int  # 128-bit
    slot1: int  # 128-bit
    slot2: int  # 128-bit
    slot3: int  # 128-bit

@dataclass
class CXL_CONTROL_FLIT_PLD:
    rsvd_slots: int  # 384-bit
    rsvd3: int  # 64-bit
    static0: int  # 24-bit
    sub_type: int  # 4-bit
    llctrl: int  # 4-bit
    rsvd2: int  # 24-bit
    ctl_fmt: int  # 3-bit
    rsvd: int  # 4-bit
    flit_type: bool  # 1-bit

@dataclass
class CXL_LLCRD_FLIT_PLD:
    rsvd_slots: int  # 384-bit
    payload: int  # 56-bit
    ak3: int  # 4-bit
    rsvd4: bool  # 1-bit
    ak2: int  # 2-bit
    static0: int  # 24-bit
    sub_type: int  # 4-bit
    llctrl: int  # 4-bit
    data_crd: int  # 4-bit
    req_crd: int  # 4-bit
    rsp_crd: int  # 4-bit
    rsvd3: int  # 12-bit
    ctl_fmt: int  # 3-bit
    rsvd2: int  # 2-bit
    ak: bool  # 1-bit
    rsvd: bool  # 1-bit
    flit_type: bool  # 1-bit

@dataclass
class CXL_RETRY_FLIT_PLD:
    rsvd_slots: int  # 384-bit
    payload: int  # 64-bit
    static0: int  # 24-bit
    sub_type: int  # 4-bit
    llctrl: int  # 4-bit
    rsvd2: int  # 24-bit
    ctl_fmt: int  # 3-bit
    rsvd: int  # 4-bit
    flit_type: bool  # 1-bit

@dataclass
class CXL_INIT_FLIT_PLD:
    rsvd_slots: int  # 384-bit
    payload: int  # 64-bit
    static0: int  # 24-bit
    sub_type: int  # 4-bit
    llctrl: int  # 4-bit
    rsvd2: int  # 24-bit
    ctl_fmt: int  # 3-bit
    rsvd: int  # 4-bit
    flit_type: bool  # 1-bit

@dataclass
class CXL_IDE_FLIT_PLD:
    unused_slots: int  # 384-bit
    payload: int  # 96-bit
    rsvd2: int  # 24-bit
    ctl_fmt: int  # 3-bit
    rsvd: int  # 4-bit
    flit_type: bool  # 1-bit

# Constants
CXL_FLIT_PLD_SIZE = 512  # 64B payload
CXL_FLIT_SIZE = 528  # payload + CRC16
CXL_FLIT_HDR_CNT_WIDTH = 3

# Link Layer Constants
CXL_LINK_LLCRD_CTL_FMT = 0b000
CXL_LINK_LLCRD_LLCTRL = 0b0000
CXL_LINK_LLCRD_SUBTYPE_ACK = 0b0001

CXL_LINK_RETRY_CTL_FMT = 0b000
CXL_LINK_RETRY_LLCTRL = 0b0001
CXL_LINK_RETRY_SUBTYPE_IDLE = 0b0000
CXL_LINK_RETRY_SUBTYPE_REQ = 0b0001
CXL_LINK_RETRY_SUBTYPE_ACK = 0b0010
CXL_LINK_RETRY_SUBTYPE_FRAME = 0b0011

CXL_LINK_IDE_CTL_FMT = 0b001
CXL_LINK_IDE_LLCTRL = 0b0010
CXL_LINK_IDE_SUBTYPE_IDLE = 0b0000
CXL_LINK_IDE_SUBTYPE_START = 0b0001
CXL_LINK_IDE_SUBTYPE_TMAC = 0b0010

CXL_LINK_INIT_CTL_FMT = 0b000
CXL_LINK_INIT_LLCTRL = 0b1100
CXL_LINK_INIT_SUBTYPE_PARAM = 0b1000
CXL_LINK_INIT_PAYLOAD_CXL2 = 0b0010

class CXL_FLIT_TYPE(Enum):
    CXL_FLIT_TYPE_PROTOCOL = 0b0
    CXL_FLIT_TYPE_CONTROL = 0b1

@dataclass
class CXL_FLIT:
    crc: int  # 16-bit
    payload: int  # CXL_FLIT_PLD_SIZE-bit

    def __init__(self, crc=0, payload=0):
        self.crc = crc  # 16bit
        self.payload = payload  # 512bit

    @classmethod
    def unpack(cls, data: bytes):

        crc = data[:2]

        payload = data[2:]

        return payload

def is_control_flit(payload) -> bool:
    return payload.flit_type == CXL_FLIT_TYPE.CXL_FLIT_TYPE_CONTROL

def is_protocol_flit(payload) -> bool:
    return payload.flit_type == CXL_FLIT_TYPE.CXL_FLIT_TYPE_PROTOCOL

def is_llcrd_flit(payload) -> bool:
    return (payload.flit_type == CXL_FLIT_TYPE.CXL_FLIT_TYPE_CONTROL and
            payload.ctl_fmt == CXL_LINK_LLCRD_CTL_FMT and
            payload.llctrl == CXL_LINK_LLCRD_LLCTRL)

def is_retry_flit(payload) -> bool:
    return (payload.flit_type == CXL_FLIT_TYPE.CXL_FLIT_TYPE_CONTROL and
            payload.ctl_fmt == CXL_LINK_RETRY_CTL_FMT and
            payload.llctrl == CXL_LINK_RETRY_LLCTRL)

def is_retry_req_flit(payload) -> bool:
    return (is_retry_flit(payload) and
            payload.sub_type == CXL_LINK_RETRY_SUBTYPE_REQ)

def is_retry_ack_flit(payload) -> bool:
    return (is_retry_flit(payload) and
            payload.sub_type == CXL_LINK_RETRY_SUBTYPE_ACK)

def is_ide_flit(payload) -> bool:
    return (payload.flit_type == CXL_FLIT_TYPE.CXL_FLIT_TYPE_CONTROL and
            payload.ctl_fmt == CXL_LINK_IDE_CTL_FMT and
            payload.llctrl == CXL_LINK_IDE_LLCTRL)

def is_init_flit(payload) -> bool:
    return (payload.flit_type == CXL_FLIT_TYPE.CXL_FLIT_TYPE_CONTROL and
            payload.ctl_fmt == CXL_LINK_INIT_CTL_FMT and
            payload.llctrl == CXL_LINK_INIT_LLCTRL)

def is_retryable_flit(payload) -> bool:
    return not is_retry_flit(payload)

def is_static0_err(payload) -> bool:
    if is_llcrd_flit(payload) or is_retry_flit(payload) or is_init_flit(payload):
        return payload.static0 != 0
    return False

CXL_CRC_COEFF = [
    0xEF9C_D9F9_C4BB_B83A_3E84_A97C_D7AE_DA13_FAEB_01B8_5B20_4A4C_AE1E_79D9_7753_5D21_DC7F_DD6A_38F0_3E77_F5F5_2A2C_636D_B05C_3978_EA30_CD50_E0D9_9B06_93D4_746B_2431,
    0x9852_B505_26E6_6427_21C6_FDC2_BC79_B71A_079E_8164_76B0_6F6A_F911_4535_CCFA_F3B1_3240_33DF_2488_214C_0F0F_BF3A_52DB_6872_25C4_9F28_ABF8_90B5_5685_DA3E_4E5E_B629,
    0x23B5_837B_57C8_8A29_AE67_D79D_8992_019E_F924_410A_6078_7DF9_D296_DB43_912E_24F9_455F_C485_AAB4_2ED1_F272_F5B1_4A00_0465_2B9A_A5A4_98AC_A883_3044_7ECB_5344_7F25,
    0x7E46_1844_6F5F_FD2E_E9B7_42B2_1367_DADC_8679_213D_6B1C_74B0_4755_1478_BFC4_4F5D_7ED0_3F28_EDAA_291F_0CCC_50F4_C66D_B26E_ACB5_B8E2_8106_B498_0324_ACB1_DDC9_1BA3,
    0x50BF_D5DB_F314_46AD_4A5F_0825_DE1D_377D_B9D7_9126_EEAE_7014_8DB4_F3E5_28B1_7A8F_6317_C2FE_4E25_2AF8_7393_0256_005B_696B_6F22_3641_8DD3_BA95_9A94_C58C_9A8F_A9E0,
    0xA85F_EAED_F98A_2356_A52F_8412_EF0E_9BBE_DCEB_C893_7757_380A_46DA_79F2_9458_BD47_B18B_E17F_2712_957C_39C9_812B_002D_B4B5_B791_1B20_C6E9_DD4A_CD4A_62C6_4D47_D4F0,
    0x542F_F576_FCC5_11AB_5297_C209_7787_4DDF_6E75_E449_BBAB_9C05_236D_3CF9_4A2C_5EA3_D8C5_F0BF_9389_4ABE_1CE4_C095_8016_DA5A_DBC8_8D90_6374_EEA5_66A5_3163_26A3_EA78,
    0x2A17_FABB_7E62_88D5_A94B_E104_BBC3_A6EF_B73A_F224_DDD5_CE02_91B6_9E7C_A516_2F51_EC62_F85F_C9C4_A55F_0E72_604A_C00B_6D2D_6DE4_46C8_31BA_7752_B352_98B1_9351_F53C,
    0x150B_FD5D_BF31_446A_D4A5_F082_5DE1_D377_DB9D_7912_6EEA_E701_48DB_4F3E_528B_17A8_F631_7C2F_E4E2_52AF_8739_3025_6005_B696_B6F2_2364_18DD_3BA9_59A9_4C58_C9A8_FA9E,
    0x8A85_FEAE_DF98_A235_6A52_F841_2EF0_E9BB_EDCE_BC89_3775_7380_A46D_A79F_2945_8BD4_7B18_BE17_F271_2957_C39C_9812_B002_DB4B_5B79_11B2_0C6E_9DD4_ACD4_A62C_64D4_7D4F,
    0xAADE_26AE_AB77_E920_8BAD_D55C_40D6_AECE_0C0C_5FFC_C09A_F38C_FC28_AA16_E3F1_98CB_E1F3_8261_C1C8_AADC_143B_6625_3B6C_DDF9_94C4_62E9_CB67_AE33_CD6C_C0C2_4601_1A96,
    0xD56F_1357_55BB_F490_45D6_EAAE_206B_5767_0606_2FFE_604D_79C6_7E14_550B_71F8_CC65_F0F9_C130_E0E4_556E_0A1D_B312_9DB6_6EFC_CA62_3174_E5B3_D719_E6B6_6061_2300_8D4B,
    0x852B_5052_6E66_4272_1C6F_DC2B_C79B_71A0_79E8_1647_6B06_F6AF_9114_535C_CFAF_3B13_2403_3DF2_4882_14C0_F0FB_F3A5_2DB6_8722_5C49_F28A_BF89_0B55_685D_A3E4_E5EB_6294,
    0xC295_A829_3733_2139_0E37_EE15_E3CD_B8D0_3CF4_0B23_B583_7B57_C88A_29AE_67D7_9D89_9201_9EF9_2441_0A60_787D_F9D2_96DB_4391_2E24_F945_5FC4_85AA_B42E_D1F2_72F5_B14A,
    0x614A_D414_9B99_909C_871B_F70A_F1E6_DC68_1E7A_0591_DAC1_BDAB_E445_14D7_33EB_CEC4_C900_CF7C_9220_8530_3C3E_FCE9_4B6D_A1C8_9712_7CA2_AFE2_42D5_5A17_68F9_397A_D8A5,
    0xDF39_B3F3_8977_7074_7D09_52F9_AF5D_B427_F5D6_0370_B640_9499_5C3C_F3B2_EEA6_BA43_B8FF_BAD4_71E0_7CEF_EBEA_5458_C6DB_60B8_72F1_D461_9AA1_C1B3_360D_27A8_E8D6_4863
]
