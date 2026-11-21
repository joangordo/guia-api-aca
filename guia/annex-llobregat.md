# Annex: la conca del Llobregat

[← 6. Trampes](06-trampes.md) · [Inici](../README.md)

Tots els codis per descarregar la conca del Llobregat, i els episodis reals que van servir
per definir el [control de qualitat](05-processat-i-filtratge.md#pas-4-control-de-qualitat).

## Aforaments

| Estació | Codi ACA | 5 min (`codi_variable`) | Diari (`codi_variable`) | Temps real (Sentilo) |
|---|---|---|---|---|
| Llobregat a Sant Joan Despí | LB-60 | `4652845` | `4369424` | `AFORAMENT-EST/CALC001261` |
| Llobregat a Martorell | LB-51 | — | `4369418` | `AFORAMENT-EST/CALC001975` |
| Llobregat a Castellbisbal | LB-30 | `4652836` | `4369411` | `AFORAMENT-EST/CALC001446` |
| Llobregat a Castellbell i el Vilar | LB-25 | `4652790` | `4261138` | `AFORAMENT-EST/CALC001244` |
| Llobregat a Balsareny | LB-15 | `4652787` | `4261134` | `AFORAMENT-EST/CALC001230` |
| Llobregat a Olvan (Berga) | LB-05 | `4652828` | `4369160` | `AFORAMENT-EST/CALC001304` |
| Llobregat a Guardiola de Berguedà | LA-10 | `4652795` | `4290751` | `AFORAMENT-EST/CALC001228` |
| Llobregat a Castellar de n'Hug | LA-05 | `4652829` | `4369171` | `AFORAMENT-EST/CALC001223` |
| Riera de Peguera (Cercs) | LA-15 | — | `4369415` | `AFORAMENT-EST/CALC001669` |
| Riu Merdançol (Vilada) | LA-20 | `4652847` | `4369430` | `AFORAMENT-EST/CALC001622` |
| Vilada | LA-25 | `4652849` | `4369432` | `AFORAMENT-EST/CALC001627` |
| Riera de Merlès | LB-10 | `4652841` | `4369420` | `AFORAMENT-EST/CALC001514` |
| Gavarresa (Artés) | LB-20 | `4652843` | `4369422` | `AFORAMENT-EST/CALC001237` |
| Cardener al Monegal (Guixers) | CA-05 | `4652865` | `4372679` | `AFORAMENT-EST/CALC001632` |
| Riera Aigua de Valls (Guixers) | CA-10 | `4652834` | `4369407` | `AFORAMENT-EST/CALC001532` |
| Riera d'Aiguadora (Navès) | CB-05 | `4652854` | `4369441` | `AFORAMENT-EST/CALC001550` |
| Cardener a Cardona | CB-10 | `4652832` | `4369406` | `AFORAMENT-EST/CALC001241` |
| Cardener a Súria | CB-15 | `4652788` | `4261135` | `AFORAMENT-EST/CALC001274` |
| Anoia a Sant Sadurní d'Anoia | LB-45 | `4652819` | `4368233` | `AFORAMENT-EST/CALC001249` |
| Riera de Mediona | LB-35 | `4652863` | `4369453` | `AFORAMENT-EST/CALC001266` |
| Riera de Carme | LB-40 | `4652859` | `4369449` | `AFORAMENT-EST/CALC001510` |
| Anoia a Martorell | LB-50 | `4652861` | `4369451` | `AFORAMENT-EST/CALC001836` |
| Riera de Rubí | LB-53 | `4652857` | `4369445` | `AFORAMENT-EST/CALC001256` |

El nivell del riu a Sant Joan Despí és `4652846` (5 min) i
`AFORAMENT-EST/082172-002-ANA010` (temps real).

**Diari de Guardiola:** fes servir `4290751` (el riu), no la sèrie «total».

## Embassaments

| Embassament | Sortida de la presa, diari (`2bwe-vgpr`) | Nom a `gn9e-3qhr` | Volum / nivell, 5 min (`vjx7-6kcp`) |
|---|---|---|---|
| la Baells | `4165139`, `4462770` (encadenats) | Embassament de la Baells (Cercs) | `4657203` / `4657202` |
| la Llosa del Cavall | `4165460` | Embassament de la Llosa del Cavall (Navès) | `4657205` / `4657204` |
| Sant Ponç | `4165146` | Embassament de Sant Ponç (Clariana de Cardener) | `4657207` / `4657206` |

En temps real (sortida, volum, nivell):

| Embassament | Sensors |
|---|---|
| la Baells | `AFORAMENT-EST/CALC000736`, `EMBASSAMENT-EST/CALC000697`, `EMBASSAMENT-EST/082687-001-ANA015` |
| la Llosa del Cavall | `AFORAMENT-EST/CALC000719`, `EMBASSAMENT-EST/CALC000698`, `EMBASSAMENT-EST/081419-003-ANA005` |
| Sant Ponç | `AFORAMENT-EST/CALC000737`, `EMBASSAMENT-EST/CALC000699`, `EMBASSAMENT-EST/250753-004-ANA010` |

## Pluviòmetres de l'ACA en temps real

Intensitat de pluja (mm/h), proveïdor `PLUVIOMETREACA-EST`:

| Lloc | Sensor |
|---|---|
| Castellar de n'Hug | `080522-006-ANA007` |
| Cercs (la Baells) | `082687-001-ANA016` |
| Guardiola de Berguedà | `080996-007-ANA009` |
| Artés (Gavarresa) | `081918-009-ANA002` |
| Guixers (Aigua de Valls) | `251116-004-ANA04` |
| Navès (Aiguadora) | `251462-001-ANA04` |
| Navès (la Llosa del Cavall) | `081419-003-ANA006` |
| Clariana de Cardener (Sant Ponç) | `250753-004-ANA011` |
| Cardona | `080478-006-ANA004` |
| Súria | `082747-007-ANA003` |
| Sant Sadurní d'Anoia | `082401-002-ANA002` |
| Sant Quintí de Mediona | `082362-002-ANA03` |
| Castellbell i el Vilar | `080538-005-ANA003` |
| Abrera (ETAP) | `080018-005-ANA016` |
| el Papiol (riera de Rubí) | `081580-002-ANA008` |
| Sant Vicenç dels Horts | `082634-001-ANA017` |
| Sant Joan Despí (ETAP) | `082172-002-ANA014` |

## Episodis revisats

Casos reals que es van mirar un per un i la regla que els tracta:

| Estació | Data | Què passava | Regla |
|---|---|---|---|
| Balsareny | 1997-10-30 | Pujada de ×10 que torna al nivell d'abans en menys de 3 h | excursio |
| Guardiola | 1997-12-18 | Tram a zero en plena crescuda | caiguda |
| Sant Joan Despí | 1998-2000 | 140 m³/s exactes durant mesos | encallat, balanc_diari |
| Cardona | 2007-02-04 i 07 | Excursió i pic aïllat | excursio, pic |
| Balsareny | 2008-10-17 | Pic aïllat | pic |
| Riera de Carme | 2009-12-12 a 23 | 140-180 m³/s quasi constants amb lectures d'1 o 0,05 intercalades | oscil·lacio, exclusió manual |
| Merlès | 2017-09-27 | Pujada sobtada que baixa en menys de 3 h | excursio |
| el Monegal | 2019-12-20 | Valor fix durant hores en plena crescuda (sensor saturat) | pla_alt |
| Castellar de n'Hug | 2019-12-22 a 23 | 568 m³/s i 104 m³/s sostinguts amb un diari de 5-6 m³/s | exclusió manual |
| Mediona | 2026-10-03 | Dos nivells alternant-se i pujades falses | oscil·lacio, excursio |
| Castellbisbal | diversos anys | Sensor encallat | encallat |

Les crescudes més grans a Sant Joan Despí des del 1996 (lectura màxima de 5 minuts, un cop
aplicat el control de qualitat):

| Data | Cabal màxim | Episodi |
|---|---|---|
| 2020-01-24 | ~1.470 m³/s | temporal Glòria |
| 2018-11 | ~1.000 m³/s | |
| 2000-06 | ~1.000 m³/s | |
| 1999-10 | ~960 m³/s | |
| 2010-10 | ~950 m³/s | |

[← 6. Trampes](06-trampes.md) · [Inici](../README.md)
