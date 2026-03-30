# User Request Deliverables

Based on the user prompt and file analysis, the following deliverables are required:

## Primary Deliverable
1. **DESeq2 Analysis Results** - Differential expression analysis comparing final_blood vs baseline_blood in Control mice
   - Design: ~ Tissue
   - Contrast: final_blood vs baseline_blood

## Specific Outputs Required
2. **Count of Significant Genes** - Number of genes meeting ALL criteria:
   - FDR (adjusted p-value) < 0.05
   - |log2FoldChange| > 1
   - baseMean ≥ 10

3. **Results Table** - CSV file containing DESeq2 results for all genes

4. **Filtered Results Table** - CSV file containing only genes meeting significance criteria

## Report
5. **HTML Report** (`demo_<timestamp>.html`) documenting:
   - Data preprocessing steps
   - DESeq2 analysis parameters
   - Filtering criteria
   - Final count of significant genes
   - Summary statistics
