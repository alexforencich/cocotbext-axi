"""

Copyright (c) 2020 Alex Forencich

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

"""

from .version import __version__

from .constants import AxiBurstType, AxiBurstSize, AxiLockType, AxiCacheBit, AxiProt, AxiResp

from .address_space import MemoryInterface, Window, WindowPool
from .address_space import Region, MemoryRegion, SparseMemoryRegion, PeripheralRegion
from .address_space import AddressSpace, Pool

from .axis import AxiStreamFrame, AxiStreamBus, AxiStreamSource, AxiStreamSink, AxiStreamMonitor

from .axil_channels import AxiLiteAWBus, AxiLiteWBus, AxiLiteBBus, AxiLiteARBus, AxiLiteRBus
from .axil_channels import AxiLiteWriteBus, AxiLiteReadBus, AxiLiteBus
from .axil_master import AxiLiteMasterWrite, AxiLiteMasterRead, AxiLiteMaster
from .axil_slave import AxiLiteSlaveWrite, AxiLiteSlaveRead, AxiLiteSlave
from .axil_ram import AxiLiteRamWrite, AxiLiteRamRead, AxiLiteRam

from .axi_channels import AxiAWBus, AxiWBus, AxiBBus, AxiARBus, AxiRBus
from .axi_channels import AxiWriteBus, AxiReadBus, AxiBus
from .axi_master import AxiMasterWrite, AxiMasterRead, AxiMaster
from .axi_slave import AxiSlaveWrite, AxiSlaveRead, AxiSlave
from .axi_ram import AxiRamWrite, AxiRamRead, AxiRam
