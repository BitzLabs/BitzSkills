---
id: ADR-042
title: 複合workspaceの同一性・所有境界・公開契約を確定する
status: accepted
relations:
  requires:
    - ADR-037
    - ADR-041
  related:
    - ADR-039
    - ADR-040
---

# ADR-042 複合workspaceの同一性・所有境界・公開契約を確定する

## Context

ADR-040は複合workspaceをCore 1.0へ再導入したが、実装前の独立reviewで、旧Coreとの互換前提、
workspace同一性、未登録設定の発見範囲、symlinkを含む所有判定、Contextと全体結果の完全Schema、CLIの
処理開始境界、複合workspaceのresource上限、性能測定条件が未確定であることが分かった。

このうち旧Coreとの互換性はrelease事実に依存する。Core 1.0は現在も仕様検討段階であり、複合workspace非対応の
Core 1.0を含め外部へreleaseしていない。したがって、公開済み1.0との互換層を追加するのではなく、初回公開する
1.0契約を完全にする必要がある。

また、filesystem全体の暗黙再帰探索はADR-040の明示catalog方針に反するが、Gitが既に認識する設定さえ比較しなければ
`--all-workspaces`が複合workspaceの完全検査を表明できない。字句pathだけの所有判定では、root workspaceからmember内へ入る
symlinkも防げない。

## Decision

1. `workspace`と`monorepo`は未releaseの初回Core 1.0 Schemaへ含める。Schema major、必須feature marker、
   旧1.0向け移行猶予は追加しない。`monorepo.v1`はadapterのCapability確認に使うが、旧版拒否用gateとはしない。
2. workspace IDを複合workspace内の永続同一性とし、Core 1.0ではrenameを対応しない。base/current catalogで同じIDを持つ
   member path移動は同一workspaceとして扱い、ID変更は旧workspace削除と新workspace追加として扱う。初回複合workspace化時だけ、
   repository rootの同じ`.spec`にある暗黙ID `root`をcurrentの明示root workspace IDへGit比較上で一方向写像する。
3. 複合workspace化はroot catalog、全member設定、横断参照、CI、JSON consumerを同じ変更集合で切り替える。不完全catalogを
   warningで許すmigration modeは追加しない。member削除にはbase側の管理済みSPEC削除検査を適用する。
4. `check`、`verify`、`doctor`の`--all-workspaces`は、操作が使う各snapshotでGitが認識する`.spec/bitz.yaml`候補を、
   そのsnapshotが複合workspaceを宣言する場合だけ同snapshotのcatalogと事前検査で比較する。現在snapshotはworking treeに
   存在するtracked／staged pathと未追跡かつ非ignore pathを対象とし、ignored path、submodule内部、別repositoryを
   暗黙参加させない。集合差は`SPEC-MONOREPO-UNREGISTERED-001`／`blocked`とする。
5. member pathと全所有pathは同じcanonicalizerを使う。字句検査後、存在するancestorのsymlinkを解決し、Git metadataと
   実pathのpath-segment包含でrepository、workspace、member、`.spec`境界を照合する。workspace設定経路とmember rootの
   symlinkは禁止し、code、test、TASK、cwdは同じ所有領域内へ解決するsymlinkだけを許す。
6. 複合workspaceのContextは`documents[].workspaceId`、`resolution.workspaces[]`、
   `resolution.crossWorkspaceEdges[]`を必須とする。Digestへは到達workspaceで実際に使ったSchema、EARS-AI、language、
   request workspaceのContext上限、収録bindingのtimeout／command定義だけを許可リストで含める。
7. `--all-workspaces`はcurrent directoryの一致ではなく、同じGit rootとroot workspaceを一意に発見できることを
   許可条件とする。未知`--workspace`はinvocation error、終了コード4、結果・reportなしとする。check／verifyの
   `revision`は最上位に1件だけ置き、操作別member fieldを必須化する。root同一性を構成できない成果物不適合の
   全体結果だけは`federation.id: null`を許し、同じ同一性確定前の設定Diagnosticだけ
   `source.workspaceId: null`を許す。
8. 複合workspaceのsnapshotのhard limitをmember 100、SPEC 10,000件、入力256 MiB、規範文100,000件、relation edge 1,000,000件、
   trace entry 1,000,000件、command定義10,000件、1 verify計画のbinding 10,000件とする。超過は
   `SPEC-MONOREPO-LIMIT-001`／`blocked`とし、dimensionとlimitをDiagnosticへ記録する。
9. 性能回帰gateは20 workspace、SPEC 1,000件、relation 20,000件のversion管理fixtureで測定する。Core cacheに
   依存せず、暖機1回後の5回中央値で`check --all-workspaces` 30秒以内、3 workspaceへ到達する20文書Context 1秒以内、
   Core peak RSS増分200 MiB以内を基準環境で確認する。10,000 SPECは性能SLOではなくhard-limit fixtureとする。
10. 本決定はADR-040 Decision 1、3、5、7の未確定境界を補完する。Decision 4の「root workspaceで」という
    current directoryにも読める条件をGit／複合workspaceの探索条件へ、Decision 8のSPEC件数だけのresource契約を
    Decision 8の方針を維持した数値表へ置き換える部分改訂とする。ADR-040の他のDecisionとscopeは変更しない。

## Consequences

- 初回Core 1.0に旧1.0互換分岐を持ち込まず、複合workspaceを含む1つのSchemaとして公開できる。
- workspace ID変更は高コストだが、Git差分、修飾ID、Digest、結果同一性を推測なしで対応付けられる。
- filesystem全体の任意探索をせず、Git既知の未登録設定とsymlinkによる所有迂回をfail-closedにできる。
- adapterはContextと全体結果の必須field、空配列、順序、null条件を実装前に固定できる。
- resource上限と性能目標が分離され、巨大入力の安全停止と通常規模の回帰を別fixtureで検証できる。
- P2として残る失敗後継続、Diagnostic優先順位、TASK directory境界、consumer rollback、計算量、適合matrixは、
  本決定のSchemaを前提に独立裁定できる。

## Alternatives

1. **旧1.0互換用にSchema majorまたはfeature markerを追加する**: 外部releaseがなく互換対象が存在しないため、
   初回1.0へ不要な分岐を持ち込む。
2. **workspace ID renameを自動推定する**: path移動、削除、再作成を意味的に区別できず、管理済みSPEC削除検査を
   fail-openにする。
3. **未登録`.spec`をfilesystem全体から再帰探索する**: ignored生成物、vendor、submoduleを信頼境界へ取り込み、
   明示catalogの入力範囲を壊す。
4. **所有境界を字句pathだけで判定する**: symlinkやcase-insensitive filesystemで別memberの実体を所有できる。
5. **設定全体をContext Digestへ含める**: 未使用commandやmember列挙順の変更でも無関係なContextをstaleにする。
6. **10,000 SPECへ30秒SLOを課す**: 安全上限と通常運用目標を混同し、基準複合workspace1,000 SPECという既存品質予算と
   整合しない。

## Notes

- 詳細なSchema、canonicalization、resource計数は`docs/03.詳細設計`を正本とする。
- 検討経緯とP1対応表は[提案22](../../04.提案資料/22_複合workspace残存P1裁定案.md)に記録する。
- ADR-041のtarget別verify証跡と明示`--report`だけの保存条件は変更しない。
- 本ADRでP2として残した継続、Diagnostic、TASK境界、rollback、計算量、適合matrixは
  [ADR-043](ADR-043_複合workspaceの継続・TASK境界・適合契約を確定する.md)で確定した。
- 結果field `federation`、設定key `monorepo`、`SPEC-MONOREPO-*`は、後続の[ADR-047](ADR-047_複合workspaceの識別子をmultiWorkspaceへ改名する.md)で`multiWorkspace`、`SPEC-MULTI-*`へ改名した。

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-09-03 | 複合workspace残存P1の同一性、所有境界、Schema、CLI、resource、性能条件を確定 | FED-CROSS-002〜007 |
| 2026-09-03 | 本ADRで残したP2の後続裁定を記録 | ADR-043 |
| 2026-09-17 | 複合workspaceの識別子の改名を後続決定へ接続 | ADR-047 |
