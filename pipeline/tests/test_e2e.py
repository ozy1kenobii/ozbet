"""Uçtan uca: ağ yerine sahte kaynaklarla tüm günlük akışı çalıştırır ve çıktı şemasını doğrular."""
import datetime as dt
import json

import numpy as np
import pytest

from ozbet import config
from ozbet.sources import flashscore, iddaa, nesine, predictions_common
from ozbet.sources.base import Prediction

TR_TEAMS = ["Galatasaray", "Fenerbahce", "Besiktas", "Trabzonspor", "Buyuksehyr", "Goztepe", "Samsunspor",
            "Kasimpasa", "Rizespor", "Antalyaspor", "Konyaspor", "Kayserispor", "Alanyaspor", "Gaziantep",
            "Kocaelispor", "Genclerbirligi", "Eyupspor", "Karagumruk"]
TODAY = dt.date(2026, 11, 5)


def synth_history(teams, seed):
    rng = np.random.default_rng(seed)
    att = rng.normal(0, .3, len(teams)); de = rng.normal(0, .25, len(teams))
    rows, d0 = [], dt.date(2024, 8, 10)
    for s, season in enumerate(["2425", "2526", "2627"]):
        for i, h in enumerate(teams):
            for j, a in enumerate(teams):
                if i == j:
                    continue
                d = d0 + dt.timedelta(days=365 * s + (i * 7 + j * 3) % 250)
                if d >= TODAY:
                    continue
                lh = np.exp(0.25 + .25 + att[i] + de[j]); la = np.exp(0.25 + att[j] + de[i])
                hg, ag = int(rng.poisson(lh)), int(rng.poisson(la))
                rows.append({"date": d, "season": season, "home": h, "away": a, "hg": hg, "ag": ag,
                             "hthg": hg // 2, "htag": ag // 2, "hs": 12, "as": 9, "hst": 5, "ast": 3,
                             "hc": 6.0, "ac": 4.0, "hy": 2.0, "ay": 2.0, "hr": 0.0, "ar": 0.0,
                             "odds_open": {"1": 2.0, "X": 3.3, "2": 3.6}, "odds_close": {"1": 2.0, "X": 3.3, "2": 3.6},
                             "src": "test"})
    return rows


NESINE_DOC = {"sg": {"LA": [{"LID": 7, "N": "Türkiye Süper Lig"}, {"LID": 9, "N": "Brezilya Serie B"}], "EA": [
    {"C": "1234", "HN": "Galatasaray", "AN": "Fenerbahçe", "LC": 7, "D": "05.11.2026", "T": "20:00",
     "MA": [{"MTID": 1, "MBS": 1, "OCA": [{"N": 1, "O": 2.10}, {"N": 2, "O": 3.40}, {"N": 3, "O": 3.20}]},
            {"MTID": 12, "MBS": 1, "OCA": [{"N": 1, "O": 2.05}, {"N": 2, "O": 1.75}]},
            {"MTID": 38, "MBS": 1, "OCA": [{"N": 1, "O": 1.70}, {"N": 2, "O": 2.05}]}]},
    {"C": "1240", "HN": "Göztepe", "AN": "Kasımpaşa", "LC": 7, "D": "05.11.2026", "T": "17:00",
     "MA": [{"MTID": 1, "MBS": 2, "OCA": [{"N": 1, "O": 1.80}, {"N": 2, "O": 3.60}, {"N": 3, "O": 4.40}]}]},
    {"C": "1300", "HN": "Bilinmeyen FC", "AN": "Başka SK", "LC": 9, "D": "05.11.2026", "T": "23:00",
     "MA": [{"MTID": 1, "MBS": 3, "OCA": [{"N": 1, "O": 2.5}, {"N": 2, "O": 3.0}, {"N": 3, "O": 2.8}]}]},
    {"C": "9999", "TYPE": -1, "HN": "x", "AN": "y", "LC": 7, "D": "05.11.2026", "T": "20:00", "MA": []},
]}}


def test_nesine_parse():
    fx = nesine.parse(NESINE_DOC, TODAY, "t")
    assert len(fx) == 3
    g = fx[0]
    assert g.league_id == "TR1" and g.code == "1234" and g.mbs == 1
    assert g.odds == {"1": 2.10, "X": 3.40, "2": 3.20, "U2.5": 2.05, "O2.5": 1.75, "BTTS_Y": 1.70, "BTTS_N": 2.05}
    assert g.kickoff.hour == 20 and fx[2].league_id is None


def test_iddaa_parse():
    ev = [{"i": 55, "hn": "Galatasaray", "an": "Fenerbahçe", "ci": 584, "mbc": "1",
           "d": int(dt.datetime(2026, 11, 5, 17, 0, tzinfo=dt.timezone.utc).timestamp()),
           "m": [{"st": 1, "o": [{"n": "1", "odd": 2.15}, {"n": "0", "odd": 3.35}, {"n": "2", "odd": 3.1}]},
                 {"st": 101, "sov": "2.5", "o": [{"n": "Alt", "odd": 2.0}, {"n": "Üst", "odd": 1.78}]},
                 {"st": 89, "o": [{"n": "Var", "odd": 1.72}, {"n": "Yok", "odd": 2.0}]}]}]
    fx = iddaa.parse_events(ev, {584: "Türkiye Süper Lig"}, TODAY, "t")
    assert fx[0].league_id == "TR1" and fx[0].mbs == 1 and fx[0].kickoff.hour == 20
    assert fx[0].odds["X"] == 3.35 and fx[0].odds["O2.5"] == 1.78 and fx[0].odds["BTTS_N"] == 2.0


def test_flashscore_parse():
    ts = int(dt.datetime(2026, 11, 4, 17, 0, tzinfo=dt.timezone.utc).timestamp())
    feed = (f"SA÷1¬~ZA÷TÜRKİYE: Süper Lig¬ZEE÷x¬~AA÷abc¬AD÷{ts}¬AB÷3¬AE÷Beşiktaş¬AF÷Trabzonspor¬AG÷2¬AH÷1¬BA÷1¬BB÷0¬~"
            f"AA÷def¬AD÷{ts}¬AB÷1¬AE÷Samsunspor¬AF÷Konyaspor¬")
    fx = flashscore.parse_feed(feed, "t")
    assert len(fx) == 2 and fx[0].league_id == "TR1"
    assert fx[0].result == {"ft": [2, 1], "ht": [1, 0]} and fx[1].status == "scheduled"


@pytest.mark.parametrize("txt,exp", [
    ("Galatasaray to win and over 3.5", {"1X2": "1", "OU25": "O2.5"}),
    ("Both teams to score", {"BTTS": "BTTS_Y"}),
    ("Under 2.5 goals", {"OU25": "U2.5"}),
    ("Draw", {"1X2": "X"}),
    ("Fenerbahce 1-2", {"1X2": "2"}),
])
def test_picks_from_text(txt, exp):
    got = predictions_common.picks_from_text(txt, "Galatasaray", "Fenerbahce")
    for k, v in exp.items():
        assert got.get(k) == v


def test_full_run(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    from ozbet import run
    from ozbet.sources import football_data, registry

    tr = synth_history(TR_TEAMS, 1)
    monkeypatch.setattr(football_data, "history", lambda c, code, s: tr if code == "T1" else [])
    monkeypatch.setattr(football_data, "fixtures", lambda c, d: [])
    nes = registry.Src("nesine", "Nesine", fixtures=lambda c, d: nesine.parse(NESINE_DOC, d, "t"))

    def boom(*a, **k):
        raise ConnectionError("engellendi")
    monkeypatch.setattr(registry, "FIXTURE_SOURCES", [nes, registry.Src("iddaa", "iddaa", fixtures=boom)])
    monkeypatch.setattr(registry, "XG_SOURCES", [])
    monkeypatch.setattr(registry, "NEWS_SOURCES", [])
    monkeypatch.setattr(registry, "RESULT_SOURCES", [])
    monkeypatch.setattr(registry, "extra_history", lambda c, b, t: {})
    fake_pred = [Prediction("forebet", "Galatasaray", "Fenerbahce", "2026-11-05", "t",
                            {"1X2": "1", "OU25": "O2.5", "BTTS": "BTTS_Y"}),
                 Prediction("sportytrader", "Galatasaray", "Fenerbahçe SK", "2026-11-05", "t",
                            {"BTTS": "BTTS_Y"})]
    monkeypatch.setattr(registry, "PREDICTION_SOURCES",
                        [registry.Src("forebet", "Forebet", predictions=lambda c, d, f: fake_pred)])

    doc = run.main(["--date", "2026-11-05", "--no-llm"])
    out = json.loads((tmp_path / "2026-11-05.json").read_text())
    assert out == json.loads(json.dumps(doc, default=str))
    st = {s["id"]: s["status"] for s in out["sources"]}
    assert st["nesine"] == "ok" and st["iddaa"] == "missing"
    ms = {m["code"]: m for m in out["matches"]}
    g = ms["1234"]
    assert g["model"]["sims"] == 10000 and len(g["model"]["score_matrix"]) == 6
    assert g["market"]["implied"]["1"] > 0 and g["stats"]["home"]["n"] == 10
    assert any(s["source"] == "forebet" for s in g["consensus"]["sources"])
    assert g["pick"]["stars"] in range(1, 6) and g["comment"]
    assert g["provenance"]["odds"]["source"] == "nesine"
    other = ms["1300"]
    assert other["model"] is None and "Veri yetersiz" in other["flags"] and other["league"] == "OTHER"
    for f in ("latest.json", "index.json", "scorecard.json", "status.json"):
        assert (tmp_path / f).exists()

    # İkinci çalıştırma: oran değişimi → oran geçmişi + hareket
    NESINE_DOC["sg"]["EA"][0]["MA"][0]["OCA"][0]["O"] = 1.90
    run.main(["--date", "2026-11-05", "--no-llm"])
    out2 = json.loads((tmp_path / "2026-11-05.json").read_text())
    g2 = next(m for m in out2["matches"] if m["code"] == "1234")
    assert len(g2["odds_history"]) == 2 and "1" in g2["market"]["drop_alarms"]

    # Ertesi gün: sonuç gelince karne puanlanır
    tr.append({**tr[0], "date": TODAY, "home": "Galatasaray", "away": "Fenerbahce", "hg": 2, "ag": 1})
    NESINE_DOC_BACKUP = json.loads(json.dumps(NESINE_DOC))
    NESINE_DOC["sg"]["EA"] = []
    run.main(["--date", "2026-11-06", "--no-llm"])
    hist = json.loads((tmp_path / "history" / "2026-11-05.json").read_text())
    assert any(r["score"] == "2-1" for r in hist["rows"])
    card = json.loads((tmp_path / "scorecard.json").read_text())
    assert card["overall"]["n"] >= 1
    NESINE_DOC.update(NESINE_DOC_BACKUP)
