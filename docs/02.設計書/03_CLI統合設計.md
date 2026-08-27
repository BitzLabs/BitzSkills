# CLI統合設計

## 1. 方針

AI CLI統合は薄く保つ。`bitz-core`がEARS-AIの解釈と判定を所有し、各CLI向けスキルは
コマンド呼出し、対象範囲の選択、結果説明だけを担当する。

Core 1.0は主要CLIを1つだけ参照実装し、2つ目はコア契約の移植性を確認する最小試験に限定する。

## 2. 配布

| 層 | 内容 | 初期配布 |
|---|---|---|
| コア | `bitz`、EARS-AI Parser、context、check、verify、doctor | PyPI + `uv tool install bitz` |
| CLIプラグイン | スキル、コマンド定義、説明文 | 各CLIのマーケットプレイス |

単一バイナリはCore 1.0の必須成果物にしない。Pythonや`uv`を導入できない利用者の実需要が
確認された場合に追加する。

## 3. 公開操作

```text
bitz context <spec-or-statement-id>... [--purpose interpret|implement|verify]
  [--format markdown|json] [--detail compact|standard|full]
  [--expand <document-id>]... [--expect-digest sha256:<hex>]
bitz check [ids-or-paths...] [--full] [--format text|json] [--report]
bitz verify [spec-or-statement-id|paths...] [--report]
bitz doctor [--format text|json]
```

`doctor`の検査順序、初回導入支援、Git不在時の縮退、Diagnosticは
[doctor仕様](../03.詳細設計/02_SPECファイル規定/11_doctor仕様.md)を正とする。

初期化はテンプレートのコピーまたはスキルで行い、専用CLIサブシステムを必須にしない。
SDD、DDD、同期はCore 1.0の公開コマンドへ含めない。

## 4. アダプター責務

- プロジェクトルートと`.spec/`の検出
- 実装前のContext Bundle取得と、編集直前のContext Digest再照合
- Constraint Ledgerの全`MUST`確認と、必要な`reference`文書だけの明示展開
- コアコマンドの呼出し
- 読取り、書込み、コマンド実行の承認仲介
- stdout、stderr、終了コードの提示
- CLI固有形式への短い説明

アダプターはEARS-AI、依存関係、Context選択を独自解析せず、合否や重大度を変更しない。

## 5. 能力不足時

| 能力 | 不足時の動作 |
|---|---|
| ファイル読取り | `blocked` |
| コマンド実行 | `context`と`check`だけ利用し、`verify`は`blocked` |
| ファイル書込み | 読取り専用で継続 |
| 対話承認 | 副作用を実行せず、実行候補を表示 |
| subagents | 同一エージェントで継続。独立監査を装わない |
| hooks | 使用しない |

別Agentや別コンテキストによるレビューは任意である。同一モデルを分離しただけのレビューを、
組織的に独立した監査として扱わない。

## 6. フック

Core 1.0はフックなしで完結する。フックは性能、互換性、攻撃面を増やすため既定で無効とし、
明示コマンドで解決できない実例が複数確認されるまで導入しない。

## 7. コア不在・版不整合

- コア不在時は`blocked`と導入手順を返す。
- プラグインがコアを自動ダウンロードまたは更新しない。
- EARS-AI Coreのメジャー版が不一致の場合だけ停止する。
- マイナー版差は未知構文を使っていない限り警告として扱う。

## 8. 互換性試験

- クリーン環境での`uv tool install`
- 同一EARS-AI fixtureから同一Semantic IRとDiagnosticを得る
- 同一依存グラフから同じContext BundleとDigestを得る
- detailを変更しても解決集合とContext Digestは不変で、Projection Digestだけが変わる
- 参照漏れ、循環、上限超過で部分bundleを成功扱いしない
- コア不在時の`blocked`
- `check`がネットワーク、LLM、フックなしで動く
- CLIアダプターが判定を変更しない
