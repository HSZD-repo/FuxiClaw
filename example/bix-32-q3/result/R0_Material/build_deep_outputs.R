suppressPackageStartupMessages(library(KEGGREST))
suppressPackageStartupMessages(library(base64enc))

# Load comparison outputs
summary_df <- read.csv('R0_Material/kegg_enrichment_summary.csv', stringsAsFactors = FALSE)
exclusive_99 <- read.csv('R0_Material/kegg_exclusive_upregulated_strain99.csv', stringsAsFactors = FALSE)
sig97 <- read.csv('R0_Material/kegg_sig_strain97.csv', stringsAsFactors = FALSE)
sig98 <- read.csv('R0_Material/kegg_sig_strain98.csv', stringsAsFactors = FALSE)
sig99 <- read.csv('R0_Material/kegg_sig_strain99.csv', stringsAsFactors = FALSE)

# 1) file_content.md
file_content <- c(
  '# file_content.md',
  '',
  'This document summarizes the input files placed in `R0_Input` for the /deep analysis.',
  '',
  '## 1) user-prompt.txt',
  '- **Path:** `R0_Input/user-prompt.txt`',
  '- **Overview:** Natural-language analysis request asking which KEGG functional categories are exclusively upregulated in the double quorum-sensing synthase knockout strain 99 (ΔlasIΔrhlI) compared with the single knockouts 97 and 98, relative to wildtype strain 1. It specifies the DE filtering thresholds (`adjusted p-value < 0.05`, `log2FoldChange > 1.5`) and the KEGG enrichment p-value cutoff (`0.05`).',
  '',
  '## 2) res_1vs97.rds',
  '- **Path:** `R0_Input/res_1vs97.rds`',
  '- **Overview:** R serialized `DESeqResults` object containing differential-expression results for wildtype strain 1 versus strain 97. The object contains 5,828 genes and the standard DESeq2 result columns: `baseMean`, `log2FoldChange`, `lfcSE`, `stat`, `pvalue`, and `padj`.',
  '',
  '## 3) res_1vs98.rds',
  '- **Path:** `R0_Input/res_1vs98.rds`',
  '- **Overview:** R serialized `DESeqResults` object containing differential-expression results for wildtype strain 1 versus strain 98. The object contains 5,828 genes and the standard DESeq2 result columns: `baseMean`, `log2FoldChange`, `lfcSE`, `stat`, `pvalue`, and `padj`.',
  '',
  '## 4) res_1vs99.rds',
  '- **Path:** `R0_Input/res_1vs99.rds`',
  '- **Overview:** R serialized `DESeqResults` object containing differential-expression results for wildtype strain 1 versus strain 99. The object contains 5,828 genes and the standard DESeq2 result columns: `baseMean`, `log2FoldChange`, `lfcSE`, `stat`, `pvalue`, and `padj`.',
  '',
  '## Content-level interpretation',
  '- The three `.rds` files are not precomputed KEGG outputs; they are gene-level DESeq2 result tables.',
  '- Therefore, the required analysis is: (1) identify upregulated genes under the user thresholds for each strain, (2) run KEGG enrichment on each upregulated set, and (3) compare significant pathways across strains to find categories unique to strain 99.'
)
writeLines(file_content, 'R0_Material/file_content.md')

# 2) user_req_deliverables.md
user_req <- c(
  '# user_req_deliverables.md',
  '',
  'Based on the prompt and the input files, the user needs the following deliverables:',
  '',
  '1. **A direct answer** identifying the two KEGG functional categories that are significantly upregulated only in strain 99 (ΔlasIΔrhlI), and not in strains 97 or 98, relative to wildtype strain 1.',
  '2. **A reproducible comparison table** showing, for each strain (97, 98, 99):',
  '   - number of upregulated genes passing the thresholds (`padj < 0.05`, `log2FoldChange > 1.5`)',
  '   - significant KEGG pathways under enrichment thresholds (`pvalue < 0.05`, `BH-adjusted pvalue < 0.05`).',
  '3. **A machine-readable table** listing the KEGG pathways significant only in strain 99 and not in 97 or 98.',
  '4. **An audit trail** documenting how the RDS files were interpreted, how pathway enrichment was performed, and which files were produced.',
  '5. **A self-contained HTML report** summarizing preprocessing, thresholds, enrichment method, comparison logic, and final answer.'
)
writeLines(user_req, 'R0_Material/user_req_deliverables.md')

# 3) execution_plan.md
exec_plan <- c(
  '# execution_plan.md',
  '',
  'To generate the required deliverables, the work is divided into 6 steps:',
  '',
  '1. **Stage the inputs**: create `R0_Input`, `R0_Material`, and `R0_Result`; copy the three RDS files into `R0_Input`; save the user question into `R0_Input/user-prompt.txt`.',
  '2. **Inspect file structure**: open each RDS object and confirm that it is a `DESeqResults` table with gene identifiers and differential-expression statistics.',
  '3. **Filter upregulated genes**: for each strain comparison (1vs97, 1vs98, 1vs99), extract genes with `padj < 0.05` and `log2FoldChange > 1.5`.',
  '4. **Run KEGG enrichment**: map PA14 genes to KEGG pathways (`organism = pau`) and perform over-representation testing on each upregulated gene set; keep pathways with `pvalue < 0.05` and `BH-adjusted pvalue < 0.05`.',
  '5. **Compare pathway sets across strains**: identify pathways significant in strain 99 but absent from the significant pathway lists of strains 97 and 98.',
  '6. **Package outputs**: write summary tables, a concise answer file, process documentation, and a self-contained HTML report; copy requested result files into `R0_Result`.'
)
writeLines(exec_plan, 'R0_Material/execution_plan.md')

# 4) final_answer.md
answer_lines <- c(
  '# final_answer.md',
  '',
  '## Direct answer',
  '',
  'The two KEGG functional categories that are **exclusively upregulated in strain 99 (ΔlasIΔrhlI)**, but **not significantly upregulated in strains 97 or 98**, are:',
  '',
  '1. **Ribosome** (`pau03010`)',
  '2. **Riboflavin metabolism** (`pau00740`)',
  '',
  '## Evidence summary',
  '',
  '- Differential-expression filter: `padj < 0.05` and `log2FoldChange > 1.5`.',
  '- KEGG enrichment filter: `pvalue < 0.05` and `BH-adjusted pvalue < 0.05`.',
  '- Significant pathway counts:',
  '  - Strain 97: 4 pathways',
  '  - Strain 98: 2 pathways',
  '  - Strain 99: 5 pathways',
  '- The significant pathways in strain 99 were: Aminoacyl-tRNA biosynthesis, Ribosome, Riboflavin metabolism, Oxidative phosphorylation, and Sulfur metabolism.',
  '- Of these, **Ribosome** and **Riboflavin metabolism** were absent from the significant pathway sets of strains 97 and 98.',
  '',
  '## Strain-99-specific pathway statistics',
  '',
  sprintf('- **Ribosome** (`pau03010`): Count=%s, GeneRatio=%s, pvalue=%.6g, BH-adjusted pvalue=%.6g', exclusive_99$Count[exclusive_99$Description == 'Ribosome'], exclusive_99$GeneRatio[exclusive_99$Description == 'Ribosome'], exclusive_99$pvalue[exclusive_99$Description == 'Ribosome'], exclusive_99$p.adjust[exclusive_99$Description == 'Ribosome']),
  sprintf('- **Riboflavin metabolism** (`pau00740`): Count=%s, GeneRatio=%s, pvalue=%.6g, BH-adjusted pvalue=%.6g', exclusive_99$Count[exclusive_99$Description == 'Riboflavin metabolism'], exclusive_99$GeneRatio[exclusive_99$Description == 'Riboflavin metabolism'], exclusive_99$pvalue[exclusive_99$Description == 'Riboflavin metabolism'], exclusive_99$p.adjust[exclusive_99$Description == 'Riboflavin metabolism'])
)
writeLines(answer_lines, 'R0_Material/final_answer.md')

# 5) Create a small plot for the HTML report
plot_file <- 'R0_Material/significant_pathways_by_strain.png'
png(plot_file, width = 1000, height = 520, res = 140)
par(mar = c(5, 5, 4, 2) + 0.1)
vals <- summary_df$significant_pathways
names(vals) <- paste0('Strain ', summary_df$strain)
bar_cols <- c('#6baed6', '#74c476', '#fd8d3c')
barplot(vals, col = bar_cols, ylim = c(0, max(vals) + 2), main = 'Significant KEGG pathways by strain', ylab = 'Number of significant pathways')
text(x = c(0.7, 1.9, 3.1), y = vals + 0.2, labels = vals)
dev.off()

# HTML helpers
html_escape <- function(x) {
  x <- gsub('&', '&amp;', x, fixed = TRUE)
  x <- gsub('<', '&lt;', x, fixed = TRUE)
  x <- gsub('>', '&gt;', x, fixed = TRUE)
  x
}

df_to_html <- function(df) {
  if (nrow(df) == 0) return('<p><em>None</em></p>')
  headers <- paste(sprintf('<th>%s</th>', html_escape(colnames(df))), collapse='')
  rows <- apply(df, 1, function(r) paste(sprintf('<td>%s</td>', html_escape(as.character(r))), collapse=''))
  rows <- paste(sprintf('<tr>%s</tr>', rows), collapse='\n')
  sprintf('<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>', headers, rows)
}

img_data <- dataURI(file = plot_file, mime = 'image/png')

timestamp <- format(Sys.time(), 'demo_%Y-%m-%d_%H%M%S.html')
html_file <- file.path('R0_Result', timestamp)
css <- "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;line-height:1.5;max-width:1100px;margin:40px auto;padding:0 20px;color:#222} h1,h2,h3{color:#111} code{background:#f4f4f4;padding:2px 5px;border-radius:4px} table{border-collapse:collapse;width:100%;margin:14px 0 24px 0;font-size:14px} th,td{border:1px solid #ddd;padding:8px;vertical-align:top} th{background:#f7f7f7;text-align:left} .callout{background:#f6fbff;border-left:4px solid #339af0;padding:14px 16px;margin:18px 0} .answer{background:#f8fff5;border-left:4px solid #51cf66;padding:14px 16px;margin:18px 0} .small{color:#666;font-size:13px}"

html <- paste0(
  '<!DOCTYPE html><html><head><meta charset="utf-8"><title>KEGG exclusivity analysis</title><style>', css, '</style></head><body>',
  '<h1>KEGG pathway enrichment comparison for quorum-sensing mutants</h1>',
  '<p class="small">Generated at ', format(Sys.time(), '%Y-%m-%d %H:%M:%S %Z'), '.</p>',
  '<div class="callout"><strong>Question.</strong> In KEGG pathway enrichment of quorum-sensing mutants, which two functional categories are exclusively upregulated in the double knockout strain 99 (ΔlasIΔrhlI) and not in single knockouts 97 and 98, relative to wildtype strain 1?</div>',
  '<h2>Input data</h2>',
  '<ul>',
  '<li><code>res_1vs97.rds</code>: DESeq2 results for strain 97 vs wildtype</li>',
  '<li><code>res_1vs98.rds</code>: DESeq2 results for strain 98 vs wildtype</li>',
  '<li><code>res_1vs99.rds</code>: DESeq2 results for strain 99 vs wildtype</li>',
  '</ul>',
  '<h2>Filtering and enrichment procedure</h2>',
  '<ol>',
  '<li>Read each <code>DESeqResults</code> object and convert it to a data frame.</li>',
  '<li>Keep upregulated genes with <code>padj &lt; 0.05</code> and <code>log2FoldChange &gt; 1.5</code>.</li>',
  '<li>Map PA14 genes to KEGG pathways using organism code <code>pau</code> (Pseudomonas aeruginosa UCBPP-PA14).</li>',
  '<li>Run one-sided hypergeometric over-representation analysis for each pathway.</li>',
  '<li>Retain pathways with <code>pvalue &lt; 0.05</code> and <code>BH-adjusted pvalue &lt; 0.05</code>.</li>',
  '<li>Compare significant pathway sets across strains and isolate categories unique to strain 99.</li>',
  '</ol>',
  '<h2>Gene-level filtering summary</h2>', df_to_html(summary_df),
  '<h2>Significant pathway counts by strain</h2>',
  '<figure><img src="', img_data, '" alt="Significant pathways by strain" style="max-width:100%;border:1px solid #ddd"><figcaption>Strain 99 produced the largest set of significant upregulated KEGG pathways.</figcaption></figure>',
  '<h2>Significant KEGG pathways</h2>',
  '<h3>Strain 97</h3>', df_to_html(sig97[, c('ID','Description','Count','GeneRatio','BgRatio','pvalue','p.adjust')]),
  '<h3>Strain 98</h3>', df_to_html(sig98[, c('ID','Description','Count','GeneRatio','BgRatio','pvalue','p.adjust')]),
  '<h3>Strain 99</h3>', df_to_html(sig99[, c('ID','Description','Count','GeneRatio','BgRatio','pvalue','p.adjust')]),
  '<h2>Exclusive pathways in strain 99</h2>', df_to_html(exclusive_99[, c('ID','Description','Count','GeneRatio','BgRatio','pvalue','p.adjust','geneID')]),
  '<div class="answer"><h2>Final answer</h2><p>The two KEGG functional categories exclusively upregulated in strain 99 are <strong>Ribosome</strong> (<code>pau03010</code>) and <strong>Riboflavin metabolism</strong> (<code>pau00740</code>).</p></div>',
  '</body></html>'
)
writeLines(html, html_file)

# 6) steps.md
steps_lines <- c(
  '# steps.md',
  '',
  '## Part 1: Environment Configuration',
  '',
  '- Detected working analysis environment: macOS host with `Rscript` available.',
  '- Required packages used successfully: `DESeq2` (autoloaded by the RDS objects), `KEGGREST`, and `base64enc`.',
  '- No blocking dependency gaps were found for this analysis.',
  '- Optional note: `clusterProfiler` was not installed, so KEGG over-representation was implemented directly with KEGG mappings plus a hypergeometric test, which is methodologically appropriate for this task.',
  '',
  '## Part 2: Refined Steps',
  '',
  '### Step 1 — Stage the inputs',
  '- **Input files:** Original RDS files from the user-provided paths; the natural-language prompt.',
  '- **Execution step:** Create `R0_Input`, `R0_Material`, and `R0_Result`; copy the RDS files into `R0_Input`; save the prompt as `R0_Input/user-prompt.txt`.',
  '- **Output files:** `R0_Input/user-prompt.txt`, `R0_Input/res_1vs97.rds`, `R0_Input/res_1vs98.rds`, `R0_Input/res_1vs99.rds`.',
  '',
  '### Step 2 — Inspect the RDS contents',
  '- **Input files:** `R0_Input/res_1vs97.rds`, `R0_Input/res_1vs98.rds`, `R0_Input/res_1vs99.rds`.',
  '- **Execution step:** Read each RDS object in R; confirm class and columns; verify that each file is a gene-level `DESeqResults` table.',
  '- **Output files:** `R0_Material/file_content.md`.',
  '',
  '### Step 3 — Filter upregulated genes',
  '- **Input files:** The three RDS files in `R0_Input`.',
  '- **Execution step:** Convert each `DESeqResults` object to a data frame and keep genes with `padj < 0.05` and `log2FoldChange > 1.5`.',
  '- **Output files:** `R0_Material/upregulated_genes_strain97.csv`, `R0_Material/upregulated_genes_strain98.csv`, `R0_Material/upregulated_genes_strain99.csv`.',
  '',
  '### Step 4 — Perform KEGG enrichment',
  '- **Input files:** Upregulated gene tables and KEGG PA14 pathway mappings (`organism = pau`).',
  '- **Execution step:** Run over-representation testing for each strain; keep pathways with `pvalue < 0.05` and `BH-adjusted pvalue < 0.05`.',
  '- **Output files:** `R0_Material/kegg_all_strain97.csv`, `R0_Material/kegg_all_strain98.csv`, `R0_Material/kegg_all_strain99.csv`, `R0_Material/kegg_sig_strain97.csv`, `R0_Material/kegg_sig_strain98.csv`, `R0_Material/kegg_sig_strain99.csv`, `R0_Material/kegg_enrichment_summary.csv`.',
  '',
  '### Step 5 — Compare strains and extract the exclusive strain-99 signal',
  '- **Input files:** `R0_Material/kegg_sig_strain97.csv`, `R0_Material/kegg_sig_strain98.csv`, `R0_Material/kegg_sig_strain99.csv`.',
  '- **Execution step:** Compare significant pathway names across strains and keep pathways present only in the significant pathway set of strain 99.',
  '- **Output files:** `R0_Material/kegg_exclusive_upregulated_strain99.csv`, `R0_Material/final_answer.md`, `R0_Material/kegg_compare_report.txt`.',
  '',
  '### Step 6 — Assemble report and publish results',
  '- **Input files:** Summary tables, exclusive pathway table, and answer file.',
  '- **Execution step:** Generate a plot, embed it into a self-contained HTML report, and copy requested result files into `R0_Result`.',
  '- **Output files:** Self-contained HTML report in `R0_Result`, plus copied CSV/Markdown result files in `R0_Result`.',
  '',
  '## Part 3: Results Organization',
  '',
  '- Copy the following deliverable files from `R0_Material` to `R0_Result`:',
  '  - `final_answer.md`',
  '  - `kegg_enrichment_summary.csv`',
  '  - `kegg_sig_strain97.csv`',
  '  - `kegg_sig_strain98.csv`',
  '  - `kegg_sig_strain99.csv`',
  '  - `kegg_exclusive_upregulated_strain99.csv`',
  '  - `kegg_compare_report.txt`',
  '',
  '## Part 4: Notification',
  '',
  sprintf('1. Generated self-contained HTML report: `%s` in `R0_Result`.', basename(html_file)),
  sprintf('2. Inform the user: "This round of execution has ended. Please check `%s` file and the results in the `R0_Result` folder."', basename(html_file))
)
writeLines(steps_lines, 'R0_Material/steps.md')

# copy results to R0_Result
files_to_copy <- c(
  'R0_Material/final_answer.md',
  'R0_Material/kegg_enrichment_summary.csv',
  'R0_Material/kegg_sig_strain97.csv',
  'R0_Material/kegg_sig_strain98.csv',
  'R0_Material/kegg_sig_strain99.csv',
  'R0_Material/kegg_exclusive_upregulated_strain99.csv',
  'R0_Material/kegg_compare_report.txt'
)
for (f in files_to_copy) file.copy(f, file.path('R0_Result', basename(f)), overwrite = TRUE)

cat(basename(html_file), '\n')
