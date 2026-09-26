"""分割した適合reportを、全件の厳密な網羅を確認して統合する。"""


def merge_reports(reports, groups, identifiers):
    if len(reports) != len(groups):
        raise ValueError("分割reportの件数が一致しません")
    rows = {}
    environment = None
    for report, group in zip(reports, groups):
        if not isinstance(report, dict) or set(report) != {"core", "environment", "fixtures", "counts", "allPassed"}:
            raise ValueError("適合reportの外形が不正です")
        if not isinstance(report["core"], str) or not isinstance(report["environment"], dict):
            raise ValueError("適合reportの実行環境が不正です")
        if environment is None:
            environment = report["environment"]
        elif environment != report["environment"]:
            raise ValueError("分割間で実行環境が一致しません")
        entries = report["fixtures"]
        if not isinstance(entries, list) or [row.get("id") for row in entries] != group:
            raise ValueError("分割内のfixture IDまたは順序が計画と一致しません")
        counts = {"passed": 0, "failed": 0, "error": 0}
        for row in entries:
            if set(row) != {"id", "result", "differences"} or row["result"] not in counts:
                raise ValueError("fixture結果の外形が不正です")
            if not isinstance(row["differences"], list) or not all(isinstance(x, str) for x in row["differences"]):
                raise ValueError("fixtureの差分が不正です")
            if row["result"] == "passed" and row["differences"]:
                raise ValueError("差分のあるfixtureをpassedにできません")
            if row["id"] in rows:
                raise ValueError("fixture IDが重複しています")
            rows[row["id"]] = row
            counts[row["result"]] += 1
        passed = bool(entries) and counts["passed"] == len(entries)
        if (report["counts"] != counts or any(type(report["counts"][k]) is not int for k in counts)
                or type(report["allPassed"]) is not bool or report["allPassed"] != passed):
            raise ValueError("適合reportの集計が実結果と一致しません")
    if set(rows) != set(identifiers) or len(identifiers) != len(rows):
        raise ValueError("全fixtureの欠落、余分または重複があります")
    counts = {status: sum(row["result"] == status for row in rows.values())
              for status in ("passed", "failed", "error")}
    return {"core": "<core>", "environment": environment,
            "fixtures": [rows[identifier] for identifier in identifiers], "counts": counts,
            "allPassed": bool(rows) and counts["passed"] == len(rows)}
