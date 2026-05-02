# gsea-fgsea-hallmark

Runs **GSEA-style preranked pathway enrichment** from a **gene-level results table** (CSV): build a **ranked gene list** from one **explicitly named numeric statistic**, then test **MSigDB Hallmark** gene sets and export a **pathway-level table** with **NES**, **significance** (raw **P** and **FDR** / **padj**), and **leading-edge** membership for filtering **enriched vs depleted** pathways; optionally deliver a **short HTML summary** with one embedded figure — the **HTML file itself must be generated with Python**, not R. **Prefer a Python analysis stack** when **`BiocManager`** / fresh Bioconductor installs would otherwise be required (see **Implementation preference**). Use when the user asks for **GSEA**, **preranked GSEA**, **fgsea**, **Hallmark enrichment**, **MSigDB Hallmark**, **pathway enrichment from DE statistics**, or **signature / ranked-list enrichment**.

## When to use

- User mentions **GSEA**, **通路富集**, **fgsea**, **Hallmark**, **MSigDB**, **preranked enrichment**, **NES**, **leading edge**, or **enrichment from logFC / t-statistic / signal-to-noise**.
- Input is a **CSV** with **gene identifiers** and **at least one numeric column** chosen as the **ranking statistic** (e.g. **log fold change**, **t statistic**, ** Wald statistic** — the skill requires **naming that column explicitly** in code and report).
- Output expectation: **pathway-level results** suitable for sorting/filtering by **NES** and **FDR**, plus **leading-edge genes** per pathway.
- Web-attached files may appear under `/workspace/uploads/<filename>`; otherwise use **relative paths** in scripts (see Inputs).

## Inputs and data checks

1. **Gene-level results table (CSV)**  
   - Must include a **gene ID column** (e.g. `gene`, `symbol`, `Gene`) and the **ranking statistic** column.  
   - **Peek** at headers and a few rows before assuming column names. A common test layout is `./data/depmap_deg_res.csv` with **`gene`** and **`logFC`** (or another statistic) — use the user’s paths when provided.  
   - **Duplicate gene symbols**: collapse or aggregate with a **documented rule** (e.g. keep row with largest `|stat|`, or mean by symbol); do not feed duplicate names silently.

2. **Ranking direction (critical)**  
   - Build a **named numeric vector**: `names` = gene symbols, `values` = ranking statistic.  
   - **State explicitly** whether **high values = “up” / activated** end of the ranking (typical for **signed logFC**). If the user wants **depletion** at the top of the list, **negate** the statistic and **say so** in the report.  
   - **`fgsea`** uses **decreasing** rank order by default for the vector — confirm behavior for your call (`?fgsea`) and **document** the ordering in the HTML summary.

3. **Gene set source — MSigDB Hallmark**  
   - **R (when used):** **`msigdbr`** to fetch **Hallmark** for the correct **species** (default **human** unless the user specifies otherwise).  
   - **Python (when used):** a **Hallmark `.gmt`** from MSigDB, or **`gseapy`**’s documented way to load **MSigDB / Hallmark** sets — **match gene ID type** to the DE table (usually **symbols**).  
   - **Either stack:** a **Hallmark `.gmt`** is portable — parse with **`fgsea::gmtPathways()`** in R or with **`gseapy`** helpers / plain parsing in Python (see **`gseapy`** docs for **`gmt`**).

4. **Paths**  
   - Use **relative paths** only in code (e.g. input CSV path the user gave); **no** machine-specific absolute paths.  
   - **Output locations are not prescribed** — pick a sensible path for the task (or follow the user’s filename) and **report the chosen paths** in the summary; **create parent directories as needed**.  
   - Web UI uploads: align with `/workspace/uploads/...` when that is the actual working copy.

## Implementation preference (read first)

1. **If `fgsea` / `msigdbr` (or equivalent R stack) is already available** in the environment — you may run the **R workflow** below without installing anything.  
2. **If those packages are missing and installing them would require `BiocManager` / Bioconductor** — **avoid that by default**; use the **Python workflow** (e.g. **`gseapy.prerank`** + Hallmark gene sets from **`gseapy`** or a **`.gmt`** file). Prefer **`pip install gseapy`** (or the project’s existing Python deps) over **`BiocManager::install(...)`** unless the user **explicitly** asks for R/`fgsea`.  
3. **Only** propose **`BiocManager::install(...)`** when the user **insists** on R Bioconductor or the environment policy requires it — give **exact** commands and warn about compile/time.

## Method — R (use only when packages are already present or user demands R)

1. **Packages**  
   - Core: **`fgsea`**.  
   - Hallmark retrieval: **`msigdbr`** (typical: `msigdbr::msigdbr(species = "Homo sapiens", category = "H")` then split to a **named list** of gene vectors), or a **Hallmark `.gmt`** with **`fgsea::gmtPathways()`**.  
   - **Do not** treat **`BiocManager::install`** as the default fix for missing packages — see **Implementation preference**.  
   - Add **`ggplot2`**, **`data.table`**, or helpers **only** if required for I/O or plotting.

2. **Ranked list**  
   - After cleaning: `ranks <- setNames(stat_vector, gene_vector)`; drop **missing** statistic or **missing** gene names.  
   - Optional: **cap** extreme values only if the user asks or if numeric overflow appears — otherwise keep the statistic as provided.

3. **Run `fgsea`**  
   - Call **`fgsea::fgsea(pathways = hallmark_list, stats = ranks, ...)`** and follow **`?fgsea`**: current releases default to a **multilevel** implementation; avoid legacy **`nperm`** unless you intentionally route to the simple sampler (the manual warns about this). Use documented parameters such as **`nPermSimple`** / **`maxSize` / `minSize`** as needed and **record** them in the report.  
   - Set **`set.seed(...)`** when the manual indicates stochastic steps so runs are **reproducible** where possible.  
   - If the user requests **`collapsePathways`** or similar post-processing, apply **after** the base run and **document** it.

4. **Leading edge**  
   - Preserve **leading-edge gene lists** from `fgsea` results; for CSV export, **flatten** list columns to a **single string** per pathway (e.g. `"; "`-separated symbols) while keeping a copy of the interpretation in the report.

5. **Enriched vs depleted**  
   - **NES > 0** with low **FDR**: pathways enriched among **high-ranking** genes (interpretation depends on the chosen statistic direction).  
   - **NES < 0**: depleted / opposite tail — report both tails when summarizing “top pathways”.

## Method — Python (preferred when R deps are not already installed)

1. **Packages**  
   - Typical: **`gseapy`** for **`prerank`** against MSigDB-style gene sets; use **`pandas`** for CSV I/O.  
   - Hallmark sets: **`gseapy`** library names (e.g. `enrichr`/`msigdb` style per **`gseapy` docs**) or a **downloaded Hallmark `.gmt`** parsed into a dict/list of gene lists — **match gene ID style** to the DE table.

2. **Ranked list**  
   - Build a **two-column** table (gene, statistic) or the structure **`prerank`** expects; **document ranking direction** the same as in the R section.

3. **Run preranked GSEA**  
   - Call **`gseapy.prerank`** (or equivalent) with **FDR** reporting enabled; map output columns to **NES**, **pval**, **FDR**, **leading edge** / **genes** as exposed by the library. **State** that **NES / p-values may differ numerically** from **`fgsea`**.

4. **Outputs**  
   - Same **CSV + HTML (Python) + figure** contract as below; plots can be **matplotlib**/**seaborn** from the results table.

## Outputs

1. **Pathway-level results CSV**  
   - Save wherever the **user or task** indicates, or use a **clear, descriptive filename** (e.g. `gsea_hallmark_results.csv`); **do not** treat any output folder as mandatory.  
   - Must include at minimum: **pathway ID / name**, **NES**, **size** (intersection size), **pval** (or equivalent raw permutation **P**), **padj** / **FDR**, and a **leading-edge** column (symbols as one string or consistent delimiter).  
   - Sort or secondary-export **top pathways by `|NES|`** and **significance** for quick review.  
   - Mention **number of pathways tested** and **how many** pass a stated **FDR** threshold (e.g. 0.05) for **NES > 0** and **NES < 0** separately when useful.

2. **Short HTML summary**  
   - After the results CSV and optional figures are produced, use the **`html-report-writer`** skill to assemble the report.  
   - Domain-specific content that must be included: input file(s) and dimensions, ranking statistic and direction, method (R `fgsea` vs Python `gseapy`, Hallmark source, species), top pathways by **NES** and **FDR**, enriched/depleted interpretation, one figure when available, and links/paths to exported CSV outputs.

3. **Verification**  
   - Before finishing, confirm **`file.exists()`** on the **results CSV**, the **HTML**, and any **image** files written.

## If required packages are missing

- **Default**: switch to the **Python** workflow (`gseapy` + GMT or built-in MSigDB/Hallmark access per docs) and **`pip install`** only what is needed — **do not** reach for **`BiocManager`** first.  
- **Only if** the user **explicitly** wants R: state what is missing and give **exact** `BiocManager::install(...)` commands, with a clear **cost** note (time, system deps).  
- Whenever both could apply, **state** that **NES / FDR** from **`gseapy`** and **`fgsea`** are **not** guaranteed to match bit-for-bit.

## Rules

- **Name the ranking statistic explicitly** in code comments and in the report; do not imply a default without checking the CSV.  
- **Hallmark + species** must match the **gene IDs** in the input table (symbols vs Ensembl).  
- **Relative paths** everywhere in scripts and HTML image references; **no** hard-coded user-specific absolute paths.  
- **`BiocManager` / Bioconductor installs**: **not** the default response to missing **`fgsea`** — prefer **Python** unless the user insists on R.  
- For the HTML report, delegate the generic report assembly rules to **`html-report-writer`**; this GSEA skill only defines the required domain facts.  
- **Do not** silently flip ranking direction; if you negate a statistic, **state why**.  
- Keep **reproducibility**: **`set.seed`** when stochastic steps apply, and record **key analysis arguments** (**`fgsea`** or **`gseapy`**) and package versions when practical.  
- When producing **CSV + plot + HTML**, **verify each artifact exists** before claiming the workflow completed.
