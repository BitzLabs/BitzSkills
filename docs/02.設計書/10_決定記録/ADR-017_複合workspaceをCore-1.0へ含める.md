---
id: ADR-017
title: 複合workspaceをCore 1.0へ含める
status: superseded
---

# ADR-017 複合workspaceをCore 1.0へ含める

## Context

Webフロントエンド、バックエンド、ネイティブlibraryなどを1つのGit repositoryで管理する場合、単一の
`.spec/`へ全要求、検証command、所有境界を集約すると、ID衝突、Context肥大化、変更影響の過大評価を招く。
一方、各プロジェクトを完全に独立したworkspaceとして扱うだけでは、公開APIや共通要求の横断依存を
決定論的に解決できない。

## Decision

### 1. 複合workspaceモデル

Core 1.0は、1つのGit repository内にある複数のSPEC workspaceを、明示的な複合workspaceとして扱う。
Git rootの`.spec/bitz.yaml`を複合workspace root兼共通workspaceとし、`monorepo.members`へ参加memberを
`id`とrepository root相対`path`で列挙する。各memberは自身の`.spec/bitz.yaml`を持ち、同じ
`workspace.id`を宣言する。

```text
repository/
├── .spec/                       # 連合ルート・共通要求
│   └── bitz.yaml
├── apps/web/
│   └── .spec/bitz.yaml          # webワークスペース
├── services/api/
│   └── .spec/bitz.yaml          # apiワークスペース
└── libs/native/
    └── .spec/bitz.yaml          # nativeワークスペース
```

暗黙の再帰探索、globによる参加、Git submoduleまたは別Git repositoryの横断は行わない。

### 2. 識別子と参照

文書IDはworkspace内で一意とし、複合workspace内の正規参照は`<workspace-id>::<document-id>`、規範文は
`<workspace-id>::<document-id>:<local-id>`とする。同一workspace内では従来の非修飾IDを許可する。
別workspaceへの関係、CLI起点、結果JSONでは修飾IDを使用し、探索順による暗黙解決を禁止する。

### 3. 所有境界

member workspaceの`implements`、`tests[].path`、TASK `changes`、検証`cwd`は、そのmemberの
directory配下へ限定する。複合workspace rootは、明示されたmember配下のcodeを直接所有しない。横断要求は
member側TECHまたはREQから共通REQ/ADRへの`refines`または`requires`で分解し、実装・test対応は
各所有workspaceへ置く。

member path同士の重複と入れ子を禁止する。これにより、1つのcode pathを複数workspaceが暗黙に
所有する状態を作らない。

### 4. 操作範囲

- 通常操作は、指定pathから最も近い`.spec/bitz.yaml`をactive workspaceとする。
- `context`は起点から到達する修飾済みの強い依存だけをworkspace境界越しに解決する。
- `check --all-workspaces`は複合workspace catalog、全workspace、横断関係を検査する。
- `verify --all-workspaces`はworkspaceごとにcommandを解決・実行し、結果を集約する。異なる設定の
  commandを1実行へ混合しない。
- `doctor --all-workspaces`は複合workspace構造、版互換性、ID、path所有、検証環境を読取り専用で診断する。

全体操作は決定論的なworkspace ID順で処理する。Core 1.0では並列実行を必須にしない。

### 5. 設定と上限

設定は継承しない。各workspaceは自身の`bitz.yaml`だけを正本とする。横断Contextには起点
workspaceのContext上限を適用し、Core hard limitを超えた部分bundleを成功扱いしない。
SPEC file 10,000件の上限はworkspaceごとではなく、複合workspace全体へ適用する。

Core 1.0では複合workspace memberの既定上限を20、hard limitを100とする。異なるEARS-AIまたはSchemaの未知major、
重複workspace ID、未登録workspace、catalogとmember宣言の不一致は`blocked`または`failed`とする。

## Consequences

- 各プロジェクトは自己完結したSPEC、設定、test commandを維持できる。
- 共通要求とプロジェクト固有実装を、修飾IDにより決定論的に追跡できる。
- LLMへ渡すContextは依存閉包に限定され、monorepo全体の投入を避けられる。
- 全体検査の索引作成と構成検証がCore 1.0の実装・性能試験へ追加される。
- Gitを越えるマルチリポジトリ複合workspaceはCore 1.0の対象外として残る。

## Alternatives

### 単一の巨大な`.spec/`

導入は単純だが、設定、ID、test command、所有境界が集中し、プロジェクト単位の独立性を失う。

### Git配下の`.spec/`を暗黙に全探索する

vendor、fixture、submodule内の意図しない設定を取り込み、入力増幅と信頼境界の曖昧化を招く。

### 複合workspace内で文書IDをグローバル一意にする

既存プロジェクトの統合時に大規模なID変更が必要になる。workspace修飾で衝突を解決する方が移行しやすい。

### root設定をmemberへ継承する

実効設定の出所が複雑になり、安全設定や検証commandが暗黙に変化する。明示的な各workspace設定を優先する。

## Notes

関連文書: [02_spec directory仕様.md](../02_specディレクトリ仕様.md), [03_CLI統合設計.md](../03_CLI統合設計.md), [06_運用設計.md](../06_運用設計.md), [08_実装ロードマップ.md](../08_実装ロードマップ.md), [SPEC複合workspace仕様](../../03.詳細設計/02_SPECファイル規定/12_モノレポSPEC連合仕様.md)

## Revision History

| Date | Summary | Reference |
|---|---|---|
| 2026-08-27 | 初版を作成 | — |
| 2026-08-31 | Frontmatterと固定H2構成へ移行 | `ADR-020` |
| 2026-09-01 | 複合workspaceをCore 1.0から延期 | `ADR-039` |
