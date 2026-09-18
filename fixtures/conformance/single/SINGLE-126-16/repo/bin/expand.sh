#!/bin/sh
printf '\343\201\202'
i=0
while [ "$i" -lt 6553 ]; do
    printf 'qz'
    i=$((i + 1))
done
printf 'end\n'
