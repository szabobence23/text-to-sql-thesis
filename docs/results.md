# Végső mérések

Az összes beállítás egyetlen commiton fut (`ea83c19`, tiszta munkakönyvtár), ugyanazzal a modellel (`qwen2.5-coder:7b`, temperature 0, seed 42, `num_ctx` 8192), 2026-11-08-án, egymás után, más Ollama-terhelés nélkül. A tesztkészlet 3 adatbázisból áll, mindegyikhez 50 kérdés tartozik magyarul és angolul is. Ez beállításonként 300 kérdés. Az angol kérdések a magyarok fordításai, a helyes lekérdezésük ugyanaz. Minden beállítás egyszer fut le. Megismételt futásoknál az eredmény gyakorlatilag ugyanaz (lásd a „Reprodukálhatóság” részt), ezért a bizonytalanság forrása a kérdések száma. Ezt mutatja a 95%-os Wilson-intervallum. Két beállítás összevetésére a párosított egzakt McNemar-próba szolgál, kérdésenként.

Előállítás:

```
python src/evaluation/run_batch.py --run-name final-<név> --repeats 1 <kapcsolók>
python src/evaluation/compare.py final-m1-baseline ... --labels ... --reference final-m1-baseline --markdown <fájl>
```

## 1. Fő táblázat (relaxed EX, az alaphoz képest)

| Beállítás | Olist | F1 | AdventureWorks | hu | en | Összesen | 95% CI | Δ vs. Alap | +/− | McNemar p |
|---|---|---|---|---|---|---|---|---|---|---|
| Alap | 51/100 | 51/100 | 55/100 | 70/150 | 87/150 | **157/300** (52%) | 47%–58% | — | — | — |
| Alap (ismétlés) | 53/100 | 51/100 | 55/100 | 72/150 | 87/150 | **159/300** (53%) | 47%–59% | +2 | +2 / −0 | 0.500 |
| + RAG | 53/100 | 48/100 | 63/100 | 70/150 | 94/150 | **164/300** (55%) | 49%–60% | +7 | +26 / −19 | 0.371 |
| + 2 javítókör | 61/100 | 54/100 | 62/100 | 80/150 | 97/150 | **177/300** (59%) | 53%–64% | +20 | +21 / −1 | < 0.001 |
| + 5 példa | 67/100 | 73/100 | 70/100 | 92/150 | 118/150 | **210/300** (70%) | 65%–75% | +53 | +67 / −14 | < 0.001 |
| 5 példa + javítás | 69/100 | 76/100 | 73/100 | 96/150 | 122/150 | **218/300** (73%) | 67%–77% | +61 | +71 / −10 | < 0.001 |
| 5 példa + RAG | 71/100 | 77/100 | 76/100 | 104/150 | 120/150 | **224/300** (75%) | 69%–79% | +67 | +75 / −8 | < 0.001 |
| Mind együtt (web UI) | 76/100 | 80/100 | 79/100 | 108/150 | 127/150 | **235/300** (78%) | 73%–83% | +78 | +82 / −4 | < 0.001 |
| Mind együtt, orákulum séma | 77/100 | 80/100 | 86/100 | 114/150 | 129/150 | **243/300** (81%) | 76%–85% | +86 | +89 / −3 | < 0.001 |
| Mind együtt + oszlopértékek | 76/100 | 79/100 | 80/100 | 108/150 | 127/150 | **235/300** (78%) | 73%–83% | +78 | +81 / −3 | < 0.001 |

A „+/−” oszlop azoknak a kérdéseknek a száma, amelyeket csak az adott beállítás, illetve csak a viszonyítási alap oldott meg helyesen. A McNemar-próba ezekből számol.

| Beállítás | Evaluator-kapcsolók | Batch |
|---|---|---|
| Alap | `(alap)` | `final-m1-baseline` |
| Alap (ismétlés) | `(alap)` | `final-m1-baseline-rerun` |
| + RAG | `--rag` | `final-m2-rag` |
| + 2 javítókör | `--correction-rounds 2` | `final-m3-corr2` |
| + 5 példa | `--sql-examples 5` | `final-m4-fewshot5` |
| 5 példa + javítás | `--sql-examples 5 --correction-rounds 2` | `final-m5-fewshot5-corr2` |
| 5 példa + RAG | `--sql-examples 5 --rag` | `final-m6-fewshot5-rag` |
| Mind együtt (web UI) | `--sql-examples 5 --correction-rounds 2 --rag` | `final-m7-full` |
| Mind együtt, orákulum séma | `--sql-examples 5 --correction-rounds 2 --schema-retrieval oracle` | `final-m8-full-oracle` |
| Mind együtt + oszlopértékek | `--sql-examples 5 --correction-rounds 2 --rag --column-values` | `final-m9-full-colvalues` |

Mit jelentenek a kapcsolók:

- **RAG** (`pipeline.RAG_SETTINGS`): bge-m3 sémakeresés, 10 jelölt tábla, FK-hidak és szigorú LLM-es táblaválasztás.
- **2 javítókör:** ha az SQL érvénytelen, vagy hibával áll le, a modell a PostgreSQL hibaüzenetét kapja vissza, legfeljebb kétszer.
- **5 példa:** dinamikus few-shot. Az `examples.json` öt, a kérdéshez leghasonlóbb megoldott példája kerül a promptba, SQL-lel együtt.
- **Orákulum séma:** csak a helyes lekérdezés által olvasott táblák szerepelnek a sémában. Ez csak kiértékelésre használható felső korlát.
- **Oszlopértékek:** a legfeljebb 50 különböző értékű szöveges oszlopok értékei bekerülnek a sémaszövegbe.

## 2. Ugyanez strict EX-szel

A strict EX azonos sorokat és oszlopokat követel meg, extra oszlop nem megengedett.

| Beállítás | Olist | F1 | AdventureWorks | hu | en | Összesen | 95% CI | Δ vs. Alap | +/− | McNemar p |
|---|---|---|---|---|---|---|---|---|---|---|
| Alap | 39/100 | 47/100 | 51/100 | 64/150 | 73/150 | **137/300** (46%) | 40%–51% | — | — | — |
| Alap (ismétlés) | 41/100 | 47/100 | 51/100 | 66/150 | 73/150 | **139/300** (46%) | 41%–52% | +2 | +2 / −0 | 0.500 |
| + RAG | 38/100 | 42/100 | 59/100 | 62/150 | 77/150 | **139/300** (46%) | 41%–52% | +2 | +22 / −20 | 0.878 |
| + 2 javítókör | 43/100 | 50/100 | 54/100 | 69/150 | 78/150 | **147/300** (49%) | 43%–55% | +10 | +11 / −1 | 0.006 |
| + 5 példa | 57/100 | 64/100 | 66/100 | 80/150 | 107/150 | **187/300** (62%) | 57%–68% | +50 | +67 / −17 | < 0.001 |
| 5 példa + javítás | 59/100 | 65/100 | 68/100 | 83/150 | 109/150 | **192/300** (64%) | 58%–69% | +55 | +71 / −16 | < 0.001 |
| 5 példa + RAG | 61/100 | 67/100 | 71/100 | 90/150 | 109/150 | **199/300** (66%) | 61%–71% | +62 | +75 / −13 | < 0.001 |
| Mind együtt (web UI) | 66/100 | 68/100 | 73/100 | 93/150 | 114/150 | **207/300** (69%) | 64%–74% | +70 | +82 / −12 | < 0.001 |
| Mind együtt, orákulum séma | 66/100 | 70/100 | 81/100 | 101/150 | 116/150 | **217/300** (72%) | 67%–77% | +80 | +88 / −8 | < 0.001 |
| Mind együtt + oszlopértékek | 66/100 | 67/100 | 74/100 | 93/150 | 114/150 | **207/300** (69%) | 64%–74% | +70 | +81 / −11 | < 0.001 |

A sorrend és a szignifikancia ugyanaz, mint relaxed EX-nél. A két mérőszám közti különbség (157 → 137 az alapnál, 235 → 207 a teljes beállításnál) azokból a válaszokból jön, amelyek a kért oszlopokon kívül további oszlopokat is visszaadnak, például a név mellé az azonosítót vagy a darabszámot.

## 3. A teljes beállításhoz (web UI) képest

| Beállítás | Olist | F1 | AdventureWorks | hu | en | Összesen | 95% CI | Δ vs. Mind együtt (web UI) | +/− | McNemar p |
|---|---|---|---|---|---|---|---|---|---|---|
| Alap | 51/100 | 51/100 | 55/100 | 70/150 | 87/150 | **157/300** (52%) | 47%–58% | -78 | +4 / −82 | < 0.001 |
| Alap (ismétlés) | 53/100 | 51/100 | 55/100 | 72/150 | 87/150 | **159/300** (53%) | 47%–59% | -76 | +5 / −81 | < 0.001 |
| + RAG | 53/100 | 48/100 | 63/100 | 70/150 | 94/150 | **164/300** (55%) | 49%–60% | -71 | +3 / −74 | < 0.001 |
| + 2 javítókör | 61/100 | 54/100 | 62/100 | 80/150 | 97/150 | **177/300** (59%) | 53%–64% | -58 | +7 / −65 | < 0.001 |
| + 5 példa | 67/100 | 73/100 | 70/100 | 92/150 | 118/150 | **210/300** (70%) | 65%–75% | -25 | +6 / −31 | < 0.001 |
| 5 példa + javítás | 69/100 | 76/100 | 73/100 | 96/150 | 122/150 | **218/300** (73%) | 67%–77% | -17 | +7 / −24 | 0.003 |
| 5 példa + RAG | 71/100 | 77/100 | 76/100 | 104/150 | 120/150 | **224/300** (75%) | 69%–79% | -11 | +0 / −11 | < 0.001 |
| Mind együtt (web UI) | 76/100 | 80/100 | 79/100 | 108/150 | 127/150 | **235/300** (78%) | 73%–83% | — | — | — |
| Mind együtt, orákulum séma | 77/100 | 80/100 | 86/100 | 114/150 | 129/150 | **243/300** (81%) | 76%–85% | +8 | +16 / −8 | 0.152 |
| Mind együtt + oszlopértékek | 76/100 | 79/100 | 80/100 | 108/150 | 127/150 | **235/300** (78%) | 73%–83% | +0 | +3 / −3 | 1.000 |

## 4. Lépésenként, adatbázisonként (relaxed EX, magyar és angol együtt, n = 100)

| Lépés | Olist | F1 | AdventureWorks |
|---|---|---|---|
| Alap → + RAG | 51 → 53 (+9/−7, p = 0.804) | 51 → 48 (+5/−8, p = 0.581) | 55 → 63 (+12/−4, p = 0.077) |
| Alap → + 2 javítókör | 51 → 61 (+11/−1, p = 0.006) | 51 → 54 (+3/−0, p = 0.250) | 55 → 62 (+7/−0, p = 0.016) |
| Alap → + 5 példa | 51 → 67 (+20/−4, p = 0.002) | 51 → 73 (+26/−4, p < 0.001) | 55 → 70 (+21/−6, p = 0.006) |
| 5 példa → + RAG | 67 → 71 (+7/−3, p = 0.344) | 73 → 77 (+6/−2, p = 0.289) | 70 → 76 (+9/−3, p = 0.146) |
| 5 példa → + javítás | 67 → 69 (+2/−0, p = 0.500) | 73 → 76 (+3/−0, p = 0.250) | 70 → 73 (+3/−0, p = 0.250) |
| 5 példa + RAG → + javítás (= web UI) | 71 → 76 (+5/−0, p = 0.063) | 77 → 80 (+3/−0, p = 0.250) | 76 → 79 (+3/−0, p = 0.250) |
| Web UI → orákulum séma | 76 → 77 (+3/−2, p = 1.000) | 80 → 80 (+3/−3, p = 1.000) | 79 → 86 (+10/−3, p = 0.092) |
| Web UI → + oszlopértékek | 76 → 76 (+0/−0) | 80 → 79 (+2/−3, p = 1.000) | 79 → 80 (+1/−0, p = 1.000) |

## 5. Részletek

### Érvényes lekérdezések és javítókörök

| Beállítás | Érvényes és lefutott SQL | Javítás indult | Ebből lefutott | Ebből helyes lett |
|---|---|---|---|---|
| Alap | 252/300 | — | — | — |
| + RAG | 258/300 | — | — | — |
| + 2 javítókör | 286/300 | 42 | 28 | 15 |
| + 5 példa | 278/300 | — | — | — |
| 5 példa + javítás | 294/300 | 22 | 16 | 8 |
| 5 példa + RAG | 278/300 | — | — | — |
| Mind együtt (web UI) | 296/300 | 22 | 18 | 11 |
| Mind együtt, orákulum séma | 299/300 | 19 | 18 | 8 |
| Mind együtt + oszlopértékek | 295/300 | 22 | 17 | 12 |

A javítás csak akkor fut, ha az első kísérlet érvénytelen vagy hibával áll le, ezért egy helyes, de rossz eredményt adó lekérdezést nem javít ki. Few-shot mellett kevesebb a hibás első kísérlet, ezért a javítás is kevesebbet tud hozzátenni: +20 helyett +8 (210 → 218, +8/−0, p = 0.008) és +11. Egyetlen kérdés sem romlott el a javítástól. Ez szerkezetileg sem lehetséges, mert hibás első kísérlet helyes sem lehetett.

### RAG: a táblakeresés teljessége

A RAG-os futásokban a kérdések ennyi részénél volt meg a sémában minden szükséges tábla: Olist 92/100, F1 73/100, AdventureWorks 77/100. Ez mindhárom RAG-beállításban ugyanannyi, mert a few-shot és a javítás nem befolyásolja a táblaválasztást. Egyedül alkalmazva a RAG csak a nagy sémán (AdventureWorks, 68 tábla) javított: 55 → 63, p = 0.077. A kis sémákon a hiányzó táblák és a rövidebb séma hatása nagyjából kiegyenlíti egymást. Few-shot mellett viszont mindhárom adatbázison +4–6 kérdést hozott: összesen 210 → 224, +22/−8, p = 0.016; adatbázisonként egyenként nem szignifikáns. Ennek valószínű oka, hogy a példák SQL-je pótolja a táblaválasztás hibáit.

### Nyelv: magyar vs. angol

| Beállítás | hu | en | csak en jó / csak hu jó | McNemar p |
|---|---|---|---|---|
| Alap | 70/150 | 87/150 | 23 / 6 | 0.002 |
| + 5 példa | 92/150 | 118/150 | 31 / 5 | < 0.001 |
| Mind együtt (web UI) | 108/150 | 127/150 | 24 / 5 | < 0.001 |
| Mind együtt, orákulum séma | 114/150 | 129/150 | 19 / 4 | 0.003 |

Minden beállításban szignifikánsan jobb az angol. A különbség nem tűnik el a módszerekkel: 11 pont az alapnál, 13 pont a teljes beállításnál. A magyar kérdés tehát nehezebb a 7B modellnek, a módszerek pedig nagyjából ugyanannyit javítanak mindkét nyelven. Kivétel a RAG few-shot mellett: magyarul +12 (92 → 104), angolul +2 (118 → 120).

### Költség

| Beállítás | Átlagos idő / kérdés | Átlagos prompt-token / kérdés | Legnagyobb prompt |
|---|---|---|---|
| Alap | 2.6 s | 2302 | 4807 |
| + RAG | 3.1 s | 418 | 859 |
| + 2 javítókör | 3.2 s | 2811 | 5199 |
| + 5 példa | 2.6 s | 2681 | 5212 |
| Mind együtt (web UI) | 3.4 s | 890 | 1424 |
| Mind együtt + oszlopértékek | 3.5 s | 1023 | 2032 |

Az idő az SQL elkészítését jelenti: generálás, keresés, táblaválasztás, validáció és futtatás, természetes nyelvű válasz nélkül. A tokenszám a modellhívások összege. A RAG a prompt hosszát harmadára–ötödére csökkenti, és egy plusz modellhívás (a táblaválasztás) miatt mégis csak ~0.5 s-mal lassabb.

### Reprodukálhatóság

Az alapbeállítás ugyanazon a commiton kétszer futott (Alap és Alap (ismétlés)). Az F1 és az AdventureWorks futások SQL-je karakterre megegyezett. Az Olistnál 13 lekérdezés szövege tért el, ebből 2 kérdés eredménye: 157 vs. 159 helyes. A javítókörös futások első kísérlete ugyanaz a prompt, mint a javítás nélküli futásé. Few-shot mellett mindkét párnál mind a 300 kérdés kimenetele egyezett, az „Alap” és a „+ 2 javítókör” első kísérleteinél 7 kérdés tért el (a 300-ból 162 helyes). Azonos promptra tehát az Ollama nem mindig ad bitre azonos választ, valószínűleg az előző kérések és a GPU-memória állapota miatt. A kimenetelben ez legfeljebb ~2%, ±3–5 kérdés a 300-ból. Ez jóval kisebb a few-shot (+53) vagy a teljes beállítás (+78) hatásánál, de összemérhető a RAG egyedüli (+7), az orákulum séma (+8) és az oszlopértékek (0) hatásával. Ezeket ezért nem szabad szignifikáns különbségként értelmezni.

## 6. Biztonság: támadásmérés

Az `attacks.json` 27 kézzel írt, támadó célú lekérdezést tartalmaz. Ezek LLM nélkül, közvetlenül mennek végig a védelmi rétegeken. A készlet csak az Olisthoz van megírva, mert a védelmi rétegek nem függenek az adatbázistól.

| Futás | Szerkezet | Függvény-tiltólista | Séma | Adatbázis | Átjutott | A várt rétegen |
|---|---|---|---|---|---|---|
| A `pg_stat_activity` visszavonása előtt | 12 | 10 | 0 | 2 | 3 (#25–27) | 24/27 |
| Visszavonás után | 12 | 10 | 0 | 5 | 0 | 27/27 |
| Visszavonás után, tiltólista nélkül | 12 | — | 1 | 10 | 4 (#16–19) | 17/27 |
| Visszavonás után, MCP-szerveren át (`run_sql`) | 12 | 10 | 0 | 5 | 0 | 27/27, mind ugyanott, mint közvetlenül |

- **#25–27:** más munkamenetek futó lekérdezéseinek olvasása. Az alkalmazás minden kliense ugyanazzal a szerepkörrel csatlakozik, ezért egy MCP-kliens láthatta volna például a web UI kérdéseit. A `readonly_role.sql` azóta visszavonja ezt a jogot, és mindhármat az adatbázis állítja meg.
- **Tiltólista nélkül** a függvényalapú támadások közül négy átjut: más munkamenet leállítása, az időkorlát kikapcsolása, tartós advisory lock és dinamikus SQL. A többit a szerepkör jogai, az időkorlát vagy a sémaellenőrzés megfogja. A tiltólista tehát mélységi védelem: a csak olvasási jogú szerepkör egyedül nem elég.

## 7. Következtetések

1. **A legnagyobb hatású módszer a dinamikus few-shot.** Egyedül +53 kérdés (52% → 70%), mindhárom adatbázison szignifikánsan, egyenként is.
2. **A javítókörök biztosan javítanak, de keveset.** Romlást nem okoznak: +20 az alapon, +8–11 few-shot mellett. Egy futáson belül ez szerkezeti tulajdonság. Egyedül a hibás vagy érvénytelen SQL-en segítenek.
3. **A RAG egyedül csak nagy sémán hasznos** (AdventureWorks +8). Few-shottal együtt mindhárom adatbázison javít (összesen +14, p = 0.016), és a promptot harmadára–ötödére rövidíti.
4. **Együtt: 52% → 78%** (157 → 235 / 300, p < 0.001). Ez a web UI és az MCP-szerver beállítása.
5. **Az orákulum séma (tökéletes táblakeresés) csak +8 kérdést adna.** Ez szinte teljesen az AdventureWorksből jön (79 → 86), és nem szignifikáns. A hátralévő ~20% hibát tehát nem a táblakeresés okozza, hanem az SQL-logika: aggregálás, holtversenyek, domain-szabályok.
6. **Az oszlopértékek nem hoznak semmit** a teljes beállítás mellett (+3/−3). A few-shot példák már megmutatják a kategóriák helyes írásmódját.
7. **A magyar kérdések minden beállításban nehezebbek:** 15–26 kérdéssel kevesebb helyes a 150-ből. A módszerek ezt a különbséget nem tüntetik el.
