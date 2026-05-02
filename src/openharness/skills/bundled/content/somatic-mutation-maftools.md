# somatic-mutation-maftools

Runs **cohort-level somatic mutation summaries** from a standard **MAF** file using **maftools** (optional **data.table** or other helpers only when needed): subset by optional **target gene** and/or **target sample** lists, **mutation frequency** overview, **oncoplot**, and **pairwise co-occurrence / mutual exclusivity** among key genes, plus a **short narrative** of mutation patterns and a **compact HTML report** with embedded figures. Use when the user asks for **MAF analysis**, **maftools**, **mutation summary**, **突变频率**, **Oncoplot**, **共突变**, **mutual exclusivity**, **somatic interactions**, or **cohort mutation landscape** for `OmicsSomaticMutationsMAF.maf` (or another MAF they name).

## When to use

- User mentions **MAF**, **maftools**, **somatic mutations**, **mutation frequency**, **oncoplot**, **co-mutation**, **mutual exclusivity**, **pairwise interactions**, **突变频率**, **Oncoplot**, or **共突变**.
- Primary input is **`OmicsSomaticMutationsMAF.maf`** (or an equivalent MAF); optional **gene list** and/or **sample ID list** to restrict the cohort or highlight genes.
- User expects **fixed-name plots and tables** plus a **brief biological summary** and **HTML** suitable for sharing.

## Inputs and data checks

1. **MAF file**  
   - Standard MAF columns as expected by `maftools::read.maf()` (at minimum Hugo_Symbol, Chromosome, Start_Position, End_Position, Reference_Allele, Tumor_Seq_Allele2, Variant_Classification, Variant_Type, Tumor_Sample_Barcode — follow maftools docs if the build is nonstandard).  
   - Inspect headers and a few rows; confirm **which column holds the primary tumor sample identifier** used for cohort-level plots.

2. **Sample identifiers**  
   - **IDs in any user sample list must match the MAF sample column after any renaming** (commonly **`Tumor_Sample_Barcode`**).  
   - If the file uses a different column (e.g. `Tumor_Sample_UUID`, `Sample_ID`), **rename explicitly in R** (e.g. `data.table::setnames()` or `dplyr::rename()`) and **state clearly in the text/HTML summary that remapping was applied** (old name → new name).

3. **Gene list (optional)**  
   - Plain text or CSV: one gene per line or a column of symbols **consistent with `Hugo_Symbol` in the MAF** (after any alias resolution the user requests).  
   - Genes absent from the MAF after subsetting should be **listed as not observed** rather than silently dropped without comment.

4. **Paths**  
   - **R scripts must not hard-code absolute machine paths.** Use **read/write relative to the process working directory** (e.g. `./OmicsSomaticMutationsMAF.maf`, `./summary_maf.png`).  
   - In web or sandbox flows, uploads may appear as `/workspace/uploads/<filename>`; still **avoid embedding user-specific directory prefixes** inside the script — parameterize filenames or assume execution from a chosen working directory and document it in the HTML.

5. **Large MAF / mutation tables (context- and token-aware)**  
   - Do **not** paste **full MAF** contents, **entire** sample×gene matrices, or other **large tables** into the **chat** (or any reply path that duplicates the whole attachment in the model request). That pattern often blows **API / model context limits** and adds no reproducible value.  
   - Prefer **`wc -l`**, **`head -c 8192`** (byte-capped peek), or **`cut`**/ **`awk`** for column-safe previews — **not** `read_file` on wide MAF bodies with a large `limit` (rows can be enormous).  
   - Work **path-first**: probe with small reads; perform the full **`read.maf`** and plots inside a **saved R script** run in the workspace or sandbox.  
   - Summarize for the user with **numbers** (row counts, sample **N**, gene **N**, paths to saved artifacts) — not megabyte-scale text dumps.  
   - When **`Rscript` fails**, do **not** paste multi-screen installer spam into the chat: **`tail -n 40`** of a log file (or the **last ~2k characters** of stderr) is enough.  
   - If inputs plus thread history still exceed limits, say so clearly and suggest **a fresh session**, **uploading a subset** (genes/samples/columns), or **splitting** the analysis — without pasting large excerpts to “prove” inspection.

## Offline / networkless execution (sandboxes)

- Many execution environments **block outbound network** (`BiocManager::install`, `install.packages` to CRAN/Bioc will **fail** with “cannot open URL”).  
- **Analysis scripts** (`analyze_maf.R`, etc.) must **assume offline execution**: start with `stopifnot(requireNamespace("maftools", quietly = TRUE))` (and `data.table` only if the script imports it). **Do not** embed `BiocManager::install()`, `install.packages()`, or `remotes::install_*()` in scripts that are meant to run in the sandbox.  
- **Dependencies scope**: this workflow needs **`maftools`** (and optionally **`data.table`**). **Do not** install or attach unrelated stacks (**GSVA**, **Seurat**, **tidyverse** wholesale, etc.) unless the user explicitly asks for those analyses.  
- If **`maftools` is absent** in the sandbox, **stop early** with a clear message: analysis cannot run until the **image / runtime is rebuilt** with Bioconductor packages, or the user runs the same script **locally / on a machine with internet** after installing. Optionally print **exact** one-line install commands **for the user’s terminal outside the sandbox** — do not loop on failed installs inside the sandbox.

## Method (R / maftools — preferred)

1. **Packages**  
   - Core: **`maftools`**. **In sandbox / CI**: rely on **preinstalled** packages only (see **Offline / networkless execution**). **On an interactive machine with network** where the user asked you to set up R, `BiocManager::install("maftools")` is acceptable **once**, outside the saved analysis script if possible.  
   - Add **`data.table`** (or **`readr`**) only if needed for fast I/O or list parsing — same offline rules apply.  
   - Run batch jobs as **`Rscript analyze_maf.R > rscript.stdout.log 2> rscript.stderr.log`** (or equivalent) so failures can be diagnosed with **`tail`** without flooding the tool channel.

2. **Read and subset**  
   - `maf <- maftools::read.maf(maf = "./<input>.maf", ...)` with appropriate optional clinical features only if supplied and valid.  
   - If a **sample list** is provided: restrict mutations to those samples (via MAF row filter **before** or **after** `read.maf` in a documented way — e.g. filter the MAF data.frame then `read.maf` on the filtered file in memory, or use `maftools` subset helpers if applicable).  
   - If a **gene list** is provided: restrict to those genes for **gene-centric** tables and plots **as requested**, but keep a **clear rule** in the report: e.g. “all plots use mutations restricted to listed genes” vs “cohort MAF unchanged, oncoplot highlights subset” — default to **consistency between summary MAF and oncoplot** unless the user specifies otherwise.

3. **Mutation overview**  
   - `plotmafSummary(maf = maf, ...)` → save as **`summary_maf.png`** (`png()`/`dev.off()` or `ggplot2::ggsave` if wrapping maftools output).

4. **Oncoplot genes — explicit rule**  
   - **If the user supplies a target gene list**: oncoplot **those genes** (order: user order or decreasing mutation frequency within the list — **state which**).  
   - **If no gene list**: oncoplot the **top mutated genes by cohort frequency** (default **top 20** unless the user names another *N*).  
   - **Always state the rule used** in the narrative and HTML.

5. **Co-occurrence / mutual exclusivity**  
   - For **key genes** (user list intersecting observed genes, or the **same genes shown in the oncoplot**), run **`maftools::somaticInteractions()`** (or the current maftools-recommended pairwise function for the installed version) to obtain **pairwise tests**.  
   - Export the **interaction / results table** exactly as **`mutation_co-occurence结果.csv`** (fixed spelling as requested for downstream tooling).  
   - Summarize **which pairs trend toward co-occurrence vs exclusivity** with **appropriate multiple-testing caution** (note that many pairwise tests are run; mention **exploratory** nature unless the user defines a formal error-rate strategy).

6. **Brief text summary**  
   - For **target genes** (user list or top-*N* rule above): **mutation frequencies**, dominant **variant classes** if informative, and **1–3 sentences** on **patterns in this cohort** (hotspots, truncating vs missense enrichment where visible from MAF annotation).

7. **HTML report**  
   - After MAF tables and figures are produced, use the **`html-report-writer`** skill to assemble a short report.  
   - Domain-specific content that must be included: objective, inputs (files, subset rules, **any column remap** for sample IDs), methods (maftools functions, versions if available), mutation frequencies, co-occurrence/exclusivity findings, limitations (MAF completeness, coverage, multiple testing), and embedded **`summary_maf.png`** / **`oncoplot.png`** when available.

## Outputs (fixed names)

1. **`summary_maf.png`** — cohort **mutation summary** figure from maftools.  
2. **`oncoplot.png`** — **oncoplot** for genes per the rule above.  
3. **`mutation_co-occurence结果.csv`** — **pairwise co-occurrence / mutual exclusivity** table from `somaticInteractions()` (or equivalent), with readable column names.  
4. **Short HTML report** (e.g. `somatic_mutation_report.html` or a user-specified name in the same working directory) — workflow, **remapping notes**, key results, embedded figures.  
5. **Optional but recommended**: the **R script** used (`analyze_maf.R` or similar) saved beside outputs, using **only working-directory-relative** data and output paths.

## If R / maftools is missing

- **In sandbox**: report that **`maftools` is not available offline**; do **not** burn turns retrying installs. Give **exact** install commands for the user’s **local** R (`install.packages("BiocManager")`; `BiocManager::install("maftools")`) and state that the **sandbox image** may need rebuilding with those packages.  
- **Locally / with network**: installing **maftools** once is fine; keep installs **out of** the reproducible `analyze_maf.R` if the user wants a script that runs anywhere.  
- Do **not** silently substitute a different toolkit unless the user declines R or install fails; if a fallback is required, warn that **plots and interaction statistics may not match maftools**.

## Rules

- **Declare sample-column remapping** whenever tumor sample IDs are renamed to match lists (e.g. → `Tumor_Sample_Barcode`).  
- **Declare the oncoplot gene-selection rule** (user list vs top-*N* by frequency).  
- **Subset the MAF** when lists are provided, and describe **final sample and gene counts** in text and HTML.  
- **Verify each artifact exists on disk** (`file.exists()` in R, or shell `test -f`) before claiming completion — especially the **HTML** after image embedding.  
- Keep analysis **reproducible**: save session **package versions** when practical (`sessionInfo()` snippet into HTML or log).  
- Do not **hard-code** host-specific absolute paths inside scripts; use **`./`**-style paths and a documented working directory.  
- Respect **item 5 (Large MAF / mutation tables)** under **Inputs**: **path-first** workflow, **no full-file or whole-matrix dumps** in chat; keep user-facing text to **counts, paths, and short quotes** (e.g. header line) only.  
- Follow **Offline / networkless execution**: **no package installs inside sandbox scripts**; **narrow dependencies**; **short log excerpts** on failure.
