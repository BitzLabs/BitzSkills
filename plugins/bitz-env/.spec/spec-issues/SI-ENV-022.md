---
id: SI-ENV-022
raised_by: ルート CORE-FR-012 実地確認（2026-07-18 セッション）からの委任
target: SI-ENV-002/005/007/008/011/014 対応 requirement/SKILL.md の origin: 記録漏れ
proposed_change_type: modify
status: accepted
---
- **目的**: ルートの CORE-FR-012（spec_status.py の accepted 未着手検知）を
  `--workspace . plugins/*` で実地実行したところ、bitz-env workspace で6件
  （SI-ENV-002 / 005 / 007 / 008 / 011 / 014）が「未着手の accepted」として検出されたが、
  いずれも実体照合の結果**実装済み**と確認できた。この6件は bitz-env の既存「軽量レーン」
  運用（`- **実施**: ...` マーカー付与）の対象になっていたにもかかわらず、実施マーカーが
  付けられていなかった（同日 2026-07-12 裁定分の SI-ENV-010/013/015/016/017/020/021 には
  実施マーカーが付いているのに、この6件だけ抜けている運用のムラ）。記録漏れを解消し、
  検知ノイズを減らす。
  - SI-ENV-002: `evals/env-init/` `evals/env-orchestration/` `evals/env-register/`
    `evals/env-doctor/` の4ディレクトリが実在確認済み。
  - SI-ENV-005: `collab-contract.md` にプレフィックス必須・ルーティングテーブルの記述が
    実在確認済み。
  - SI-ENV-007: `collab-contract.md` に客観的状態変化の検収規定が実在確認済み。
  - SI-ENV-008: `ENV-FR-004.md` にマーカー内側整形ルールの記述が実在確認済み。
  - SI-ENV-011: `env-register/SKILL.md` の「### 3. 委譲マトリクスの更新」節に、提案文と
    ほぼ同一の同期規則（「レジストリの登録・更新・削除が完了するたびに、ユーザーの明示依頼の
    有無にかかわらずこのステップを実行する」）が実在確認済み。
  - SI-ENV-014: `env-orchestration/SKILL.md` に break-even 基準との接続記述が実在確認済み。
- **提案する修正**: 各 spec-issue（SI-ENV-002/005/007/008/011/014）本文に、他の
  2026-07-12 裁定分と同じ書式で `- **実施**: 2026-07-18（事後確認） <実装済みの根拠>` 行を
  追記する（既存の bitz-env 実績パターンをそのまま適用。新しいフィールドやスキーマ変更は
  不要）。日付は元々の裁定日（2026-07-12）ではなく、事後確認で判明した本ISSUE起票日
  （2026-07-18）とし、後追い確認である旨を明示する。
- **対象ファイル**: `plugins/bitz-env/.spec/spec-issues/SI-ENV-002.md`, `SI-ENV-005.md`,
  `SI-ENV-007.md`, `SI-ENV-008.md`, `SI-ENV-011.md`, `SI-ENV-014.md`（実施マーカー追記のみ）。
- **確認観点**:
  - `spec_status.py --workspace . plugins/*` を再実行し、bitz-env workspace の
    `accepted_unaddressed` が0件になること
  - `spec_inspect.py --workspace . plugins/*` が引き続き PASS すること
  - 実施マーカーの根拠が、実際に本ISSUEの「目的」節に列挙した実体確認と一致していること
- **影響推定・ロールバック**: spec-issue 本文6件への追記のみ。コード・要件への影響なし。
  追記の削除で即座に revert 可能。
- **依存**: なし（ルートの CORE-FR-012 が本ISSUEの発見契機だが、実施自体は bitz-env
  workspace 内で完結する）。

## 予備判定（推薦） — 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。本文追記のみ |
| ガードレール抵触 | なし |
| 影響範囲 | 限定的。spec-issue 本文6件のみ |
| 軽量レーン適否 | 適（可）。既存の bitz-env 軽量レーン運用パターンをそのまま踏襲するだけ |

**推薦: accept**（根拠: 既に同日裁定で他7件に適用済みの運用パターンを、抜け落ちていた6件へ揃えるだけの低リスク修正）。
最終裁定はユーザー自身の明示指示による `spec_update.py --to accepted --by-human` で行うこと。
- **実施**: 2026-07-18 SI-ENV-002/005/007/008/011/014 の6件全てに実施マーカーを追記済み。
