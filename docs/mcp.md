# MCP-szerver

A text-to-SQL rendszer [Model Context Protocol](https://modelcontextprotocol.io) (MCP) szerverként is elérhető. Az MCP nyílt szabvány arra, hogyan használhat egy MI-asszisztens külső eszközöket. Ezért a szerver változtatás nélkül beköthető bármely MCP-klienst támogató alkalmazásba: Claude Code, Claude Desktop, VS Code, Cursor és mások.

```
Felhasználó → MCP-kliens (saját nyelvi modellel) → MCP (stdio) → src/mcp_server.py
                                                                    │
                                     service.py (ugyanaz, mint a web UI-ban)
                                                                    │
                                 pipeline (qwen2.5-coder:7b, Ollama) → PostgreSQL
```

A szerver csak egy újabb front-end a `pipeline.run_pipeline` előtt, ugyanúgy, mint a konzolos demó, a web UI és a kiértékelő. Ugyanazokat a motorokat és ugyanazt a beállítást használja, mint a web UI: `pipeline.app_config`, 5 few-shot példa, RAG, 2 javítókör és természetes nyelvű válasz.

## Eszközök

| Eszköz | Mit csinál |
|---|---|
| `list_databases()` | Az elérhető adatbázisok neve és leírása |
| `ask_database(question, database)` | **A teljes rendszer:** a helyi modell megírja és lefuttatja az SQL-t, és a kérdés nyelvén válaszol. Visszaadja az SQL-t, legfeljebb 50 sort és a „gyanús” jelzést (`doubtful`). |
| `get_schema(database, tables?)` | Ugyanaz a sémaszöveg, amit a helyi modell lát, a dataset-tippekkel együtt. Kérhető csak a megadott táblákra is. |
| `find_tables(question, database, k=10)` | A RAG-kereső (bge-m3 és a köztes FK-táblák): a kérdéshez legjobban illő táblák |
| `find_examples(question, database, n=3)` | A leghasonlóbb megoldott példák az `examples.json`-ból, SQL-lel |
| `run_sql(sql, database, max_rows=50)` | Saját lekérdezés futtatása. Ugyanazon a validációs láncon megy át, mint a pipeline lekérdezései, és csak olvasási jogú szerepkörrel, 10 másodperces időkorláttal fut. |

Két használati mód van:

- **A) kész rendszer:** az `ask_database` eszközzel az SQL-t a mi pipeline-unk írja.
- **B) nyers eszközök:** a `get_schema`, `find_tables`, `find_examples` és `run_sql` eszközzel a kliens modellje maga írja az SQL-t.

Mindegyik eszköz csak olvasásra szolgáló eszközként van jelölve. Az eszközök leírása angol, mert ezt a kliens modellje olvassa.

## Előfeltételek

- Fut a PostgreSQL konténer: `docker compose up -d`.
- Fut az Ollama, és le van töltve a `qwen2.5-coder:7b` és a `bge-m3` modell.
- Telepítve vannak a függőségek: `.venv\Scripts\python.exe -m pip install -r requirements.txt` (köztük az `mcp` 2.x).

A szervert a kliens indítja el, kézzel nem kell futtatni. Kipróbálni így lehet: `.venv\Scripts\python.exe src\mcp_server.py`. Ilyenkor a szerver a standard bemeneten JSON-RPC üzenetekre vár.

## Bekötés

### Claude Code (VS Code-bővítmény vagy CLI)

A repó gyökerében lévő [`.mcp.json`](../.mcp.json) már tartalmazza a szervert:

```json
{
  "mcpServers": {
    "text-to-sql": {
      "type": "stdio",
      "command": ".venv/Scripts/python.exe",
      "args": ["src/mcp_server.py"]
    }
  }
}
```

1. Nyiss új Claude Code munkamenetet a repóban. Projektszintű szervert az első indításkor jóvá kell hagyni.
2. A `/mcp` parancs mutatja a szerver állapotát és az eszközöket.
3. Minden eszközhíváshoz engedélyt kér. Ha nem kell minden hívást külön jóváhagyni, a `.claude/settings.local.json` fájlban a `"permissions": {"allow": ["mcp__text-to-sql"]}` beállítás a szerver összes eszközét engedélyezi.

Nem interaktív próba (a VS Code-bővítmény saját `claude.exe`-jével vagy a `claude` CLI-vel):

```
claude -p "Hány rendelés van az Olist adatbázisban?" --mcp-config .mcp.json --strict-mcp-config --allowedTools "mcp__text-to-sql__list_databases,mcp__text-to-sql__ask_database"
```

### Claude Desktop

A `%APPDATA%\Claude\claude_desktop_config.json` fájlba kell beírni. Itt abszolút útvonal kell, mert a Claude Desktop nem a repó könyvtárából indítja a szervert:

```json
{
  "mcpServers": {
    "text-to-sql": {
      "command": "C:\\BME\\text-to-sql\\.venv\\Scripts\\python.exe",
      "args": ["C:\\BME\\text-to-sql\\src\\mcp_server.py"]
    }
  }
}
```

Utána újra kell indítani a Claude Desktopot.

### Más kliensek

Minden stdio-t támogató MCP-kliensnek ugyanez a két adat kell: a parancs (a venv Pythonja) és az argumentum (`src/mcp_server.py`). A beállítás formátuma kliensenként kicsit eltér. Fejlesztéshez és hibakereséshez az MCP Inspector jó választás: böngészőben fut, nincs benne nyelvi modell, az eszközöket kézzel lehet meghívni.

```
npx @modelcontextprotocol/inspector .venv\Scripts\python.exe src\mcp_server.py
```

## Demó

Példakérdések:

- „Hány rendelés van az Olist adatbázisban?”
- „Ki nyerte a 2007-es Forma–1-es világbajnokságot?”
- „Melyik pilóta nyerte a legtöbb futamot a 2010-es szezonban?”
- „Melyik 5 termék hozta a legtöbb bevételt az AdventureWorksben?”

Egy rögzített futás (2026-11-04, Claude Code `-p`, engedélyezett eszközök: `list_databases` és `ask_database`). A kérdés: „Melyik pilóta nyerte a legtöbb futamot a 2010-es szezonban?”

1. A Claude meghívta a `list_databases`, majd az `ask_database` eszközt az `f1` adatbázisra. A helyi rendszer 33 másodperc alatt, javítókör nélkül válaszolt: Fernando Alonso, 5 győzelem. A „gyanús” jelzés nem jelent meg.
2. A Claude észrevette, hogy a generált SQL `LIMIT 1`-gyel csak egy pilótát ad vissza. Holtversenynél ez elhallgatja a többieket, és 2010-ben Sebastian Vettelnek is 5 győzelme volt. Az adatbázis ezt igazolja: Alonso 5, Vettel 5, Webber 4.
3. Ezután magától a B módra próbált váltani: le akarta kérni a sémát a `get_schema`-val, és `LIMIT 1` nélkül akarta lefuttatni a lekérdezést a `run_sql`-lel. Ezt csak azért nem tehette meg, mert ebben a futásban ez a két eszköz nem volt engedélyezve.

Mit mutat ez a futás:

- A szerver szabványos kliensből is működik.
- A helyi rendszer „helyes, de hiányos” hibáját (holtverseny `LIMIT 1` mellett) a saját ellenőrzése nem veszi észre, mert a visszaadott sor önmagában hihető.
- Egy erősebb kliens modell a nyers eszközökkel ki tudja javítani ezt a hibát.

## Biztonság és adatvédelem

- **Írni nem lehet.** A `run_sql` ugyanazon a láncon megy át, mint a pipeline saját lekérdezései: szerkezeti ellenőrzés, függvénytiltólista, a PostgreSQL `PREPARE`-alapú sémaellenőrzése, végül futtatás csak olvasási jogú szerepkörrel, rollbackkel és 10 másodperces időkorláttal. Az `attacks.json` 25 támadása MCP-n át is mind a várt rétegen akadt el, és minden esetben ugyanazon, mint közvetlen futtatásnál:

  ```
  python src/evaluation/attack_evaluator.py --dataset olist --via-mcp
  ```

- **Ismert rés:** a `SELECT query FROM pg_stat_activity` lefut (#25). MCP-n át ez azt jelenti, hogy egy külső kliens láthatja ugyanannak a szerepkörnek a többi munkamenetét, például a web UI éppen futó lekérdezéseinek szövegét.
- **Az adatok elhagyhatják a gépet.** Felhőben futó kliens modellnél (Claude) az eszközök eredménye, vagyis a sorok, a séma és a példák, eljut a modellhez. Ez eltér a „minden helyben fut” alapelvtől. Az `ask_database` legfeljebb 50 sort ad vissza, a `run_sql` alapból 50-et, legfeljebb 200-at. Teljesen helyi működéshez helyi modellt futtató MCP-kliens kell.
- **A szerver csak helyben érhető el.** stdio kapcsolaton fut, hálózati portot nem nyit.

## Tesztek

```
python -m pytest src/tests/test_mcp_server.py src/tests/test_service.py src/tests/test_attack_evaluator.py
```

A `test_mcp_server.py` folyamaton belül hívja az eszközöket, álobjektumokkal. Egy tesztje valódi stdio-folyamatként indítja a szervert. Ezekhez nem kell sem adatbázis, sem LLM. A `test_service.py` `db`-jelölésű tesztjei a `run_sql`-t a valódi Olist adatbázison futtatják.
