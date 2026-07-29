---
id: FLW-DSN-009
title: "release・CHANGELOG詳細設計"
status: active
version: 1.0
updated: 2026-07-29
owner: hide
implements: FLW-FR-010, FLW-NFR-003, FLW-NFR-004, FLW-NFR-005, FLW-NFR-006, FLW-NFR-007, FLW-CON-002, FLW-CON-004
origin: FLW-DSC-003
---

# FLW-DSN-009 release・CHANGELOG詳細設計

## 基本方針

- CHANGELOGとGitHub Release notesを同じcanonical change setから生成する。
- versionは人間またはproject固有toolが決め、bitz-flowは妥当性だけを検証する。
- release対象をtagとtarget SHAで固定する。
- CHANGELOG変更は通常のworktree + PRで先にlandする。
- release作成はdraftを既定とし、publishを別の承認操作にする。
- action境界は`changelog-apply`、`tag-create`、`tag-push`、`draft`、`publish`に分離する。

## release mode

| mode | 対象 | tag例 | changelog |
|---|---|---|---|
| `repository` | 単一製品repo | `v2.1.0` | root `CHANGELOG.md` |
| `component` | monorepoの1component | `bitz-flow-v2.0.0` | component `CHANGELOG.md` |

本モノリポでは`component`を既定提案とする。component path、tag prefix、manifest versionは
CLI引数または`.bitz-flow.json`で明示する。

## canonical change set

前回release tagからtarget SHAまでのcommit集合をGitで固定し、GitHubのmerged PRを全page取得した上で、
`mergeCommit.oid`が集合に含まれるPRだけをcanonical change setに採用する。OID欠落・重複・pagination
未完了は`INDETERMINATE`としてreleaseを停止する。rebase merge等で一意に対応できないrepositoryは、
allowlist固定endpointによるcommit-associated PR照合を使い、それでも一意でなければ手動証跡を要求する。

change setは次を保持する:

- PR number / title / URL
- mergedAt / merge commit
- labels / author
- closing Issues
- component pathへの変更有無

分類順:

1. `release:skip`は除外
2. `release:breaking`
3. Conventional PR titleの`feat` → Added
4. `fix` → Fixed
5. `refactor/perf` → Changed
6. `docs` → Documentation
7. その他 → Other

同じPRを複数categoryへ重複掲載しない。component modeではPR filesを全page取得し、対象pathに
変更があるPRだけを含める。files取得が省略・上限到達した場合は黙って除外せず`INDETERMINATE`。
共通fileの扱いは設定で明示する。

## changelog

`release changelog`:

- 既存CHANGELOGをparseし、version重複を拒否する。
- `Unreleased`があれば対象versionへ移す。
- date、category、PR link、breaking noteを決定論的にrenderする。
- 既定はstdout preview。`--apply`時だけworktree内の指定pathへ書く。
- applyは同一directory tempへの書込み・parse/digest検証後のatomic replaceを使う。
- 更新後は通常のcommit / PRフローでdefaultへlandする。

## tag

前提:

- changelog commitがtarget SHAから到達可能
- manifest versionが指定versionと一致（検査adapterがあるcomponentのみ）
- working tree clean
- local/remote tag不存在
- target SHAがdefaultから到達可能

annotated tag作成`tag-create`とremote push`tag-push`は別plan。署名はbitz-flowが扱わない。

## release draft / publish

draft前提:

- remote tagが指定targetを指す
- 同tag release不存在
- notesがcanonical change setと一致
- no-commit releaseでない

`gh release create <tag> --draft --verify-tag --notes-file ...`相当を固定引数で実行する。
GitHub側の自動notes生成には依存せず、CHANGELOGと同じrendererを使う。

publish:

- draft release、tag、target SHA、notes digestを再照会
- 外部の明示的人間確認
- publish後のURL、publishedAt、tagを再照会

## Release notes

- summary
- Breaking Changes
- Added / Fixed / Changed / Documentation / Other
- linked Issues
- contributors
- full changelog link

token削減のため通常resultには全文を返さず、file path、digest、項目件数、先頭summaryを返す。

## 非対象

- version bumpの推測実行
- build/test commandの任意実行
- signing key操作
- artifact生成
- package registry publish

これらはproject側release processのevidenceとして受け取り、欠落時はreleaseを`BLOCKED`にできる。

## 診断

`version-mismatch`, `tag-exists`, `tag-missing`, `target-mismatch`, `changelog-missing`,
`duplicate-version`, `no-changes`, `release-exists`, `draft-mismatch`, `evidence-missing`。

## 影響

新規module。M5前半でrepository modeのnotesとdraftまでを実装し、recovery fault injectionと
人間確認契約がgreenになったM5後半でpublishを有効化する。v2完成条件にはpublishを含むが、
前半prereleaseではapplyを`UNSUPPORTED`へ縮退する。component modeはShouldとして後続昇格する。
