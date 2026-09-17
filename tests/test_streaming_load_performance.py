from scripts.perf_streaming_load import run_load_test


def test_streaming_load_harness_reports_pipeline_metrics() -> None:
    report = run_load_test(
        total_messages=100,
        min_seconds=1,
        max_seconds=1,
        min_batch_size=1,
        max_batch_size=10,
        seed=7,
    )

    assert report["input"]["total_messages"] == 100
    assert report["summary"]["processed_messages"] == 100
    assert report["summary"]["generated_batches"] >= 10
    assert report["summary"]["elapsed_seconds"] <= 2
    assert report["summary"]["throughput_messages_per_second"] > 0
    assert report["batches"]["min_size"] >= 1
    assert report["batches"]["max_size"] <= 10
    assert report["pipeline"]["stream_extract"]["count"] == 100
    assert report["pipeline"]["parse_event"]["count"] == 100
    assert report["pipeline"]["route_event"]["count"] == 100
    assert report["pipeline"]["resolve_identifier"]["count"] == 100
    assert report["pipeline"]["fetch_ohip_rest"]["count"] == 100
    assert report["pipeline"]["transform_core"]["count"] == 100
