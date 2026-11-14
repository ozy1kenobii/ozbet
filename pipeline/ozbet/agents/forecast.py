"""Tahmin Motoru: HER maç için doğrudan maç sonu tahmini — dış tahmin sitelerine ve engellenen kaynaklara bağlı değil.

Tek zorunlu girdi bültenin kendisidir (iddaa/Nesine oranları). Oranlar o maç hakkında bilinen her şeyi (form, kadro,
haber, para akışı) zaten fiyatlar; repo araştırması (docs/research/roi-model.md) kendi modelimizin piyasayı
geçemediğini gösterdi. Bu yüzden motor oranları ÇÖZER:

1. Sonuç olasılığı: 1X2 oranlarından Shin ile marj ayıklanır. Ligin kendi Dixon-Coles modeli varsa kalibrasyon
   modülüyle (model/calibration.py) küçük ağırlıkla harmanlanır.
2. Skor dağılımı: piyasa λ'ları (model/market_lambda.py: 1X2 + Alt/Üst + KG'ye uydurulmuş Dixon-Coles) → en olası
   skor, gol beklentisi, Alt/Üst, KG.
3. 1X2 grubu eksikse (yalnız çifte şans / KG / Alt-Üst açılmış maçlar) eldeki marketlerden kısmi uydurma yapılır.
4. Oran hareketi: kendi anlık görüntülerimizden (odds_history) tahmin edilen sonucun olasılığı açılıştan bu yana
   ne kadar değişti.

Çıktı bir OLASILIK tahminidir, kesinlik değildir. Güven kademesi geriye dönük ölçüme dayanır (187 biten maç,
5–13 Kas 2026): yüksek (p ≥ 0,60) %75 isabet (n=56), orta (0,45–0,60) %49 (n=71), düşük (< 0,45) %42 (n=60).
Karne her çalıştırmada bu isabeti yeniden ölçer (scorecard.forecast).
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import minimize

from ..markets import probs_from_matrix
from ..model import market_lambda
from .market import shin

CONF_HIGH, CONF_MID = 0.60, 0.45          # güven kademesi eşikleri (tahmin edilen sonucun olasılığı)
SINGLE_MARGIN = 1.07                      # grubu tamamlanamayan tek oran için varsayılan marj (iddaa ~%6–8 / seçenek)
MOVE_MIN = 0.015                          # bundan küçük olasılık değişimi "hareket" sayılmaz
OUTCOME_TEXT = {"1": "Ev sahibi kazanır", "X": "Beraberlik", "2": "Deplasman kazanır"}
PAIRS = (("O1.5", "U1.5"), ("O2.5", "U2.5"), ("O3.5", "U3.5"), ("BTTS_Y", "BTTS_N"))
STRENGTH_KEYS = ("1", "X", "2", "1X", "X2", "12")


def _num(odds: dict, k: str) -> float | None:
    v = odds.get(k)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 1.0 and math.isfinite(v) else None


def fair_1x2(odds: dict | None) -> dict[str, float] | None:
    """1X2 oranlarından marjsız olasılık (Shin); grup eksikse None."""
    if not odds:
        return None
    vals = [_num(odds, k) for k in ("1", "X", "2")]
    if any(v is None for v in vals):
        return None
    return dict(zip(("1", "X", "2"), shin(vals)))


def partial_targets(odds: dict) -> dict[str, float]:
    """1X2 grubu olmayan maçta eldeki marketlerden hedef olasılıklar: ikili gruplar Shin ile, tekler varsayılan marjla."""
    t: dict[str, float] = {}
    for a, b in PAIRS:
        oa, ob = _num(odds, a), _num(odds, b)
        if oa and ob:
            pa, pb = shin([oa, ob])
            t[a], t[b] = pa, pb
    dc = [_num(odds, k) for k in ("1X", "X2", "12")]
    if all(dc):   # çifte şans üçlüsünün adil toplamı 2'dir
        s = sum(1 / v for v in dc)
        for k, v in zip(("1X", "X2", "12"), dc):
            t[k] = min(0.99, (1 / v) * 2 / s)
    else:
        for k in STRENGTH_KEYS:
            v = _num(odds, k)
            if v and k not in t:
                t[k] = min(0.99, (1 / v) / SINGLE_MARGIN)
    return t


def partial_fit(odds: dict | None) -> dict | None:
    """Kısmi uydurma: eldeki marketlere en yakın (λ_ev, λ_dep). Güç bilgisi (1/X/2/çifte şans) yoksa None."""
    if not odds:
        return None
    t = partial_targets(odds)
    if not any(k in t for k in STRENGTH_KEYS):
        return None

    def f(x):
        p = probs_from_matrix(market_lambda.score_matrix(math.exp(x[0]), math.exp(x[1]), 0.0))
        return sum((p[k] - q) ** 2 for k, q in t.items() if k in p)

    r = minimize(f, [math.log(1.4), math.log(1.2)], method="L-BFGS-B", bounds=[(-3, 2.2), (-3, 2.2)])
    return {"lambda_home": math.exp(r.x[0]), "lambda_away": math.exp(r.x[1]), "rho": 0.0,
            "used": sorted(t), "err": float(r.fun)}


def _lambdas(m: dict) -> tuple[float, float, float, str] | None:
    """Skor dağılımı için λ kaynağı: önce piyasa λ'ları, yoksa lig modeli."""
    for key in ("market_model", "model"):
        mo = m.get(key)
        if mo and mo.get("lambda_home") and mo.get("lambda_away") and (key == "market_model" or mo.get("source") == "piyasa"):
            return float(mo["lambda_home"]), float(mo["lambda_away"]), float(mo.get("rho") or 0.0), "piyasa"
    mo = m.get("model")
    if mo and mo.get("lambda_home") and mo.get("lambda_away"):
        return float(mo["lambda_home"]), float(mo["lambda_away"]), float(mo.get("rho") or 0.0), "model"
    return None


def _move(m: dict, outcome: str) -> dict | None:
    """Tahmin edilen sonucun marjsız olasılığı ilk anlık görüntüden bu yana ne kadar değişti."""
    hist = [h for h in (m.get("odds_history") or []) if fair_1x2(h)]
    if len(hist) < 2:
        return None
    d = fair_1x2(hist[-1])[outcome] - fair_1x2(hist[0])[outcome]
    if abs(d) < MOVE_MIN:
        return None
    return {"delta": round(d, 4), "dir": "güçleniyor" if d > 0 else "zayıflıyor", "since": hist[0].get("t")}


def confidence(p: float) -> str:
    return "yüksek" if p >= CONF_HIGH else "orta" if p >= CONF_MID else "düşük"


def build(m: dict) -> dict | None:
    """Maç sözlüğünden tahmin bloğu; hiçbir güç/gol bilgisi yoksa None."""
    odds = m.get("odds") or {}
    q = fair_1x2(odds)
    lam = _lambdas(m)
    basis, used = "piyasa", None
    model = m.get("model")
    own = bool(model and model.get("source") != "piyasa" and model.get("probs"))
    if q and own:   # lig modeli varsa kalibre harman (model ağırlığı küçük; piyasa çapa)
        try:
            from ..model.calibration import calibrated_group
            q = calibrated_group({k: model["probs"][k] for k in ("1", "X", "2")}, q, ["1", "X", "2"], m.get("league"))
            basis = "piyasa+model"
        except Exception:  # noqa: BLE001 — kalibrasyon yoksa yalnız piyasa
            pass
    elif not q and own:
        q = {k: float(model["probs"][k]) for k in ("1", "X", "2")}
        basis = "model"
    if not q or not lam:
        pf = partial_fit(odds) if not q else None
        if pf:
            lam = lam or (pf["lambda_home"], pf["lambda_away"], 0.0, "kısmi")
            pp = probs_from_matrix(market_lambda.score_matrix(pf["lambda_home"], pf["lambda_away"], 0.0))
            q = {k: float(pp[k]) for k in ("1", "X", "2")}
            basis, used = "kısmi", pf["used"]
    if not q:
        return None
    s = sum(q.values())
    q = {k: v / s for k, v in q.items()}
    ranked = sorted(q.items(), key=lambda kv: -kv[1])
    outcome, p = ranked[0]
    fc = {"outcome": outcome, "label": OUTCOME_TEXT[outcome], "p": round(p, 4),
          "probs": {k: round(v, 4) for k, v in q.items()}, "margin": round(p - ranked[1][1], 4),
          "confidence": "düşük" if basis == "kısmi" else confidence(p), "basis": basis}
    dc = {"1X": q["1"] + q["X"], "X2": q["X"] + q["2"], "12": q["1"] + q["2"]}
    k_dc = max(dc, key=dc.get)
    fc["dc"] = {"market": k_dc, "p": round(dc[k_dc], 4)}
    if lam:
        lh, la, rho, lsrc = lam
        mat = market_lambda.score_matrix(lh, la, rho)
        pm = probs_from_matrix(mat)
        idx = np.dstack(np.unravel_index(np.argsort(-mat, axis=None)[:3], mat.shape))[0]
        fc["scores"] = [{"score": f"{int(i)}-{int(j)}", "p": round(float(mat[i, j]), 4)} for i, j in idx]
        fc["xg"] = [round(lh, 2), round(la, 2)]
        ou = "O2.5" if pm["O2.5"] >= 0.5 else "U2.5"
        bt = "BTTS_Y" if pm["BTTS_Y"] >= 0.5 else "BTTS_N"
        fc["goals"] = {"market": ou, "p": round(float(pm[ou]), 4)}
        fc["btts"] = {"market": bt, "p": round(float(pm[bt]), 4)}
        fc["lambda_source"] = lsrc
    if used:
        fc["used"] = used
    mv = _move(m, outcome)
    if mv:
        fc["move"] = mv
    fc["text"] = _text(fc)
    return fc


def _text(fc: dict) -> str:
    parts = [f"Tahmin: {fc['label']} (%{fc['p'] * 100:.0f}, güven {fc['confidence']})"]
    if fc.get("scores"):
        sc = fc["scores"][0]
        parts.append(f"en olası skor {sc['score']} (%{sc['p'] * 100:.0f})")
    if fc.get("goals"):
        parts.append(f"{'2.5 Üst' if fc['goals']['market'] == 'O2.5' else '2.5 Alt'} %{fc['goals']['p'] * 100:.0f}")
    if fc.get("btts"):
        parts.append(f"{'KG Var' if fc['btts']['market'] == 'BTTS_Y' else 'KG Yok'} %{fc['btts']['p'] * 100:.0f}")
    s = "; ".join(parts) + "."
    if fc.get("move"):
        s += f" Oran hareketi: tahmin {fc['move']['dir']} ({fc['move']['delta'] * 100:+.1f} puan)."
    if fc["basis"] == "kısmi":
        s += " Maç sonu oranı açılmadığı için eldeki marketlerden kısmi çözüm; güven düşük."
    return s


def grade(fc: dict | None, ft: list[int]) -> dict | None:
    """Biten maçta tahmini puanla (karne satırına yazılır)."""
    if not fc or not fc.get("outcome"):
        return None
    h, a = ft
    res = "1" if h > a else "X" if h == a else "2"
    row = {"o": fc["outcome"], "p": fc["p"], "c": fc.get("confidence"), "hit": res == fc["outcome"]}
    if fc.get("scores"):
        row["score_hit"] = fc["scores"][0]["score"] == f"{h}-{a}"
    if fc.get("goals"):
        row["ou_hit"] = (h + a > 2) == (fc["goals"]["market"] == "O2.5")
        row["ou_p"] = fc["goals"]["p"]
    if fc.get("btts"):
        row["btts_hit"] = (h > 0 and a > 0) == (fc["btts"]["market"] == "BTTS_Y")
        row["btts_p"] = fc["btts"]["p"]
    return row


def grade_from_markets(markets: list[dict] | None, score: str | None) -> dict | None:
    """Tahmin bloğu yazılmadan önceki geçmiş satırları için: saklı piyasa ima olasılıklarından (q) geriye dönük puan."""
    if not markets or not score:
        return None
    q = {r["m"]: r.get("q") for r in markets if r.get("m") in ("1", "X", "2", "O2.5", "BTTS_Y") and r.get("q")}
    if not all(k in q for k in ("1", "X", "2")):
        return None
    try:
        h, a = (int(x) for x in score.split("-"))
    except ValueError:
        return None
    s = q["1"] + q["X"] + q["2"]
    p3 = {k: q[k] / s for k in ("1", "X", "2")}
    o = max(p3, key=p3.get)
    row = {"o": o, "p": round(p3[o], 4), "c": confidence(p3[o]), "hit": o == ("1" if h > a else "X" if h == a else "2"),
           "retro": True}
    if "O2.5" in q:
        row["ou_hit"] = (h + a > 2) == (q["O2.5"] >= 0.5)
        row["ou_p"] = round(max(q["O2.5"], 1 - q["O2.5"]), 4)
    if "BTTS_Y" in q:
        row["btts_hit"] = (h > 0 and a > 0) == (q["BTTS_Y"] >= 0.5)
        row["btts_p"] = round(max(q["BTTS_Y"], 1 - q["BTTS_Y"]), 4)
    return row


def summarize(rows: list[dict], wilson) -> dict:
    """Karne özeti: tahmin isabeti (genel, güven kademesine göre), skor / Alt-Üst / KG isabeti."""
    fcs = [r["fc"] for r in rows if r.get("fc")]

    def agg(xs: list[dict], key: str = "hit", pkey: str = "p") -> dict:
        ys = [x for x in xs if x.get(key) is not None]
        n, k = len(ys), sum(1 for x in ys if x[key])
        ps = [x[pkey] for x in ys if x.get(pkey) is not None]
        return {"n": n, "hit_rate": round(k / n, 4) if n else None, "hit_ci": wilson(k, n) if n else None,
                "avg_p": round(sum(ps) / len(ps), 4) if ps else None}

    out = agg(fcs)
    out["by_conf"] = [dict(conf=c, **agg([x for x in fcs if x.get("c") == c])) for c in ("yüksek", "orta", "düşük")]
    out["score"] = agg(fcs, "score_hit", "_")
    out["goals"] = agg(fcs, "ou_hit", "ou_p")
    out["btts"] = agg(fcs, "btts_hit", "btts_p")
    out["n_retro"] = sum(1 for x in fcs if x.get("retro"))
    return out
