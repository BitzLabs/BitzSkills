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

**要件化・実装（2026-07-30）**: 提案1・3 を `SDD-FR-164` として起票し、`SDD-TSK-053` で
実装・検証した。提案2（mutation lock 参加）は**追加裁定により V4 へ送った**（下記）。

- **提案1**（mtime 精度の統一）— **実装済**（`SDD-FR-164`）。比較側を `st_mtime_ns` へ揃えた。
  選択肢にあった**内容ハッシュ比較への移行は採らない** — 公開契約 `SDD-FR-100` の破壊的変更に
  なり、V4 Design Gate 必須の論点を順序8 へ持ち込むことになる。必要性が生じたら V4
  ターゲット設計で再検討する。
- **提案2**（mutation lock 参加）— **V4 へ送る（2026-07-30 追加裁定）**。lock 機構の実体は
  sdd-core の `spec_transaction.py` にあり、スキル自己完結原則（`CORE-CON-004`）により
  sdd-docs から相対パスで参照できない。`spec_labels.py` と同型の「SSOT＋複製＋release_check
  照合」で解決する案と、最小 advisory lock の自作案を提示したうえで、裁定者は
  **mtime 修正だけ先行し lock は V4 へ**を選択した。共有 Python コードの配置は
  V4 の未裁定論点1（配布単位）で決める。
  本 spec-issue 提案2 の後半「参加させない場合は設計判断として明記し、適用範囲と
  残余リスクを限定する」に従い、`SDD-FR-164` の受入基準と `sdd-docs/SKILL.md` へ明記した。
- **提案3**（同一秒内・並行実行の unit-test）— **同一秒内は実装済**（`SDD-FR-164`。float 秒では
  消える ns 差で pull / push / diff を固定する回帰テスト4件）。**並行実行のテストは提案2 と
  同時に V4 へ送る**（lock が無い状態では固定すべき挙動が定義できないため）。
- 残余リスク: lock 不参加のため、`sdd_sync` / `migrate_docs` を `spec_update` /
  `spec_scaffold` 等の変更 CLI と**同時に実行すると lost update が起こりうる**。
  単独実行なら影響しない。V4 で lock 参加を実装するまで運用制約として残る。
