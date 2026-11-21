# 6. Trampes conegudes

[← 5. Processat i filtratge](05-processat-i-filtratge.md) · [Inici](../README.md) · [Annex: Llobregat →](annex-llobregat.md)

Totes comprovades amb dades reals. Si en trobes una altra, obre una *issue*.

## Temps

1. **Totes les hores són UTC.** A l'hivern, l'hora oficial és UTC+1, i a l'estiu, UTC+2. Una
   crescuda que va passar a les 14:00 hora oficial d'estiu surt a les 12:00.
2. **`hora` pot ser `24:00`**: vol dir les 00:00 del dia següent. Molts lectors de dates la
   rebutgen o la converteixen malament.
3. **No se sap si el dia del cabal diari és UTC o local.** Quan es compara amb les lectures
   de 5 minuts, prova tots dos (vegeu el
   [balanç diari](05-processat-i-filtratge.md#les-regles)).

## Unitats i valors

4. **Trams en L/s** encara que el camp digui m³/s, sobretot del 2020 al 2025 i alguns del
   1996. És la trampa més greu: multiplica els cabals per 1.000. Vegeu el
   [pas 3](05-processat-i-filtratge.md#pas-3-corregir-les-unitats).
5. **El `valor` és text.** Cal convertir-lo a número; i a les consultes del portal,
   `max(valor)` compara text (fes servir `max(valor::number)`).
6. **Valors impossibles al cabal diari** (milions de m³/s). Cal un límit físic.
7. **Diferències sistemàtiques de ×2** entre el 5 minuts i el diari en algunes estacions
   petites. No és un error d'unitats: no les corregeixis multiplicant per 2.

## Qualitat

8. **`NQ_REV0` vol dir sense revisar.** Normalment, els darrers mesos. Hi pot haver pics
   falsos, zeros, sensors encallats o saturats.
9. **Les revisades (`NQ_REV1`) tampoc no són una garantia.** Passa tota la sèrie pel control
   de qualitat: per exemple, Sant Joan Despí va marcar 140 m³/s exactes durant mesos entre
   el 1998 i el 2000.
10. **Sensors amb sostre**: en les crescudes grans, alguns aforaments es queden en un valor
    màxim i el pic real no queda registrat.

## Consultes al portal

11. **Només 1.000 files per defecte.** Sense `$limit`, el resultat queda tallat sense cap
    avís.
12. **Paginar sense ordenar** pot repetir o saltar files: posa sempre `$order` quan facis
    servir `$offset`.
13. **Agrupar un conjunt de 5 minuts sencer** acaba en *timeout*: filtra per dates o per
    `codi_variable`.
14. **Files repetides**: el mateix instant pot sortir dues vegades al mateix conjunt.
    Elimina'n els duplicats.
15. **Noms de camp truncats**: `estaci`, `descripci_variable` (sense la `ó`).

## Cobertura

16. **Algunes estacions no tenen sèrie de 5 minuts** (per exemple, el Llobregat a
    Martorell, LB-51), però sí la diària i la de temps real.
17. **Codis diaris que canvien**: la mateixa estació, amb codis diferents en èpoques
    diferents. Cal encadenar-los.
18. **Diari «riu» i diari «total»**: algunes estacions tenen dues sèries diàries (el riu, i
    el riu més canals o derivacions). Tria la que correspon al que mesura el sensor.
19. **Embassaments cada 5 minuts**: el conjunt `vjx7-6kcp` pot tenir només els darrers
    mesos d'algun embassament. Per a l'històric, fes servir el diari (`gn9e-3qhr`).

## Temps real (Sentilo)

20. **Màxim 200 lectures per petició**, de la més recent a la més antiga, encara que es
    demani un `limit` més alt. Demana blocs de 12 hores.
21. **Escapaments invàlids** dins del JSON: cal netejar-los abans de llegir-lo.
22. **Només els darrers dies.** No serveix com a històric.

[← 5. Processat i filtratge](05-processat-i-filtratge.md) · [Inici](../README.md) · [Annex: Llobregat →](annex-llobregat.md)
