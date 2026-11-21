"""Funcions comunes dels scripts: consultes al portal de dades obertes i fitxers.

No s'executa sol: el fan servir els scripts 01 a 05 d'aquesta carpeta.
Explicació: guia/02-portal-dades-obertes.md
"""

from __future__ import annotations

import logging
import os
import re
import time
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd
import requests

log = logging.getLogger("dades-aigua")

PORTAL = "https://analisi.transparenciacatalunya.cat/resource/{id}.json"

# Cabals i nivells cada 5 minuts: una sola sèrie partida en tres conjunts (mateix codi)
CONJUNTS_5MIN = [
    ("mmzz-keb8", 1996, 2009),
    ("9evs-b5nk", 2010, 2019),
    ("3yr3-vq6y", 2020, None),  # fins avui
]
CABAL_DIARI = "2bwe-vgpr"
EMBASSAMENTS_DIARI = "gn9e-3qhr"

CARPETA_DADES = Path("dades")


def configura_registre(detall: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if detall else logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )


# --------------------------------------------------------------------------- #
# Portal de dades obertes (API Socrata)
# --------------------------------------------------------------------------- #
class Portal:
    """Consultes al portal, amb paginació i reintents.

    Si existeix la variable d'entorn SOCRATA_APP_TOKEN, s'envia com a testimoni
    d'aplicació (permet més peticions seguides). No és obligatori.
    """

    def __init__(self, timeout: int = 300, reintents: int = 6, pausa: float = 0.2):
        self.timeout = timeout
        self.reintents = reintents
        self.pausa = pausa
        self.sessio = requests.Session()
        token = os.environ.get("SOCRATA_APP_TOKEN")
        if token:
            self.sessio.headers["X-App-Token"] = token

    def get(self, conjunt: str, params: dict) -> list[dict]:
        """Una petició (una pàgina)."""
        url = PORTAL.format(id=conjunt)
        for intent in range(1, self.reintents + 1):
            try:
                r = self.sessio.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                espera = min(2**intent, 60)
                log.warning("Error de xarxa (%s). Reintent %d en %d s", exc, intent, espera)
                time.sleep(espera)
                continue
            if r.status_code == 200:
                time.sleep(self.pausa)
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                espera = min(2**intent, 60)
                log.warning("HTTP %d. Reintent %d en %d s", r.status_code, intent, espera)
                time.sleep(espera)
                continue
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        raise RuntimeError(f"S'han esgotat els reintents ({url})")

    def consulta(self, conjunt: str, pagina: int = 50_000, **soql) -> pd.DataFrame:
        """Totes les files d'una consulta, pàgina a pàgina.

        soql: where=..., select=..., order=..., group=... (sense el símbol $)
        """
        params = {f"${k}": v for k, v in soql.items() if v}
        files, offset = [], 0
        while True:
            part = self.get(conjunt, {**params, "$limit": pagina, "$offset": offset})
            files += part
            if len(part) < pagina:
                return pd.DataFrame(files)
            offset += pagina


def data_soql(d: date | pd.Timestamp) -> str:
    """Data en el format que entén el portal: '2024-04-01T00:00:00'."""
    return pd.Timestamp(d).strftime("%Y-%m-%dT%H:%M:%S")


def text_soql(valor: str) -> str:
    """Escapa les cometes simples d'un text dins d'una condició SoQL."""
    return str(valor).replace("'", "''")


def mesos(inici: date, fi: date) -> list[tuple[date, date]]:
    """[(1r dia del mes, 1r dia del mes següent), ...] entre inici i fi."""
    out, a = [], date(inici.year, inici.month, 1)
    while a < fi:
        b = date(a.year + (a.month == 12), a.month % 12 + 1, 1)
        out.append((max(a, inici), min(b, fi)))
        a = b
    return out


# --------------------------------------------------------------------------- #
# Dates i fitxers
# --------------------------------------------------------------------------- #
def marca_de_temps(dia: pd.Series, hora: pd.Series | None = None) -> pd.Series:
    """dia (+ hora 'HH:MM', UTC) → Timestamp en UTC. '24:00' és les 00:00 de l'endemà."""
    d = dia.astype(str).str[:10]
    if hora is None:
        return pd.to_datetime(d, utc=True)
    h = hora.astype(str).str.strip()
    mitjanit = h == "24:00"
    t = pd.to_datetime(d + " " + h.where(~mitjanit, "00:00"), utc=True, errors="coerce")
    return t + pd.to_timedelta(mitjanit.astype(int), unit="D")


def nom_fitxer(text: str) -> str:
    """Text → nom de fitxer segur ('Embassament de la Baells' → 'embassament_de_la_baells')."""
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_").lower()


def desa(df: pd.DataFrame, cami: Path, csv: bool = False) -> Path:
    """Desa en Parquet (i, si es vol, també en CSV per obrir-lo amb Excel)."""
    cami.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cami, index=False)
    if csv:
        df.to_csv(cami.with_suffix(".csv"), index=False)
    return cami


def llegeix(cami: Path) -> pd.DataFrame:
    """Llegeix un fitxer Parquet, o tots els d'una carpeta."""
    cami = Path(cami)
    if cami.is_dir():
        fitxers = sorted(cami.glob("*.parquet"))
        if not fitxers:
            raise SystemExit(f"No hi ha cap fitxer a {cami}")
        return pd.concat([pd.read_parquet(f) for f in fitxers], ignore_index=True)
    if not cami.exists():
        raise SystemExit(f"No existeix {cami}")
    return pd.read_parquet(cami)
