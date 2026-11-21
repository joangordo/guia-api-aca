# Dades de l'aigua a Catalunya

**Guia pràctica per descarregar i netejar les dades obertes de l'Agència Catalana de l'Aigua
(ACA)**: cabals dels rius cada 5 minuts des del 1996, cabals diaris des del 1951,
embassaments i lectures en temps real.

*A practical, unofficial guide (in Catalan) to downloading and cleaning the open hydrological
data of the Catalan Water Agency: river flows, reservoirs and real-time readings.*

> Guia **no oficial**, feta per un usuari de les dades. No té cap relació amb l'ACA. Si hi
> trobes un error, obre una *issue*.

Té dues parts que van juntes:

- **La guia** ([`guia/`](guia/)): què hi ha, com es consulta i, sobretot, com es neteja, amb
  els criteris i els casos reals que els justifiquen.
- **Els scripts** ([`scripts/`](scripts/)): un programa de Python per a cada pas, per fer-ho
  directament amb qualsevol estació de Catalunya.

No cal cap clau ni registre. Els exemples són de la conca del Llobregat, però tot funciona
igual per a qualsevol riu.

---

## Per on començar

| Vull… | Llegeix | Script |
|---|---|---|
| Saber quines dades hi ha i on | [1. Quines dades hi ha](guia/01-quines-dades-hi-ha.md) | |
| Fer la primera consulta | [2. El portal de dades obertes](guia/02-portal-dades-obertes.md) | `02`, `03` |
| Trobar els codis del meu riu o embassament | [3. Trobar estacions i codis](guia/03-trobar-estacions.md) | `01_conques.py` |
| Les darreres hores, abans que arribin al portal | [4. Temps real](guia/04-temps-real.md) | `04_temps_real.py` |
| Una sèrie llarga i neta per analitzar-la | [5. Processat i filtratge](guia/05-processat-i-filtratge.md) | `02` → `03` → `05_neteja.py` |
| Saber què pot sortir malament | [6. Trampes conegudes](guia/06-trampes.md) | |
| Un exemple sencer, amb tots els codis | [Annex: la conca del Llobregat](guia/annex-llobregat.md) | |

## Els scripts en cinc minuts

Cal Python 3.9 o posterior (si tens Anaconda, ja el tens). Baixa el repositori (botó verd
**Code → Download ZIP**, o `git clone https://github.com/joangordo/guia-api-aca.git`)
i, dins de la carpeta:

```
pip install -r requirements.txt
```

Exemple: la sèrie neta del Llobregat a Sant Joan Despí, del 1996 fins avui.

```
python scripts/01_conques.py --conca Llobregat                  # 1. codis de la conca
python scripts/02_descarrega_5min.py --codi 4652845             # 2. lectures de 5 min (~30 min)
python scripts/03_descarrega_diari.py cabal --codi 4369424      # 3. cabal diari oficial
python scripts/05_neteja.py --codi 4652845 --diari 4369424 --agrega 30min 1D --csv
```

El resultat queda a la carpeta `dades/net/`: les lectures amb el valor original, el valor
corregit, el valor net i el motiu de cada lectura descartada; la sèrie cada 30 minuts i
diària; i un `resum.txt` amb les unitats corregides, les lectures descartades per cada regla
i els màxims que convé revisar.

| Script | Què fa |
|---|---|
| [`01_conques.py`](scripts/01_conques.py) | Llista les conques, i les estacions, sèries i embassaments de cadascuna, amb els codis |
| [`02_descarrega_5min.py`](scripts/02_descarrega_5min.py) | Descarrega una sèrie de 5 minuts sencera dels tres conjunts i l'encadena. Es pot aturar i reprendre |
| [`03_descarrega_diari.py`](scripts/03_descarrega_diari.py) | Cabal diari oficial d'una estació (encadenant codis) o estat diari d'un embassament |
| [`04_temps_real.py`](scripts/04_temps_real.py) | Catàleg de sensors i darreres lectures en temps real, guardant-les de forma incremental |
| [`05_neteja.py`](scripts/05_neteja.py) | Corregeix les unitats, aplica el control de qualitat, agrega i en fa el resum |
| [`qualitat.py`](scripts/qualitat.py), [`comu.py`](scripts/comu.py) | Les funcions que fan servir els altres: es poden importar des d'un altre programa |

Cada script explica com es fa servir amb `python scripts/<nom>.py --help`. Les dades es
desen en Parquet (amb `--csv`, també en CSV per obrir-les amb Excel) a la carpeta `dades/`.

Per fer servir les funcions des d'un notebook:

```python
import sys
sys.path.append("scripts")
from qualitat import corregeix_unitats, control_qualitat, agrega
```

## Tres consultes per provar ara mateix

Copia l'adreça al navegador.

**Les 10 últimes lectures del Llobregat a Sant Joan Despí:**

```
https://analisi.transparenciacatalunya.cat/resource/3yr3-vq6y.json?codi_variable=4652845&$order=dia DESC, hora DESC&$limit=10
```

**L'estat dels embassaments de Catalunya avui** (els últims registres):

```
https://analisi.transparenciacatalunya.cat/resource/gn9e-3qhr.json?$order=dia DESC&$limit=60
```

**Totes les conques amb dades de cabal aquest mes:**

```
https://analisi.transparenciacatalunya.cat/resource/3yr3-vq6y.json?$select=conca, count(*) AS lectures&$where=dia >= '2026-11-01T00:00:00'&$group=conca&$order=conca
```

Canvia la data per la del mes en curs. I canviant `.json` per `.csv`, ho baixes en CSV.

## El procés en una imatge

```
 Portal de dades obertes (històric)            API en temps real (darrers dies)
 ├─ cabals 5 min 1996-2009  ┐
 ├─ cabals 5 min 2010-2019  ├─ 1. encadenar ──┐
 ├─ cabals 5 min 2020-avui  ┘                 │
 └─ cabal diari oficial ──── 2. corregir unitats (L/s → m³/s)
                                              │
                             3. control de qualitat (pics, zeros, sensors encallats…)
                                              │
                             4. revisió manual dels episodis grans
                                              │
                             5. agregar a 30 min / hora / dia (sense interpolar)
                                              │
                                   sèrie neta + registre del que s'ha descartat
```

Cada pas s'explica a [Processat i filtratge](guia/05-processat-i-filtratge.md), amb els
criteris concrets i els casos reals que els justifiquen, i el fan `02`, `03` i `05_neteja.py`.

Els scripts tenen proves automàtiques ([`tests/`](tests/)) amb els casos reals revisats: un pic
aïllat a Balsareny, un tram a zero en plena crescuda a Guardiola, un sensor saturat al
Monegal… i també crescudes reals molt ràpides que **no** s'han de descartar.

## Abast

- **Territori:** la xarxa de l'ACA cobreix sobretot les **conques internes de Catalunya**
  (Muga, Fluvià, Ter, Tordera, Besòs, Llobregat, Foix, Gaià, Francolí i les rieres
  litorals). Per al Segre, l'Ebre i els seus afluents, la xarxa principal és la de la
  Confederación Hidrográfica del Ebro (SAIH Ebro).
- **Pluja:** els pluviòmetres de l'ACA tenen temps real, però l'històric no és al portal
  obert (cal demanar-lo a l'ACA). La pluja de les estacions del Meteocat (XEMA) sí que hi és,
  al conjunt [`nzvn-apee`](https://analisi.transparenciacatalunya.cat/d/nzvn-apee).

## D'on surt aquesta guia

L'he escrit mentre construïa un sistema de predicció de crescudes del Llobregat a partir de
les dades de 23 aforaments i 3 embassaments. Les trampes i els criteris de neteja que hi
apareixen es van trobar i comprovar revisant episodis reals un per un.

## Fonts i llicència

Dades: **Agència Catalana de l'Aigua**, a través del portal
[Dades Obertes de Catalunya](https://analisi.transparenciacatalunya.cat) (llicència oberta
de la Generalitat; consulta la fitxa de cada conjunt) i de la seva API en temps real. Si les
fas servir, cita'n la font.

Text de la guia: [CC BY 4.0](LICENSE.md). Scripts: [MIT](LICENSE.md). Autor: Joan Gordó Guardia.
