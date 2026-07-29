---
id: FLW-DSN-004
title: "bitz-flow v2 アーキテクチャ"
status: active
version: 1.1
updated: 2026-07-29
owner: hide
implements: FLW-FR-003, FLW-NFR-003, FLW-NFR-004, FLW-NFR-005, FLW-NFR-006, FLW-NFR-007, FLW-CON-001, FLW-CON-002, FLW-CON-003, FLW-CON-004
origin: FLW-DSC-001
---

# FLW-DSN-004 bitz-flow v2 アーキテクチャ

## 3ビュー

### 論理ビュー

```text
Agent
  → flow-core/SKILL.md
  → flow.py (single public dispatcher)
      → CLI parser
      → application service
      → policy / state machine
      → Git or GitHub adapter
      → process runner / atomic file I/O
  ← Result object
  ← compact / JSON renderer
```

### 実装ビュー

```text
flow-core/
├── SKILL.md
├── schemas/
│   ├── result-v1.schema.json
│   └── operations/
├── references/
│   ├── operation-catalog.md
│   ├── output-contract.md
│   ├── safety-policy.md
│   ├── worktree-workflow.md
│   ├── issue-sdd-linkage.md
│   ├── pr-workflow.md
│   └── release-workflow.md
└── scripts/
    ├── flow.py
    └── flowlib/
        ├── cli.py
        ├── result.py
        ├── process.py
        ├── policy.py
        ├── git_read.py
        ├── git_write.py
        ├── github_read.py
        ├── github_write.py
        ├── github_fixed_api.py
        ├── worktree.py
        ├── issue.py
        ├── pull_request.py
        └── release.py

flow-doctor/
├── SKILL.md
└── scripts/flow_doctor.py
```

`flow.py`だけがpublic executable。`flowlib`を直接呼ぶことは公開契約外とする。
`flow-doctor`はフォルダ単体コピーを守るためflow-coreをimportせず、読み取り専用の小さな
scriptとして自己完結させる。result schemaの共通部分はgolden testで一致を強制する。
operation別schemaは`schemas/operations/`を正とし、M0でread-only 3操作から固定する。

### 実行ビュー

1. CLIがinputをcanonical化する。
2. adapterがmachine-readable optionで事実を取得する。
3. policyがplanと必要承認を決定する。
4. rendererが許可リスト結果を返す。
5. apply時は同じ事実を再取得し、operation IDを照合する。
6. 副作用途中で失敗した場合は、確定済みなら`PARTIAL`、成否不明なら`INDETERMINATE`を返す。
7. 再実行は内部journalではなくGit / GitHubのmarker、digest、ref、SHA、URLから再開点を再構成する。

## 依存方向

```text
cli → application services → domain policies → adapters → process runner
renderer ← result object
```

- policyは`subprocess`を直接呼ばない。
- parserは状態変更を行わない。
- rendererはraw outputへアクセスしない。
- GitHub adapterは固定した`gh` subcommandと`--json` fieldを優先する。
- 高水準commandで不足するMust capabilityだけ、source codeにmethod/path/fieldを列挙した
  `github_fixed_api.py`を使う。利用者入力のendpointやGraphQL documentは受け取らない。
- 任意shell文字列を構築せず、全コマンドをargument arrayで実行する。

## 設定

初期版はzero-configを成立させる。反復設定が必要な場合だけrepo rootの
`.bitz-flow.json`を読み取る。未知keyはwarning、型不正は`INVALID_INPUT`。

候補key:

```json
{
  "schema": "bitz-flow/config/v1",
  "default_branch": "main",
  "worktree_root": "../.worktrees",
  "changelog": {"mode": "component", "path": "CHANGELOG.md"},
  "github": {"project_owner": null, "project_number": null}
}
```

scriptは初期版で設定ファイルを自動作成・変更しない。worktree pathにはrepo名だけでなく、
canonical Git common-dirまたはremote identityから得る短いrepo identity hashを含める。

## Security / failure boundary

- subprocessはshellを使わずtimeoutを必須化する。
- stdout/stderrはoperation別byte上限までmemory上でparse後に破棄し、resultへ転記しない。
- credential関連commandは存在・scopeの判定だけを返す。
- repo root、worktree root、pathspec、refを副作用前にcanonical検証する。
- network operationとlocal operationを別stageにし、どちらが失敗したかcauseで示す。
- timeout後はprocess groupを収束させ、必ずpostconditionを再照会する。
- writeはFLW-DSN-012のper-target `concurrency_key`で直列化し、証明できないcross-host競合は
  single coordinator前提または`UNSUPPORTED`へ縮退する。
- 永続fileは同一directory tempへの書込みと検証後のatomic replaceで更新する。
- process、recovery、file I/Oの詳細はFLW-DSN-013を正とする。

## 技術判断

- Python 3.10+標準ライブラリのみ。Go実装、部分置換、再実装、移行比較は行わない。
- Pythonで必須のprocess tree収束、locking、atomic I/O、配布一貫性を成立させられない場合は、
  対象operationを縮小するかv2をNo-Goとし、別言語への移行でDesign Gateを迂回しない。
- 内部永続DB・journalなし。
- Git machine-readable output、`gh --json`、allowlist固定endpointのJSONだけをparse入力にする。
- 設計条件で除外された実装方式をarchitecture optionとして残さない。

## ロールバック

M0〜M5のmodule境界ごとにrevert可能。result schemaとread-only thin sliceはM0で先にlandし、
後続moduleは公開fieldの意味を変更せず加算する。M0の正はFLW-DSN-014、規範切替は
FLW-DSN-011に従う。
