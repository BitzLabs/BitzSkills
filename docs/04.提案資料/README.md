# 提案資料

## 1. 位置づけ

本directoryは、確定した設計（[02.設計書](../02.設計書/README.md)、
[03.詳細設計](../03.詳細設計/)）に対するreview原文と、その裁定状況を保持する。

- 設計書本文は「現在の決定内容」を述べる
- [決定記録](../02.設計書/10_決定記録/README.md)は「なぜその決定に至ったか」を保持する
- 各review文書は「決定を変えるべきかもしれない材料」を、[用語集](../用語集.md)による文言統一を除き原文のまま保持する
- 本READMEは「何を採用し、何を残したか」の最新状態を保持する

提案が裁定されたら、設計書本文と決定記録へ反映する。review文書内の行番号や
改訂例はreview時点のsnapshotであり、裁定後の仕様の正にはしない。

## 2. 一覧

| 文書 | 対象 | 状態 |
|---|---|---|
| [01_詳細設計reviewと改訂提案.md](01_詳細設計reviewと改訂提案.md) | 03.詳細設計 全19文書 | **Closed**（32件裁定済み、評価のみ1件） |
| [02_Antigravity_詳細設計reviewと改訂提案.md](02_Antigravity_詳細設計reviewと改訂提案.md) | 02.設計書、03.詳細設計 | **Closed**（4件裁定済み） |
| [03_設計書・詳細設計reviewと改訂提案.md](03_設計書・詳細設計reviewと改訂提案.md) | 02.設計書、03.詳細設計 | **Closed**（17件裁定済み） |
| [04_Core-1.0_P1残存契約reviewと改訂提案.md](04_Core-1.0_P1残存契約reviewと改訂提案.md) | 02.設計書、03.詳細設計 | **Closed**（P1 3件裁定・反映済み） |
| [05_Core-1.0_P2残存運用契約reviewと改訂提案.md](05_Core-1.0_P2残存運用契約reviewと改訂提案.md) | 02.設計書、03.詳細設計 | **Closed**（P2 7件裁定・反映済み） |
| [06_Core-1.0_P3記述整合reviewと改訂提案.md](06_Core-1.0_P3記述整合reviewと改訂提案.md) | 02.設計書、03.詳細設計 | **Closed**（P3 6件裁定・反映済み） |
| [07_ユースケース・flow遷移reviewと修正提案.md](07_ユースケース・flow遷移reviewと修正提案.md) | 02.設計書、03.詳細設計 | **Closed**（8件裁定・反映済み） |
| [08_flow終端・遷移条件reviewと修正提案.md](08_flow終端・遷移条件reviewと修正提案.md) | 02.設計書、03.詳細設計 | **Closed**（8件裁定・反映済み） |
| [09_Core-1.0_実装前異常case-reviewと修正提案.md](09_Core-1.0_実装前異常case-reviewと修正提案.md) | 02.設計書、03.詳細設計 | **Closed**（4件裁定・反映済み） |
| [10_並行開発におけるID重複対策の検討と提案.md](10_並行開発におけるID重複対策の検討と提案.md) | 02.設計書、03.詳細設計 | **Closed**（採決事項9件・裁定事項16件を裁定・反映済み） |
| [11_仕様構造の再編とCore-1.0簡素化提案.md](11_仕様構造の再編とCore-1.0簡素化提案.md) | 02.設計書、03.詳細設計 | **Closed**（11件採用・ADR-039と正本へ反映済み） |
| [12_Core-1.0実装計画.md](12_Core-1.0実装計画.md) | Core 1.0実装順序 | **Active**（非規範の実装計画） |
| [13_複合workspaceモデル・不変条件review.md](13_複合workspaceモデル・不変条件review.md) | 複合workspaceモデル・不変条件 | **Closed**（P1裁定時にP2も解消） |
| [14_ID・横断関係・Context-review.md](14_ID・横断関係・Context-review.md) | ID・横断関係・Context | **Closed**（P1・P2裁定済み） |
| [15_CLI・対象選択・結果集約review.md](15_CLI・対象選択・結果集約review.md) | CLI・対象選択・結果集約 | **Closed**（P1・P2裁定済み） |
| [16_verify実行モデルreview.md](16_verify実行モデルreview.md) | verify実行モデル | **Closed**（ADR-041で5件裁定・反映済み） |
| [17_セキュリティ・信頼境界review.md](17_セキュリティ・信頼境界review.md) | セキュリティ・信頼境界 | **Closed**（P1・P2裁定済み） |
| [18_互換性・移行・運用review.md](18_互換性・移行・運用review.md) | 互換性・移行・運用 | **Closed**（P1・P2裁定済み） |
| [19_実装可能性・性能・文書構造review.md](19_実装可能性・性能・文書構造review.md) | 実装可能性・性能・文書構造 | **Closed**（P1・P2裁定済み） |
| [20_複合workspace-Core-1.0横断review.md](20_複合workspace-Core-1.0横断review.md) | review 13〜19の横断整理 | **Closed**（P0・P1・P2裁定済み） |
| [21_P0_verify証跡Schema検討.md](21_P0_verify証跡Schema検討.md) | FED-CROSS-001のSchema案 | **Accepted**（ADR-041と正本へ反映済み） |
| [22_複合workspace残存P1裁定案.md](22_複合workspace残存P1裁定案.md) | FED-CROSS-002〜007の裁定案 | **Accepted**（ADR-042と正本へ反映済み） |
| [23_複合workspace残存P2裁定案.md](23_複合workspace残存P2裁定案.md) | 複合workspace残存P2 6件の裁定案 | **Accepted**（ADR-043と正本へ反映済み） |
| [24_Core-1.0実装着手方針.md](24_Core-1.0実装着手方針.md) | 実装着手可能性と欠落 | **Accepted**（G1〜G8裁定・反映済み、G9は実装計画へ） |
| [25_Core-1.0実装前最終reviewと修正提案.md](25_Core-1.0実装前最終reviewと修正提案.md) | 02.設計書、03.詳細設計の実装前最終点検 | **Accepted / Reflected**（Step 0B完了、Gate A `Allowed`） |
| [26_context-Markdown提示仕様案.md](26_context-Markdown提示仕様案.md) | contextの既定Markdown提示 | **Accepted / Reflected**（P0 3件・P1 4件を裁定し§9と`SINGLE-104-01`へ反映済み） |
| [27_適合harness外部仕様の検討.md](27_適合harness外部仕様の検討.md) | 適合harnessの検査対象・実行環境・runner | **Accepted / Reflected**（4件を裁定しADR-046と正本へ反映済み） |

## 3. 検討結果の要約

review 01とAntigravity reviewは2026-08-27時点で全提案を裁定した。
以下の§3〜§7はreview 01・02を閉じた時点の記述である。review 03と後続reviewは§8以降を正とする。
review 01〜11は全提案を裁定・反映済みである。review 11では仕様の責務境界とCore 1.0 scopeを再評価し、
11件をADR-039と再編後の正本へ反映した。Core 1.0へ入れない案は再評価条件を明記した。

| 文書 | 反映済み・修正反映済み | Core 1.0未採用 | 1.1以降の候補 | 評価のみ |
|---|---:|---:|---:|---:|
| review 01 | 27 | 3 | 2 | 1 |
| Antigravity review | 1 | 2 | 1 | 0 |

1.1以降の候補も原則としてCore 1.0に対しては不採用であり、自動的な実装予定ではない。各review文書に記載した
実測条件を満たした場合に限り、新しい提案またはADRとして再起票する。複合workspaceだけは後発のADR-040で
Core 1.0へ再導入した。

| 区分 | 判断 | 進捗 |
|---|---|---|
| 識別子・構文 | 3桁以上のID、許可接頭辞、括弧・escapeの字句優先順位を採用 | 完了 |
| 置換済み要件 | `supersedes` の逆参照を含め、置換済みREQ・TECHの適用を遮断 | 完了 |
| Diagnostic | codeの所有者と命名規則をADRで固定し、style診断を追加 | 完了 |
| 検証契約 | 引数なしverify、全体Frontmatter索引、対象限定AST、`cwd`、coverage強度を明記 | 完了 |
| doctor・Git | doctorの出力契約、Git情報取得のフォールバック、reportsのGit除外を明記 | 完了 |
| 導入計画 | Phase 0の試験対象を5件へ縮小し、小規模開発向けの軽量性を優先 | 完了 |
| EARS-AI表現 | 詳細な構文木ではなく、要求の意味軸を保持する軽量Semantic IRとしてASTを定義 | 完了 |
| Context提示 | 完全解決と提示量を分離し、Constraint Ledgerと3段階Projectionを採用 | 完了 |
| 複合workspace | 提案11の延期をADR-040で部分改訂し、現行の簡素化を維持して再導入 | Core 1.0対象 |
| 配布 | Agent Plugins 1.0準拠の`bitz-core`と独立拡張、GitHubマーケットプレイス、doctor事前検査を採用 | 完了 |

主な反映先は次のとおり。

- [ADR-011](../02.設計書/10_決定記録/ADR-011_Diagnostic所有者とcode命名規約.md)
- [ADR-012](../02.設計書/10_決定記録/ADR-012_置換済みREQ・TECHの適用禁止.md)
- [ADR-013](../02.設計書/10_決定記録/ADR-013_文書IDとローカルIDの字句規則訂正.md)
- [ADR-014](../02.設計書/10_決定記録/ADR-014_Semantic-IRと段階的Context-Projection.md)
- [ADR-039](../02.設計書/10_決定記録/ADR-039_Core-1.0仕様構造の再編とscope縮小.md)
- [ADR-040](../02.設計書/10_決定記録/ADR-040_複合workspaceをCore-1.0へ再導入する.md)
- [ADR-041](../02.設計書/10_決定記録/ADR-041_verify対象別証跡とreport明示保存の分離.md)
- [ADR-042](../02.設計書/10_決定記録/ADR-042_複合workspaceの同一性・所有境界・公開契約を確定する.md)
- [EARS-AI言語・Semantic IR仕様](../03.詳細設計/01_EARS-AI/01_言語・Semantic-IR仕様.md)
- [関係・トレースモデル](../03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md)
- [context仕様](../03.詳細設計/03_操作仕様/01_context.md)
- [check仕様](../03.詳細設計/03_操作仕様/02_check.md)
- [verify仕様](../03.詳細設計/03_操作仕様/03_verify.md)
- [doctor仕様](../03.詳細設計/03_操作仕様/04_doctor.md)

## 4. Core 1.0で採用しない事項

| 事項 | 1.0での判断 | 再評価条件 |
|---|---|---|
| 汎用test selector/nodeid | file単位を維持 | 複数runnerで偽陽性が日常的に発生し、共通契約を定義できる |
| purpose別の`refines`省略 | 完全閉包を維持 | 上限超過が実タスクで反復し、意味を欠落させないstatement起点規則を証明できる |
| `bitz check --strict` | 共通終了コードと可視化を維持 | warning種別ごとのCI昇格需要が確認される |
| `bitz fmt` | 公開操作へ追加しない | EARS-AI表記揺れが主要な運用負荷になる |
| 後置Profile拡張 | 前置拡張だけを確定 | 実Profileで前置表現が不十分になる |
| `implements.addresses` | TASK `addresses`とtest `covers`を維持 | 実装漏れが現行の句単位TASK・coverageで防げない |
| TASK境界のwarning化・自動承認 | `blocked`を維持 | fail-openにせず開始時差分を再現できる契約が成立する |
| 削除済みIDのGit履歴tombstone索引 | 管理済みSPECの削除禁止と現在集合の重複検出に限定 | Core検査を迂回したID再利用事故が確認され、shallow clone時も決定論的な検出範囲を定義できる |
| 未所有code/test pathのwarning化 | 対象外（件数のみ）を維持 | SPEC整備率が高い運用で、未所有pathの見落としが実害として確認される |
| ADR改訂関係の型付き語彙・`x-amends` | 3点記録の規約を維持 | 改訂関係の機械追跡が実測で必要になる（ADR-020 Decision 4、ADR-033） |
| file数によるcache bypass | 固定閾値を設けない | benchmarkでcache I/Oが支配的と判明する |

## 5. クローズ判定

- 次期版の構想、共通設計、EARS-AI規格、SPEC file規定は設計済み
- 旧版の試行錯誤から有効な依存解決・境界検証を選別し、軽量な中核へ反映済み
- 全提案に採否、理由、反映先または再評価条件を記録済み
- 実装前に解消すべき契約矛盾は正本へ反映済み
- 実装code、性能benchmark、1.1以降の拡張機能は未着手

したがってreview 01・02の設計reviewゲートは**完了**とする。次の工程はCore 1.0の最小垂直スライス実装である。
将来候補は本directoryから直接実装せず、新しい実測結果と裁定を伴う提案またはADRから開始する。

## 6. クローズ後review

2026-08-27に、提案項目の網羅性、裁定と正本の対応、未決表現、将来候補の再評価条件をreviewした。

review中に、補助SPECの関係図へADRの`requires`がない不整合と、旧版調査refが短縮SHAのままの
記述を検出した。前者は現契約を関係図へ反映し、後者は到達可能性を確認して完全SHAへ修正した。

- review 01の32提案と評価1件、Antigravity reviewの4提案に裁定がある
- 各fileの状態は`Closed`で一致し、未検査項目はない
- 採用項目は設計書、詳細設計、ADRのいずれかを正本とし、提案原文を規範化していない
- 未採用項目は理由を持ち、将来候補は再評価条件を持つ
- Core 1.0の実装を止める未裁定事項はない

修正後のreview結果は**残存指摘なし（クローズ可）**とする。

## 7. 外部CLI review

2026-08-27にagyへ設計書全体の独立reviewを依頼した。総合判定は
「合格（一部軽微な不整合あり）」で、3件の指摘を正本と照合して次のように裁定した。

| 指摘 | 裁定 | 対応 |
|---|---|---|
| `SPEC-STYLE-HISTORY-001`がDiagnostic一覧にない | 採用・反映済み | 参照・トレース・検証仕様の正本一覧へ追加 |
| Git不在時のDiagnostic severityと操作statusが異なる | 未採用 | severityとstatusは別軸であり、`error`診断を伴う`blocked`結果は矛盾しない |
| Context性能目標の128 KiB条件が一部で省略 | 採用・反映済み | 実装ロードマップとContext Resolution仕様を共通アーキテクチャに統一 |

Claude Codeは通常サンドボックス内でAnthropic APIのDNS timeoutとなったが、外部通信を許可した
読取り専用実行で設計書全体のreviewを完了した。5件の指摘を正本と照合し、すべて採用・反映した。

| 指摘 | 裁定 | 対応 |
|---|---|---|
| doctorで`bitz.yaml`不在とSchema不正が同じ`blocked` | 修正採用・反映済み | 不在と未対応majorは`blocked`、構文・型・必須項目不正は`error`へ分離 |
| REQ必須H2の列挙に`Verification`がない | 採用・反映済み | 要求SPEC仕様の必須節へ追加 |
| Context Bundle例の文書直下に未定義`expandable`がある | 採用・反映済み | 重複fieldを削除し、`revisionHistory.expandable`へ一本化 |
| 運用設計のContext性能目標に128 KiB条件がない | 採用・反映済み | 共通アーキテクチャ、ロードマップ、詳細仕様と統一 |
| Constraint Ledgerの`role`がSemantic IRで未定義 | 採用・反映済み | `documentRole`へ改称し、所有文書から導出するContext metadataとして定義 |

## 8. review 03（2026-08-31、裁定済み）

裁定済み提案の反映後の正本を対象に、独立reviewを実施した。既裁定の論点は再提起せず、
反映によって生じた接続部の不整合と未指摘の欠落だけを扱う。

| 区分 | 件数 | 主な内容 |
|---|---:|---|
| P1 | 5 | 上位文書が前提とする設定key・field・モードが正本Schemaに存在しない |
| P2 | 7 | 引数なし`verify`の対象漏れ、複合workspace段階導入時の集約status、`doctor`判定、自己適合性 |
| P3 | 5 | CLI文法、表区分、severity記載の整合 |

P1の5件（`profiles`設定key、`verify`の`cwd`、Frontmatter `owners`、`EAI-*`のseverity、
Profile `dependencies`）は、いずれも「どちらが正か」ではなく「片方に定義がない」型の欠落であり、
実装者が仕様から動作を決定できない。

2026-08-31にP1の5件を裁定し、[ADR-018](../02.設計書/10_決定記録/ADR-018_正本Schemaの欠落補完とDiagnostic-severityの明示.md)として記録して正本へ反映した。
適用差分は[03_設計書・詳細設計reviewと改訂提案.md](03_設計書・詳細設計reviewと改訂提案.md) 附録A、
裁定内容は同書 §5の表を正とする。

| 項目 | 裁定 | 対応 |
|---|---|---|
| `profiles`設定keyが`bitz.yaml`にない | 採用 | 予約keyとして追加。Core 1.0では型のみ検査し判定に不使用 |
| `verify`が`cwd`を無視 | 採用 | 解決した`cwd`で実行。未指定時のみworkspace root |
| Frontmatter `owners`が未定義 | 修正採用 | 共通項目へ追加せず、規格本文を`x-owners`へ統一 |
| `EAI-*`にseverityがない | 採用 | severity列と`draft`降格規則を追加。ID系は`draft`でもerror |
| Profile `dependencies`がADR-016と矛盾 | 採用 | Manifestから削除し、Profile間依存を無条件禁止 |

2026-08-31にP2の7件を裁定した。3.1〜3.6は
[ADR-019](../02.設計書/10_決定記録/ADR-019_検証対象と縮退判定の明確化.md)、3.7は
[ADR-020](../02.設計書/10_決定記録/ADR-020_決定記録をSPEC本文構造規定へ適合させる.md)として記録し、正本へ反映した。

| 項目 | 裁定 | 対応 |
|---|---|---|
| 存在しない「厳格モード」の記述 | 採用 | 未知拡張をwarning固定とし記述を削除 |
| 規範文なしTECHが引数なしverifyの対象外 | 採用 | `tests`宣言のあるものを対象へ追加。句単位coverage判定は対象外 |
| 0件memberが`verify --all-workspaces`全体を`blocked`にする | 採用 | member単位はwarning、複合workspace全体0件だけerror |
| `doctor`検査1の`error`とADR-016の`blocked`の食い違い | 採用 | 版不適合と起動失敗を分離し`SPEC-DOCTOR-CORE-002`を追加 |
| `bitz verify`に`--format`がない | 採用 | 公開文法へ追加し`--all-workspaces`形を分離 |
| 横断testの重複排除scopeが未定義 | 採用 | 実行済み集合を複合workspace全体で1つに統一 |
| 決定記録が自らの本文構造規定に非適合 | 修正採用 | 本文構造規定だけを適用（配置・命名規則は対象外）。ADR 20件を適合 |

2026-08-31にP3の5件を裁定した。いずれも既存の決定を変更せず、決まっている内容を読み取れる形に
するだけであるため、新規ADRは起こさない。

| 項目 | 裁定 | 対応 |
|---|---|---|
| `check --all-workspaces`の排他・含意が文法に現れない | 採用 | `verify`と同じ2行形式へ分離 |
| 「採用しない機能」表に必須化済みの`Revision History`が残る | 採用 | 「簡素化して採用する知見」へ移動 |
| hooksがCore 1.0非搭載と供給網要件で二重 | 採用 | 対象をクライアント固有hooksへ限定し非同梱を併記 |
| `check`読取り専用の表現が3文書で異なる | 採用 | 最も正確な表現へ統一 |
| `CTX-COVERAGE-*`にseverityがない | 採用 | `implement`でwarning、`verify`で`blocked`を表へ明記 |

review 03の全17件が裁定済みとなり、Core 1.0の設計reviewゲートは再び**完了**とする。
未着手として残るのは実装code、性能benchmark、1.1以降の拡張機能である。
本reviewで追加した決定記録はADR-018、ADR-019、ADR-020の3件である。

## 9. P1残存契約review（2026-08-31、裁定済み）

review 03の反映後に、Diagnostic共通契約、規範行候補Scanner、`bitz verify`の明示対象へ
実装分岐が残っていることを確認した。3件を
[04_Core-1.0_P1残存契約reviewと改訂提案.md](04_Core-1.0_P1残存契約reviewと改訂提案.md)へ記録し、
[ADR-021](../02.設計書/10_決定記録/ADR-021_Diagnostic-severity・操作status・source-Schemaの分離.md)、
[ADR-022](../02.設計書/10_決定記録/ADR-022_規範行候補抽出とID構文検証の分離.md)、
[ADR-023](../02.設計書/10_決定記録/ADR-023_verify明示対象とpath入力の確定.md)として裁定した。

| 項目 | 裁定 | 対応 |
|---|---|---|
| Diagnosticのseverity・status・source | 採用・反映済み | severityと操作statusを分離し、`source.kind`を`file`、`environment`、`invocation`で定義 |
| 不正規範行の検出 | 採用・反映済み | 候補抽出とID構文検証を分離し、`SPEC-REQ-STATEMENT-001`を追加 |
| `verify`明示対象 | 採用・反映済み | REQ、TECH、規範文、TASK、SPEC file pathへ限定し、code・test pathとADRを拒否 |

P1 3件の正本反映を完了したため、Core 1.0の設計reviewゲートを再び**完了**とする。

## 10. P2残存運用契約review（2026-08-31、裁定済み）

P1反映後の正本について、状態遷移、Git差分、`check`入力、verify実行、TASK接続、Diagnostic集約、
report生成の実装分岐を確認した。review 03の旧P2 7件とは別の指摘として、
[05_Core-1.0_P2残存運用契約reviewと改訂提案.md](05_Core-1.0_P2残存運用契約reviewと改訂提案.md)へ記録した。

| 項目 | 裁定 | 対応 |
|---|---|---|
| SPEC状態遷移 | 採用・反映済み | [ADR-024](../02.設計書/10_決定記録/ADR-024_SPEC文書の状態遷移契約.md) |
| Git基準版と`check`明示対象 | 採用・反映済み | [ADR-025](../02.設計書/10_決定記録/ADR-025_Git基準版とcheck明示対象の確定.md) |
| verify timeout・command結果・Digest | 採用・反映済み | [ADR-026](../02.設計書/10_決定記録/ADR-026_verify実行binding・timeout・結果Schemaの確定.md) |
| TASKと規範文なしTECH、`adjacent` | 修正採用・反映済み | 既存型制約をTASK・Context・verifyへ同期 |
| Diagnostic効果・集約・workspace source | 採用・反映済み | [ADR-027](../02.設計書/10_決定記録/ADR-027_Diagnostic結果効果・集約・workspace-sourceの確定.md) |
| report生成条件 | 後続改訂 | 当時は非成功時の自動保存へ統一。ADR-041でstatusを問わず明示`--report`時だけへ変更 |

P2 7件の正本反映を完了したため、Core 1.0の設計reviewゲートを再び**完了**とする。

## 11. P3記述整合review（2026-08-31、裁定済み）

P2反映後の正本について、TASK要約、JSON例、Digest表記、report名、Diagnostic表の同期を確認した。
review 03の旧P3 5件とは別の指摘として、
[06_Core-1.0_P3記述整合reviewと改訂提案.md](06_Core-1.0_P3記述整合reviewと改訂提案.md)へ記録した。

| 項目 | 裁定 | 対応 |
|---|---|---|
| TASKと規範文なしTECHの要約 | 採用・反映済み | 最小トレース、Context関係説明、`implement`閉包を同期 |
| warning結果のJSON例 | 採用・反映済み | warningの根拠を追加し、単純な外形例は`passed`へ変更 |
| `check`結果例の`revision` | 採用・反映済み | `base`、`commit`、`dirty`を追加 |
| SHA-256表記 | 採用・反映済み | `sha256:[0-9a-f]{64}`へ統一 |
| report file名 | 採用・反映済み | UTC basic形式と衝突時連番を正規形へ明記 |
| Diagnostic表の列名 | 採用・反映済み | `resultStatus`へ統一 |

P3 6件の正本反映を完了したため、Core 1.0の設計reviewゲートを再び**完了**とする。

## 12. ユースケース・flow遷移review（2026-08-31、全8件裁定済み）

[ユースケース設計](../02.設計書/05_ユースケース.md)の作成時に、状態遷移matrixではなく
ユースケース間の接続に残る8件の実装分岐を確認した。

| 優先度 | 件数 | 主な内容 | 状態 |
|---|---:|---|---|
| P1 | 3 | Small Flowの実装後検査、先行TASKの状態ガード、verify bindingの重複排除 | 裁定・反映済み |
| P2 | 4 | code/test逆引き、Intent起点、Full Flowの戻り先、削除済みIDの保証範囲 | 裁定済み（ID保証はADR-037で再裁定） |
| P3 | 1 | ADR部分改訂の追跡方法 | 裁定・反映済み |

P1 3件はADR-028〜030、P2のうち2件はADR-031・032、P3 1件はADR-033として裁定し、正本へ反映した。
ADR-032は後続の実装前異常case reviewで[ADR-037](../02.設計書/10_決定記録/ADR-037_Git基準版間のSPEC同一性と削除規則.md)により置き換えた。
UC-FLOW-005と006はCoreの機械契約を追加しないため、本文反映だけで裁定した。

| ID | 裁定 | 主なADR |
|---|---|---|
| UC-FLOW-001 | Small/Full Flowを`Pre-check -> Implement -> Post-check`骨格へ改訂し、TASK起点は実装後に`bitz check <TASK-ID>`で境界を強制する | [ADR-028](../02.設計書/10_決定記録/ADR-028_開発flowの実装後検査とTASK境界の接続.md) |
| UC-FLOW-002 | TASK起点の`implement`／`verify`で`requires`先TASKの`done`を要求し、未完了は`CTX-TASK-DEPENDENCY-001`／`blocked`とする | [ADR-029](../02.設計書/10_決定記録/ADR-029_TASK先行依存の状態ガード.md) |
| UC-FLOW-003 | 検証binding識別子を`(workspaceId, 正規化argv template, 正規化cwd)`へ統一し、`{tests}`の有無にかかわらず1回実行とする | [ADR-030](../02.設計書/10_決定記録/ADR-030_verify実行bindingの正規識別子と重複排除単位の統一.md) |
| UC-FLOW-004 | 変更code/test pathを`implements`・`tests[].path`の逆索引から所有REQ/TECHへ正規化し、未所有pathは対象外（件数のみ）とする | [ADR-031](../02.設計書/10_決定記録/ADR-031_変更code・testからの検査対象選択.md) |
| UC-FLOW-005 | 機械起点をREQ・TECH・規範文・`open` TASKに限り、SPECを作らない変更をCore保証外と明示する | 本文反映 |
| UC-FLOW-006 | Full Flowへ否決edgeと`Done`を追加し、reviewの承認・否決をCoreの機械契約に含めないと明示する | 本文反映 |
| UC-FLOW-007 | 2時点比較で意味の再利用を判定せず、管理済みSPECの削除禁止と現在集合の重複検出へ限定する | [ADR-037](../02.設計書/10_決定記録/ADR-037_Git基準版間のSPEC同一性と削除規則.md) |
| UC-FLOW-008 | ADRの部分改訂を許可し、後継ADRのDecision・旧ADRの`Notes`・旧ADRの`Revision History`の3点で記録する | [ADR-033](../02.設計書/10_決定記録/ADR-033_部分改訂ADRの記録規約.md) |

指摘、修正候補、反映先、受入条件、裁定結果は
[07_ユースケース・flow遷移reviewと修正提案.md](07_ユースケース・flow遷移reviewと修正提案.md)を正とする。
8件すべてを裁定・反映し、本reviewはCloseした。

## 13. flow終端・遷移条件review（2026-08-31、8件裁定・反映済み）

review 07の8件を裁定・反映した状態で、開発flowとSPEC状態機械を終端と遷移条件の観点から再確認した。

| 優先度 | 裁定済み | 未裁定 | 主な残存内容 |
|---|---:|---:|---|
| P1 | 2 | 0 | — |
| P2 | 4 | 0 | — |
| P3 | 2 | 0 | — |

2026-09-01にUC-FLOW-009とUC-FLOW-012を裁定し、
[ADR-034](../02.設計書/10_決定記録/ADR-034_TASK完了終端とdone起点操作の確定.md)として正本へ反映した。

| ID | 裁定 | 対応 |
|---|---|---|
| UC-FLOW-009 | 修正採用・反映済み | TASK起点の`Done`をHuman Review、`open -> done`、Revision History更新、変更後の最終`check`、Git記録の順に固定 |
| UC-FLOW-012 | 採用・反映済み | `done` TASKは`implement`を`blocked`、`verify`と`interpret`を許可し、明示`check`も許可 |
| UC-FLOW-010 | 採用・反映済み | 引数なし変更範囲`check`の対象0件は、他のDiagnosticがなければ`passed`とし、選択件数を結果へ記録 |
| UC-FLOW-013 | 採用・反映済み | checkは`passed`または`passed_with_warnings`でflowを通過し、`--strict`は追加しない |
| UC-FLOW-016 | 採用・反映済み | Done前の`Stopped`、REQ／TECHの`rejected`と不採用理由、TASKの`cancelled`と中止理由を追加し、Historyとして保持 |
| UC-FLOW-011 | 修正採用・反映済み | Human Review否決を理由別にIntent、Context、Implementへ戻し、再作業しない場合は`Stopped`とする |
| UC-FLOW-014 | 案1採用・反映済み | ADR部分改訂を設計資料のローカル規約に限定し、Coreは文書全体の後継化だけを認識する |
| UC-FLOW-015 | 採用・反映済み | TASKの`changes`境界を明示checkだけで検査し、暗黙選択では文書検査だけを行う |

UC-FLOW-010と013は
[ADR-035](../02.設計書/10_決定記録/ADR-035_check空対象とflow通過statusの確定.md)として正本へ反映した。
UC-FLOW-016は
[ADR-036](../02.設計書/10_決定記録/ADR-036_flow取止めと不採用履歴の保持.md)として正本へ反映した。
P1はすべて裁定済みである。

指摘、修正候補、反映先、受入条件は
[08_flow終端・遷移条件reviewと修正提案.md](08_flow終端・遷移条件reviewと修正提案.md)を正とする。
8件すべてを裁定・反映し、本reviewはClosedした。実装根拠にはADR-034、ADR-035、ADR-036と
反映後の正本を使用する。

## 14. 実装前異常case review（2026-09-01、4件裁定・反映済み）

実装着手前に、削除・rename、取止め後の途中成果物、verify異常終了、入力読取り障害を再確認した。

| ID | 裁定 | 対応 |
|---|---|---|
| EDGE-001 | 修正採用 | `(workspaceId, documentId)`で基準版と現在版を対応付け、管理済みSPEC削除を拒否。ADR-032をADR-037で置換 |
| EDGE-002 | 縮小採用 | 既存Rationaleで途中成果物の処遇を記録し、変更を伴うphaseだけを個別commitへ分離 |
| EDGE-003 | 縮小採用 | verifyを決定論的に逐次実行し、timeout停止保証を直接processへ限定。有限時間回収は後続`FIN-PROC-001`で補完 |
| EDGE-004 | 縮小採用 | `SPEC-INPUT-READ-001`を追加し、原子的snapshotはCore 1.0の非目標とする |

Git全履歴走査、tombstone索引、`Stopped`専用status、空commit、verify並列scheduler、OS横断の
process-tree完全制御、filesystem全体の原子的snapshotは、Core 1.0には過大として採用しない。
理由と再評価条件は
[09_Core-1.0_実装前異常case-reviewと修正提案.md](09_Core-1.0_実装前異常case-reviewと修正提案.md)を正とする。
4件すべてを裁定・反映し、本reviewはClosedした。

## 15. 並行開発におけるID重複対策（2026-09-01、裁定・反映済み）

> この節は提案10を裁定した時点の記録である。ADR-038は後にADR-039で置換され、ここで追加した自動改番支援と
> `Integrate`段階はCore 1.0から延期された。現行契約には使用しない。

並行branchで独立採番された文書IDの衝突は、当初の設計では検出できるがmerge後にしか検出できなかった。
予防機構と早期検出機構がなく、正規file名が`<ID>-<slug>.md`を許すためGitのadd/add conflictも働かない。
検討経緯は
[10_並行開発におけるID重複対策の検討と提案.md](10_並行開発におけるID重複対策の検討と提案.md)、
当時の決定は[ADR-038](../02.設計書/10_決定記録/ADR-038_並行開発のID衝突解決と統合段階.md)に記録した。

採決事項9件（IDDUP-001〜009）と、それを設計へ落とす過程で確認した裁定事項16件（甲5件・乙4件・丙5件・
丁2件）をすべて裁定し、正本へ反映した。ADR-038として1件にまとめ、ADR-028とADR-037はADR-033の3点記録に
よる部分改訂とし、いずれも置換していない。

### 15.1 確定した骨子

| 論点 | 確定した方針 |
|---|---|
| 先勝ちの基準 | 統合先branchの先端に存在する側を勝者とする。commit時刻、`semanticHash`、Git rename検出を使わない |
| 正規手順 | 統合先との合流をGitへ記録した後の木で改番する。勝者が旧IDを保持するためkeyが消えない |
| 改番の実行主体 | Skill／拡張へ委譲し、Coreは検出と機械可読な提示に限る。公開操作は4つのまま非変更系 |
| 新IDの採番 | 同一workspace・同一種別の全IDの最大値+1。0埋め幅の異なるIDは別IDとする |
| 対象種別 | REQ、TECH、TASK、ADR |
| Frontmatter | 改番を表す項目を追加しない。記録は`Revision History`へ置く |
| 開発flow | 骨格へ`Integrate`を追加。完了条件はPR mergeを含めず、統合先先端を基準版とする再検査の通過まで |
| CIの基準版 | `--base <統合先先端>`へ統一。検査対象の木が統合先先端を含むことを前提とする |

新しい入力機構、永続台帳、Git履歴走査は追加していない。ADR-037が裁定した「削除と再作成の交差」に対する
保証範囲も変更していない。

### 15.2 検討中に見つかった既存設計の欠落

裁定の過程で、改番に固有ではない欠落と、提案本文自体の誤りが見つかった。いずれも訂正して反映した。

- **TASKをPR内で完了できない。** §6.3とFrontmatter共通仕様 §5の遷移表はTASKの作成時状態を`open`だけと
  するが、基準版は自branchの外側にあるため、branch内で`open -> done`まで進めたTASKは`[new] -> done`と
  なり許可された遷移に含まれない。実装すれば`done` TASKを含むPRを一律に`failed`にする。基準版に存在
  しない文書は現在値の語彙だけを検査する規則を確定した（丙-2）。承認済みREQ保護が「Git基準版に存在
  しない新規fileは変更前状態との比較対象外とする」としているのと同じ原則である。
- **§4.2の判定表が§3.1と矛盾していた。** 「両方が基準版に存在する＝発生しない」としていたが、slugの
  異なる同一ID fileはGitがconflictにせず、合流commitのtreeには2件入る。`SPEC-BASE-AMBIGUOUS-001`／
  error／`blocked`として扱う（甲-1、乙-1）。
- **IDDUP-005の推奨が実装できなかった。** 改番pathを`rewriteSites`から境界検査の対象外にする案は、
  境界検査の時点で重複が解消し`idCollisions`が空になるため成立しない。P1で確定したcommit規約とflow
  順序が既に解になっており、追加したのは基準版の条件1文だけである（丙-3）。
- **改番でDigestが変化しないという受入条件が成立しなかった。** `semanticHash`は正規化Frontmatterを含む
  ため、`id`の変更はContext Digestを変える。`Revision History`への追記だけが意味集合の外にある（甲-3）。
- **IDDUP-009の理由付けが誤っていた。** 敗者の削除が許されるのはADR-037 Decision 4（未追跡SPECの破棄）
  ではなく、勝者が同じ文書IDを保持しkeyが消えないためである（丁-2）。

### 15.3 安全側へ倒した判断

- `SPEC-BASE-AMBIGUOUS-001`はseverityを`error`、resultStatusを`blocked`とした。warningにすると改番適用後に
  勝者の遷移検査・削除判定・承認保護が通過statusのまま抜ける。`warning`／`blocked`はADR-021 Decision 4が
  禁じるため中間の強度は取れない。
- `--base`未指定時は`idCollisions`へ`instances`だけを返す。既定`HEAD`は新規の衝突について正しい勝敗を
  出せず、合流を未commitのまま検査すると統合済みの勝者側へ改番を提案してしまう。

### 15.4 不採用とした案

`renumberedFrom`および`x-renumbered-from`は撤回した。前者はGitから導ける情報をFrontmatterへ持ち込み、
ADR-015 Decision 4と旧SPEC知見の「成果物ごとのversion、updated」と同型の陳腐化を生む。後者は`x-`拡張を
合否判定へ使用しない規則に反する。Coreへの`bitz renumber`追加、commit時刻による先勝ち、番号レンジ予約、
ULID等への変更、基準版の重複pathから代表を選ぶ案も採らない。不採用理由はADR-038のAlternatives（18件）を
正とする。

## 16. 仕様構造の再編とCore 1.0簡素化（2026-09-01、裁定・反映済み）

既存reviewで契約の欠落と不整合を解消した結果、同じ規則を設計書、詳細設計、ユースケース、運用、ADRへ
同期するコストが顕在化した。構造化設計、KISS、YAGNI、DRYの観点から、規範の所有者を1か所へ固定し、
Core 1.0を単一workspaceの垂直スライスへ戻す案を
[11_仕様構造の再編とCore-1.0簡素化提案.md](11_仕様構造の再編とCore-1.0簡素化提案.md)に記録した。

STRUCT-001〜011をすべて採用し、[ADR-039](../02.設計書/10_決定記録/ADR-039_Core-1.0仕様構造の再編とscope縮小.md)、
再編後の`docs/02.設計書`と`docs/03.詳細設計`へ反映した。複合workspace、ID改番支援、Profile実行基盤、
Projection Digestなどは、提案11の再評価条件を満たすまでCore 1.0へ戻さない。このうち複合workspace延期だけは、
2026-09-02の後続判断で部分改訂した。

## 17. 複合workspaceのCore 1.0再導入（2026-09-02、裁定・反映済み）

対象monorepoで1.0から安定したworkspace ID、横断参照、所有境界を持たせるため、
[ADR-040](../02.設計書/10_決定記録/ADR-040_複合workspaceをCore-1.0へ再導入する.md)で
ADR-039 Decision 5だけを部分改訂した。旧仕様をそのまま戻さず、明示catalog、修飾ID、横断Context、
`--all-workspaces`を再編後の責務境界へ追加した。

command名単位のverify、Context Digestだけを公開hashとする方針、Profile実行基盤・ID自動改番・必須Revision Historyの
延期は維持する。Context Digestの結果内配置は後続ADR-041でtarget単位へ改訂した。
規範は再編後の`docs/02.設計書`と`docs/03.詳細設計`、実装順序は更新後の
[12_Core-1.0実装計画](12_Core-1.0実装計画.md)へ反映済みである。

## 18. 複合workspaceCore 1.0再review（2026-09-02、review時点）

ADR-040反映後の作業treeを固定し、7観点を互いに独立してreviewした。結果はP0 1件、P1 18件、P2 10件の
計29件である。同じ原因を別観点から検出した指摘を、
[横断review](20_複合workspace-Core-1.0横断review.md)で7つの裁定単位へ統合した。

| 横断課題 | 優先度 | 要旨 |
|---|---|---|
| FED-CROSS-001 | P0 / Closed | 複数target verifyを単一`contextDigest`で証明できない |
| FED-CROSS-002 | P1 | 旧Coreが同一Schema majorの`monorepo`を無視できる可能性がある |
| FED-CROSS-003 | P1 | 未登録SPECとsymlinkを含む所有境界の完全性が不足する |
| FED-CROSS-004 | P1 | Context、複合workspaceの結果、bindingの公開Schemaが閉じていない |
| FED-CROSS-005 | P1 | 全体操作の起点、未知workspace、継続、revisionが未確定である |
| FED-CROSS-006 | P1 | workspace同一性と移行・rollback契約が不足する |
| FED-CROSS-007 | P1 | resource数値、性能測定、期待JSON fixtureが不足する |

設計方針は条件付き採用を維持するが、設計reviewゲートは再度**未完了**とする。§17のContext Digest配置は、
単一targetには成立するものの複数targetでは成立しないことが判明した。FED-CROSS-001は後続ADR-041で裁定・反映した。
この時点では残るP1裁定まで実装着手を保留した。P1は後続の§20とADR-042で裁定・反映済みである。

## 19. verify対象別証跡と明示report保存（2026-09-02、裁定・反映済み）

FED-CROSS-001を[提案21](21_P0_verify証跡Schema検討.md)で具体化し、
[ADR-041](../02.設計書/10_決定記録/ADR-041_verify対象別証跡とreport明示保存の分離.md)として裁定した。

- targetごとにContextを解決し、`targetResults[]`を検証証跡の正本とする
- 最上位の単一`contextDigest`、`targets[]`、`statements[]`を廃止する
- binding IDを単一workspaceでも`<workspace-id>::<command-name>`へ統一する
- Context／coverageが非成功のtargetだけが要求するbindingは実行しない
- target、workspace、最上位のstatusを段階別に集約する
- `check`と`verify`はstatusにかかわらず`--report`指定時だけ結果fileを保存する

report保存条件は、独立履歴branchで確認した並行PR／worktree検査の残留file事例を踏まえた。Git除外は維持するが、
自動保存の根拠には使わない。これによりFED-VER-001〜005とFED-CROSS-001をClosedとする。

## 20. 複合workspace残存P1の裁定（2026-09-03、裁定・反映済み）

P0反映後に残るP1 15件を[提案22](22_複合workspace残存P1裁定案.md)で再整理した。Core 1.0が未releaseという
確認済み事実により`FED-MIG-001`はversion gateを追加せず解消でき、正本への追加裁定が必要な実質残件は14件である。

残件は、初回公開と同一性、catalog完全性と所有境界、公開Schema、CLI境界、resource上限、性能受入条件の
6単位へ統合し、全点を採用した。判断理由を
[ADR-042](../02.設計書/10_決定記録/ADR-042_複合workspaceの同一性・所有境界・公開契約を確定する.md)、
機械契約を詳細設計、移行と性能条件を運用手順・実装計画へ反映した。これによりP0・P1 gateはClosedとする。
設計review全体は残るP2 6件の裁定まで完了としない。

## 21. 複合workspace残存P2の裁定（2026-09-03、裁定・反映済み）

P1反映後に残ったDiagnostic優先順位、非成功後の継続、TASK directory境界、consumer rollback、計算量、
conformance matrixの6件を[提案23](23_複合workspace残存P2裁定案.md)で具体化した。

提案は、全体事前検査だけを全停止境界とし、その後は文書・target・binding単位で独立処理を継続する。
TASKの許可集合は字句Git path、所有集合はbase/current双方のcanonical pathで判定する。運用はdual-read consumerを
先行配備し、複合workspace化とrollbackを同じ変更単位にする。受入ではgraph sizeへ線形な索引memory、最大Context閉包へ
線形な一時memory、hard-limit fixture、期待JSON matrixを固定する。

6件を一括採用し、[ADR-043](../02.設計書/10_決定記録/ADR-043_複合workspaceの継続・TASK境界・適合契約を確定する.md)と
各正本へ反映した。review 14、15、17、18、19と横断review 20のP2をClosedとし、複合workspaceCore 1.0の
設計reviewを完了する。実装受入にはversion管理した期待JSON matrixの全通過を要求する。

## 22. 実装着手可能性の点検（2026-09-03、裁定・反映済み）

設計review gateがすべてClosedしたため、確定した規範だけで実装へ着手できるかを
[提案24](24_Core-1.0実装着手方針.md)で点検した。「Coreが何をするか」の契約は実装可能な水準に達している。

不足するのは「実装が何を出力すれば適合と言えるか」を閉じる契約である。G1〜G9のうち、
Context DigestのCanonical JSON未定義（G1）と、適合fixture matrixが非規範文書にしかないこと（G2）は
受入基準そのものであり、これを閉じるまでcode着手を保留する。G3〜G7は既存の裁定に反さず記述の追補で足りる。

提案24は、codeを書かないStep 0で上記を閉じ、その後の実行順をdoctorと結果配管を先に通す
骨格優先へ変更することを求めた。

同日、G1〜G8を全件採用して正本へ反映した。Context Digestの正規化と適合fixtureは
`03.詳細設計/00_共通契約`へ新設し、期待matrixへ単一workspaceの`SINGLE-001`〜`080`を追加した。
Diagnostic表の閉包、終了コード4の出力、非成功時のtext出力を共通契約へ追記し、
MCP面のscope外化を[ADR-044](../02.設計書/10_決定記録/ADR-044_MCP面をCore-1.0のscope外とする.md)、
実行環境と配布物を[ADR-045](../02.設計書/10_決定記録/ADR-045_実行環境と配布物の確定.md)で確定した。
accepted ADR 8件のlinkは現構造へ訂正した。G9は着手gateに含めず実装計画Step 6とした。

[実装計画](12_Core-1.0実装計画.md)へStep 0と骨格優先の実行順を反映し、Step 0をClosedとした。
実装着手gateはOpenである。

## 23. 実装前最終review（2026-09-04、裁定・反映済み）

提案24の反映後、提案資料01〜24を検討履歴、`02.設計書`を目的・境界、`03.詳細設計`を機械契約の正として
再度横断し、規範だけから独立した2実装が同じ結果を再現できるかを
[提案25](25_Core-1.0実装前最終reviewと修正提案.md)で点検した。

設計方針、scope、安全境界、複合workspaceidentityと所有境界は妥当であり、全面再設計は不要である。
一方、適合fixtureの再現性、Diagnostic閉包、EARS-AI文法、公開結果Schema、target展開、
Frontmatter/YAML型にP0 6件が残る。Context Digest、cache、verify process、CLIとADR依存、
性能受入成果物にもP1 5件が残る。

提案24でOpenとした実装着手gateは、これらの不足により本review時点では**No-Go**とする。
提案25は、契約修正、fixture/Schema/CI準備だけを先行可能とし、P0を閉じるStep 0B、
機械検証、golden Digest、有限時間のtimeout試験を完了してからgateを再判定することを提案する。

提案25のD1〜D8を採用し、P0 6件とP1 5件を正本、Schema、matrixまたは性能受入成果物へ反映した。
提案の裁定・反映は完了したが、実fixture成果物、実測baseline、Step 0Bのcross-checkとgate再検証は未完了である。

## 24. 実装前最終reviewの反映状況（2026-09-24更新）

提案25の採否と実装着手可否を分離して管理する。提案25はAccepted / Reflectedであり、現在のGate Aは
`Allowed`である（2026-09-24、commit `cf2fa3d`で認定）。Gate条件の正本は[実装計画 §1.1](12_Core-1.0実装計画.md#11-進行状態とgate)とする。

| 区分 | 現在の状態 | 残件 |
|---|---|---|
| P0 6件 | 契約、Schema、matrixへ反映済み | 実入力と期待結果は310件すべてfixture化済み（golden Digestは`SINGLE-042`と`MULTI-002-01`で確定）。統合検証がmatrixの全IDの検証を確認 |
| P1 5件 | 契約または性能受入成果物へ反映済み | process helper等の検証基盤、Core実装後の受入結果と性能baseline |
| P2文書衛生 | accepted ADR linkとREADME状態を修正済み | — |
| 自己適用 | 実装計画へ配置済み | Step 2完了後に`.spec/`を作成し、Gate Cで最終判定 |
| Step 0B | `Complete` | 公開JSON・文法・link・Git/process基盤・Diagnostic意味網羅・target集合25 case・実fixture 310件（単一workspace 250件、複合workspace 60件。内訳は[実装計画 §3.1](12_Core-1.0実装計画.md#31-step-0b-gate-a実証基盤)）の準備を検証済み。golden Digestは単一・複合workspaceとも独立2系統のreference計算で一致。上限境界24件はscale検証で実寸を照合済み。2026-09-18にfresh checkoutでも統合検証とscale検証が作業treeと一致。2026-09-24に`uv run fixtures/certify_gate_a.py`が独立した2つのcloneで統合検証とscale検証を再実行し、結果の一致を確認 |
| Step 0-P | `Complete` | 基準入力・比較条件を固定し一括検証済み。実測はCore実装後 |
| Gate A | `Allowed` | —（認定結果と実行環境は[適合fixture検証記録](../../fixtures/conformance/適合fixture検証記録.md)に記録） |
| Step 1 | `Complete` | 参照harness、偽のCoreによる自己試験、Core骨格、`doctor`、`check`の設定・workspace段階を実装済み |
| Gate B | Step 1 `Passed`、Step 2〜5 `Pending` | 各StepのCore実装を固定済みfixtureへ通して判定。認定結果は[Gate B認定記録](../../tests/bitz-core/Gate-B認定記録.md)に記録 |
| Gate C | `Pending` | 全適合、性能、決定性、副作用、process、自己適用をまとめて判定 |

2026-09-17の単一fixture作成で、role割当、interpretのdraft refinement、statement起点の提示、verifyの起点TASKの
`requires`を裁定し、関係・トレースモデル §6.1・§6.4・§7、context仕様 §4・§5、matrix `SINGLE-106-03`・`110`行へ
本文反映した（既存決定の欠落補完のためADRは起こさない）。経緯は
[Diagnostic台帳の再review](../../fixtures/conformance/Diagnostic意味網羅review.md)に記録した。

同日、`SINGLE-127-15`〜`19`を作成するため[提案27](27_適合harness外部仕様の検討.md)で適合harnessの外部仕様を検討し、
検査対象の受取り、Python・Git versionの指定、JSON互換runner、package runnerを
[ADR-046](../02.設計書/10_決定記録/ADR-046_適合harnessの検査対象・実行環境・runnerを確定する.md)として裁定した。
Gate Cには全matrixを下限CPython 3.11と基準環境の2環境で通す条件を加えた。
2026-09-24に[ADR-053](../02.設計書/10_決定記録/ADR-053_CPythonの下限を3.12へ引き上げる.md)で下限と基準環境を
CPython 3.12へ引き上げ、`SINGLE-127-19`を`python: "3.12"`へ改めた。

表記統一のため[用語集](../用語集.md)を定め、複数のworkspaceを束ねる構成を「複合workspace」と呼ぶことにした。あわせて[ADR-047](../02.設計書/10_決定記録/ADR-047_複合workspaceの識別子をmultiWorkspaceへ改名する.md)で、識別子を`multiWorkspace`、`SPEC-MULTI-*`、`MULTI-*`へ改名した。本READMEと裁定済みの提案資料の履歴部分は当時の識別子を残す。

Gate Aを`Allowed`へ変更するのは、[提案25 §9.1](25_Core-1.0実装前最終reviewと修正提案.md#91-gate-a-実装着手可能性)の
Core非依存条件を満たす自動検査結果と実行環境を同一commitで確認した後とする。Core本体の挙動はGate Aで要求せず、
対応するGate Bと最終のGate Cで判定する。
