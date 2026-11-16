# Fine-tuning bérelt GPU-n

A finomhangolás (LoRA a `Qwen2.5-Coder-7B-Instruct`-on) egyszeri, bérelt GPU-n fut;
a projekthez semmit nem kell bekötni. A kész modell GGUF fájlként jön haza, Ollamába
töltjük, és onnan ugyanúgy mérjük, mint az alapmodellt (`--model`).

| Hol | Mi | Szkript |
|---|---|---|
| itthon | BIRD train importja, gold SQL ellenőrzése, tanítóadat | `import_bird_train.py`, `transpile_gold.py`, `build_sft_data.py` |
| bérelt gép | tanítás, összevonás, GGUF-konverzió | `train_lora.py`, `merge_lora.py`, `export_gguf.sh` |
| itthon | GGUF → Ollama, mérés | `install_ollama_model.py`, `evaluator.py --model` |

A 6 GB-os laptop GPU-ra a 7B modell tanítása nem fér rá; egy RTX 4090 (24 GB) elég
(mért csúcs 21,4 GB, QLoRA nélkül).

Az alábbi lépések azt írják le, ahogy a tanítás 2026-11-15-én ténylegesen lefutott
(a pod a RunPod MCP-szerveren keresztül, a gépen minden SSH-n). Kézzel, a RunPod
webes felületén és Jupyter Lab-ban ugyanez megcsinálható; az eltérések a lépéseknél.
Az 1–9. rész az első futás (BIRD gold célválaszok), a 10. a második (a modell saját
válaszai, `generate_vllm.py`, `build_self_distill.py`).

## 1. Feltöltendő csomag

`finetune/data/finetune-upload.zip` (2,7 MB, sha256 `e3b6051b…57bc`): a három szkript,
a `requirements-train.txt` és a tanítóadat (`sft/train.jsonl` 5507, `sft/valid.jsonl`
696 példa, `sft/meta.json`). Ha a tanítóadat vagy egy szkript változik, újra kell
építeni (`build_sft_data.py`, majd a csomag).

## 2. Gép bérlése (RunPod)

| | Ténylegesen |
|---|---|
| GPU | 1 × RTX 4090 (24 GB), Secure Cloud, EU-RO-1, **0,89 $/óra** |
| image | `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404` (Python 3.12.3, torch 2.8.0+cu128) |
| gép | 12 vCPU, 62 GB RAM |
| network volume | 40 GB, `/workspace`: csomag, adapterek, logok, kész GGUF-ok |
| container disk | 120 GB, helyi: HF-cache (`/root/hf`, ~15 GB), összevont modellek, f16 GGUF |
| elérés | csak SSH (`22/tcp`), saját kulcspárral |

A nagy köztes fájlok (két 15 GB-os összevont modell, 15 GB-os f16 GGUF) a container
diskre kerülnek: a network volume-ra nem férnének, és lassabb is. Ami megmarad, az a
volume-on van, így egy pod-hiba nem viszi el a tanítás eredményét.

Kézzel: **Pods → Deploy**, RTX 4090, RunPod PyTorch template, Container Disk 120 GB
(vagy Volume Disk 100 GB a `/workspace`-en), **Connect → Jupyter Lab** vagy SSH.

## 3. Előkészítés a gépen

```bash
cd /workspace && unzip finetune-upload.zip -d ft && cd ft
cat > env.sh <<'EOF'
export HF_HOME=/root/hf                    # modell-cache a container disken
export HF_HUB_ENABLE_HF_TRANSFER=0
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TOKENIZERS_PARALLELISM=false
EOF
. ./env.sh
pip freeze > pip-freeze-before.txt
pip install --break-system-packages -r requirements-train.txt
nvidia-smi        # RTX 4090, 24 GB
python train_lora.py --data-dir sft --out-dir out --dry-run
```

Az Ubuntu 24.04-es image rendszer-Pythonja PEP 668 szerint „externally managed”: a
sima `pip install` hibával megáll, ezért kell a `--break-system-packages` (a torch
a gyári 2.8.0+cu128 marad; a csomagverziók a `train_meta.json`-ban).

A `--dry-run` letölti a tokenizert, és minden példán ellenőrzi, hogy a prompt bájtra
az, amit az Ollama küld; hibánál megáll. Kimenet: `train: 5507 examples`,
`valid: 696 examples`, 0 kihagyott (leghosszabb példa 2720 token).

**Memóriapróba** a teljes futás előtt: a 32 leghosszabb tanító- és 4 validációs
példából külön `sft` mappa, rajta `train_lora.py --max-steps 2` (= 32 példa, egy
effektív batch kétszer). Csúcs 21,2 GB a 24-ből, 32 s, ~2150 token/s: a bf16 LoRA
elfér, nem kell QLoRA.

## 4. Tanítás

```bash
setsid nohup python train_lora.py --data-dir sft --out-dir out > train.log 2>&1 < /dev/null &
tail -f train.log          # Ctrl+C csak a figyelést állítja le, a tanítást nem
```

A `setsid nohup` miatt a tanítás akkor is fut, ha az SSH-kapcsolat (vagy a böngésző)
bezárul. Beállítások (alapértelmezés): bf16 LoRA, r = 16, alpha = 32, dropout 0,05,
minden lineáris réteg (40,4 M tanítható paraméter, 0,53%), tanulási ráta 1e-4
koszinusszal, 3% warmup, effektív batch 16 (1 × 16 gradiens-akkumuláció), 2 epoch =
688 lépés, seed 0, a veszteség csak a válaszon (376 015 a 4,17 M tokenből). Minden
epoch végén elmenti az adaptert (`out/adapter-epoch1`, `out/adapter-epoch2`), és
kiírja a validációs veszteséget.

Két ártalmatlan figyelmeztetés: „Sliding Window Attention is enabled but not
implemented for `sdpa`” (a Qwen2.5 configjában `use_sliding_window` hamis) és „No
label_names provided” (a validációs veszteség ettől még kiszámolódik).

**Lefutott:** 4148 s (69 perc), ~6 s/lépés, GPU-memória csúcs 21,4 GB.

| | 1. epoch | 2. epoch |
|---|---|---|
| tanítási veszteség (epoch vége) | 0,092 | 0,065 |
| validációs veszteség | **0,0967** | 0,0991 |

A 2. epochban a tanítási veszteség tovább esett, a validációs kicsit nőtt (enyhe
túlillesztés), ezért az **1. epoch** adapterét exportáltuk.

A végén `out/train_meta.json`: minden beállítás, csomagverziók (`pip freeze`), az
alapmodell commitja (`c03e6d35…`), a tanítóadat hash-e, a veszteségek, az idő és a
GPU-memória csúcs.

## 5. Export

```bash
WORK=/root/work setsid nohup bash export_gguf.sh out/adapter-epoch1 /workspace/ft/export \
    > export.log 2>&1 < /dev/null &
```

Összevonja az adaptert az alapmodellbe, és mellette az **érintetlen alapmodellt** is
átviszi ugyanazon az úton (konverziós kontroll). Lefordítja a llama.cpp kvantálóját,
mindkettőt f16 GGUF-fá alakítja és **Q4_K_M**-re kvantálja (mint az Ollama
`qwen2.5-coder:7b`). A `WORK` a köztes fájlok helye (alapértelmezés `/workspace`;
itt a container disk). A `merge_lora.py` `low_cpu_mem_usage`-dzsel tölt, így a
súlyokból egy példány van a RAM-ban (~15 GB, nem ~30).

A llama.cpp-t (commit `e574a17b`) és a konverter venv-jét a tanítás alatt előre
felraktuk (`nice`, 4 szálon; a tanítás ezalatt ~5,5-ről ~6,3 s/lépésre lassult), így
maga az export **4 perc** volt. Eredmény:

| fájl | méret | sha256 |
|---|---|---|
| `qwen2.5-coder-7b-ft-q4_k_m.gguf` | 4 683 073 632 B | `1c45028b…1b76` |
| `qwen2.5-coder-7b-base-q4_k_m.gguf` | 4 683 073 632 B | `09ac4b78…c707` |

plusz `export_meta.json` (llama.cpp commit, teljes sha256-ok) és `train_meta.json`.

## 6. Letöltés

```bash
scp -F <ssh_config> pod:/workspace/ft/export/qwen2.5-coder-7b-ft-q4_k_m.gguf .
```

Itthon a sha256-ot össze kell vetni az `export_meta.json`-nal. A sebességet az otthoni
kapcsolat szabta meg (~2 MB/s összesen, két párhuzamos `scp` sem volt gyorsabb), egy
GGUF így ~40 perc. A logok, a `train_meta.json` és mindkét adapter (2 × 154 MB) is
hazajött (`C:\BME\ft-export\`), hogy az összevonás tanítás nélkül megismételhető legyen.
Kézzel: Jupyter Lab-ban jobb klikk → Download, vagy `runpodctl send` / `receive`.

## 7. A gép leállítása

**Terminate** (nem csak Stop): a leállított pod tárhelye tovább számláz, és a network
volume is külön számláz, amíg nincs törölve. Előtte minden fájl legyen itthon, sha256-tal
ellenőrizve.

## 8. Itthon: Ollama és mérés

```bash
python finetune/install_ollama_model.py <út>/qwen2.5-coder-7b-ft-q4_k_m.gguf qwen2.5-coder-7b-ft
python finetune/install_ollama_model.py <út>/qwen2.5-coder-7b-base-q4_k_m.gguf qwen2.5-coder-7b-base-conv
```

A szkript a `qwen2.5-coder:7b` Modelfile-ját másolja (template, system prompt,
paraméterek), csak a `FROM` sor más, és ellenőrzi, hogy a template és a system prompt
egyezik. Utána ugyanazokkal a beállításokkal mérünk, mint eddig, `--model
qwen2.5-coder-7b-ft`; a `-base-conv` modell a baseline-on megmutatja, mennyit változtat
maga a konverzió (elvárás: zajon belül, ±5/300).

## 9. Eredmény

A mérés a [finetune-results.md](finetune-results.md) fájlban. Röviden: a konverzió nem
torzít (`base-conv` zajon belül egyezik a `qwen2.5-coder:7b`-vel), a finomhangolt modell
a saját adatbázisokon mindhárom mért beállításban szignifikánsan rosszabb (teljes
beállítás: 230 → 141/300), a BIRD Mini-Dev-en ugyanannyit ér (211 vs. 207/498). A modell
a BIRD válaszainak stílusát vette át. A második futás (10. rész) ezt megerősíti: ugyanazokon
a kérdéseken a gold válaszokon tanított modell ugyanúgy romlik (230 → 143), a saját
válaszain tanított nem (230 → 230), és a Mini-Dev-en javítókörök nélkül javít (207 → 224).

## 10. Második futás: tanítás a modell saját válaszain

A második finomhangolás (2026-11-15 délelőtt–délután) azt ellenőrzi, hogy a romlást a
célválaszok stílusa okozta-e. Ugyanaz a recept és ugyanazok a kérdések, de a célválasz
az alapmodell saját, helyesnek bizonyult válasza (`ft-self`), illetve kontrollként a BIRD
gold válasza ugyanazokon a kérdéseken (`ft-goldsub`). Az eredmény a
[finetune-results.md](finetune-results.md) 7. részében.

| Hol | Mi | Szkript |
|---|---|---|
| bérelt gép | az alapmodell válaszai minden promptra (1 mohó + 4 minta) | `generate_vllm.py` |
| itthon | a jelöltek ellenőrzése a birdtrain adatbázisokon, két adatkészlet | `build_self_distill.py` |
| bérelt gép | két tanítás, export | `train_lora.py`, `export_gguf.sh` |

**Gép:** ugyanaz, mint az első futásnál (RTX 4090, Secure Cloud, EU-RO-1, 0,89 $/óra,
`runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404`, 120 GB container disk, 40 GB network
volume a `/workspace`-en, csak SSH). Pod `t2ta75mkrb40rq`, volume `ld9qqr67ra`,
10:54–13:39 UTC.

**Generálás (vLLM).** A vLLM saját venvbe kerül (`requirements-vllm.txt`), mert saját
torch-ot és újabb transformerst hoz, mint a tanítás. A `transformers`-t 4.57.1-re kell
rögzíteni: a pip magától az 5.x-et rakta fel, amivel a vLLM 0.11.0 el sem indul
(`Qwen2Tokenizer has no attribute all_special_tokens_extended`).

```bash
python -m venv /root/venv-vllm
/root/venv-vllm/bin/pip install -r requirements-vllm.txt
/root/venv-vllm/bin/python generate_vllm.py --data-dir sft --out distill
```

Az alapmodell ugyanaz a bf16 Hugging Face modell (commit `c03e6d35…`), amelyre az
adapter tanul. A prompt bájtra az, amit a tanítás lát (Ollama-template, a tokenizer
chat-template-jével ellenőrizve), token-azonosítókként átadva. Promptonként egy mohó
válasz (temperature 0, repetition penalty nélkül) és 4 minta a modell saját
`generation_config`-jával (temperature 0.7, top_p 0.8, top_k 20, repetition_penalty
1.05, seed 0). 6203 prompt, a mohó kör 200 s, mind 804 s (az Ollamán a laptopon ez kb. 8
óra lett volna). Egyik válaszon sem állt meg a hosszkorlát (1024 token).

**Ellenőrzés itthon.**

```bash
python finetune/build_self_distill.py finetune/data/distill
```

Minden jelölt (mohó, majd a minták; azonos SQL egyszer) átmegy a pipeline validációján
(`validate_sql`), és lefut az olvasási szerepkörrel a `birdtrain_<db>` adatbázison.
Helyes, ha set EX vagy relaxed EX szerint egyezik a gold válasz eredményével. A relaxed
elfogadás azért kell, mert csak set EX-szel épp a BIRD minimális-oszlop konvencióját
válogatnánk ki: az alapmodell szokása, hogy a kért érték mellé egy leíró oszlopot is
visszaad. Az első helyes jelölt marad; ahol egy sincs, a kérdés kimarad mindkét
adatkészletből. 15 perc.

| | tanító | validációs |
|---|---|---|
| megtartott kérdés | 3441 / 5507 (62%) | 416 / 696 (60%) |
| mohó válasz | 3094 | 372 |
| minta (1./2./3./4.) | 150 / 104 / 59 / 34 | 24 / 14 / 3 / 3 |
| set EX szerint helyes / csak relaxed EX szerint | 3286 / 155 | 407 / 9 |

A `finetune/data/sft_self/` és `sft_goldsub/` ugyanazokat a kérdéseket, promptokat és
sorrendet tartalmazza, csak a válasz más; az evidence a példák 50,5%-ánál, few-shot
példák 33%-uknál (a teljes adatban 46% és 30%: a könnyebb kérdések maradtak).

**Tanítás.** Ugyanazok a beállítások, mint az első futásnál, a revízió rögzítve
(`--revision c03e6d35…`), egymás után, egy szkriptből; az első modell exportja a második
tanítás alatt futott.

| | `ft-self` | `ft-goldsub` |
|---|---|---|
| példák (tanító / validációs) | 3441 / 416 | 3441 / 416 |
| lépések (2 epoch) | 430 | 430 |
| idő, GPU-csúcs | 2411 s, 21,1 GB | 2465 s, 21,2 GB |
| validációs veszteség 1. / 2. epoch | 0,0229 / **0,0228** | **0,0730** / 0,0738 |
| exportált adapter | 2. epoch | 1. epoch |

Az epochot előre rögzített szabály választotta: a kisebb validációs veszteség. Az
`ft-self` vesztesége azért ilyen kicsi, mert a célválaszok az alapmodell saját szövegei;
a két epoch között alig van különbség.

**Export:** `NAME=ft-self BASE=0 bash export_gguf.sh out-self/adapter-epoch2 export-self`
(és ugyanígy `ft-goldsub`). `BASE=0`: az alapmodell konverziós kontrollja (`base-conv`)
már megvan ugyanazzal a llama.cpp committal (`e574a17b`; a szkript alapértelmezésben ezt
a commitot veszi ki, `LLAMA_COMMIT`-tal felülírható). Modellenként 2 perc. A két GGUF:

| fájl | sha256 |
|---|---|
| `qwen2.5-coder-7b-ft-self-q4_k_m.gguf` | `dba5ee52…e40d` |
| `qwen2.5-coder-7b-ft-goldsub-q4_k_m.gguf` | `684e6576…1b1b` |

**Letöltés:** a GGUF-ok, mind a négy adapter, a `train_meta.json`-ok és a logok a
`C:\BME\ft-export2\` mappába. Egy GGUF ~14 perc volt. A második letöltése az otthoni
internet kiesésekor 3,5 GB-nál megszakadt; `sftp` `reget`-tel onnan folytatódott, a
sha256 egyezett. Utána a pod és a volume törölve.

**Itthon:** `install_ollama_model.py` → `qwen2.5-coder-7b-ft-self`,
`qwen2.5-coder-7b-ft-goldsub`, mérés ugyanazokkal a parancsokkal, mint az első modellnél.
