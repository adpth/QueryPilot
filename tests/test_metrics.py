from evals.metrics import RunRecord, execution_match, normalise, summarise


def test_row_order_ignored_without_order_by():
    assert execution_match([(1,), (2,)], [(2,), (1,)], order_matters=False)


def test_row_order_enforced_with_order_by():
    assert not execution_match([(1,), (2,)], [(2,), (1,)], order_matters=True)


def test_int_and_float_compare_equal():
    assert execution_match([(1,)], [(1.0,)], order_matters=False)
    assert execution_match([(1.0,)], [(1,)], order_matters=True)
    assert execution_match([("1.0",)], [(1,)], order_matters=False)


def test_float_drift_tolerance():
    # 0.1 + 0.2 in Python yields 0.30000000000000004
    assert execution_match([(0.1 + 0.2,)], [(0.3,)], order_matters=False)


def test_none_sorting_does_not_raise_type_error():
    rows_a = [(None,), (1.0,), (2.0,)]
    rows_b = [(2.0,), (None,), (1.0,)]
    assert execution_match(rows_a, rows_b, order_matters=False)


def test_summary_counts():
    records = [
        RunRecord("a", True, True, 0, False, 3, 100.0, input_tokens=1000, output_tokens=100),
        RunRecord("b", False, True, 2, False, 7, 300.0, input_tokens=2000, output_tokens=200),
        RunRecord("c", True, True, 1, True, 5, 200.0, input_tokens=1000, output_tokens=100),
    ]
    summary = summarise(records, cost_per_1k_in=0.001, cost_per_1k_out=0.002)
    assert summary["execution_accuracy"] == 66.67
    assert summary["valid_sql_rate"] == 100.0
    # Two runs needed repair; one of them ended correct.
    assert summary["self_repair_rate"] == 50.0
    assert summary["avg_tool_calls"] == 5.0
    assert summary["tokens_in"] == 4000
    assert summary["tokens_out"] == 400
    # Cost: (4 * 0.001 + 0.4 * 0.002) / 3 = (0.004 + 0.0008) / 3 = 0.0016
    assert summary["cost_per_query_usd"] == 0.0016


def test_self_repair_rate_is_none_when_nothing_needed_repair():
    records = [RunRecord("a", True, True, 0, False, 2, 50.0)]
    assert summarise(records)["self_repair_rate"] is None

