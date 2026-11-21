"""Pas 1. Quines conques, estacions i embassaments hi ha, i amb quins codis.

Explicació: guia/03-trobar-estacions.md

Ús:
  python scripts/01_conques.py                     llista les conques amb dades
  python scripts/01_conques.py --conca Ter         estacions i sèries d'una conca
  python scripts/01_conques.py --conca Ter --historic   també les estacions ja tancades
  python scripts/01_conques.py --embassaments      llista dels embassaments

Escriu a dades/:
  estacions_<conca>_5min.csv   sèries de 5 minuts (codi_variable per a 02_descarrega_5min.py)
  estacions_<conca>_diari.csv  sèries diàries, amb el primer i l'últim dia
  estacions_<conca>.csv        les dues unides pel codi d'estació (prefix)
  embassaments.csv
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

import pandas as pd

from comu import (
    CABAL_DIARI,
    CARPETA_DADES,
    CONJUNTS_5MIN,
    EMBASSAMENTS_DIARI,
    Portal,
    configura_registre,
    data_soql,
    log,
    nom_fitxer,
    text_soql,
)

CAMPS_5MIN = "codi_estacio, estacio, subconca, codi_variable, tipus_variable, unitat_mesura"


def conques(portal: Portal) -> pd.DataFrame:
    """Conques amb lectures de 5 minuts durant l'últim mes."""
    des_de = date.today() - timedelta(days=30)
    df = portal.consulta(
        "3yr3-vq6y",
        select="conca, count(*) AS lectures",
        where=f"dia >= '{data_soql(des_de)}'",
        group="conca",
        order="conca",
    )
    if not df.empty:
        df["lectures"] = pd.to_numeric(df["lectures"])
    return df


def series_5min(portal: Portal, conca: str, historic: bool = False) -> pd.DataFrame:
    """Sèries de 5 minuts d'una conca.

    Agrupar un conjunt sencer fa caure la consulta (desenes de milions de files), així que es
    mira una finestra de temps: l'últim mes i, amb --historic, també el gener del 2019 i el
    del 2009 (per trobar les estacions que ja no funcionen).
    """
    avui = date.today()
    finestres = [("3yr3-vq6y", avui - timedelta(days=30), avui + timedelta(days=1))]
    if historic:
        finestres += [
            ("9evs-b5nk", date(2019, 1, 1), date(2019, 2, 1)),
            ("mmzz-keb8", date(2009, 1, 1), date(2009, 2, 1)),
        ]
    parts = []
    for conjunt, a, b in finestres:
        log.info("Sèries de 5 minuts a %s (%s - %s)...", conjunt, a, b)
        df = portal.consulta(
            conjunt,
            select=f"{CAMPS_5MIN}, max(dia) AS vista",
            where=f"upper(conca) like '%{text_soql(conca.upper())}%' "
            f"AND dia >= '{data_soql(a)}' AND dia < '{data_soql(b)}'",
            group=CAMPS_5MIN,
        )
        if not df.empty:
            parts.append(df.assign(conjunt=conjunt))
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True)
    # Una fila per codi_variable: la informació més recent mana
    ordre = {c: i for i, (c, _, _) in enumerate(CONJUNTS_5MIN)}
    df["_o"] = df["conjunt"].map(ordre)
    df = df.sort_values("_o").groupby("codi_variable", as_index=False).last().drop(columns="_o")
    df["prefix"] = df["codi_estacio"].astype(str).str.split("_").str[0]
    return df.sort_values(["estacio", "tipus_variable"]).reset_index(drop=True)


def series_diaries(portal: Portal, conca: str) -> pd.DataFrame:
    log.info("Sèries diàries...")
    try:
        df = portal.consulta(
            CABAL_DIARI,
            select="estaci, codi_variable, descripci_variable, min(dia) AS inici, max(dia) AS fi, "
            "count(*) AS dies",
            where=f"upper(conca) like '%{text_soql(conca.upper())}%'",
            group="estaci, codi_variable, descripci_variable",
            order="estaci",
        )
    except RuntimeError as exc:  # el portal pot canviar el nom d'un camp
        log.warning("No s'han pogut llistar les sèries diàries (%s)", exc)
        return pd.DataFrame()
    if df.empty:
        return df
    df["inici"], df["fi"] = df["inici"].str[:10], df["fi"].str[:10]
    df["prefix"] = df["descripci_variable"].astype(str).str.split("_").str[0]
    return df


def embassaments(portal: Portal) -> pd.DataFrame:
    df = portal.consulta(
        EMBASSAMENTS_DIARI,
        select="estaci, min(dia) AS inici, max(dia) AS fi, count(*) AS dies",
        group="estaci",
        order="estaci",
    )
    if not df.empty:
        df["inici"], df["fi"] = df["inici"].str[:10], df["fi"].str[:10]
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--conca", help="Nom (o part del nom) de la conca, p. ex. Llobregat, Ter")
    ap.add_argument("--historic", action="store_true", help="Busca també estacions tancades")
    ap.add_argument("--embassaments", action="store_true", help="Llista els embassaments")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()
    configura_registre()
    portal = Portal(timeout=args.timeout)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_rows", 500)
    pd.set_option("display.max_colwidth", 50)
    CARPETA_DADES.mkdir(exist_ok=True)

    if args.embassaments:
        df = embassaments(portal)
        df.to_csv(CARPETA_DADES / "embassaments.csv", index=False, encoding="utf-8-sig")
        print(df.to_string(index=False))
        return

    if not args.conca:
        df = conques(portal)
        print(df.to_string(index=False))
        print("\nAra: python scripts/01_conques.py --conca <nom>")
        return

    nom = nom_fitxer(args.conca)
    s5 = series_5min(portal, args.conca, args.historic)
    sd = series_diaries(portal, args.conca)
    if s5.empty and sd.empty:
        raise SystemExit(f"No he trobat cap sèrie de la conca «{args.conca}».")
    s5.to_csv(CARPETA_DADES / f"estacions_{nom}_5min.csv", index=False, encoding="utf-8-sig")
    sd.to_csv(CARPETA_DADES / f"estacions_{nom}_diari.csv", index=False, encoding="utf-8-sig")

    # Les dues taules unides pel codi d'estació (p. ex. EA049): quin diari va amb cada sèrie
    cabals = s5[s5["tipus_variable"].str.contains("cabal", case=False, na=False)] if len(s5) else s5
    if len(cabals) and len(sd):
        unio = cabals.merge(
            sd[["prefix", "codi_variable", "descripci_variable", "inici", "fi"]],
            on="prefix",
            how="left",
            suffixes=("", "_diari"),
        )
        unio.to_csv(CARPETA_DADES / f"estacions_{nom}.csv", index=False, encoding="utf-8-sig")
        cols = ["estacio", "codi_variable", "codi_variable_diari", "descripci_variable", "inici"]
        print(unio[cols].to_string(index=False))
    else:
        print(s5.to_string(index=False) if len(s5) else sd.to_string(index=False))
    print(
        f"\n{len(s5)} sèries de 5 min i {len(sd)} de diàries. Desat a {CARPETA_DADES}/"
        f"estacions_{nom}*.csv\n"
        "Ara: python scripts/02_descarrega_5min.py --codi <codi_variable>"
    )


if __name__ == "__main__":
    main()
