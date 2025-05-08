#!/bin/bash

# VCS가 설치된 기본 경로
VCS_HOME=/usr/synopsys/vcs/T-2022.06-SP2-3
VERDI_HOME=""

# 동일한 버전의 Verdi가 있는지 확인
if [ -d "/usr/synopsys/verdi/T-$(basename $VCS_HOME)" ]; then
    VERDI_HOME="/usr/synopsys/verdi/T-$(basename $VCS_HOME)"
else
    # 동일한 버전이 없으면 가장 최신 버전의 Verdi를 선택
    VERDI_HOME=$(ls -d /usr/synopsys/verdi/* 2>/dev/null | sort -r | head -n 1)
fi

# Verdi가 설치되어 있지 않으면 오류 출력
if [ -z "$VERDI_HOME" ]; then
    echo "❌ Verdi가 설치된 버전을 찾을 수 없습니다. Verdi 설치를 확인하세요."
    exit 1
fi

echo "✅ Verdi 실행: $VERDI_HOME/bin/verdi"

# Verdi 실행
#$VERDI_HOME/bin/verdi -sv -f filelist.f -ssf dump.fsdb -dbdir sim_build/simv.daidir &

# Verdi 실행 명령어
verdi -dbdir sim_build/simv.daidir/ -ssf dump.fsdb &
