# survival-signature-km-cox

Runs signature-based survival analysis from a gene-by-sample expression table plus an OS clinical table: build a continuous score (row-scaled genes, mean across signature), median-split High/Low, Kaplan–Meier with log-rank test, Cox regression on the continuous score, optional HTML report with embedded KM figure; use when the user asks for survival analysis, Cox regression, Kaplan–Meier curves, prognosis signatures, or TCGA-style OS workflows.

## When to use

- User mentions **survival analysis**, **Kaplan–Meier**, **KM curve**, **Cox regression**, **Cox PH**, **prognostic signature**, **high/low risk groups**, **OS** (overall survival), or **log-rank**.
- Inputs are a **genes × samples** expression matrix (often `.txt` or `.csv` tab-delimited) and a **sample-level survival table** with time and event columns (e.g. `OS.time`, `OS`), with **sample IDs matching expression column names**.
- Optional second endpoint table (e.g. **PFI**: progression-free interval) if the user supplies it.

## Inputs and data checks

1. **Expression matrix (genes × samples)**  
   - **Rownames** = gene symbols (or IDs consistent with the signature list). **Colnames** = sample IDs.  
   - Peek at dimensions and headers; if the layout is **samples × genes**, **transpose** before scoring.  
   - Note the scale (log TPM/FPKM vs counts); row scaling still runs, but mention the assumption in the report if values look like raw counts.

2. **OS table (CSV)**  
   - Required columns: **survival time** (e.g. `OS.time`) and **event indicator** (e.g. `OS`, 1 = event/death, 0 = censored — confirm coding from the file or user; TCGA-style is common).  
   - A **sample ID column** must align with expression `colnames` (either rownames of the clinical table or an explicit `barcode` / `sample` column).  
   - **Inner join** (or explicit choice) between expression samples and OS rows; report **N** after merge and list **dropped** samples if any.

3. **Signature gene set**  
   - Use the user’s list if provided; otherwise a reasonable default example is **MMR / immune**: `MLH1`, `MSH2`, `MSH6`, `PMS2`, `CD8A`, `CXCL9`, `CXCL10`, `PDCD1`, `CTLA4`.  
   - Subset the expression matrix to genes present in both; report **coverage** (genes found vs requested). If many genes are missing, say scores are less reliable.

4. **Paths**  
   - Prefer **relative paths** in the R script (e.g. `TCGA_CRC_gene_expression.txt`, `TCGA_CRC_OS.csv` next to the script or a stated `./data/` folder).  
   - Web-attached files may appear under `/workspace/uploads/<filename>`; keep paths consistent with the runtime.

## Method (R — `survival`, `surminer`)

1. **Packages**: `survival`, `survminer`; use **base R** for `scale()` / I/O unless something else is clearly needed (e.g. `readr` for large CSVs).  
2. Read expression into a `matrix` with `rownames` = genes, `colnames` = samples.  
3. **Signature score (continuous)**  
   - Subset to signature genes present in the matrix.  
   - **Row-wise z-scale across samples**: e.g. `X <- t(scale(t(X))))` and replace any `NaN` from zero-variance genes with 0 or drop those genes with a note.  
   - **Per-sample mean** across signature rows = one score per sample (column mean of the scaled submatrix).  
4. **Merge** scores with the OS table on sample ID; ensure column names for `Surv(time, event)`.  
5. **Binary group**  
   - Split **High / Low** at the **median** of the continuous score (state which side is “high risk” if time-to-event: usually higher score = higher hazard — interpret after seeing Cox sign).  
6. **Kaplan–Meier**  
   - `survival::survfit(Surv(time, event) ~ group, data = ...)`; plot with `survminer::ggsurvplot` (or equivalent).  
   - **Log-rank**: `survival::survdiff(...)` or output from `survminer` comparisons; report **P value** clearly.  
7. **Cox proportional hazards**  
   - **Continuous score**: `survival::coxph(Surv(time, event) ~ score, data = ...)` (optionally add `ties=` if many tied times).  
   - Report **HR**, **95% CI**, and **Wald / likelihood P** via `summary()` or `broom::tidy()` only if already justified; prefer minimizing extra packages.  
8. **Save fitted object**  
   - `save(cox_fit, file = "CRC_OS_coxph_res.Rdata")` (or a user-specified basename). Use **`.Rdata`** extension; the saved object should be the **`coxph`** fit (and optionally a small `list` with metadata if the user asks).  
9. **Optional PFI**  
   - If `TCGA_CRC_PFI.csv` (or similar) is provided, repeat KM/Cox for **PFI** time/event columns with parallel output names (e.g. `CRC_PFI_coxph_res.Rdata`).

## Outputs (match common reporting expectations)

1. **KM figure**  
   - PNG or PDF next to the script (e.g. `KM_signature_OS.png`); High/Low legend, risk table optional.  
2. **Cox table**  
   - Short console summary or a one-row CSV with HR, lower CI, upper CI, P.  
3. **`CRC_OS_coxph_res.Rdata`** (or user-specified)  
   - Contains the `coxph` object for reproduction (`load()` + `summary()`).  
4. **Short HTML report**  
   - After the KM figure, Cox table, and `.Rdata` are produced, use the **`html-report-writer`** skill to assemble the report.  
   - Domain-specific content that must be included: data (N, genes in signature, event rate), methods (scaling, median split, tests), key findings (log-rank P, Cox HR/CI/P), limitations (single cohort, median dichotomization, proportionality), and embedded KM plot when available.

## If R or packages are missing

- Give **exact install commands**: `install.packages(c("survival", "survminer"))` (both on CRAN).  
- If `survminer` fails, fall back to **base** `plot(survfit(...))` and `survdiff` for log-rank, still with `survival` only.

## Rules

- **Verify artifacts** (`file.exists` / shell `test -f`) for the KM image, `.Rdata`, and HTML before claiming the workflow finished.  
- Always report **sample N** after merge and **censoring/event counts**.  
- State **median cutoff** and which label corresponds to higher raw score.  
- Do not invert HR interpretation silently; align text with the **sign** of the coefficient.  
- Keep **reproducibility**: `set.seed()` only if a step is stochastic; record **package versions** in the HTML if easy (`sessionInfo()` snippet).  
- Add packages **beyond** `survival` / `survminer` only when necessary, and name them in the report.
