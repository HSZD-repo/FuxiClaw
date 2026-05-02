# execution_plan.md

To generate the required deliverables, the work is divided into 6 steps:

1. **Stage the inputs**: create `R0_Input`, `R0_Material`, and `R0_Result`; copy the three RDS files into `R0_Input`; save the user question into `R0_Input/user-prompt.txt`.
2. **Inspect file structure**: open each RDS object and confirm that it is a `DESeqResults` table with gene identifiers and differential-expression statistics.
3. **Filter upregulated genes**: for each strain comparison (1vs97, 1vs98, 1vs99), extract genes with `padj < 0.05` and `log2FoldChange > 1.5`.
4. **Run KEGG enrichment**: map PA14 genes to KEGG pathways (`organism = pau`) and perform over-representation testing on each upregulated gene set; keep pathways with `pvalue < 0.05` and `BH-adjusted pvalue < 0.05`.
5. **Compare pathway sets across strains**: identify pathways significant in strain 99 but absent from the significant pathway lists of strains 97 and 98.
6. **Package outputs**: write summary tables, a concise answer file, process documentation, and a self-contained HTML report; copy requested result files into `R0_Result`.
