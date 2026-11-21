# 3. Trobar estacions i codis

[← 2. El portal](02-portal-dades-obertes.md) · [Inici](../README.md) · [4. Temps real →](04-temps-real.md)

> **Script:** `python scripts/01_conques.py` llista les conques i
> `python scripts/01_conques.py --conca Ter` fa els passos 1 a 4 d'aquest capítol: desa les
> sèries de 5 minuts i les diàries de la conca, i les uneix pel codi d'estació. Amb
> `--embassaments`, fa el pas 5. Vegeu [`01_conques.py`](../scripts/01_conques.py).

Per descarregar una sèrie, cal el seu **`codi_variable`**. Aquest capítol explica com
trobar-lo per a qualsevol conca, i com relacionar la mateixa estació als tres llocs on
apareix (5 minuts, diari i temps real).

Per situar les estacions en un mapa, l'ACA té el
[visor hidrològic](https://aplicacions.aca.gencat.cat/aetr/vishid/), on surten amb el nom i
les dades del moment.

## Pas 1. Quines conques hi ha

```
https://analisi.transparenciacatalunya.cat/resource/3yr3-vq6y.json?$select=conca, count(*) AS lectures&$where=dia >= '2026-11-01T00:00:00'&$group=conca&$order=conca
```

Fes servir el primer dia del mes en curs. El valor de `conca` és el que posaràs als filtres
següents.

## Pas 2. Les estacions i variables d'una conca (5 minuts)

```
https://analisi.transparenciacatalunya.cat/resource/3yr3-vq6y.csv?$select=codi_estacio, estacio, subconca, codi_variable, tipus_variable, unitat_mesura, utm_x, utm_y&$where=conca='Ter' AND dia >= '2026-11-01T00:00:00'&$group=codi_estacio, estacio, subconca, codi_variable, tipus_variable, unitat_mesura, utm_x, utm_y&$order=estacio
```

Surt una fila per sèrie: normalment, cada aforament té una variable de **cabal** i una de
**nivell**.

**El filtre de dates és imprescindible**: sense, el portal hauria d'agrupar desenes de
milions de files i talla la consulta. Per això aquesta consulta només troba les estacions
que funcionen ara. Per a les que ja no existeixen, repeteix-la amb els altres dos conjunts i
una finestra del seu període (per exemple, `mmzz-keb8` i el gener del 2009, i `9evs-b5nk` i
el gener del 2019). El mateix `codi_variable` es manté als tres conjunts.

## Pas 3. Les sèries diàries d'una conca

El conjunt diari és més petit i es pot agrupar sencer. Aquí, a més, surten el primer i
l'últim dia de cada sèrie:

```
https://analisi.transparenciacatalunya.cat/resource/2bwe-vgpr.csv?$select=estaci, codi_variable, descripci_variable, min(dia) AS inici, max(dia) AS fi, count(*) AS dies&$where=conca='Ter'&$group=estaci, codi_variable, descripci_variable&$order=estaci
```

Hi sortiran també les **sortides de les preses**, que són al conjunt diari com si fossin
aforaments.

## Pas 4. Relacionar el 5 minuts amb el diari

Els codis de variable són diferents, però el **codi de l'estació** és el mateix:

| | Camp | Exemple |
|---|---|---|
| 5 minuts | `codi_estacio` | `EA049_C4049` |
| Diari | `descripci_variable` | `EA049_Sant Joan Despi_Cabal riu Llobregat` |

La primera part (`EA049`) les uneix. Algunes estacions tenen **més d'una sèrie diària**:

- perquè el codi va canviar en algun moment: cal **encadenar-les** per data;
- perquè n'hi ha una del riu i una de «total» (riu més canals): tria la que s'assembla més
  a la sèrie de 5 minuts. Una manera senzilla: compara la mitjana d'un any de cadascuna amb
  la mitjana de les lectures de 5 minuts del mateix any (amb les unitats ja corregides).

```python
def prefix(codi):
    return str(codi).split("_")[0]          # 'EA049_C4049' → 'EA049'

diari["prefix"] = diari["descripci_variable"].map(prefix)
cinc_min["prefix"] = cinc_min["codi_estacio"].map(prefix)
parelles = cinc_min.merge(diari, on="prefix", suffixes=("_5min", "_diari"))
```

## Pas 5. Els embassaments

```
https://analisi.transparenciacatalunya.cat/resource/gn9e-3qhr.json?$select=estaci, min(dia) AS inici, max(dia) AS fi&$group=estaci&$order=estaci
```

El diari d'embassaments es filtra pel nom (`estaci like '%Sau%'`). La sortida d'aigua de la
presa no hi és: és al conjunt de cabals diaris (pas 3), com una estació més.

## Pas 6. El mateix sensor en temps real

L'API en temps real fa servir uns altres codis (`AFORAMENT-EST/CALC001261`). El
[catàleg](04-temps-real.md#el-catàleg-de-sensors) dona per a cada sensor la descripció i
les coordenades: es relaciona amb el portal pel nom de l'estació i, si cal, per la
proximitat de les coordenades (el portal les dona en UTM i el catàleg, en latitud i
longitud).

Comprova sempre la correspondència: les últimes lectures del sensor en temps real han de
coincidir amb les últimes del portal per al mateix instant.

## Exemple sencer

A l'[annex del Llobregat](annex-llobregat.md) hi ha la taula completa de 23 aforaments i
3 embassaments, amb els codis de 5 minuts, del diari i del temps real.

[← 2. El portal](02-portal-dades-obertes.md) · [Inici](../README.md) · [4. Temps real →](04-temps-real.md)
