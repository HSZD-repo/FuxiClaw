# file_content.md

This document summarizes the input files placed in `R0_Input` for the /deep analysis.

## 1) user-prompt.txt
- **Path:** `R0_Input/user-prompt.txt`
- **Overview:** Natural-language analysis request asking which KEGG functional categories are exclusively upregulated in the double quorum-sensing synthase knockout strain 99 (ΔlasIΔrhlI) compared with the single knockouts 97 and 98, relative to wildtype strain 1. It specifies the DE filtering thresholds (`adjusted p-value < 0.05`, `log2FoldChange > 1.5`) and the KEGG enrichment p-value cutoff (`0.05`).

## 2) res_1vs97.rds
- **Path:** `R0_Input/res_1vs97.rds`
- **Overview:** R serialized `DESeqResults` object containing differential-expression results for wildtype strain 1 versus strain 97. The object contains 5,828 genes and the standard DESeq2 result columns: `baseMean`, `log2FoldChange`, `lfcSE`, `stat`, `pvalue`, and `padj`.

## 3) res_1vs98.rds
- **Path:** `R0_Input/res_1vs98.rds`
- **Overview:** R serialized `DESeqResults` object containing differential-expression results for wildtype strain 1 versus strain 98. The object contains 5,828 genes and the standard DESeq2 result columns: `baseMean`, `log2FoldChange`, `lfcSE`, `stat`, `pvalue`, and `padj`.

## 4) res_1vs99.rds
- **Path:** `R0_Input/res_1vs99.rds`
- **Overview:** R serialized `DESeqResults` object containing differential-expression results for wildtype strain 1 versus strain 99. The object contains 5,828 genes and the standard DESeq2 result columns: `baseMean`, `log2FoldChange`, `lfcSE`, `stat`, `pvalue`, and `padj`.

## Content-level interpretation
- The three `.rds` files are not precomputed KEGG outputs; they are gene-level DESeq2 result tables.
- Therefore, the required analysis is: (1) identify upregulated genes under the user thresholds for each strain, (2) run KEGG enrichment on each upregulated set, and (3) compare significant pathways across strains to find categories unique to strain 99.
