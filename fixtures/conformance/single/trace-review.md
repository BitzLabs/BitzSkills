# 関係・path・coverage fixtureレビュー

2026-09-11。SINGLE-020、021、023、024、025、026の6件の入力と完全期待値を固定する。
Coreの関係解決、path検査、coverage判定を実装・実行した結果ではない。

## 単一原因

各fixtureは正常なREQ-001、必須H2、妥当なAC-01を保持する。明示HEADとcurrentは同じ木で、
`check --full --base HEAD --format json`を計画する。Git変更・承認保護を別原因にしない。

| ID | 原因の固定 | Diagnostic / status / exit | 完全検査文書 / 規範文 |
|---|---|---|---|
| SINGLE-020 | requiresが存在しないREQ-999を参照 | SPEC-RELATION-MISSING-001 / failed / 1 | 1 / 1 |
| SINGLE-021 | REQが存在するapproved TECH-001をrefines | CTX-RELATION-TYPE-001 / failed / 1 | 2 / 1 |
| SINGLE-023 | 旧refsが存在するTECH-001を参照 | SPEC-RELATION-LEGACY-001 / failed / 1 | 2 / 1 |
| SINGLE-024 | approved REQのimplementsが未作成src/missing.pyを宣言 | SPEC-PATH-INVALID-001 / failed / 1 | 1 / 1 |
| SINGLE-025 | 024のstatusだけdraftへ変更 | SPEC-PATH-INVALID-001 / passed_with_warnings / 0 | 1 / 1 |
| SINGLE-026 | 実在testのcoversが存在しない同一REQのAC-99を参照 | SPEC-TEST-COVERAGE-001 / failed / 1 | 1 / 1 |

020は参照先IDの語彙・型自体は正しく、横断意図を推測しない。
021では参照先を実在させ、REQ→TECHのrefines型違反だけを返す。TECHは規範文なしを許され、
正常なH1・Frontmatter・Contextを持つため、規範文不足の別原因を作らない。
023も同じTECHを置き、旧refsだけを拒否する。未知field warning、参照切れ、requiresへの自動変換を追加しない。

024と025はstatus以外のbyte列を同じにし、存在しない通常の相対file pathを宣言する。
絶対path、parent traversal、directory、symlink、workspace外の所有境界は混ぜない。
026はtest fileを通常fileとして配置し、default command、cwd、実行fileも用意する。
commandはLinux環境の`/bin/true`、cwdは`.`。準備検証では実行可能性だけを確認して起動しない。
test fileは誤って実行すれば失敗する内容だが、checkでtestを実行しないことの実証はGate Bで行う。
MUST句の未testedに対するverifyのblockedをcheckへ追加せず、covers不在の診断だけを返す。

## 完全期待JSONと副作用

registryの関係3件はskip-edgeであり、文書自体の独立した検査を続ける。
path・coversはcontinueなので、いずれも正常な本文の完全検査件数を保持する。
checkの文書検査完了を、非成功の関係を含むContext閉包が完全であることの証明には使わない。

- 各原因のprimaryは1件だけとする。error / failedを基本とし、025だけwarning / passed_with_warnings。
- sourceはfile、workspaceId root、path `.spec/requirements/REQ-001.md`。
  source.keyは順に`relations.requires`、`relations.refines`、`refs`、`implements`、`implements`、`tests[0].covers`。
  配列の原因要素が各1件であるため、関係とimplementsはfield keyで固定する。
- line/column、specRefs、evidence、suggestedActionは付加しない。summaryはexpected JSONの固定日本語文字列とする。
- Git IDとdurationだけ既存normalizer用の代表値を使う。件数・診断順・任意fieldを比較から除外しない。
- repo、Git status/index、HOME、cache、TMPDIRのread-only before/afterを固定し、許可書込みを0件とする。

これらの任意field・文字列は今回の受入期待値の選択であり、既存Coreから採取したものではない。
根拠は[関係・トレースモデル §4・§5.1・§9](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md)、
[文書・Frontmatter仕様 §3・§4・§5](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md)、
[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
[check仕様 §4・§9](../../../docs/03.詳細設計/03_操作仕様/02_check.md)、
[適合matrix](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)である。

## 準備検証

trace_fixtures.pyは固定入力byte列、レビュー済みFrontmatter値のSchema、manifest、完全期待JSON、
副作用Schemaを照合する。FrontmatterのYAML原文と対応する値は固定ペアであり、汎用YAML parserは実装しない。
各2回の隔離setupを固定snapshotと比較し、余分なfile、原因の修復、別原因の混入を拒否する。
回帰試験は二重診断、missingとtypeの取り違え、独立TECHの検査漏れ、draft severity、covers source、
report指定、cache書込み期待、参照先・test・commandの欠落、path作成、refs自動変換を拒否する。

[ID重複・循環の4件](graph-review.md)を追加し、40/311件を準備済み、実fixture残271件とする。golden Digest、全体の副作用期待値、
fresh checkoutの全Gate A検証は引き続き残る。Gate AはBlockedである。
