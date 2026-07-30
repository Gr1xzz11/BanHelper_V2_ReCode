from tools.benchmark_events import run


def test_100_event_benchmark_meets_acceptance_criteria():
    result = run(100)
    assert result["lost"] == 0
    assert result["duplicates_created"] == 0
    assert result["duplicates_rejected"] == 100
    assert result["second_delivery_accepted"] == 0
    assert result["p95_ms"] <= 500
    assert result["queue_items"] == 100
