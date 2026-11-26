#!/bin/ksh
# detlab demo: a "mis-prioritized service" — compute bursts at a raised
# priority, then sleeps. Launched at priority above the app loop, it
# delays the app's timer wakeups (the regression) while leaving enough
# idle gaps for sshd to stay responsive.
while :; do
    i=0
    while [ $i -lt 4000 ]; do
        i=$((i+1))
    done
    sleep 0.004
done
