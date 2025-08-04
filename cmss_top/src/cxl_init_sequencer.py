import asyncio
import cocotb
from enum import Enum, auto
from cxl_pkg import *
from cocotb.queue import Queue
from cocotb.triggers import First, Timer, with_timeout
from cocotb.result import TestFailure

class InitState(Enum):
    START = auto()
    SEND_RETRY_IDLE = auto()
    WAIT_RETRY_IDLE = auto()
    SEND_INIT_PARAM = auto()
    WAIT_INIT_PARAM = auto()
    SEND_CREDIT = auto()
    DONE = auto()
    ERROR = auto() 

class CxlInitSequencer:
    def __init__(self, control_flit_queue, flit_output_queue):
        self.log = cocotb.log
        self.control_flit_queue = control_flit_queue
        self.flit_output_queue = flit_output_queue
        self.state = InitState.START

    async def run(self):
        await Timer(10, "ns")
        self.log.info("Starting CXL Init Sequence...")
        self.state = InitState.SEND_RETRY_IDLE

        while self.state not in [InitState.DONE, InitState.ERROR]:
            if self.state == InitState.SEND_RETRY_IDLE:
                await self._state_send_retry_idle()
            elif self.state == InitState.WAIT_RETRY_IDLE:
                await self._state_wait_retry_idle()
            elif self.state == InitState.SEND_INIT_PARAM:
                await self._state_send_init_param()
            elif self.state == InitState.WAIT_INIT_PARAM:
                await self._state_wait_init_param()
            elif self.state == InitState.SEND_CREDIT:
                for i in range(7): # FIXME : Credit send mechanism
                    await self._state_send_credit()
                    self.state = InitState.DONE
        
        if self.state == InitState.DONE:
            self.log.info("CXL Init Sequence COMPLETED successfully.")
        else:
            self.log.error("CXL Init Sequence FAILED.")
            raise TestFailure("Init sequence failed")

    async def _state_send_retry_idle(self):
        self.log.info(f"[State: {self.state.name}] Sending RETRY.Idle...")
        CMSS_RETRY_BUF_IDX_WIDTH = 7
        CMSS_RETRY_BUF_SIZE = 2**CMSS_RETRY_BUF_IDX_WIDTH
        payload = 0
        payload |= (CMSS_RETRY_BUF_SIZE) << 24
        payload |= CXL_LINK_INIT_PAYLOAD_CXL2
        flit = CXL_RETRY_FLIT_PLD(
            flit_type = CXL_FLIT_TYPE.CXL_FLIT_TYPE_CONTROL.value,
            ctl_fmt = CXL_LINK_RETRY_CTL_FMT,
            llctrl = CXL_LINK_RETRY_LLCTRL,
            sub_type = CXL_LINK_RETRY_SUBTYPE_IDLE
        )

        await self.flit_output_queue.put(flit)
        self.state = InitState.WAIT_RETRY_IDLE

    async def _state_wait_retry_idle(self):
        self.log.info(f"[State: {self.state.name}] Waiting for RETRY.Idle from DUT...")
        try:
            payload = await with_timeout(self.control_flit_queue.get(), 1, 'us')

            if payload and is_retry_idle_flit(payload):
                self.log.info("-> Received RETRY.Idle ACK from DUT.")
                self.state = InitState.SEND_INIT_PARAM
            else:
                self.log.error(f"-> Received unexpected flit: {payload}")
                self.state = InitState.ERROR
        except asyncio.TimeoutError:
            self.log.error("-> Timed out waiting for RETRY.Idle ACK.")
            raise TestFailure("Test failed due to timeout")

    async def _state_send_init_param(self):
        self.log.info(f"[State: {self.state.name}] Sending INIT.Param...")
        CMSS_RETRY_BUF_IDX_WIDTH = 7
        CMSS_RETRY_BUF_SIZE = 2**CMSS_RETRY_BUF_IDX_WIDTH
        payload = 0
        payload |= ((CMSS_RETRY_BUF_SIZE) << 24) | CXL_LINK_INIT_PAYLOAD_CXL2
        flit = CXL_INIT_FLIT_PLD(
            flit_type = CXL_FLIT_TYPE.CXL_FLIT_TYPE_CONTROL.value,
            payload = payload,
            ctl_fmt = CXL_LINK_INIT_CTL_FMT,
            llctrl = CXL_LINK_INIT_LLCTRL,
            sub_type = CXL_LINK_INIT_SUBTYPE_PARAM
        )
        await self.flit_output_queue.put(flit)
        self.state = InitState.WAIT_INIT_PARAM
    
    async def _state_wait_init_param(self):
        self.log.info(f"[State : {self.state.name}] Waiting INIT.Param...")
        try:
            payload = await with_timeout(self.control_flit_queue.get(), 1, 'us')
            if payload and is_init_flit(payload):
                self.log.info("-> Received INIT.Param ACK from DUT.")
                self.state = InitState.SEND_CREDIT
            else:
                self.log.error(f"-> Received unexpected flit: {payload}")
                self.state = InitState.ERROR
        except asyncio.TimeoutError:
            self.log.error("-> Timed out waiting for RETRY.Idle ACK.")
            raise TestFailure("Test failed due to timeout")
    
    async def _state_send_credit(self):
        self.log.info(f"[State: {self.state.name}] Sending Credit")
        # First .mem credit
        flit = CXL_LLCRD_FLIT_PLD(
            flit_type = CXL_FLIT_TYPE.CXL_FLIT_TYPE_CONTROL.value,
            ctl_fmt = CXL_LINK_LLCRD_CTL_FMT,
            llctrl = CXL_LINK_LLCRD_LLCTRL,
            sub_type = CXL_LINK_LLCRD_SUBTYPE_ACK,
            data_crd = 0b1111,
            req_crd = 0b1111,
            rsp_crd = 0b1111
        )
        await self.flit_output_queue.put(flit)
        # Second .cache credit
        flit = CXL_LLCRD_FLIT_PLD(
            flit_type = CXL_FLIT_TYPE.CXL_FLIT_TYPE_CONTROL.value,
            ctl_fmt = CXL_LINK_LLCRD_CTL_FMT,
            llctrl = CXL_LINK_LLCRD_LLCTRL,
            sub_type = CXL_LINK_LLCRD_SUBTYPE_ACK,
            data_crd = 0b0111,
            req_crd = 0b0111,
            rsp_crd = 0b0111
        )
        await self.flit_output_queue.put(flit)
        #self.state = InitState.DONE

