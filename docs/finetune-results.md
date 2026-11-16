# Fine-tuning: mérés

A finomhangolt modell (`qwen2.5-coder-7b-ft`) a Qwen2.5-Coder-7B-Instruct LoRA-val tanítva, a BIRD train készletén. A tanítás menete, a beállítások és a bérelt gép: [finetune.md](finetune.md). Itt az a kérdés, hogy a nyilvános text-to-SQL tanítóadaton végzett finomhangolás javít-e a saját adatbázisokon és a BIRD Mini-Dev-en, ugyanazokkal a beállításokkal, mint a [végső mérések](results.md) és a [BIRD-mérés](bird.md).

**Röviden: nem.** A saját adatbázisokon a finomhangolt modell mindhárom mért beállításban szignifikánsan rosszabb (a teljes beállításban 230 → 141/300), a BIRD Mini-Dev-en ugyanannyit ér, mint az alapmodell (211 vs. 207/498). A tanításból kihagyott BIRD train adatbázisokon javul (363 → 421/696), de a nyereség nagy része egyetlen formai szabály: a kötőjeles táblanevek idézése. A modell a BIRD válaszainak stílusát tanulta meg, és ez a saját tesztkészletek konvencióival és sémáival ütközik.

**Egy második kísérlet ezt oksági próbával megerősíti** (7. rész). Ugyanazokon a kérdéseken, ugyanazzal a recepttel két modell készült. Az egyik a BIRD gold válaszain tanult; a saját adatbázisokon ugyanúgy romlik (230 → 143). A másik az alapmodell saját, helyesnek bizonyult válaszain; nem romlik (230 → 230), és a BIRD Mini-Dev-en javítókörök nélkül szignifikánsan javít (207 → 224). A saját adatbázisokon viszont egyik finomhangolás sem hoz nyereséget.

Az első kísérlet minden futása 2026-11-15-én ment le, a másodiké 2026-11-15 és 16 között. A futások egymás után, más Ollama-terhelés nélkül, egyszer mentek le (`--repeats 1`), ugyanazokkal a beállításokkal, mint eddig: Q4_K_M, temperature 0, seed 42, `num_ctx` 8192.

A pipeline kódja (`src/`, `database/`, `datasets/`) azonos az `ada7880` commitéval; a futások azért „dirty”-k, mert a `finetune/` mappa és a dokumentáció még nem volt commitolva. A második kísérlet futásainál egy hibajavítás is commitolatlan volt a két offline validátorban. Ezek a sqlglot `TokenError`-ját (lezáratlan idézőjel) is szintaktikai hibának veszik; korábban ez kivételt dobott, és leállította volna a kiértékelést. A mért futásokban ilyen hiba nem fordult elő, ezért az eredményeket nem érinti. A prompt, a tesztkészletek és a sémaszöveg hash-e minden futásban egyezik a korábbi mérésekével.

Előállítás:

```
python src/evaluation/run_batch.py --run-name ft-<név> --repeats 1 --model qwen2.5-coder-7b-ft <kapcsolók>
python src/evaluation/compare.py final-m1-baseline ft-m1-baseconv ft-m1 --labels qwen base-conv ft --reference ft-m1-baseconv
python finetune/eval_valid.py --model qwen2.5-coder-7b-ft --run-name ft
python finetune/eval_valid.py --compare <eredmény A> <eredmény B>
```

A második kísérlet batch-ei: `ft-self-m1`, `ft-self-m4-fewshot5`, `ft-self-m7-full`, `ft-self-bird-b2-evidence`, `ft-self-bird-b3-evidence-corr2`, és ugyanezek `ft-goldsub-` előtaggal. A BIRD-összevetés `--metric set --columns difficulty` kapcsolókkal készült.

**Csonkított eredményfájl.** Az `ft-goldsub-m7-full` olist-hu fájljában (`20261115-160222_…`) a 40. kérdés generált sorai csonkítva vannak. A modell lekérdezésének JOIN-ja nem kötötte össze a két táblát, ezért 57 328 értékelés × 71 kategórianév = 4 070 288 sort adott vissza, és a fájl 222 MB lett. Ez a GitHub 100 MB-os korlátja fölött van. Az első 1000 sor maradt meg; mellette `generated_result_rows` (4070288) és `generated_result_truncated` (true) jelzi a csonkítást. A pontozás a mentés előtt, a teljes eredményen történt, ezért minden mérőszám változatlan; a `compare.py` és a `report.py` kimenete előtte és utána bájtra azonos. Az eredeti fájl tömörítve: `C:\BME\ft-export2\20261115-160222_olist-hu_ft-goldsub-m7-full-r1.ORIGINAL.json.gz` (sha256 `ceb0b959…`).

## 1. Modellek és tanítóadat

| Modell | Mi ez | Ollama digest |
|---|---|---|
| `qwen2.5-coder:7b` | az Ollama hivatalos modellje; eddig minden mérés ezzel készült | `dae161e2…` |
| `qwen2.5-coder-7b-base-conv` | ugyanaz az alapmodell (Hugging Face `Qwen/Qwen2.5-Coder-7B-Instruct`, commit `c03e6d35…`), a saját exportúton GGUF-fá alakítva (llama.cpp `e574a17b`, Q4_K_M) | `b0563339…` |
| `qwen2.5-coder-7b-ft` | az alapmodell + a LoRA-adapter (1. epoch), ugyanazon az exportúton | `b3c41078…` |

Mindhárom modellnek ugyanaz a chat-template-je és system promptja (az `install_ollama_model.py` ellenőrzi). A finomhangolt modellt a `base-conv`-hoz kell mérni, mert a kettő között csak az adapter a különbség.

Tanítóadat (`finetune/build_sft_data.py`, `finetune/data/sft/meta.json`):

- **Forrás:** BIRD train, a 69 SQLite-adatbázisból 58. Kimaradt a 10 legnagyobb (1 GB fölött, összesen 1425 kérdés), és a `works_cycles`, mert az az AdventureWorks OLTP, vagyis átfed a saját AdventureWorks-tesztadatbázissal. A Mini-Dev 11 adatbázisa nincs a train készletben. A saját adatbázisok kérdései és few-shot példái nem szerepelnek a tanítóadatban, így a few-shot a mérésben független változó marad.
- **Helyes SQL:** a BIRD gold lekérdezései sqlglot-tal SQLite-ról PostgreSQL-re fordítva, és mindkét adatbázison lefuttatva: a 7529 kérdésből 6390-nél egyezett az eredmény, ebből 6213 nem üres. Ezekből 6203 került a tanítóadatba.
- **Típusok:** a SQLite `REAL` oszlopai PostgreSQL-ben `double precision`-ök lettek. **Ez eltér a Mini-Dev dumpjától**, amely `real`-t (float4) használ. Float4-gyel a gold SQL `rate = 2.99`-féle egyenlőségei elromlottak (a próbán 509 helyett 520 egyezés az 567-ből double precision-nel). Az eltérés csak a tanítóadat-adatbázisokat érinti, a Mini-Dev mérését nem.
- **Felosztás:** validáció 5 teljes adatbázis (image_and_language, legislator, soccer_2016, trains, video_games; 696 példa), tanítás a többi 53 (5507 példa).
- **Prompt:** pontosan a pipeline promptja (`llm.sql_prompt`, a `schema.py` sémaszövegével). A tanítópéldák 46%-a evidence-blokkot is kap (a cél 50% volt, de nem minden BIRD-kérdéshez van evidence), 30%-uk 3 vagy 5 few-shot példa ugyanabból az adatbázisból (hasonlóság < 0.9, sosem ugyanaz az SQL). A válasz egy ```` ```sql ```` blokk, mint az alapmodellé. A `train_lora.py` minden példánál ellenőrizte, hogy a tokenizált prompt bájtra az, amit az Ollama küld.

## 2. Konverziós kontroll

Az alapmodell a saját exportúton (`base-conv`) ugyanolyan pontos, mint az Ollama hivatalos `qwen2.5-coder:7b`-je:

| Beállítás | qwen2.5-coder:7b | base-conv | +/− | McNemar p |
|---|---|---|---|---|
| m1 alap (relaxed EX, 300) | 157 | 164 | +14 / −7 | 0.189 |
| m4 5 példa (relaxed EX, 300) | 210 | 210 | +9 / −9 | 1.000 |
| m7 teljes beállítás (relaxed EX, 300) | 235 | 230 | +5 / −10 | 0.302 |
| BIRD + evidence (set EX, 498) | 215 | 207 | +15 / −23 | 0.256 |
| BIRD + evidence + 2 javítókör (set EX, 498) | 236 | 231 | +17 / −22 | 0.522 |

A „+/−” itt azoknak a kérdéseknek a száma, amelyeket csak a `base-conv`, illetve csak a `qwen2.5-coder:7b` oldott meg helyesen.

A két modell nem bitre azonos: az alapbeállításban a 300 lekérdezésből 146 szövege tér el (a `qwen2.5-coder:7b` két futása között csak 13). A kvantált fájl nem azonos az Ollama-éval (más digest, más llama.cpp-verzió), ezért a súlyok kicsit mások. A kimenetel azonban egyik beállításban sem tér el szignifikánsan, és az előjel is váltakozik. A konverzió tehát nem torzít, és a finomhangolás hatása a `base-conv`-hoz mérve tisztán az adapteré.

## 3. Saját adatbázisok (relaxed EX)

| Beállítás | Modell | Olist | F1 | AdventureWorks | hu | en | Összesen | 95% CI | Δ vs. base-conv | +/− | McNemar p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| m1 alap | qwen | 51 | 51 | 55 | 70 | 87 | **157/300** (52%) | 47%–58% | −7 | +7 / −14 | 0.189 |
| | base-conv | 54 | 52 | 58 | 73 | 91 | **164/300** (55%) | 49%–60% | — | — | — |
| | ft | 40 | 42 | 29 | 47 | 64 | **111/300** (37%) | 32%–43% | −53 | +18 / −71 | < 0.001 |
| m4 5 példa | qwen | 67 | 73 | 70 | 92 | 118 | **210/300** (70%) | 65%–75% | +0 | +9 / −9 | 1.000 |
| | base-conv | 69 | 72 | 69 | 90 | 120 | **210/300** (70%) | 65%–75% | — | — | — |
| | ft | 41 | 44 | 43 | 61 | 67 | **128/300** (43%) | 37%–48% | −82 | +14 / −96 | < 0.001 |
| m7 teljes (5 példa + 2 javítókör + RAG) | qwen | 76 | 80 | 79 | 108 | 127 | **235/300** (78%) | 73%–83% | +5 | +10 / −5 | 0.302 |
| | base-conv | 73 | 80 | 77 | 107 | 123 | **230/300** (77%) | 72%–81% | — | — | — |
| | ft | 43 | 48 | 50 | 63 | 78 | **141/300** (47%) | 41%–53% | −89 | +9 / −98 | < 0.001 |

Adatbázisonként 100, nyelvenként 150 kérdés. A beállítások neve a [végső mérések](results.md) számozását követi (`final-m1-baseline`, `final-m4-fewshot5`, `final-m7-full`); az m2, m3, m5, m6, m8 és m9 beállítást a finomhangolt modellel nem mértem.

A finomhangolt modell **mindhárom beállításban, mindhárom adatbázison és mindkét nyelven** rosszabb. Az alapbeállításban az AdventureWorksön a legnagyobb a veszteség (58 → 29, részben a séma nélküli táblanevek miatt), a few-shot beállításokban mindhárom adatbázison hasonló (−26 és −32 között). A few-shot és a javítás neki is segít, de sokkal kevésbé: az alapbeállításból a teljes beállításba a `base-conv` +66 kérdést nyer, a finomhangolt modell +30-at.

Strict és set EX-szel a finomhangolt modell eredménye szinte ugyanaz (alap: set 108, relaxed 111, strict 108), a `base-conv`-é nem (set 143, relaxed 164, strict 141). Az alapmodell gyakran ad vissza a kérdezettnél több oszlopot (például a név mellé a darabszámot is), amit a relaxed EX elfogad. A finomhangolt modell szinte soha. Ennek okát a 6. rész tárgyalja.

## 4. BIRD Mini-Dev (set EX)

| Beállítás | Modell | simple (148) | moderate (248) | challenging (102) | Összesen | 95% CI | Δ vs. base-conv | +/− | McNemar p |
|---|---|---|---|---|---|---|---|---|---|
| + evidence | qwen | 91 | 95 | 29 | **215/498** (43.2%) | 39%–48% | +8 | +23 / −15 | 0.256 |
| | base-conv | 90 | 93 | 24 | **207/498** (41.6%) | 37%–46% | — | — | — |
| | ft | 92 | 96 | 23 | **211/498** (42.4%) | 38%–47% | +4 | +60 / −56 | 0.781 |
| + evidence + 2 javítókör | qwen | 96 | 106 | 34 | **236/498** (47.4%) | 43%–52% | +5 | +22 / −17 | 0.522 |
| | base-conv | 95 | 109 | 27 | **231/498** (46.4%) | 42%–51% | — | — | — |
| | ft | 93 | 109 | 26 | **228/498** (45.8%) | 41%–50% | −3 | +53 / −56 | 0.848 |

A finomhangolt modell a Mini-Dev-en ugyanannyit ér, mint az alapmodell, minden nehézségi szinten. A kérdésenkénti kép viszont nagyon más: 60 kérdést csak a finomhangolt, 56-ot csak az alapmodell old meg (a `qwen2.5-coder:7b` és a `base-conv` között ez 23 / 15). A finomhangolás tehát erősen megváltoztatta a válaszokat, csak a nyereség és a veszteség kiegyenlíti egymást.

Strict és relaxed EX-szel ugyanez a kép:

| Beállítás | Modell | set EX | relaxed EX | strict EX | érvényes és lefutott SQL |
|---|---|---|---|---|---|
| + evidence | base-conv | 207 | 204 | 188 | 381 |
| | ft | 211 | 201 | 196 | 406 |
| + evidence + 2 javítókör | base-conv | 231 | 230 | 209 | 454 |
| | ft | 228 | 217 | 211 | 456 |

A finomhangolt modell első kísérlete gyakrabban fut le hibátlanul (406 vs. 381): a BIRD sémáin kevesebb érvénytelen lekérdezést ír. Ebből viszont nem lesz több helyes válasz. A javítókörök neki kevesebbet hoznak (+17, az alapmodellnek +24), mert kevesebb az érvénytelen első kísérlet (92 vs. 117).

Adatbázisonként (set EX, + evidence + 2 javítókör):

| Adatbázis | Kérdések | base-conv | ft |
|---|---|---|---|
| california_schools | 30 | 6 | 5 |
| card_games | 52 | 26 | 22 |
| codebase_community | 49 | 23 | 25 |
| debit_card_specializing | 30 | 13 | 11 |
| european_football_2 | 51 | 27 | 31 |
| financial | 30 | 6 | 8 |
| formula_1 | 66 | 28 | 21 |
| student_club | 48 | 35 | 34 |
| superhero | 52 | 41 | 36 |
| thrombosis_prediction | 50 | 15 | 22 |
| toxicology | 40 | 11 | 13 |
| **Összesen** | 498 | **231** | **228** |

Nincs olyan adatbázis, ahol a különbség rendszerszerű lenne; a legnagyobb a thrombosis_prediction +7 és a formula_1 −7.

**Reprodukálhatóság:** a javítókörös futások első kísérlete ugyanaz a prompt, mint az evidence-es futásé. Mindkét modellnél mind a 498 kérdésnél karakterre ugyanaz lett az SQL.

## 5. Validációs adatbázisok: a tanítás saját eloszlása

Javított-e a finomhangolás egyáltalán azon, amire tanítottuk? A `finetune/eval_valid.py` a tanításból kihagyott 5 BIRD train adatbázison (696 kérdés) méri, pontosan a `valid.jsonl` promptjaival: evidence a kérdések kb. felénél, 3 vagy 5 few-shot példa 30%-uknál, ugyanúgy, mint a tanítóadatban. Csak az első kísérlet számít, javítás nélkül; a helyes válasz a `valid.jsonl` ellenőrzött SQL-je.

| Részhalmaz (set EX) | Kérdések | base-conv | ft | +/− | McNemar p |
|---|---|---|---|---|---|
| **Összesen** | 696 | **363** (52%) | **421** (60%) | +112 / −54 | < 0.001 |
| legislator | 141 | 34 | 82 | +48 / −0 | < 0.001 |
| a másik 4 adatbázis | 555 | 329 | 339 | +64 / −54 | 0.41 |
| ebből few-shot példák nélkül | 388 | 216 | 229 | +51 / −38 | 0.20 |
| ebből few-shot példákkal | 167 | 113 | 110 | +13 / −16 | 0.71 |

Relaxed EX-szel 346 → 404, strict EX-szel 335 → 399. Adatbázisonként: image_and_language 78 → 79 (131), legislator 34 → 82 (141), soccer_2016 117 → 121 (199), trains 25 → 24 (36), video_games 109 → 115 (189).

**A nyereség egyetlen adatbázisból jön, és egyetlen szabályból.** A legislator tábláinak nevében kötőjel van (`current-terms`, `historical-terms`, `social-media`). A sémaszöveg a táblaneveket idézőjel nélkül írja ki (`Table: current-terms`; a `schema.sql_identifier` csak az oszlopneveket idézi), ezért a modellnek magától kell tudnia, hogy PostgreSQL-ben `"current-terms"` a helyes írásmód. Az alapmodell ezt sokszor nem tudja: 40 lekérdezésben MySQL-es backticket használ (`` `current-terms` ``), 19-ben idézőjel nélkül írja; 77 lekérdezése szintaktikai hibával áll meg. A finomhangolt modell mind a 110 ilyen lekérdezésben idézőjelet tesz, és csak 3 lekérdezése nem fut le. A tanítóadatban három adatbázisnak (airline, disney, regional_sales) van ilyen táblaneve, és 414 válasz használ idézett nevet.

A saját adatbázisokon és a Mini-Dev-en egyetlen táblanév sem igényel idézést, ezért ez a nyereség ott nem jelenhet meg. **A másik 4 validációs adatbázison a finomhangolás +10 kérdést hoz, ami nem szignifikáns (p = 0.41), few-shot példákkal pedig semmit** (113 vs. 110). A validációs veszteség (0.0967) attól csökkent, hogy a modell egyre pontosabban reprodukálja a BIRD-válaszok szövegét (aliasok, oszlopválasztás); ez a helyes válaszok számán alig látszik.

## 6. Miért rosszabb a saját adatbázisokon

### Átvett BIRD-konvenciók

A finomhangolt modell a BIRD válaszainak stílusát vette át, akkor is, ha a promptban lévő few-shot példák mást mutatnak:

| Jellemző | tanítóadat (5507) | base-conv m1 | ft m1 | base-conv m4 | ft m4 | base-conv m7 | ft m7 |
|---|---|---|---|---|---|---|---|
| `AS T1`-féle táblaaliasok | 78% | 1 | 192 | 0 | 181 | 0 | 161 |
| `SELECT DISTINCT` | 9% | 1 | 38 | 1 | 33 | 2 | 25 |
| kevesebb oszlop, mint a helyes válaszban (lefutott, nem üres) | — | 11/250 | 79/240 | 3/275 | 65/245 | 5/290 | 49/261 |
| nem létező tábla (AdventureWorks) | — | 1 | 18 | 0 | 3 | 0 | 2 |

A saját adatbázisok 111 few-shot példája és 150 helyes lekérdezése közül egy sem használ `T1`-aliast; `DISTINCT`-et 4 példa és 3 helyes lekérdezés.

- **Aliasok:** az `AS T1`, `AS T2` önmagában ártalmatlan, de jól mutatja, mennyire erős az átvitt stílus: 5 eltérő stílusú példa mellett is a válaszok 60%-ában megjelenik.
- **Minimális oszlopok:** a BIRD helyes válaszai pontosan azt adják vissza, amit a kérdés kér („Which driver …?” → csak a név). A saját tesztkészletek helyes válaszai a rangsoroló értéket is visszaadják (név + győzelmek száma). A relaxed EX megenged extra oszlopot, hiányzót nem. A BIRD-en ugyanez a szokás nem árt: ott a finomhangolt modell ugyanolyan ritkán ad kevesebb oszlopot, mint a helyes válasz (10/365, az alapmodell 11/354).
- **Séma nélküli táblanevek:** a BIRD train SQLite-ból jön, ott minden tábla egy névtérben van. Az AdventureWorks 5 PostgreSQL-sémában tárolja a táblákat (`sales.customer`). A finomhangolt modell alapbeállításban 18 kérdésnél séma nélkül írta a táblanevet („relation does not exist”). A few-shot példák ezt szinte megszüntetik (3 és 2).
- **`DISTINCT`:** a `SELECT DISTINCT … ORDER BY` alapbeállításban 7 kérdésnél PostgreSQL-hibát okozott („ORDER BY expressions must appear in select list”).

Ha utólag a kevesebb oszlopot is elfogadnánk, amikor minden visszaadott oszlop a helyes válasz egy oszlopa, ugyanazokkal a sorokkal (a relaxed EX fordított szerepekkel), a különbség csökken, de nagy marad:

| Beállítás | base-conv | base-conv, elnézőbben | ft | ft, elnézőbben | különbség → elnézőbben |
|---|---|---|---|---|---|
| m1 alap | 164 | 166 | 111 | 136 | −53 → −30 |
| m4 5 példa | 210 | 212 | 128 | 164 | −82 → −48 |
| m7 teljes | 230 | 232 | 141 | 171 | −89 → −61 |

A hátrány kb. harmada–kétötöde tehát mérési konvenció, a többi valódi hiba.

### A lefutó, de rossz válaszok

A teljes beállításban a finomhangolt modell lekérdezéseinek 93%-a lefut, mégis csak 47%-a helyes:

| Kimenetel (m7, 300 kérdés) | base-conv | ft |
|---|---|---|
| helyes | 230 | 141 |
| nem futott le | 9 | 20 |
| üres eredmény | 1 | 19 |
| kevesebb oszlop, egyébként egyező | 2 | 30 |
| kevesebb oszlop, más sorok | 3 | 19 |
| más sorszám | 17 | 15 |
| ugyanannyi sor, más értékek | 38 | 56 |

A tipikus hiba, hogy a finomhangolt modell nem követi a promptban lévő few-shot példák domain-szabályait, és egyszerűbb, a BIRD-ből ismerős mintát választ. Három példa az F1-ről, 5 példával (m4); a `base-conv` mindhármat helyesen oldotta meg:

- **„How many world championship titles did Michael Schumacher win?”** A promptban lévő egyik példa („Which drivers have won at least three world championship titles …”) megmutatja, hogy a bajnok a szezon utolsó futama utáni állás első helyezettje (`r.round = (SELECT MAX(r2.round) …)`). A finomhangolt modell ezt kihagyja, és minden `driver_standings` sort megszámol, ahol `position = 1`, vagyis minden futamot, amely után Schumacher vezetett.
- **„Which driver won the 2007 world championship?”** Ugyanez a példa volt a promptban. A finomhangolt modell a `races` táblát kihagyja, és `t2.year`-re szűr a `driver_standings`-en, amelynek nincs `year` oszlopa: a lekérdezés le sem fut.
- **„How many races has the Red Bull team won?”** A promptban két példa is a `results` táblából számolja a győzelmeket (`res.position = 1`). A finomhangolt modell a konstruktőri állásból (`constructor_standings`) számol, ami a futamok utáni vezetést méri, nem a győzelmet.

A javítókörök is kevesebbet segítenek neki: a teljes beállításban 43 kérdésnél indult javítás, ebből 3 lett helyes (a `base-conv`-nál 28-ból 9). A le nem futó lekérdezések hibája többnyire nem létező oszlop (`t2.year`, `t2.freight_value`, `t2.product_category_name_english`).

### Nyelv

| Beállítás | hu: base-conv → ft | en: base-conv → ft |
|---|---|---|
| m1 alap | 73 → 47 (−26) | 91 → 64 (−27) |
| m4 5 példa | 90 → 61 (−29) | 120 → 67 (−53) |
| m7 teljes | 107 → 63 (−44) | 123 → 78 (−45) |

A tanítás csak angol kérdéseken folyt. A magyar kérdéseken a veszteség mégsem nagyobb, mint az angolokon: a romlás nyelvfüggetlen, a stílusból és a sémakezelésből jön, nem a kérdés megértéséből.

## 7. Második kísérlet: tanítás a modell saját válaszain

Az első kísérlet alapján a romlás oka a célválaszok stílusa. Ezt egy második kísérlet ellenőrzi oksági próbával (menete: [finetune.md](finetune.md), 10. rész). A recept ugyanaz, de két új modell készült, és ezek csak a célválasz szövegében különböznek:

| Modell | Célválasz | Tanítókérdések | Exportált epoch | Ollama digest |
|---|---|---|---|---|
| `qwen2.5-coder-7b-ft` (1. kísérlet) | BIRD gold | 5507 | 1. | `b3c41078…` |
| `qwen2.5-coder-7b-ft-goldsub` | BIRD gold | 3441 | 1. | `f1c68197…` |
| `qwen2.5-coder-7b-ft-self` | az alapmodell saját, helyesnek bizonyult válasza | 3441 | 2. | `9ecd8b81…` |

**Honnan jön a 3441 kérdés?** Ezeknél a kérdéseknél az alapmodell öt válasza közül (1 mohó, 4 mintavételezett, vLLM-mel a bérelt gépen) legalább egy helyes volt: lefutott, és set vagy relaxed EX szerint egyezett a gold eredményével. Az első helyes válasz lett az `ft-self` célválasza.

**Mi a két modell szerepe?** Az `ft-goldsub` ugyanazokat a kérdéseket, promptokat és sorrendet látja, csak a BIRD gold válaszával. Ez a kontroll arra, hogy a kisebb, könnyebb kérdéshalmaz már önmagában nem okoz-e különbséget.

**Mit vártunk?** Ha a romlást a stílus okozza, az `ft-goldsub` úgy romlik, mint az első `ft`, az `ft-self` pedig nem.

A két tanítókészlet stílusa:

| Jellemző (3441 válasz) | `sft_goldsub` | `sft_self` |
|---|---|---|
| `AS T1`-alias, few-shot példák nélküli promptban (2294) | 1754 (76%) | 70 (3%) |
| `AS T1`-alias, few-shot példás promptban (1147) | 859 (75%) | 872 (76%) |
| `SELECT DISTINCT` | 290 | 216 |

Ha a promptban BIRD-stílusú few-shot példák vannak, az alapmodell is átveszi az aliasokat; példák nélkül szinte sosem használja őket. Az `ft-self` célválaszai tehát a példák stílusát követik, a gold válaszok mindig ugyanazt a stílust.

### 7.1 Saját adatbázisok (relaxed EX)

| Beállítás | Modell | Olist | F1 | AdventureWorks | hu | en | Összesen | 95% CI | Δ vs. base-conv | +/− | McNemar p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| m1 alap | base-conv | 54 | 52 | 58 | 73 | 91 | **164/300** | 49%–60% | — | — | — |
| | ft | 40 | 42 | 29 | 47 | 64 | **111/300** | 32%–43% | −53 | +18 / −71 | < 0.001 |
| | ft-goldsub | 41 | 34 | 32 | 47 | 60 | **107/300** | 30%–41% | −57 | +12 / −69 | < 0.001 |
| | ft-self | 56 | 50 | 57 | 73 | 90 | **163/300** | 49%–60% | −1 | +12 / −13 | 1.000 |
| m4 5 példa | base-conv | 69 | 72 | 69 | 90 | 120 | **210/300** | 65%–75% | — | — | — |
| | ft | 41 | 44 | 43 | 61 | 67 | **128/300** | 37%–48% | −82 | +14 / −96 | < 0.001 |
| | ft-goldsub | 42 | 44 | 44 | 61 | 69 | **130/300** | 38%–49% | −80 | +11 / −91 | < 0.001 |
| | ft-self | 66 | 73 | 70 | 90 | 119 | **209/300** | 64%–75% | −1 | +8 / −9 | 1.000 |
| m7 teljes | base-conv | 73 | 80 | 77 | 107 | 123 | **230/300** | 72%–81% | — | — | — |
| | ft | 43 | 48 | 50 | 63 | 78 | **141/300** | 41%–53% | −89 | +9 / −98 | < 0.001 |
| | ft-goldsub | 47 | 46 | 50 | 63 | 80 | **143/300** | 42%–53% | −87 | +8 / −95 | < 0.001 |
| | ft-self | 74 | 80 | 76 | 104 | 126 | **230/300** | 72%–81% | +0 | +10 / −10 | 1.000 |

A kontrollokkal páronként:

| Összevetés | m1 | m4 | m7 |
|---|---|---|---|
| ft-goldsub vs. ft | 107 vs. 111, +10 / −14, p = 0.54 | 130 vs. 128, +17 / −15, p = 0.86 | 143 vs. 141, +13 / −11, p = 0.84 |
| ft-self vs. ft-goldsub | +69 / −13, p < 0.001 | +87 / −8, p < 0.001 | +95 / −8, p < 0.001 |

**A romlást a célválasz stílusa okozza, nem maga a finomhangolás és nem a kérdéshalmaz.**

- Az `ft-goldsub` mindhárom beállításban ugyanannyit ér, mint az első `ft`, pedig 38%-kal kevesebb és könnyebb kérdésen tanult. A két gold-tanítású modell válaszai az alapbeállításban 170 kérdésnél szövegre eltérnek, a kimenetel csak 24-nél.
- Az `ft-self` mindhárom beállításban, minden adatbázison és mindkét nyelven az alapmodell szintjén van; a legnagyobb eltérés adatbázisonként −3 (Olist, m4).
- A válaszokat kb. annyira változtatta meg, mint egy másik kvantálás: az alapbeállításban 165 SQL-szöveg tér el a `base-conv`-étól (25 kimenetel). A `qwen2.5-coder:7b` és a `base-conv` között ez 146 (21).

| Jellemző (m1 / m4 / m7) | base-conv | ft-goldsub | ft-self |
|---|---|---|---|
| `AS T1`-féle aliasok | 1 / 0 / 0 | 157 / 154 / 139 | 0 / 0 / 0 |
| `SELECT DISTINCT` | 1 / 1 / 2 | 19 / 17 / 15 | 2 / 1 / 1 |
| kevesebb oszlop, mint a helyes válaszban (lefutott, nem üres) | 11/250, 3/275, 5/290 | 76/236, 71/244, 67/261 | 13/252, 4/273, 4/293 |
| nem létező tábla (AdventureWorks) | 1 / 0 / 0 | 18 / 0 / 3 | 1 / 0 / 0 |

Az `ft-self` tanítóválaszainak 27%-a `T1`-aliasos (a few-shot példás promptoknál), a saját adatbázisokon mégsem használja őket, mert ott a példák nem ilyenek. Ha utólag a kevesebb oszlopot is elfogadnánk (6. rész), az `ft-goldsub` 107 → 138, 130 → 179 és 143 → 188 lenne. Az `ft-self` 163 → 167, 209 → 210 és 230 → 232 lenne, a `base-conv` 166, 212 és 232. Az `ft-goldsub` hátránya így is 28–44 kérdés.

### 7.2 BIRD Mini-Dev (set EX)

| Beállítás | Modell | simple (148) | moderate (248) | challenging (102) | Összesen | 95% CI | Δ vs. base-conv | +/− | McNemar p |
|---|---|---|---|---|---|---|---|---|---|
| + evidence | base-conv | 90 | 93 | 24 | **207/498** | 37%–46% | — | — | — |
| | ft | 92 | 96 | 23 | **211/498** | 38%–47% | +4 | +60 / −56 | 0.781 |
| | ft-goldsub | 89 | 99 | 24 | **212/498** | 38%–47% | +5 | +52 / −47 | 0.688 |
| | ft-self | 92 | 101 | 31 | **224/498** | 41%–49% | +17 | +23 / −6 | **0.002** |
| + evidence + 2 javítókör | base-conv | 95 | 109 | 27 | **231/498** | 42%–51% | — | — | — |
| | ft | 93 | 109 | 26 | **228/498** | 41%–50% | −3 | +53 / −56 | 0.848 |
| | ft-goldsub | 92 | 109 | 28 | **229/498** | 42%–50% | −2 | +50 / −52 | 0.921 |
| | ft-self | 95 | 109 | 36 | **240/498** | 44%–53% | +9 | +22 / −13 | 0.175 |

Az `ft-self` az `ft-goldsub`-hoz képest: evidence-szel +12 (+52 / −40, p = 0.25), javítókörökkel +11 (+49 / −38, p = 0.28).

| Beállítás | Modell | set EX | relaxed EX | strict EX | lefutott SQL | javítás indult → set szerint helyes |
|---|---|---|---|---|---|---|
| + evidence | base-conv | 207 | 204 | 188 | 381 | — |
| | ft-goldsub | 212 | 202 | 198 | 409 | — |
| | ft-self | 224 | 220 | 203 | 401 | — |
| + evidence + 2 javítókör | base-conv | 231 | 230 | 209 | 454 | 117 → 24 |
| | ft-goldsub | 229 | 218 | 213 | 459 | 89 → 17 |
| | ft-self | 240 | 236 | 216 | 472 | 97 → 16 |

**Az `ft-self` a Mini-Dev-en javít.**

- **Javítókörök nélkül szignifikánsan:** +17, p = 0.002. Az `ft` és az `ft-goldsub` sok választ megváltoztat, és a nyereség meg a veszteség kiegyenlíti egymást (+52 / −47). Az `ft-self` keveset változtat, és szinte csak nyer (+23 / −6).
- **Honnan jön a 23 nyereség?** 13 kérdésnél az alapmodell lekérdezése lefutott, de rossz sorokat adott, 6-nál nem létező oszlopra hivatkozott, 2-nél szintaktikai, 2-nél függvényhiba volt. A szintaktikai hibák száma 16-ról 3-ra csökken.
- **Nehézség szerint** a nyereség legnagyobb része a challenging kérdéseken van: 24 → 31, javítókörökkel 27 → 36.
- **A javítókörök után a különbség +9, és nem szignifikáns.** A javítás az alapmodellnél részben ugyanazt hozza be, amit az `ft-self` elsőre eltalál (117 javításból 24 helyes, az `ft-self`-nél 97-ből 16).
- **Adatbázisonként** a különbség evidence-szel −1 és +4 között van; nincs olyan adatbázis, amelyen rendszerszerű lenne.

**Elszabadult generálás.** A california_schools 87-es kérdésénél az `ft-goldsub` ismétlődő hurokba került: a „lekérdezés” egymásba ágyazott zárójelek sora. Evidence-szel 6136 s alatt 6,26 millió karaktert írt, a javítókörös futásban 5339 s alatt 5,27 milliót. A javítókör ezután egy rövid, lefutó, de rossz lekérdezést adott. Mindkét futás rossz válaszként számolja, ahogy kell. A pipeline nem korlátozza a válasz hosszát (az Ollamának nincs `num_predict`-je), ezért egy ilyen hurok csak magától áll meg. Az eddigi összes mérés kb. 17 ezer válaszában ez még egyszer fordult elő: a `qwen2.5-coder:7b`-nél, a `bird-b1-baseline` student_club #1426-os kérdésén (241 ezer karakter, 4868 s). Minden más válasz legfeljebb 2779 karakter.

**Reprodukálhatóság:** a javítókörös futás első SQL-válasza ugyanaz a prompt, mint az evidence-es futásé. Az `ft-self`-nél mind a 498 kérdésnél karakterre azonos lett, az `ft-goldsub`-nál 495-nél. A 3 eltérés a california_schools hurkos futásában van, és ott is azonos a kimenetel.

### 7.3 Validációs adatbázisok

Ugyanaz a mérés, mint az 5. részben: a tanításból kihagyott 5 BIRD train adatbázis mind a 696 kérdése, a `valid.jsonl` promptjaival, csak az első kísérlet, set EX. Itt azok a kérdések is szerepelnek, amelyeknél az alapmodell egyik válasza sem volt helyes.

| Részhalmaz | Kérdések | base-conv | ft | ft-goldsub | ft-self | ft-goldsub vs. base-conv | ft-self vs. base-conv |
|---|---|---|---|---|---|---|---|
| **Összesen** | 696 | **363** | **421** | **419** | **371** | +101 / −45, p < 0.001 | +25 / −17, p = 0.28 |
| image_and_language | 131 | 78 | 79 | 85 | 84 | +13 / −6 | +8 / −2 |
| legislator | 141 | 34 | 82 | 69 | 34 | +37 / −2 | +2 / −2 |
| soccer_2016 | 199 | 117 | 121 | 124 | 122 | +24 / −17 | +9 / −4 |
| trains | 36 | 25 | 24 | 25 | 26 | +2 / −2 | +1 / −0 |
| video_games | 189 | 109 | 115 | 116 | 105 | +25 / −18 | +5 / −9 |
| a másik 4 (legislator nélkül) | 555 | 329 | 339 | 350 | 337 | +64 / −43, p = 0.053 | +23 / −15, p = 0.26 |
| ebből few-shot példák nélkül | 388 | 216 | 229 | 237 | 220 | +53 / −32, p = 0.029 | +15 / −11, p = 0.56 |
| ebből few-shot példákkal | 167 | 113 | 110 | 113 | 117 | +11 / −11, p = 1.0 | +8 / −4, p = 0.39 |

Az `ft-goldsub` a saját eloszlásán ugyanannyit ér, mint az `ft` (419 vs. 421, +37 / −39, p = 0.91). A legislator nyereségének nagyjából háromnegyedét ő is megkapja: a kötőjeles táblaneveket 92 lekérdezésben idézi, 13-ban még backtickkel írja. Az `ft-self` a legislatoron semmit sem tanult (34 → 34; 30 idézett név, 28 backtick, az alapmodellnél 28 és 40).

A kiválogatás a quotingot tanító kérdések nagy részét elhagyta: a regional_sales 124 kérdéséből 30 maradt, mert az alapmodell ezeket ritkán oldja meg. Így mindkét új modell csak kb. 40 olyan választ lát, amelynek `FROM`/`JOIN`-ja idézett, kötőjeles vagy szóközös nevű táblát olvas; az első `ft` 186-ot látott. A két új modell ugyanazokat a kérdéseket látja, a quotingot mégis csak az `ft-goldsub` tanulta meg részben. Ennek oka nem tisztázott.

A legislator nélkül egyik modell javulása sem szignifikáns a négy adatbázison együtt. Few-shot példák nélkül az `ft-goldsub` +21 kérdése éppen szignifikáns (p = 0.029), few-shot példákkal egyik modell sem javít.

### 7.4 Értelmezés

- **Az oksági próba megerősíti az első kísérlet magyarázatát.** Ugyanazokon a kérdéseken, ugyanazzal a recepttel csak a célválasz szövege különbözik. A gold szövegen tanított modell a saját adatbázisokon 57–87 kérdést veszít, a saját szövegén tanított egyet sem. A kisebb kérdéshalmaz semmit nem változtat (`ft-goldsub` ≈ `ft`).
- **A saját válaszokon tanítás nem árt, de a saját adatbázisokon nem is segít.** A Mini-Dev-en javítókörök nélkül +17 (p = 0.002), a többi összevetésben a javulás kisebb és nem szignifikáns: javítókörökkel +9, a validációs adatbázisokon +8. A nyereség a tanítóadattal azonos benchmarkon jelenik meg (angol BIRD-kérdések, evidence), a saját adatbázisokra, a magyar kérdésekre és a few-shot beállításokra nem viszi át.
- **A termék marad a `qwen2.5-coder:7b`-n.** Az `ft-self` a teljes beállításban pontosan annyit ér, mint az alapmodell (230 vs. 230), így a cserének nincs haszna.

## 8. Költség

| Tétel | Összeg |
|---|---|
| **1. kísérlet:** pod `2js25ff6ihhgzt` (RTX 4090, ~2 óra 11 perc, 2026-11-15 00:17–02:28 UTC): GPU | $1.929 |
| ugyanaz: disk | $0.035 |
| Network volume `np2stvutbi` (40 GB) | $0.012 |
| **2. kísérlet:** pod `t2ta75mkrb40rq` (RTX 4090, ~2 óra 45 perc, 2026-11-15 10:54–13:39 UTC): GPU | $2.435 |
| ugyanaz: disk | $0.044 |
| Network volume `ld9qqr67ra` (40 GB) | $0.012 |
| **Összesen** | **$4.47** (1. kísérlet $1.98, 2. kísérlet $2.49) |

A RunPod számlázási adataiból (2026-11-15). Az 1. kísérletben a tanítás 69 perc, az export 4 perc volt, a többi előkészítés és letöltés. A 2. kísérletben a generálás 13 perc, a két tanítás 40 és 41 perc, a két export 2-2 perc volt. Helyben az 1. kísérlet mérései kb. 3,5 órát vettek igénybe, a 2. kísérleté kb. 7,5 órát. Ebből kb. 3 óra a hurkos kérdés két generálása volt (helyi idő szerint 2026-11-15 13:29 – 11-16 02:59, egy szünettel).

## 9. Következtetések

1. **A konverzió nem torzít.** Az alapmodell a saját exportúton mind az öt összevetett beállításban zajon belül megegyezik az Ollama hivatalos modelljével.
2. **A saját adatbázisokon a finomhangolás egyértelműen árt:** −53, −82 és −89 kérdés a 300-ból (p < 0.001), mindhárom adatbázison és mindkét nyelven. A few-shot és a javítókörök a finomhangolt modellnek is segítenek, de az alapmodellhez mért hátrányát nem hozzák be.
3. **A BIRD Mini-Dev-en nincs hatása:** 211 vs. 207 és 228 vs. 231 (p ≥ 0.78), bár a válaszokat erősen megváltoztatta (+60 / −56). A tanító- és a tesztkészlet ugyanabból a benchmarkból jön, a nyereség mégsem jelenik meg az összesítésben.
4. **A saját eloszlásán is szinte csak egy formai szabályt tanult meg.** A tanításból kihagyott BIRD train adatbázisokon +58 kérdés (363 → 421/696, p < 0.001), de ebből +48 egyetlen adatbázisból jön, ahol a kötőjeles táblaneveket kell idézőjelbe tenni. A másik négyen +10 (p = 0.41), few-shot példákkal 0.
5. **Az ok a stílus átvitele, és ezt a második kísérlet oksági próbával is megerősíti.** A modell a BIRD válaszainak konvencióit tanulta meg (minimális oszlopok, `T1`-aliasok, `DISTINCT`, séma nélküli táblanevek), és ezeket a promptban lévő példák ellenében is követi. A hátrány kb. harmada–kétötöde mérési konvenció (hiányzó, de nem kért oszlopok), a többi valódi hiba: rossz tábla vagy join, nem létező oszlop, a domain-szabályok figyelmen kívül hagyása. Ugyanazokon a 3441 kérdésen, ugyanazzal a recepttel a gold szövegen tanított modell (`ft-goldsub`) ugyanannyit veszít, mint az első (107 / 130 / 143 vs. 111 / 128 / 141). A saját helyes válaszain tanított modell (`ft-self`) semmit (163 / 209 / 230 vs. 164 / 210 / 230).
6. **A saját válaszokon tanítás biztonságos, de kevés haszna van.** Az `ft-self` a Mini-Dev-en javítókörök nélkül szignifikánsan jobb (224 vs. 207, p = 0.002), javítókörökkel már nem (240 vs. 231, p = 0.18). A validációs adatbázisokon sem (371 vs. 363, p = 0.28), a saját adatbázisokon pedig ugyanannyit ér. Ennyi adat és ez a recept a 7B modell tudásához alig tesz hozzá.
7. **A termék marad az alapmodellen.** A web UI és az MCP-szerver továbbra is a `qwen2.5-coder:7b`-t használja; a finomhangolt modellek csak mérési eredmények.
8. **Korlátok:** két kísérlet, három tanítás, egyetlen hiperparaméter-beállítással és seeddel, csak angol tanítóadattal, futásonként egy mérés. A nem exportált epochok adapterei elkészültek (`C:\BME\ft-export\adapter-epoch2`, `C:\BME\ft-export2\`), de nincsenek mérve.
9. **Egy robusztussági hiány a pipeline-ban:** nincs generálási hosszkorlát. Kb. 17 ezer mért válaszból kettő ismétlődő hurokba került, és 1,3–1,7 óráig generált (7.2). A web UI-ban egy ilyen kérdés ennyi ideig foglalná az adatbázis motorját.

Lehetséges következő lépések, ha a finomhangolás folytatódik:

- **Kisebb beavatkozás:** alacsonyabb tanulási ráta, kevesebb lépés vagy kisebb rang, hogy a modell kevésbé írja felül a saját stílusát. A második kísérlet után ez kevésbé sürgős: a stílus megtartását a saját válaszokon tanítás közvetlenül megoldja.
- **Több és nehezebb saját válasz:** most a kérdések 38%-a kimaradt, mert az alapmodell öt válaszából egyik sem volt helyes. Több mintával vagy a javítókörök válaszaival a nehezebb kérdések is bekerülhetnének, és ott várható a legtöbb tanulnivaló.
- **Többsémás tanítóadat:** olyan adatbázisok, ahol a táblákat sémanévvel kell minősíteni.
- **Generálási hosszkorlát** (`num_predict`, pl. 1024 token): a mért válaszok közül csak a két hurkot érintené (minden más legfeljebb 2779 karakter, kb. 800 token). Az LLM-beállítás változása azonban új mérési konfiguráció, ezért külön döntést igényel.
- **Domainen belüli szintetikus kérdések** a saját adatbázisokra, szivárgásszűréssel (a terv opcionális ablációja). A few-shot példák ezt a szerepet már most is jól töltik be: +46 kérdés a `base-conv`-on, +53 a `qwen2.5-coder:7b`-n.
- **A sémaszöveg pótlása, finomhangolás nélkül:** a nem sima táblaneveket (`current-terms`) a sémaszöveg is idézőjellel írhatná, ahogy az oszlopneveket (`schema.sql_identifier`). A validációs nyereség nagy része ebből a hiányból jön. A mért adatkészletek egyikének sem változna tőle a sémaszövege, mert mindegyikben sima táblanevek vannak.
