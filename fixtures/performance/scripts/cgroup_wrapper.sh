#!/bin/sh
set -u

control=$1
shift

IFS= read -r _ < "$control/start"
set +e
"$@" > "$control/stdout" 2> "$control/stderr"
code=$?
set -e

temporary="$control/status.tmp"
printf '%s\n' "$code" > "$temporary"
mv "$temporary" "$control/status"

# 親runnerがmemory.peakと残存processを読むまでcgroupを保持する。
IFS= read -r _ < "$control/release" || true
exit "$code"
