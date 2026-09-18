#!/bin/sh
# stdinが即時EOFで、1byteも読めない場合だけ成功する。
if IFS= read -r line; then exit 1; fi
[ -z "$line" ] || exit 1
exit 0
