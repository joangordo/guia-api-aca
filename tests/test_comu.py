from datetime import date

import pandas as pd

from comu import Portal, marca_de_temps, mesos, nom_fitxer, text_soql


def test_marca_de_temps_amb_24_00():
    dia = pd.Series(["2024-04-29T00:00:00.000", "2024-04-29T00:00:00.000"])
    hora = pd.Series(["23:55", "24:00"])
    t = marca_de_temps(dia, hora)
    assert t.tolist() == [
        pd.Timestamp("2024-04-29 23:55", tz="UTC"),
        pd.Timestamp("2024-04-30 00:00", tz="UTC"),
    ]
    assert marca_de_temps(pd.Series(["1966-03-11T00:00:00.000"])).iloc[0] == pd.Timestamp(
        "1966-03-11", tz="UTC"
    )


def test_mesos_i_textos():
    assert mesos(date(2024, 11, 15), date(2025, 1, 10)) == [
        (date(2024, 11, 15), date(2024, 12, 1)),
        (date(2024, 12, 1), date(2025, 1, 1)),
        (date(2025, 1, 1), date(2025, 1, 10)),
    ]
    assert nom_fitxer("Embassament de la Baells (Cercs)") == "embassament_de_la_baells_cercs"
    assert text_soql("l'Anoia") == "l''Anoia"


def test_paginacio(monkeypatch):
    files = [{"i": i} for i in range(12)]
    vistes = []

    def fals_get(self, conjunt, params):
        vistes.append(params["$offset"])
        return files[params["$offset"] : params["$offset"] + params["$limit"]]

    monkeypatch.setattr(Portal, "get", fals_get)
    df = Portal().consulta("x", pagina=5, where="a=1", order="dia")
    assert len(df) == 12 and vistes == [0, 5, 10]
