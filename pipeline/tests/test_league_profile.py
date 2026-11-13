"""Lig profili ve kademe testleri: büzme, kademe kuralı, bilinmeyen kimlikler, eksik dosyalar, önbellek."""
import json

import pytest

from ozbet import config, league_profile as lp


@pytest.fixture(autouse=True)
def fresh_cache():
    lp.clear_cache()
    yield
    lp.clear_cache()


def write(d, lid, scores, start=1):
    """scores: [(ev, dep), ...] → results-{lid}.json; her maç ayrı tarih/takım."""
    rows = [{"date": f"2026-{1 + (start + i) // 28:02d}-{1 + (start + i) % 28:02d}", "home": f"H{i}", "away": f"A{i}",
             "ft": [h, a], "ht": None, "src": "test"} for i, (h, a) in enumerate(scores)]
    d.mkdir(parents=True, exist_ok=True)
    (d / f"results-{lid}.json").write_text(json.dumps({"league": lid, "rows": rows}), encoding="utf-8")
    return rows


# ---------- büzme ----------

def test_shrink_formula():
    assert lp.shrink(0.5, 0, 0.26, 200) == 0.26
    assert lp.shrink(0.5, 200, 0.26, 200) == pytest.approx(0.38)
    assert lp.shrink(0.5, 10**9, 0.26, 200) == pytest.approx(0.5, abs=1e-6)
    assert lp.shrink(0.5, -5, 0.26, 200) == 0.26


def test_small_sample_stays_near_prior(tmp_path):
    # 10 maçın hepsi 0-0: ham beraberlik %100 ama büzülmüş değer öncüle yakın kalmalı
    write(tmp_path, "XX1", [(0, 0)] * 10)
    p = lp.league_profile("XX1", tmp_path)
    pool = lp.pooled_prior(tmp_path)
    assert p["n"] == 10
    assert p["draw_rate"] == pytest.approx((10 * 1.0 + 200 * pool["draw_rate"]) / 210, abs=1e-3)
    assert p["draw_rate"] < 0.32
    assert p["goals_avg"] == pytest.approx((10 * 0.0 + 60 * pool["goals_avg"]) / 70, abs=1e-3)
    assert lp.draw_prior("XX1", tmp_path) == p["draw_rate"]
    assert lp.goals_prior("XX1", tmp_path) == p["goals_avg"]


def test_large_sample_moves_to_observed(tmp_path):
    # 2000 maç, hepsi 2-1: gözlem ağır basmalı
    write(tmp_path, "BIG", [(2, 1)] * 2000)
    p = lp.league_profile("BIG", tmp_path)
    assert p["home_win_rate"] > 0.9 and p["draw_rate"] < 0.03
    assert p["goals_avg"] > 2.95 and p["btts_rate"] > 0.9 and p["o25_rate"] > 0.9
    assert p["home_adv"] > 0.9


def test_outcome_rates_sum_to_one_and_fields(tmp_path):
    write(tmp_path, "XX1", [(1, 0), (0, 0), (1, 2), (3, 3), (2, 0)])
    p = lp.league_profile("XX1", tmp_path)
    assert set(p) == {"n", "goals_avg", "draw_rate", "home_win_rate", "away_win_rate", "btts_rate", "o25_rate",
                      "home_adv", "updated"}
    assert p["home_win_rate"] + p["draw_rate"] + p["away_win_rate"] == pytest.approx(1.0, abs=2e-4)
    assert p["updated"] == "2026-01-06"


def test_pooled_prior_base_and_blend(tmp_path):
    # arşiv yokken sabit taban
    assert lp.pooled_prior(tmp_path / "yok")["draw_rate"] == lp.BASE_PRIOR["draw_rate"]
    lp.clear_cache()
    write(tmp_path, "XX1", [(0, 0)] * 500)
    pool = lp.pooled_prior(tmp_path)
    assert pool["n"] == 500
    assert pool["draw_rate"] == pytest.approx((500 * 1.0 + 500 * 0.26) / 1000, abs=1e-4)


def test_bad_rows_and_duplicates_skipped(tmp_path):
    rows = write(tmp_path, "XX1", [(1, 0), (2, 2)])
    rows += [rows[0], {"date": "2026-02-01", "home": "a", "away": "b", "ft": None}, {"ft": ["x", 1]}, "bozuk",
             {"date": "2026-02-02", "home": "a", "away": "b", "ft": [-1, 0]}]
    (tmp_path / "results-XX1.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")
    assert lp.league_profile("XX1", tmp_path)["n"] == 2


# ---------- kademe ----------

def test_tier_config_rules(tmp_path):
    for lid in ("TR1", "ENG1", "ESP1", "ITA1", "GER1", "FRA1", "ENG2", "NED1", "POR1", "SCO2"):
        assert lp.league_tier(lid, tmp_path) == "A", lid
    for lid in ("TR2", "AUT1", "NOR1", "BRA1", "USA1"):
        assert lp.league_tier(lid, tmp_path) == "B", lid
    for lid in ("UCL", "UEL", "UECL"):
        assert lp.league_tier(lid, tmp_path) == "C", lid


def test_every_config_league_has_tier(tmp_path):
    tiers = lp.all_tiers(tmp_path)
    assert set(tiers) == set(config.LEAGUE_BY_ID)
    assert set(tiers.values()) == {"A", "B", "C"}
    for lid, lg in config.LEAGUE_BY_ID.items():
        if lg.cup:
            assert tiers[lid] == "C"
        elif lg.fd_code:
            assert tiers[lid] == "A"
        else:
            assert tiers[lid] == "B"


def test_tier_unknown_ids(tmp_path):
    for lid in ("OTHER", "other", "", "  ", None, 123, "ZZZ9", "Kadınlar Süper Ligi", ["TR1"]):
        assert lp.league_tier(lid, tmp_path) == "C", lid
        assert lp.tier_reason(lid, tmp_path).startswith("C kademe")
        assert lp.league_profile(lid, tmp_path) is None
    # bilinmeyen ligde öncüller havuz değerine düşer
    assert lp.draw_prior("ZZZ9", tmp_path) == lp.BASE_PRIOR["draw_rate"]
    assert lp.goals_prior(None, tmp_path) == lp.BASE_PRIOR["goals_avg"]


def test_tier_archive_thresholds(tmp_path):
    write(tmp_path, "NEW1", [(1, 0)] * (config.ARCHIVE_MIN_MATCHES - 1))
    write(tmp_path, "NEW2", [(1, 0)] * config.ARCHIVE_MIN_MATCHES)
    write(tmp_path, "NEW3", [(1, 0)] * (lp.TIER_A_MIN_MATCHES - 1))
    write(tmp_path, "NEW4", [(1, 0)] * lp.TIER_A_MIN_MATCHES)
    write(tmp_path, "TR2", [(1, 0)] * lp.TIER_A_MIN_MATCHES)
    write(tmp_path, "UEL", [(1, 0)] * 500)
    assert lp.league_tier("NEW1", tmp_path) == "C"
    assert lp.league_tier("NEW2", tmp_path) == "B"
    assert lp.league_tier("NEW3", tmp_path) == "B"
    assert lp.league_tier("NEW4", tmp_path) == "A"
    assert lp.league_tier("TR2", tmp_path) == "A"      # config B ligi arşivle A'ya çıkar
    assert lp.league_tier("UEL", tmp_path) == "C"      # kupa, arşiv ne olursa olsun C
    assert "59 maç" in lp.tier_reason("NEW1", tmp_path)
    assert "300 maç" in lp.tier_reason("NEW4", tmp_path)


def test_tier_reason_turkish_and_prefixed(tmp_path):
    for lid in ("TR1", "TR2", "AUT1", "UEL", "OTHER", "ZZZ9"):
        r = lp.tier_reason(lid, tmp_path)
        assert r.startswith(f"{lp.league_tier(lid, tmp_path)} kademe · ") and len(r) < 120
    assert "Kupa" in lp.tier_reason("UEL", tmp_path)
    assert "şut" in lp.tier_reason("AUT1", tmp_path)


# ---------- eksik / bozuk dosyalar ----------

def test_missing_dir_is_tolerated(tmp_path):
    d = tmp_path / "hic" / "yok"
    assert lp.league_profile("TR1", d) is None
    assert lp.league_tier("TR1", d) == "A"
    assert lp.league_tier("ZZZ9", d) == "C"
    assert lp.draw_prior("TR1", d) == lp.BASE_PRIOR["draw_rate"]
    assert lp.archive_matches("TR1", d) == 0


def test_corrupt_files_are_skipped(tmp_path):
    write(tmp_path, "XX1", [(1, 1)] * 3)
    (tmp_path / "results-BAD.json").write_text("{bozuk json", encoding="utf-8")
    (tmp_path / "results-LST.json").write_text("[1, 2]", encoding="utf-8")
    (tmp_path / "results-NOR.json").write_text('{"rows": "yok"}', encoding="utf-8")
    assert lp.league_profile("XX1", tmp_path)["n"] == 3
    for lid in ("BAD", "LST", "NOR"):
        assert lp.league_profile(lid, tmp_path) is None
        assert lp.league_tier(lid, tmp_path) == "C"


# ---------- önbellek / import ----------

def test_cache_loads_once_and_clear_reloads(tmp_path):
    write(tmp_path, "XX1", [(1, 0)] * 4)
    before = lp._load_count
    assert lp.league_profile("XX1", tmp_path)["n"] == 4
    lp.league_tier("XX1", tmp_path); lp.draw_prior("XX1", tmp_path); lp.tier_reason("XX1", tmp_path)
    assert lp._load_count == before + 1
    # dosya değişse de önbellek aynı kalır; clear_cache sonrası yeni veri okunur
    write(tmp_path, "XX1", [(1, 0)] * 9)
    assert lp.league_profile("XX1", tmp_path)["n"] == 4
    lp.clear_cache()
    assert lp.league_profile("XX1", tmp_path)["n"] == 9
    assert lp._load_count == before + 2


def test_cache_is_per_directory(tmp_path):
    write(tmp_path / "a", "XX1", [(1, 0)] * 2)
    write(tmp_path / "b", "XX1", [(1, 0)] * 5)
    assert lp.league_profile("XX1", tmp_path / "a")["n"] == 2
    assert lp.league_profile("XX1", tmp_path / "b")["n"] == 5


def test_profile_returns_copy(tmp_path):
    write(tmp_path, "XX1", [(1, 0)] * 2)
    lp.league_profile("XX1", tmp_path)["n"] = 999
    assert lp.league_profile("XX1", tmp_path)["n"] == 2


def test_no_io_at_import():
    # import sonrası (önbellek temizken) hiçbir dizin yüklenmemiş olmalı
    assert lp._cache == {}


def test_default_dir_points_to_repo_archive():
    d = lp.default_archive_dir()
    assert d.parts[-2:] == ("data", "archive")
    assert (d.parents[1] / "pipeline" / "ozbet" / "league_profile.py").exists()
    # gerçek depo verisiyle uçtan uca: hata vermeden çalışır, oranlar makul aralıkta
    for lid in ("TR1", "UEL", "OTHER"):
        assert lp.league_tier(lid) in ("A", "B", "C")
        assert 0.15 < lp.draw_prior(lid) < 0.40
        assert 1.8 < lp.goals_prior(lid) < 3.6
