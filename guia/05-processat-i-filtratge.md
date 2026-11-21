# 5. Processat i filtratge

[← 4. Temps real](04-temps-real.md) · [Inici](../README.md) · [6. Trampes →](06-trampes.md)

> **Script:** [`05_neteja.py`](../scripts/05_neteja.py) fa els passos 3 a 8 sobre una sèrie
> descarregada amb `02` i el seu diari descarregat amb `03`:
>
> ```
> python scripts/05_neteja.py --codi 4652845 --diari 4369424 --agrega 30min 1D
> ```
>
> Totes les regles són a [`qualitat.py`](../scripts/qualitat.py), amb els llindars a la classe
> `Parametres`. Els casos reals de la taula de regles són proves automàtiques a
> [`tests/test_qualitat.py`](../tests/test_qualitat.py).

Com passar de les lectures del portal a una **sèrie de cabal llarga i neta**. Els passos
són aquests, en aquest ordre:

1. [Marca de temps](#pas-1-marca-de-temps)
2. [Encadenar els tres trams](#pas-2-encadenar-els-tres-trams)
3. [Corregir les unitats](#pas-3-corregir-les-unitats)
4. [Control de qualitat](#pas-4-control-de-qualitat)
5. [Revisió manual](#pas-5-revisió-manual)
6. [Agregar a 30 minuts, hores o dies](#pas-6-agregar)
7. [Netejar el cabal diari](#pas-7-netejar-el-cabal-diari)
8. [Documentar el resultat](#pas-8-documentar-el-resultat)

Els criteris i els llindars no són teòrics: es van fixar revisant episodis reals de la conca
del Llobregat (1996-2026), i al costat de cada regla hi ha el cas que la justifica. Per a una
altra conca, val la pena tornar-los a comprovar.

**Principi general: no s'esborra mai res.** Es guarda el valor original i, al costat, el
valor net i el motiu pel qual s'ha descartat. Així qualsevol decisió es pot revisar o desfer.

---

## Pas 1. Marca de temps

El portal dona `dia` (data) i `hora` (`HH:MM`) per separat, **en UTC**. L'hora pot ser
`24:00`, que és les 00:00 de l'endemà.

```python
def marca_de_temps(dia, hora):
    mitjanit = hora == "24:00"
    t = pd.to_datetime(dia.str[:10] + " " + hora.where(~mitjanit, "00:00"), utc=True)
    return t + pd.to_timedelta(mitjanit.astype(int), unit="D")
```

Treballa sempre en UTC i, si cal, converteix a l'hora oficial només per mostrar els
resultats (`.dt.tz_convert("Europe/Madrid")`). Així no hi ha hores repetides ni absents
amb els canvis d'hora.

## Pas 2. Encadenar els tres trams

Les sèries de 5 minuts són en tres conjunts (1996-2009, 2010-2019 i 2020-avui) amb el mateix
`codi_variable`. Es baixen totes tres, s'ajunten i, si un instant hi és dues vegades, es
queda el del conjunt **més recent** (és el que l'ACA ha revisat més tard).

```python
# descarrega(conjunt, codi): la funció consulta() del capítol 2, mes a mes, amb les
# columnes timestamp (pas 1) i valor (numèric)
trams = [("mmzz-keb8", 0), ("9evs-b5nk", 1), ("3yr3-vq6y", 2)]
parts = [descarrega(conjunt, codi).assign(rang=rang) for conjunt, rang in trams]
serie = (
    pd.concat(parts)
    .sort_values(["timestamp", "rang"])
    .drop_duplicates("timestamp", keep="last")   # mana el conjunt més recent
    .drop(columns="rang")
)
```

Elimina també les files sense valor i les repetides dins d'un mateix conjunt (n'hi ha).

## Pas 3. Corregir les unitats

**El problema.** El portal diu que tots els cabals són en m³/s, però hi ha trams sencers en
**L/s**: al Llobregat, la major part del 2020 al 2025 en moltes estacions, i alguns trams del
1996. Un cabal de 4.790 «m³/s» a Sant Joan Despí un dia normal són, en realitat, 4,79 m³/s.

**La solució.** El cabal diari oficial (`2bwe-vgpr`) sí que és en m³/s. Per a cada dia, es
compara la **mitjana de les lectures de 5 minuts** amb el cabal diari:

```
q = log10( mitjana del dia / cabal diari oficial )
```

| q | El dia és en… |
|---|---|
| a prop de 0 (entre −0,7 i 0,7) | m³/s |
| a prop de 3 (entre 2,3 i 3,7) | L/s → es divideix per 1.000 |
| entremig | mixt (canvi d'unitat a mig dia) |
| fora d'aquests marges, o sense diari, o riu sec (diari < 0,01 m³/s) | sense classificar |

Els dies sense classificar prenen la unitat **majoritària dels 15 dies d'abans i de
després** (mediana de 31 dies, amb almenys 3 dies classificats) i, si no n'hi ha, la del dia
classificat més proper.

**Per què la mitjana del dia, i no lectura a lectura:** en una crescuda, el cabal d'un
instant pot ser desenes de vegades el mitjà del dia, i una comparació lectura a lectura el
confondria amb un canvi d'unitat.

```python
# diari: el cabal diari oficial (2bwe-vgpr) amb les columnes dia (pd.to_datetime(..., utc=True))
# i cabal (numèric, m³/s)
dia = serie["timestamp"].dt.floor("D")
mitjana = serie.groupby(dia)["valor"].mean()
oficial = diari.set_index("dia")["cabal"].reindex(mitjana.index)

q = np.log10(mitjana / oficial).where((oficial > 0.01) & (mitjana > 0))
nivell = pd.Series(np.nan, index=mitjana.index)
nivell[(q - 0).abs() < 0.7] = 0.0     # m³/s
nivell[(q - 3).abs() < 0.7] = 3.0     # L/s

tots = pd.date_range(nivell.index.min(), nivell.index.max(), freq="D", tz="UTC")
veins = nivell.reindex(tots).rolling(31, center=True, min_periods=3).median()
nivell = nivell.fillna(veins.reindex(nivell.index)).ffill().bfill().fillna(0.0)

factor = pd.Series(np.where(nivell >= 1.5, 0.001, 1.0), index=nivell.index)
serie["valor_brut"] = serie["valor"]
serie["factor_unitat"] = dia.map(factor).to_numpy()
serie["valor"] = serie["valor_brut"] * serie["factor_unitat"]
```

Si una estació té més d'una sèrie diària, fes servir la que classifica més dies (la que
quadra millor).

## Pas 4. Control de qualitat

Les dades brutes (`nivell_qualitat = NQ_REV0`, i sovint també les revisades) tenen errors de
sensor que, si no es treuen, semblen crescudes o sequeres. Cada regla **marca** lectures; el
valor net és buit on hi ha alguna marca.

### Les regles

| Regla | Què detecta | Criteri | Cas real |
|---|---|---|---|
| **pic** | Un valor aïllat molt alt | Més de **4 ×** la mediana de les 3 lectures d'abans i de les 3 de després, **+ 5 m³/s**, i per sobre del percentil 99 de l'estació | Balsareny 2008-10-17, Cardona 2007-02-07 |
| **caiguda** | Lectures a zero o gairebé enmig d'un riu que porta aigua | Un valor **< 1/10** de la mediana dels veïns quan aquests porten més d'**1 m³/s**; o un tram a ≤ **0,02 m³/s** que comença després d'una hora amb aigua (almenys 3 valors diferents) i torna a més de la meitat del nivell anterior en menys de **6 h** | Guardiola 1997-12-18 (en plena crescuda) |
| **excursio** | Un «pic» de diverses lectures que baixa massa de pressa | Pujada de més de **10 ×** la mediana de l'hora anterior, per sobre del p99, que torna a menys del **doble** d'aquell nivell en menys de **3 h**: un riu real no baixa tan ràpid | Balsareny 1997-10-30, Merlès 2017-09-27, Mediona 2026-10-03 |
| **oscil·lacio** | Dos nivells que s'alternen | **3 o més** salts de **×20** entre lectures consecutives dins de qualsevol hora: es marca tota l'hora | Mediona 2026-10-03, riera de Carme 2009-12-14 |
| **encallat** | Sensor encallat | El mateix valor exacte durant **7 dies** o més, amb més de **0,5 m³/s** (un riu sec que marca el cabal mínim no és un error) | Sant Joan Despí 1998-2000 (140 m³/s fixos), Castellbisbal |
| **pla_alt** | Sensor saturat en una crescuda | El mateix valor **6 h** o més per sobre del **percentil 95** de l'estació | el Monegal 2019-12-20 |
| **pas_unitat** | Lectures mal corregides on canvia la unitat | Salt de **×100** entre dues lectures just on canvia el factor del pas 3: es marquen els dos dies | — |
| **balanc_diari** | El dia no quadra amb el diari oficial | Amb almenys el **80 %** del dia cobert i un diari de més de 0,05 m³/s, la mitjana del dia és més de **3 ×** o menys d'**1/3** del diari oficial. Es prova amb el dia desplaçat 0, +1 i +2 h (no se sap si el diari és en hora UTC o local) i només es marca si no quadra amb cap | Sant Joan Despí 1999, Aigua de Valls |
| **exclusio** | Trams revisats a mà | Vegeu el [pas 5](#pas-5-revisió-manual) | Riera de Carme 2009-12 |

### L'ordre importa

1. Primer, `pic`, `caiguda`, `oscil·lacio`, `encallat`, `pla_alt`, `pas_unitat` i les
   exclusions.
2. Les **excursions es busquen sense els trams a zero**: si no, la tornada a l'aigua
   després d'un tram a zero semblaria una pujada sobtada.
3. El **balanç diari es calcula només amb les lectures que han superat les altres regles**:
   un pic fals no ha de fer que tot el dia sembli dolent, ni un dia dolent ha d'amagar-se
   darrere d'un pic.

### Algunes regles en codi

```python
x = serie.set_index("timestamp")["valor"]
p99 = x.quantile(0.99)

# pic: comparat amb les 3 lectures d'abans i les 3 de després
abans = x.shift(1).rolling(3, min_periods=1).median()
despres = x[::-1].shift(1).rolling(3, min_periods=1).median()[::-1]
ref = np.fmax(abans, despres)
pic = (x > 4 * ref + 5) & (x > p99)

# caiguda aïllada
veins = np.fmin(abans, despres)
caiguda = (veins > 1) & (x < veins / 10)

# encallat i pla_alt: durada de cada tram de valors idèntics
tram = (x != x.shift()).cumsum()
t = x.index.to_series()
hores = (t.groupby(tram).transform("max") - t.groupby(tram).transform("min")).dt.total_seconds() / 3600
encallat = (hores >= 24 * 7) & (x > 0.5)
pla_alt = (hores >= 6) & (x > x.quantile(0.95))

# balanç diari (només amb les lectures bones i sense el desplaçament horari, per simplificar)
bo = ~(pic | caiguda | encallat | pla_alt)
dia = x.index.floor("D")
mitjana = x[bo].groupby(dia[bo.to_numpy()]).mean()
cobertura = x[bo].groupby(dia[bo.to_numpy()]).size() / 288        # 288 lectures en un dia
quocient = mitjana / oficial.reindex(mitjana.index)
dia_dolent = (cobertura >= 0.8) & (oficial.reindex(mitjana.index) > 0.05) & (
    (quocient > 3) | (quocient < 1 / 3)
)
balanc = pd.Series(dia, index=x.index).isin(dia_dolent[dia_dolent].index)

valor_net = x.where(~(pic | caiguda | encallat | pla_alt | balanc))
```

(La cobertura es pot calcular també comptant mitges hores amb alguna lectura, que és més
robust si el sensor envia lectures cada 10 o 15 minuts.)

### El que no es corregeix

- **Sensors amb sostre**: alguns aforaments no passen d'un valor (Merlès, 127 m³/s; el
  Monegal, 10,67; l'Aigua de Valls, 32,06). En les crescudes més grans, el pic queda tallat.
  Si el sostre dura més de 6 h, `pla_alt` el marca; si és més curt, queda.
- **Diferències de ×2** entre el 5 minuts i el diari en algunes estacions petites:
  probablement, una corba de cabals revisada en una sèrie i no a l'altra. Per això el
  llindar del balanç diari és ×3 i no ×2: amb ×2 es marcaven anys sencers correctes.

## Pas 5. Revisió manual

Les regles no ho detecten tot. Abans de donar una sèrie per bona, revisa a mà:

1. **Els màxims de cada estació** (els 10 valors més alts de cada sèrie, un per episodi). Un
   màxim real té pujada i baixada graduals, apareix també a les estacions de dalt o de baix
   del riu amb un cert retard, i té un diari oficial alt el mateix dia.
2. **Els màxims de les lectures descartades**, per comprovar que no s'ha tret cap crescuda
   real.
3. **Els dies que no quadren amb el diari** (la taula del balanç diari).

Quan un tram és clarament dolent i cap regla el treu, s'afegeix a una **llista d'exclusions**
amb la data d'inici, la de final i el motiu (amb l'script, un CSV que es passa amb
`--exclusions`; n'hi ha un d'exemple a
[`scripts/exclusions_llobregat.csv`](../scripts/exclusions_llobregat.csv)). Al Llobregat:

| Sèrie | De | A | Motiu |
|---|---|---|---|
| Riera de Carme (`4652859`) | 2009-12-12 | 2009-12-23 | 140-180 m³/s gairebé constants durant dies, amb lectures d'1 o 0,05 intercalades |
| Llobregat a Castellar de n'Hug (`4652829`) | 2019-12-22 22:45 | 2019-12-23 23:59 | Salt a 568 m³/s i 104 m³/s sostinguts amb un diari oficial de 5-6 m³/s |

Una crescuda real i una avaria es poden assemblar molt. Si dubtes, compara amb les
estacions veïnes i amb la pluja.

## Pas 6. Agregar

Per analitzar o modelitzar, normalment s'agrega a 30 minuts, a 1 hora o a 1 dia:

- **Etiqueta cada interval amb el seu final**: el valor de les 10:30 és la mitjana de les
  lectures de 10:00 (exclosa) a 10:30 (inclosa). Així, la fila de l'instant *t* només conté
  informació observada fins a *t*, i no hi ha fuites d'informació en un model de predicció.
- **Cabal: la mitjana** (i, si interessa, el màxim) de les lectures netes.
- **Pluja: la suma** (en mm).
- **No interpolis en aquest pas.** Un interval sense lectures netes queda buit. Si després un
  model necessita omplir forats curts d'una variable d'entrada, fes-ho allà, documentat, i
  **mai a la variable que vols predir**.

```python
net = serie.set_index("timestamp")["valor_net"].dropna()
cada_30min = net.resample("30min", label="right", closed="right").mean()
```

## Pas 7. Netejar el cabal diari

El diari oficial és la sèrie més llarga i més neta, però també té problemes:

- **Codis que canvien**: una mateixa estació pot tenir dues o més sèries diàries amb la
  mateixa descripció i diferents codis al llarg del temps. S'encadenen per data i, on se
  solapen, mana la més recent.
- **Valors impossibles**: n'hi ha de milions de m³/s (per exemple, 3.369.195 m³/s a l'Aigua
  de Valls). Descarta els negatius i els que superin un màxim físic raonable per a la conca
  (al Llobregat, 5.000 m³/s) o unes 20 vegades el percentil 99,9 de l'estació.

## Pas 8. Documentar el resultat

Una sèrie neta només és útil si se sap què se n'ha fet. Desa al costat de les dades:

- un **diccionari de columnes**: font, codis, nom, unitat, coordenades, període i cobertura;
- per estació, el **% de dies en L/s** i en quins anys;
- per estació i regla, **quantes lectures s'han descartat**;
- la **llista d'exclusions** amb el motiu de cadascuna.

Revisa aquests recomptes: si una estació perd moltes lectures per una sola regla, mira per
què abans de fer-la servir. Al Llobregat, les que més en perden són les que han tingut el
sensor encallat durant anys (Castellbisbal, Sant Joan Despí 1998-2000).

[← 4. Temps real](04-temps-real.md) · [Inici](../README.md) · [6. Trampes →](06-trampes.md)
