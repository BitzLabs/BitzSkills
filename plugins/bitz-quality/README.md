# bitz-quality 0.1.1

BitzSkills 2系の品質計画と独立レビューの試作版。
`skills/quality-plan/SKILL.md`は変更リスクと必要な証拠を計画し、
`skills/quality-review/SKILL.md`は一次資料を独立検分して受入れの助言を返す。
モデル行動、発火、保持ケース、Skill Gate、配布は未認定である。

Coreの合否、要求承認、TASK完了、出荷許可は変更しない。品質の助言はadvisoryとして記録する。
計画はコードや試験を実行せず、文書保存も依頼がある場合だけ行う。
独立レビューは別の文脈・一次差分・実証拠と安全な再実行を必要とする。
既知の重大事項はnot_ready、重大事項が未確認でも必須証拠または独立性が欠ければunknownとする。

CPython 3.12以上、Linux/macOS、bitz-core 1.0.0の公開CLIが必要。
JSON Schemaのローカル検査には既存のjsonschemaライブラリを使う。Core内部APIや1系スクリプトは利用しない。
計画/レビューの形式はschemas/、未実証の例はexamples/へ置く。形式検査はリスク判断の正しさを証明しない。
scripts/validate_quality.pyは形式と申告された事実の整合性だけを検査する。
参照先の実在、hashと実内容の一致、所見の真偽、独立文脈の実成立は別に直接検分する。
出力のvalidは品質の合格ではなく、certifiesQuality=falseを常に返す。
Core取得は共通の[観測形式](schemas/core-observation.schema.json)へ、argv・cwd・対象ref・取得先とhash・rawResult・stderrを保存する。
rawResultは元JSONを削らず保持し、対象・完全解決・digest・警告を含む。exit 4はstatus/rawResultともnullで、Coreのerrorへ変換しない。
current_gateは今回の判定用、historicalは過去参照、expected_negativeは意図した不適合の試験結果で、roleReasonへ適用根拠を残す。
現在のfailedはnot_ready、blocked/error/引数不正・不完全/dirtyなcontext・現在のcontext/check不足はunknownとする。既知重大事項は優先する。
過去・期待した不適合は現在の通過証拠に代用しない。分類の真実性と元JSONの適合性は一次資料で別に検分する。
計画のnotRunとレビューのnotRerunは証拠IDと取得可否を保持し、未取得をcollectedEvidenceへ載せない。
再実行しなくても取得済み一次結果を直接検分できる場合は、根拠を記録して必須証拠の十分性を判断する。
SDDの確定変更の入力は既存のevals/skills/schemas/handoff.schema.jsonを使い、そのフィールドを拡張しない。
品質計画は別文書で、独立レビュー結果や取得済み証拠として渡さない。

正本はADR-060、品質属性と安全境界、SDDフロー、提案30の品質管理と公開引渡し契約。

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<worktree絶対パス>/plugins/bitz-core/src:<ruamel.yaml-0.19.1のパス> \
  python3 -B tests/skills/test_quality_contracts.py
```

検査は合成workspaceの公開CLIを読取り実行し、偽のready、証拠不足、未成立の独立性、重大事項の相殺を拒否する。
製品の実証、モデル評価、総合品質の認定とは別の検査である。
