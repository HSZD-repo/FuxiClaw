# Execution Plan

## Step 1: Environment Setup
- Check if R and required packages (DESeq2, readxl) are installed
- Install missing dependencies if needed

## Step 2: Data Loading and Exploration
- Read the Excel file using Python (pandas/readxl)
- Examine data structure (samples, genes, metadata)
- Identify Control mice samples
- Separate count matrix from metadata
- Check if counts are normalized (if so, convert to integer pseudo-counts)

## Step 3: Data Preparation for DESeq2
- Extract count data for Control mice only
- Filter for final_blood and baseline_blood samples
- Create metadata dataframe with Tissue column
- Ensure counts are integers (scale if normalized)
- Remove genes with very low counts across all samples

## Step 4: DESeq2 Analysis
- Create DESeqDataSet object with design ~ Tissue
- Run DESeq2 pipeline (estimation, testing)
- Extract results for contrast: final_blood vs baseline_blood
- Apply independent filtering (alpha=0.05)

## Step 5: Filtering and Results
- Filter results by: FDR < 0.05, |log2FC| > 1, baseMean ≥ 10
- Count genes meeting all criteria
- Save full results table
- Save filtered results table

## Step 6: Report Generation
- Generate HTML report with analysis summary
- Include data preprocessing steps
- Document filtering criteria
- Report final gene count
