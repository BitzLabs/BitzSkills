"""承認済み要求の保護の途中のコミットの読取り（文書・フロントマター・状態仕様 §8.1、ADR-072、ADR-078、ADR-079、ADR-081）。

途中のコミット（intermediate commit）は、`HEAD`から到達でき、基準版から到達できないコミットである。端点の比較で違反になった文書
（違反の候補）がある場合だけ、呼び出し側（:mod:`bitz.basecompare`）が:meth:`History.evaluate`を呼ぶ。違反の候補がなければ、
このモジュールはGitを1回も呼ばない（ADR-072の`Consequences`）。

Gitの呼出し（違反の候補がある場合。1回の`check`で共有する）:

1. `git rev-parse --verify HEAD^{commit}`（`HEAD`の解決）
2. `git merge-base --is-ancestor HEAD <base>`（`HEAD`が基準版と同じなら呼ばない）
3. `git rev-parse --git-path shallow`（シャロークローンの境界のファイルの位置）。境界があれば、`git rev-list HEAD <base>`を1回加える
4. `git rev-list --parents --max-count=<上限+1> HEAD --not <base>`（途中のコミットとその親）
5. 作業ワークスペースのルートごとに、`git rev-parse --show-toplevel`と`git cat-file --batch`（コミット、ツリー、ブロブを1つのプロセスで読む）

途中のコミットの集合が空であると確定する場合（基準版が`HEAD`と同じ、`HEAD`が基準版の祖先）は、1.と2.だけで終わり、シャロークローンの境界を見ない
（ADR-079の決定1）。
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from . import gitutil
from . import limits as limits_mod
from .document import _kind_for_base_path, _process_document_content

#: 途中の状態として認める状態（§8.1）。
DRAFT_STATES = frozenset({"draft", "outdated"})

#: `.spec/`の配下で仕様文書を置くディレクトリ（基準版の仕様文書の一覧と同じ。`document._kind_for_base_path`）。
_KIND_DIRS = frozenset({b"requirements", b"technical", b"decisions", b"tasks"})

_TREE_MODE = b"40000"
#: 通常のファイル（`git ls-tree`の種類`blob`のうち、シンボリックリンク`120000`を除く）。
_BLOB_MODES = frozenset({b"100644", b"100755", b"100664"})

_STATE_EMPTY = "empty"
_STATE_INCOMPLETE = "incomplete"
_STATE_READY = "ready"


@dataclass(frozen=True)
class Verdict:
    """違反の候補の判定の結果。

    ``incomplete``が真なら、途中のコミットの集合を完全に得られない（§8.1）。違反の候補はすべて違反のままとし、
    `CHECK-APPROVED-MEANING-HISTORY`の文言を使う。``recognized``は、途中の状態（状態を`draft`または`outdated`へ変えた版）が
    見つかった文書のIDの集合で、``incomplete``のときは常に空である。
    """

    incomplete: bool
    recognized: frozenset[str]


ENDPOINT_ONLY = Verdict(incomplete=False, recognized=frozenset())
INCOMPLETE = Verdict(incomplete=True, recognized=frozenset())


def _run(executable: str, cwd: str, env: dict[str, str], *args: str) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            [executable, "--no-optional-locks", *args],
            cwd=cwd, env=env, capture_output=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _is_hex_oid(token: str) -> bool:
    return len(token) in (40, 64) and all(c in "0123456789abcdef" for c in token)


def _parse_tree(data: bytes, hash_bytes: int) -> list[tuple[bytes, bytes, str]]:
    """ツリーオブジェクトの内容を``(mode, name, oid)``の一覧にする。形式が不正なら:class:`gitutil.GitReadError`。"""

    entries: list[tuple[bytes, bytes, str]] = []
    pos = 0
    length = len(data)
    while pos < length:
        space = data.find(b" ", pos)
        nul = data.find(b"\0", space + 1) if space >= 0 else -1
        if space < 0 or nul < 0 or nul + 1 + hash_bytes > length:
            raise gitutil.GitReadError("ツリーオブジェクトの形式が不正です")
        mode = data[pos:space]
        name = data[space + 1 : nul]
        oid = data[nul + 1 : nul + 1 + hash_bytes].hex()
        entries.append((mode, name, oid))
        pos = nul + 1 + hash_bytes
    return entries


class History:
    """1回の`check`の途中のコミットの読取り。結果をキャッシュし、複数の作業ワークスペースで共有する。

    ``limit``は`limits.historyCommitCount`（単一ワークスペースでは作業ワークスペースの設定、複合ワークスペースではルートの設定。
    安全な入出力・互換性 §4.1）。
    """

    def __init__(self, executable: str, cwd: str, env: dict[str, str], base_commit: str, limit: int) -> None:
        self._executable = executable
        self._cwd = cwd
        self._env = env
        self._base = base_commit
        self._limit = limit
        self._state: str | None = None
        #: 途中のコミットと、その親（`git rev-list --parents`の順）。
        self._commits: list[tuple[str, tuple[str, ...]]] = []
        #: 作業ワークスペースのルート（絶対パス）ごとの、コミットからの``doc_id -> [status, ...]``。読めなければ``None``。
        self._documents_by_root: dict[str, dict[str, dict[str, list[str]]] | None] = {}
        #: Gitを呼んだ回数（単体試験が、違反の候補がない場合に呼ばないことを確かめる）。
        self.git_calls = 0

    # --- 途中のコミットの集合 ---------------------------------------------------------------

    def _git(self, *args: str) -> subprocess.CompletedProcess | None:
        self.git_calls += 1
        return _run(self._executable, self._cwd, self._env, *args)

    def _resolve_head(self) -> str | None:
        proc = self._git("rev-parse", "--verify", "--quiet", "HEAD^{commit}")
        if proc is None or proc.returncode != 0:
            return None
        out = proc.stdout.decode("ascii", "replace").strip()
        return out if _is_hex_oid(out) else None

    def _shallow_boundaries(self) -> list[str] | None:
        """シャロークローンの境界のコミット（`.git/shallow`）。シャロークローンでなければ空。読めなければ``None``。"""

        proc = self._git("rev-parse", "--git-path", "shallow")
        if proc is None or proc.returncode != 0:
            return None
        rel = os.fsdecode(proc.stdout.rstrip(b"\n"))
        if not rel:
            return None
        path = rel if os.path.isabs(rel) else os.path.join(self._cwd, rel)
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except FileNotFoundError:
            return []
        except OSError:
            return None
        tokens = raw.decode("ascii", "replace").split()
        if any(not _is_hex_oid(t) for t in tokens):
            return None
        return tokens

    def _compute_state(self) -> str:
        head = self._resolve_head()
        if head is None:
            # `HEAD`を解決できなければ、途中のコミットの集合をGitから読めない（§8.1）。
            return _STATE_INCOMPLETE
        if head == self._base:
            return _STATE_EMPTY
        proc = self._git("merge-base", "--is-ancestor", head, self._base)
        if proc is not None and proc.returncode == 0:
            return _STATE_EMPTY
        if proc is None or proc.returncode not in (0, 1):
            return _STATE_INCOMPLETE

        boundaries = self._shallow_boundaries()
        if boundaries is None:
            return _STATE_INCOMPLETE
        if boundaries:
            # 境界のコミットのいずれかが`HEAD`または基準版から到達できれば、完全に得られない（§8.1）。
            proc = self._git("rev-list", head, self._base)
            if proc is None or proc.returncode != 0:
                return _STATE_INCOMPLETE
            reachable = set(proc.stdout.decode("ascii", "replace").split())
            if any(b in reachable for b in boundaries):
                return _STATE_INCOMPLETE

        # 途中のコミットの数（`HEAD`自身とマージコミットを含む）が上限より大きければ、完全に得られない（§4.1）。
        # 上限より1つ多く読めば超過を判定できるので、それ以上は列挙しない。
        proc = self._git("rev-list", "--parents", f"--max-count={self._limit + 1}", head, "--not", self._base)
        if proc is None or proc.returncode != 0:
            return _STATE_INCOMPLETE
        commits: list[tuple[str, tuple[str, ...]]] = []
        for line in proc.stdout.decode("ascii", "replace").splitlines():
            tokens = line.split()
            if not tokens or any(not _is_hex_oid(t) for t in tokens):
                return _STATE_INCOMPLETE
            commits.append((tokens[0], tuple(tokens[1:])))
        if len(commits) > self._limit:
            return _STATE_INCOMPLETE
        if not commits:
            # `HEAD`が基準版から到達できる（上の祖先の判定と同じ。念のため端点の比較だけで判定する）。
            return _STATE_EMPTY
        self._commits = commits
        return _STATE_READY

    def _ensure_state(self) -> str:
        if self._state is None:
            self._state = self._compute_state()
        return self._state

    # --- 途中のコミットとその親の仕様文書 -----------------------------------------------------

    def _read_documents(
        self, workspace_root: str, workspace_id: str, limits: limits_mod.Limits
    ) -> dict[str, dict[str, list[str]]] | None:
        """途中のコミットとその親のすべてについて、作業ワークスペースのルートの配下の仕様文書を読む（ADR-079の決定2）。

        戻り値はコミットから``doc_id -> [status, ...]``（IDを読める版だけ。同じIDの版が2つ以上なら要素も2つ以上）。
        コミット、ツリー、仕様文書のファイルのどれかをGitから読めなければ``None``（完全には読めない）。
        ルートの外のツリーとファイルは読まない（ルートへの経路のツリーだけを読む）。
        """

        self.git_calls += 1
        toplevel = gitutil.show_toplevel(self._executable, self._cwd, self._env)
        if toplevel is None:
            return None
        offset = os.path.relpath(os.path.abspath(workspace_root), os.path.abspath(toplevel)).replace(os.sep, "/")
        if offset == ".":
            components: list[bytes] = []
        elif offset == ".." or offset.startswith("../"):
            return None
        else:
            components = [os.fsencode(part) for part in offset.split("/") if part]

        wanted: list[str] = []
        seen: set[str] = set()
        for commit, parents in self._commits:
            for oid in (commit, *parents):
                if oid not in seen:
                    seen.add(oid)
                    wanted.append(oid)

        tree_cache: dict[str, list[tuple[bytes, bytes, str]]] = {}
        version_cache: dict[tuple[str, str], tuple[str | None, str | None]] = {}
        out: dict[str, dict[str, list[str]]] = {}
        self.git_calls += 1
        try:
            with gitutil.BlobReader(self._executable, toplevel, self._env) as reader:
                hash_bytes = len(wanted[0]) // 2 if wanted else 20

                def tree(oid: str) -> list[tuple[bytes, bytes, str]]:
                    cached = tree_cache.get(oid)
                    if cached is None:
                        obj_type, data = reader.read_object(oid)
                        if obj_type != "tree" or data is None:
                            raise gitutil.GitReadError("ツリーオブジェクトを読めません")
                        cached = _parse_tree(data, hash_bytes)
                        tree_cache[oid] = cached
                    return cached

                def subtree(oid: str, name: bytes) -> str | None:
                    for mode, entry_name, entry_oid in tree(oid):
                        if entry_name == name:
                            return entry_oid if mode == _TREE_MODE else None
                    return None

                def walk(oid: str, prefix: str, files: list[tuple[str, str]]) -> None:
                    for mode, name, entry_oid in tree(oid):
                        rel = f"{prefix}/{os.fsdecode(name)}"
                        if mode == _TREE_MODE:
                            walk(entry_oid, rel, files)
                        elif mode in _BLOB_MODES:
                            files.append((rel, entry_oid))

                for commit in wanted:
                    obj_type, data = reader.read_object(commit)
                    if obj_type != "commit" or data is None or not data.startswith(b"tree "):
                        raise gitutil.GitReadError("コミットオブジェクトを読めません")
                    current: str | None = data[5 : data.index(b"\n")].decode("ascii")
                    for component in [*components, b".spec"]:
                        current = subtree(current, component) if current is not None else None
                    files: list[tuple[str, str]] = []
                    if current is not None:
                        for mode, name, entry_oid in tree(current):
                            if mode == _TREE_MODE and name in _KIND_DIRS:
                                walk(entry_oid, f".spec/{os.fsdecode(name)}", files)
                    documents: dict[str, list[str]] = {}
                    for path, blob in sorted(files):
                        if not path.endswith(".md"):
                            continue
                        kind = _kind_for_base_path(path)
                        if kind is None:
                            continue
                        key = (blob, path)
                        version = version_cache.get(key)
                        if version is None:
                            version = self._read_version(reader, blob, path, kind, workspace_id, limits)
                            version_cache[key] = version
                        doc_id, status = version
                        if doc_id is not None:
                            documents.setdefault(doc_id, []).append(status or "")
                    out[commit] = documents
        except gitutil.GitReadError:
            return None
        return out

    @staticmethod
    def _read_version(
        reader: gitutil.BlobReader, blob: str, path: str, kind: str, workspace_id: str, limits: limits_mod.Limits
    ) -> tuple[str | None, str | None]:
        """版の``(doc_id, status)``。IDを読めない版（索引に入らない版。ファイルごとの上限の超過を含む）は``(None, None)``。

        内容は現在版と同じ:func:`document._process_document_content`で読む（`specBytes`、`frontmatterBytes`を同じく当てる。
        ADR-078の決定3）。`specBytes`を超えるファイルは、内容を保持せずに読み捨てる。
        """

        obj_type, data = reader.read_object(blob, max_bytes=limits.specBytes)
        if obj_type != "blob":
            raise gitutil.GitReadError("仕様文書のファイルを読めません")
        if data is None:
            return None, None
        entry = _process_document_content(data, path, kind, workspace_id, limits)
        if entry.doc_id is None:
            return None, None
        return entry.doc_id, entry.status

    # --- 判定 ----------------------------------------------------------------------------

    def evaluate(
        self, workspace_root: str, workspace_id: str, limits: limits_mod.Limits, candidate_ids: set[str]
    ) -> Verdict:
        """違反の候補``candidate_ids``について、途中の状態の有無と、完全に読めるかを判定する（§8.1）。"""

        if not candidate_ids:
            return ENDPOINT_ONLY
        state = self._ensure_state()
        if state == _STATE_EMPTY:
            return ENDPOINT_ONLY
        if state == _STATE_INCOMPLETE:
            return INCOMPLETE
        root_key = os.path.abspath(workspace_root)
        if root_key not in self._documents_by_root:
            self._documents_by_root[root_key] = self._read_documents(workspace_root, workspace_id, limits)
        documents = self._documents_by_root[root_key]
        if documents is None:
            return INCOMPLETE
        recognized = frozenset(
            doc_id for doc_id in candidate_ids if self._has_intermediate_state(documents, doc_id)
        )
        return Verdict(incomplete=False, recognized=recognized)

    def _has_intermediate_state(self, documents: dict[str, dict[str, list[str]]], doc_id: str) -> bool:
        """途中のコミットのうち少なくとも1つが、文書の状態を`draft`または`outdated`へ変えたか（§8.1、ADR-081）。

        変えたとは、そのコミットの版（同じIDの版がちょうど1つ）の状態が`draft`または`outdated`で、親の少なくとも1つで、
        同じIDの文書が存在しないか、その状態が`draft`でも`outdated`でもないことをいう。親のないコミットでは、すべての文書の状態を
        変えたものとする。親に同じIDの文書が2つ以上あれば、その親との比較では状態を変えたとしない（ADR-079の決定4、ADR-081の決定2）。
        """

        for commit, parents in self._commits:
            versions = documents[commit].get(doc_id, [])
            if len(versions) != 1 or versions[0] not in DRAFT_STATES:
                continue
            if not parents:
                return True
            for parent in parents:
                previous = documents[parent].get(doc_id, [])
                if len(previous) >= 2:
                    continue
                if not previous or previous[0] not in DRAFT_STATES:
                    return True
        return False
