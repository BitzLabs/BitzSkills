"""保存済み故障診断のAPI試行数を照合する。"""
import production_trace as trace


def check_api(api, row, receipt, fault, expected):
    count = 1 if fault == 'connection' else expected
    statuses = [None] if fault == 'connection' else [503 if fault == 'http-503' else 200] * expected
    trace.require(type(row['apiRequests']) is int and type(receipt['apiRequests']) is int and
                  len(api) == row['apiRequests'] == receipt['apiRequests'] == count and
                  trace.json_equal([e.get('http.response.status_code') for e in api], statuses) and
                  trace.json_equal(row['httpStatuses'], statuses) and
                  trace.json_equal(receipt['httpStatuses'], statuses) and
                  all(type(e.get('attempt')) is int and e['attempt'] == i and
                      e.get('auth.header_attached') is False for i, e in enumerate(api)), 'fixed fault API attempts')
