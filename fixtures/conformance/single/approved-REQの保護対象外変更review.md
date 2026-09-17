# approved REQの保護対象外変更fixtureレビュー

2026-09-11。SINGLE-032-01〜05の5件を追加する。approved REQの意味変更拒否を扱うSINGLE-031と対にし、
保護対象外の変更だけを拒否しない受入期待値を固定する。Coreを実行した結果ではない。

## 単一原因と期待値

全件のHEADには同じapproved REQ-001とAC-01を置く。必要な補助fileはHEADに配置済みとし、
manifestはREQ-001の未stage更新1回だけを行う。`check --full --base HEAD --format json`を計画する。

| ID | REQの唯一の変更 | HEADから存在し変更しない入力 | 完全検査文書 / 規範文 |
|---|---|---|---|
| SINGLE-032-01 | implementsへsrc/contract.pyを追加 | 通常の実装file | 1 / 1 |
| SINGLE-032-02 | testsへ実在testとAC-01へのcovers、default commandを追加 | test fileと有効なcommand設定 | 1 / 1 |
| SINGLE-032-03 | relatedへTECH-001を追加 | 正常なapproved TECH、規範文なし | 2 / 1 |
| SINGLE-032-04 | x-risk: lowを追加 | なし | 1 / 1 |
| SINGLE-032-05 | Intentの説明文だけを追記 | なし | 1 / 1 |

全件passed / exit 0、Diagnosticは空配列。title、H1、status、規範文、強い関係を変更しない。
revisionのbaseとcommitは同じHEADの代表値、dirtyはtrueとし、既存normalizer以外で比較を弱めない。

01の実装fileは存在確認用であり、その挙動を証明したとは扱わない。
02はtestsの追加だけが差分になるよう、test fileとdefault commandをbaseから置く。
coversは現在のAC-01を指し、未定義句・別文書句・重複を含めない。
commandはLinuxの`/bin/true`、cwdは`.`であり、準備検証は実行可能性だけを確認して起動しない。
test fileには誤実行時の失敗を置くが、checkが実行しないことの実証はGate Bで行う。
03は実在するTECHへの弱い関係とし、参照切れwarning・strong dependencyの影響候補を混ぜない。
full検査ではTECHも検査対象なので文書数は2、TECHに規範文はないので規範文数は1。
04は許可されたx-拡張であり、未知key warningを追加しない。05は規範文の句点や意味を変更しない。

根拠は[文書・Frontmatter・状態仕様 §8](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md)、
[関係・トレースモデル §8・§9](../../../docs/03.詳細設計/02_SPECモデル/04_関係・トレースモデル.md)、
[check仕様](../../../docs/03.詳細設計/03_操作仕様/02_check.md)、
[適合matrix](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)である。

## 準備検証

既存git_fixtures.pyを拡張し、実入力と変更後byte列、固定YAMLとレビュー済みFrontmatter値のSchema、
manifest、完全期待JSON、read-only副作用期待値を照合する。汎用YAML解析や意味差分の判定は実装しない。

各2回の隔離setupでHEAD/indexのpathとblob、worktreeのfile集合とbyte列を直接比較する。
変更はREQの未stage更新だけで、補助fileと設定はHEAD/index/worktreeのすべてで同一でなければならない。
Core実行直前のrepo・Git status/index・HOME・cache・TMPDIRを固定snapshotへ照合し、afterも同一を要求する。
このafterは期待値であり、Core実行後の観測値ではない。

回帰試験は成功の失敗化、文書・規範文数の誤り、x-拡張へのwarning追加、dirtyの消去、
実装path不在、covers不正、relatedのstrong化、x-なしkeyへの変更、説明変更への規範文変更混入を拒否する。
新5件でも誤ってstageした実repositoryをHEAD/index照合が拒否することを確認する。
Coreの意味変更保護、副作用、実stdoutと終了コードはGate Bで受け入れる。

50/311件を準備済み、実fixture残261件とする。golden Digest、残fixtureの副作用期待値、
fresh checkoutからの全Gate A検証は未完了であり、Gate AはBlockedを維持する。
