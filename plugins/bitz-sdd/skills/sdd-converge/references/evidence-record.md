# 規範文と直接証拠の対応

対象は実在するrefと、そこからの変更差分で固定する。実行時のrevision.commit・dirty、workspace、
対象ID、比較基準を原結果から確認する。dirtyならHEADだけでは未コミット内容を識別できない。
修正後に古い結果を流用せず、必要な検査を同じ範囲で取り直す。過去の非成功は履歴として残す。

各MUST規範文に、変更ファイル、実assert、テスト対応のcovers・bindingRefs、実コマンド、
終了結果を対応付ける。Coreが解決する対応と、assertが実際に検査する内容を区別する。
例えばlen(errors)==1は件数の証拠であり、errorsの型、エラー文字列、通常入力、認可の検査を証明しない。
該当する異常・境界・安全の証拠がなければ不足として残し、終了0だけで全要求を実証したと報告しない。

context／check／verifyはJSON全体、終了コード、stderr、取得先と実SHA-256を保持する。
targetResultsのstatus・diagnostics・statements・bindingRefs、commandsの対象とargv・cwd・termination・exitCodeを確認する。
トップレベルpassedでも空のテスト集合、未テストMUST、破損証拠があれば完了としない。
contextDigestが一致しても、コード・テスト本文やコマンド設定の無変更・安全性は保証されない。

前context、前check、書込み直前のdigest照合は実施時の証拠に限る。
記録がなければ不足として返し、現在の成功を過去の実施へ書き換えない。
戻り先を示して必要な工程をやり直すか、人間の判断を待つ。再実行不能な検査も実施済みにしない。

品質計画の必須証拠には取得済みのsource・hash・対象を対応付け、未収集には具体的な理由と担当を残す。
計画は実装前のrefで作られるため、作成元refと検分対象refを区別する。
古い計画が現変更へ適用できるかは起点・差分・リスク・必須条件を直接照合し、対象を黙って書き換えない。
独立レビューにも対象ref、実行ID、継承した情報、直接検査と未再実行の理由が必要である。
証拠の形とhashの一致だけでは十分性や独立性を証明しない。

複合workspaceでは所有者付きIDと各メンバーの結果を残す。要求・コード・テスト・境界を所有者へ対応付け、
メンバーごとのcontext、前後check、verify、人手レビューを一部の成功で集約しない。
横断作業では同じGitのルートでcheck --all-workspaces --base <統合先先端>とverify --all-workspacesの
原結果も必要である。全体contextやcheck --all-workspaces --fullという未提供の操作を作らない。

型付き引渡しは同梱の[形式の参照](../../sdd-implement/references/handoff.md)を使う。
収集済み証拠と不足を別に保持し、人手レビュー未実施をmissingEvidenceとnot-runへ残す。
文書保存の依頼がなければ会話で返す。保存先と権限がある場合にだけ記録を作り、Coreの--reportへ任意パスを渡さない。
