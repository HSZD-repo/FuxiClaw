# Steps Document

## Part 1: Environment Configuration

### Required Software
- **R** (version 4.5.3) - Installed at /opt/homebrew/bin/R
- **R Packages Required:**
  - DESeq2 (from Bioconductor)
  - readxl (for reading Excel files)
  - dplyr (for data manipulation)

### Installation Commands (if needed)
```R
install.packages("BiocManager")
BiocManager::install("DESeq2")
install.packages("readxl")
install.packages("dplyr")
```

## Part 2: Refined Steps

### Step 1: Data Extraction and Preparation
**Input Files:**
- `/Users/maxliu01/Desktop/0_project/1_bio_agent/hszd/BixBench/hf/testcase/bix-3-q1/CapsuleData-94bcdbc9-c729-4661-9bc1-0057bbea39c4/Data_deposition_RNAseq_Paroxetine_2017.xlsx`

**Execution:**
1. Read Mapping_statistics sheet to identify Control samples
2. Filter for Control samples with Tissue = "baseline_blood" or "final_blood"
3. Read NormCount sheet with proper headers (skip first 3 rows, use row 4 as header)
4. Extract gene IDs and normalized counts for Control baseline and final blood samples
5. Scale normalized counts to integer pseudo-counts by multiplying by 100 and rounding
6. Create sample metadata dataframe with Tissue column

**Output Files:**
- `R0_Material/count_matrix.csv` - Processed count matrix
- `R0_Material/sample_metadata.csv` - Sample metadata

### Step 2: DESeq2 Analysis
**Input Files:**
- `R0_Material/count_matrix.csv`
- `R0_Material/sample_metadata.csv`

**Execution:**
1. Load count matrix and ensure all values are integers
2. Create DESeqDataSet with design = ~ Tissue
3. Run DESeq() function
4. Extract results with contrast: c("Tissue", "final_blood", "baseline_blood")
5. Extract log2FoldChange, padj (FDR), and baseMean values

**Output Files:**
- `R0_Material/deseq2_results_raw.csv` - Raw DESeq2 results

### Step 3: Results Filtering and Summary
**Input Files:**
- `R0_Material/deseq2_results_raw.csv`

**Execution:**
1. Filter for genes with padj < 0.05 (FDR < 0.05)
2. Filter for |log2FoldChange| > 1
3. Filter for baseMean >= 10
4. Count number of significant genes
5. Write filtered results

**Output Files:**
- `R0_Material/deseq2_results_filtered.csv` - Filtered significant genes
- `R0_Material/count_summary.txt` - Summary count report

### Step 4: Results Organization
**Input Files:**
- `R0_Material/deseq2_results_raw.csv`
- `R0_Material/deseq2_results_filtered.csv`
- `R0_Material/count_summary.txt`

**Execution:**
Copy deliverable files from R0_Material to R0_Result:
- deseq2_results.csv (full results)
- significant_genes.csv (filtered results)
- count_summary.txt (summary report)

**Output Files (in R0_Result):**
- `R0_Result/deseq2_results.csv`
- `R0_Result/significant_genes.csv`
- `R0_Result/count_summary.txt`

### Step 5: HTML Report Generation
**Input Files:**
- All results files

**Execution:**
Generate HTML report documenting:
- Data preprocessing steps
- DESeq2 analysis parameters
- Filtering criteria
- Final count of significant genes
- Sample of significant genes table

**Output Files:**
- `R0_Result/demo_YYYY-MM-DD_HHMMSS.html`

## Part 3: Results Organization

### Files to Copy from R0_Material to R0_Result:
1. `deseq2_results_raw.csv` → `R0_Result/deseq2_results.csv`
2. `deseq2_results_filtered.csv` → `R0_Result/significant_genes.csv`
3. `count_summary.txt` → `R0_Result/count_summary.txt`

## Part 4: Notification

### HTML Report Requirements
- Document full solution process
- Include data preprocessing steps
- Describe DESeq2 analysis
- List filtering criteria
- Display count of significant genes
- Include table of significant genes (first 20 rows)

### User Notification Message
"This round of execution has ended. Please check `demo_<YYYY-MM-DD>_<HHmmss>.html` file and the results in the `R0_Result` folder."
