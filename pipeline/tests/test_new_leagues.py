"""football-data.co.uk "new leagues" okuyucusu + yeni ek ligler (SC1/E2/E3, AUT/DNK/SWE...)."""
from __future__ import annotations

import random
from datetime import date, timedelta

from ozbet import config
from ozbet.agents import simulation
from ozbet.agents.bulletin import league_for
from ozbet.sources import football_data as fd
from ozbet.teams import TeamMatcher

HDR = ("Country,League,Season,Date,Time,Home,Away,HG,AG,Res,PSCH,PSCD,PSCA,MaxCH,MaxCD,MaxCA,"
       "AvgCH,AvgCD,AvgCA,BFECH,BFECD,BFECA")

SWE = ["Malmo FF", "AIK", "Djurgarden", "Hammarby", "Goteborg", "Elfsborg", "Hacken", "Mjallby",
       "Sirius", "Norrkoping"]
DNK = ["FC Copenhagen", "Midtjylland", "Brondby", "Aarhus", "Nordsjaelland", "Silkeborg", "Randers",
       "Viborg", "Odense", "Vejle"]


def _csv(country, league, teams, seasons, start_of) -> str:
    rnd = random.Random(7)
    lines = [HDR]
    for s in seasons:
        d0 = start_of(s)
        k = 0
        for h in teams:
            for a in teams:
                if h == a:
                    continue
                d = d0 + timedelta(days=3 * k); k += 1
                hg, ag = rnd.choice([0, 1, 1, 2, 2, 3]), rnd.choice([0, 0, 1, 1, 2])
                res = "H" if hg > ag else ("A" if ag > hg else "D")
                lines.append(f"{country},{league},{s},{d:%d/%m/%Y},18:00,{h},{a},{hg},{ag},{res},"
                             "2.1,3.4,3.6,2.2,3.6,3.8,2.05,3.35,3.5,2.15,3.5,3.7")
    return "\n".join(lines) + "\n"


class FakeClient:
    def __init__(self, files):
        self.files, self.urls = files, []

    def get(self, url, **kw):
        self.urls.append(url)
        for k, v in self.files.items():
            if url.endswith(k):
                return v
        raise RuntimeError("404 " + url)


SEASONS = config.season_codes(date(2026, 11, 7))   # 2627, 2526, 2425


def _swe():
    return _csv("Sweden", "Allsvenskan", SWE, ["2022", "2023", "2024", "2025", "2026"],
                lambda s: date(int(s), 3, 30))


def _dnk():
    return _csv("Denmark", "Superliga", DNK, ["2022/2023", "2023/2024", "2024/2025", "2025/2026", "2026/2027"],
                lambda s: date(int(s[:4]), 7, 20))


def test_summer_years_mapping():
    assert config.summer_years(SEASONS) == [2027, 2026, 2025, 2024]
    assert config.summer_label(2026) == SEASONS[0]
    assert fd._new_season_label("2025/2026", False) == "2526"
    assert fd._new_season_label("2025", True) == "2526"
    assert fd._new_season_label(2025.0, True) == "2526"
    assert fd._new_season_label("abc", True) is None


def test_history_new_summer_and_european():
    c = FakeClient({"new/SWE.csv": _swe(), "new/DNK.csv": _dnk()})
    swe = fd.history_new(c, "SWE", SEASONS)
    assert c.urls[-1].endswith("/new/SWE.csv")
    assert {r["season"] for r in swe} == {"2627", "2526", "2425"}   # 2022/2023 dışarıda
    assert len(swe) == 3 * 90
    r = swe[0]
    assert r["hthg"] is None and r["hst"] is None and r["hs"] is None
    assert r["odds_close"] == {"1": 2.05, "X": 3.35, "2": 3.5}
    dnk = fd.history_new(c, "DNK", SEASONS)
    assert {r["season"] for r in dnk} == {"2627", "2526", "2425"}


def test_model_without_ht_and_shots():
    rows = fd.history_new(FakeClient({"new/DNK.csv": _dnk()}), "DNK", SEASONS)
    ref = date(2026, 11, 7)
    M = simulation.build("DEN1", rows, ref)
    assert M is not None
    assert M.goals.ht_share == 0.44           # İY verisi yok → varsayılan
    assert M.shots is None                    # şut yok → şut harmanı devre dışı
    p = simulation.predict("Brøndby IF", "F.C. København", "DEN1", {"DEN1": M}, None, "k")
    assert p is not None
    assert not any("Şut" in n for n in p.get("notes", []))


def test_team_matcher_new_league_names():
    tm = TeamMatcher(SWE + DNK)
    assert tm.match("Malmö FF") == "Malmo FF"
    assert tm.match("Djurgårdens IF") == "Djurgarden"
    assert tm.match("IFK Göteborg") == "Goteborg"
    assert tm.match("BK Häcken") == "Hacken"
    assert tm.match("Brøndby IF") == "Brondby"
    assert tm.match("FC Midtjylland") == "Midtjylland"
    assert tm.match("FC Nordsjælland") == "Nordsjaelland"


def test_main_file_new_codes_sc1():
    sc1 = ("Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,HS,AS,HST,AST,AvgH,AvgD,AvgA\n"
           "SC1,02/08/2025,15:00,Partick,Raith Rvs,2,1,H,1,0,H,12,8,5,3,2.1,3.3,3.4\n"
           "SC1,02/08/2025,15:00,St Johnstone,Ayr,1,1,D,0,1,A,10,9,4,4,1.9,3.4,3.9\n")
    rows = fd.history(FakeClient({"2526/SC1.csv": sc1}), "SC1", ["2526"])
    assert len(rows) == 2 and rows[0]["hthg"] == 1
    assert {"SCO2", "ENG3", "ENG4", "GRE1", "ITA2", "ESP2", "FRA2"} <= set(config.LEAGUE_BY_ID)


def test_league_aliases_from_bulletin():
    ok = {
        "İskoçya Championship": "SCO2", "Danimarka Süper Ligi": "DEN1", "Avusturya Bundesliga": "AUT1",
        "Polonya Ekstraklasa": "POL1", "Romanya 1. Lig": "ROU1", "Rusya Premier Lig": "RUS1",
        "İsveç Allsvenskan": "SWE1", "Brezilya Serie A": "BRA1", "Arjantin Primera LPF, Kapanış": "ARG1",
    }
    for raw, lid in ok.items():
        assert league_for(raw) == lid, raw
    # İkinci kademeler / kadın / alt gruplar asla üst lige düşmez
    for raw in ["Danimarka 1. Lig", "Danimarka 2. Ligi", "Avusturya 2. Lig", "Polonya 1. Lig",
                "İsviçre Challenge Ligi", "Romanya 2. Lig", "Brezilya Serie B", "İsveç Damallsvenskan, Kadınlar",
                "Arjantin Primera A Kapanış, Kadınlar", "Rusya 1. Lig", "İngiltere 1. Lig"]:
        assert league_for(raw) is None, raw
    assert league_for("Premier Lig") == "ENG1"   # eski davranış korunur
