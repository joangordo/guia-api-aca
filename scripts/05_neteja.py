"""Pas 5. Corregeix les unitats, aplica el control de qualitat i agrega la sèrie.

Explicació: guia/05-processat-i-filtratge.md (passos 3 a 8)

Cal haver descarregat abans la sèrie de 5 minuts (02) i el cabal diari de la mateixa
estació (03).

Ús:
  python scripts/05_neteja.py --codi 4652845 --diari 4369424
  python scripts/05_neteja.py --codi 4652845 --diari 4369424 --agrega 30min 1h --csv
  python scripts/05_neteja.py --codi 4652859 --diari 4369449 --exclusions exclusions.csv

--exclusions: CSV amb els trams revisats a mà que cal descartar (pas 5 de la guia), amb les
columnes codi, inici, fi, motiu (dates en UTC, p. ex. 2009-12-12 o 2019-12-22 22:45).

Escriu a dades/net/:
  <codi>.parquet         lectures de 5 min: timestamp, valor_brut (tal com ve del portal),
                         factor_unitat, valor (m³/s), valor_net (buit si s'ha descartat),
                         regles (per què), nivell_qualitat, conjunt
  <codi>_<freq>.parquet  mitjana, màxim i nombre de lectures per interval (etiqueta = final)
  <codi>_unitats.csv     classe d'unitat de cada dia (m3s, ls, mixt...)
  <codi>_dies_que_no_quadren.csv   dies descartats pel balanç diari
  <codi>_resum.txt       resum de tot el que s'ha fet
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from comu import CARPETA_DADES, configura_registre, desa, llegeix
from qualitat import REGLES, agrega, control_qualitat, corregeix_unitats


def llegeix_exclusions(cami: Path | None, codi: str) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    if not cami:
        return []
    ex = pd.read_csv(cami, dtype=str)
    ex = ex[ex["codi"].str.strip() == codi]
    return [
        (pd.Timestamp(r.inici, tz="UTC"), pd.Timestamp(r.fi, tz="UTC")) for r in ex.itertuples()
    ]


def resum(codi: str, net: pd.DataFrame, unitats: pd.DataFrame, dies: pd.DataFrame) -> str:
    n = len(net)
    regles = net["regles"].astype(str)
    linies = [
        f"Sèrie {codi}: {n:,} lectures, {net['timestamp'].min()} - {net['timestamp'].max()}",
        "",
        "Unitats (dies):",
    ]
    if len(unitats):
        for classe, k in unitats["classe"].value_counts().items():
            linies.append(f"  {classe:18s} {k:7,d}  ({100 * k / len(unitats):5.1f} %)")
        anys_ls = (
            pd.Series(net["factor_unitat"].lt(1).to_numpy(), index=net["timestamp"].dt.year)
            .groupby(level=0)
            .mean()
        )
        anys_ls = [str(a) for a, s in anys_ls.items() if s > 0.5]
        linies.append(f"  Anys majoritàriament en L/s: {', '.join(anys_ls) or 'cap'}")
    else:
        linies.append("  Sense cabal diari: no s'han pogut comprovar (es deixen com vénen)")
    linies += ["", "Control de qualitat (lectures marcades):"]
    for r in REGLES:
        k = int(regles.str.contains(r, regex=False).sum())
        if k:
            linies.append(f"  {r:14s} {k:9,d}  ({100 * k / n:6.3f} %)")
    descartades = int((regles != "").sum())
    linies.append(f"  {'total':14s} {descartades:9,d}  ({100 * descartades / n:6.3f} %)")
    linies.append(f"\nDies que no quadren amb el diari oficial: {len(dies)}")
    top = net.dropna(subset=["valor_net"]).nlargest(10, "valor_net")
    linies.append("\nLes 10 lectures més altes que es conserven (revisa-les, pas 5 de la guia):")
    for r in top.itertuples():
        linies.append(f"  {r.timestamp:%Y-%m-%d %H:%M}  {r.valor_net:10.2f} m³/s")
    top_d = net[regles != ""].nlargest(5, "valor")
    if len(top_d):
        linies.append("\nLes 5 lectures més altes descartades (comprova que no siguin reals):")
        for r in top_d.itertuples():
            linies.append(f"  {r.timestamp:%Y-%m-%d %H:%M}  {r.valor:10.2f} m³/s  {r.regles}")
    return "\n".join(linies)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--codi", required=True, help="codi_variable de 5 minuts (descarregat amb 02)")
    ap.add_argument("--diari", nargs="*", default=[], help="codi(s) del cabal diari (03)")
    ap.add_argument("--exclusions", type=Path, help="CSV de trams a descartar a mà")
    ap.add_argument("--agrega", nargs="*", default=["30min"], help="Intervals: 30min 1h 1D...")
    ap.add_argument("--csv", action="store_true", help="Desa també en CSV")
    args = ap.parse_args()
    configura_registre()

    serie = llegeix(CARPETA_DADES / "5min" / args.codi)
    serie["timestamp"] = pd.to_datetime(serie["timestamp"], utc=True)
    diari = None
    if args.diari:
        diari = llegeix(CARPETA_DADES / "diari" / f"cabal_{'_'.join(args.diari)}.parquet")
        diari["timestamp"] = pd.to_datetime(diari["timestamp"], utc=True)

    serie, unitats = corregeix_unitats(serie, diari)
    net, dies = control_qualitat(
        serie, diari, exclusions=llegeix_exclusions(args.exclusions, args.codi)
    )

    sortida = CARPETA_DADES / "net"
    cols = ["timestamp", "valor_brut", "factor_unitat", "valor", "valor_net", "regles"]
    cols += [c for c in ("nivell_qualitat", "conjunt") if c in net]
    desa(net[cols], sortida / f"{args.codi}.parquet", csv=args.csv)
    for freq in args.agrega:
        desa(agrega(net, freq), sortida / f"{args.codi}_{freq}.parquet", csv=args.csv)
    if len(unitats):
        unitats.rename_axis("dia").to_csv(sortida / f"{args.codi}_unitats.csv")
    dies.to_csv(sortida / f"{args.codi}_dies_que_no_quadren.csv", index=False)
    text = resum(args.codi, net, unitats, dies)
    (sortida / f"{args.codi}_resum.txt").write_text(text, encoding="utf-8")
    print(text)
    print(f"\nDesat a {sortida}/")


if __name__ == "__main__":
    main()
