"""実行file解決（`03_操作仕様/03_verify.md` §5.1、`04_doctor.md`）。

`doctor`と`verify`は同じ解決関数を使う。argv[0]に`/`があれば絶対pathはそのpath、相対pathは
実効cwdを基準に解決する。`/`がなければ実効環境のPATHを左から探索し、空または相対PATH要素は
実効cwdを基準にする。通常fileでない、存在しない、実行不能なら``None``を返す。
"""

from __future__ import annotations

import os


def resolve_executable(argv0: str, cwd: str, env: dict[str, str]) -> str | None:
    """``argv0``を実効``cwd``・``env``の下で解決する。見つからなければ``None``を返す。"""

    if "/" in argv0:
        candidate = argv0 if os.path.isabs(argv0) else os.path.join(cwd, argv0)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
        return None

    path_value = env.get("PATH", "")
    for directory in path_value.split(os.pathsep):
        if directory == "":
            base = cwd
        elif os.path.isabs(directory):
            base = directory
        else:
            base = os.path.join(cwd, directory)
        candidate = os.path.join(base, argv0)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None
