"""Keskin Fark ajanı (S1 hipotezi) ve fixtures.csv `books` ayrıştırması — sentetik satırlarla."""
from datetime import date, datetime, timedelta

import pytest

from ozbet import config
from ozbet.agents import sharp_edge as se
from ozbet.agents.market import shin
from ozbet.sources import football_data as fd
from ozbet.sources.base import Fixture

DAY = date(2026, 11, 14)
HEAD = ("Div,Date,Time,HomeTeam,AwayTeam,B365H,B365D,B365A,PSH,PSD,PSA,MaxH,MaxD,MaxA,AvgH,AvgD,AvgA,"
        "BFEH,BFED,BFEA,B365>2.5,B365<2.5,P>2.5,P<2.5,Max>2.5,Max<2.5,Avg>2.5,Avg<2.5,BFE>2.5,BFE<2.5,"
        "AHh,B365AHH,B365AHA,PAHH,PAHA")
ROW = ("E0,14/11/2026,15:00,Arsenal,Chelsea,2.05,3.50,3.60,2.10,3.55,3.70,2.15,3.65,3.80,2.06,3.50,3.62,"
       "2.14,3.65,3.80,1.80,2.00,1.85,2.03,1.88,2.06,1.82,2.00,1.87,2.08,-0.5,2.05,1.85,2.07,1.86")


class FakeClient:
    def __init__(self, text):
        self.text = text

    def get(self, url, ttl=None):
        return self.text


def _csv(drop=(), row=ROW, head=HEAD):
    """Verilen önekle başlayan kolonları başlıktan ve satırdan çıkarır (2026-27'de PS* olmaması gibi)."""
    cols, vals = head.split(","), row.split(",")
    keep = [i for i, c in enumerate(cols) if not any(c.startswith(d) for d in drop)]
    return ",".join(cols[i] for i in keep) + "\n" + ",".join(vals[i] for i in keep) + "\n"


def _fx(drop=(), **kw):
    out = fd.fixtures(FakeClient(_csv(drop, **kw)), DAY)
    assert len(out) == 1
    return out[0]


def _iddaa(fx, odds, home="Arsenal", away="Chelsea", source="nesine", shift=timedelta(0), extra=None):
    return Fixture("EN1", "İngiltere Premier Lig", fx.kickoff + shift, home, away, source, "t", code="1",
                   odds=dict(odds), extra=extra or {})


def _match():
    return {"status": "scheduled", "flags": [], "provenance": {}}


# iddaa'nın tipik (%~8-10 marjlı) oranları: hiçbir markette fark yok
DULL = {"1": 1.95, "X": 3.20, "2": 3.35, "O2.5": 1.70, "U2.5": 1.85}


# ---------------- ayrıştırıcı ----------------
def test_books_all_columns():
    fx = _fx()
    b = fx.extra["books"]
    assert set(b) == {"PS", "BFE", "Avg", "Max", "B365", "ah_line"}
    assert b["PS"] == {"1": 2.10, "X": 3.55, "2": 3.70, "O2.5": 1.85, "U2.5": 2.03, "AHH": 2.07, "AHA": 1.86}
    assert b["BFE"] == {"1": 2.14, "X": 3.65, "2": 3.80, "O2.5": 1.87, "U2.5": 2.08}
    assert b["ah_line"] == -0.5 and fx.extra["time_known"] is True
    assert fx.odds["1"] == 2.06          # eski davranış (Avg yedek oran) bozulmadı
    assert fx.kickoff.astimezone(config.TZ).hour == 18


def test_books_tolerates_missing_and_blank_columns():
    b = _fx(drop=("PS", "P>", "P<", "PAH")).extra["books"]
    assert "PS" not in b and "BFE" in b
    # yarım grup (PSD boş) yazılmaz; saat bozuksa time_known False
    row = ROW.replace("2.10,3.55,3.70", "2.10,,3.70").replace("15:00", "")
    fx = _fx(row=row)
    assert "1" not in fx.extra["books"]["PS"] and fx.extra["books"]["PS"]["O2.5"] == 1.85
    assert fx.extra["time_known"] is False
    assert _fx(drop=("B365", "PS", "P", "Max", "Avg", "BFE", "AHh")).extra["books"] == {}


# ---------------- kaynak önceliği ----------------
def test_all_columns_uses_pinnacle(monkeypatch):
    from ozbet import config as _c
    monkeypatch.setattr(_c, "PICK_MAX_ODDS", 5.0)   # bu test 4.00 oranlı örnekle formülü sınar; bant üst sınırı ayrı testte
    fx = _fx()
    odds = {**DULL, "2": 4.00}           # deplasman iddaa'da keskin piyasadan yüksek
    m = _match()
    blk = se.attach(m, _iddaa(fx, odds), [fx])
    assert blk is m["sharp"] and blk["source"] == "pinnacle" and "allowance" not in blk
    p = dict(zip(("1", "X", "2"), shin([2.10, 3.55, 3.70])))
    assert blk["fair"]["2"] == pytest.approx(p["2"], abs=1e-4)
    assert blk["edge"]["2"] == pytest.approx(4.00 * p["2"] - 1, abs=1e-4)
    assert set(blk["edge"]) == {"1", "X", "2", "O2.5", "U2.5"}      # negatifler de kayıtlı
    assert blk["edge"]["1"] < 0 and blk["edge"]["O2.5"] < 0
    assert blk["best"] == {"market": "2", "edge": blk["edge"]["2"], "odds": 4.00, "fair_p": blk["fair"]["2"]}
    assert se.FLAG in m["flags"] and m["provenance"]["sharp"]["t"] == fx.fetched_at
    assert sum(blk["fair"][k] for k in ("1", "X", "2")) == pytest.approx(1, abs=1e-3)


def test_ps_missing_falls_back_to_betfair_with_allowance(monkeypatch):
    from ozbet import config as _c
    monkeypatch.setattr(_c, "PICK_MAX_ODDS", 5.0)   # bu test 4.00 oranlı örnekle formülü sınar; bant üst sınırı ayrı testte
    fx = _fx(drop=("PS", "P>", "P<", "PAH"))
    m = _match()
    blk = se.attach(m, _iddaa(fx, {**DULL, "2": 4.10}), [fx])
    assert blk["source"] == "betfair" and blk["allowance"] == 0.02
    p2 = shin([2.14, 3.65, 3.80])[2]
    assert blk["edge"]["2"] == pytest.approx(4.10 * p2 - 1 - 0.02, abs=1e-4)
    assert blk["best"]["market"] == "2"


def test_only_avg():
    fx = _fx(drop=("PS", "P>", "P<", "PAH", "BFE"))
    blk = se.attach(_match(), _iddaa(fx, DULL), [fx])
    assert blk["source"] == "avg" and blk["best"] is None
    assert all(e < 0 for e in blk["edge"].values())


def test_mixed_sources_per_group():
    # 1X2 Pinnacle'da var, Alt/Üst yalnız Avg'de
    fx = _fx(drop=("P>", "P<", "BFE>", "BFE<"))
    blk = se.attach(_match(), _iddaa(fx, DULL), [fx])
    assert blk["source"] == "pinnacle" and blk["source_ou25"] == "avg" and blk["allowance"] == 0.02


# ---------------- korumalar ----------------
def test_team_mismatch_no_sharp_key():
    fx = _fx()
    m = _match()
    assert se.attach(m, _iddaa(fx, {**DULL, "2": 4.0}, home="Arsenal", away="Everton"), [fx]) is None
    assert "sharp" not in m and m["flags"] == []


def test_kickoff_mismatch_and_ambiguous_match():
    fx = _fx()
    m = _match()
    assert se.attach(m, _iddaa(fx, DULL, shift=timedelta(hours=3)), [fx]) is None
    assert se.attach(m, _iddaa(fx, DULL), [fx, _fx()]) is None      # iki aday → emin değiliz
    assert "sharp" not in m
    # saat bilinmiyorsa: aynı gün + birebir takım anahtarı yeter
    fx2 = _fx(row=ROW.replace("15:00", ""))
    assert se.attach(_match(), _iddaa(fx2, DULL, shift=timedelta(hours=6)), [fx2]) is not None


def test_implausible_edge_recorded_as_note():
    fx = _fx()
    m = _match()
    blk = se.attach(m, _iddaa(fx, {**DULL, "2": 5.50}), [fx])
    assert blk["edge"]["2"] > se.MAX_EDGE and blk["best"] is None
    assert blk["notes"] and "olağan dışı" in blk["notes"][0]
    assert se.FLAG not in m["flags"]


def test_odds_below_floor_and_buffer():
    fx = _fx()
    # Üst 2.5 iddaa'da 1.58 → fark pozitif olsa da oran tabanının altında
    row = ROW.replace("1.85,2.03", "1.50,2.70")
    fx = _fx(row=row)
    m = _match()
    blk = se.attach(m, _iddaa(fx, {**DULL, "O2.5": 1.58, "U2.5": 2.20}), [fx])
    assert blk["edge"]["O2.5"] >= se.MIN_EDGE and blk["best"] is None and se.FLAG not in m["flags"]
    # tamponun altındaki küçük pozitif fark seçilmez
    p2 = shin([2.10, 3.55, 3.70])[2]
    fx = _fx()
    blk = se.attach(_match(), _iddaa(fx, {**DULL, "2": round(1.005 / p2, 2)}), [fx])
    assert 0 < blk["edge"]["2"] < se.MIN_EDGE and blk["best"] is None


def test_only_real_iddaa_odds_are_compared():
    fx = _fx()
    # birincil kaynak football-data ise (iddaa oranı yok) kıyas yapılmaz
    assert se.attach(_match(), _iddaa(fx, DULL, source="football-data.co.uk"), [fx]) is None
    # Alt/Üst yedek kaynaktan doldurulmuşsa yalnız 1X2 kıyaslanır
    f = _iddaa(fx, DULL, extra={"odds_sources": {"O2.5": "football-data.co.uk", "U2.5": "football-data.co.uk"}})
    blk = se.attach(_match(), f, [fx])
    assert set(blk["edge"]) == {"1", "X", "2"}
    # biten maç ve bozuk referans (toplam ima olasılık saçma) → blok yok
    assert se.attach({"status": "finished", "flags": []}, _iddaa(fx, DULL), [fx]) is None
    assert se.compute(DULL, {"PS": {"1": 5.0, "X": 6.0, "2": 7.0}}) is None
    assert se.compute(DULL, {}) is None and se.compute(None, fx.extra["books"]) is None


def test_status_row():
    assert se.status([{"id": "a"}]).status == "skipped"
    fx = _fx()
    m = _match()
    se.attach(m, _iddaa(fx, {**DULL, "2": 4.0}), [fx])
    st = se.status([m, {"id": "b"}])
    assert st.status == "ok" and st.items == 1 and "pinnacle 1" in st.note
