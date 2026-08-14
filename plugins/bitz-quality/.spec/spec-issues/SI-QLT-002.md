---
id: SI-QLT-002
raised_by: PR #270再レビュー
target: bitz-qualityレビュー契約（V4 profile、公開schema、障害・移行・qualification）
proposed_change_type: modify
status: accepted
origin: SI-QLT-001
---
- **目的**: Design Gate後の再レビューで検出した契約の未確定・障害時の不整合を解消し、
  bitz-sdd V4レビュー要件を実装可能なprofileとschemaへ固定する。
- **提案する修正**:
  1. `quality-review/sdd-v4@1` profileを追加し、System Engineering Review、measurability、
     V4の品質閾値・No-Go条件をversion付きで定義する。V4未裁定値は`contract pending`として分離する。
  2. CLI、exit code、schemaの型・必須性・enum・cardinality、project overrideの配置を確定する。
  3. timeoutの必須/任意Reviewer判定、single current pointer、attempt fencing、read-only snapshot、
     raw log default-denyをEARS要件へ追加する。
  4. qualificationの最低trial数・失効・再認定、移行のdual-read・rollback rehearsal・復旧bundleを定義する。
  5. `sdd-review`のdeprecation/removalはbitz-sdd側のDesign/Promotion Gateを必須とし、
     quality単独で削除を裁定しない。
- **対象ファイル**: `plugins/bitz-quality/.spec/requirements/`、`.spec/design/`、`.spec/discovery/`、
  `.spec/reviews/`、`.spec/ROADMAP.md`。必要に応じてbitz-sdd側へ委託spec-issueを起票する。
- **確認観点**: V4 profileの閾値と必須観点、schema validatorの閉集合、consumerのstatus写像、
  generation fencing、crash injection、snapshot escape、raw log redaction、qualification失効、
  dual-read/rollback、SDD/FlowのSSOT境界。
- **影響推定・ロールバック**: approved要件とactive設計に関わるため通常フローと再Design Gateを必須とする。
  既存`QLT-FR-017〜026`の意味を保ちながら補足要件を追加し、quality実装は未確定契約が解消されるまで開始しない。
  問題時は追加成果物とprofileをrevertし、現行`sdd-review`を正として維持する。
- **依存**: `QLT-GATE-001`、`QLT-REV-003`、bitz-sdd V4 Charter/API確定、bitz-flow V2 Promotion Gate。
- **推薦**: **accept**。公開契約・障害安全性・移管境界に関わるため、修正後に5観点再レビューとDesign Gate補足裁定を行う。

本issueは`SI-QLT-001`から委託された補足修正であり、`SI-QLT-002`として再レビューと補足Design Gateを追跡する。
