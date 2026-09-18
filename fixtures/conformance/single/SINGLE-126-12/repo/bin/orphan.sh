#!/bin/sh
setsid sh -c 'trap "" TERM; echo orphan-ready; exec sleep 8' &
i=0
while [ "$i" -lt 60 ]; do
    sleep 1
    i=$((i + 1))
done
