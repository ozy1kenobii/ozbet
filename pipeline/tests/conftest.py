import pytest

from ozbet import config


@pytest.fixture(autouse=True)
def raw_model_weight(monkeypatch):
    """Birim testleri harmansız (α=1) model olasılığıyla çalışır; harman ayrıca test edilir."""
    monkeypatch.setattr(config, "MODEL_WEIGHT", 1.0)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Testler asla gerçek ağa çıkmaz: her HTTP isteği anında ConnectionError verir, yeniden deneme beklemesi yok."""
    import requests
    from ozbet import http as ozhttp

    def refuse(*a, **k):
        raise requests.ConnectionError("testte ağ erişimi kapalı")
    monkeypatch.setattr(requests.Session, "get", refuse)
    monkeypatch.setattr(requests, "post", refuse)
    monkeypatch.setattr(ozhttp.time, "sleep", lambda s: None)


@pytest.fixture(autouse=True)
def fast_retry(monkeypatch):
    monkeypatch.setattr(config, "RETRY_DELAY_S", 0.0)
