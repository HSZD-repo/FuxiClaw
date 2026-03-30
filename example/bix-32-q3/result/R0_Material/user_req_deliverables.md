# user_req_deliverables.md

Based on the prompt and the input files, the user needs the following deliverables:

1. **A direct answer** identifying the two KEGG functional categories that are significantly upregulated only in strain 99 (ΔlasIΔrhlI), and not in strains 97 or 98, relative to wildtype strain 1.
2. **A reproducible comparison table** showing, for each strain (97, 98, 99):
   - number of upregulated genes passing the thresholds (`padj < 0.05`, `log2FoldChange > 1.5`)
   - significant KEGG pathways under enrichment thresholds (`pvalue < 0.05`, `BH-adjusted pvalue < 0.05`).
3. **A machine-readable table** listing the KEGG pathways significant only in strain 99 and not in 97 or 98.
4. **An audit trail** documenting how the RDS files were interpreted, how pathway enrichment was performed, and which files were produced.
5. **A self-contained HTML report** summarizing preprocessing, thresholds, enrichment method, comparison logic, and final answer.
