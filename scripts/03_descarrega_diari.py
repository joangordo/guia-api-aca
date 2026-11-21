"""Pas 3. Descarrega el cabal diari oficial d'una estació o l'estat diari d'un embassament.

Explicació: guia/02-portal-dades-obertes.md i guia/05-processat-i-filtratge.md (pas 7)

Ús:
  python scripts/03_descarrega_diari.py cabal --codi 4369424
  python scripts/03_descarrega_diari.py cabal --codi 4165139 4462770     (codis encadenats)
  python scripts/03_descarrega_diari.py embassament --nom Baells
  python scripts/03_descarrega_diari.py embassament --nom Sau --csv

cabal: el codi és el codi_variable del conjunt diari (columna codi_variable_diari de
01_conques.py). Si una estació va canviar de codi, posa'ls tots en ordre: s'encadenen i,
on se solapen, mana l'últim. Es descarten els valors negatius i els impossibles.
  → dades/diari/cabal_<codi>.parquet (timestamp, valor en m³/s, codi)

embassament: el nom (o part del nom) tal com surt a 01_conques.py --embassaments.
  → dades/diari/embassament_<nom>.parquet (timestamp, nivell_msnm, volum_hm3, percentatge)
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from comu import (
    CABAL_DIARI,
    CARPETA_DADES,
    EMBASSAMENTS_DIARI,
    Portal,
    configura_registre,
    desa,
    log,
    marca_de_temps,
    nom_fitxer,
    text_soql,
)


def cabal_diari(portal: Portal, codis: list[str], maxim: float) -> pd.DataFrame:
    parts = []
    for rang, codi in enumerate(codis):
        df = portal.consulta(
            CABAL_DIARI,
            select="dia, cabal_riu_m3_s",
            where=f"codi_variable='{text_soql(codi)}'",
            order="dia",
        )
        log.info("%s: %d dies", codi, len(df))
        if not df.empty:
            parts.append(df.assign(codi=codi, _rang=rang))
    if not parts:
        return pd.DataFrame(columns=["timestamp", "valor", "codi"])
    df = pd.concat(parts, ignore_index=True)
    df["timestamp"] = marca_de_temps(df["dia"])
    df["valor"] = pd.to_numeric(df["cabal_riu_m3_s"], errors="coerce")
    # Valors impossibles (n'hi ha de milions de m³/s): negatius, per sobre d'un màxim físic
    # o més de 20 vegades el percentil 99,9 de la mateixa sèrie
    sostre = min(maxim, 20 * float(np.nanquantile(df["valor"], 0.999)))
    dolent = (df["valor"] < 0) | (df["valor"] > sostre)
    if dolent.any():
        log.warning("%d dies amb valors impossibles, descartats", int(dolent.sum()))
        df.loc[dolent, "valor"] = np.nan
    df = df.sort_values(["timestamp", "_rang"]).drop_duplicates("timestamp", keep="last")
    return df[["timestamp", "valor", "codi"]].reset_index(drop=True)


def embassament(portal: Portal, nom: str) -> pd.DataFrame:
    df = portal.consulta(
        EMBASSAMENTS_DIARI,
        where=f"upper(estaci) like '%{text_soql(nom.upper())}%'",
        order="dia",
    )
    if df.empty:
        return df
    noms = df["estaci"].unique()
    if len(noms) > 1:
        raise SystemExit(f"Hi ha més d'un embassament amb «{nom}»: {', '.join(noms)}")
    out = pd.DataFrame({"timestamp": marca_de_temps(df["dia"]), "embassament": df["estaci"]})
    for camp, nou in (
        ("nivell_absolut", "nivell_msnm"),
        ("volum_embassat", "volum_hm3"),
        ("percentatge_volum_embassat", "percentatge"),
    ):
        if camp in df:
            out[nou] = pd.to_numeric(df[camp], errors="coerce")
    return out.drop_duplicates("timestamp", keep="last").reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--csv", action="store_true", help="Desa també en CSV")
    ap.add_argument("--timeout", type=int, default=300)
    sub = ap.add_subparsers(dest="ordre", required=True)
    c = sub.add_parser("cabal", help="Cabal diari oficial d'una estació")
    c.add_argument("--codi", nargs="+", required=True)
    c.add_argument("--maxim", type=float, default=10_000, help="Màxim físic en m³/s")
    e = sub.add_parser("embassament", help="Nivell, volum i percentatge d'un embassament")
    e.add_argument("--nom", required=True)
    args = ap.parse_args()
    configura_registre()
    portal = Portal(timeout=args.timeout)

    if args.ordre == "cabal":
        df = cabal_diari(portal, args.codi, args.maxim)
        cami = CARPETA_DADES / "diari" / f"cabal_{'_'.join(args.codi)}.parquet"
        resum = df["valor"].describe().round(2).to_string() if len(df) else ""
    else:
        df = embassament(portal, args.nom)
        cami = CARPETA_DADES / "diari" / f"embassament_{nom_fitxer(args.nom)}.parquet"
        resum = df.tail(5).to_string(index=False) if len(df) else ""
    if df.empty:
        raise SystemExit("Cap dada. Comprova el codi o el nom amb 01_conques.py.")
    desa(df, cami, csv=args.csv)
    print(
        f"\n{len(df):,} dies ({df['timestamp'].min():%Y-%m-%d} - {df['timestamp'].max():%Y-%m-%d})"
    )
    print(resum)
    print(f"Desat a {cami}")


if __name__ == "__main__":
    main()
