# 4. Temps real

[← 3. Trobar estacions](03-trobar-estacions.md) · [Inici](../README.md) · [5. Processat i filtratge →](05-processat-i-filtratge.md)

> **Script:** [`04_temps_real.py`](../scripts/04_temps_real.py).
> `python scripts/04_temps_real.py cataleg --cerca "Sant Joan"` busca sensors i
> `python scripts/04_temps_real.py lectures --sensor AFORAMENT-EST/CALC001261` en baixa les
> lectures i les va afegint al mateix fitxer cada vegada que l'executes.

L'API en temps real de l'ACA fa servir la plataforma **Sentilo**:

```
https://aplicacions.aca.gencat.cat/sdim2/apirest
```

No cal clau. L'ACA en publica un manual (*us_serveis_dades_API_REST.pdf*) a la seva pàgina
de dades en temps real.

## El catàleg de sensors

```
https://aplicacions.aca.gencat.cat/sdim2/apirest/catalog?componentType=AFORAMENT-EST
```

| `componentType` | Què és |
|---|---|
| `AFORAMENT-EST` | aforaments (cabal, nivell) i sortides de les preses |
| `EMBASSAMENT-EST` | embassaments (volum, nivell) |
| `PLUVIOMETREACA-EST` | pluviòmetres de l'ACA (intensitat de pluja, mm/h) |

La resposta és un JSON amb `providers`, i cada proveïdor té una llista de `sensors`. Cada
sensor té `sensor` (codi), `description`, `unit`, `location` (latitud i longitud separades
per un espai) i `componentAdditionalInfo`.

```python
import pandas as pd
import requests

BASE = "https://aplicacions.aca.gencat.cat/sdim2/apirest"


def cataleg(tipus):
    js = requests.get(f"{BASE}/catalog", params={"componentType": tipus}, timeout=60).json()
    files = []
    for prov in js.get("providers", []):
        for s in prov.get("sensors", []):
            lat, lon = (str(s.get("location") or "").replace(",", " ").split() + [None, None])[:2]
            files.append({"provider": prov["provider"], "sensor": s.get("sensor"),
                          "descripcio": s.get("description"), "unitat": s.get("unit"),
                          "lat": lat, "lon": lon})
    return pd.DataFrame(files)


aforaments = cataleg("AFORAMENT-EST")
aforaments[aforaments["descripcio"].str.contains("Sant Joan", case=False, na=False)]
```

Per quedar-te amb una zona, filtra per `lat` i `lon` (un rectangle al voltant de la conca)
o per la descripció.

## Les lectures d'un sensor

```
https://aplicacions.aca.gencat.cat/sdim2/apirest/data/<proveïdor>/<sensor>?from=<inici>&to=<fi>
```

Les dates van en format **`dd/MM/aaaaTHH:mm:ss`** i en **UTC**. Exemple: el cabal a Sant
Joan Despí en una franja de 12 hores.

```
https://aplicacions.aca.gencat.cat/sdim2/apirest/data/AFORAMENT-EST/CALC001261?from=20/11/2026T00:00:00&to=20/11/2026T12:00:00
```

Resposta:

```json
{"observations": [
  {"value": "12.34", "timestamp": "20/11/2026T11:55:00", "time": 1795175700000},
  ...
]}
```

`time` són mil·lisegons des de l'1 de gener de 1970 (UTC) i coincideix amb `timestamp`.

## Tres coses a saber

1. **Com a màxim 200 lectures per petició**, de la més recent a la més antiga, encara que
   demanis un `limit` més alt. A 5 minuts, això són unes 16 hores: demana-ho **en blocs de
   12 hores**.
2. **Alguns textos porten escapaments invàlids** dins del JSON (una barra invertida seguida
   d'una lletra que no toca) i un lector de JSON estricte falla. Cal netejar-los abans.
3. **Només hi ha els darrers dies.** Si vols un registre continu, cal anar-lo guardant: cada
   vegada, demana només des de l'última lectura que ja tens i afegeix-la, sense duplicats.

```python
import json
import re
from datetime import datetime, timedelta, timezone

FMT = "%d/%m/%YT%H:%M:%S"


def lectures(provider, sensor, inici, fi):
    """Lectures entre inici i fi (UTC), en blocs de 12 h."""
    files, t = [], inici
    while t < fi:
        t2 = min(t + timedelta(hours=12), fi)
        r = requests.get(f"{BASE}/data/{provider}/{sensor}",
                         params={"from": t.strftime(FMT), "to": t2.strftime(FMT)}, timeout=60)
        r.raise_for_status()
        text = re.sub(r'\\[^\\"bfnrtu/]', "", r.content.decode("utf-8", errors="replace"))
        if text.strip():
            files += json.loads(text).get("observations", [])
        t = t2
    df = pd.DataFrame(files, columns=["value", "timestamp", "time"])
    df["timestamp"] = pd.to_datetime(df["time"].astype("int64"), unit="ms", utc=True)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.drop_duplicates("timestamp").sort_values("timestamp")[["timestamp", "value"]]


ara = datetime.now(timezone.utc)
sjd = lectures("AFORAMENT-EST", "CALC001261", ara - timedelta(days=2), ara)
```

## Intensitat de pluja

Els pluviòmetres donen **intensitat en mm/h**, no mil·límetres caiguts. Per passar-ho a mm
en un interval, multiplica la intensitat mitjana per la durada en hores: en 30 minuts,
`mm = mitjana(mm/h) × 0,5`.

## Les dades en temps real són brutes

No tenen cap revisió: pics falsos, zeros o un sensor encallat hi arriben tal qual. I la
regla de qualitat més útil, comparar amb el cabal diari oficial, no es pot aplicar fins que
l'endemà surt el diari. Vegeu el [capítol 5](05-processat-i-filtratge.md).

[← 3. Trobar estacions](03-trobar-estacions.md) · [Inici](../README.md) · [5. Processat i filtratge →](05-processat-i-filtratge.md)
