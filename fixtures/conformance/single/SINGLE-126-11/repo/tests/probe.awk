#!/usr/bin/awk -f
# 起動環境を継承し、PWDだけが実効cwdの絶対pathへ置き換わった場合だけ成功する。
# shはPWDを起動時に再計算するため、環境をそのまま読めるawkで観測する。
BEGIN {
    if (ENVIRON["BITZ_FIXTURE_PROBE"] != "inherited-value") exit 11
    if (ENVIRON["LANG"] != "C.UTF-8") exit 12
    if (ENVIRON["LC_COLLATE"] != "C") exit 13
    pwd = ENVIRON["PWD"]
    if (pwd == "/bitz-fixture-stale-pwd") exit 14
    if (substr(pwd, 1, 1) != "/") exit 15
    if ((getline line < (pwd "/probe.awk")) <= 0) exit 16
    count = split(pwd, parts, "/")
    if (parts[count] != "tests") exit 17
    if (ARGC != 3 || ARGV[1] != "test_auth.py" || ARGV[2] != "test_session.py") exit 18
    exit 0
}
