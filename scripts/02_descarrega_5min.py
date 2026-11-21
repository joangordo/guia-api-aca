"""Pas 2. Descarrega una sèrie de 5 minuts sencera (1996 - avui) i encadena els tres trams.

Explicació: guia/02-portal-dades-obertes.md i guia/05-processat-i-filtratge.md (passos 1 i 2)

Ús:
  python scripts/02_descarrega_5min.py --codi 4652845
  python scripts/02_descarrega_5min.py --codi 4652845 4652790 --des-de 2015-01-01
  python scripts/02_descarrega_5min.py --codi 4652845 --csv

El codi és el codi_variable (vegeu 01_conques.py). Es demana mes a mes i es desa un fitxer
per any a dades/5min/<codi>/<any>.parquet. Si es talla, torna a executar la mateixa ordre:
els anys ja descarregats no es tornen a demanar (excepte l'any en curs, que creix).

Columnes: timestamp (UTC), valor (tal com ve del portal: pot ser en L/s!), nivell_qualitat
i conjunt (d'on ve la lectura).
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

import pandas as pd

from comu import (
    CARPETA_DADES,
    CONJUNTS_5MIN,
    Portal,
    configura_registre,
    data_soql,
    desa,
    llegeix,
    log,
    marca_de_temps,
    mesos,
    text_soql,
)


def conjunts_de_lany(any_: int) -> list[tuple[int, str]]:
    """Conjunts que poden tenir dades d'un any (amb un any de marge pels solapaments)."""
    avui = date.today().year
    out = []
    for rang, (conjunt, primer, darrer) in enumerate(CONJUNTS_5MIN):
        if primer - 1 <= any_ <= (darrer or avui) + 1:
            out.append((rang, conjunt))
    return out


def primer_any(portal: Portal, codi: str) -> int:
    """Primer any amb dades de la sèrie (per no demanar anys buits)."""
    for conjunt, primer, _ in CONJUNTS_5MIN:
        try:
            r = portal.get(
                conjunt,
                {"$select": "min(dia) AS inici", "$where": f"codi_variable='{text_soql(codi)}'"},
            )
        except RuntimeError:
            return primer
        if r and r[0].get("inici"):
            return int(r[0]["inici"][:4])
    return date.today().year


def descarrega_any(portal: Portal, codi: str, any_: int) -> pd.DataFrame:
    """Totes les lectures d'un any, mes a mes, de tots els conjunts que el poden tenir."""
    inici, fi = date(any_, 1, 1), min(date(any_ + 1, 1, 1), date.today() + timedelta(days=1))
    parts = []
    for rang, conjunt in conjunts_de_lany(any_):
        for a, b in mesos(inici, fi):
            df = portal.consulta(
                conjunt,
                select="dia, hora, valor, nivell_qualitat",
                where=f"codi_variable='{text_soql(codi)}' "
                f"AND dia >= '{data_soql(a)}' AND dia < '{data_soql(b)}'",
                order="dia, hora",
            )
            if not df.empty:
                parts.append(df.assign(conjunt=conjunt, _rang=rang))
    if not parts:
        return pd.DataFrame(columns=["timestamp", "valor", "nivell_qualitat", "conjunt"])
    df = pd.concat(parts, ignore_index=True)
    df["timestamp"] = marca_de_temps(df["dia"], df["hora"])
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["timestamp", "valor"])
    # Encadenament: si un instant surt dues vegades, mana el conjunt més recent
    df = df.sort_values(["timestamp", "_rang"]).drop_duplicates("timestamp", keep="last")
    if "nivell_qualitat" not in df:
        df["nivell_qualitat"] = pd.NA
    return df[["timestamp", "valor", "nivell_qualitat", "conjunt"]].reset_index(drop=True)


def descarrega_serie(
    portal: Portal, codi: str, des_de: date | None, fins: date | None, torna: bool = False
) -> pd.DataFrame:
    carpeta = CARPETA_DADES / "5min" / codi
    any_inici = des_de.year if des_de else primer_any(portal, codi)
    any_fi = (fins or date.today()).year
    for any_ in range(any_inici, any_fi + 1):
        cami = carpeta / f"{any_}.parquet"
        buit = carpeta / f"{any_}.buit"
        tancat = any_ < date.today().year
        if tancat and not torna and (cami.exists() or buit.exists()):
            log.info("%s %d: ja descarregat", codi, any_)
            continue
        df = descarrega_any(portal, codi, any_)
        carpeta.mkdir(parents=True, exist_ok=True)
        if df.empty:
            buit.touch()
            log.info("%s %d: sense dades", codi, any_)
            continue
        desa(df, cami)
        log.info("%s %d: %d lectures", codi, any_, len(df))
    df = llegeix(carpeta)
    if des_de:
        df = df[df["timestamp"] >= pd.Timestamp(des_de, tz="UTC")]
    if fins:
        df = df[df["timestamp"] < pd.Timestamp(fins, tz="UTC") + pd.Timedelta(days=1)]
    return df.sort_values("timestamp").reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--codi", nargs="+", required=True, help="codi_variable de 5 minuts")
    ap.add_argument("--des-de", type=date.fromisoformat, help="AAAA-MM-DD (per defecte, l'inici)")
    ap.add_argument("--fins", type=date.fromisoformat, help="AAAA-MM-DD (per defecte, avui)")
    ap.add_argument("--torna-a-baixar", action="store_true", help="Torna a demanar tots els anys")
    ap.add_argument("--csv", action="store_true", help="Desa també la sèrie sencera en CSV")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()
    configura_registre()
    portal = Portal(timeout=args.timeout)
    for codi in args.codi:
        df = descarrega_serie(portal, codi, args.des_de, args.fins, args.torna_a_baixar)
        if args.csv:
            df.to_csv(CARPETA_DADES / "5min" / f"{codi}.csv", index=False)
        if df.empty:
            print(f"{codi}: cap lectura")
            continue
        per_conjunt = df.groupby("conjunt")["timestamp"].agg(["min", "max", "count"])
        print(f"\n{codi}: {len(df):,} lectures, {df['timestamp'].min()} - {df['timestamp'].max()}")
        print(per_conjunt.to_string())
    print(
        "\nCompte: els valors encara no tenen les unitats corregides ni el control de qualitat.\n"
        "Ara: python scripts/03_descarrega_diari.py cabal --codi <codi diari> i 05_neteja.py"
    )


if __name__ == "__main__":
    main()
