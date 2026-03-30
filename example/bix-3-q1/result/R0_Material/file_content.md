# Document Analysis Summary

## Input File
- **File Name:** Data_deposition_RNAseq_Paroxetine_2017.xlsx
- **File Path:** /Users/maxliu01/Desktop/0_project/1_bio_agent/hszd/BixBench/hf/testcase/bix-3-q1/CapsuleData-94bcdbc9-c729-4661-9bc1-0057bbea39c4/Data_deposition_RNAseq_Paroxetine_2017.xlsx
- **Format:** Excel (.xlsx) - RNA-seq count data from Paroxetine 2017 study

## Content Overview
This file contains RNA-seq count data from a study on Paroxetine. The data includes:
- Gene expression counts (likely normalized or raw count matrix)
- Sample metadata including tissue type (final_blood vs baseline_blood)
- Treatment information (Control mice)

## Analysis Task
Using DESeq2 to compare final blood vs baseline blood in Control mice with the following parameters:
- Design formula: ~ Tissue
- Contrast: final_blood vs baseline_blood
- Filtering criteria: FDR < 0.05, |log2FC| > 1, baseMean ≥ 10

## Expected Deliverables
1. DESeq2 results table with differentially expressed genes
2. Count of genes meeting the filtering criteria (FDR<0.05, |log2FC|>1, baseMean≥10)
3. HTML report documenting the analysis
