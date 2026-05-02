# gene-clinical-correlation

Runs genome-wide **Pearson** and **Spearman** correlations between a **genes × samples** expression matrix and one or more **continuous** clinical variables (e.g. survival time `OS.time`), with **FDR (Benjamini–Hochberg)** correction per testing family; optionally reports associations with a **binary** event column (e.g. `OS`) in a **separate** table and FDR pass; produces full results tables, a significant-pairs list, correlation heatmap and/or scatterplot(s), and a short HTML summary. Use when the user asks for **correlation analysis**, **Pearson**, **Spearman**, **variable association**, **gene–clinical correlation**, **expression vs outcome**, **TCGA-style** screens, or **FDR-adjusted** multiple testing for many genes.

## When to use

- User mentions **correlation**, **Pearson**, **Spearman**, **gene–clinical association**, **expression vs phenotype**, **variable association**, **FDR**, **q value**, or **multiple testing** for many genes vs one or more clinical columns.
- Inputs are a **genes × samples** expression matrix (columns = sample IDs) plus a clinical / outcome table whose **sample IDs match** expression column names, with at least one **continuous** column to correlate (e.g. **`OS.time`**, lab values, scores).
- Survival-style tables: treat **time** (`OS.time` or similar) as the **primary continuous target** for the main gene-wise screen; treat **event / censoring** (`OS`, etc.) as **context** unless the user explicitly requests a separate binary correlation analysis.
- User expects a **results table** (coefficient, P, FDR, **n**), a **significant pairs** extract, **figures**, and optionally an **HTML** report.

## Inputs and data checks

1. **Expression matrix (File A — e.g. `TCGA_CRC_gene_expression.txt`)**  
   - Layout: **rows = genes**, **columns = sample IDs** (header row).  
   - Peek at dimensions and corners; if the file is **samples × genes**, **transpose** before analysis.  
   - Note value scale (log TPM/FPKM vs raw counts) in the report if it affects interpretation; correlation is still mathematically defined, but mention sparsity or extreme skew if visible.

2. **Clinical / OS table (File B — e.g. `TCGA_CRC_OS.csv`)**  
   - Must include a **sample ID** key that aligns with expression **column names** (rownames or a column such as `barcode`, `sample`, `patient_id` — use the column the user names or the one that matches after inspection).  
   - **Continuous variable(s)** for the main analysis: e.g. **`OS.time`** (and any other requested continuous columns).  
   - **Event / censoring column** (e.g. **`OS`**, 0/1): use for **descriptive context** (event rates, censoring) and, if requested, for a **separate** gene–binary correlation block — **do not** merge binary and continuous tests into **one** FDR family.

3. **Sample intersection**  
   - **Inner-join** expression samples with clinical rows on sample ID; report **effective n** used and list or count **dropped** samples.  
   - Per gene–variable pair, **n** = number of samples with **non-missing** expression and non-missing clinical value (usually constant across genes if expression is complete; document if gene-specific missingness exists).

4. **Paths**  
   - Use **relative paths everywhere** in scripts (e.g. `./TCGA_CRC_gene_expression.txt`, `./TCGA_CRC_OS.csv`, or `./data/...`).  
   - Web-attached files may appear under `/workspace/uploads/<filename>`; keep paths consistent with the execution environment.

## Method

1. **Read and align data**  
   - Build a numeric expression matrix \(G\) (genes × samples) and a clinical frame indexed by sample ID; restrict to **intersecting samples** in a documented order.

2. **Primary analysis: gene × continuous variable(s)**  
   - For **each gene** and **each continuous clinical column** (e.g. `OS.time`): compute **Pearson r** and **Spearman ρ** (and two-sided **P values**) usingcomplete-case pairs for that gene.  
   - **FDR**: apply **Benjamini–Hochberg** (`p.adjust(..., method = "BH")`) **separately** for each combination of *(variable, correlation type)* you report as a discovery family — e.g. one FDR pass over all genes for **Pearson vs OS.time**, and a **separate** pass for **Spearman vs OS.time**. State exactly which vectors of P values were adjusted.

3. **Optional: gene × binary event (e.g. `OS`)**  
   - If the user wants gene–**binary** associations: use **point-biserial** correlation (equivalent to Pearson when the binary is 0/1) or explicitly label it as such; report in a **separate table**.  
   - Apply FDR **only within that binary family** (again, separate passes for Pearson vs Spearman if both are reported). **Never** pool binary and continuous gene-level P values into a single FDR adjustment.

4. **Implementation notes**  
   - **R**: `cor.test(..., method = "pearson" | "spearman")` per gene is simple; for large matrices consider vectorized approaches, `psych::corr.test`, or chunked `apply` with explicit NA handling — always match the user’s **n** definition.  
   - **Python**: `scipy.stats.pearsonr` / `spearmanr` per gene, or equivalent; **`pingoui`** / **pandas** helpers are acceptable if dependencies are OK.  
   - Record **software and key package versions** in the HTML or a log line when practical.

## Outputs

1. **Results table(s) (CSV)**  
   - For each **gene–variable pair** and each method: **coefficient** (r or ρ), **P value**, **FDR (q)**, **n**.  
   - Use clear filenames, e.g. separate files for Pearson vs Spearman if that aids clarity, or one long table with a `method` column — **as long as FDR columns are labeled** to show which family was adjusted.

2. **Significant-pairs list**  
   - Rows with **q** below a stated threshold (e.g. **q < 0.05**), with the same columns as the main table; optionally **ranked** by |coefficient| or by q.

3. **Figures**  
   - At least **one** of: **correlation heatmap** (e.g. top genes × one or more variables, or clustered subset) and/or **scatterplot(s)** for the **strongest** or **representative** gene–variable pairs.  
   - Save as PNG/PDF **next to the script** using **relative paths** in code.

4. **HTML summary**  
   - Use the **`html-report-writer`** skill after result tables and figures are produced.  
   - Domain-specific content that must be included: inputs (files, dimensions), sample matching (N before/after, drops), methods (Pearson/Spearman, FDR scheme, separate families for binary vs continuous), top hits, direction of association, caveats (observational, skewed time, many tests), and embedded figures when available.  
   - **Verify** the files exist before linking.

## If core tools are missing

- State what is missing and give **exact install** commands (e.g. R CRAN packages or `pip install scipy pandas ...`).  
- Prefer a minimal stack: **base R** + `stats` is enough for `cor.test` and `p.adjust`; avoid extra packages unless speed or clarity requires them.

## Rules

- **Relative paths only** inside scripts and in HTML references (no absolute paths to the user’s machine).  
- **Declare FDR families** explicitly; **never** mix continuous and binary gene-level P values in one BH pass.  
- Report **effective n** per gene–pair (or document global n if identical for all genes).  
- **Verify artifacts** exist (CSV, figures, HTML) before claiming completion.  
- Keep the write-up **reproducible**: saved tables, fixed random seeds only if needed, versions when possible.
