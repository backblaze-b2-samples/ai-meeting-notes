import pytest

from app.service import pipeline


def test_run_pipeline_marks_unexpected_running_stage_failed(monkeypatch):
    writes = []

    def fake_write_status(
        meeting_id,
        state,
        stages,
        error=None,
        provider=None,
        llm_model=None,
    ):
        writes.append(
            {
                "meeting_id": meeting_id,
                "state": state,
                "stages": {
                    name: stage.model_dump(mode="json")
                    for name, stage in stages.items()
                },
                "error": error,
                "provider": provider,
                "llm_model": llm_model,
            }
        )

    monkeypatch.setattr(pipeline, "_write_status", fake_write_status)
    monkeypatch.setattr(
        pipeline,
        "transcribe",
        lambda _file_data: (_ for _ in ()).throw(RuntimeError("network down")),
    )

    with pytest.raises(RuntimeError, match="network down"):
        pipeline.run_pipeline("meeting123", b"audio")

    assert writes[-1]["state"] == "failed"
    assert writes[-1]["error"] == "network down"
    assert writes[-1]["stages"]["asr"]["status"] == "failed"
    assert writes[-1]["stages"]["asr"]["error"] == "network down"
