import pytest

from ozbet import config


@pytest.fixture(autouse=True)
def raw_model_weight(monkeypatch):
    """Birim testleri harmansız (α=1) model olasılığıyla çalışır; harman ayrıca test edilir."""
    monkeypatch.setattr(config, "MODEL_WEIGHT", 1.0)
