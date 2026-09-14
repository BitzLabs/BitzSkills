#!/bin/sh
head="verify-output-head---------------------------------------------"
filler="verify-output-filler-------------------------------------------"
tail="verify-output-tail---------------------------------------------"
echo "$head"
echo "$head" >&2
i=1
while [ "$i" -le 1098 ]; do
    echo "$filler"
    echo "$filler" >&2
    i=$((i + 1))
done
echo "$tail"
echo "$tail" >&2
exit 1
