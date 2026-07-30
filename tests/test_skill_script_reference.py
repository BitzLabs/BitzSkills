"""CORE-CON-012 SKILL.md のスクリプト呼び出し表記の回帰テスト（テスト先行）。

SKILL.md はスキルフォルダ単位で任意のプロジェクトへ配置される。実行例のパスが
どこ基準の相対パスか表記から判別できないと、読み手（人間もエージェントも）は
実行すべきパスを決定できない。実測（2026-07-30）では bitz-sdd の呼び出し34件のうち
33件が基準の書かれていない `python3 scripts/<name>.py` 形式で、うち5件は
自スキルに存在しないスクリプト（`sdd_sync.py` は sdd-docs 配下）を参照しており
CORE-CON-004（スキルの自己完結）にも反していた。

許容する3形式:
  <このスキル>/scripts/<name>.py    自スキル同梱。実在をスキルフォルダ内で解決する
  <NAME スキル>/scripts/<name>.py   他スキル同梱。NAME のスキル配下で解決する
  <リポジトリ>/scripts/<name>.py    消費先リポジトリのスクリプト（プラグイン同梱ではない）

検査対象は plugins/*/skills/*/SKILL.md を動的収集する（CORE-CON-011 の
test_cli_contract.py と同型）。新規に追加された SKILL.md も登録なしで対象に入る。
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# `python3 <path>.py` 形式の実行例だけを拾う（散文中のスクリプト名の言及は対象外）
INVOCATION_RE = re.compile(r"python3?\s+(?P<path>(?:<[^>]+>/)?[\w./-]+\.py)")
OWN_SKILL_PREFIX = "<このスキル>/"
REPO_PREFIX = "<リポジトリ>/"
OTHER_SKILL_RE = re.compile(r"^<(?P<name>[\w-]+)\s+スキル>/(?P<rest>.+)$")


def skill_files():
    """plugins/*/skills/*/SKILL.md を動的収集する。"""
    return sorted(ROOT.glob("plugins/*/skills/*/SKILL.md"))


def invocations(path: Path):
    """(行番号, パス表記) の一覧を返す。"""
    found = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for match in INVOCATION_RE.finditer(line):
            found.append((number, match.group("path")))
    return found


def resolve_other_skill(name: str) -> Path | None:
    """スキル名から plugins/*/skills/<name>/ を解決する（プラグイン横断）。"""
    for candidate in ROOT.glob(f"plugins/*/skills/{name}"):
        if candidate.is_dir():
            return candidate
    return None


def test_skill_md_files_are_collected():
    """動的収集が空にならない（収集ロジックの破損で検査が素通りするのを防ぐ）。"""
    assert len(skill_files()) >= 10


@pytest.mark.parametrize("skill_md", skill_files(), ids=lambda p: p.parent.name)
def test_CORE_CON_012_invocations_declare_their_base(skill_md: Path):
    """実行例のパスは基準を明示する（裸の `scripts/<name>.py` を許さない）。"""
    bare = [
        f"{skill_md.relative_to(ROOT)}:{number}: {path}"
        for number, path in invocations(skill_md)
        if not path.startswith("<")
    ]
    assert not bare, (
        "基準の書かれていないパスがあります。`<このスキル>/` `<NAME スキル>/` "
        "`<リポジトリ>/` のいずれかで基準を明示してください:\n" + "\n".join(bare)
    )


@pytest.mark.parametrize("skill_md", skill_files(), ids=lambda p: p.parent.name)
def test_CORE_CON_012_own_skill_scripts_exist(skill_md: Path):
    """`<このスキル>/` が指すスクリプトはそのスキルフォルダに実在する。"""
    skill_dir = skill_md.parent
    missing = [
        f"{skill_md.relative_to(ROOT)}:{number}: {path}"
        for number, path in invocations(skill_md)
        if path.startswith(OWN_SKILL_PREFIX)
        and not (skill_dir / path[len(OWN_SKILL_PREFIX):]).is_file()
    ]
    assert not missing, "自スキルに実在しないスクリプトを参照しています:\n" + "\n".join(missing)


@pytest.mark.parametrize("skill_md", skill_files(), ids=lambda p: p.parent.name)
def test_CORE_CON_012_other_skill_scripts_exist(skill_md: Path):
    """`<NAME スキル>/` が指すスクリプトは当該スキルに実在し、自スキルではない。

    自スキルのスクリプトを `<NAME スキル>/` で書くと、フォルダ単位でコピーされたときに
    読み手が別スキルの導入を要すると誤解する。自スキルは `<このスキル>/` で書く。
    """
    problems = []
    for number, path in invocations(skill_md):
        match = OTHER_SKILL_RE.match(path)
        if match is None:
            continue
        location = f"{skill_md.relative_to(ROOT)}:{number}: {path}"
        if match.group("name") == skill_md.parent.name:
            problems.append(f"{location} — 自スキルなので `{OWN_SKILL_PREFIX}` を使う")
            continue
        other = resolve_other_skill(match.group("name"))
        if other is None:
            problems.append(f"{location} — スキル '{match.group('name')}' が存在しない")
        elif not (other / match.group("rest")).is_file():
            problems.append(f"{location} — 参照先スクリプトが存在しない")
    assert not problems, "他スキル参照が解決できません:\n" + "\n".join(problems)


@pytest.mark.parametrize("skill_md", skill_files(), ids=lambda p: p.parent.name)
def test_CORE_CON_012_repository_scripts_exist(skill_md: Path):
    """`<リポジトリ>/` が指すスクリプトはリポジトリルートから解決できる。"""
    missing = [
        f"{skill_md.relative_to(ROOT)}:{number}: {path}"
        for number, path in invocations(skill_md)
        if path.startswith(REPO_PREFIX) and not (ROOT / path[len(REPO_PREFIX):]).is_file()
    ]
    assert not missing, (
        "リポジトリ側スクリプトが解決できません:\n" + "\n".join(missing)
    )


@pytest.mark.parametrize("skill_md", skill_files(), ids=lambda p: p.parent.name)
def test_CORE_CON_012_placeholder_vocabulary_is_closed(skill_md: Path):
    """パス先頭のプレースホルダは3形式に限る（語彙を閉じてドリフトを止める）。"""
    unknown = []
    for number, path in invocations(skill_md):
        if not path.startswith("<"):
            continue
        if path.startswith((OWN_SKILL_PREFIX, REPO_PREFIX)) or OTHER_SKILL_RE.match(path):
            continue
        unknown.append(f"{skill_md.relative_to(ROOT)}:{number}: {path}")
    assert not unknown, (
        "未知のプレースホルダです。`<このスキル>/` `<NAME スキル>/` `<リポジトリ>/` "
        "のいずれかを使ってください:\n" + "\n".join(unknown)
    )
