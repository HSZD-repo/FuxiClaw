---
name: immune-deconvolution-cibersort
description: Runs immune microenvironment deconvolution with a fixed LM22-style reference signature using a standard CIBERSORT workflow in R—gene alignment, recommended preprocessing, per-sample cell fractions plus P-value/correlation/RMSE, one combined CSV, a simple composition figure, and a short HTML narrative assembled via html-report-writer. Unless necessary, do not feed whole-file contents to the model; summarize to save tokens. For compressed uploads, after decompressing never show more than five text lines to the model; otherwise parse-only. Use for CIBERSORT, immune infiltration, tumor microenvironment cell composition, or bulk RNA-seq/microarray immune-cell proportions.
---

# immune-deconvolution-cibersort

Runs **immune microenvironment deconvolution** from a **bulk gene expression matrix** (microarray or RNA-seq) using a **standard CIBERSORT-style workflow** with a **fixed reference signature matrix** (typically **LM22**); aligns gene identifiers with the signature; applies **method-appropriate preprocessing**; exports **per-sample immune cell fractions** and **quality metrics** (**P-value**, **correlation**, **RMSE**) in **one combined table**; saves a **simple cell-composition figure** for comparing infiltration across samples; then builds a **short HTML summary via `html-report-writer`**. Use when the user asks for **immune deconvolution**, **CIBERSORT**, **tumor microenvironment cell composition**, **immune infiltration**, **LM22**, or **bulk-based immune fractions**.

## When to use

- User mentions **CIBERSORT**, **immune deconvolution**, **immune infiltration**, **tumor microenvironment (TME)**, **immune cell fractions**, **LM22**, or **bulk deconvolution** (not single-cell annotation).
- Input is a **gene × sample** (or **probe × sample**) expression table supplied as a **user upload** (format is whatever the UI or session attaches—matrix / table / compressed text).
- Deliverables include **sample-level fractions**, **QC columns** (P-value, correlation, RMSE), **one CSV**, **one composition plot**, and optionally **minimal HTML** written **after** R completes.

## Inputs and data checks

1. **Expression matrix**  
   - Inspect orientation: **genes (or probes) × samples** is typical for deconvolution; if **samples × features**, **transpose**.  
   - Identify **ID type**: **gene symbols**, **Ensembl**, or **microarray probe IDs** (e.g. **Affymetrix** `1xxxx_at`).  
   - **Microarray / probes**: map **probe → gene symbol** before matching the signature (e.g. **`AnnotationDbi::mapIds`** with a platform package such as **`hgu133plus2.db`**, **`hgu133a.db`**, etc., chosen from the dataset platform; or **`biomaRt`**). **Collapse duplicate symbols** with a documented rule (**median**, **max variance**, or **mean**) so each gene appears once.  
   - **RNA-seq**: prefer **TPM** or **CPM/log-CPM** consistently with the chosen implementation’s docs; **raw counts** usually need transformation—state the assumption explicitly.

2. **Reference signature matrix**  
   - Use a **fixed** LM22-style matrix (**genes × cell types**) from the **official CIBERSORT distribution** or a matrix the **user supplies in the same session**; **do not** silently substitute a different signature without stating it.  
   - **Intersect** genes between mixture and signature; report **overlap count** and warn if coverage is poor.

3. **Paths and filenames (agent behavior)**  
   - **Inputs are uploads**: the agent must use the **paths or handles that the runtime injects** after attachment—**never** ask the user for a filesystem path, **never** bake in tutorial or GEO example filenames, and **never** assume a fixed name for the expression table.  
   - **Outputs**: write artifacts to the **current task workspace** using **names that describe the role** (combined results table, composition figure, HTML). **No prescribed filenames**—pick sensible names locally and refer to those same names when embedding the figure in HTML.

4. **Large files, GEO SOFT headers, compressed uploads, and context limits (avoid model / API token errors)**  
   - **Unless strictly necessary**, **do not** pass **entire file contents** through tool output or into the assistant / model—**parse and summarize offline** (dimensions, types, paths, a few IDs) and **keep token usage minimal**.  
   - GEO **series matrix** and other SOFT-family files often start with **very long** `!Series_*` / `!Sample_*` metadata. **Even one extremely long line** (e.g. summary / contributor lists) can dominate the tool transcript and **push the chat over provider context limits** (failure looks like “exceeded model token limit”).  
   - **Never** stream or `print` large slices of these files into bash/Python tool output (e.g. **avoid “first 100–150 lines”** as a default peek).  
   - **Compressed uploads** (e.g. **`.gz`**, **`.bz2`**, **`.xz`**, or text inside **`.zip`** / **`.tar.*`**): after you **decompress or open** the archive and read the **inner file as text**, you may expose to the tool transcript / assistant / model **at most five (5) lines** of that decoded content—**count lines, not bytes**; **do not** substitute a larger byte window to “sneak in” more content. Anything beyond analysis should be **parsed in code** with **no** raw dump, or written to disk and only **summarized** (dimensions, types, paths).  
   - **Same 5-line ceiling** applies to **any** deliberate **raw text preview** of an upload (including **uncompressed** SOFT/CSV) if you must peek—**prefer zero lines** and **parse first**.  
   - **Default for GEO SOFT / series_matrix** (often delivered as **`.txt.gz`**): **do not** print raw inner text—**parse in R or Python first**, then report only dimensions and IDs (see below). The **5-line rule** is an **absolute cap** when any preview is used.  
   - **Prefer parsing over peeking**: load the matrix in **R** or **Python** (skip/jump to the numeric table per format docs), then echo only a **tiny summary** back to the user: **dimensions** (genes × samples), **identifier type**, **first few row/column names**, **file path**—not the full header.  
   - For one-off metadata, use **narrow** extraction (e.g. lines matching **`^!Series_title`** / **`^!Series_geo_accession`**) rather than dumping **`!Series_summary`** or contributor blocks; **each** such line still counts toward **safety**—prefer **no** bulk title+summary printing.  
   - **Intermediate matrices** (full expression table): **write to disk** in the workspace; **do not** `cat` or paste them into tool results or assistant-visible logs.

## Method (R — CIBERSORT-style; add packages only as needed)

1. **Implementation choice (must include QC metrics)**  
   - **Primary**: Stanford **CIBERSORT** reference bundle (**reference script + LM22 signature matrix** from the official distribution) so outputs include **fractions** and **P-value**, **Correlation**, **RMSE** per sample as in the original workflow—load these from wherever the session provides them after download or attach, not from an assumed repo path.  
   - If using a wrapper (e.g. **`immunedeconv`**), **verify** the returned table includes **all required QC fields**; if not, **fall back** to the official script/method that does.  
   - Install only what is required (commonly **`e1071`** for SVM pieces, plus utilities for I/O); use **`BiocManager::install`** / **`install.packages`** as appropriate.

2. **Gene alignment**  
   - Restrict mixture and signature to the **same gene identifier space** (symbols as used in **LM22**).  
   - Sort rows to match the signature; drop genes absent from either side **symmetrically** after mapping.

3. **Preprocessing**  
   - Follow **CIBERSORT / LM22** guidance for the mixture file: scaling consistent with the signature (often **non-negative**, **no log applied twice**—if data are already **log2**, avoid duplicate logging).  
   - Optional steps (e.g. **quantile normalization**) should match the **referenced protocol** for the matrix type (array vs-seq); **document** every transform in one sentence for the HTML summary.

4. **Run deconvolution**  
   - Use sufficient **permutations** for meaningful **P-values** when the implementation supports it (e.g. **`perm`**); state **`perm`** in documentation.  
   - Collect **cell-type fraction columns**, **`P-value`**, **`Correlation`**, **`RMSE`** (exact column names may vary slightly—normalize names in the exported CSV header for clarity).

5. **Figure (simple composition plot)**  
   - One clear plot: **stacked bar** of fractions per sample, or **heatmap** of cell × sample proportions—**`ggplot2`** or base graphics; save **PNG** (or SVG) **next to** the other deliverables in the task workspace. **Keep the design minimal** and readable for many samples (rotate labels, facet, or restrict to top cell types only if the user agrees when *p* is huge).

## Outputs

1. **Combined results table (primary deliverable)**  
   - **One** CSV table with **one row per sample**: all **immune cell fraction** columns **plus** **P-value**, **Correlation**, and **RMSE** (and **Sample** / identifier column). Save under any clear name in the workspace; this table is what **Python reads** for the HTML narrative.

2. **Cell-composition figure**  
   - One raster or vector image saved in the workspace; the HTML references it **by the same basename** you actually wrote (relative `src`) or embeds via base64.

3. **Short HTML document**  
   - After R writes the combined CSV and composition figure, use the **`html-report-writer`** skill to assemble the report.  
   - Domain-specific content that must be included: workflow overview (mapping, preprocessing, permutation count), main takeaways from the table (dominant subsets/cell types, weak-fit samples if **Correlation**/**RMSE** indicate trouble), embedded figure, and reproducibility notes including package versions, **`perm`**, and gene overlap *n* when available.  
   - **Verify** CSV, PNG, and HTML exist on disk before claiming completion.

## If packages or reference files are missing

- Give **exact install** commands for required R packages.  
- For the **LM22 signature** and **reference CIBERSORT implementation**, explain **official acquisition** (license / academic-use constraints) or use a copy **attached in the session**—**do not** invent proprietary files or assume they already exist on disk without checking.

## Rules

- **Unless strictly necessary**, **never** expose **whole uploaded files** to the model—**prefer terse summaries** so **tokens stay low** (full dumps break context limits and slow the run).  
- **Probe IDs must become symbols** (or the same ID type as LM22) **before** alignment—many pipelines fail silently otherwise.  
- Prefer **one combined CSV** with **fractions + QC metrics**; avoid splitting metrics into separate files unless the user asks.  
- **Reproducibility**: include **session-tight** notes in the HTML (packages/versions when available, **`perm`**, gene overlap *n*).  
- For the HTML report, delegate the generic report assembly rules to **`html-report-writer`**; this immune deconvolution skill only defines the required domain facts.  
- **Paths**: follow the **“Paths and filenames (agent behavior)”** section above—uploads define inputs; outputs use **role-based names**, not fixed tutorial filenames.  
- **GEO / SOFT / compressed uploads / huge headers**: follow **subsection 4** above—**compressed files: ≤5 lines** of inner decoded text may ever be shown to the model; otherwise **parse and summarize dimensions only** so the run **does not exceed model token limits**.
