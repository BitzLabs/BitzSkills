---
id: ADR-041
title: verify対象別証跡とreport明示保存の分離
status: accepted
relations:
  related:
    - ADR-019
    - ADR-026
    - ADR-039
    - ADR-040
---

# ADR-041 verify対象別証跡とreport明示保存の分離

## Context

モノレポ連合を再導入した結果、引数なしverifyと複数対象verifyは複数のContextを解決する一方、結果Schemaは
top-levelに`contextDigest`を1つしか持たず、target、Context、statement、binding、command結果の対応を
証明できなくなった。

また、従来の`check`と`verify`は非成功時に日時付きreportを自動保存した。並行PRやworktreeの検査で生成reportが
差分や残留fileになる既存事例を再確認し、Git除外は書込み副作用そのものを解消しないと判断した。結果の生成、
標準出力、永続化を分離する必要がある。

## Decision

1. `verify`は正規化したtargetごとに`purpose=verify` Contextを解決し、`targetResults[]`を検証証跡の正本とする。
   各要素は`target`、`status`、`contextDigest`、`statements[]`、`bindingRefs[]`、`diagnostics[]`を持つ。
2. verify結果のtop-level `targets[]`、`contextDigest`、`statements[]`を廃止する。公開hashの種類はContext Digestだけを
   維持し、targetごとの`contextDigest`へ配置する。
3. binding IDは単一workspaceを含め`<workspace-id>::<command-name>`に統一する。`commands[]`は`bindingId`と
   `workspaceId`を持ち、同じbindingを要求する複数targetから参照して1回だけ実行する。
4. Context解決またはcoverageが非成功のtargetだけが要求するbindingは実行計画へ入れない。別の通過targetも同じ
   bindingを要求する場合だけ実行し、command結果を通過targetへ反映する。元の非成功statusは上書きしない。
5. `check`と`verify`は、statusにかかわらず`--report`が指定された場合だけ`.spec/reports/`へ結果を書き出す。
   `--report`がなければ標準出力と終了コードだけを返し、既存reportの変更も新規作成もしない。
6. `--all-workspaces`もDecision 5と同じであり、明示保存先だけをfederation rootとする。memberごとのreportを
   複製しない。`.spec/reports/`のGit管理外指定は防御として維持するが、自動保存の根拠にしない。
7. target statusはContext、coverage、参照bindingの最悪値、workspace／top-level statusはtarget、所有command、
   Diagnosticの最悪値とする。command実体と所要時間をrequest側へ複製しない。

## Consequences

- 複数targetが異なるContext Digestを持っても、各targetのverified述語とstale判定が成立する。
- 共有bindingを1回だけ実行しつつ、どのtargetがどの結果を根拠にしたかを機械追跡できる。
- `check`は既定でfile system上も読取り専用となり、失敗したCI、並行PR、worktreeにreportを残さない。
- 障害結果を永続化したい利用者とCIは`--report`を明示する。`--format json`は保存せず同じ構造化結果を返す。
- Core 1.0は未リリースであるため、旧結果Schemaとの移行fieldと非推奨期間を設けない。

## Alternatives

1. **全targetを1つのmulti-root Contextへまとめる**: 引数なし実行と全workspace実行では非成功targetを独立継続するため、
   結局複数Contextになり解決しない。
2. **`contexts[]`を別表にして参照する**: Digest自体が一意な参照値であり、Core 1.0には正規化が過剰である。
3. **非成功reportの自動保存を維持してGit除外だけ行う**: Git差分は隠せるが、file蓄積、書込み権限、並行実行の
   副作用を解消しない。
4. **CI専用`--check-only`を追加する**: 既に`--report`が明示optionなので、既定を非書込みにすれば別optionは不要である。

## Notes

- 現行契約は`docs/03.詳細設計`のverify仕様と共通結果契約を正とする。
- 2026-09-02のP0レビュー`FED-VER-001`と、独立履歴branchで確認したread-only検査の運用知見を裁定した。
- 運用知見の参照元は`origin/design/flw-tsk-106-safety-boundary`から到達可能なcommit
  `f2b7db6905b1dc38ba75b8f0b44ce93d100c7c33`である。`--check-only`時の既存report不変、非生成、失敗時非書込み、
  複数workspace非書込みをfixture化していた。
- ADR-039 Decision 9の公開hash種別とDecision 10のcommand名bindingは変更しない。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-02 | target別verify証跡と明示report保存を採用 | FED-CROSS-001 |
