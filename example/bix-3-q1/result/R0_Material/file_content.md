# Input Files Analysis

## File 1: Data_deposition_RNAseq_Paroxetine_2017.xlsx

**Path:** `/Users/maxliu01/Desktop/0_project/1_bio_agent/hszd/BixBench/hf/testcase/bix-3-q1/CapsuleData-94bcdbc9-c729-4661-9bc1-0057bbea39c4/Data_deposition_RNAseq_Paroxetine_2017.xlsx`

**Format:** Excel (.xlsx) file containing RNA-seq count data from a Paroxetine 2017 study

**Content Overview:**
This file contains RNA-seq gene expression count data. Based on the filename, it appears to be from a study on Paroxetine (an antidepressant). The user specifies:
- Need to filter for Control mice only
- Compare "final_blood" vs "baseline_blood" samples
- Design formula: ~ Tissue
- Contrast: final_blood vs baseline_blood
- Need to count genes meeting criteria: FDR<0.05, |log2FC|>1, baseMean≥10
- If counts are normalized, they should be scaled to integer pseudo-counts before DESeq2 analysis

The file likely contains:
- Gene identifiers (gene symbols or IDs)
- Sample columns with count data
- Sample metadata (Condition, Tissue type, Timepoint)

**Next Steps:**
1. Load the Excel file to inspect its structure
2. Identify control samples
3. Filter for baseline_blood and final_blood samples
4. Run DESeq2 analysis
5. Extract and count genes meeting the specified criteria
