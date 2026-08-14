#!/usr/bin/env python3
"""quality_session.py — bitz-quality セッション管理スクリプト

qa-session.json の生成・フェーズ更新・成果物パス記録・完了処理を行う。
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

def init_session(target_dir: Path, feature_id: str, title: str) -> Path:
    sessions_dir = target_dir / ".spec/quality/sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    
    safe_id = feature_id.lower().replace("/", "-").replace(" ", "-")
    session_file = sessions_dir / f"qa-session-{safe_id}.json"
    
    data = {
        "session_id": f"qa-{safe_id}",
        "feature_id": feature_id,
        "title": title,
        "current_phase": "phase_0_intake",
        "qa_level": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "artifacts": {
            "scoring": None,
            "impact_analysis": None,
            "bug_analysis": None,
            "viewpoints": None,
            "test_cases": [],
            "gate_results": None,
            "summary_report": None
        },
        "history": [
            {
                "phase": "phase_0_intake",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "started",
                "note": "QAセッションを開始しました。"
            }
        ]
    }
    
    session_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return session_file

def update_phase(session_file: Path, next_phase: str, note: str = "") -> dict:
    if not session_file.exists():
        raise FileNotFoundError(f"セッションファイルが存在しません: {session_file}")
        
    data = json.loads(session_file.read_text(encoding="utf-8"))
    data["current_phase"] = next_phase
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["history"].append({
        "phase": next_phase,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "in_progress",
        "note": note
    })
    session_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data

def main() -> int:
    parser = argparse.ArgumentParser(description="qa-session.json のライフサイクルを管理します。")
    subparsers = parser.add_subparsers(dest="action", required=True)
    
    # init
    p_init = subparsers.add_parser("init", help="セッションを初期化する")
    p_init.add_argument("feature_id", help="フィーチャーID (例: FEAT-001)")
    p_init.add_argument("target", nargs="?", default=".", help="プロジェクトルートパス")
    p_init.add_argument("--title", default="新機能QA", help="機能タイトル")
    
    # update
    p_up = subparsers.add_parser("update", help="フェーズを更新する")
    p_up.add_argument("session_path", help="qa-session.json のパス")
    p_up.add_argument("--next-phase", required=True, help="次のフェーズ名")
    p_up.add_argument("--note", default="", help="更新メモ")
    
    args = parser.parse_args()
    
    if args.action == "init":
        target_path = Path(args.target)
        file_path = init_session(target_path, args.feature_id, args.title)
        print(f"[✔] QAセッションを初期化しました: {file_path}")
        return 0
    elif args.action == "update":
        session_file = Path(args.session_path)
        data = update_phase(session_file, args.next_phase, args.note)
        print(f"[✔] フェーズを '{args.next_phase}' に更新しました。")
        return 0
        
    return 1

if __name__ == "__main__":
    sys.exit(main())
