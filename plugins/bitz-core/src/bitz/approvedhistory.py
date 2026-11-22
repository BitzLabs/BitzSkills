"""承認済み要求の保護の途中のコミットの読取り（文書・フロントマター・状態仕様 §8.1、ADR-072、ADR-078、ADR-079、ADR-081）。

途中のコミット（intermediate commit）は、`HEAD`から到達でき、基準版から到達できないコミットである。端点の比較で違反になった文書
（違反の候補）がある場合だけ、呼び出し側（:mod:`bitz.basecompare`）が:meth:`History.evaluate`を呼ぶ。違反の候補がなければ、
このモジュールはGitを1回も呼ばない（ADR-072の`Consequences`）。

Gitの呼出し（違反の候補がある場合。1回の`check`で共有する）:

1. `git rev-parse --verify HEAD^{commit}`（`HEAD`の解決）
2. `git merge-base --is-ancestor HEAD <base>`（`HEAD`が基準版と同じなら呼ばない）
3. `git rev-parse --git-path shallow`（シャロークローンの境界のファイルの位置）。境界があれば、`git rev-list HEAD <base>`を1回加える
4. `git rev-list --parents --max-count=<上限+1> HEAD --not <base>`（途中のコミットとその親）
5. 作業ワークスペースのルートごとに、`git rev-parse --show-toplevel`、途中のコミットの外にある親（基準版など）と親のない途中のコミットごとの
   `git ls-tree -r`、途中のコミットの1つ目の親からの差分をまとめて得る`git diff-tree --stdin`の1回、仕様文書のファイルを読む`git cat-file --batch`の1回

Coreが起動するGitは遅延取得をしない（:func:`bitz.gitutil.git_env`）。欠けたオブジェクトはGitから読めないものとし、完全には読めない側にする。

途中のコミットの集合が空であると確定する場合（基準版が`HEAD`と同じ、`HEAD`が基準版の祖先）は、1.と2.だけで終わり、シャロークローンの境界を見ない
（ADR-079の決定1）。
"""

from __future__ import annotations

import heapq
import os
import subprocess
from dataclasses import dataclass

from . import gitutil
from . import limits as limits_mod
from .document import _kind_for_base_path, _process_document_content

#: 途中の状態として認める状態（§8.1）。
DRAFT_STATES = frozenset({"draft", "outdated"})

#: 通常のファイルのモード（`git ls-tree`の種類`blob`のうち、シンボリックリンク`120000`を除く）。
_BLOB_MODES = frozenset({"100644", "100755", "100664"})

#: `git diff-tree --stdin`の1回の呼出しの時間の上限（秒）。途中のコミットの数に比例して出力が増えるので、ほかの呼出しより長くする。
_DIFF_TIMEOUT_SECONDS = 300

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
            cwd=cwd, env=gitutil.git_env(env), capture_output=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _is_hex_oid(token: str) -> bool:
    return len(token) in (40, 64) and all(c in "0123456789abcdef" for c in token)


def _topological_order(commits: list[tuple[str, tuple[str, ...]]]) -> list[str]:
    """途中のコミットを、親（途中のコミットに含まれるもの）が子より先になる順に並べる。

    同じ時点で選べるコミットは、`git rev-list`の出力の逆順（古いものから）で選ぶので、順は入力だけで決まる。再帰を使わない。
    """

    index = {commit: i for i, (commit, _parents) in enumerate(reversed(commits))}
    waiting = {commit: sum(1 for p in parents if p in index) for commit, parents in commits}
    children: dict[str, list[str]] = {}
    for commit, parents in commits:
        for parent in parents:
            if parent in index:
                children.setdefault(parent, []).append(commit)
    ready = [(index[c], c) for c, n in waiting.items() if n == 0]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        _i, commit = heapq.heappop(ready)
        order.append(commit)
        for child in children.get(commit, ()):
            waiting[child] -= 1
            if waiting[child] == 0:
                heapq.heappush(ready, (index[child], child))
    if len(order) != len(commits):
        raise ValueError("途中のコミットの親子の関係が循環しています")
    return order


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
        #: ``(作業ワークスペースのルート（絶対パス）, 違反の候補)``ごとの、コミットからの``doc_id -> [status, ...]``。読めなければ``None``。
        self._documents_by_root: dict[tuple[str, frozenset[str]], dict[str, dict[str, list[str]]] | None] = {}
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
        self, workspace_root: str, workspace_id: str, limits: limits_mod.Limits, candidate_ids: frozenset[str]
    ) -> dict[str, dict[str, list[str]]] | None:
        """途中のコミットとその親のすべてについて、作業ワークスペースのルートの配下の仕様文書を読む（ADR-079の決定2）。

        戻り値はコミットから``doc_id -> [status, ...]``（違反の候補のIDについて、IDを読める版だけ。同じIDの版が2つ以上なら要素も2つ以上）。
        コミット、ツリー、仕様文書のファイルのどれかをGitから読めなければ``None``（完全には読めない）。

        読み方（変わっていない部分木をたどり直さない）:

        - 途中のコミットの外にある親（基準版など）と、親のない途中のコミットは、`git ls-tree -r`で仕様文書の一覧を得る。
        - そのほかの途中のコミットは、1つ目の親の一覧に、`git diff-tree --stdin`で得た1つ目の親からの差分を当てて一覧を得る。
          `git diff-tree`は、同じオブジェクトIDの部分木をたどらず、ルートの`.spec`の外のツリーとファイルを読まない。
        - 一覧に現れたすべての仕様文書のファイルを、`git cat-file --batch`でオブジェクトIDごとに1回だけ読む。
          欠けたオブジェクトは、Gitから読めないものとする（Gitは遅延取得をしない。ADR-082の決定1）。
        - 違反の候補のIDを持つ版だけを、コミットごとに差分で更新して保持する（コミットごとに全体を数え直さない）。
        """

        try:
            return self._read_documents_unchecked(workspace_root, workspace_id, limits, candidate_ids)
        except (gitutil.GitReadError, ValueError, RecursionError, KeyError, IndexError):
            # 出力やオブジェクトの形の不正（`UnicodeDecodeError`は`ValueError`に含む）、深いツリーも、完全には読めない側にする。
            return None

    def _read_documents_unchecked(
        self, workspace_root: str, workspace_id: str, limits: limits_mod.Limits, candidate_ids: frozenset[str]
    ) -> dict[str, dict[str, list[str]]] | None:
        self.git_calls += 1
        toplevel = gitutil.show_toplevel(self._executable, self._cwd, self._env)
        if toplevel is None:
            return None
        offset = os.path.relpath(os.path.abspath(workspace_root), os.path.abspath(toplevel)).replace(os.sep, "/")
        if offset == ".." or offset.startswith("../"):
            return None
        repo_prefix = "" if offset == "." else offset.rstrip("/") + "/"
        spec_pathspec = f"{repo_prefix}.spec"

        commits = self._commits
        parents_of = dict(commits)
        # 一覧を`ls-tree`で得るコミット: 親のない途中のコミットと、途中のコミットの外にある親。
        listed: list[str] = []
        seen: set[str] = set()
        for commit, parents in commits:
            for oid in (commit,) if not parents else parents:
                if (oid == commit or oid not in parents_of) and oid not in seen:
                    seen.add(oid)
                    listed.append(oid)
        diffed = [c for c in _topological_order(commits) if parents_of[c]]
        #: 1つ目の親として一覧を引き継ぐ、まだ処理していない子の数。0になった一覧は引き継いで捨てる（写さない）。
        pending: dict[str, int] = {}
        for commit in diffed:
            first = parents_of[commit][0]
            pending[first] = pending.get(first, 0) + 1

        def locate(repo_path: str) -> tuple[str, str] | None:
            """リポジトリからの相対パスを``(ワークスペースのルートからの相対パス, 種別)``にする。仕様文書でなければ``None``。"""

            if not repo_path.startswith(repo_prefix):
                return None
            rel = repo_path[len(repo_prefix):]
            if not rel.endswith(".md"):
                return None
            kind = _kind_for_base_path(rel)
            return (rel, kind) if kind is not None else None

        versions: dict[tuple[str, str], tuple[str | None, str | None]] = {}
        #: コミットから``(仕様文書の一覧 rel -> oid, 違反の候補のIDを持つ版 rel -> status)``。
        state: dict[str, tuple[dict[str, str], dict[str, tuple[str, str]]]] = {}
        summaries: dict[str, dict[str, list[str]]] = {}

        self.git_calls += 1
        with gitutil.BlobReader(self._executable, toplevel, self._env) as reader:

            def version(oid: str, rel: str, kind: str) -> tuple[str | None, str | None]:
                key = (oid, kind)
                found = versions.get(key)
                if found is None:
                    found = self._read_version(reader, oid, rel, kind, workspace_id, limits)
                    versions[key] = found
                return found

            def summarize(candidates: dict[str, tuple[str, str]]) -> dict[str, list[str]]:
                out: dict[str, list[str]] = {}
                for rel in sorted(candidates):
                    doc_id, status = candidates[rel]
                    out.setdefault(doc_id, []).append(status)
                return out

            for commit in listed:
                self.git_calls += 1
                listing = gitutil.list_base_spec_blobs(self._executable, self._cwd, self._env, commit, workspace_root)
                if listing is None:
                    return None
                files: dict[str, str] = {}
                candidates: dict[str, tuple[str, str]] = {}
                for rel, oid in sorted(listing):
                    if not rel.endswith(".md"):
                        continue
                    kind = _kind_for_base_path(rel)
                    if kind is None:
                        continue
                    files[rel] = oid
                    doc_id, status = version(oid, rel, kind)
                    if doc_id is not None and doc_id in candidate_ids:
                        candidates[rel] = (doc_id, status or "")
                if commit in pending:
                    state[commit] = (files, candidates)
                summaries[commit] = summarize(candidates)

            if diffed:
                self.git_calls += 1
                diffs = self._diff_spec_files(toplevel, [(c, parents_of[c][0]) for c in diffed], spec_pathspec)
                if diffs is None:
                    return None
            else:
                diffs = {}
            for commit in diffed:
                first = parents_of[commit][0]
                pending[first] -= 1
                if pending[first] == 0:
                    files, candidates = state.pop(first)
                else:
                    inherited_files, inherited_candidates = state[first]
                    files, candidates = dict(inherited_files), dict(inherited_candidates)
                for repo_path, dst_mode, dst_oid in diffs.get(commit, ()):
                    located = locate(repo_path)
                    if located is None:
                        continue
                    rel, kind = located
                    files.pop(rel, None)
                    candidates.pop(rel, None)
                    if dst_mode in _BLOB_MODES:
                        files[rel] = dst_oid
                        doc_id, status = version(dst_oid, rel, kind)
                        if doc_id is not None and doc_id in candidate_ids:
                            candidates[rel] = (doc_id, status or "")
                if commit in pending:
                    state[commit] = (files, candidates)
                summaries[commit] = summarize(candidates)
        return summaries

    def _diff_spec_files(
        self, toplevel: str, pairs: list[tuple[str, str]], spec_pathspec: str
    ) -> dict[str, list[tuple[str, str, str]]] | None:
        """``(コミット, 1つ目の親)``ごとに、``spec_pathspec``の配下の差分を``(パス, 変更後のモード, 変更後のオブジェクトID)``で返す。

        `git diff-tree --stdin --always -r -z --no-renames`へ各組を1行ずつ渡す。`--always`で、差分のない組にもコミットの行を出させ、
        出力のコミットの行の並びが入力と一致することを確かめる。失敗した場合と、出力の形が不正な場合は``None``。
        """

        try:
            proc = subprocess.run(
                [self._executable, "--no-optional-locks", "--literal-pathspecs", "diff-tree", "--stdin", "--always",
                 "-r", "-z", "--no-renames", "--no-ext-diff", "--", spec_pathspec],
                cwd=toplevel, env=gitutil.git_env(self._env), capture_output=True, timeout=_DIFF_TIMEOUT_SECONDS,
                input="".join(f"{commit} {parent}\n" for commit, parent in pairs).encode("ascii"),
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        tokens = proc.stdout.split(b"\0")
        if tokens and tokens[-1] == b"":
            tokens.pop()
        out: dict[str, list[tuple[str, str, str]]] = {}
        expected = iter(commit for commit, _parent in pairs)
        current: list[tuple[str, str, str]] | None = None
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token.startswith(b":"):
                if current is None or i + 1 >= len(tokens):
                    return None
                fields = token[1:].split(b" ")
                if len(fields) != 5:
                    return None
                path = tokens[i + 1].decode("utf-8", "surrogateescape")
                current.append((path, fields[1].decode("ascii"), fields[3].decode("ascii")))
                i += 2
                continue
            commit = token.decode("ascii").strip()
            if commit != next(expected, None):
                return None
            current = out.setdefault(commit, [])
            i += 1
        if next(expected, None) is not None:
            return None
        return out

    @staticmethod
    def _read_version(
        reader: gitutil.BlobReader, blob: str, path: str, kind: str, workspace_id: str, limits: limits_mod.Limits
    ) -> tuple[str | None, str | None]:
        """版の``(doc_id, status)``。IDを読めない版（索引に入らない版。ファイルごとの上限の超過を含む）は``(None, None)``。

        内容は現在版と同じ:func:`document._process_document_content`で、IDと状態を確定するところまで読む。`specBytes`、
        `frontmatterBytes`、`documentArrayItemCount`を現在版と同じく当てる（安全な入出力・互換性 §4.1、ADR-078の決定3、ADR-082の決定3）。
        `specBytes`を超えるファイルは、内容を保持せずに読み捨てる。
        """

        obj_type, data = reader.read_object(blob, max_bytes=limits.specBytes)
        if obj_type != "blob":
            raise gitutil.GitReadError("仕様文書のファイルを読めません")
        if data is None:
            return None, None
        entry = _process_document_content(data, path, kind, workspace_id, limits, identity_only=True)
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
        candidates = frozenset(candidate_ids)
        root_key = (os.path.abspath(workspace_root), candidates)
        if root_key not in self._documents_by_root:
            self._documents_by_root[root_key] = self._read_documents(workspace_root, workspace_id, limits, candidates)
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
