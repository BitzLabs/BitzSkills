---
implements: SDD-FR-156
depends_on: [SDD-TSK-044]
boundary: skills/sdd-core/scripts/spec_status.py, skills/sdd-core/references/adoption-metrics.md, tests/test_spec_status.py
status: done
---

### 未検分の代行遷移を decision_ref 単位で集計し可視化する

- **作業内容**: `spec_status.py` に `unreviewed_proxy_decisions`（`count` /
  `oldest_age_days` / `decision_refs`）を**加算のみ**で追加する。判定は
  `provenance.kind` が `agent-proxy-unverified` の STATE event のうち、`decision_ref` が
  どの GatePassage の `confirmed_decision_refs` にも現れないもの。フラグメント無しで
  裁定記録そのものを確認した GatePassage は同一ファイルのアンカーも覆う。対象成果物が
  promoted に到達したかは判定に使わない（spec-issue の代行遷移を永久滞留にしないため）。
  次アクション候補とテキスト出力へ件数・裁定記録数・最古の滞留日数を出し、
  **滞留ゼロのワークスペースでは出力しない**。GatePassage の読み取りは `spec_inspect` の
  `load_gate_passages` / `gate_field_list` を共有し二重実装しない。
  `adoption-metrics.md` に2指標を機械集計とセットで定義し、閾値は宣言しない。
- **備考**: 本文にタスク自身の ID を書くと spec_inspect が幽霊参照として検出するため記載しない（SI-CORE-002 参照）。
