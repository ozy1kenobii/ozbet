"""Gol yanlılığı araştırması ve toplam gol büzmesi (dixon_coles.shrink_total) testleri. Ağ yok, sentetik veri."""
import datetime as dt
import json
import math

import numpy as np
import pytest

from ozbet.agents import simulation
from ozbet.model import dixon_coles as dc
from ozbet.research import goals_bias as gb

from .test_e2e import TR_TEAMS, synth_history

TODAY = dt.date(2026, 11, 5)


# ---------------- shrink_total ----------------
@pytest.mark.parametrize("lh,la,base,k", [(2.2, 1.6, 1.3, 0.5), (0.7, 0.9, 1.4, 0.25), (1.8, 0.6, 1.2, 0.75)])
def test_shrink_total_keeps_ratio_and_moves_level(lh, la, base, k):
    sh, sa = dc.shrink_total(lh, la, base, k)
    assert sh / sa == pytest.approx(lh / la)                       # maç sonucu bilgisi (oran) korunur
    g0, g1 = math.sqrt(lh * la), math.sqrt(sh * sa)
    assert math.log(g1 / base) == pytest.approx(k * math.log(g0 / base))   # log ölçekte k kadar kalır


def test_shrink_total_edges():
    assert dc.shrink_total(1.7, 1.1, 1.3, 1.0) == (1.7, 1.1)        # k=1 → dokunmaz
    sh, sa = dc.shrink_total(1.7, 1.1, 1.3, 0.0)                    # k=0 → tam lig seviyesi
    assert math.sqrt(sh * sa) == pytest.approx(1.3)
    assert dc.shrink_total(1.7, 1.1, 0.0, 0.5) == (1.7, 1.1)        # geçersiz taban → dokunmaz
    assert dc.shrink_total(1.7, 1.1, 1.3) == dc.shrink_total(1.7, 1.1, 1.3, dc.TOTAL_SHRINK)


def test_base_level_is_league_mean_geomean():
    R = dc.fit(synth_history(TR_TEAMS, 1), TODAY, 0.0019)
    logs = [0.5 * math.log(np.prod(R.lambdas(h, a))) for h in R.teams for a in R.teams if h != a]
    assert math.exp(np.mean(logs)) == pytest.approx(R.base_level(), rel=1e-6)
    assert R.base_level(neutral=True) == pytest.approx(math.exp(R.mu))


# ---------------- üretim yolu (agents.simulation.predict) ----------------
def test_predict_applies_total_shrink_and_keeps_schema(monkeypatch):
    M = {"TR1": simulation.build("TR1", synth_history(TR_TEAMS, 1), TODAY)}
    h, a = TR_TEAMS[0], TR_TEAMS[5]
    monkeypatch.setattr(dc, "TOTAL_SHRINK", 1.0)
    raw = simulation.predict(h, a, "TR1", M, None, "k")
    monkeypatch.setattr(dc, "TOTAL_SHRINK", 0.5)
    shr = simulation.predict(h, a, "TR1", M, None, "k")
    assert set(raw) == set(shr)                                     # çıktı şeması değişmez
    assert simulation.TOTAL_SHRINK_NOTE not in raw["notes"] and simulation.TOTAL_SHRINK_NOTE in shr["notes"]
    assert gb.SHRINK_NOTE == simulation.TOTAL_SHRINK_NOTE
    assert shr["lambda_home"] / shr["lambda_away"] == pytest.approx(raw["lambda_home"] / raw["lambda_away"], rel=5e-3)
    base = M["TR1"].goals.base_level()
    g_raw = math.sqrt(raw["lambda_home"] * raw["lambda_away"]); g_shr = math.sqrt(shr["lambda_home"] * shr["lambda_away"])
    assert abs(math.log(g_shr / base)) <= abs(math.log(g_raw / base)) + 1e-3   # lig seviyesine yaklaşır
    assert math.log(g_shr / base) == pytest.approx(0.5 * math.log(g_raw / base), abs=3e-3)


# ---------------- walk-forward ----------------
def _synth_league(n_teams=12, rounds=6, seed=3, total_sd=0.0, strength_sd=0.35):
    """Bilinen parametreli lig: güç farkı (a−d) gerçek, toplam gol eğilimi (a+d) total_sd kadar."""
    rng = np.random.default_rng(seed)
    teams = [f"T{i:02d}" for i in range(n_teams)]
    s = rng.normal(0, strength_sd, n_teams); t = rng.normal(0, total_sd, n_teams)
    att, dfn = (s + t) / 2, (t - s) / 2
    rows, day = [], dt.date(2025, 8, 1)
    for _ in range(rounds):
        for i in range(n_teams):
            for j in range(n_teams):
                if i == j:
                    continue
                lh, la = math.exp(0.25 + 0.25 + att[i] + dfn[j]), math.exp(0.25 + att[j] + dfn[i])
                rows.append({"date": day + dt.timedelta(days=len(rows) // 6), "home": teams[i], "away": teams[j],
                             "hg": int(rng.poisson(lh)), "ag": int(rng.poisson(la)), "hthg": None, "htag": None})
    return rows


def test_walk_forward_uses_only_past_and_is_calibrated():
    rows = _synth_league()
    recs = gb.walk_forward(rows, 1.0)
    first = min(r["date"] for r in recs)
    assert sum(1 for r in rows if r["date"].isoformat() < first) >= gb.MIN_TRAIN   # ilk tahminden önce yeterli eğitim
    assert 0 < len(recs) < len(rows)
    s = gb.summarize(recs)
    assert s["n"] == len(recs) and set(s["events"]) == set(gb.EVENTS)
    assert abs(s["lambda_sum"] - s["goals"]) < 4 * s["goals_se"]
    assert all(abs(e["z"]) < 3.5 for e in s["events"].values())
    assert s["ll_1x2"] < math.log(3)


def test_walk_forward_no_leakage_from_future_results():
    rows = _synth_league(rounds=3)
    a = gb.walk_forward(rows, 1.0)
    cut = sorted(r["date"] for r in rows)[len(rows) * 2 // 3]
    monday = cut - dt.timedelta(days=cut.weekday())
    changed = [dict(r, hg=9, ag=9) if r["date"] >= monday else r for r in rows]   # geleceği boz
    b = gb.walk_forward(changed, 1.0)
    pa = {(r["date"], i): r["p"]["O2.5"] for i, r in enumerate(a) if r["date"] < (monday + dt.timedelta(days=7)).isoformat()}
    pb = {(r["date"], i): r["p"]["O2.5"] for i, r in enumerate(b) if r["date"] < (monday + dt.timedelta(days=7)).isoformat()}
    assert pa and pa == pb


def test_shrink_helps_goal_markets_when_totals_are_noise_and_keeps_1x2():
    """Mekanizma testi: takımların toplam gol eğilimi gerçekte yoksa büzme gol log-loss'unu düşürür, 1X2'yi bozmaz."""
    rows = _synth_league(rounds=4, seed=11, total_sd=0.0)
    s1 = gb.summarize(gb.walk_forward(rows, 1.0)); s5 = gb.summarize(gb.walk_forward(rows, 0.5))
    assert s5["n"] == s1["n"]
    assert s5["ll_goal"] < s1["ll_goal"]
    assert s5["ll_1x2"] <= s1["ll_1x2"] + 0.002


def test_archive_report_skips_thin_leagues(tmp_path):
    thin = [{"date": "2026-10-30", "home": "A", "away": "B", "ft": [1, 0], "ht": [0, 0]}] * 9
    (tmp_path / "results-TR1.json").write_text(json.dumps({"league": "TR1", "rows": thin}))
    big = [{"date": r["date"].isoformat(), "home": r["home"], "away": r["away"], "ft": [r["hg"], r["ag"]], "ht": None}
           for r in _synth_league(rounds=2)]
    (tmp_path / "results-XX1.json").write_text(json.dumps({"league": "XX1", "rows": big}))
    rep = gb.archive_report(tmp_path, shrinks=(1.0, 0.5))
    assert "TR1" in rep["skipped"] and rep["skipped"]["TR1"]["rows"] == 9
    assert set(rep["leagues"]["XX1"]) == {"k=1", "k=0.5"}
    assert rep["pooled"]["k=1"]["n"] == rep["leagues"]["XX1"]["k=1"]["n"] >= gb.MIN_TEST
    assert rep["total_rows"] == 9 + len(big)


# ---------------- canlı örnek ----------------
def _live_match(i, lh, la, ft, league="TR1", notes=(), method="league"):
    p = gb.event_probs(lh, la, -0.05)
    return {"id": f"m{i}", "league": league, "result": {"ft": list(ft)},
            "model": {"lambda_home": lh, "lambda_away": la, "rho": -0.05, "method": method, "data_quality": "high",
                      "probs": {k: p[k] for k in ("1", "X", "2", "O1.5", "O2.5", "O3.5", "BTTS_Y")},
                      "extra": {"H_O1.5": p["H_O1.5"], "A_O1.5": p["A_O1.5"]},
                      "score_matrix": [[p["0-0"]]], "notes": list(notes)}}


def _live_set(n=80, seed=5):
    """Gerçek toplam gol her maçta aynı (2.7); modelin λ'ları bunun etrafında gürültülü → büzme yardımcı olmalı."""
    rng = np.random.default_rng(seed)
    ms = []
    for i in range(n):
        f = math.exp(rng.normal(0, 0.25))
        ms.append(_live_match(i, 1.5 * f, 1.2 * f, (rng.poisson(1.5), rng.poisson(1.2)), notes=("Şut tabanlı güç harmanı (%40)",)))
    return ms


def test_load_live_and_report(tmp_path):
    ms = _live_set(20)
    ms.append({"id": "x", "league": "TR1", "result": None, "model": ms[0]["model"]})                 # bitmemiş
    ms.append({"id": "y", "league": "TR1", "result": {"ft": [1, 1]}, "model": None})                # modelsiz
    ms.append({"id": "z", "league": "TR1", "result": {"ft": [1, 1]},
               "model": dict(ms[0]["model"], source="piyasa")})                                     # piyasa-tabanlı
    (tmp_path / "2026-11-07.json").write_text(json.dumps({"date": "2026-11-07", "matches": ms}))
    (tmp_path / "2026-11-08.json").write_text(json.dumps({"date": "2026-11-08", "matches": ms[:3]}))  # tekrar
    (tmp_path / "latest.json").write_text(json.dumps({"date": "2026-11-08", "matches": ms}))
    live = gb.load_live(tmp_path)
    assert len(live) == 20
    rep = gb.live_report(live)
    assert rep["all"]["n"] == 20 and rep["splits"]["sut_harmani"]["var"]["n"] == 20
    assert rep["splits"]["kadro_duzeltmesi"]["yok"]["n"] == 20
    assert rep["all"]["events"]["0-0"]["n"] == 20


def test_replay_shrink_improves_noisy_totals_and_skips_already_shrunk():
    ms = _live_set(200)
    rep = gb.replay_shrink(ms, ks=(1.0, 0.5), n_boot=300)
    assert rep["n"] == 200
    assert rep["k"]["0.5"]["ll_goal"] < rep["k"]["1"]["ll_goal"]
    d = rep["diff_vs_k1"]["0.5"]
    assert d["gol"]["d"] < 0 and d["gol"]["ci95"][0] <= d["gol"]["d"] <= d["gol"]["ci95"][1]
    assert abs(d["1x2"]["d"]) < 0.01
    # üretimde zaten büzülmüş (notlu) ve lig-dışı maçlar ikinci kez büzülmez
    done = [_live_match(900 + i, 1.5, 1.2, (1, 1), notes=(gb.SHRINK_NOTE,)) for i in range(5)]
    cup = [_live_match(950, 1.5, 1.2, (1, 1), method="elo")]
    assert gb.replay_shrink(ms + done + cup, ks=(1.0, 0.5), n_boot=50)["n"] == 200
    assert gb.replay_shrink(done, n_boot=10) == {"n": 0}


# ---------------- tercih ayrıştırması ----------------
def test_history_report_separates_level_bias_from_selection():
    rows = []
    for i in range(100):
        won = i % 2 == 0                                   # tüm maçlarda gözlenen %50, model %50 → seviye yanlılığı 0
        r = {"markets": [{"m": "BTTS_Y", "p": 0.45 + 0.1 * (i % 3 == 0), "q": 0.52, "o": 1.8, "won": won}]}
        if i < 40:                                         # tercihler: p %62 ama isabet %50 → fark seçimden
            r.update({"pick": "BTTS_Y", "p": 0.62, "won": i % 2 == 0})
        rows.append(r)
    rep = gb.history_report(rows)
    mk, pk = rep["markets"]["BTTS_Y"], rep["picks"]["BTTS_Y"]
    assert mk["n"] == 100 and mk["obs"] == 0.5 and mk["market"] == pytest.approx(0.52)
    assert pk["n"] == 40 and pk["gap"] == pytest.approx(0.12)
    assert pk["level_bias_all"] == pytest.approx(mk["model"] - 0.5, abs=1e-4)
    assert pk["selection_effect"] == pytest.approx(pk["gap"] - pk["level_bias_all"], abs=1e-4)


def test_cli_runs_on_repo_like_dir(tmp_path, capsys):
    (tmp_path / "archive").mkdir(); (tmp_path / "history").mkdir()
    (tmp_path / "2026-11-07.json").write_text(json.dumps({"date": "2026-11-07", "matches": _live_set(12)}))
    out = tmp_path / "rep.json"
    rep = gb.main(["--data", str(tmp_path), "--out", str(out)])
    assert rep["live"]["all"]["n"] == 12 and json.loads(out.read_text())["replay"]["n"] == 12
    assert "Canlı örnek" in capsys.readouterr().out
