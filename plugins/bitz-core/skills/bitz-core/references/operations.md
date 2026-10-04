# 操作の参照

## 公開面と呼出し

この参照はCore 1.0の公開CLIを利用する手順である。構文・対象解決・診断の規範はCoreの操作仕様を正とする。
`bitz`を導入済みの環境で、対象ワークスペースから起動する。
開発リポジトリでは、導入済みの依存を使う環境を用意して
`uv run --project <Coreのprojectディレクトリ> bitz ...`として起動できる。
依存取得や環境作成は導入作業であり、操作の依頼から暗黙に追加しない。

以下は操作を選ぶための例であり、4操作を順番に実行する指示ではない。
`REQ-001`、`api`は確認済みの実際のIDへ置き換える。

| 目的 | 例 |
|---|---|
| 前提の診断 | `bitz doctor --format json` |
| 実装用コンテキスト | `bitz context REQ-001 --purpose implement --format json` |
| 解釈用コンテキスト | `bitz context REQ-001 --purpose interpret --format json` |
| 検証用コンテキスト | `bitz context REQ-001 --purpose verify --format json` |
| 選択した仕様の検査 | `bitz check REQ-001 --format json` |
| 現在の変更集合の検査 | `bitz check --format json` |
| ワークスペース内の全仕様検査 | `bitz check --full --format json` |
| 選択した要求のテスト検証 | `bitz verify REQ-001 --format json` |

## 対象と範囲

- `context`は文書IDまたは規範文IDを1件以上指定する。パスを起点にしない。
  `--purpose`は取得目的に合わせる。表示量を減らしても完全解決を省略したとは解釈しない。
  追加本文が必要なら結果の集合内の文書を`--expand`で指定する。
- `check`は仕様文書のID、規範文ID、仕様文書のパスを指定できる。
  引数なしは変更集合、`--full`は全件である。コード・テストのパスを対象にしない。
  比較基準を明示する依頼では`--base <git-revision>`を使う。
- `verify`はREQ、TECH、TASKのID・パス、対応する規範文IDを指定する。
  ADR、コード・テストのパスを対象にしない。引数なしは当該ワークスペースの全検証である。
  範囲が未確定の依頼を引数なしの実行へ拡大しない。
- `doctor`は前提を診断し、修復や登録テストの実行を行わない。
  APIや対応機能を検査する場合は公開CLIの互換性要求を使う。
  Coreスキルが必要とする操作の対応機能は`doctor.v1`、`context.v1`、`check.v1`、`verify.v1`である。
  複合ワークスペースでは`multiWorkspace.v1`も確認する。

## 単一／複合ワークスペース

単一では現在のワークスペースを使う。複合では公開設定のカタログと所有者を確認し、
`--workspace api`または修飾ID`api::REQ-001`で対象を明確にする。
ルートの`.spec/bitz.yaml`にある`multiWorkspace.members`で`id`と`path`の対応を読む。
`api`というIDが`api/`というディレクトリを指すとは推測しない。確認したメンバーの設定を読む。
カタログ・設定・登録の前提診断は`doctor`、仕様文書のID・関係・状態の検査は`check`を選ぶ。
単独の操作へ異なる所有ワークスペースの起点・検査・検証対象を混ぜない。

全体が依頼範囲なら、`doctor`、`check`、`verify`の`--all-workspaces`を使う。
`check --all-workspaces`は全件検査を含意するため、`--full`を併用しない。
`context`には全体操作がない。所有ワークスペースの起点から返された越境関係を確認する。
全体操作と単独操作の範囲指定を混ぜず、Gitの境界やカタログが不明なら前提を診断する。
一部の成功を全体の成功へ読み替えない。

## 保存と再実行

通常は`--format json`だけを指定する。`check`と`verify`の結果保存を利用者が依頼した場合だけ
`--report`を加える。任意の保存パスや、`context`・`doctor`への`--report`を作らない。
明示レポートは対象ワークスペース、全体操作ならルートワークスペースの`.spec/reports/`へCoreが保存する。

不成功を隠すために対象や範囲を縮めて再実行しない。修正後の再実行は元の範囲を確認し、
前後の実行を区別する。`verify`の再実行前にも安全を確認する。
取得済みコンテキストの同一性が必要なら、Coreが返した`contextDigest`を
`context --expect-digest`へ渡す。スキルで独自のダイジェストを再計算しない。
