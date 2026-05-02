# differential-expression-deseq2

Runs **two-group RNA-seq differential expression** from a **raw count matrix** (genes as rows, samples as columns) and **explicit per-sample group labels**, using **Bioconductor `DESeq2`**; filters significant genes by **adjusted p-value** and **log2 fold change**; exports **CSV results** (filtered as the primary deliverable, optional full table) plus a **short HTML report** (written in **Python**, not R) with methods, counts of significant genes, and **one figure** (volcano or MA plot). Use when the user asks for **DESeq2**, **RNA-seq DE**, **differential expression**, **count-based DE**, **Wald test / LRT**-style two-group comparison on **raw counts**, or **padj / log2FC** filtering on bulk RNA-seq.

## When to use

- User mentions **DESeq2**, **differential expression**, **RNA-seq counts**, **DE / DEG**, **two-group comparison**, **contrast**, **Wald test**, or **normalized counts** (`counts(dds, normalized=TRUE)` / **VST** / **rlog**).
- Input is a **gene × sample count matrix** (integers or numeric counts suitable for `DESeq2`) and a **sample-to-group mapping** whose **sample IDs match matrix column names** exactly.
- Typical contrasts are named groups (e.g. **treatment vs control**); the skill is written for **exactly two groups** unless the user expands scope.
- **Uploads:** Count and metadata usually arrive as **user-attached files**. The agent should **read whatever paths the runtime provides** (e.g. workspace or attachment handles) — **do not** ask the user for filesystem paths or assume filenames like `data/...csv`. Describe deliverables by **role** (filtered table, HTML report, figure), not by a fixed path.

## Inputs and data checks

1. **Count matrix (CSV or similar)**  
   - Expected layout: **rows = genes** (IDs in the first column or as row names), **columns = samples**.  
   - Peek at headers and a few rows; if the layout is **samples × genes**, **transpose** before `DESeq2`.  
   - Values must be **raw (or appropriately modeled) counts** — not log-TPM alone. If the user only supplies TPM/FPKM, say clearly that **DESeq2 is inappropriate** unless they provide counts or agree to a different method.

2. **Group labels**  
   - A **table or file** mapping **each sample ID** to **one group** (two levels for a simple contrast).  
   - **Column names in the count matrix must match** the sample identifiers in this mapping (after any agreed renaming).  
   - Confirm **balanced or unbalanced design** as given; state **replicates per group** in the report.

3. **Contrast**  
   - Define the comparison in plain language, e.g. **“group A vs group B”**, and map it to `DESeq2`’s **numerator / denominator** (which level is “up” in **log2 fold change**).  
   - Example phrasing for documentation: *log2 fold change represents A relative to B* — align with `results(dds, contrast=...)` or `name`/`coef` usage.

4. **Paths (agent behavior)**  
   - **Do not** tell the user to place files at a specific path or name outputs with a **mandatory** filename; write outputs to the **current task workspace** using names that make sense for the deliverable.  
   - In code, use variables or the paths **injected by the environment** for uploaded inputs — never hard-code example paths from tutorials.

## Method (R / Bioconductor — preferred)

1. **Packages**  
   - Core: **`DESeq2`**. Install if needed, e.g. `BiocManager::install("DESeq2")`.  
   - Add **`ggplot2`**, **`pheatmap`**, or **`EnhancedVolcano`** (or base graphics) **only** for plotting; keep dependencies minimal.

2. **Build `DESeqDataSet`**  
   - `countData`: matrix with **genes × samples**, non-negative.  
   - `colData`: `DataFrame` with sample rows, **group as factor**; set **reference level** explicitly so the contrast direction is unambiguous (`relevel` / `factor(..., levels=...)`).

3. **Run pipeline**  
   - `DESeq(dds)` for standard **size-factor normalization + dispersion + Wald test**.  
   - Retrieve **all genes** with `results(dds, ...)`; use `resultsNames(dds)` / `contrast` to match the requested comparison.  
   - Prefer **`alpha`** consistent with the **adjusted p-value** threshold used for reporting (e.g. **0.05**).

4. **Columns to export (name them clearly in CSV headers)**  
   - At minimum from `results`: **gene id**, **baseMean**, **log2FoldChange**, **lfcSE**, **stat**, **pvalue**, **padj** (BH / FDR as implemented by DESeq2).  
   - **Normalized expression**: e.g. **`counts(dds, normalized=TRUE)`** per gene and sample, or **per-gene summaries** (row means per group) with **clear column names** — state in the report what was exported.

5. **Filter significant genes**  
   - Default rule (unless the user changes it): **`padj < 0.05`** **and** **`|log2FoldChange| > 1`**.  
   - Apply filters **after** obtaining `results`; handle **`NA` padj** (low counts) explicitly (e.g. exclude from “significant” or document).

6. **Figures (pick one for the HTML report)**  
   - **MA plot**: `plotMA` or **ggplot2** equivalent on `results`.  
   - **Volcano**: **-log10(p)** or **padj** vs **log2FC**, with threshold lines.  
   - Save as **PNG** (or SVG) in the task workspace; the **HTML file itself** is generated by **Python** (see Outputs), which can reference that image with a **relative** `<img src="...">` or **base64** embed — **one primary figure** is enough.

## Outputs

1. **Filtered results CSV (main deliverable)**  
   - Rows = genes passing **padj** and **|log2FC|** cutoffs.  
   - Include **statistics** and **normalized expression columns** as chosen above; **column names must be self-explanatory**.

2. **Optional full results CSV**  
   - All genes (or all tested) **before** filtering — useful for review; name it distinctly from the filtered file.

3. **Short HTML report**  
   - After DESeq2 writes CSVs and any plot image, use the **`html-report-writer`** skill to assemble the report.  
   - Domain-specific content that must be included: data dimensions, **contrast** (which group vs which), **DESeq2** workflow, **BH/adjusted p-value** and **|log2FC|** thresholds, number of filtered genes, direction of effect, one primary figure when available, and links/paths to filtered/full CSV outputs.  
   - **Verify** each artifact exists before claiming completion.

## If DESeq2 is missing

- Give **exact install** commands (`install.packages("BiocManager")`; `BiocManager::install("DESeq2")`).  
- Only if install fails or the user refuses, discuss alternatives (**edgeR**, **limma-voom**) and that **results will not match DESeq2**.

## Rules

- **Never** swap **genes × samples** silently — **inspect** dimensions first.  
- **Do not** treat **log-normalized expression** as **counts** without user confirmation.  
- Keep **contrast direction** and **filter rules** **explicit** in code comments and the HTML report (the report document is **Python-generated**).  
- **Reproducibility**: `set.seed()` if any step is stochastic; record **DESeq2** version when practical.  
- **Example group names** (e.g. **Wingless vs Normal**) in a user message are **biological labels**, not file locations — map them to factor levels in `colData`, not to path strings.  
- For the HTML report, delegate the generic report assembly rules to **`html-report-writer`**; this DESeq2 skill only defines the required domain facts.
