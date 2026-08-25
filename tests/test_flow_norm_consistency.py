"""FLW-REV-029:GP-003 / GP-004 — 規範と証跡が実装から乖離しないことを機械検査する。

`FLW-REV-029` は 2 種類の乖離を指摘した。

- **`SYN-003`**: 2026-08-24 の Linux 限定の裁定が §1.1／§13.5 にしか適用されず、
  `FLW-NFR-014` の `verified` 昇格条件、`FLW-DSN-017` §7 の fixture 要求、§13.7 の
  Gate blocking には「3 OS」が残っていた。**規範が互いに矛盾していた。**
- **`SYN-004`**: tmpfs を allowlist から外し case 判定を mount 局所へ変えたのに、
  §13.5 の証跡欄は「ext4・tmpfs で SUPPORTED」「swapcase path の存在で判定」のまま
  だった。**撤回した事実を証跡が主張し続けていた。**

どちらも「直した」あとに「他の箇所も直ったか」を確認していなかったことが原因である。
本ファイルは**実装を正**として、規範文書がそこから乖離していないかを検査する。

`GP-006` に従い source 文字列の照合は用途を限定する — ここで見るのは実装コードではなく
**規範文書の主張**であり、主張の照合はこの方式でしか行えない。実装側の振る舞いは
`test_flow_m2_platform_probe.py` などが担う。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "plugins" / "bitz-flow" / ".spec"
SKILL = ROOT / "plugins" / "bitz-flow" / "skills" / "flow-core"
sys.path.insert(0, str(SKILL / "scripts"))

from flowlib import worktree_platform as PF  # noqa: E402

#: 保証範囲を語る規範文書。ここに「保証対象外の OS を保証する」記述があってはならない。
NORMATIVE = (
    SPEC / "design" / "FLW-DSN-017.md",
    SPEC / "requirements" / "FLW-NFR-014.md",
    SPEC / "requirements" / "FLW-FR-006.md",
)

#: 保証範囲を広く読ませる言い回し。裁定で範囲を狭めたときに置き去りになりやすい。
WIDER_SCOPE_CLAIMS = (
    "対象3 OS",
    "3種の実観測",
    "Linux、macOS、Windowsの適用可能",
    "Linux・macOS・Windowsの登録済み",
)


def _out_of_scope_platforms() -> set[str]:
    return set(PF.PLATFORMS) - set(PF.SUPPORTED_SCOPE)


@pytest.mark.parametrize("path", NORMATIVE, ids=lambda p: p.stem)
def test_normative_documents_do_not_claim_a_wider_guarantee_scope(path):
    """規範が保証対象外の platform まで保証すると読める記述を持たないこと。

    実装の正は `SUPPORTED_SCOPE` である。裁定で範囲を狭めたら規範も追随しなければ、
    どちらを満たせばよいか決まらない（`FLW-REV-029:SYN-003`）。
    """
    text = path.read_text(encoding="utf-8")
    # Revision History は「何を直したか」を記すために旧文言を引用する。履歴まで
    # 禁じると変更の経緯を残せなくなるため、本文だけを対象にする。
    body = text.split("Revision History")[0]
    found = [claim for claim in WIDER_SCOPE_CLAIMS if claim in body]
    assert not found, (
        f"{path.name}: 保証範囲を広く読ませる記述 {found}。"
        f"保証対象は {sorted(PF.SUPPORTED_SCOPE)} のみである"
    )


def test_design_platform_labels_match_the_scope_exactly():
    """§13.5 の保証対象／対象外ラベルが `SUPPORTED_SCOPE` と**厳密に一致**すること。

    片方向だけ（対象外が明示されているか）を見ると、`SUPPORTED_SCOPE` を広げたときに
    検査が空振りする（実際に空振りした）。両方向を突き合わせる。
    """
    text = (SPEC / "design" / "FLW-DSN-017.md").read_text(encoding="utf-8")
    section = text[text.index("### 13.5 platform reality表"):text.index("### 13.6 ")]
    labelled_in = {m for m in PF.PLATFORMS if f"| {m}（**保証対象**）" in section}
    labelled_out = {m for m in PF.PLATFORMS if f"| {m}（**保証対象外**）" in section}
    assert labelled_in == set(PF.SUPPORTED_SCOPE), (
        f"§13.5 の保証対象 {sorted(labelled_in)} が SUPPORTED_SCOPE "
        f"{sorted(PF.SUPPORTED_SCOPE)} と一致しない"
    )
    assert labelled_out == _out_of_scope_platforms(), (
        f"§13.5 の保証対象外 {sorted(labelled_out)} が実際の対象外 "
        f"{sorted(_out_of_scope_platforms())} と一致しない"
    )
    assert labelled_in | labelled_out == set(PF.PLATFORMS), "§13.5 に未分類の platform がある"


def test_platform_reality_table_matches_the_allowlist():
    """§13.5 が挙げる filesystem が registry の allowlist と一致すること。

    tmpfs を allowlist から外したのに証跡欄が「tmpfs で SUPPORTED」と主張し続けていた
    （`FLW-REV-029:SYN-004`）。撤回した事実を証跡が主張してはならない。
    """
    text = (SPEC / "design" / "FLW-DSN-017.md").read_text(encoding="utf-8")
    section = text[text.index("### 13.5 platform reality表"):text.index("### 13.6 ")]
    profiles = PF.load_support_profiles(PF.SUPPORT_REGISTRY_PATH)
    allowed = set()
    for platform in PF.SUPPORTED_SCOPE:
        allowed |= set(profiles[platform].filesystem_types)

    # `SUPPORTED` を主張する箇所の**直前**に並ぶ filesystem 名を取り出す。
    # 「ext4・tmpfs で `SUPPORTED`」のように連記されるため、`X で SUPPORTED` の
    # 完全一致では列挙の 2 件目以降を取りこぼす（実際に取りこぼした）。
    problems = []
    for claim in re.finditer(r"([^。｜|]*?)で`SUPPORTED`", section):
        for name in re.findall(r"[A-Za-z0-9]+", claim.group(1)):
            lowered = name.lower()
            if lowered in {"linux", "macos", "windows", "wsl2"} or lowered.isdigit():
                continue
            if lowered in allowed:
                continue
            if lowered in {"tmpfs", "apfs", "hfs", "ntfs", "refs", "nfs", "overlay"} or \
                    re.fullmatch(r"\d+p", lowered):
                problems.append(name)
    assert not problems, (
        f"§13.5 が allowlist 外の filesystem を SUPPORTED として記述している: "
        f"{sorted(set(problems))}（allowlist: {sorted(allowed)}）"
    )


def test_design_does_not_describe_a_replaced_probe_method():
    """§13.5 の probe 方法が置き換え前の記述を残していないこと。

    case 判定は `FLW-TSK-125` で mount 局所へ、filesystem 種別は mount point 最長一致へ
    変えた。証跡欄が旧方式を書いたままだと、読み手は実装と違うものを検証したと誤解する。
    """
    text = (SPEC / "design" / "FLW-DSN-017.md").read_text(encoding="utf-8")
    section = text[text.index("### 13.5 platform reality表"):text.index("### 13.6 ")]
    for retired in ("swapcase pathの存在で判定", "`st_dev`（major:minor）で引きfstype"):
        assert retired not in section, f"§13.5 が置き換え前の probe 方法を記述している: {retired}"


def test_scope_source_of_truth_is_named_in_the_norms():
    """規範が保証範囲の正（`SUPPORTED_SCOPE`）を名指ししていること。

    名指ししていないと、次に範囲が変わったとき規範のどこを直すか判らない。
    """
    for path in (SPEC / "design" / "FLW-DSN-017.md",
                 SPEC / "requirements" / "FLW-NFR-014.md"):
        text = path.read_text(encoding="utf-8")
        assert "SUPPORTED_SCOPE" in text, f"{path.name}: 保証範囲の正を名指ししていない"
