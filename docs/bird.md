# BIRD Mini-Dev mérés

A saját tesztkészletek kérdéseit én írtam, ezért kérdés, hogy az eredmények mennyire általánosíthatók. Ezt egy független, nyilvános benchmarkon ellenőriztem. A BIRD Mini-Dev a BIRD text-to-SQL benchmark fejlesztői készletéből kiválasztott 500 kérdés 11 adatbázison (2024-06). Van belőle SQLite-, MySQL- és PostgreSQL-változat. Minden kérdéshez tartozik helyes lekérdezés, nehézségi szint (simple, moderate, challenging) és egy „evidence”: rövid háttértudás, amely a kérdés megértéséhez szükséges szabályt vagy kódolást írja le.

Az összes beállítás ugyanazon a commiton futott (`a247a62`, tiszta munkakönyvtár), ugyanazzal a modellel, mint a saját mérések: `qwen2.5-coder:7b`, Ollama, Q4_K_M kvantálás, temperature 0, seed 42, `num_ctx` 8192. Minden beállítás egyszer futott le, 2026-11-10 és 11-12 között, más Ollama-terhelés nélkül. A kérdések angolok. Magyar fordítás nem készült, mert az külön döntés.

Előállítás:

```
python database/import_bird.py <kicsomagolt minidev mappa>
python src/evaluation/run_batch.py --run-name bird-<név> --datasets bird_california_schools ... bird_toxicology --languages en --repeats 1 <kapcsolók>
python src/evaluation/compare.py bird-b1-baseline ... --labels ... --reference bird-b1-baseline --metric set --columns difficulty
```

## 1. Adatok és import

- **Forrás:** `minidev.zip` (https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip), ebből a PostgreSQL-változat. Ez egyetlen `pg_dump` mind a 11 adatbázisról, összesen 75 táblával, és egy JSON-fájl a kérdésekkel.
- **Import** (`database/import_bird.py`): a dump egy ideiglenes adatbázisba töltődik. Onnan a szkript adatbázisonként saját adatkészlet-mappát készít a megszokott formában (`datasets/bird_<név>/`: `schema.sql`, `import.sql`, `test_cases/en.json`). A mappa tartalmazza a táblákat, elsődleges kulcsokat, egyedi indexeket és mind a 87 idegen kulcsot, valamint CSV-ben az adatokat. Utána a `setup_dataset.py` építi fel az adatbázisokat, ugyanazzal a csak olvasási jogú szerepkörrel, mint a többit.
- **Ellenőrzés:**
  - mind a 75 tábla sorszáma és tartalma (md5) megegyezik az eredeti dumpéval;
  - mind a 498 helyes lekérdezés lefut a csak olvasási jogú szerepkörrel, a 10 s-os időkorláton belül, ezért egy kérdést sem kellett kizárni (`excluded_cases.json` mindenhol üres).
- **498 kérdés 500 helyett:** a kérdésfájlban két financial-kérdés kétszer szerepel, ezeket egyszer tartottam meg. Nehézség szerint: simple 148, moderate 248, challenging 102.
- **Csak kiértékelésre:** a BIRD-adatkészletek `"listed": false` jelölést kaptak, ezért a webes felület és az MCP-szerver nem kínálja fel őket.
- **Sémaszöveg:** ugyanaz a formátum, mint a saját adatbázisoknál: oszlopok típussal, majd a kapcsolatok. Ahol egy oszlopnév idézőjelet igényel (például `"Free Meal Count (K-12)"`), ott a séma idézőjellel mutatja. A többi adatkészlet sémaszövege ettől nem változott. A BIRD-adatbázisokhoz nincs `hints.txt` és nincs `examples.json`, ezért ezeken few-shot nem mérhető.

Egy példa az evidence-re (debit_card_specializing, moderate):

> **Kérdés:** In 2012, who had the least consumption in LAM?
> **Evidence:** Year 2012 can be presented as Between 201201 And 201212; The first 4 strings of the Date values in the yearmonth table can represent year.

Az évszám a `yearmonth.Date` szöveg első négy karaktere. Ezt a sémából nem lehet kitalálni, az evidence mondja meg.

## 2. Beállítások

| Beállítás | Evaluator-kapcsolók | Batch |
|---|---|---|
| Alap | `(alap)` | `bird-b1-baseline` |
| + evidence | `--evidence` | `bird-b2-evidence` |
| + evidence + 2 javítókör | `--evidence --correction-rounds 2` | `bird-b3-evidence-corr2` |
| + evidence + javítás + RAG | `--evidence --correction-rounds 2 --rag` | `bird-b4-evidence-corr2-rag` |

- **Evidence** (`--evidence`, `PipelineConfig.question_evidence`): a kérdés evidence-e egy külön blokkban (`EXTERNAL KNOWLEDGE`) kerül a promptba, közvetlenül a kérdés elé. A RAG táblakeresése és táblaválasztása is a kérdést és az evidence-et együtt kapja. Kikapcsolva a prompt bájtra azonos a korábbival.
- **Javítókörök és RAG:** ugyanazok, mint a [végső méréseknél](results.md).
- **A negyedik beállítás két részletben futott.** A california_schools 2026-11-11-én futott le, a többi tíz adatbázis 2026-11-12-én, ugyanazon a commiton, ugyanazokkal a kapcsolókkal. Az első kísérletet a gép alvása és egy Windows-frissítés szakította meg. A batch-fájl `note` mezője rögzíti ezt.

**Mérőszám:** a fő mérőszám a BIRD hivatalos végrehajtási pontossága (set EX). A válasz akkor helyes, ha a lekérdezés sorai halmazként megegyeznek a helyes lekérdezés soraival: a sorrend és az ismétlődés nem számít, az oszlopok száma és sorrendje igen. Mellette a saját strict és relaxed EX is szerepel.

## 3. Fő táblázat (set EX, az alaphoz képest)

| Beállítás | simple (148) | moderate (248) | challenging (102) | Összesen | 95% CI | Δ vs. Alap | +/− | McNemar p |
|---|---|---|---|---|---|---|---|---|
| Alap | 63 | 49 | 12 | **124/498** (24.9%) | 21%–29% | — | — | — |
| + evidence | 91 | 95 | 29 | **215/498** (43.2%) | 39%–48% | +91 | +107 / −16 | < 0.001 |
| + evidence + 2 javítókör | 96 | 106 | 34 | **236/498** (47.4%) | 43%–52% | +112 | +123 / −11 | < 0.001 |
| + evidence + javítás + RAG | 96 | 106 | 26 | **228/498** (45.8%) | 41%–50% | +104 | +124 / −20 | < 0.001 |

A „+/−” oszlop azoknak a kérdéseknek a száma, amelyeket csak az adott beállítás, illetve csak az alap oldott meg helyesen. A McNemar-próba ezekből számol.

Lépésenként (set EX):

| Lépés | Összesen | +/− | p | simple | moderate | challenging |
|---|---|---|---|---|---|---|
| Alap → + evidence | 124 → 215 | +107 / −16 | < 0.001 | 63 → 91 | 49 → 95 | 12 → 29 |
| + evidence → + 2 javítókör | 215 → 236 | +21 / −0 | < 0.001 | 91 → 96 | 95 → 106 | 29 → 34 |
| + javítás → + RAG | 236 → 228 | +25 / −33 | 0.358 | 96 → 96 | 106 → 106 | 34 → 26 (+2/−10, p = 0.039) |
| + evidence → + javítás + RAG | 215 → 228 | +43 / −30 | 0.160 | 91 → 96 | 95 → 106 | 29 → 26 |

Strict és relaxed EX-szel ugyanez a kép:

| Beállítás | set EX | relaxed EX | strict EX |
|---|---|---|---|
| Alap | 124 | 124 | 112 |
| + evidence | 215 | 207 | 195 |
| + evidence + 2 javítókör | 236 | 231 | 213 |
| + evidence + javítás + RAG | 228 | 221 | 205 |

A set és a relaxed EX kérdésenként nem mindig egyezik: a „+ evidence + 2 javítókör” beállításban 23 válasz csak set szerint, 18 csak relaxed szerint helyes. A set EX nem nézi a sorrendet és az ismétlődő sorokat, viszont nem enged meg extra oszlopot. A relaxed EX megenged extra oszlopot, de `ORDER BY` esetén a sorrendet is ellenőrzi.

## 4. Adatbázisonként (set EX)

| Adatbázis | Táblák | Kérdések | Alap | + evidence | + 2 javítókör | + RAG |
|---|---|---|---|---|---|---|
| california_schools | 3 | 30 | 2 | 6 | 7 | 8 |
| card_games | 6 | 52 | 12 | 27 | 27 | 21 |
| codebase_community | 8 | 49 | 19 | 20 | 21 | 26 |
| debit_card_specializing | 5 | 30 | 6 | 14 | 14 | 12 |
| european_football_2 | 7 | 51 | 14 | 24 | 30 | 30 |
| financial | 8 | 30 | 2 | 4 | 5 | 8 |
| formula_1 | 13 | 66 | 17 | 24 | 28 | 27 |
| student_club | 8 | 48 | 20 | 32 | 35 | 35 |
| superhero | 10 | 52 | 30 | 39 | 40 | 36 |
| thrombosis_prediction | 3 | 50 | 0 | 14 | 17 | 17 |
| toxicology | 4 | 40 | 2 | 11 | 12 | 8 |
| **Összesen** | 75 | 498 | **124** | **215** | **236** | **228** |

Az evidence hatása adatbázisonként nagyon eltér. A thrombosis_prediction 0/50-ről 14/50-re javul, mert a kérdései kódokra és orvosi határértékekre épülnek, és ezeket csak az evidence adja meg: a fekvőbeteg `Admission = '+'`, a normál tartomány fölötti LDH `LDH > 500`. A codebase_community szinte nem változik (19 → 20). Itt az evidence többnyire csak azt mondja meg, melyik oszlopban van egy név („csgillespie is the DisplayName of user”), ami a sémából is kitalálható. Ezen az adatbázison egyik lépés sem szignifikáns, a legnagyobb a RAG +5/−0 (p = 0.062).

## 5. Részletek

### Érvényes lekérdezések és javítókörök

| Beállítás | Érvényes és lefutott SQL | Javítás indult | Ebből lefutott | Ebből helyes lett |
|---|---|---|---|---|
| Alap | 411/498 | — | — | — |
| + evidence | 392/498 | — | — | — |
| + evidence + 2 javítókör | 460/498 | 106 | 68 | 20 |
| + evidence + javítás + RAG | 466/498 | 95 | 63 | 13 |

Az evidence-szel kevesebb lekérdezés fut le hibátlanul (411 → 392), mégis jóval több a helyes. 59 lekérdezés, amely evidence nélkül lefutott, evidence-szel hibára futott, 40 pedig fordítva. A hibák főleg nem létező oszlopok és típushibák, például szöveg és szám összehasonlítása. Az evidence a BIRD saját, félig SQL-es jelölését használja (`year(Birthday) > '1930'`, `DIVIDE(COUNT(ID) ...)`), és a modell ezt nem mindig ülteti át helyesen a PostgreSQL-sémára.

Az első kísérlet hibái a „+ evidence” beállításban (106 kérdés):

| Hiba | Kérdések |
|---|---|
| nem létező oszlop | 43 |
| típushiba vagy nem létező függvény | 26 |
| szintaktikai hiba | 12 |
| nullával osztás | 6 |
| GROUP BY / aggregálás | 6 |
| többértelmű oszlopnév | 5 |
| nem létező tábla | 2 |
| egyéb (például a MySQL-es `LIMIT x, y`) | 6 |

A javítókörök itt többet hoznak, mint a saját adatbázisokon: +21, 0 romlással, p < 0.001. A saját méréseken few-shot mellett csak +8–11 volt, mert ott kevés az érvénytelen első kísérlet. A BIRD-en 106 kérdésnél (21%) hibás az első kísérlet. A hibaüzenet többnyire pontosan megmondja, mi a baj: nem létező oszlop, típushiba.

### RAG: miért nem segít a BIRD-en

A BIRD adatbázisai kicsik, 3–13 táblásak. A RAG-beállítás 10 jelöltet keres, ezért a keresés gyakorlatilag mindig az összes táblát (a formula_1-nél 10–12-t a 13-ból) adja tovább. Mind a 498 kérdésnél ott volt minden szükséges tábla a jelöltek között. A hatás tehát teljes egészében az LLM-es táblaválasztásból jön:

- **71 kérdésnél (14%) a táblaválasztás elhagyott egy szükséges táblát.** Ezeken a RAG 25 helyes válaszból 8-at hagyott meg (+3 / −20).
- **A többi 427 kérdésnél** a rövidebb séma kicsit segített: 211 → 220 (+22 / −13).
- **Javítás nélkül a RAG nulla:** a RAG-os futás első kísérletei és a „+ evidence” futás egyaránt 215 helyes, +30 / −30. A negatív előjelű különbség a javítókörökből jön. RAG mellett a javítás csak 13 kérdést mentett meg (20 helyett). Ennek valószínű oka, hogy a javítókör ugyanazt a szűkített sémát kapja, így egy elhagyott táblát a hibaüzenet alapján sem tud pótolni.

Ez egyezik a saját mérésekkel: a RAG egyedül csak a nagy sémán (AdventureWorks, 68 tábla) javított. A web UI beállítása (`pipeline.app_config`) ezért példák nélkül csak 30 táblától kapcsolja be a RAG-ot. A BIRD-adatbázisokon tehát nem használná.

### Költség

| Beállítás | Átlagos idő / kérdés | Medián | Átlagos prompt-token / kérdés | Legnagyobb prompt |
|---|---|---|---|---|
| Alap | 12.7 s (2.9 s egy kérdés nélkül) | 2.5 s | 675 | 1719 |
| + evidence | 2.6 s | 2.4 s | 719 | 1813 |
| + evidence + 2 javítókör | 3.6 s | 2.6 s | 1022 | 2207 |
| + evidence + javítás + RAG | 4.3 s | 3.3 s | 560 | 1663 |

Az alapbeállításban egy kérdésnél (student_club #1426) a modell ismétlő hurokba került: ugyanazokat az oszlopneveket sorolta 81 920 tokenen át, ahol az Ollama leállítja a generálást. Ez 81 percig tartott, és rossz válasznak számít. Az átlagot ez az egy kérdés viszi fel 12.7 s-ra. A többi beállításban nem fordult elő hasonló. A generált lekérdezések közül csak az alapbeállításban ütközött kettő a 10 s-os időkorlátba.

### Reprodukálhatóság

A javítókörös futás első kísérlete ugyanaz a prompt, mint a „+ evidence” futásé. 496/498 kérdésnél a generált SQL karakterre megegyezett, 497/498 kérdésnél a kimenetel is.

## 6. Összevetés a ranglistával

A Mini-Dev saját ranglistája (a BIRD `mini_dev` README-je, PostgreSQL oszlop, EX %, 500 kérdés, evidence-szel) és a saját eredmények:

| Rendszer | EX (PostgreSQL) |
|---|---|
| Mixtral-8x7b | 12.40 |
| Llama3-8b-instruct | 18.40 |
| Phi-3-medium-128k-instruct | 21.60 |
| GPT-35-turbo-instruct | 26.60 |
| GPT-35-turbo | 27.40 |
| Llama3-70b-instruct | 29.40 |
| GPT-4-32k | 35.00 |
| GPT-4 | 35.80 |
| GPT-4-turbo | 36.00 |
| **qwen2.5-coder:7b, alap (evidence nélkül)** | **24.9** |
| **qwen2.5-coder:7b + evidence** | **43.2** |
| **qwen2.5-coder:7b + evidence + 2 javítókör** | **47.4** |

A ranglista modelljei evidence-szel futottak, ezért velük a „+ evidence” sor vethető össze. Ez 43.2%, magasabb a legjobb PostgreSQL-eredménynél (GPT-4-turbo, 36.0%). Ez nem jelenti azt, hogy a rendszer jobb a GPT-4-nél. A mérés több ponton eltér a hivatalostól:

- **Modell és időpont:** a ranglista 2024 közepi modelleket mér. A Qwen2.5-Coder későbbi (2024 ősz), kifejezetten kódra tanított modell. A BIRD fejlesztői készlete 2023 óta nyilvános, ezért nem zárható ki, hogy a kérdések szerepeltek a tanítóadatában.
- **Prompt:** a hivatalos alapprompt `CREATE TABLE`-ként adja a sémát, és lépésenkénti gondolkodást kér (chain-of-thought). Itt a saját sémaszöveg és a saját prompt szerepel, gondolkodási lépés nélkül.
- **Értékek normalizálása:** a kiértékelő az összehasonlítás előtt 4 tizedesre kerekíti a számokat, és egységes alakra hozza a dátumokat és időtartamokat. A hivatalos szkript nyers értékeket hasonlít, így itt egy-egy lebegőpontos eltérés nem számít hibának.
- **Időkorlát:** 10 s a hivatalos 30 s helyett. Ez legfeljebb rontja az eredményt, és csak az alapbeállításban érintett két kérdést.
- **Kérdésszám:** 498 az 500 helyett (két ismétlődő kérdés).

A Qwen2.5-Coder technikai riportja a BIRD-eredményeit csak ábrán közli, és nem írja le pontosan, melyik készleten és milyen beállítással mért. Ezért ahhoz itt nem hasonlítok. Az összevetésből annyi következik, hogy a helyben futó 7B-s modell ezen a benchmarkon a 2024-es nagy felhőmodellek nagyságrendjében teljesít. A ranglista SQLite-oszlopa magasabb: ott a GPT-4 47.8%, a legjobb bejegyzés („TA + GPT-4o”, egy módszer a modell előtt) 63.0%. A „TA +” bejegyzéseknek nincs PostgreSQL-eredménye.

## 7. Következtetések

1. **A BIRD-en az evidence a döntő tényező:** 25% → 43% (+91 kérdés, p < 0.001), mindhárom nehézségi szinten szignifikánsan. A kérdések jó része olyan kódolásra vagy szakmai szabályra épül, amely a sémából nem derül ki. A saját adatbázisokon ezt a szerepet a dinamikus few-shot példák töltik be.
2. **A javítókörök itt erősebbek, mint a saját méréseken:** +21 kérdés, 0 romlással (p < 0.001). A BIRD-en sok az érvénytelen első kísérlet (21%), főleg nem létező oszlop és típushiba miatt.
3. **A RAG kis sémákon nem segít:** −8 kérdés, nem szignifikáns (p = 0.36), a challenging kérdéseken viszont szignifikáns romlás (34 → 26, p = 0.039). A keresés mindig megtalálja a szükséges táblákat, a hibát a 7B modell táblaválasztása okozza. Ez megerősíti a saját mérések eredményét, és azt a döntést, hogy a web UI csak nagy sémán (30 táblától) használja a RAG-ot, ha nincsenek példák.
4. **A legjobb beállítás 47.4% (236/498).** Ez a ranglistán a GPT-4-modellek PostgreSQL-eredményei (35–36%) fölött van, de a mérés eltérései miatt (prompt, normalizálás, újabb modell) ez csak nagyságrendi összevetés.
5. **A saját tesztkészleteken mért 78%-hoz képest a BIRD jóval nehezebb.** A saját mérés legfontosabb tényezője, a few-shot példák, itt hiányzik, mert a BIRD-adatbázisokhoz nincsenek példák. Ugyanazok az irányok azonban itt is érvényesek: a háttértudás a legfontosabb, a javítás biztosan javít, a RAG csak nagy sémán éri meg.
