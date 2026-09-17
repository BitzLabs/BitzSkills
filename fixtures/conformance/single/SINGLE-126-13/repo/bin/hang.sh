#!/bin/sh
trap '' TERM
sh -c "trap '' TERM; sleep 60" &
echo hang-ready
i=0
while [ "$i" -lt 60 ]; do
    sleep 1
    i=$((i + 1))
done
