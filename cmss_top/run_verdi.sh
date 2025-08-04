#!/bin/bash

VCS_HOME=/usr/synopsys/vcs/T-2022.06-SP2-3
VERDI_HOME=""

if [ -d "/usr/synopsys/verdi/T-$(basename $VCS_HOME)" ]; then
    VERDI_HOME="/usr/synopsys/verdi/T-$(basename $VCS_HOME)"
else
    VERDI_HOME=$(ls -d /usr/synopsys/verdi/* 2>/dev/null | sort -r | head -n 1)
fi

if [ -z "$VERDI_HOME" ]; then
    echo "Not Found Verdi."
    exit 1
fi


#$VERDI_HOME/bin/verdi -sv -f filelist.f -ssf dump.fsdb -dbdir sim_build/simv.daidir &

verdi -dbdir sim_build/simv.daidir/ -ssf dump.fsdb &
