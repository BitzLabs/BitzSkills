#!/bin/sh
# 空stringのargv[1]を1引数として受け取った場合だけ成功する。
[ "$#" -eq 3 ] || exit 1
[ -z "$1" ] || exit 1
[ "$2" = tests/test_auth.py ] && [ "$3" = tests/test_session.py ] || exit 1
exit 0
