"""Pas 4. Les darreres lectures de l'API en temps real de l'ACA (Sentilo).

Explicació: guia/04-temps-real.md

Ús:
  python scripts/04_temps_real.py cataleg                       tots els sensors
  python scripts/04_temps_real.py cataleg --cerca "Sant Joan"   filtrats per text
  python scripts/04_temps_real.py lectures --sensor AFORAMENT-EST/CALC001261 --dies 2
  python scripts/04_temps_real.py lectures --sensor AFORAMENT-EST/CALC001261 \
         PLUVIOMETREACA-EST/082172-002-ANA014        (diversos sensors)

cataleg  → dades/temps_real/cataleg.csv (proveïdor, sensor, descripció, unitat, lat, lon)
lectures → dades/temps_real/<proveïdor>__<sensor>.parquet (timestamp UTC, valor)
           Si el fitxer ja existeix, només es demana el que falta des de l'última lectura i
           s'hi afegeix: executant-lo cada pocs dies es construeix un registre continu.

L'API només guarda els darrers dies i les dades són brutes (sense cap revisió).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from comu import CARPETA_DADES, configura_registre, log

BASE = "https://aplicacions.aca.gencat.cat/sdim2/apirest"
FORMAT = "%d/%m/%YT%H:%M:%S"
BLOC = timedelta(hours=12)  # l'API dona com a màxim 200 lectures per petició (~16 h)
TIPUS = ["AFORAMENT-EST", "EMBASSAMENT-EST", "PLUVIOMETREACA-EST"]
CARPETA = CARPETA_DADES / "temps_real"


def neteja_json(text: str) -> str:
    """Treu les seqüències d'escapament invàlides que l'API posa de vegades dins del JSON."""
    text = re.sub(r"\\b5", "m", text)
    text = re.sub(r"\\ba", "º", text)
    return re.sub(r'\\[^\\"bfnrtu/]', "", text)


def get(cami: str, params: dict | None = None, reintents: int = 5) -> dict:
    for intent in range(1, reintents + 1):
        try:
            r = requests.get(f"{BASE}/{cami}", params=params, timeout=60)
        except requests.RequestException as exc:
            log.warning("Error de xarxa (%s). Reintent %d", exc, intent)
            time.sleep(min(2**intent, 60))
            continue
        if r.status_code == 200:
            text = r.content.decode("utf-8", errors="replace")
            return json.loads(neteja_json(text)) if text.strip() else {}
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(min(2**intent, 60))
            continue
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    raise RuntimeError("S'han esgotat els reintents")


def cataleg(tipus: list[str]) -> pd.DataFrame:
    files = []
    for t in tipus:
        for prov in get("catalog", {"componentType": t}).get("providers", []):
            for s in prov.get("sensors", []):
                lat = lon = None
                loc = str(s.get("location") or "").replace(",", " ").split()
                if len(loc) >= 2:
                    with contextlib.suppress(ValueError):
                        lat, lon = float(loc[0]), float(loc[1])
                files.append(
                    {
                        "sensor": f"{prov.get('provider')}/{s.get('sensor')}",
                        "descripcio": s.get("description"),
                        "tipus": s.get("type"),
                        "unitat": s.get("unit"),
                        "component": s.get("component"),
                        "lat": lat,
                        "lon": lon,
                    }
                )
    cols = ["sensor", "descripcio", "tipus", "unitat", "component", "lat", "lon"]
    return pd.DataFrame(files, columns=cols).drop_duplicates("sensor").reset_index(drop=True)


def a_temps(obs: dict) -> pd.Timestamp | None:
    if obs.get("time") not in (None, ""):
        return pd.Timestamp(int(obs["time"]), unit="ms", tz="UTC")
    with contextlib.suppress(ValueError):
        return pd.Timestamp(datetime.strptime(str(obs.get("timestamp")), FORMAT), tz="UTC")
    return None


def lectures(sensor: str, inici: datetime, fi: datetime) -> pd.DataFrame:
    """Lectures entre inici i fi (UTC), demanades en blocs de 12 hores."""
    proveidor, codi = sensor.split("/", 1)
    files, t = [], inici
    while t < fi:
        t2 = min(t + BLOC, fi)
        js = get(
            f"data/{proveidor}/{codi}", {"from": t.strftime(FORMAT), "to": t2.strftime(FORMAT)}
        )
        obs = js.get("observations", []) if isinstance(js, dict) else []
        if len(obs) >= 200:
            log.warning("%s: 200 lectures en un bloc, en poden faltar", sensor)
        for o in obs:
            ts = a_temps(o)
            if ts is not None:
                files.append(
                    {"timestamp": ts, "valor": pd.to_numeric(o.get("value"), errors="coerce")}
                )
        t = t2
    df = pd.DataFrame(files, columns=["timestamp", "valor"])
    return df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


def afegeix(sensor: str, dies: int) -> pd.DataFrame:
    """Descàrrega incremental: només el que falta des de l'última lectura desada."""
    cami = CARPETA / f"{sensor.replace('/', '__')}.parquet"
    ara = datetime.now(timezone.utc)
    vell = pd.read_parquet(cami) if cami.exists() else pd.DataFrame(columns=["timestamp", "valor"])
    if len(vell):
        inici = pd.Timestamp(vell["timestamp"].max()).to_pydatetime() + timedelta(seconds=1)
    else:
        inici = ara - timedelta(days=dies)
    nou = lectures(sensor, inici, ara)
    if len(vell) and len(nou):
        df = pd.concat([vell, nou], ignore_index=True)
    else:
        df = nou if len(nou) else vell.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.drop_duplicates("timestamp", keep="last").sort_values("timestamp")
    CARPETA.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cami, index=False)
    log.info("%s: %d lectures noves, %d en total", sensor, len(nou), len(df))
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest="ordre", required=True)
    c = sub.add_parser("cataleg", help="Llista de sensors")
    c.add_argument("--tipus", nargs="+", default=TIPUS)
    c.add_argument("--cerca", help="Text dins del codi, la descripció o el component")
    lec = sub.add_parser("lectures", help="Darreres lectures d'un o més sensors")
    lec.add_argument("--sensor", nargs="+", required=True, help="PROVEÏDOR/SENSOR")
    lec.add_argument("--dies", type=int, default=7, help="Dies enrere la primera vegada")
    args = ap.parse_args()
    configura_registre()
    pd.set_option("display.width", 200)

    if args.ordre == "cataleg":
        df = cataleg(args.tipus)
        if args.cerca and len(df):
            camps = df[["sensor", "descripcio", "component"]].fillna("").astype(str)
            text = camps.agg(" ".join, axis=1)
            df = df[text.str.contains(args.cerca, case=False, regex=False)]
        CARPETA.mkdir(parents=True, exist_ok=True)
        df.to_csv(CARPETA / "cataleg.csv", index=False, encoding="utf-8-sig")
        print(df.head(50).to_string(index=False))
        print(f"\n{len(df)} sensors. Desat a {CARPETA / 'cataleg.csv'}")
        return

    for sensor in args.sensor:
        try:
            df = afegeix(sensor, args.dies)
        except RuntimeError as exc:  # un sensor que falla no atura la resta
            log.error("%s: %s", sensor, exc)
            continue
        if len(df):
            ult = df.iloc[-1]
            print(
                f"{sensor}: última lectura {ult['timestamp']:%Y-%m-%d %H:%M} UTC = {ult['valor']}"
            )


if __name__ == "__main__":
    main()
