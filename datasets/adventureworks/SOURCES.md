# AdventureWorks: data sources

Downloaded on 2026-10-11. The raw files in `data/` are not in git; this
file is how to get exactly the same files again.

## 1. Data: Microsoft AdventureWorks OLTP (SQL Server sample)

- Repository: https://github.com/microsoft/sql-server-samples
- Release: "AdventureWorks sample databases", tag `adventureworks`,
  published 2017-12-12:
  https://github.com/microsoft/sql-server-samples/releases/tag/adventureworks
- File: `AdventureWorks-oltp-install-script.zip`
  https://github.com/microsoft/sql-server-samples/releases/download/adventureworks/AdventureWorks-oltp-install-script.zip
  - Asset last updated by Microsoft: 2025-11-18 (later than the release date)
  - Size: 17 486 641 bytes
  - SHA-256: `58962e94ea386ef7cd3d8a08211bfd42a79d9b81bdd68fd4b6b0051de6c5bd42`
  - Contents: 69 CSV files and `instawdb.sql` (the SQL Server install script)
- License: MIT License text in the repository's
  [license.txt](https://github.com/microsoft/sql-server-samples/blob/master/license.txt)
  ("Microsoft SQL Server Sample Code, Copyright (c) Microsoft Corporation").
  GitHub labels it "Other" only because of the non-standard header.

## 2. PostgreSQL port: lorint/AdventureWorks-for-Postgres

- Repository: https://github.com/lorint/AdventureWorks-for-Postgres
- Pinned commit: `b474991f0df1c4bf55ca4735eb0254ca0709eed2`
  (2026-06-29, "Merge pull request #21 from WJ44/master"):
  https://github.com/lorint/AdventureWorks-for-Postgres/tree/b474991f0df1c4bf55ca4735eb0254ca0709eed2
- File: source archive of that commit
  https://github.com/lorint/AdventureWorks-for-Postgres/archive/b474991f0df1c4bf55ca4735eb0254ca0709eed2.zip
  - Size: 38 614 bytes
  - SHA-256: `f9a687fe1d36a54ed7e24b23c08020deba04d7d1f0e62049242fa2775d7bf07a`
  - Contents: `install.sql` (PostgreSQL schema and load script),
    `update_csvs.rb` (converts Microsoft's CSVs for PostgreSQL), README
- License: MIT

## How the database is built

1. `python datasets/adventureworks/prepare_data.py` converts the CSVs into
   `data/converted/`. It is a Python port of the port's `update_csvs.rb`
   (so Ruby is not needed) and converts the same 15 files that the Ruby
   script lists; the other 54 are copied unchanged. The downloaded files
   are not modified.
2. `python database/setup_dataset.py adventureworks` runs `import.sql`,
   which executes the port's `install.sql` unchanged from
   `data/converted/`.

Observations after loading (2026-10-11):
- All 68 tables in 5 schemas load without errors; row counts match the
  CSVs. `production.productreview` is the exception by design: the port
  inserts its 4 reviews with an `INSERT` (multi-line text breaks `\copy`).
- Dates are not consistent across tables: sales orders run 2022-05-30 to
  2025-06-29 (Microsoft's 2025 update shifted them by about 11 years),
  employee hire dates are 2006-2013, and the 4 product reviews are dated
  2013 (the port's `INSERT`; the updated CSV has 2024).
- The port also creates 20 views and 68 shortcut views in schemas
  `pe`, `hr`, `pr`, `pu`, `sa`; the prompt lists only the 68 base tables.
- It installs the `tablefunc` extension, whose `crosstab`/`connectby` run
  SQL given as a string; they are on the function blocklist.

## Layout after download

```
data/AdventureWorks-oltp-install-script.zip   # source 1, as downloaded
data/*.csv, data/instawdb.sql                 # source 1, extracted
data/AdventureWorks-for-Postgres-<commit>.zip # source 2, as downloaded
data/postgres-port/                           # source 2, extracted
data/converted/                               # prepare_data.py output
```
