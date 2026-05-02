---
name: coexpression-network-wgcna
description: Runs WGCNA co-expression network analysis from an expression matrix plus clinical traits to identify modules, module eigengenes, module-trait correlations, and gene significance. Use when the user mentions WGCNA, weighted gene co-expression network analysis, module-trait correlation, module eigengenes, soft thresholding, TOM, or academic HTML reports for co-expression analysis.
---

# coexpression-network-wgcna

Runs weighted gene co-expression network analysis in R from an expression matrix plus clinical traits; use when the user asks for WGCNA, co-expression modules, module eigengenes, module-trait correlation heatmaps, or gene significance analysis with an academic HTML report.

## When to use

- User mentions **WGCNA**, **weighted gene co-expression network analysis**, **co-expression modules**, **module eigengenes**, **module-trait correlation**, **soft threshold power**, **TOM**, or **gene significance**.
- Inputs include a **gene-by-sample expression matrix** and a **sample trait / clinical table** with shared sample IDs.
- The user wants standard WGCNA outputs such as module colors, eigengenes, module-trait correlations, correlation heatmaps, or gene significance tables.

## Expected inputs

1. **Expression matrix (CSV/TSV)**
   - Read the header and a few rows first to confirm orientation.
   - Common layout for this workflow:
     - rows = genes / probes
     - first 8 columns = annotation
     - expression values start at column 9
     - probe IDs live in `substanceBXH`
   - Strip annotation columns before analysis.
   - Transpose so that **samples are rows** and **genes are columns** for WGCNA.
   - Use the probe ID column as gene identifiers unless the user explicitly asks for gene symbols instead.
   - Ensure column names are unique with `make.unique()` if duplicated probe IDs are present.

2. **Clinical / trait table**
   - Confirm the sample ID column from the actual file header; a common layout for this workflow uses `Mice`.
   - Drop comment / note columns only if they are truly the requested non-analytic columns. For the reference mouse liver workflow, this means **columns 16 and 31** after verifying the table width matches expectations.
   - Keep only **continuous numeric traits** for module-trait correlation unless the user asks for categorical recoding.

3. **Paths**
   - Web-attached files appear as `/workspace/uploads/<filename>` after injection.
   - Do not copy large input files unless the user asks.

## Analysis workflow

### 1. Data inspection and QC

1. Only peek at the header and first few rows of the expression file. Do not print the full matrix into chat.
2. Build `datExpr` as a numeric matrix / data frame with:
   - rows = samples
   - columns = genes / probes
3. Run `goodSamplesGenes(datExpr, verbose = 3)` and remove failed samples / genes if needed.
4. Cluster samples with `flashClust::flashClust(dist(datExpr), method = "average")`.
5. Plot the sample dendrogram and mark the outlier cut line at **height = 15**.
6. If clear outliers fall outside the main cluster at that cut height, remove them and report which sample IDs were excluded. Do not silently remove samples without documenting it.

### 2. Network construction and module detection

1. Use **R** with the `WGCNA` and `flashClust` packages.
2. Prefer a **single self-contained `WGCNA.R` script** that performs the full workflow end to end.
3. If the user already specified the soft-thresholding power, use that value directly. For the reference mouse liver workflow, **power = 6**.
4. Construct:
   - adjacency matrix via `adjacency(datExpr, power = 6, type = "unsigned" or project-appropriate default)`
   - TOM via `TOMsimilarity(adjacency)`
   - dissimilarity via `1 - TOM`
5. Cluster genes from `dissTOM`.
6. Run dynamic tree cutting with:
   - `deepSplit = 2`
   - `minClusterSize = 30`
7. Convert module labels to colors with `labels2colors()`.
8. Preserve the exact parameter values in the script and final report; do not silently swap in `blockwiseModules()` with different defaults unless memory constraints force it, and if so, state that clearly.

### 3. Module eigengenes

1. Compute module eigengenes with `moduleEigengenes(datExpr, colors = moduleColors)$eigengenes`.
2. Reorder with `orderMEs()` before downstream correlation.
3. Save the result to **`Module_Eigengene_Res.csv`**.
4. Include sample IDs as the first column or row names and make the saved orientation explicit in one sentence.

### 4. Module-trait correlation

1. Read the trait table and remove the requested comment / note columns after verifying the layout.
2. Keep only numeric continuous traits for correlation.
3. Match samples between expression and trait tables using the shared mouse IDs.
4. Reorder both matrices so their sample order is identical before correlation.
5. Compute Pearson correlations between module eigengenes and traits:
   - `moduleTraitCor <- cor(MEs, datTraits, use = "p")`
   - `moduleTraitPvalue <- corPvalueStudent(moduleTraitCor, nSamples)`
6. Create a labeled heatmap with:
   - `blueWhiteRed(50)` color palette
   - text labels showing both correlation and p-value
7. Save:
   - **`module.trait.correlation.png`**
   - **`module.trait.correlation_res.csv`**
8. The CSV should contain the numeric module-trait correlation matrix. Keep p-values available in the script for labels and report text; if the user explicitly asks, an additional p-value CSV can be saved too.

### 5. Gene significance

1. Use the trait of interest specified by the user. For the reference workflow, use **`weight_g`**.
2. Compute gene significance against that trait with Pearson correlation.
3. Compute module membership for each gene against the eigengenes.
4. Save **`gene_significance_res.csv`** with enough columns to be useful downstream. Prefer:
   - probe / gene ID
   - module color
   - gene significance
   - gene significance p-value
   - module membership
   - module membership p-value
5. If `weight_g` is absent, stop and report that the required trait column was not found rather than substituting another trait.

## Required script behavior

- Write a single `WGCNA.R` script that:
  - loads packages
  - reads both input files
  - performs QC
  - detects modules
  - computes eigengenes
  - computes module-trait correlations
  - computes gene significance
  - writes all requested CSV / PNG outputs
  - generates the HTML report
- Use explicit output filenames unless the user requests alternatives:
  - `Module_Eigengene_Res.csv`
  - `module.trait.correlation_res.csv`
  - `module.trait.correlation.png`
  - `gene_significance_res.csv`
  - `report.html`
- Fix a random seed anywhere stochastic behavior appears.

## HTML report

When the user asks for a report, use the **`html-report-writer`** skill to generate **`report.html`**.

Domain-specific content that must be included:

- expression and trait file names
- matrix dimensions before and after QC
- whether any outlier samples were removed at cut height 15
- core parameters: soft power, deepSplit, minClusterSize
- the trait used for gene significance (`weight_g` in the reference workflow)
- the generated output file names

Embed figures inline when available, especially:

- sample clustering / QC dendrogram if generated
- module-trait heatmap

After writing the report, verify that `report.html` exists before claiming success.

## Language and package preference

- Use **R** by default.
- Use the **`WGCNA`** and **`flashClust`** packages as requested.
- Add install guidance only if the packages are missing; do not silently switch to Python substitutes for a requested WGCNA workflow.

## Rules

- **Token budget**: expression matrices and trait tables can be large. Never print full tables or matrices in the conversation.
- **Read first, then assume**: inspect headers before assuming exact column names, orientation, or whether columns 16 and 31 are still the note fields.
- **Reproducibility**: keep all critical parameters explicit in the script and report.
- **Sample matching**: do not correlate unmatched or differently ordered samples.
- **No silent parameter drift**: keep `power = 6`, `deepSplit = 2`, `minClusterSize = 30`, and QC cut height `15` when those are the requested settings.
- **Artifact verification**: when producing multiple outputs, verify that each expected CSV / PNG / HTML file exists before reporting completion.
- **Failure handling**: if package installation, sample matching, or required trait lookup fails, report the exact blocking issue instead of claiming the workflow completed.
