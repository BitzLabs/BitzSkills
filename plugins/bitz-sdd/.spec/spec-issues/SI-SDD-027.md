---
id: SI-SDD-027
raised_by: 2026-07-27 PR #107/#108（無記録promotion事故）後のユーザー指示による再検討
target: spec_update.py 人間裁定必須遷移への代行可視化経路（on-behalf-of）の追加 — SDD-DSN-005 却下判断の再評価
proposed_change_type: modify
status: accepted
origin: BitzSkills root（26件無記録promotion事故と、SI-SDD-022 案3の再評価指示）
---
- **優先度（推薦）**: **高**。SDD-FR-143 の強制が実運用コスト（1実行1ID × TTY × 完全一致再入力）に
  対して過大であることが、リリース当日の迂回事故（PR #107: 26件の frontmatter 手編集による
  promotion → #108 で revert）で実証された。正直な経路の不在が無記録経路を誘発する構造は、
  SI-SDD-026（事後検出）だけでは解消しない。
- **目的**: SDD-DSN-005 は SI-SDD-022 案3（代行の可視化）を「検証不能な自由記述 authorization
  reference は自己申告能力になる」として却下し、人間裁定必須遷移の唯一の CLI 経路を TTY 対話確認に
  限定した。この却下判断を、事故の実績を踏まえて再評価する。
  - **却下論理の再検証（1）比較対象の誤り**: 設計時の比較は「代行 vs 人間の直接 TTY 実行」だったが、
    実運用で発生した比較は「正直に記録された代行 vs 無記録の手編集」だった。後者は STATE に
    表示行も構造化 event も残さず、`spec inspect` / `release_check.py` の全ゲートを PASS して
    main へマージされた（SI-SDD-026 起票の根拠事故）。
  - **却下論理の再検証（2）保証水準の一貫性**: 「検証不能」を却下理由とするなら、TTY 確認自体も
    本人認証ではない（SDD-DSN-005 自身が「エージェントも PTY を確保できる」と明記）。脅威モデルは
    repository 書込み権限者を信頼済みで、改ざん耐性は当初から主張していない。ゲートの実価値は
    「証跡の正直さ」と「エージェント単独実行への摩擦」であり、可視化された代行経路はこの両方と
    両立し得る。
  - **却下論理の正しい核（維持する）**: 無条件の `--on-behalf-of` はエージェントの自己申告能力に
    なり、2026-07-21 の `--by-human` 事故（口頭指示を根拠にエージェントが人間専用遷移を自ら実行）の
    再来となる。したがって代行経路には**人間裁定の所在を指す参照（decision-ref）を必須**とする。
- **提案する修正**（設計論点。Design Gate で裁定）:
  1. `spec update` に `--on-behalf-of <human> --decision-ref <参照>` を追加する。provenance kind は
     `agent-proxy-unverified`（構造化 event schema へ加算）。STATE 表示行は
     「代行実行（裁定参照: X・実行者未検証）」等とし、TTY 経路（対話入力確認済み）と明確に区別する。
  2. decision-ref の要求水準: 参照先の**実在**（spec-issue の実施マーカー、`gates.md` 裁定記録、
     PR URL、STATE 行等）を `spec inspect` が検査する。参照の**真正性**（その裁定が本当に当該遷移を
     許可したか）は機械検証せず、残余リスクとして SDD-FR-143 後継節・CLI help・STATE 表示に明記する。
  3. バッチ遷移: 1 decision-ref × 複数 ID の一括遷移を代行経路で許可するか。26件事故の直接原因は
     バッチ経路の不在であり、キャンペーン型運用（一括 approved 化・一括 promoted 化）の実態に合わせる。
  4. 適用範囲: 全人間裁定必須遷移に開くか、一部（`verified→promoted` 等のキャンペーン系）に
     限定して `draft→approved` / `open→accepted` は TTY 限定を維持するか。
  5. 抑止・可視化: `spec_status.py` / `sdd_report.py` で proxy 比率を集計し、Promotion Gate
     チェックリストに proxy 遷移の人間再確認を追加する。
  6. TTY 経路（`--interactive-decision`）は第一級経路として維持し、廃止しない。
- **対象ファイル**: `plugins/bitz-sdd/skills/sdd-core/scripts/spec_update.py`、
  `spec_inspect.py`（decision-ref 実在検査・event schema 検査の拡張）、
  `references/lifecycle.md`（権限マトリクス・記録語彙）、
  `.spec/requirements/SDD-FR-143.md`（bump または supersede）、
  `.spec/design/SDD-DSN-005.md`（設計判断の改訂）、
  `tests/test_spec_update.py`・`tests/test_spec_inspect.py`、bitz-sdd の3マニフェスト。
- **確認観点**:
  - SDD-FR-143 の既存 EARS 節（TTY と完全一致再入力を要求し「条件を満たさない場合は
    `authorization-required` で終了」）は代行経路の追加で**意味が変わる**。bump で足りるか
    supersede が必要かを裁定する（SI-SDD-026 と同種の判断であり、両方が同一要件へ入るため
    実施順序も裁定する）。
  - SDD-DSN-005 の Design Gate 裁定点2（「検証可能な host receipt が無い代行経路は設けない」）を
    明示的に覆すため、**Design Gate の再裁定が必須**。軽量レーン不可。
  - 憲法4「仕様の変更権は常に人間が持つ」との整合: 裁定（決定）と執行（コマンド実行）を分離し、
    代行が担うのは執行のみ。decision-ref が裁定の所在を要求することで裁定権は人間に残る、という
    整理が成立しているか。
  - 代行がデフォルト化して TTY 経路が形骸化するリスクの許容可否（proxy 比率の可視化で足りるか）。
  - event schema version の扱い（provenance kind の追加は schema version 1 のまま加算できるか）。
  - SI-SDD-026（CLI 迂回の事後検出）との関係: 入口（正直な代行経路）と出口（迂回検出）で相補。
    本経路の導入で event ゼロ artifact が減り、026 の baseline 検査の実効性も上がる。
- **影響推定・ロールバック**: 加算 CLI のため既存の TTY 経路・エージェント許容遷移は不変
  （semver は CLI 加算なら minor、SDD-FR-143 既存節の意味変更を伴う場合は major を検討）。
  `.spec/` のデータ移行は不要。ロールバックは代行経路の revert で戻り、STATE に残った
  `agent-proxy-unverified` event は legacy として読取保持する（遡及変更しない）。
- **依存**: SDD-FR-143（bump/supersede 対象）、SDD-DSN-005（改訂対象）、
  SI-SDD-026（同一要件への変更が競合するため順序調整）、`references/lifecycle.md`。
- **予備判定（推薦）**: **accept 推薦（条件付き）**。根拠:
  - 実証: 正直な代行経路の不在が、最悪の経路（無記録の手編集・検出不能）へ運用を押し出した実績がある。
  - 保証水準の一貫性: TTY 確認は本人認証ではなく（SDD-DSN-005 自認）、decision-ref 付き代行は
    ゲートの実価値（証跡の正直さ・単独実行への摩擦）を毀損しない。
  - 条件: decision-ref の要求水準・適用範囲・バッチ可否の設計裁定が前提。無条件の
    `--on-behalf-of` は 2026-07-21 事故の再来となるため不可。
  - 軽量レーン適否: **不可**。公開 CLI・監査契約・Design Gate 済み設計判断の変更に触れる。
