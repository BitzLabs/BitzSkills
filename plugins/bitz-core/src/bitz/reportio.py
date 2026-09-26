"""明示`--report`のreport書出し（`00_共通契約/02_安全な入出力・互換性.md` §8、`01_結果・…` §8）。

`.spec/reports/`（workspace root相対）へ排他的に作成する。`.spec`と`.spec/reports`は
symlinkを辿らないdirectory fd（`os.open`に`O_DIRECTORY | O_NOFOLLOW`）として開き、以後の
一時fileの作成（`O_CREAT | O_EXCL | O_NOFOLLOW`）、最終report名への確定（`os.link`の
`src_dir_fd`/`dst_dir_fd`）、一時fileの除去（`os.unlink`の`dir_fd`）はすべてそのfd基準で行う。
`.spec/reports`が存在しない場合は`.spec`のfdを`dir_fd`にして`os.mkdir`した後、同じ規則で開き直す。
workspace root自体は（規範の対象外のため）symlinkを辿ってよく、`O_NOFOLLOW`なしのdirectory fd
として開く。

`.spec`または`.spec/reports`のfdを取得する**前**に名前が別directoryへのsymlinkへ差し替えられて
いれば、`O_NOFOLLOW`付きの`open`が`ELOOP`で失敗するため（検査と開封を1回の`open`呼出しへ統合して
いるため、検査と開封の間に差し替えの隙が生じない）、symlink先には何も作成されない。

一方、fdを取得した**後**に名前が差し替えられても、`dir_fd`基準の以後の操作（一時fileの作成・
`os.link`による確定・`os.unlink`による除去）はすでに取得済みのfd（＝差し替え前の実directory）を
参照し続けるため、symlink先ではなく元のdirectoryへ書き込まれてしまう。この場合は書込み自体は
「成功」してしまうが、現在の`.spec`または`.spec/reports`という名前の下にreportが存在しない
（＝symlink先はもちろん、名前が指す場所のどこにも到達できない）ため、`os.link`による確定の直後に
`os.stat(..., follow_symlinks=False)`で現在その名前が指す先の`(st_dev, st_ino)`と、取得済みfdの
`os.fstat`の`(st_dev, st_ino)`を照合し、一致しない（＝directoryそのものが差し替えられた）場合は
確定済みのreportと一時fileをfd基準で除去したうえで書き込まず`SPEC-REPORT-WRITE-001`を返す。この
照合を可能にするため、workspace root自体もdirectory fdとして開き、`.spec`の照合の基準にする。

`os.open`の`dir_fd`・`O_DIRECTORY`・`O_NOFOLLOW`、`os.mkdir`/`os.link`/`os.unlink`の`dir_fd`系引数、
および`os.stat`の`dir_fd`・`follow_symlinks=False`はPOSIX platformでのみ利用できる。Core 1.0の
対象OSはLinuxとmacOSであり（ADR-055、`00_共通契約/06_Core実行環境・CLI基盤契約.md` §2）、これらが
利用できない環境では保証を弱めた代替動作へ切り替えず、reportを書き込まず`SPEC-REPORT-WRITE-001`を返す。
"""

from __future__ import annotations

import json
import os
import stat
import time

from . import messages
from .config import Diagnostic

_SPEC_DIRNAME = ".spec"
_REPORTS_DIRNAME = "reports"

_DIR_FD_FUNCS = (os.open, os.mkdir, os.unlink, os.link, os.stat)
_HAS_DIR_FD_SUPPORT = (
    hasattr(os, "O_DIRECTORY")
    and hasattr(os, "O_NOFOLLOW")
    and all(func in os.supports_dir_fd for func in _DIR_FD_FUNCS)
    and os.stat in os.supports_follow_symlinks
)


def _report_write_failed(workspace_id: str | None) -> Diagnostic:
    return Diagnostic(
        code="SPEC-REPORT-WRITE-001",
        severity="error",
        resultStatus="error",
        summary=messages.REPORT_WRITE_FAILED,
        source={"kind": "file", "workspaceId": workspace_id, "path": ".spec/reports"},
    )


def _open_dir_no_follow(name: str, dir_fd: int) -> int:
    """``dir_fd``基準で``name``をsymlinkを辿らずdirectoryとして開きfdを返す。

    ``name``がsymlink・directory以外・存在しない場合は``OSError``を送出する。
    """

    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    return os.open(name, flags, dir_fd=dir_fd)


def _open_reports_dir(spec_fd: int) -> int | None:
    """``.spec``のfd基準で``reports``をsymlinkを辿らずdirectoryとして開く。

    存在しなければ``.spec``のfdを``dir_fd``にして``mkdir``してから開き直す。失敗時は``None``。
    """

    try:
        return _open_dir_no_follow(_REPORTS_DIRNAME, dir_fd=spec_fd)
    except FileNotFoundError:
        pass
    except OSError:
        return None

    try:
        os.mkdir(_REPORTS_DIRNAME, dir_fd=spec_fd)
    except FileExistsError:
        pass
    except OSError:
        return None

    try:
        return _open_dir_no_follow(_REPORTS_DIRNAME, dir_fd=spec_fd)
    except OSError:
        return None


def _silent_remove(name: str, dir_fd: int) -> None:
    try:
        os.unlink(name, dir_fd=dir_fd)
    except OSError:
        pass


def _same_directory(dir_fd: int, name: str, opened_fd: int) -> bool:
    """``dir_fd``基準で現在``name``が指す先が、``opened_fd``が参照するdirectoryと同一か。

    symlinkへ差し替えられていた場合や、別のdirectoryへ差し替えられていた場合は
    ``False``を返す（``name``の照会自体はsymlinkを辿らない）。
    """

    try:
        looked_up = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    except OSError:
        return False
    if not stat.S_ISDIR(looked_up.st_mode):
        return False
    opened = os.fstat(opened_fd)
    return (looked_up.st_dev, looked_up.st_ino) == (opened.st_dev, opened.st_ino)


def _reports_path_unchanged(root_fd: int, spec_fd: int, reports_fd: int) -> bool:
    """取得済みの``spec_fd``・``reports_fd``が、現在の``.spec``・``.spec/reports``という
    名前が指す先と依然として同一directoryを参照しているか。"""

    return _same_directory(root_fd, _SPEC_DIRNAME, spec_fd) and _same_directory(
        spec_fd, _REPORTS_DIRNAME, reports_fd
    )


def _write_into_reports_dir(
    root_fd: int,
    spec_fd: int,
    reports_fd: int,
    workspace_id: str | None,
    operation: str,
    result: dict,
) -> Diagnostic | None:
    payload = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    tmp_name = f".bitz-report-{os.getpid()}-{time.monotonic_ns()}.tmp"

    try:
        fd = os.open(
            tmp_name,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
            0o644,
            dir_fd=reports_fd,
        )
    except OSError:
        return _report_write_failed(workspace_id)

    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
    except OSError:
        _silent_remove(tmp_name, reports_fd)
        return _report_write_failed(workspace_id)

    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    seq = 0
    while True:
        name = f"{timestamp}-{operation}.json" if seq == 0 else f"{timestamp}-{operation}-{seq}.json"
        try:
            os.link(tmp_name, name, src_dir_fd=reports_fd, dst_dir_fd=reports_fd)
        except FileExistsError:
            seq += 1
            continue
        except OSError:
            _silent_remove(tmp_name, reports_fd)
            return _report_write_failed(workspace_id)
        else:
            if not _reports_path_unchanged(root_fd, spec_fd, reports_fd):
                # `.spec`または`.spec/reports`という名前が、fd取得後に別directory・symlinkへ
                # 差し替えられていた。確定操作自体はfd基準のため取得済みfdが参照する
                # （＝差し替え前の）directoryへは成功しているが、現在の`.spec/reports`という
                # 名前の下にはreportが存在しないため、成功として扱わずreportと一時fileを
                # （差し替え前のdirectoryを参照し続けるfd基準で）除去し、失敗を返す。
                _silent_remove(name, reports_fd)
                _silent_remove(tmp_name, reports_fd)
                return _report_write_failed(workspace_id)
            _silent_remove(tmp_name, reports_fd)
            return None


def write_report(workspace_root: str, workspace_id: str | None, operation: str, result: dict) -> Diagnostic | None:
    """``result``をJSONのままreportへ書き出す。成功なら``None``、失敗ならDiagnosticを返す。"""

    if not _HAS_DIR_FD_SUPPORT:
        return _report_write_failed(workspace_id)

    try:
        root_fd = os.open(workspace_root, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return _report_write_failed(workspace_id)

    try:
        try:
            spec_fd = _open_dir_no_follow(_SPEC_DIRNAME, dir_fd=root_fd)
        except OSError:
            return _report_write_failed(workspace_id)

        try:
            reports_fd = _open_reports_dir(spec_fd)
            if reports_fd is None:
                return _report_write_failed(workspace_id)
            try:
                return _write_into_reports_dir(
                    root_fd, spec_fd, reports_fd, workspace_id, operation, result
                )
            finally:
                os.close(reports_fd)
        finally:
            os.close(spec_fd)
    finally:
        os.close(root_fd)
