"""Casos reals revisats: cada regla del control de qualitat (guia, capítol 5)."""

import numpy as np
import pandas as pd

from qualitat import Parametres, control_qualitat

P = Parametres()


def _df(values, start="2020-01-01", freq="5min", factor=None):
    t = pd.date_range(start, periods=len(values), freq=freq, tz="UTC")
    d = pd.DataFrame({"timestamp": t, "valor": np.asarray(values, dtype=float)})
    if factor is not None:
        d["factor_unitat"] = factor
    return d


def _base(n=288 * 20, level=6.0, seed=0):
    rng = np.random.default_rng(seed)
    # Cabal de base sempre positiu (les sèries reals no tenen negatius)
    return level * (1 + 0.05 * np.sin(np.arange(n) / 300) + rng.normal(0, 0.002, n))


def marcat(out, rule):
    return out["regles"].str.contains(rule, regex=False).to_numpy()


def test_isolated_spikes_like_balsareny_2008():
    v = _base()
    v[3000], v[3002] = 909.98, 1140.82  # dos pics separats per una lectura normal
    out, _ = control_qualitat(_df(v), None, P)
    assert marcat(out, "pic")[[3000, 3002]].all()
    assert marcat(out, "pic").sum() == 2


def test_flash_flood_rising_limb_is_kept():
    # Gavarresa 2022-07-29 (ja en m³/s): de 0,001 a 5 m³/s en 5 min, 1,5 h alt i baixada
    v = np.r_[
        np.full(2000, 0.001),
        np.linspace(2.3, 5.0, 18),
        np.geomspace(2.5, 0.2, 30),
        np.full(2000, 0.2),
    ]
    out, _ = control_qualitat(_df(v), None, P)
    assert out["regles"].eq("").all()


def test_smooth_big_flood_is_kept():
    # Castellbell 1996-11-17: pujada i baixada suau fins a ~970 m³/s
    x = np.linspace(-3, 3, 400)
    v = np.r_[_base(3000, 7.0), 7 + 960 * np.exp(-(x**2)), _base(3000, 9.0, seed=1)]
    out, _ = control_qualitat(_df(v), None, P)
    assert out["regles"].eq("").all()


def test_oscillation_like_mediona_2026():
    v = _base(level=0.02)
    v[5000:5024:2] = 230.0  # 230 i 0,02 alternats durant 2 h
    out, _ = control_qualitat(_df(v), None, P)
    assert marcat(out, "oscil·lacio")[5000:5024].all()


def test_saturated_and_stuck_sensors():
    v = _base(n=288 * 30, level=1.0)
    v[4000 : 4000 + 12 * 7] = 10.67  # 7 h plans amb cabal alt (Monegal 2019-12-20)
    v[6000 : 6000 + 288 * 8] = 2.5  # 8 dies el mateix valor
    out, _ = control_qualitat(_df(v), None, P)
    assert marcat(out, "pla_alt")[4000:4084].all()
    assert marcat(out, "encallat")[6000 : 6000 + 288 * 8].all()


def test_daily_balance_against_official_daily():
    v = _base(n=288 * 5, level=5.3)
    v[288 * 2 : 288 * 3] = 104.0 + np.linspace(0, 1, 288)  # un dia desplaçat (Castellar 2019)
    d = _df(v)
    days = pd.date_range("2020-01-01", periods=5, freq="D", tz="UTC")
    daily = pd.DataFrame({"timestamp": days, "valor": 5.3})
    out, bal = control_qualitat(d, daily, P)
    day = out["timestamp"].dt.floor("D")
    assert marcat(out, "balanc_diari")[(day == days[2]).to_numpy()].all()
    assert not marcat(out, "balanc_diari")[(day != days[2]).to_numpy()].any()
    assert len(bal) == 1


def test_unit_step_flags_both_days():
    v = _base(n=288 * 4, level=5.0)
    f = np.r_[np.full(288 * 2, 1.0), np.full(288 * 2, 0.001)]
    v[288 * 2 :] = 0.3  # a mitjanit, el factor canvia i el valor cau x16 (no prou per marcar)
    out, _ = control_qualitat(_df(v, factor=f), None, P)
    assert not marcat(out, "pas_unitat").any()
    v[288 * 2 :] = 0.005  # x1000: es marquen els dos dies del canvi
    out, _ = control_qualitat(_df(v, factor=f), None, P)
    assert marcat(out, "pas_unitat")[288 : 288 * 3].all()
    assert not marcat(out, "pas_unitat")[:288].any()


def test_exclusions_and_valor_net():
    v = _base(n=288 * 2)
    a, b = pd.Timestamp("2020-01-01 10:00", tz="UTC"), pd.Timestamp("2020-01-01 12:00", tz="UTC")
    out, _ = control_qualitat(_df(v), None, P, exclusions=[(a, b)])
    m = marcat(out, "exclusio")
    assert m.sum() == 25 and out.loc[m, "valor_net"].isna().all()
    assert out.loc[~m, "valor_net"].notna().all()


def test_excursions_like_merles_and_mediona():
    v = _base(n=288 * 30, level=0.16)
    v[300:312] = 127.0  # Merlès 2017-09-27: 1 h a 127 i de tornada a 0,16
    v[600:612] = 230.0  # Mediona 2026-10-03
    out, _ = control_qualitat(_df(v), None, P)
    ex = marcat(out, "excursio")
    assert ex[300:312].all() and ex[600:612].all()
    assert ex.sum() == 24


def test_burst_like_balsareny_1997():
    v = _base(n=288 * 30, level=2.0)
    v[400:407] = [584.7, 1.78, 255.5, 1.96, 621.8, 1.96, 1.78]
    out, _ = control_qualitat(_df(v), None, P)
    assert out.loc[400:405, "valor_net"].isna().sum() >= 3
    assert out.loc[[400, 402, 404], "valor_net"].isna().all()


def test_real_flash_flood_like_vilada_2026_is_kept():
    peak = [
        0.66,
        1.15,
        40.0,
        152.4,
        194.2,
        160.0,
        105.2,
        98.0,
        91.9,
        80.0,
        63.7,
        58.0,
        50.5,
        45.0,
        39.5,
        36.0,
        33.3,
        30.0,
        27.0,
        24.0,
        22.0,
        20.0,
        18.0,
        16.0,
    ]
    v = np.r_[
        _base(2000, 0.12),
        peak,
        np.geomspace(15, 2, 200),
        np.full(500, 2.0) + np.linspace(0, 0.01, 500),
    ]
    out, _ = control_qualitat(_df(v), None, P)
    assert out["regles"].eq("").all()


def test_flood_that_recedes_in_days_is_not_an_excursion():
    # Regressió: amb pandas 3 l'índex és en µs i la finestra de 2 h es tornava de 2000 h
    x = np.linspace(0, 1, 36)
    rise = 0.2 + 120 * x
    fall = 120 * np.exp(-np.linspace(0, 7, 288 * 2)) + 0.2
    v = np.r_[_base(2000, 0.2), rise, fall, _base(2000, 0.2, seed=2)]
    out, _ = control_qualitat(_df(v), None, P)
    assert not marcat(out, "excursio").any()


def test_oscillation_does_not_spread_to_hourly_data():
    t1 = pd.date_range("2009-12-01", periods=100, freq="1h", tz="UTC")
    t2 = pd.date_range(t1[-1] + pd.Timedelta("5min"), periods=48, freq="5min", tz="UTC")
    t3 = pd.date_range(t2[-1] + pd.Timedelta("1h"), periods=100, freq="1h", tz="UTC")
    t = t1.append(t2).append(t3)
    v = np.r_[np.linspace(0.5, 0.6, 100), np.tile([0.05, 180.0], 24), np.linspace(0.5, 0.6, 100)]
    out, _ = control_qualitat(pd.DataFrame({"timestamp": t, "valor": v}), None, P)
    osc = marcat(out, "oscil·lacio")
    assert osc[100:148].all()
    assert not osc[:99].any() and not osc[150:].any()


def test_zero_block_in_flood_like_guardiola_1997():
    flood = np.r_[np.linspace(140, 255, 36), np.zeros(36), np.linspace(252, 150, 48)]
    v = np.r_[_base(3000, 3.0), flood, np.geomspace(150, 3, 300), _base(3000, 3.0, seed=3)]
    out, _ = control_qualitat(_df(v), None, P)
    z = slice(3036, 3072)
    assert marcat(out, "caiguda")[z].all()
    assert not marcat(out, "excursio").any()
    assert out["valor_net"].iloc[3072:3120].notna().all()


def test_repeated_constant_blocks_like_mediona_2026():
    # Blocs de 230,00 exactes d'1 h separats per 0,02: els blocs són l'error, no els zeros
    v = _base(n=288 * 30, level=0.02)
    for s in (5000, 5024, 5048):
        v[s : s + 12] = 230.0
    out, _ = control_qualitat(_df(v), None, P)
    hi = np.r_[5000:5012, 5024:5036, 5048:5060]
    lo = np.r_[5012:5024, 5036:5048]
    assert out["valor_net"].iloc[hi].isna().all()
    assert not marcat(out, "caiguda")[lo].any()


def test_excursion_after_a_gap_like_cardona_2007():
    t = pd.date_range("2007-01-01", periods=288 * 30, freq="5min", tz="UTC")
    v = _base(n=len(t), level=3.2)
    d = pd.DataFrame({"timestamp": t, "valor": v})
    # forat d'1,5 h i després 214, 408, 83 i tornada a 3,26 en 2 h
    gap = (d["timestamp"] > "2007-01-20 07:30") & (d["timestamp"] < "2007-01-20 09:00")
    d = d[~gap].copy()
    for ts, val in [("09:00", 214.4), ("09:55", 408.9), ("10:00", 83.4)]:
        d.loc[d["timestamp"] == pd.Timestamp(f"2007-01-20 {ts}", tz="UTC"), "valor"] = val
    out, _ = control_qualitat(d, None, P)
    m = out["timestamp"] == pd.Timestamp("2007-01-20 09:00", tz="UTC")
    assert out.loc[m, "valor_net"].isna().all()


def test_constant_blocks_with_interleaved_zeros_like_mediona_2026():
    v = _base(n=288 * 30, level=0.02)
    v[5000:5024] = 230.0
    v[[5006, 5015]] = 0.02  # zeros intercalats dins del bloc
    out, _ = control_qualitat(_df(v), None, P)
    assert out["valor_net"].iloc[5000:5024].isna().all()
    assert not marcat(out, "caiguda")[5024:5100].any()


def test_unitats_detecta_litres_per_segon():
    from qualitat import corregeix_unitats

    t = pd.date_range("2020-01-01", "2020-01-20", freq="5min", tz="UTC", inclusive="left")
    q = pd.Series(10.0, index=t)  # cabal real de 10 m³/s...
    q["2020-01-12 06:00":"2020-01-12 09:00"] = 400.0  # ... amb una crescuda curta
    brut = q.copy()
    brut["2020-01-05":"2020-01-15"] *= 1000  # onze dies en L/s (inclou el de la crescuda)
    serie = pd.DataFrame({"timestamp": t, "valor": brut.to_numpy()})
    dies = pd.date_range("2020-01-01", "2020-01-19", freq="D", tz="UTC")
    diari = q.resample("D").mean().reindex(dies).to_frame("valor").reset_index(names="timestamp")
    diari = diari.drop(index=[7, 8])  # dos dies sense diari, dins del tram en L/s
    out, resum = corregeix_unitats(serie, diari)
    assert (out["valor"] - q.to_numpy()).abs().max() < 1e-9
    assert (resum["classe"] == "ls").any() and (resum["classe"] == "sense_referencia").any()
    assert (out["valor_brut"] == serie["valor"]).all()


def test_agrega_etiqueta_el_final_i_no_interpola():
    from qualitat import agrega

    t = pd.date_range("2020-01-01 00:05", periods=12, freq="5min", tz="UTC")
    v = np.r_[np.ones(6), np.full(6, np.nan)]
    out = agrega(pd.DataFrame({"timestamp": t, "valor_net": v}), "30min")
    assert out["timestamp"].iloc[0] == pd.Timestamp("2020-01-01 00:30", tz="UTC")
    assert out["mitjana"].iloc[0] == 1.0
    assert out["mitjana"].isna().iloc[1]  # mitja hora sense lectures: buida
