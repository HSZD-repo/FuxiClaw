# subtype-clustering

Runs unsupervised clustering on a gene-by-sample expression matrix to identify potential sample subtypes; use when the user mentions subtype clustering, subtype identification, unsupervised clustering, sample classification, consensus clustering, or asks for subtype labels, clustering heatmaps, PCA/UMAP plots, or an academic HTML report of clustering results.

## When to use

- User mentions **subtype clustering**, **subtype identification**, **unsupervised clustering**, **sample classification**, **consensus clustering**, **NMF clustering**, or **k-means / hierarchical clustering on expression data**.
- Inputs include a **CSV/TSV expression matrix** (typically genes × samples) and optionally a **sample metadata table** (clinical annotations, grouping info).
- User wants **subtype labels per sample**, **cluster visualizations**, or **optimal cluster number selection**.

## Expected inputs

1. **Expression matrix (CSV/TSV)**
   - Default layout: **first column = gene identifiers**, **remaining columns = samples**.
   - Peek at the first rows/columns; if the layout is **samples × genes**, transpose before analysis.
   - Values are usually **log-normalized** (log TPM/CPM/RPKM). If raw counts are detected (all non-negative integers), apply log2(x + 1) transformation and state the assumption.

2. **Sample metadata (optional)**
   - A table mapping sample IDs to clinical variables (e.g., stage, treatment, known subtypes).
   - Used for annotation on heatmaps and for post-hoc comparison with discovered clusters.

3. **Paths**
   - Web-attached files appear as `/workspace/uploads/<filename>` (see system prompt). Do not copy them elsewhere unless the user asks.

## Analysis workflow

### 1. Data inspection and preprocessing

1. **Only peek** at the first 5–10 rows of the CSV to confirm orientation (genes × samples vs. samples × genes) and value range. **Never read or print the full matrix into the conversation**—this will exceed token limits for any real dataset.
2. **Write a single self-contained Python (or R) script** that performs all subsequent steps (loading, preprocessing, clustering, saving outputs) in one execution. Do not load data interactively row-by-row in chat.
3. Report **data dimensions** (number of genes, number of samples).
4. **Filter low-variance genes**: remove genes with near-zero variance across samples (e.g., bottom 25 % by MAD or variance). State the threshold used.
5. **Normalize / scale**: z-score standardize genes (row-wise) so that each gene has mean 0 and SD 1 across samples, unless data is already scaled.
6. **Handle missing values**: if NAs are present, report the fraction and either impute (median per gene) or drop, stating the choice.

### 2. Dimensionality reduction (for visualization)

1. Run **PCA** on the preprocessed matrix; retain top components explaining ≥ 80 % cumulative variance or the first 10 PCs, whichever is fewer.
2. Run **UMAP** (or t-SNE) on the top PCs for 2D visualization. Fix the random seed for reproducibility.
3. These embeddings are for visualization; clustering should operate on the filtered, scaled expression matrix or the top PCs, not the 2D embedding.

### 3. Clustering

Use **one primary method** plus a validation approach:

- **Primary — Consensus clustering** (preferred when feasible):
  - Use `ConsensusClusterPlus` (R/Bioconductor) or `sklearn.cluster` with repeated subsampling (Python).
  - Test k = 2 through k = 8 (or user-specified range).
  - Select optimal k via **consensus CDF delta area plot**, **silhouette score**, or **gap statistic**. State which criterion was used and why.

- **Alternative methods** (acceptable if consensus clustering is unavailable):
  - Hierarchical clustering (Ward's method) with dynamic tree cutting.
  - k-means on top PCs with silhouette-based k selection.
  - NMF (non-negative matrix factorization) if the user specifically requests it.

- **Validation**:
  - Compute **silhouette scores** per sample at the selected k.
  - If silhouette scores are overall low (mean < 0.2), warn the user that cluster separation is weak.

### 4. Subtype assignment

1. Assign each sample a cluster label: `Subtype_1`, `Subtype_2`, …, `Subtype_k` (or user-preferred naming).
2. Report **cluster sizes** (number of samples per subtype).
3. If sample metadata is available, cross-tabulate clusters with known clinical variables and note any enrichment.

### 5. Marker identification (optional but recommended)

1. For each cluster, identify **top differentially expressed genes** (e.g., top 10 by fold change or statistical test).
2. These markers help the user interpret what each subtype represents biologically.

## Required outputs

### Chat summary (concise, no raw data)

Return a short summary covering:

1. **Data dimensions** — genes × samples after filtering.
2. **Preprocessing** — transformations applied (log, z-score, gene filtering).
3. **Clustering method** — algorithm and parameters used.
4. **Selected cluster number** — k and the criterion for selection.
5. **Cluster sizes** — number of samples per subtype.
6. **Brief interpretation** — any notable patterns (e.g., clear separation in PCA, alignment with known subtypes).
7. **Limitations** — sample size, gene coverage, stability caveats.

Do **not** print raw data tables, large matrices, or long intermediate outputs in the chat.

### Saved files

1. **Sample-to-subtype assignment table**
   - Save as CSV (e.g., `sclc_subtype_assignments.csv` or a name matching the user's data).
   - Columns: `sample_id`, `subtype`, and optionally `silhouette_score`.

2. **Academic HTML report** (`subtype_clustering_report.html` or user-specified name)
   - After assignments, plots, and summaries are produced, use the **`html-report-writer`** skill to assemble the report.  
   - Domain-specific content that must be included: source file, dimensions, preprocessing steps, packages/versions, clustering algorithm, k selection criterion, dimensionality reduction, random seed, cluster sizes table, PCA/UMAP scatter plot when available, heatmap or silhouette summary when available, biological/clinical interpretation, limitations, and links/paths to saved outputs.  
   - After writing the report, **verify it exists on disk** before telling the user it was generated.

## Language preference

- **Python (scikit-learn + scanpy/matplotlib)** is the default for this skill unless the user requests R.
- **R (ConsensusClusterPlus)** is preferred when the user specifically asks for consensus clustering or when that package is already available.
- State which language/packages were used.

## Rules

- **Token budget**: Expression matrices are large. **Never** `cat`, `print()`, or read an entire matrix file into the conversation context. Only peek at the header + a few rows to confirm format, then process everything inside a script. Intermediate results (DataFrames, arrays) must stay inside the script, not be echoed to chat.
- **Single-script execution**: Combine all steps (load → preprocess → cluster → save CSV → generate HTML) into **one script** run in a single shell command. Avoid multi-turn interactive data exploration that accumulates large outputs in the conversation.
- Prefer **reading the CSV header and a few rows** before assuming orientation.
- Do not silently switch preprocessing without stating the assumption about data scale.
- Keep the analysis **reproducible**: fixed random seeds everywhere, saved CSV path reported to the user.
- If both the matrix and metadata are large, watch **memory**; subsampling only with explicit user consent.
- When producing multiple outputs (CSV, plot, HTML), **verify each expected artifact exists** before concluding success. If any step fails, report that clearly instead of claiming the full workflow completed.
- Do not overstate biological conclusions from unsupervised clustering alone; always note that subtypes need independent validation.
