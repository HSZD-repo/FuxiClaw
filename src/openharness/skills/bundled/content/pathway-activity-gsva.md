# pathway-activity-gsva

Runs GSVA pathway-activity analysis from a gene-by-sample expression matrix plus MSigDB-style GMT gene sets; use when the user asks for GSVA, Hallmark/E2F scores, pathway enrichment scores per sample, or DepMap-style expression tables with optional academic HTML reporting.

## When to use

- User mentions **pathway activity**, **GSVA**, **sample-level pathway scores**, **Hallmark**, **E2F targets**, or **gene set variation analysis**.
- Inputs are a **CSV expression matrix** (typically genes × samples) and one or more **`.gmt`** files (or equivalent gene-set definitions).
- User attached files via the web UI (paths under `/workspace/uploads/` after injection).

## Inputs and data checks

1. **Expression matrix (CSV)**  
   - Default layout: **first column = gene identifiers** (symbols or Ensembl IDs consistent with the GMT), **remaining columns = samples**.  
   - Peek at the first rows/columns; if the layout is **samples × genes**, transpose before GSVA.  
   - Values are usually **log-normalized** (log TPM/CPM/RPKM). Raw **counts** need a different kernel (see below).

2. **Gene sets (GMT)**  
   - Standard GMT: one line per set — name, description, then tab-separated gene IDs.  
   - Prefer `GSVA::readGMT()` in R; if needed for compatibility, `GSEABase::getGmt()` is also acceptable. Parse manually only if R is unavailable and the user accepts a documented Python substitute.

3. **Paths**  
   - Web-attached files appear as `/workspace/uploads/<filename>` (see system prompt). Do not copy them elsewhere unless the user asks.

## Method (R / Bioconductor — preferred)

1. Ensure packages: `GSVA`, `GSEABase`, and dependencies (often `BiocManager::install(c("GSVA", "GSEABase"))`).  
2. Read the matrix into a `matrix` with `rownames` = genes, `colnames` = samples.  
3. Load GMT with `GSVA::readGMT(path)` (preferred) or `GSEABase::getGmt(path)` and keep the resulting gene-set object for the parameter constructor.  
4. **`kcdf` choice**  
   - **`"Gaussian"`** when values are **continuous log-scale** expression (typical DepMap / microarray-like processed data).  
   - **`"Poisson"`** only for **non-negative integer counts**; state explicitly why counts were assumed.  
5. Use the **new parameter-object API**. For standard GSVA, construct `param <- gsvaParam(mat, gsets, kcdf = ...)` and then run `es <- gsva(param, verbose = TRUE)`.  
6. If the requested method is **ssGSEA**, **PLAGE**, or **z-score**, use the matching constructor (`ssgseaParam()`, `plageParam()`, or `zscoreParam()`) instead of the old `method=...` style.  
7. Do **not** generate legacy calls such as `gsva(expr = ..., gset.idx.list = ..., method = ...)`; that API is defunct in current GSVA releases.  
8. **Gene overlap**: if many genes in the GMT are missing from the matrix, mention coverage; extremely low overlap makes scores unreliable.

## Outputs (match common MedClaw-style expectations)

1. **`GSVA_E2F_res.csv` (or user-specified name)**  
   - Save the score matrix with clear **rownames = gene set / pathway**, **colnames = sample** (or the transpose if the downstream tool expects it — **state the convention in one sentence**).  
2. **Short biological summary**  
   - Score range across samples; call out **notably high / low** samples if differences are clear.  
3. **Optional HTML report (academic tone)**  
   - After the GSVA CSV and optional figure are produced, use the **`html-report-writer`** skill to assemble the report.  
   - Domain-specific content that must be included: dimensions, `kcdf`, packages/versions if known, method summary, score range, notably high/low samples, interpretation, limitations (gene ID mapping, coverage), reproducibility note, and a small barplot when available.
   - After writing the report, **verify it exists on disk** (for example, `file.exists(...)` in R or `test -f ...` / `ls -l ...` in a follow-up command) before telling the user it was generated.

## If R / GSVA is missing

- Say clearly that GSVA is missing, then offer **exact install commands** (`install.packages("BiocManager")`; `BiocManager::install(c("GSVA", "GSEABase"))`).  
- Only after the user declines or install fails, propose a **fallback** (e.g. `decoupler` / single-sample enrichment in Python) and warn that scores may not match R GSVA bit-for-bit.

## Rules

- Prefer **reading the CSV header and a few rows** before assuming orientation.  
- Do not silently switch `kcdf` without stating the assumption about the data scale.  
- Keep the analysis **reproducible**: fixed seeds where applicable, saved CSV path reported to the user.  
- If both CSV and GMT are large, watch **memory**; subsampling is only with explicit user consent.
- When producing multiple outputs (CSV, plot, HTML), **verify each expected artifact exists** before concluding success. If the HTML/report step fails, report that clearly instead of claiming the full workflow completed.
