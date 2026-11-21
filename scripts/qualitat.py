"""Correcció d'unitats i control de qualitat dels cabals de 5 minuts.

No s'executa sol: el fa servir 05_neteja.py. Explicació de cada pas i dels casos reals que
justifiquen els llindars: guia/05-processat-i-filtratge.md

Entrada: una taula amb les columnes timestamp (UTC) i valor (cabal tal com ve del portal),
i el cabal diari oficial (timestamp, valor) de la mateixa estació.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Pas 3. Unitats (L/s → m³/s)
# --------------------------------------------------------------------------- #
TOLERANCIA_UNITAT = 0.7  # marge en log10 al voltant de x1 (m³/s) i x1000 (L/s)
DIARI_MINIM = 0.01  # m³/s; per sota, el quocient no és fiable (riu sec)


def factors_unitat(serie: pd.DataFrame, diari: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
    """Factor per lectura (1 si és en m³/s, 0,001 si és en L/s), decidit per dies sencers.

    q = log10(mitjana de les lectures del dia / cabal diari oficial): ~0 → m³/s, ~3 → L/s.
    Els dies sense classe clara prenen la unitat majoritària dels ±15 dies del voltant.
    """
    t = pd.DatetimeIndex(serie["timestamp"])
    dia = t.floor("D")
    mitjana = pd.Series(serie["valor"].to_numpy(dtype=float), index=dia).groupby(level=0).mean()
    oficial = pd.Series(
        diari["valor"].to_numpy(dtype=float), index=pd.DatetimeIndex(diari["timestamp"]).floor("D")
    )
    oficial = oficial[~oficial.index.duplicated(keep="last")].reindex(mitjana.index)
    with np.errstate(divide="ignore", invalid="ignore"):
        q = np.log10(mitjana / oficial).where((oficial > DIARI_MINIM) & (mitjana > 0))
    classe = pd.Series("sense_referencia", index=mitjana.index, dtype=object)
    classe[(q - 0).abs() < TOLERANCIA_UNITAT] = "m3s"
    classe[(q - 3).abs() < TOLERANCIA_UNITAT] = "ls"
    classe[(q >= TOLERANCIA_UNITAT) & (q <= 3 - TOLERANCIA_UNITAT)] = "mixt"
    classe[(q < -TOLERANCIA_UNITAT) | (q > 3 + TOLERANCIA_UNITAT)] = "estrany"
    nivell = pd.Series(np.nan, index=mitjana.index)
    nivell[classe == "m3s"] = 0.0
    nivell[classe == "ls"] = 3.0
    tots = pd.date_range(mitjana.index.min(), mitjana.index.max(), freq="D")
    veins = nivell.reindex(tots).rolling(31, center=True, min_periods=3).median()
    nivell = nivell.fillna(veins.reindex(mitjana.index)).ffill().bfill().fillna(0.0)
    factor_dia = pd.Series(np.where(nivell >= 1.5, 0.001, 1.0), index=mitjana.index)
    resum = pd.DataFrame({"classe": classe, "factor": factor_dia, "log10_quocient": q})
    return factor_dia.reindex(dia).to_numpy(), resum


def corregeix_unitats(
    serie: pd.DataFrame, diari: pd.DataFrame | None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Afegeix valor_brut i factor_unitat, i deixa valor en m³/s."""
    if diari is None or diari.empty:
        return serie.assign(valor_brut=serie["valor"], factor_unitat=1.0), pd.DataFrame()
    f, resum = factors_unitat(serie, diari)
    out = serie.assign(valor_brut=serie["valor"], factor_unitat=f)
    out["valor"] = out["valor_brut"] * out["factor_unitat"]
    return out, resum


# --------------------------------------------------------------------------- #
# Pas 4. Control de qualitat
# --------------------------------------------------------------------------- #
@dataclass
class Parametres:
    """Llindars de les regles (els valors per defecte són els de la guia)."""

    pic_factor: float = 4.0  # pic: > 4 x la mediana de les 3 lectures d'abans i de després...
    pic_minim: float = 5.0  # ... + 5 m³/s, i per sobre del percentil 99 de l'estació
    caiguda_factor: float = 10.0  # caiguda: < 1/10 dels veïns...
    caiguda_minim: float = 1.0  # ... quan els veïns porten > 1 m³/s
    zero_maxim: float = 0.02  # tram a zero (≤ 0,02 m³/s) enmig d'aigua...
    zero_tornada_h: float = 6.0  # ... que es recupera en menys de 6 h
    excursio_factor: float = 10.0  # excursió: > x10 el nivell de l'hora anterior...
    excursio_tornada_h: float = 3.0  # ... i de tornada a < 2x aquell nivell en < 3 h
    oscillacio_quocient: float = 20.0  # salts de x20 entre lectures consecutives...
    oscillacio_salts: int = 3  # ... 3 o més dins d'una hora
    encallat_dies: float = 7.0  # el mateix valor 7 dies o més...
    encallat_minim: float = 0.5  # ... amb > 0,5 m³/s
    pla_alt_hores: float = 6.0  # el mateix valor 6 h o més...
    pla_alt_quantil: float = 0.95  # ... per sobre del percentil 95
    pas_unitat_quocient: float = 100.0  # salt de x100 on canvia el factor d'unitat
    balanc_quocient: float = 3.0  # mitjana del dia vs diari oficial: x3 o /3
    balanc_diari_minim: float = 0.05
    balanc_cobertura: float = 0.8  # el dia ha de tenir el 80 % de les mitges hores


REGLES = [
    "excursio",
    "pic",
    "caiguda",
    "oscil·lacio",
    "encallat",
    "pla_alt",
    "pas_unitat",
    "balanc_diari",
    "exclusio",
]


def _nanosegons(t: pd.DatetimeIndex) -> np.ndarray:
    return t.as_unit("ns").asi8  # pandas 3 pot desar les dates en µs


def medianes_veines(x: pd.Series, k: int = 3) -> tuple[np.ndarray, np.ndarray]:
    abans = x.shift(1).rolling(k, min_periods=1).median().to_numpy()
    despres = x[::-1].shift(1).rolling(k, min_periods=1).median()[::-1].to_numpy()
    return abans, despres


def regla_pic_i_caiguda(x: pd.Series, p: Parametres, p99: float) -> tuple[np.ndarray, np.ndarray]:
    abans, despres = medianes_veines(x)
    v = x.to_numpy()
    pic = (v > p.pic_factor * np.fmax(abans, despres) + p.pic_minim) & (v > p99)
    veins = np.fmin(abans, despres)
    caiguda = (veins > p.caiguda_minim) & (v < veins / p.caiguda_factor)
    return np.nan_to_num(pic).astype(bool), np.nan_to_num(caiguda).astype(bool)


def _marca_finestres(t: pd.DatetimeIndex, final: np.ndarray, amplada: str) -> np.ndarray:
    """Marca les lectures dins d'alguna finestra (t_final - amplada, t_final] marcada."""
    if not final.any():
        return np.zeros(len(t), dtype=bool)
    ns = _nanosegons(t)
    inv = pd.Series(final[::-1].astype(float), index=pd.to_datetime(ns[-1] - ns[::-1], unit="ns"))
    return inv.rolling(amplada, closed="both").max().to_numpy()[::-1] > 0


def regla_oscillacio(t: pd.DatetimeIndex, x: pd.Series, p: Parametres) -> np.ndarray:
    v = x.to_numpy()
    anterior = np.r_[np.nan, v[:-1]]
    baix = np.fmax(np.fmin(v, anterior), 1e-3)
    salt = ((np.fmax(v, anterior) / baix) > p.oscillacio_quocient).astype(float)
    n = pd.Series(salt, index=t).rolling("1h").sum().to_numpy()
    return _marca_finestres(t, n >= p.oscillacio_salts, "1h")


def regla_tram_a_zero(t: pd.DatetimeIndex, x: pd.Series, p: Parametres) -> np.ndarray:
    """Tram a zero enmig d'un riu que porta aigua que es recupera en menys de 6 h."""
    v = x.to_numpy()
    abans = pd.Series(v, index=t).rolling("1h", closed="left").median().to_numpy()
    anterior = np.r_[np.nan, v[:-1]]
    inici = (v <= p.zero_maxim) & (anterior > p.zero_maxim)
    candidats = np.flatnonzero(inici & (abans > p.caiguda_minim))
    out = np.zeros(len(v), dtype=bool)
    ns = _nanosegons(t)
    hora = int(pd.Timedelta(hours=1).value)
    horitzo = int(pd.Timedelta(hours=p.zero_tornada_h).value)
    for i in candidats:
        if out[i]:
            continue
        # L'hora anterior ha de ser aigua real: almenys 3 valors diferents per sobre de zero
        j0 = np.searchsorted(ns, ns[i] - hora, side="left")
        previ = v[j0:i]
        if len(np.unique(previ[previ > p.zero_maxim])) < 3:
            continue
        k = np.searchsorted(ns, ns[i] + horitzo, side="right")
        torna = np.flatnonzero(v[i + 1 : k] >= abans[i] / 2)
        if len(torna):
            out[i : i + 1 + torna[0]] = True
    return out


def regla_excursio(t: pd.DatetimeIndex, x: pd.Series, p: Parametres, p99: float) -> np.ndarray:
    """Pujada de més de x10 que torna a menys del doble del nivell d'abans en menys de 3 h."""
    v = x.to_numpy()
    abans = pd.Series(v, index=t).rolling("1h", closed="left").median()
    abans = abans.fillna(pd.Series(v, index=t).shift(1).ffill()).to_numpy()  # després d'un forat
    candidats = np.flatnonzero((v > p.excursio_factor * np.fmax(abans, 1e-3)) & (v > p99))
    out = np.zeros(len(v), dtype=bool)
    ns = _nanosegons(t)
    horitzo = int(pd.Timedelta(hours=p.excursio_tornada_h).value)
    for i in candidats:
        if out[i]:
            continue
        k = np.searchsorted(ns, ns[i] + horitzo, side="right")
        torna = np.flatnonzero(v[i + 1 : k] <= 2 * max(abans[i], 1e-3))
        if len(torna):
            out[i : i + 1 + torna[0]] = True
    return out


def regla_valor_fix(
    t: pd.DatetimeIndex, v: np.ndarray, p: Parametres, alt: float
) -> tuple[np.ndarray, np.ndarray]:
    """encallat (7 dies iguals, > 0,5 m³/s) i pla_alt (6 h iguals per sobre del p95)."""
    tram = np.cumsum(np.r_[True, v[1:] != v[:-1]])
    s = pd.Series(t, index=tram)
    hores = (
        s.groupby(level=0).transform("max") - s.groupby(level=0).transform("min")
    ) / pd.Timedelta(hours=1)
    hores = hores.to_numpy()
    encallat = (hores >= 24 * p.encallat_dies) & (v > p.encallat_minim)
    pla_alt = (hores >= p.pla_alt_hores) & (v > alt)
    return encallat, pla_alt


def regla_pas_unitat(
    t: pd.DatetimeIndex, v: np.ndarray, factor: np.ndarray | None, p: Parametres
) -> np.ndarray:
    out = np.zeros(len(v), dtype=bool)
    if factor is None or len(v) < 2:
        return out
    canvi = np.r_[False, factor[1:] != factor[:-1]]
    anterior = np.r_[np.nan, v[:-1]]
    with np.errstate(divide="ignore", invalid="ignore"):
        quocient = np.fmax(v, anterior) / np.fmax(np.fmin(v, anterior), 1e-3)
    salts = canvi & (quocient > p.pas_unitat_quocient)
    if salts.any():
        dia = t.floor("D")
        dolents = set(dia[salts]) | set(dia[np.r_[salts[1:], False]])
        out = np.isin(dia, list(dolents))
    return out


def regla_balanc_diari(
    t: pd.DatetimeIndex, v: np.ndarray, bo: np.ndarray, diari: pd.DataFrame | None, p: Parametres
) -> tuple[np.ndarray, pd.DataFrame]:
    """La mitjana del dia (amb les lectures bones) ha de quadrar amb el diari oficial.

    Es prova amb el dia desplaçat 0, +1 i +2 h (no se sap si el diari és UTC o hora local)
    i només es marca si no quadra amb cap.
    """
    buida = pd.DataFrame(columns=["dia", "mitjana_5min", "diari_oficial", "quocient"])
    if diari is None or diari.empty:
        return np.zeros(len(v), dtype=bool), buida
    oficial = pd.Series(
        diari["valor"].to_numpy(dtype=float), index=pd.DatetimeIndex(diari["timestamp"]).floor("D")
    )
    oficial = oficial[~oficial.index.duplicated(keep="last")]
    sostre = 20 * float(np.nanquantile(v, 0.999)) if len(v) else np.inf
    oficial = oficial.where(oficial <= sostre)  # diari impossible per a l'estació
    dia0 = t.floor("D")
    dolent, q0, m0, o0 = None, None, None, None
    for h in (0, 1, 2):
        dia = (t + pd.Timedelta(hours=h)).floor("D")
        mitjana = pd.Series(np.where(bo, v, np.nan), index=dia).groupby(level=0).mean()
        mitges_hores = pd.Series(t.floor("30min"), index=dia).where(bo).groupby(level=0).nunique()
        ref = oficial.reindex(mitjana.index)
        q = mitjana / ref
        es_prova = (mitges_hores / 48 >= p.balanc_cobertura) & (ref > p.balanc_diari_minim)
        d = es_prova & ((q > p.balanc_quocient) | (q < 1 / p.balanc_quocient))
        d = d.reindex(dia0.unique(), fill_value=False)
        dolent = d if dolent is None else (dolent & d)
        if h == 0:
            q0, m0, o0 = q, mitjana, ref
    dies = dolent[dolent].index
    taula = pd.DataFrame(
        {
            "dia": dies,
            "mitjana_5min": m0.reindex(dies).round(3).to_numpy(),
            "diari_oficial": o0.reindex(dies).round(3).to_numpy(),
            "quocient": q0.reindex(dies).round(2).to_numpy(),
        }
    )
    return np.isin(dia0, dies), taula


def control_qualitat(
    serie: pd.DataFrame,
    diari: pd.DataFrame | None = None,
    p: Parametres | None = None,
    exclusions: list[tuple[pd.Timestamp, pd.Timestamp]] = (),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aplica totes les regles. Retorna la sèrie amb valor_net i regles, i la taula de dies
    que no quadren amb el diari oficial."""
    p = p or Parametres()
    df = serie.dropna(subset=["valor"]).sort_values("timestamp").reset_index(drop=True)
    t = pd.DatetimeIndex(df["timestamp"])
    x = df["valor"].astype(float)
    v = x.to_numpy()
    p99, alt = float(x.quantile(0.99)), float(x.quantile(p.pla_alt_quantil))
    m = pd.DataFrame(False, index=df.index, columns=REGLES)
    m["pic"], m["caiguda"] = regla_pic_i_caiguda(x, p, p99)
    m["caiguda"] |= regla_tram_a_zero(t, x, p)
    # Les excursions es busquen sense els trams a zero: si no, la tornada a l'aigua després
    # d'un tram a zero semblaria una pujada sobtada
    m["excursio"] = regla_excursio(t, x.where(~m["caiguda"].to_numpy()), p, p99)
    m["oscil·lacio"] = regla_oscillacio(t, x, p)
    m["encallat"], m["pla_alt"] = regla_valor_fix(t, v, p, alt)
    factor = df["factor_unitat"].to_numpy() if "factor_unitat" in df else None
    m["pas_unitat"] = regla_pas_unitat(t, v, factor, p)
    for a, b in exclusions:
        m["exclusio"] |= (t >= a) & (t <= b)
    # El balanç diari es calcula només amb les lectures que han superat les altres regles
    bo = ~m.any(axis=1).to_numpy()
    m["balanc_diari"], dies_dolents = regla_balanc_diari(t, v, bo, diari, p)
    marcat = m.any(axis=1).to_numpy()
    out = df.copy()
    out["valor_net"] = np.where(marcat, np.nan, v)
    etiquetes = np.full(len(df), "", dtype=object)
    idx = np.flatnonzero(marcat)
    if len(idx):
        sub = m.iloc[idx]
        et = pd.Series("", index=sub.index, dtype=object)
        for r in REGLES:
            et = et + np.where(sub[r].to_numpy(), r + ",", "")
        etiquetes[idx] = et.str.rstrip(",").to_numpy()
    out["regles"] = etiquetes
    return out, dies_dolents


def agrega(serie: pd.DataFrame, freq: str = "30min", columna: str = "valor_net") -> pd.DataFrame:
    """Mitjana (i màxim) per interval, etiquetada amb el FINAL de l'interval. Sense interpolar."""
    # Sense dropna: així la graella cobreix tot el període i els intervals sense cap lectura
    # neta queden buits (i visibles) en lloc de desaparèixer
    s = serie.set_index("timestamp")[columna].sort_index()
    r = s.resample(freq, label="right", closed="right")
    out = pd.DataFrame({"mitjana": r.mean(), "maxim": r.max(), "lectures": r.count()})
    out.loc[out["lectures"] == 0, ["mitjana", "maxim"]] = np.nan
    return out.reset_index()
