"""frontmatter パーサ4実装の共通テストケース集（P7）。

スキルの自己完結規約によりコード共有はしない方針のため、
「仕様（テストケース）の共有」で4実装の挙動を揃える。
このリポジトリの成果物で実際に使われる書式（column-0 の flat な key、
インラインコメント、クォート値）を契約とし、実装ごとの API 差
（dict / str / None / {}）は吸収して比較する。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load_module(name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


spec_inspect = load_module("p_spec_inspect", "plugins/bitz-sdd/skills/sdd-core/scripts/spec_inspect.py")
docs_inspect = load_module("p_docs_inspect", "plugins/bitz-sdd/skills/sdd-docs/scripts/docs_inspect.py")
sdd_report = load_module("p_sdd_report", "plugins/bitz-sdd/skills/sdd-report/scripts/sdd_report.py")
release_check = load_module("p_release_check", "scripts/release_check.py")

# dict を返す3実装（release_check は文字列 API のため別枠で検証）
DICT_PARSERS = [
    ("spec_inspect", spec_inspect.parse_frontmatter),
    ("docs_inspect", docs_inspect.parse_frontmatter),
    ("sdd_report", sdd_report.parse_frontmatter),
]

# fixture 用 ID は連結で組み立てる（リテラルだと本リポジトリ自身の spec_inspect 走査が
# 幽霊参照として誤検知するため。test_spec_inspect.py と同じ方式）
REQ_ID = "FR-" + "000"

# 共通ケース: (名前, 入力テキスト, 期待するキー→値)
COMMON_CASES = [
    (
        "基本の key: value",
        f"---\nid: {REQ_ID}\nstatus: draft\n---\n\n本文\n",
        {"id": REQ_ID, "status": "draft"},
    ),
    (
        "非クォート値のインラインコメント除去（テンプレート様式）",
        f"---\nid: {REQ_ID}            # 凍結。プレフィックス規約\nstatus: draft         # draft|approved\n---\n本文\n",
        {"id": REQ_ID, "status": "draft"},
    ),
    (
        "クォート値のクォート除去",
        '---\nversion: "1.0.0"\nupdated: \'2026-07-11\'\n---\n本文\n',
        {"version": "1.0.0", "updated": "2026-07-11"},
    ),
]

# frontmatter が無い/閉じていない入力（値が取れてはいけない）
NO_FM_CASES = [
    ("frontmatter なし", f"# 見出しだけの文書\nid: {REQ_ID}\n"),
    ("終端 --- なし", f"---\nid: {REQ_ID}\nstatus: draft\n\n本文\n"),
]


@pytest.mark.parametrize("case_name,text,expected", COMMON_CASES)
@pytest.mark.parametrize("parser_name,parser", DICT_PARSERS)
def test_dict_parsers_agree_on_common_cases(parser_name, parser, case_name, text, expected):
    """3つの dict パーサが、リポジトリで実際に使う書式について同じ値を返すこと"""
    fm = parser(text)
    assert fm, f"{parser_name}: {case_name} で frontmatter を検出できない"
    for key, val in expected.items():
        assert fm.get(key) == val, f"{parser_name}: {case_name} の {key} が {fm.get(key)!r}（期待 {val!r}）"


@pytest.mark.parametrize("case_name,text", NO_FM_CASES)
@pytest.mark.parametrize("parser_name,parser", DICT_PARSERS)
def test_dict_parsers_reject_missing_frontmatter(parser_name, parser, case_name, text):
    """frontmatter が無い/壊れている入力から値を拾わないこと（None か 空 dict）"""
    fm = parser(text)
    assert not fm or not fm.get("id"), f"{parser_name}: {case_name} なのに id を拾った: {fm!r}"


@pytest.mark.parametrize("case_name,text,expected", COMMON_CASES)
def test_release_check_extracts_block(case_name, text, expected):
    """release_check.frontmatter は fm ブロック文字列を返す（キーの存在検査に使うため、キーを含むこと）"""
    block = release_check.frontmatter(text)
    for key in expected:
        assert f"{key}:" in block, f"release_check: {case_name} のブロックに {key}: が無い"


@pytest.mark.parametrize("case_name,text", NO_FM_CASES)
def test_release_check_rejects_missing_frontmatter(case_name, text):
    block = release_check.frontmatter(text)
    assert block == "", f"release_check: {case_name} なのにブロックを返した: {block!r}"
