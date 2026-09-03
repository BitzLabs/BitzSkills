---
id: ADR-043
title: モノレポ連合の継続・TASK境界・適合契約を確定する
status: accepted
relations:
  requires:
    - ADR-041
    - ADR-042
  related:
    - ADR-028
---

# ADR-043 モノレポ連合の継続・TASK境界・適合契約を確定する

## Context

ADR-041とADR-042により、target別verify証跡、明示report保存、workspace identity、global preflight、
canonical所有境界、公開結果Schema、resource上限、通常性能fixtureを確定した。一方、Core 1.0受入までに、
横断参照失敗のDiagnostic優先順位、workspace非成功後の継続範囲、TASK directory prefixとsymlink、
consumer rollback、hard limit時の計算量・memory、期待JSON適合matrixを確定する必要がある。

workspace単位で一律に停止すると無関係な文書とtestを検査できない。逆に、失敗後も一律継続すると、不完全な
strong relation閉包からContextやverify planを作る。継続可否はglobal preflightと、文書・target・bindingの
依存単位に分けなければならない。

TASK境界では、symlink解決後の実pathを許可prefixとの比較に使うと、字句上は列挙していないpathへ許可が広がる。
ただし字句比較だけでは別memberへ解決するsymlinkを防げないため、許可集合と所有集合を別々に検査する必要がある。

## Decision

1. relation edgeは構文・型、修飾ID字句、非修飾横断参照、未知workspace、存在workspace内のtarget不在、
   source／target型不適合の順に検査し、最初の1原因だけをprimary Diagnosticとする。未知workspaceまでは
   `SPEC-MONOREPO-REF-001`、存在workspace内のstrong target不在は`SPEC-RELATION-MISSING-001`、存在する
   targetの型不適合は`CTX-RELATION-TYPE-001`とする。`CTX-RELATION-MISSING-001`は公開結果で使わず予約する。
2. ADR-042のglobal preflight非成功だけを全停止境界とし、member処理、Context解決、command実行を開始しない。
   preflight通過後は、checkは文書とsource edge、context／verifyはtargetのstrong relation閉包、verify commandは
   bindingを独立処理単位とし、依存しない後続処理を決定論的順序で継続する。
3. 根本原因を持つunitとは別のtargetまたはdoctor checkが依存出力を得られず実行不能になった場合だけ、
   `SPEC-MONOREPO-DEPENDENCY-001`／`blocked`を返す。既に同じunitへ具体的なmissing、type、state、coverage
   Diagnosticがある場合は重複させない。
4. TASK `changes`のfileとdirectory prefixは、正規化した字句Git pathの完全一致またはpath segment prefixで
   許可判定する。symlink解決先へ許可を拡張しない。宣言pathと変更pathの所有判定は別に行い、追加はcurrent、
   削除はbase、変更とsymlink変更はbase/current双方をcanonicalizeする。renameは削除と追加の2 pathとして扱う。
5. JSON consumerは`schemaVersion` majorを確認した後、`workspace`だけを持つ単独結果と、`federation`および
   `workspaces`だけを持つ全体結果を排他的に識別する。修飾ID、report名、current directoryから形式を推測しない。
   連合producerより先にconsumerをdual-read化し、adapter／CIは`monorepo.v1`を確認してから全体操作を有効にする。
6. rollbackはcatalog、member設定、修飾関係・coverage・TASK参照、CI全体操作、Capability gate、report consumerを
   同じrelease単位で戻す。過去reportを書き換えず、単一と連合のartifact系列を混ぜない。後続変更を失わずに
   全体を戻せない場合は自動down migrationを行わず、連合状態をforward fixする。
7. global索引のmemoryをfile、statement、edge、trace、commandの入力graph sizeへ線形とする。target Contextは
   visited集合で到達graphへ線形に解決し、全体verifyはtargetごとの完全Bundleを同時保持せず、Digest、statement、
   binding参照へ縮約して次targetへ進む。全組合せmatrixを作らない。
8. resource dimensionごとに他dimensionを通常規模へ保った`limit - 1`、`limit`、`limit + 1` fixtureを作る。
   最大dimension fixtureは基準環境でCore peak RSS増分1 GiB以下、2 GiB memory limit下で正常終了させる。
   これは通常fixtureの200 MiB目標を緩和せず、公開SLOではなくhard-limit安全受入条件とする。
9. 同名local ID、横断関係、Diagnostic優先順位、未登録設定、symlink、TASK prefix、継続、multi-context verify、
   共有binding、0件、identity、Git不在、resource境界、report副作用、consumer、rollbackをversion管理fixtureと
   期待JSONへ固定する。`durationMs`等の指定済み非決定値だけを共通normalizerで除外し、fixture固有除外を許さない。
10. 本決定はADR-042でP2として残した契約を補完し、同ADRのidentity、Schema、resource数値、性能SLOを変更しない。
    fail-fast option、並列scheduler、migration mode、自動workspace rename、自動down migrationは追加しない。

## Consequences

- global trust boundaryの失敗を越えず、局所不適合後も無関係な検査とtestを継続できる。
- target不在のDiagnosticが操作ごとに分岐せず、同じedgeへ複数codeを返さない。
- TASKのdirectory prefixがsymlinkの解決先へ暗黙拡張されず、base側だけに存在するpathも検査できる。
- consumerの更新順、結果形式の判別、rollback可能条件が明示され、単一結果と連合結果を誤集約しない。
- hard limitは件数だけでなく、線形な実装構造、peak RSS、期待JSONで受入判定できる。
- Core 1.0実装は適合matrixをすべて通過するまで受入完了にならない。

## Alternatives

1. **workspaceが1つでも非成功ならfail-fastする**: 無関係なmemberの検査証跡を失い、既存の逐次継続方針と矛盾する。
2. **すべて継続して最後に集約する**: 不完全なstrong閉包からContextまたはcommand計画を構成し得る。
3. **TASK prefixをsymlink解決後の実pathへ展開する**: 宣言していない字句pathまで許可集合へ入る。
4. **連合結果を修飾IDの有無で判別する**: 空結果やDiagnosticだけの結果を安定して識別できない。
5. **全targetの完全Contextを同時保持する**: target数と閉包sizeの積でmemoryを消費する。
6. **fixtureごとに期待JSONの除外fieldを選べるようにする**: 実装差を適合として隠せる。

## Notes

- 詳細な優先順位、継続単位、計算量、適合matrixは`docs/03.詳細設計`と実装計画を正本とする。
- 検討経緯とP2対応表は[提案23](../../04.提案資料/23_モノレポ残存P2裁定案.md)に記録する。
- ADR-041のtarget別証跡と明示`--report`だけの保存条件、ADR-042の初回1.0公開前提を維持する。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-03 | モノレポ残存P2の継続、TASK境界、rollback、計算量、適合契約を確定 | FED-CTX-003ほか5件 |
