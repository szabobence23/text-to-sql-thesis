# Text-to-SQL helyi nyelvi modellel

BSc szakdolgozat (BME). A rendszer természetes nyelvű, főként magyar kérdéseket alakít PostgreSQL-lekérdezésekké egy helyben futó nyelvi modellel (Ollama, `qwen2.5-coder:7b`), és méri, mennyit javítanak az egyes módszerek a pontosságon.

- **Adatbázisok:** Olist (brazil webáruház, 9 tábla), Forma–1 (17 tábla), AdventureWorks (68 tábla, 5 séma), és a `sales` mint kis próba-adatbázis. Mindegyikhez 50 magyar és 50 angol tesztkérdés tartozik, helyes lekérdezéssel.
- **Módszerek, mind külön kapcsolhatók és mérhetők:**
  - sémakeresés (RAG): bge-m3 embedding, FK-hidak és LLM-es táblaválasztás;
  - dinamikus few-shot: hasonló megoldott példák a promptban;
  - javítókörök: a PostgreSQL hibaüzenetével;
  - oszlopértékek a sémában;
  - természetes nyelvű válasz, saját ellenőrzéssel.
- **Biztonság:** háromrétegű validáció (szerkezet, függvénytiltólista, `PREPARE`-alapú sémaellenőrzés), utána futtatás csak olvasási jogú szerepkörrel, rollbackkel és időkorláttal. Ezt egy kézzel írt támadáskészlet méri.
- **Felületek:**
  - konzolos demó;
  - webes chat;
  - MCP-szerver, amellyel bármely MCP-kliensbe beköthető (Claude Code, Claude Desktop stb.);
  - kiértékelő szkriptek.

## Telepítés

Kell hozzá Python 3.13, Docker és [Ollama](https://ollama.com).

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull qwen2.5-coder:7b
ollama pull bge-m3
docker compose up -d
```

Az adatbázisok létrehozása: az adatfájlokat a `datasets/<név>/data/` mappába kell tenni. A forrásuk a `dataset.json` leírásában szerepel, az AdventureWorksé a `SOURCES.md`-ben. Utána:

```
.venv\Scripts\python.exe database\setup_dataset.py olist
.venv\Scripts\python.exe database\setup_dataset.py f1
.venv\Scripts\python.exe database\setup_dataset.py adventureworks
```

## Használat

| Mit | Parancs |
|---|---|
| Konzolos demó | `python src\main.py "Hány rendelés van?" --dataset olist` |
| Webes felület | `python src\web_app.py` (http://127.0.0.1:8000) |
| MCP-szerver | a kliens indítja, lásd a [docs/mcp.md](docs/mcp.md) fájlt |
| Kiértékelés | `python src\evaluation\evaluator.py --dataset f1 --language hu --run-name proba` |
| Ismételt / több adatbázisos mérés | `python src\evaluation\run_batch.py --run-name proba --repeats 1` |
| Eredmények összesítése | `python src\evaluation\report.py src\evaluation\results\*_proba*.json` |
| Beállítások összevetése (McNemar) | `python src\evaluation\compare.py proba-a proba-b --reference proba-a` |
| Támadásmérés | `python src\evaluation\attack_evaluator.py --dataset olist` |
| Tesztek | `python -m pytest` (adatbázis nélkül: `-m "not db"`) |

A kiértékelés minden futás eredményét egy JSON-fájlba menti a `src/evaluation/results/` mappába. A fájlban benne van a teljes beállítás, a git-commit, a modell azonosítója és a promptok hash-e, így a futások reprodukálhatók és összevethetők.

## További dokumentáció

- [datasets/README.md](datasets/README.md): adatkészletek, és hogyan lehet újat hozzáadni
- [docs/results.md](docs/results.md): a végső mérések táblázatai, szignifikanciatesztekkel
- [docs/mcp.md](docs/mcp.md): az MCP-szerver, a bekötés és a biztonság
- [CLAUDE.md](CLAUDE.md): részletes architektúra és a mérések története (angolul)
