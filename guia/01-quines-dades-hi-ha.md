# 1. Quines dades hi ha i on

[← Inici](../README.md) · [2. El portal →](02-portal-dades-obertes.md)

L'ACA publica les dades hidrològiques per **dues vies**, totes dues públiques i sense clau:

| Via | Adreça | Per a què |
|---|---|---|
| **Portal de dades obertes** de la Generalitat | `analisi.transparenciacatalunya.cat` | L'històric: des del 1951 (diari) i des del 1996 (cada 5 minuts) |
| **API en temps real** de l'ACA | `aplicacions.aca.gencat.cat/sdim2/apirest` | Les darreres hores i dies de cada sensor |

## Què hi ha al portal

| Dades | Conjunt | Període | Cada |
|---|---|---|---|
| Cabal i nivell dels rius | [`mmzz-keb8`](https://analisi.transparenciacatalunya.cat/d/mmzz-keb8) | 1996 – 2009 | 5 min |
| Cabal i nivell dels rius | [`9evs-b5nk`](https://analisi.transparenciacatalunya.cat/d/9evs-b5nk) | 2010 – 2019 | 5 min |
| Cabal i nivell dels rius | [`3yr3-vq6y`](https://analisi.transparenciacatalunya.cat/d/3yr3-vq6y) | 2020 – avui | 5 min |
| Cabal mitjà diari oficial (inclou les sortides de les preses) | [`2bwe-vgpr`](https://analisi.transparenciacatalunya.cat/d/2bwe-vgpr) | 1951 – avui | dia |
| Volum, nivell i % dels embassaments | [`gn9e-3qhr`](https://analisi.transparenciacatalunya.cat/d/gn9e-3qhr) | 2000 – avui | dia |
| Volum i nivell dels embassaments | [`vjx7-6kcp`](https://analisi.transparenciacatalunya.cat/d/vjx7-6kcp) | recent | 5 min |

Els tres conjunts de 5 minuts són **una sola sèrie partida en tres**: tenen el mateix format i
els mateixos codis. Per a una sèrie del 1996 ençà, es demana el mateix codi als tres.

L'ACA en té més (qualitat de l'aigua, aqüífers, sequera…). Per veure'ls tots:

```
https://api.us.socrata.com/api/catalog/v1?domains=analisi.transparenciacatalunya.cat&q=ACA&limit=100
```

## Què hi ha en temps real

L'API en temps real dona les lectures dels sensors de la xarxa de l'ACA amb pocs minuts de
retard: aforaments (cabal, nivell), embassaments (volum, nivell, sortida de la presa) i
pluviòmetres (intensitat de pluja). **No guarda l'històric**: només els darrers dies. Vegeu
[4. Temps real](04-temps-real.md).

## Què no hi ha

- **L'històric dels pluviòmetres de l'ACA.** Es pot demanar a l'ACA, que l'envia en fitxers
  Excel per conca.
- **Algunes sèries de 5 minuts:** hi ha estacions que només tenen la sèrie diària (per
  exemple, el Llobregat a Martorell, LB-51).
- **Les conques de l'Ebre i del Segre**, en bona part: la xarxa d'aforaments principal hi és
  la de la Confederación Hidrográfica del Ebro.

## Quina via fer servir

| Vull… | Fes servir |
|---|---|
| Una sèrie de molts anys | El portal, cada 5 minuts (i el diari per comprovar-la) |
| Una estadística mensual o anual | El cabal diari oficial: és més net i més llarg |
| L'estat dels embassaments | El diari d'embassaments |
| Saber què passa ara mateix | L'API en temps real |
| Un registre continu fins avui | El portal i, per a les últimes hores, el temps real |

[← Inici](../README.md) · [2. El portal →](02-portal-dades-obertes.md)
