"""SDD-FR-137 spec_labels.py の回帰テスト（テスト先行）。

ライフサイクル語彙の対訳辞書（SSOT）の網羅性・表示形式・逆引き一意性と、
sdd-core / sdd-report 間の複製一致を検証する。
"""
import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SDD_CORE_SCRIPTS = REPO / "plugins" / "bitz-sdd" / "skills" / "sdd-core" / "scripts"
SDD_REPORT_SCRIPTS = REPO / "plugins" / "bitz-sdd" / "skills" / "sdd-report" / "scripts"

CORE_LABELS = SDD_CORE_SCRIPTS / "spec_labels.py"
REPORT_LABELS = SDD_REPORT_SCRIPTS / "spec_labels.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def labels():
    return _load(CORE_LABELS, "spec_labels_core")


# --- 辞書の網羅性 -------------------------------------------------------------

def test_status_labels_cover_permission_matrix():
    """対訳辞書は spec_update.py の権限マトリクスに現れる全 status を過不足なく含む。"""
    lb = labels()
    up = _load(SDD_CORE_SCRIPTS / "spec_update.py", "spec_update_for_labels")
    for kind, transitions in up.TRANSITIONS.items():
        used = {s for pair in transitions for s in pair}
        assert set(lb.STATUS_LABELS_JA[kind]) == used, (
            f"{kind}: 対訳辞書と権限マトリクスの status 集合が乖離している")


def test_phase_labels_match_phase_codes():
    """フェーズ対訳は spec_status.py の PHASE_CODES と1対1で対応する。"""
    lb = labels()
    st = _load(SDD_CORE_SCRIPTS / "spec_status.py", "spec_status_for_labels")
    assert set(lb.PHASE_LABELS_JA) == set(st.PHASE_CODES)


def test_confirmed_translations():
    """SI-CORE-018 で人間が確定した訳語そのものを固定する。"""
    lb = labels()
    assert lb.STATUS_LABELS_JA["requirement"] == {
        "draft": "起草中", "approved": "承認済み", "implementing": "実装中",
        "verified": "検証済み", "promoted": "確定", "deprecated": "廃止"}
    assert lb.STATUS_LABELS_JA["spec-issue"] == {
        "open": "裁定待ち", "accepted": "採用", "rejected": "不採用",
        "superseded": "統合済み"}
    assert lb.STATUS_LABELS_JA["task"] == {
        "pending": "着手待ち", "implementing": "実装中", "blocked": "介入待ち",
        "done": "完了"}
    assert lb.PHASE_LABELS_JA == {
        "map": "未着手", "discovery": "企画", "design": "設計", "plan": "要件定義",
        "execute": "実装", "verify": "検証", "done": "確定待ち"}


# --- 表示形式 ----------------------------------------------------------------

def test_status_label_is_japanese_first():
    """status の併記は日本語主（日本語（機械値））。"""
    lb = labels()
    assert lb.status_label("spec-issue", "accepted") == "採用（accepted）"
    assert lb.status_label("requirement", "promoted") == "確定（promoted）"


def test_phase_label_is_english_first():
    """フェーズの併記は英語主（English（日本語））。"""
    lb = labels()
    assert lb.phase_label("execute") == "Execute（実装）"
    assert lb.phase_label("design") == "Design（設計）"


def test_done_phase_label_names_promotion_gate():
    """done は訳語に Gate 名を合成する（SDD-FR-136 の受入基準を維持）。"""
    lb = labels()
    assert lb.phase_label("done") == "Done（確定待ち: Promotion Gate）"


def test_unknown_values_pass_through():
    """未知の status / phase は機械値のまま返し、表示を壊さない。"""
    lb = labels()
    assert lb.status_label("requirement", "unknown-status") == "unknown-status"
    assert lb.phase_label("unknown-phase") == "unknown-phase"


# --- 逆引きの一意性 -----------------------------------------------------------

def test_reverse_lookup_unique_within_kind():
    """同一種別内で日本語ラベルが重複しない（逆引きが一意に定まる）。"""
    lb = labels()
    for kind, table in lb.STATUS_LABELS_JA.items():
        assert len(set(table.values())) == len(table), f"{kind}: 訳語が重複している"


def test_shared_label_maps_to_same_machine_value():
    """種別を跨いで同じ訳語が現れる場合、機械値も一致していなければならない。"""
    lb = labels()
    seen = {}
    for table in lb.STATUS_LABELS_JA.values():
        for machine, ja in table.items():
            assert seen.setdefault(ja, machine) == machine, (
                f"訳語 '{ja}' が異なる機械値に割り当てられている")


# --- 正規化 (SDD-FR-138 が利用) ------------------------------------------------

def test_normalize_accepts_japanese_and_machine_values():
    lb = labels()
    assert lb.normalize_status("spec-issue", "採用") == "accepted"
    assert lb.normalize_status("requirement", "承認済み") == "approved"
    assert lb.normalize_status("requirement", "approved") == "approved"


def test_normalize_rejects_combined_form():
    """併記形は受理しない（機械値と純粋な日本語ラベルの2種のみ）。"""
    lb = labels()
    assert lb.normalize_status("spec-issue", "採用（accepted）") != "accepted"


def test_normalize_passes_unknown_through():
    """未知語はそのまま返し、呼び出し側の権限マトリクスで不正遷移として弾かせる。"""
    lb = labels()
    assert lb.normalize_status("requirement", "でたらめ") == "でたらめ"


# --- SSOT と複製の一致 ---------------------------------------------------------

def test_sdd_report_copy_is_identical():
    """sdd-report の複製は sdd-core の SSOT と完全一致する（自己完結原則の代償の担保）。"""
    assert REPORT_LABELS.exists(), "sdd-report 側に spec_labels.py の複製が必要"
    assert CORE_LABELS.read_bytes() == REPORT_LABELS.read_bytes(), (
        "sdd-core と sdd-report の対訳辞書が乖離している（両方を同時に更新すること）")
