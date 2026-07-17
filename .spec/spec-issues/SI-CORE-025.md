---
id: SI-CORE-025
raised_by: ユーザーからの照会（2026-07-18 セッション）— accepted のまま7件（SI-CORE-007/008/009/010/013/014/018）が未実装で放置されていたが、spec_status.py はこれを検知せず「クリーン」と誤報告していた
target: plugins/bitz-sdd/skills/sdd-core/scripts/spec_status.py（next_actions 関数、L88-111）
proposed_change_type: bump
status: accepted
---
- **目的**: `spec_status.py` の次アクション候補（`next_actions`）が、`status: accepted` の
  spec-issue のうち requirement への分解が未着手（= 積み残し）のものを検知できず、
  「未処理の作業なし（クリーン）」と誤報告する盲点を塞ぐ。2026-07-18 のセッションで、
  ルート workspace が `spec status .` で「フェーズ: Done（検証完了）」「クリーン」と
  報告していたにもかかわらず、実際には `status: accepted` のまま7件
  （SI-CORE-007 / 008 / 009 / 010 / 013 / 014 / 018）が要件化も実装もされずに放置されていた
  ことが手動照合（対象ファイルの実在確認・git ログ突合）で判明した。`next_actions`（L88-111）は
  `issues.get("open", 0)`（裁定待ち件数）のみを見ており、`accepted` 件数と、その accepted が
  実際に requirement へ繋がっているか（`requirements/*.md` の `origin:` フィールドでの
  参照有無）を突き合わせていないため、この種の積み残しは機械的に不可視だった。
- **提案する修正**（**テスト先行**）:
  1. `spec_status.py` に、`status: accepted` の spec-issue の ID を集め、各ワークスペースの
     `requirements/*.md` の `origin:` フィールドに当該 ID への言及があるかを突合する処理を追加する
     （読み取り専用のまま。書き込み・自動修正は行わない）。
  2. 言及が一件も見つからない accepted spec-issue を「未着手の accepted」として件数集計し、
     `next_actions` に
     `f"accepted のまま未着手の spec-issue が {n} 件 — 要件化 or 軽量レーンでの実施を検討する"`
     のような候補を追加する（`n_open` の直後、要件系の候補より前に提示し優先度を示す）。
  3. `origin:` に個別 ID を書かず複数 ID をまとめて言及する等の表記ゆれを吸収できるよう、
     正規表現でのゆるい部分一致にする（誤検知よりも見逃し防止を優先。過検知が問題になれば
     別途 issue で厳密化する）。
  4. JSON 出力にも同フィールド（例: `"accepted_unaddressed": [...]`）を追加し、エージェント側が
     一覧を機械的に取得できるようにする。
  5. `--json` 未指定時のテキスト出力にも該当 ID 一覧を明示する（人間が一目で気付けるように）。
- **対象ファイル**: `tests/test_spec_status.py`（先行）、
  `plugins/bitz-sdd/skills/sdd-core/scripts/spec_status.py`、
  `plugins/bitz-sdd/skills/sdd-core/references/`（next_actions の仕様記述があれば追記）、
  bitz-sdd マニフェスト（bump）。
- **確認観点**:
  - テストが先にコミットされ、fixture の `.spec` ツリー（accepted だが `origin:` 未参照の
    spec-issue を含む構成）に対して新規集計が正しく検出されること
  - 既存の集計・フェーズ判定・JSON 構造に対する既存テストが引き続き green であること
    （後方互換 — 出力フィールドの追加のみで既存フィールドは変更しない）
  - `.venv/bin/pytest` 全件 green、`.spec/` への書き込みが発生しないこと（読み取り専用の保証）
  - 本リポジトリのルート workspace で実行し、SI-CORE-007/008/009/010/013/014/018 が
    「未着手の accepted」として検出されること（回帰の実地確認）
- **影響推定・ロールバック**: `spec_inspect --impact CORE-FR-003` で確認済み、依存成果物は
  `.spec/tasks/CORE-TSK-004.md` と `tests/test_spec_status.py` の2件のみ。出力フィールド追加の
  範囲に留め既存フィールドを変更しないため、`next_actions` の追加ロジックのみ revert すれば
  旧挙動に戻る。CORE-FR-003 の受入基準を破壊しない拡張（既存 EARS 節は書き換えない）。
  版は minor bump（新機能追加、既存出力の破壊的変更なし）。
- **依存**: CORE-FR-003（spec_status.py 本体）。SI-CORE-007/008/009/010/013/014/018 は本
  ISSUE の直接の依存ではなく、検知漏れの実例（再現ケース）として引用するのみ — それら自体の
  実装スケジューリングは本 ISSUE の範囲外（人間裁定 or 別途 sdd-implement で扱う）。

## 予備判定（推薦） — 裁定は人間専用

| 判定軸 | 確認結果 |
|---|---|
| 既存要件との矛盾 | なし。CORE-FR-003 の既存 EARS 節（件数集計・JSON/テキスト出力・読み取り専用・複数workspace対応）とは矛盾せず、出力フィールドの追加のみで両立する |
| ガードレール抵触 | なし。AGENTS.md の禁止事項・事前確認事項（破壊的操作・リポジトリ外書き込み等）に触れない |
| 影響範囲 | 限定的。`spec_inspect --impact CORE-FR-003` で依存成果物2件のみ確認済み（上記） |
| 軽量レーン適否 | 不可・通常フロー推奨。`spec_status.py` の出力契約（JSON構造）に触れるため、CORE-FR-003 の
  requirement 改訂（revision bump）を経る通常フローが妥当 |

**推薦: accept**（根拠: 既存要件と非矛盾・ガードレール抵触なし・影響範囲限定・実害の実例あり）。
最終裁定はユーザー自身の明示指示による `spec_update.py --to accepted --by-human` で行うこと。
