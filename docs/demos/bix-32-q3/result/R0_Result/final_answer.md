# final_answer.md

## Direct answer

The two KEGG functional categories that are **exclusively upregulated in strain 99 (ΔlasIΔrhlI)**, but **not significantly upregulated in strains 97 or 98**, are:

1. **Ribosome** (`pau03010`)
2. **Riboflavin metabolism** (`pau00740`)

## Evidence summary

- Differential-expression filter: `padj < 0.05` and `log2FoldChange > 1.5`.
- KEGG enrichment filter: `pvalue < 0.05` and `BH-adjusted pvalue < 0.05`.
- Significant pathway counts:
  - Strain 97: 4 pathways
  - Strain 98: 2 pathways
  - Strain 99: 5 pathways
- The significant pathways in strain 99 were: Aminoacyl-tRNA biosynthesis, Ribosome, Riboflavin metabolism, Oxidative phosphorylation, and Sulfur metabolism.
- Of these, **Ribosome** and **Riboflavin metabolism** were absent from the significant pathway sets of strains 97 and 98.

## Strain-99-specific pathway statistics

- **Ribosome** (`pau03010`): Count=6, GeneRatio=6/43, pvalue=0.00229706, BH-adjusted pvalue=0.0293942
- **Riboflavin metabolism** (`pau00740`): Count=3, GeneRatio=3/43, pvalue=0.0026722, BH-adjusted pvalue=0.0293942
