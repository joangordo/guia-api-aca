# 2. El portal de dades obertes

[← 1. Quines dades hi ha](01-quines-dades-hi-ha.md) · [Inici](../README.md) · [3. Trobar estacions →](03-trobar-estacions.md)

> **Script:** [`02_descarrega_5min.py`](../scripts/02_descarrega_5min.py) i
> [`03_descarrega_diari.py`](../scripts/03_descarrega_diari.py) fan aquestes consultes per tu,
> amb paginació, reintents i descàrrega mes a mes. Les funcions són a
> [`comu.py`](../scripts/comu.py).

El portal de la Generalitat fa servir l'API **Socrata** (SODA). Cada conjunt de dades té un
identificador (`3yr3-vq6y`…) i es consulta amb una adreça web.

## Els camps

### Cabals cada 5 minuts (`mmzz-keb8`, `9evs-b5nk`, `3yr3-vq6y`)

| Camp | Exemple | Notes |
|---|---|---|
| `dia` | `2024-04-29T00:00:00.000` | data, sense l'hora |
| `hora` | `13:05` | text `HH:MM`, en **UTC**; pot ser `24:00` |
| `codi_estacio` | `EA049_C4049` | estació |
| `estacio` | `Aforament - Sant Joan Despí` | nom |
| `conca`, `subconca` | `Llobregat`, `Baix Llobregat` | |
| `tipus_variable` | `Cabal riu`, `Nivell riu` | |
| `codi_variable` | `4652845` | **la clau**: una sèrie = un codi |
| `descripcio_variable` | | |
| `unitat_mesura` | `m³/s` | no sempre és certa: vegeu les [trampes](06-trampes.md) |
| `nivell_qualitat` | `NQ_REV0`, `NQ_REV1` | sense revisar / revisat per l'ACA |
| `valor` | `4.79` | arriba com a text |
| `utm_x`, `utm_y` | | coordenades UTM |

### Cabal diari (`2bwe-vgpr`)

`dia`, `estaci` (nom de l'estació), `conca`, `subconca`, `codi_variable`,
`descripci_variable` i `cabal_riu_m3_s`. Els codis de variable **no són els mateixos** que
als conjunts de 5 minuts: la correspondència és al [capítol 3](03-trobar-estacions.md).

### Embassaments diari (`gn9e-3qhr`)

`dia`, `estaci` (nom de l'embassament), `nivell_absolut` (m s. n. m.),
`percentatge_volum_embassat` (%) i `volum_embassat` (hm³). No hi ha codi de variable: es
filtra pel nom.

> Alguns noms de camp perden lletres accentuades (`estaci`, `descripci_variable`). Si una
> consulta falla, comprova el nom exacte a la pestanya *Dades* de la fitxa del conjunt.

## Com és una consulta

```
https://analisi.transparenciacatalunya.cat/resource/<identificador>.<json|csv>?<paràmetres>
```

| Paràmetre | Per a què | Exemple |
|---|---|---|
| `camp=valor` | filtre d'igualtat ràpid | `codi_variable=4652845` |
| `$where` | filtre general | `codi_variable='4652845' AND dia >= '2024-04-01T00:00:00'` |
| `$select` | triar camps o calcular | `dia, hora, valor` · `count(*)` · `max(valor)` |
| `$order` | ordenar | `dia, hora` · `dia DESC` |
| `$group` | agrupar | `codi_variable, descripcio_variable` |
| `$limit` | files per resposta (per defecte, **1.000**) | `50000` |
| `$offset` | saltar files (paginació) | `50000` |

- Les dates van entre cometes simples, en format `AAAA-MM-DDTHH:MM:SS`.
- Per buscar text: `upper(estacio) like '%DESP%'`.
- El navegador codifica sol els espais i els símbols. Amb curl, cal `--data-urlencode`.

## Exemples

**Un episodi concret** (crescuda d'abril del 2024 a Sant Joan Despí), en CSV:

```
https://analisi.transparenciacatalunya.cat/resource/3yr3-vq6y.csv?$select=dia, hora, valor, nivell_qualitat&$where=codi_variable='4652845' AND dia >= '2024-04-28T00:00:00' AND dia < '2024-05-02T00:00:00'&$order=dia, hora&$limit=5000
```

**El màxim de cada dia d'un mes** (calculat pel portal):

```
https://analisi.transparenciacatalunya.cat/resource/3yr3-vq6y.json?$select=dia, max(valor) AS maxim&$where=codi_variable='4652845' AND dia >= '2024-04-01T00:00:00' AND dia < '2024-05-01T00:00:00'&$group=dia&$order=dia
```

Compte: `valor` és text, i el màxim de text no és el màxim numèric. Si surt estrany,
fes servir `max(valor::number)`.

**Cabal diari oficial de Sant Joan Despí des del 1966:**

```
https://analisi.transparenciacatalunya.cat/resource/2bwe-vgpr.csv?codi_variable=4369424&$order=dia&$limit=50000
```

**Un embassament, els últims 30 dies:**

```
https://analisi.transparenciacatalunya.cat/resource/gn9e-3qhr.json?$where=estaci like '%Baells%'&$order=dia DESC&$limit=30
```

## Amb Python

```python
import pandas as pd
import requests

URL = "https://analisi.transparenciacatalunya.cat/resource/{id}.json"


def consulta(conjunt, where, select=None, order=None, pagina=50_000):
    """Totes les files d'una consulta, pàgina a pàgina."""
    files, offset = [], 0
    while True:
        params = {"$where": where, "$limit": pagina, "$offset": offset}
        if select:
            params["$select"] = select
        if order:
            params["$order"] = order  # sense ordre, la paginació no és estable
        r = requests.get(URL.format(id=conjunt), params=params, timeout=300)
        r.raise_for_status()
        part = r.json()
        files += part
        if len(part) < pagina:
            return pd.DataFrame(files)
        offset += pagina


df = consulta(
    "3yr3-vq6y",
    "codi_variable='4652845' AND dia >= '2024-04-01T00:00:00' AND dia < '2024-05-01T00:00:00'",
    select="dia, hora, valor, nivell_qualitat",
    order="dia, hora",
)
```

Per passar `dia` i `hora` a una marca de temps (vegeu el [capítol 5](05-processat-i-filtratge.md#pas-1-marca-de-temps)):

```python
def marca_de_temps(dia, hora):
    """dia + hora (UTC) → Timestamp. «24:00» és les 00:00 de l'endemà."""
    mitjanit = hora == "24:00"
    t = pd.to_datetime(dia.str[:10] + " " + hora.where(~mitjanit, "00:00"), utc=True)
    return t + pd.to_timedelta(mitjanit.astype(int), unit="D")


df["timestamp"] = marca_de_temps(df["dia"], df["hora"])
df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
```

## Amb R

```r
library(httr2)
library(jsonlite)

r <- request("https://analisi.transparenciacatalunya.cat/resource/2bwe-vgpr.json") |>
  req_url_query(codi_variable = "4369424", `$order` = "dia", `$limit` = 50000) |>
  req_perform()
df <- fromJSON(resp_body_string(r))
df$cabal_riu_m3_s <- as.numeric(df$cabal_riu_m3_s)
```

## Amb curl

```
curl -G "https://analisi.transparenciacatalunya.cat/resource/3yr3-vq6y.csv" \
  --data-urlencode "codi_variable=4652845" \
  --data-urlencode "\$order=dia DESC, hora DESC" \
  --data-urlencode "\$limit=10"
```

## Consultes grans

- **Demana una sèrie llarga mes a mes.** Una estació té unes 105.000 lectures l'any. Les
  consultes molt grans tarden minuts i el portal les pot tallar (*timeout*).
- **No agrupis tot un conjunt sencer.** Un `$group` sobre desenes de milions de files falla:
  afegeix sempre un filtre de dates o de codi.
- **Reintenta.** Els errors 429, 500, 502, 503 i 504 solen ser temporals: espera uns segons
  (cada vegada més) i torna-ho a provar.
- **Testimoni d'aplicació.** Sense registre, el portal limita les peticions seguides. Si en
  fas moltes, crea't un compte al portal, demana un *app token* gratuït i envia'l a la
  capçalera `X-App-Token`.
- **Descàrrega sencera.** El botó *Exporta* de la fitxa baixa tot el conjunt en CSV, però els
  de 5 minuts ocupen molts GB: només val la pena si vols totes les estacions de Catalunya.

[← 1. Quines dades hi ha](01-quines-dades-hi-ha.md) · [Inici](../README.md) · [3. Trobar estacions →](03-trobar-estacions.md)
