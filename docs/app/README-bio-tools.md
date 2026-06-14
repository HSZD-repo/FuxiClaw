# Bioinformatics Tools

This document lists the bioinformatics-oriented capabilities currently available in the MedClaw project.

## Skills

- `druggable-gene-matching`
  - Druggable-gene / drug-target matching workflow guidance
  - Covers candidate genes, DGI-style databases, prioritization, unmatched genes, and academic HTML reporting
- `pathway-activity-gsva`
  - GSVA / pathway activity analysis workflow guidance
  - Covers expression matrix checks, GMT handling, `kcdf` choice, and expected outputs
- `immune-deconvolution-cibersort`
  - CIBERSORT-style bulk immune infiltration workflow guidance (LM22 reference signature)
  - Covers probe → symbol mapping for microarray, gene–signature alignment, preprocessing, fractions plus P-value / correlation / RMSE in one CSV, composition figure from R, **HTML summary written with Python**
- `differential-expression-deseq2`
  - Two-group bulk RNA-seq differential expression with **DESeq2** (raw count matrix + sample groups)
  - Covers contrast direction, `padj` / `|log2FC|` filtering, CSV exports (filtered + optional full), R for analysis and figures; **HTML report written with Python**
- `differential-expression-limma-ebayes`
  - Two-group differential analysis with **`limma`** + **`eBayes`** on continuous gene-level tables (e.g. DependencyScore / log-TPM), including **two-sample vs rest** DepMap-style designs, full CSV with **`dependency_direction`**, optional **`.RData`** workspace, R for fit and optional figure; **HTML summary written with Python**
- `coexpression-network-wgcna`
  - WGCNA / co-expression network analysis workflow guidance
  - Covers QC, module detection, module-trait correlation, gene significance, and academic HTML reporting
- `survival-signature-km-cox`
  - Signature-based survival analysis workflow guidance
  - Covers gene × sample checks, row-scaled signature scores, KM with log-rank, Cox PH, saved `coxph` objects, and optional HTML reporting
- `gene-clinical-correlation`
  - Genome-wide gene–clinical correlation workflow guidance (Pearson and Spearman, BH-FDR)
  - Covers genes × samples vs continuous clinical columns (e.g. `OS.time`), separate FDR families for binary outcomes, results tables, heatmap/scatter figures, and HTML reporting
- `go-enrichment-clusterprofiler`
  - Human GO over-representation (BP / CC / MF) with `clusterProfiler::enrichGO`, `org.Hs.eg.db`, BH adjustment, `pvalueCutoff` / `qvalueCutoff`, three CSV tables, optional figures; **HTML report written with Python** (R for enrichment only)

## Sandbox Tools

- `sandbox_list_envs`
  - List available OpenSandbox environments
- `sandbox_exec`
  - Run commands inside the configured bioinformatics sandbox container
- `sandbox_status`
  - Check status of background sandbox tasks
- `sandbox_cancel`
  - Cancel running sandbox tasks

## Local Plotting Tools

- `heatmap_plot`
  - Draw heatmaps from numeric matrix tables
- `pca_plot`
  - Draw PCA scatter plots from sample-by-feature matrices
- `umap_plot`
  - Draw UMAP scatter plots from sample-by-feature matrices
- `volcano_plot`
  - Draw volcano plots from differential analysis result tables
- `survival_curve`
  - Draw Kaplan-Meier survival curves from clinical tables
- `network_plot`
  - Draw static network plots from edge list tables
- `forest_plot`
  - Draw forest plots from summary result tables
- `expression_boxplot`
  - Draw grouped expression boxplots for one gene / feature
- `enrichment_barplot`
  - Draw horizontal barplots for enriched pathways / terms
- `enrichment_dotplot`
  - Draw dotplots for enriched pathways / terms

## Public Data Query Tools

### DepMap

- `depmap_search_gene`
- `depmap_get_dependency_summary`
- `depmap_search_cell_lines`

### GDC

- `gdc_search_projects`
- `gdc_search_cases`
- `gdc_search_files`

### GTEx

- `gtex_list_tissues`
- `gtex_search_gene`
- `gtex_get_median_expression`

### GDSC

- `gdsc_list_release_files`
- `gdsc_get_release_overview`
- `gdsc_search_compounds_annotation`

### STRING

- `string_search_entity`
- `string_get_network`
- `string_get_enrichment`

## Notes

- Many plotting tools rely on Python scientific plotting libraries such as `matplotlib`, `pandas`, `numpy`, `seaborn`, or `umap-learn`.
- Sandbox-based workflows are recommended when analyses depend on heavy bioinformatics environments or R / Bioconductor packages.
- Tool availability still depends on the runtime path you are using (`oh`, `oh web`, or the Application UI backend) and whether that runtime is wired to the full tool registry.
