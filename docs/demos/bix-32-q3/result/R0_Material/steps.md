# steps.md

## Part 1: Environment Configuration

- Detected working analysis environment: macOS host with `Rscript` available.
- Required packages used successfully: `DESeq2` (autoloaded by the RDS objects), `KEGGREST`, and `base64enc`.
- No blocking dependency gaps were found for this analysis.
- Optional note: `clusterProfiler` was not installed, so KEGG over-representation was implemented directly with KEGG mappings plus a hypergeometric test, which is methodologically appropriate for this task.

## Part 2: Refined Steps

### Step 1 — Stage the inputs
- **Input files:** Original RDS files from the user-provided paths; the natural-language prompt.
- **Execution step:** Create `R0_Input`, `R0_Material`, and `R0_Result`; copy the RDS files into `R0_Input`; save the prompt as `R0_Input/user-prompt.txt`.
- **Output files:** `R0_Input/user-prompt.txt`, `R0_Input/res_1vs97.rds`, `R0_Input/res_1vs98.rds`, `R0_Input/res_1vs99.rds`.

### Step 2 — Inspect the RDS contents
- **Input files:** `R0_Input/res_1vs97.rds`, `R0_Input/res_1vs98.rds`, `R0_Input/res_1vs99.rds`.
- **Execution step:** Read each RDS object in R; confirm class and columns; verify that each file is a gene-level `DESeqResults` table.
- **Output files:** `R0_Material/file_content.md`.

### Step 3 — Filter upregulated genes
- **Input files:** The three RDS files in `R0_Input`.
- **Execution step:** Convert each `DESeqResults` object to a data frame and keep genes with `padj < 0.05` and `log2FoldChange > 1.5`.
- **Output files:** `R0_Material/upregulated_genes_strain97.csv`, `R0_Material/upregulated_genes_strain98.csv`, `R0_Material/upregulated_genes_strain99.csv`.

### Step 4 — Perform KEGG enrichment
- **Input files:** Upregulated gene tables and KEGG PA14 pathway mappings (`organism = pau`).
- **Execution step:** Run over-representation testing for each strain; keep pathways with `pvalue < 0.05` and `BH-adjusted pvalue < 0.05`.
- **Output files:** `R0_Material/kegg_all_strain97.csv`, `R0_Material/kegg_all_strain98.csv`, `R0_Material/kegg_all_strain99.csv`, `R0_Material/kegg_sig_strain97.csv`, `R0_Material/kegg_sig_strain98.csv`, `R0_Material/kegg_sig_strain99.csv`, `R0_Material/kegg_enrichment_summary.csv`.

### Step 5 — Compare strains and extract the exclusive strain-99 signal
- **Input files:** `R0_Material/kegg_sig_strain97.csv`, `R0_Material/kegg_sig_strain98.csv`, `R0_Material/kegg_sig_strain99.csv`.
- **Execution step:** Compare significant pathway names across strains and keep pathways present only in the significant pathway set of strain 99.
- **Output files:** `R0_Material/kegg_exclusive_upregulated_strain99.csv`, `R0_Material/final_answer.md`, `R0_Material/kegg_compare_report.txt`.

### Step 6 — Assemble report and publish results
- **Input files:** Summary tables, exclusive pathway table, and answer file.
- **Execution step:** Generate a plot, embed it into a self-contained HTML report, and copy requested result files into `R0_Result`.
- **Output files:** Self-contained HTML report in `R0_Result`, plus copied CSV/Markdown result files in `R0_Result`.

## Part 3: Results Organization

- Copy the following deliverable files from `R0_Material` to `R0_Result`:
  - `final_answer.md`
  - `kegg_enrichment_summary.csv`
  - `kegg_sig_strain97.csv`
  - `kegg_sig_strain98.csv`
  - `kegg_sig_strain99.csv`
  - `kegg_exclusive_upregulated_strain99.csv`
  - `kegg_compare_report.txt`

## Part 4: Notification

1. Generated self-contained HTML report: `demo_2026-03-31_000751.html` in `R0_Result`.
2. Inform the user: "This round of execution has ended. Please check `demo_2026-03-31_000751.html` file and the results in the `R0_Result` folder."
