# User Requirements and Deliverables

## User Question Summary
Using DESeq2 on Control mice, compare final blood vs baseline blood (design ~ Tissue; contrast final_blood vs baseline_blood). Report the count of genes with FDR<0.05, |log2FC|>1, and baseMean≥10; if counts are normalized, scale to integer pseudo-counts before running DESeq2.

## Data Description
- **Source File:** Data_deposition_RNAseq_Paroxetine_2017.xlsx
- **NormCount Sheet:** Contains normalized count data for 25,405 genes across 90 samples
- **Mapping_statistics Sheet:** Contains sample metadata

## Control Sample Structure
- **baseline_blood:** 10 Control samples (Sample IDs ending in _bl)
- **final_blood:** 10 Control samples (Sample IDs ending in _fi)
- **dentate_gyrus:** 10 Control samples (Sample IDs ending in _c) - not used in this comparison

## Analysis Parameters
1. **Design Formula:** ~ Tissue
2. **Contrast:** final_blood vs baseline_blood
3. **Filtering Criteria:**
   - FDR < 0.05
   - |log2FoldChange| > 1
   - baseMean ≥ 10

## Required Deliverables
1. **deseq2_results.csv** - Full DESeq2 results table
2. **significant_genes.csv** - Filtered significant genes meeting criteria
3. **count_summary.txt** - Report with count of significant genes
4. **demo_*.html** - HTML report documenting the full analysis

