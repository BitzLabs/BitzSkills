---
implements: FLW-NFR-004, FLW-CON-001
depends_on: [FLW-TSK-005]
boundary: plugins/bitz-flow/skills/flow-core/scripts/flowlib/process.py
status: done
---

### M0 process runner の実装（3プラットフォーム可搬な外部プロセス実行）

- **作業内容**: FLW-DSN-013 の process runner 節に従い、Python 3.10+ 標準ライブラリのみで
  `flowlib/process.py` を実装する。
  command は argument array・`shell=False` で実行し、任意 shell 文字列を構築しない。
  operation timeout（read は 1〜300 秒、既定 30 秒）とは別に action 全体 deadline を持つ。
  stdout / stderr は operation 別 byte 上限まで memory へ読み、超過時は process を終了して
  `UNAVAILABLE` を返す。timeout 時は process group へ terminate → 短い猶予 → kill → 必ず wait する。
  POSIX は新規 session + process group signal、Windows は `ctypes` の Job Object で
  process tree を所有・終了する。安全な tree 収束を提供できない platform では、
  M0 は read-only のため read を継続し、将来の write が `UNSUPPORTED` へ縮退できるよう
  capability 判定結果を戻り値に含める。
  exception・traceback・raw stdout / stderr を result へ連結しない。cause は
  FLW-TSK-005 が定めた許可語彙・command 名・stage・exit category だけを返す。
- **完了条件**: Linux / macOS / Windows のパス表現と process 終了処理が分岐込みで実装され、
  timeout・byte 上限超過・存在しない command・非ゼロ終了の各経路が cause 語彙へ正規化されること。
  秘密値・environment・raw 出力が戻り値に含まれないこと。
- **備考**: 本 module は Git / GitHub の知識を持たない汎用 runner とする（依存方向は
  adapters → process runner の一方向。FLW-DSN-004）。Go 実装・部分置換・移行比較は行わない。
  Python で安全な process tree 収束を成立させられない場合は実装を中断し、
  `.spec/spec-issues/` へ起票して人間の裁定を待つ（scope 縮小・再設計・No-Go の裁定対象）。
