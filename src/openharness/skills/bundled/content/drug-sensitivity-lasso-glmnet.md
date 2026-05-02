# drug-sensitivity-lasso-glmnet

Runs cross-validated LASSO (`glmnet`) to predict a continuous drug-sensitivity measure (e.g. GI50, IC50, AUC) from an omics expression matrix after merging sample metadata to cell line IDs and intersecting with drug-response rows; pre-filters genes by variance, exports sparse coefficients and saves the CV fit; optional coefficient plot and short HTML report—use when the user asks for 药敏预测, drug sensitivity prediction, LASSO regression, feature selection, or feature importance for pharmacogenomics.

## When to use

- User mentions **drug sensitivity**, **pharmacogenomics**, **GI50**, **IC50**, **drug response**, **LASSO**, **elastic net**, **glmnet**, **feature importance**, **sparse regression**, or **DepMap / cell line** prediction from expression.
- Inputs include a **gene × sample expression matrix** (or sample × gene, to be transposed), a **model / sample metadata** table that maps samples to **cell line identifiers**, and a **drug-response table** with a **continuous** sensitivity column and cell line IDs overlapping the expression cohort.
- Typical file names (examples only): `OmicsExpressionTPMLogp1HumanProteinCodingGenes.csv`, `Model.csv`, `SCLC_cell_lines.xlsx` (or similar) with GI50-style columns.

## Inputs and data checks

1. **Expression matrix (CSV)**  
   - Default layout: **genes × samples** (first column = gene IDs, remaining columns = samples). If the file is **samples × genes**, **transpose** after confirming headers.  
   - Values are usually **log-scale** (e.g. log TPM+1). Note the scale in the report.

2. **Model / metadata (CSV or similar)**  
   - Must contain a reliable mapping from **expression column names** (sample IDs) to **cell line IDs** used in the drug-response table (e.g. DepMap `ModelID`, CCLE name, or custom IDs).  
   - **Inner join**: keep only samples that have both expression and a matched drug-sensitivity row after merging metadata and drug table. Report **N samples** used and list dropped IDs if informative.

3. **Drug-response table (CSV, TSV, or XLSX)**  
   - Must include **cell line ID** (join key consistent with metadata) and at least one **continuous** sensitivity outcome (e.g. **GI50**, log GI50, IC50, or normalized response).  
   - If multiple drugs or conditions exist, use the column the user specifies or the clearest single endpoint; state the column name in outputs.  
   - Restrict modeling to **cell lines present in both** expression (via metadata) and this table.

4. **Paths**  
   - Web-attached files may appear under `/workspace/uploads/<filename>`. Prefer **relative paths** in scripts and in HTML narrative—**do not** embed machine-specific absolute paths in the written report.

## Method (R — `glmnet` only for modeling)

1. **Packages (minimal)**  
   - Core: **`glmnet`** for `cv.glmnet`; **`Matrix`** if needed for sparse inputs.  
   - I/O: base R `read.csv` / `utils::read.table`; for **Excel**, `readxl::read_xlsx()` is acceptable if the user supplies `.xlsx` (e.g. `SCLC_cell_lines.xlsx`); otherwise ask for CSV export.  
   - Do **not** add tidyverse or extra ML stacks unless the user requires them.

2. **Merge workflow**  
   - Parse expression → `matrix` with `rownames` = genes, `colnames` = samples.  
   - Join metadata to attach **cell line ID** per sample; align drug-response rows by cell line ID.  
   - Subset expression columns to **samples** that survive the merge and have non-missing sensitivity.

3. **Variance filter**  
   - Compute **per-gene variance** across retained samples; sort descending and keep the **top 200** genes (or user-specified *K*). Document *K* in the report.

4. **Regression setup**  
   - **Outcome**: continuous sensitivity vector **y** aligned to sample order of **X** (samples × genes after transpose if needed: `glmnet` expects **x** as **n × p** matrix).  
   - **Family**: **`gaussian`** for continuous drug response.  
   - **`standardize = TRUE`** in `cv.glmnet` (predictors standardized inside `glmnet` as usual).  
   - **`alpha = 1`** for **LASSO** (pure L1); only use elastic net if the user asks.  
   - **Cross-validation**: `cv.glmnet(..., nfolds = ...)` — use a **small fold count** when **n** is small (e.g. 3–5); state `nfolds` and sample size.  
   - **`set.seed(<fixed>)`** before fitting; record the seed in the report and script comments.

5. **Lambda and fit**  
   - Select **λ at minimum cross-validated error** (e.g. `cv_fit$lambda.min` from `cv.glmnet`). Report this value explicitly.  
   - Refit or extract **coefficients at `lambda.min`**; count **non-zero** predictors (excluding intercept if present).

6. **Exports**  
   - **Coefficients table**: non-zero coefficients **sorted by absolute value** (descending); columns should include gene/feature name, coefficient, and optionally sign. Default filename: **`feature_imp_drug_sensitivity_res.csv`** (or user-specified).  
   - **Workspace**: `save(cv_fit, file = "<name>.RData")` (or `.rda`) containing the **`cv.glmnet`** object (and optionally a small `list` with `lambda.min`, seed, gene list if the user wants full reproducibility in one file).

7. **Optional figure**  
   - Barplot or similar of **top features by |coefficient|** at `lambda.min`. Save as **`drug_sensitivity_lasso_importance.png`** (or user-specified) **in the same folder** as the HTML report so the report can reference it with a **same-directory relative** name only.

## Outputs (match common expectations)

1. **`feature_imp_drug_sensitivity_res.csv`** (default) — non-zero LASSO coefficients ranked by |β|.  
2. **Best λ** — numeric value at minimum CV error (`lambda.min`); also mention **how many** non-zero features at that λ.  
3. **`<basename>.RData`** — saved **`cv.glmnet`** object (binary workspace).  
4. **Optional** — importance PNG next to the report.  
5. **Short HTML report** — see below.

## HTML report (short, reproducible)

Use the **`html-report-writer`** skill after the coefficient CSV, RData, and optional PNG are produced.

Domain-specific content that must be included: dimensions after merge, *N* samples, *K* genes after variance filter, outcome column name, LASSO Gaussian method, CV folds, seed, standardization, λ at minimum CV error, number of surviving features, main predictive genes from the coefficient table, limitations (small *n*, cell line-specific findings, extrapolation), and package versions if easily available.

- **Embed the optional importance figure** using **only** a **relative** same-folder reference (e.g. `<img src="drug_sensitivity_lasso_importance.png" ...>`) or **inline base64** if the user prefers a single portable HTML—**never** put absolute filesystem paths in the narrative body.

- **Verify** that the HTML, CSV, RData, and any PNG **exist on disk** before claiming success.

## Rules

- **Survival analysis is a different workflow**; if the user asks for KM/Cox, use the survival signature skill instead. This skill is for **continuous drug-sensitivity** outcomes.  
- Always **state** the outcome column and unit (e.g. log GI50) when known.  
- Do not silently change **fold count**, **seed**, or **K** without noting it in outputs.  
- If **samples are fewer than folds**, reduce folds or error clearly.  
- If **`glmnet` is missing**, give exact install: `install.packages("glmnet")` (and `readxl` only if Excel is required).
