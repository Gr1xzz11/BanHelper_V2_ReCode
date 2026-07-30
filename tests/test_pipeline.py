from tools.benchmark_pipeline import run


def test_full_local_pipeline_handles_100_events():
    result = run(100)
    assert result["http_accepted"] == 100
    assert result["lost"] == 0
    assert result["duplicates_created"] == 0
    assert result["duplicates_rejected"] == 100
    assert result["p95_ms"] <= 500
    assert result["clean_shutdown"]
