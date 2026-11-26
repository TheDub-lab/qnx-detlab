#!/bin/bash
# detlab demo — recording script for the QNX Global Hackathon submission.
# Every command is real; the regression is a real dropped-RT-policy mistake.
# Run from ~/Projects/qnx-detlab on a host with the QNX QSTI VM already up.

set -u
cd "$(dirname "$0")/.."

SSH="ssh -p 2222 -i .detlab/qnx_key -o BatchMode=yes root@127.0.0.1"
GREEN='\033[1;32m'; RED='\033[1;31m'; B='\033[1m'; N='\033[0m'

DL() { PYTHONPATH=host python -m detlab "$@"; }

run_scenario_to() {  # run_scenario_to <out.json>
    DL run scenarios/demo.json --target qsti --target-config .detlab/target.json \
       --probe-binary probe/detlab-probe --out "$1" >/dev/null
}

gate() {  # gate <run.json> — runs the check, prints verdict + real exit code
    local rc
    DL check "$1" --baseline baselines/demo.json | sed 's/^/    /'
    rc=${PIPESTATUS[0]}
    if [ "$rc" -eq 0 ]; then
        echo -e "    exit=$rc  ${GREEN}PASS${N}"
    else
        echo -e "    exit=$rc  ${RED}FAIL — the regression is caught${N}"
    fi
    return "$rc"
}

card() {  # card <pause-secs> <lines...>
    local pause="$1"; shift
    clear
    echo -e "\n"
    for line in "$@"; do echo -e "    $line"; done
    sleep "$pause"
}

clear
echo -e "\n\n"
echo -e "    ${B}detlab${N} ${GREEN}— determinism, gated.${N}"
echo -e "    a regression harness for QNX 8.0  ·  QNX Global Hackathon 2026"
sleep 6

card 6 "$B[ 1 ]${N} QNX 8.0 is running here — free QNX Everywhere license, QEMU target"
echo -e "    \$ ssh root@qnx.target"
$SSH 'uname -a' | sed 's/^/    /'
sleep 5

card 5 "$B[ 2 ]${N} The probe: one process on the target, cycle-accurate wakeup timing"
echo -e "    \$ detlab-probe jitter period_us=1000 policy=fifo priority=50"
$SSH '/tmp/detlab-probe jitter period_us=1000 iterations=200 warmup=10 policy=fifo priority=50' \
    | head -c 300 | sed 's/^/    /'
echo " ..."
sleep 6

card 4 "$B[ 3 ]${N} A scenario runs the timing contract — 1,000 wakeups at 100 Hz, SCHED_FIFO"
echo -e "    \$ detlab run scenarios/demo.json --target qsti"
run_scenario_to /tmp/demo-run.json
python3 - <<'EOF' | sed 's/^/    /'
import json
d = json.load(open('/tmp/demo-run.json'))
r = d['results'][0]
s = r['summary']
print(f"{r['id']}   p50={s['p50_ns']/1000:7.1f} us   p99={s['p99_ns']/1000:7.1f} us   max={s['max_ns']/1000:7.1f} us")
EOF
sleep 6

card 4 "$B[ 4 ]${N} Record this as the baseline — the timing contract, as data"
echo -e "    \$ detlab report /tmp/demo-run.json --baseline-out baselines/demo.json"
DL report /tmp/demo-run.json --out /tmp/demo-report.html \
   --baseline-out baselines/demo.json >/dev/null
echo -e "    ${GREEN}baseline recorded: control-loop${N}"
sleep 5

card 4 "$B[ 5 ]${N} The gate: does this build still meet the contract?"
echo -e "    \$ detlab check /tmp/demo-run.json --baseline baselines/demo.json"
gate /tmp/demo-run.json
sleep 5

card 5 "$B[ 6 ]${N} Days later, a config refactor changes the loop's period constant…"
echo -e "    \$ sed -i 's/period_us\": 10000/period_us\": 1000/' scenarios/demo.json   # the mistake"
cp scenarios/demo.json /tmp/demo-scenario-good.json
sed -i 's/period_us": 10000/period_us": 1000/' scenarios/demo.json
sleep 4
echo -e "    \$ detlab run scenarios/demo.json && detlab check …"
run_scenario_to /tmp/demo-run-bad.json
gate /tmp/demo-run-bad.json || true
sleep 7

card 4 "$B[ 7 ]${N} Revert the config, prove the fix"
echo -e "    \$ restore scenarios/demo.json && detlab run … && detlab check …"
cp /tmp/demo-scenario-good.json scenarios/demo.json
run_scenario_to /tmp/demo-run.json
gate /tmp/demo-run.json
sleep 5

card 5 "$B[ 8 ]${N} The same gate, wired into CI: every commit answers"
echo -e "    \"did this change make the system less deterministic?\""
echo ""
echo -e "    detlab — QNX 8.0 · ClockCycles · SIGEV_PULSE · SCHED_FIFO/SPORADIC"
echo -e "    github.com/michaelhammett/qnx-detlab"
sleep 6
clear
