# Execution Plan

## Step 1: Data Extraction and Preparation
- Read the NormCount sheet from the Excel file
- Extract column headers (row 3) to identify sample groupings
- Map samples to their tissue types and response groups
- Filter for Control samples only
- Subset data to include only baseline_blood and final_blood samples
- Scale normalized counts to integer pseudo-counts (multiply by a scaling factor and round)
- Create sample metadata data frame with Tissue information

## Step 2: DESeq2 Analysis
- Install/load required R packages: DESeq2, BiocManager
- Create DESeqDataSet object with design formula ~ Tissue
- Run DESeq() function to perform differential expression analysis
- Extract results with contrast: final_blood vs baseline_blood

## Step 3: Results Filtering and Reporting
- Filter results for genes meeting criteria:
  - FDR (padj) < 0.05
  - |log2FoldChange| > 1
  - baseMean ≥ 10
- Count the number of significant genes
- Save full results and filtered results to CSV files
- Generate summary report

## Step 4: HTML Report Generation
- Create comprehensive HTML report with:
  - Analysis methodology
  - Sample information
  - DESeq2 results summary
  - Significant genes table
  - Count of genes meeting criteria

