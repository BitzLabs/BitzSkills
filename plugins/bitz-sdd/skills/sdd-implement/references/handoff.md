# 証拠と不足の引渡し

小変更の会話でも、起点・所有者、フロー、リスクの帯・観点・理由、変更パス、
実行したCore操作・元status・終了コード、テストと差分、レビュー、不足証拠を区別して返す。
型付き記録が必要なら、BitzSkills 2系の公開 `evals/skills/schemas/handoff.schema.json` に従う。
Schemaの通過は形の整合性であり、証拠の実在・十分性・readyを証明しない。

## 公開形式

| 項目 | 記録する事実 |
|---|---|
| schemaVersion | 1.0 |
| subjectCommit | 実在する検分対象の確定commit、40桁のhex |
| originIds | 起点ID。複合では所有者付きID |
| changedPaths | リポジトリ相対の安全な変更パス、重複なし |
| risk | band Q0〜Q3、dimensions、rationale |
| requiredEvidence／collectedEvidence | 実在する証拠のevidenceId・kind・source・SHA-256 |
| missingEvidence | 未収集・未作成・未実施のevidenceIdと理由 |
| checks | name・command（配列またはnull）・result |

risk.dimensionsはsecurity、privacy、reliability、compatibility、performance、supply-chain、
operations、maintainabilityから該当するものを使う。
証拠kindはcore-result、test-result、diff、review、benchmark、provenance。
checks.resultはpassed、failed、blocked、not-runで、元Coreのpassed_with_warningsやerrorを直接入れない。
通過はpassedへ対応させつつ警告を残し、非成功は事実に合わせた項目と理由を記す。
必ず元Core JSONを証拠として保存し、そのSHA-256と参照先を残して元statusを保持する。

未作成の証拠へ架空のsourceやhashを入れない。未収集の必要証拠はmissingEvidenceへ記し、
実在する予定・既存証拠だけを証拠行として扱う。空のchecksや欠落を通過と解釈しない。
Q2／Q3の品質計画と必須証拠は実装前に決め、未達分を隠さない。

## 対象とレビューの固定

汚れたツリーのHEADを、新しい変更を含むsubjectCommitとして扱わない。
許可されたコミット等で検分対象を確定できない場合は、現在の差分と実証を返し、正式な記録は対象ref確定待ちとする。
型を満たすためだけに無許可コミットを行わず、結果のrevision.commit・dirtyと実行対象を保存する。
確定refの記録にはそのrefで測った差分・証拠を結び付け、変更後に古い実証を黙って流用しない。

人手レビュー未実施はmissingEvidenceとchecksのnot-runに残し、TASKはopenを維持する。
Coreの通過、Schemaの通過、レビュー実施、SDDフロー完了、総合的な品質・出荷判断を区別する。
引渡しは後続レビューの入力であり、readyやリリース許可の自動決定ではない。
