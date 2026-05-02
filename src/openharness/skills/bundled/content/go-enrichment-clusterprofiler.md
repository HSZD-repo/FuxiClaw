# go-enrichment-clusterprofiler

Runs **human Gene Ontology (GO) over-representation enrichment** from a **plain-text gene-symbol list** (one symbol per line unless the file format is obviously different), using **Bioconductor `org.Hs.eg.db`** for annotation / ID consistency and **`clusterProfiler::enrichGO`** for BP, CC, and MF **separately**; the **HTML summary is produced with Python**, not R. Use when the user asks for **GO enrichment**, **Gene Ontology**, **GO-BP / GO-CC / GO-MF**, **functional annotation**, **ORA**, or **clusterProfiler**-style GO analysis with **BH** multiple-testing control and standard reporting tables plus a short HTML summary.

## When to use

- User mentions **GO enrichment**, **Gene Ontology**, **Biological Process**, **Cellular Component**, **Molecular Function**, **ORA**, or **`enrichGO` / clusterProfiler**.
- Input is a **gene list** as **symbols** (plain text: **one symbol per line**); if the file is clearly **comma-/tab-separated** with headers, parse accordingly instead of blindly splitting on newlines only.
- Scope is **Homo sapiens** and mapping via **`org.Hs.eg.db`** (do not swap organism unless the user asks).
- User expects **three** result tables (BP, CC, MF), **BH**-adjusted inference, stated cutoffs, and often a **short HTML report** with at least one **figure** (barplot, dotplot, or similar). The **HTML report file itself must be generated with Python**, not R (see Outputs).

## Inputs and data checks

1. **Gene list file**  
   - Default: **one HGNC-style gene symbol per line**; trim whitespace; drop empty lines; optionally de-duplicate while **preserving** a note that duplicates were removed.  
   - If the file is **obviously** CSV/TSV with a dedicated symbol column, read that column.  
   - Report **N input genes** and **N unique** after cleaning.

2. **Organism / annotation**  
   - Use **`org.Hs.eg.db`** as **`OrgDb`** in `enrichGO` (and for any explicit **`AnnotationDbi::select`** / **`clusterProfiler::bitr`** steps if you need to document ID translation).  
   - For standard symbol input, pass genes as **`keyType = "SYMBOL"`** so mapping stays tied to `org.Hs.eg.db`.

3. **Paths**  
   - Use **relative paths** in scripts (e.g. `./data/genelist4test.txt`, `./res/...`).  
   - Web-attached files may appear under `/workspace/uploads/<filename>`; align paths with the execution environment.  
   - **Do not** invent directory trees (e.g. `data/`, `res/`) unless the user or task already uses them; otherwise create only what is needed and keep references relative.

## Method (R / Bioconductor — preferred)

1. **Packages**  
   - Core: **`clusterProfiler`**, **`org.Hs.eg.db`**.  
   - Install if missing, e.g. `BiocManager::install(c("clusterProfiler", "org.Hs.eg.db"))`.  
   - Add **`enrichplot`**, **`ggplot2`**, or other packages **only** for plotting or parsing when needed.

2. **Enrichment — three separate runs**  
   - For each ontology **`ont` ∈ `c("BP", "CC", "MF")`**, call **`clusterProfiler::enrichGO`** with:  
     - **`gene`**: cleaned symbol vector.  
     - **`OrgDb = org.Hs.eg.db::org.Hs.eg.db`**, **`keyType = "SYMBOL"`**.  
     - **`ont`**: `"BP"`, `"CC"`, or `"MF"` (do **not** use `ont = "ALL"` for this workflow).  
     - **`pAdjustMethod = "BH"`** — Benjamini–Hochberg FDR on enrichment **P** values.  
     - **`pvalueCutoff = 0.05`** and **`qvalueCutoff = 0.2`**.

3. **How cutoffs map to `enrichGO` arguments (state this explicitly in the report)**  
   - Per the **`?enrichGO`** documentation: **`pvalueCutoff`** is the **adjusted P-value** cutoff used to **report** enriched terms.  
   - **`pAdjustMethod = "BH"`** selects **Benjamini–Hochberg** adjustment (reported column is typically **`p.adjust`**).  
   - **`qvalueCutoff`** is the **q-value** cutoff; the manual states that tests must satisfy **all** of: (i) **`pvalueCutoff`** on **unadjusted** P values, (ii) **`pvalueCutoff`** on **adjusted** P values, and (iii) **`qvalueCutoff`** on **q-values**, to be reported.  
   - If any installed version’s behavior differs, follow **`?enrichGO`** for that version and **document** what was used.

4. **Readable gene columns (symbols in output)**  
   - Either set **`readable = TRUE`** in `enrichGO`, or pipe the result through **`clusterProfiler::setReadable(..., OrgDb = org.Hs.eg.db, keyType = "ENTREZID")`** depending on ID column behavior — goal is **gene symbols** in the exported table for **query genes per term**.

5. **Optional figures for the HTML report**  
   - You may create plots in **R** (`enrichplot`, `ggplot2`, etc.) and save **PNG** (or PDF) next to the deliverables, **or** build simple plots in **Python** (e.g. **matplotlib**) from the exported CSVs.  
   - **Do not** build or write the **HTML document** in R — assembly of the final `.html` file is **Python-only** (see Outputs).

## Outputs

1. **Three CSV files (BP, CC, MF)**  
   - Filenames: follow the user (e.g. `res/AML_bp_go_res.csv`, `res/AML_cc_go_res.csv`, `res/AML_mf_go_res.csv`) or a clear pattern like `*_go_bp.csv`, `*_go_cc.csv`, `*_go_mf.csv`.  
   - Export from **`as.data.frame()`** on each `enrichResult` (or equivalent) so columns are flat and portable.  
   - Each table **must** include at least:  
     - **Term name** — e.g. **`Description`**.  
     - **Enrichment strength / counts** — e.g. **`GeneRatio`**, **`BgRatio`**, and/or **`Count`** (state which columns you kept).  
     - **Raw P** — **`pvalue`**.  
     - **BH-adjusted P** — **`p.adjust`**.  
     - **Query genes hitting the term** — prefer **symbols**; the **`geneID`** column after `setReadable` / `readable = TRUE` is often slash-separated; use a **consistent delimiter** if you concatenate (e.g. `"; "` or keep `/` to match clusterProfiler).  
   - Optionally include **`ID`**, **`GeneRatio`/`BgRatio`** explicitly if not already present.

2. **Short HTML report**  
   - After the BP/CC/MF CSVs and optional plots are written, use the **`html-report-writer`** skill to assemble the report.  
   - Domain-specific content that must be included: file name(s), **N** genes, organism, **`org.Hs.eg.db`**, `enrichGO`, **`ont`** run separately, **`pAdjustMethod = "BH"`**, **`pvalueCutoff`**, **`qvalueCutoff`**, the cutoff-to-argument mapping above, counts of significant terms per ontology, top themes/notable genes, and links/paths to all BP/CC/MF CSVs.  
   - Include at least one embedded figure when a plot exists.

3. **Verification**  
   - Before finishing, confirm all **three CSVs** and the **HTML** (and any **figure** files) **`file.exists()`** or shell-equivalent.

## If R / Bioconductor packages are missing

- State what is missing and give **exact** install commands (`install.packages("BiocManager")`; `BiocManager::install(c("clusterProfiler", "org.Hs.eg.db"))`).  
- Only if R is unavailable and the user accepts it, sketch a **non-Bioconductor** fallback and warn that results may not match `enrichGO`.

## Rules

- **Human + `org.Hs.eg.db`** unless the user changes organism.  
- **BP, CC, MF** as **three separate** `enrichGO` calls with identical statistical arguments unless the user requests otherwise.  
- **Relative paths** in code and HTML image references; **no** hard-coded machine-specific absolute paths.  
- For the HTML report, delegate the generic report assembly rules to **`html-report-writer`**; this GO skill only defines the required enrichment-specific facts.  
- **Declare** cutoff → argument mapping and **report** effective numbers of terms **per ontology**.  
- **Do not** silently change **`pAdjustMethod`** or cutoffs.  
- Keep the analysis **reproducible**: saved tables, session notes with package versions when practical.
