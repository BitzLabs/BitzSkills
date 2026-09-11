# 文書構造・UTF-8 fixtureレビュー

2026-09-11。SINGLE-014、016、017-01/02/03、018-01/02/03、019の9件を追加する。
入力と受入期待値の準備であり、Coreの実装結果ではない。文書ID重複のSINGLE-015は今回の対象に含めない。

## 単一原因と完全期待値

全件を最小設定、SPEC 1件、関係・code・test・bindingなしで独立配置する。
入力を固定metadataでcommitし、`check --full --base HEAD --format json`を実行する計画とする。
base/currentを同一にして変更保護・状態遷移などを別原因として混ぜない。

| ID | 入力の唯一の差分 | Diagnostic | status / exit | 完全検査文書 / 規範文 |
|---|---|---|---|---|
| SINGLE-014 | FrontmatterとH1はREQ-001のまま、file名だけREQ-002.md | SPEC-FILE-NAME-001 | failed / 1 | 0 / 0 |
| SINGLE-016 | approved REQのAcceptance Criteriaを非空の説明文だけにする | SPEC-REQ-STATEMENT-001 | failed / 1 | 0 / 0 |
| SINGLE-017-01 | H1のtitleだけFrontmatterと異なる | SPEC-STYLE-H1-001 | failed / 1 | 1 / 1 |
| SINGLE-017-02 | Verification節だけを削除 | SPEC-STYLE-SECTION-001 | failed / 1 | 1 / 1 |
| SINGLE-017-03 | accepted ADRのDecisionにADR-001:AC-01の規範行を1件配置 | SPEC-STYLE-PLACEMENT-001 | failed / 1 | 1 / 0 |
| SINGLE-018-01 | 必須H2をVerification、Acceptance Criteria、Intentの順へ変更 | なし | passed / 0 | 1 / 1 |
| SINGLE-018-02 | 空の任意Notes節を追加 | なし | passed / 0 | 1 / 1 |
| SINGLE-018-03 | 太字の疑似節と説明段落を追加 | なし | passed / 0 | 1 / 1 |
| SINGLE-019 | 有効なREQの末尾に単独の0xff byteを追加 | SPEC-INPUT-READ-001 | failed / 1 | 0 / 0 |

014は参照解決の正をFrontmatterとし、本文とFrontmatterのID不一致を作らない。
016は必須節を空にせず、規範文0件だけで失敗させる。017-02も正常な規範文と他の必須節を残す。
017-03は配置directory、Frontmatter、H1、候補行IDをADRへ統一し、ID不一致を混ぜない。
文法上妥当な候補を使い、placement以外の構文不正を作らない。ADRは規範契約の所有者ではないので
規範文数へ候補行を加えない。018系は必須節と正常規範文をすべて保持し、style warningも出さない。
019は権限・file不在・設定不正ではなく、SPEC MarkdownのUTF-8復号だけに失敗する。
入力はbinary byte列のままversion管理し、置換文字への修復を禁止する。

## 診断位置・件数の選択

registryのskip-documentに従い014、016、019は後段の完全検査件数へ加えない。
styleの3件はcontinueなので全検査を続け、非成功でも文書数は1とする。
失敗statusを理由にすべての文書数を0へ丸めない。

- 全Diagnosticはerror / failed、file source、workspaceId rootとし、原因のpathを固定する。
- 014は実在するREQ-002.mdを指し、source.keyはidとする。
- 017-01はH1の7行1列、017-03は候補行IDの15行3列を指す。
- 016、017-02、019はfile単位。欠落位置や復号不能位置のline/columnを推測しない。
- summaryは各expected/check.jsonの固定値。suggestedAction、specRefs、evidenceは付加しない。
- Git IDとdurationだけは既存normalizer用の代表値とし、status、件数、配列、sourceは比較から除外しない。

これらの任意fieldと文字列は今回固定した受入期待値であり、Coreから採取したものではない。
根拠は[文書・Frontmatter仕様 §1](../../../docs/03.詳細設計/02_SPECモデル/02_文書・Frontmatter・状態仕様.md)、
[本文テンプレート §1・§2・§4・§7](../../../docs/03.詳細設計/02_SPECモデル/03_文書種別・本文テンプレート.md)、
[Diagnostic registry](../../../docs/03.詳細設計/00_共通契約/05_Diagnostic-registry.md)、
[check仕様 §4・§9](../../../docs/03.詳細設計/03_操作仕様/02_check.md)、
[適合matrix §6.2](../../../docs/03.詳細設計/00_共通契約/04_適合fixture仕様.md)である。

## 検証範囲

document_fixtures.pyはmanifest、完全期待JSON、Frontmatterの固定3 field、副作用期待値のSchemaと、
レビュー済み入力byte列を検査する。余分なfileや最小設定の変更も拒否する。汎用Parserは実装しない。
各fixtureのrepository、Git status/index、HOME、cache、TMPDIRを独立した2回のsetupで固定snapshotと照合する。
read-onlyのafterはbeforeと同じ期待値であり、Coreによる実測値ではない。

回帰試験はskip/continue件数、ADR候補の件数、診断path/code、styleへのwarning追加、report指定、
HOMEへの書込み期待、UTF-8不正のstatus変更・置換文字への修復、余分な文書・設定不正を拒否する。
実際のCore出力と副作用はGate Bで確認する。

導入・設定9件、EARS 12件、[関係・path・coverageの6件](trace-review.md)、[ID重複・循環の4件](graph-review.md)、[Git基準版の5件](git-review.md)、[保護対象外変更の5件](exempt-review.md)と合わせて50/311件を準備した。
017-02と018-01の末尾の余分な空行を除去し、固定入力とsnapshotも同期した。意味上の期待値は変更しない。
実fixture残261件、golden Digest、全体の副作用期待値、fresh checkoutの全Gate A検証は未完了である。
