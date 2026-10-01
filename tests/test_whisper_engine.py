from unittest.mock import MagicMock

from diswhisper.transcriber.engine import WhisperEngine


def test_missing_lazy_cuda_libraries_fall_back_before_inference(monkeypatch):
    monkeypatch.setattr("ctranslate2.get_cuda_device_count", lambda: 1)
    monkeypatch.setattr("diswhisper.transcriber.engine._cuda_libraries_available", lambda: False)
    monkeypatch.setattr("diswhisper.transcriber.engine._prepare_windows_cuda_libraries", lambda *args: None)
    model = MagicMock()
    monkeypatch.setattr("diswhisper.transcriber.engine.WhisperModel", model)
    engine = WhisperEngine("base", "auto", "float16")
    assert engine.active_device == "cpu"
    assert engine.active_compute_type == "int8"
    assert model.call_args.kwargs["device"] == "cpu"


def test_failed_cuda_model_initialization_falls_back_to_cpu(monkeypatch):
    monkeypatch.setattr("diswhisper.transcriber.engine._cuda_libraries_available", lambda: True)
    monkeypatch.setattr("diswhisper.transcriber.engine._prepare_windows_cuda_libraries", lambda *args: None)
    model = MagicMock(side_effect=[RuntimeError("GPU unavailable"), MagicMock()])
    monkeypatch.setattr("diswhisper.transcriber.engine.WhisperModel", model)
    engine = WhisperEngine("base", "cuda", "float16")
    assert engine.active_device == "cpu"
    assert model.call_count == 2
