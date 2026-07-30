---
id: SI-SDD-032
raised_by: SDD-REV-006（2026-07-29）SYN-004。SDD-REV-004 からの積み残し
target: sdd_sync の mtime 精度非対称と mutation lock 不参加
proposed_change_type: modify
status: accepted
---
- **目的**: SDD-REV-004（2026-07-22）が指摘しながら spec-issue 化されず、7日以上放置された
  2件を起票する（SI-SDD-031 が扱う追跡機構の欠落の、具体的な帰結）。
  1. **mtime 精度の非対称**: `sdd_sync.py` は `atomic_write_document` で `st_mtime_ns` を
     書き込む一方、`get_mtime` は `st_mtime`（float 秒）で比較する。同一実装内で精度が
     非対称であり、粗い粒度のファイルシステムでは同一秒内の変更を検出できず、
     pull / push が無音で上書きをスキップまたは実施しうる。
  2. **mutation lock 不参加**: `spec_update` 等の変更 CLI は workspace mutation lock へ
     参加して直列化されるが、`sdd_sync.py`（および `migrate_docs.py`）は参加していない。
     並行実行で lost update が起こりうる。
- **提案する修正**:
  1. 比較側を `st_mtime_ns` へ揃える。または mtime 依存をやめて内容ハッシュ比較へ移行する
     （後者は公開契約 SDD-FR-100 の改訂を伴うため Design Gate で裁定する）
  2. `sdd_sync` / `migrate_docs` を mutation lock へ参加させる。参加させない場合は
     設計判断として明記し、適用範囲と残余リスクを限定する
  3. 同一秒内の変更・並行実行の各ケースを unit-test で固定する
- **対象ファイル**: `skills/sdd-docs/scripts/sdd_sync.py`、`skills/sdd-docs/scripts/migrate_docs.py`、
  `skills/sdd-core/scripts/spec_transaction.py`（lock 機構）、SDD-FR-100 / SDD-FR-135 の
  改訂または後継要件、`tests/test_sdd_sync.py`、bitz-sdd マニフェスト。
- **確認観点**: 同一秒内の連続変更で上書き判定が正しいこと。並行 pull / push で lost update が
  起きないこと。既存の mtime 同値化契約（同期直後の逆方向同期を防ぐ）を壊さないこと。
- **影響推定・ロールバック**: 1 が内容ハッシュ比較へ進む場合は公開契約の破壊的変更となり
  Design Gate 必須。`st_mtime_ns` へ揃えるだけなら挙動の厳密化のみで加法的。
  lock 参加は既存 CLI と同じ機構の再利用であり、問題時は参加をやめて現状へ戻せる。
- **依存**: SDD-FR-100（mtime 比較による上書き制御）、SDD-FR-135（frontmatter 境界を保持する同期）、
  SI-SDD-031（レビュー指摘の追跡機構）。

## 予備判定（推薦）— 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。SDD-FR-100 の意図（新しい方を残す）を精度面で満たしに行く |
| ガードレール抵触 | なし |
| 影響範囲 | sdd-docs（同期・移行）、sdd-core（lock）、テスト |
| 軽量レーン適否 | 不適。公開契約の受入基準に触れる可能性がある |

**推薦: accept**。無音のデータ損失は検証で気づけない種類の欠陥であり、
`.spec` と `docs` の双方向同期という中核機能に存在する。7日以上放置された経緯自体が
SI-SDD-031 の必要性の実例でもある。

## 実施

2026-07-30 に **accept**。裁定記録は
`.spec/reports/decision-2026-07-30-order8-design-foundation.md`（裁定I）。
**V4 設計前に解消する**（3.x 無破壊準備フェーズへ後回しにしない）。V4 設計は `.spec` と
`docs` の同期を多用し、無音のデータ損失は成果物の信頼性そのものを崩すためである。

- **提案1**（mtime 精度の統一）— **比較側を `st_mtime_ns` へ揃える案を採用**。
  選択肢にあった**内容ハッシュ比較への移行は採らない** — 公開契約 `SDD-FR-100` の破壊的変更に
  なり、V4 Design Gate 必須の論点を順序8 へ持ち込むことになる。必要性が生じたら V4
  ターゲット設計で再検討する。
- **提案2**（mutation lock 参加）— 実装対象。`sdd_sync` / `migrate_docs` を参加させる。
- **提案3**（同一秒内・並行実行の unit-test）— 実装対象。
- 残余リスク: lock 参加により長時間の同期が他の変更 CLI をロック待ちさせうる。
  粒度・タイムアウトは実装時に実測する。
