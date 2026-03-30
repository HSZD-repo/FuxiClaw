# Steps Document

## Part 1: Environment Configuration

### Required Dependencies
- Python 3.x with pandas, numpy
- R with DESeq2 package from Bioconductor
- rpy2 for Python-R integration (or run R directly)

### Installation Check
The analysis will use R directly with DESeq2 Bioconductor package.

## Part 2: Refined Steps

### Step 1: Data Loading and Exploration
**Input Files:**
- `/Users/maxliu01/Desktop/0_project/1_bio_agent/hszd/BixBench/hf/testcase/bix-3-q1/CapsuleData-94bcdbc9-c729-4661-9bc1-0057bbea39c4/Data_deposition_RNAseq_Paroxetine_2017.xlsx`

**Execution:**
1. Use Python pandas to read Excel file and explore structure
2. Identify Control mice samples (final_blood and baseline_blood)
3. Check if data is normalized (if max values are small, likely normalized)
4. If normalized, scale to integer pseudo-counts by multiplying by 1e6 and rounding

**Output Files:**
- `R0_Material/counts_matrix.csv` - Extracted count matrix
- `R0_Material/metadata.csv` - Sample metadata

### Step 2: DESeq2 Analysis
**Input Files:**
- `R0_Material/counts_matrix.csv`
- `R0_Material/metadata.csv`

**Execution:**
1. Load counts and metadata in R
2. Create DESeqDataSet with design = ~ Tissue
3. Filter genes with low counts (rowSums(counts) >= 10)
4. Run DESeq() function
5. Extract results with contrast c("Tissue", "final_blood", "baseline_blood")
6. Apply lfcShrink if needed (for better log2FC estimates)

**Output Files:**
- `R0_Material/deseq2_results.csv` - Full DESeq2 results

### Step 3: Filtering and Counting
**Input Files:**
- `R0_Material/deseq2_results.csv`

**Execution:**
1. Filter for padj (FDR) < 0.05
2. Filter for |log2FoldChange| > 1
3. Filter for baseMean >= 10
4. Count genes meeting all three criteria

**Output Files:**
- `R0_Material/filtered_results.csv` - Filtered significant genes
- `R0_Material/summary.txt` - Summary statistics

### Step 4: Results Organization
**Input Files:**
- `R0_Material/deseq2_results.csv`
- `R0_Material/filtered_results.csv`
- `R0_Material/summary.txt`

**Execution:**
Copy all result files to R0_Result folder

**Output Files (in R0_Result):**
- `deseq2_results.csv`
- `filtered_results.csv`
- `summary.txt`

### Step 5: HTML Report Generation
**Input Files:**
- All result files

**Execution:**
Generate HTML report documenting:
- Data preprocessing steps
- DESeq2 parameters
- Filtering criteria applied
- Final gene count

**Output Files:**
- `R0_Result/demo_<timestamp>.html`

## Part 3: Results Organization
All files mentioned in Part 2 Step 4 will be copied from R0_Material to R0_Result.

## Part 4: Notification
After completion, notify user to check the HTML report and results in R0_Result folder.
