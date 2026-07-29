---
id: SI-SDD-031
raised_by: SDD-REV-006（2026-07-29）SYN-001
target: レビュー指摘の消化が追跡されない
proposed_change_type: modify
status: accepted
---
- **目的**: SDD-REV-004（2026-07-22）は自身の P1 指摘（`sdd_sync` の mtime 精度による無音データ
  損失リスク）について「別途 spec-issue 化を推奨」と明記したうえで `decision: PASS` とした。
  しかし spec-issue は起票されず、実装も 2026-07-29 現在まで未変更である。次のレビュー
  SDD-REV-005 はスコープが異なるため拾わず、`review-synthesis.json` の `gate_preconditions` は
  空配列のままだった。同じ経路で「`sdd_sync` が mutation lock に不参加」「Discovery が停止」も
  未消化のまま残っている。**レビューは実施されても効果が消える構造**になっており、
  多観点レビュー機構そのものの費用対効果が失われている。
- **提案する修正**:
  1. synthesis の各 finding に**追跡先（spec-issue ID）を持たせる**。P0/P1 は必須とし、
     未紐づけの P0/P1 がある状態で `decision: PASS` を出せないようにする
  2. `gate_preconditions` を実際に運用する。未消化の前提条件がある間は Design Gate /
     Promotion Gate を通過できないことを機械検証する
  3. 過去レビューの未消化指摘を次レビューへ**持ち越す**機構を定義する
     （`review-synthesis` は最新1件で上書きされるため、現状は前回の未消化が消える）
  4. 上記を `spec_inspect` または `sdd_report` のいずれで検査するかを Design Gate で確定する
- **対象ファイル**: `skills/sdd-review/SKILL.md`、`skills/sdd-review/references/synthesis.md`、
  `skills/sdd-core/references/gates.md`、`skills/sdd-core/scripts/spec_inspect.py` または
  `skills/sdd-report/scripts/sdd_report.py`、SDD-FR-060 の改訂または後継要件、
  関連テスト、bitz-sdd マニフェスト。
- **確認観点**: 未紐づけの P0/P1 がある synthesis が PASS にならないこと。前回の未消化指摘が
  次レビューへ持ち越されること。指摘ゼロのレビューでノイズが出ないこと。
  既存の SDD-REV-002〜005 を遡及的に不整合としないこと。
- **影響推定・ロールバック**: レビュー成果物の schema と Gate 判定に触れるため軽量レーン不可・
  Design Gate 必須。検査の追加は加法的で、問題時は検査だけ無効化して schema は残せる。
- **依存**: SDD-FR-060（統合報告書の decision 必須出力）、SI-SDD-028（Promotion Gate の運用）。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。SDD-FR-060 の decision 出力を保ったまま追跡項目を足す |
| ガードレール抵触 | なし |
| 影響範囲 | sdd-review（synthesis schema）、sdd-core（Gate 判定）、検査・テスト |
| 軽量レーン適否 | 不適。成果物 schema と Gate 判定に触れる |

**推薦: accept、かつ最優先**。SDD-REV-006 が P0 とした唯一の新規指摘であり、
**他の全指摘の前提条件**である。この仕組みが無いまま設計フェーズへ進むと、
SDD-REV-006 自身の指摘も SDD-REV-004 と同じ経路で消える。
