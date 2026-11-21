"""Proves de punta a punta dels scripts amb respostes simulades del portal i de Sentilo."""

import importlib.util
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def carrega(nom):
    spec = importlib.util.spec_from_file_location(nom, SCRIPTS / f"{nom}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Sèrie "real" de 10 m³/s amb una crescuda, i el que en publica el portal
T = pd.date_range("2019-11-01 00:05", "2020-03-01", freq="5min", tz="UTC")
REAL = pd.Series(10 + 0.5 * np.sin(np.arange(len(T)) / 500), index=T)
REAL["2020-01-20 10:00":"2020-01-20 16:00"] += np.linspace(0, 300, 73)
PIC = pd.Timestamp("2019-12-05 12:00", tz="UTC")


def publicat(conjunt):
    """El 2010-2019 en m³/s amb un pic fals; el 2020- en L/s (com al portal) i solapat un dia."""
    if conjunt == "9evs-b5nk":
        s = REAL[:"2019-12-31 23:55"].copy()
        s[PIC] = 900.0
        return s
    if conjunt == "3yr3-vq6y":
        return REAL["2019-12-31":] * 1000
    return REAL[:0]


class PortalFals:
    def __init__(self, *a, **k):
        self.peticions = []

    def get(self, conjunt, params):
        return [{"inici": "2019-11-01T00:00:00.000"}] if conjunt == "9evs-b5nk" else [{}]

    def consulta(self, conjunt, pagina=50_000, **soql):
        self.peticions.append((conjunt, soql.get("where")))
        w = soql.get("where", "")
        if conjunt == "2bwe-vgpr":
            dies = REAL.resample("D").mean()
            df = pd.DataFrame(
                {"dia": dies.index.strftime("%Y-%m-%dT00:00:00.000"), "cabal_riu_m3_s": dies.values}
            )
            df.loc[3, "cabal_riu_m3_s"] = 3_369_195.0  # valor impossible, com a l'Aigua de Valls
            return df.astype(str)
        a, b = re.findall(r"dia [<>]=? '([^']+)'", w)
        s = publicat(conjunt)
        s = s[(s.index > pd.Timestamp(a, tz="UTC")) & (s.index <= pd.Timestamp(b, tz="UTC"))]
        if s.empty:
            return pd.DataFrame()
        # El portal dona dia + hora, i les 00:00 com a «24:00» del dia anterior
        mitjanit = (s.index.hour == 0) & (s.index.minute == 0)
        dia = (s.index - pd.to_timedelta(mitjanit.astype(int), unit="D")).strftime("%Y-%m-%d")
        hora = np.where(mitjanit, "24:00", s.index.strftime("%H:%M"))
        return pd.DataFrame(
            {
                "dia": [d + "T00:00:00.000" for d in dia],
                "hora": hora,
                "valor": s.round(4).astype(str).values,
                "nivell_qualitat": "NQ_REV0",
            }
        )


def executa(mod, args, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["script", *args])
    mod.main()


def test_descarrega_neteja_i_agrega(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    s02, s03, s05 = (
        carrega("02_descarrega_5min"),
        carrega("03_descarrega_diari"),
        carrega("05_neteja"),
    )
    monkeypatch.setattr(s02, "Portal", PortalFals)
    monkeypatch.setattr(s03, "Portal", PortalFals)

    executa(
        s02, ["--codi", "4652845", "--des-de", "2019-11-01", "--fins", "2020-02-29"], monkeypatch
    )
    anys = sorted(p.name for p in (tmp_path / "dades/5min/4652845").glob("*.parquet"))
    assert anys == ["2019.parquet", "2020.parquet"]
    brut = pd.concat(
        pd.read_parquet(p) for p in (tmp_path / "dades/5min/4652845").glob("*.parquet")
    )
    assert brut["timestamp"].is_unique
    # El 31/12/2019 surt als dos conjunts: mana el més recent (en L/s)
    dia31 = brut[brut["timestamp"].dt.strftime("%Y-%m-%d") == "2019-12-31"]
    assert (dia31["conjunt"] == "3yr3-vq6y").all()

    executa(s03, ["cabal", "--codi", "4369424"], monkeypatch)
    diari = pd.read_parquet(tmp_path / "dades/diari/cabal_4369424.parquet")
    assert diari["valor"].max() < 100  # el valor impossible s'ha descartat

    executa(
        s05, ["--codi", "4652845", "--diari", "4369424", "--agrega", "30min", "1h"], monkeypatch
    )
    net = pd.read_parquet(tmp_path / "dades/net/4652845.parquet").set_index("timestamp")
    real = REAL.reindex(net.index)
    bo = net["regles"] == ""
    assert (net.loc[bo, "valor"] - real[bo]).abs().max() < 1e-3  # unitats corregides
    assert "pic" in net.loc[PIC, "regles"]
    assert net.loc["2020-01-20 13:00":"2020-01-20 16:00", "valor_net"].notna().all()  # crescuda
    assert bo.mean() > 0.99
    m30 = pd.read_parquet(tmp_path / "dades/net/4652845_30min.parquet")
    assert m30["timestamp"].diff().dropna().eq(pd.Timedelta("30min")).all()
    assert (tmp_path / "dades/net/4652845_1h.parquet").exists()
    resum = (tmp_path / "dades/net/4652845_resum.txt").read_text(encoding="utf-8")
    assert "Anys majoritàriament en L/s: 2020" in resum

    # Tornar a executar 02 no torna a demanar el 2019 (any tancat)
    fals = PortalFals()
    monkeypatch.setattr(s02, "Portal", lambda timeout: fals)
    executa(
        s02, ["--codi", "4652845", "--des-de", "2019-11-01", "--fins", "2020-02-29"], monkeypatch
    )
    assert fals.peticions == []


def test_exclusions(tmp_path):
    s05 = carrega("05_neteja")
    f = tmp_path / "ex.csv"
    f.write_text("codi,inici,fi,motiu\n1,2009-12-12,2009-12-23,prova\n2,2020-01-01,2020-01-02,x\n")
    ex = s05.llegeix_exclusions(f, "1")
    assert ex == [(pd.Timestamp("2009-12-12", tz="UTC"), pd.Timestamp("2009-12-23", tz="UTC"))]


class Resposta:
    def __init__(self, js, cru=None):
        self.status_code = 200
        self.content = (cru or json.dumps(js)).encode()
        self.text = self.content.decode()


def sentilo_fals(url, params=None, timeout=None):
    if url.endswith("/catalog"):
        js = {
            "providers": [
                {
                    "provider": "AFORAMENT-EST",
                    "sensors": [
                        {
                            "sensor": "CALC001261",
                            "description": "Cabal Sant Joan Despí",
                            "unit": "m3/s",
                            "location": "41.36 2.06",
                        },
                        {"sensor": "CALC000001", "description": "Cabal Girona", "unit": "m3/s"},
                    ],
                }
            ]
        }
        # amb un escapament invàlid, com de vegades l'API real
        return Resposta(None, json.dumps(js).replace("Girona", "Giro\\na\\x"))
    t0 = datetime.strptime(params["from"], "%d/%m/%YT%H:%M:%S").replace(tzinfo=timezone.utc)
    t1 = datetime.strptime(params["to"], "%d/%m/%YT%H:%M:%S").replace(tzinfo=timezone.utc)
    obs, t = [], t0.replace(second=0) + timedelta(minutes=5 - t0.minute % 5)
    while t <= t1:
        obs.append(
            {
                "value": "6.5",
                "timestamp": t.strftime("%d/%m/%YT%H:%M:%S"),
                "time": int(t.timestamp() * 1000),
            }
        )
        t += timedelta(minutes=5)
    return Resposta({"observations": obs[::-1]})


def test_temps_real(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    s04 = carrega("04_temps_real")
    monkeypatch.setattr(s04, "CARPETA", Path("dades/temps_real"))
    monkeypatch.setattr(s04.requests, "get", sentilo_fals)
    executa(s04, ["cataleg", "--cerca", "sant joan"], monkeypatch)
    cat = pd.read_csv(tmp_path / "dades/temps_real/cataleg.csv")
    assert cat["sensor"].tolist() == ["AFORAMENT-EST/CALC001261"]

    executa(s04, ["lectures", "--sensor", "AFORAMENT-EST/CALC001261", "--dies", "2"], monkeypatch)
    f = tmp_path / "dades/temps_real/AFORAMENT-EST__CALC001261.parquet"
    df = pd.read_parquet(f)
    assert 570 <= len(df) <= 580 and df["timestamp"].is_unique
    executa(s04, ["lectures", "--sensor", "AFORAMENT-EST/CALC001261"], monkeypatch)
    df2 = pd.read_parquet(f)
    assert len(df2) - len(df) <= 1  # la segona vegada només afegeix el que falta
    assert df2["timestamp"].is_monotonic_increasing


@pytest.mark.parametrize(
    "nom", ["01_conques", "02_descarrega_5min", "03_descarrega_diari", "04_temps_real", "05_neteja"]
)
def test_ajuda(nom, monkeypatch, capsys):
    mod = carrega(nom)
    monkeypatch.setattr(sys, "argv", [nom, "--help"])
    with pytest.raises(SystemExit):
        mod.main()
    assert "Ús:" in capsys.readouterr().out


def test_conques_uneix_5min_i_diari(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    s01 = carrega("01_conques")

    class Fals:
        def __init__(self, *a, **k):
            pass

        def consulta(self, conjunt, **soql):
            if conjunt == "2bwe-vgpr":
                return pd.DataFrame(
                    {
                        "estaci": ["Aforament - Sant Joan Despí"],
                        "codi_variable": ["4369424"],
                        "descripci_variable": ["EA049_Sant Joan Despi_Cabal riu Llobregat"],
                        "inici": ["1966-03-11T00:00:00.000"],
                        "fi": ["2026-11-20T00:00:00.000"],
                        "dies": ["22000"],
                    }
                )
            return pd.DataFrame(
                {
                    "codi_estacio": ["EA049_C4049", "EA049_C4049"],
                    "estacio": ["Aforament - Sant Joan Despí"] * 2,
                    "subconca": ["Baix Llobregat"] * 2,
                    "codi_variable": ["4652845", "4652846"],
                    "tipus_variable": ["Cabal riu", "Nivell riu"],
                    "unitat_mesura": ["m³/s", "m"],
                    "vista": ["2026-11-20T00:00:00.000"] * 2,
                }
            )

    monkeypatch.setattr(s01, "Portal", Fals)
    executa(s01, ["--conca", "Llobregat"], monkeypatch)
    unio = pd.read_csv(tmp_path / "dades/estacions_llobregat.csv", dtype=str)
    parelles = unio[["codi_variable", "codi_variable_diari"]].values.tolist()
    assert parelles == [["4652845", "4369424"]]
    assert "4369424" in capsys.readouterr().out
