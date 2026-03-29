---
name: bio-rnaseq-pipeline-core
description: >
  Complete RNA-seq analysis pipeline from raw FASTQ to differential expression. 
  Includes QC, trimming, alignment (HISAT2/STAR), quantification (featureCounts/Salmon), 
  and downstream analysis. Use for bulk RNA-seq projects.
license: MIT
category: bioinformatics
tags: [rnaseq, rna-seq, gene-expression, differential-expression, pipeline]
---

# RNA-seq Analysis Pipeline

Standard workflow for bulk RNA-seq analysis: from raw reads to differential expression.

## Pipeline Overview

```
Raw FASTQ → QC → Trimming → Alignment → Quantification → Differential Expression
```

## 1. Quality Control

**Run FastQC on raw reads:**
```bash
# Single sample
fastqc sample_R1.fastq.gz sample_R2.fastq.gz -o qc/

# Batch processing
for r1 in *_R1.fastq.gz; do
    r2=${r1/_R1/_R2}
    fastqc "$r1" "$r2" -o qc/
done

# Aggregate reports
multiqc qc/ -o multiqc_report/
```

**What to check:**
| Metric | Good | Bad | Action |
|--------|------|-----|--------|
| Per-base quality | Most >Q20 | Drop at ends | Trim low quality |
| Adapter content | <5% | >20% | Remove adapters |
| GC content | ~50% | Extreme | Check for contamination |
| Duplication | <50% | >70% | May indicate low complexity |

## 2. Adapter Trimming

**Using fastp (recommended):**
```bash
# Single sample
fastp -i sample_R1.fastq.gz -I sample_R2.fastq.gz \
    -o sample_R1.clean.fq.gz -O sample_R2.clean.fq.gz \
    --detect_adapter_for_pe \
    -q 20 -u 40 -l 20 \
    -j sample_fastp.json -h sample_fastp.html

# Parameters:
# -q 20    : Quality threshold (Q20)
# -u 40    : Max 40% low quality bases
# -l 20    : Min read length 20bp
# --detect_adapter_for_pe : Auto-detect adapters

# Batch processing
for r1 in *_R1.fastq.gz; do
    sample=$(basename $r1 _R1.fastq.gz)
    r2=${sample}_R2.fastq.gz
    
    fastp -i $r1 -I $r2 \
        -o ${sample}_R1.clean.fq.gz \
        -O ${sample}_R2.clean.fq.gz \
        --detect_adapter_for_pe \
        -q 20 -u 40 -l 20 \
        -j qc/${sample}_fastp.json
done
```

**Using trimmomatic (alternative):**
```bash
trimmomatic PE -threads 8 \
    sample_R1.fastq.gz sample_R2.fastq.gz \
    sample_R1.paired.fq.gz sample_R1.unpaired.fq.gz \
    sample_R2.paired.fq.gz sample_R2.unpaired.fq.gz \
    ILLUMINACLIP:adapters.fa:2:30:10 \
    LEADING:3 TRAILING:3 SLIDINGWINDOW:4:15 MINLEN:36
```

## 3. Alignment

### Option A: HISAT2 (recommended for splicing)

**Prerequisites:**
```bash
# Build HISAT2 index (one-time)
mkdir -p hisat2_index
hisat2-build -p 16 reference.fa hisat2_index/reference
```

**Alignment:**
```bash
# Single sample
hisat2 -p 8 \
    -x hisat2_index/reference \
    -1 sample_R1.clean.fq.gz \
    -2 sample_R2.clean.fq.gz \
    --rg-id sample \
    --rg SM:sample \
    --rg PL:ILLUMINA \
    --rg LB:lib1 \
    2> logs/sample.hisat2.log | \
    samtools sort -@ 4 -o aligned/sample.sorted.bam -

samtools index aligned/sample.sorted.bam

# Parameters:
# -p 8                    : 8 threads
# --rg-*                  : Read group info (required for GATK)
# 2> log                  : Save stderr (alignment stats)

# Batch processing
for r1 in clean/*_R1.clean.fq.gz; do
    sample=$(basename $r1 _R1.clean.fq.gz)
    r2=clean/${sample}_R2.clean.fq.gz
    
    hisat2 -p 8 -x hisat2_index/reference \
        -1 $r1 -2 $r2 \
        --rg-id $sample --rg SM:$sample --rg PL:ILLUMINA \
        2> logs/${sample}.hisat2.log | \
        samtools sort -@ 4 -o aligned/${sample}.bam -
    
    samtools index aligned/${sample}.bam
done
```

### Option B: STAR (faster, more memory)

**Prerequisites:**
```bash
# Generate genome index (one-time, needs ~32GB RAM)
mkdir -p star_index
STAR --runMode genomeGenerate \
    --genomeDir star_index/ \
    --genomeFastaFiles reference.fa \
    --sjdbGTFfile annotations.gtf \
    --sjdbOverhang 100 \
    --runThreadN 16

# sjdbOverhang = read length - 1 (for 100bp reads, use 99)
```

**Alignment:**
```bash
# Single sample
STAR --genomeDir star_index/ \
    --readFilesIn sample_R1.clean.fq.gz sample_R2.clean.fq.gz \
    --readFilesCommand zcat \
    --outFileNamePrefix star/sample_ \
    --outSAMtype BAM SortedByCoordinate \
    --outSAMattrRGline ID:sample SM:sample PL:ILLUMINA LB:lib1 \
    --twopassMode Basic \
    --runThreadN 8

# Output is already sorted and indexed
mv star/sample_Aligned.sortedByCoord.out.bam aligned/sample.bam
samtools index aligned/sample.bam
```

## 4. Alignment QC

```bash
# Alignment statistics
samtools flagstat aligned/sample.bam > qc/sample.flagstat.txt

# Gene body coverage
qualimap rnaseq \
    -bam aligned/sample.bam \
    -gtf annotations.gtf \
    -outdir qualimap/sample/

# RNA-seq metrics with Picard
picard CollectRnaSeqMetrics \
    I=aligned/sample.bam \
    O=qc/sample.rnaseq_metrics \
    REF_FLAT=ref_flat.txt \
    STRAND=SECOND_READ_TRANSCRIPTION_STRAND

# MultiQC aggregate
multiqc aligned/ qualimap/ qc/ -o multiqc_final/
```

## 5. Gene Quantification

### Option A: featureCounts (recommended)

```bash
# Single sample
featureCounts -T 8 \
    -a annotations.gtf \
    -o counts/sample.counts.txt \
    -t exon -g gene_id \
    -p --countReadPairs \
    aligned/sample.bam

# Parameters:
# -T 8           : 8 threads
# -t exon        : Feature type (exon)
# -g gene_id     : Group by gene_id
# -p              : Paired-end (count fragments, not reads)
# --countReadPairs : Count read pairs (RNA-seq specific)

# Multiple samples - create count matrix
featureCounts -T 8 \
    -a annotations.gtf \
    -o counts/all_samples.counts.txt \
    -t exon -g gene_id \
    -p --countReadPairs \
    aligned/*.bam

# Output format (first 6 columns are annotations):
# Geneid Chr Start End Strand Length Sample1 Sample2 ...
```

### Option B: HTSeq

```bash
htseq-count -f bam -r pos -s no \
    -t exon -i gene_id \
    aligned/sample.bam \
    annotations.gtf \
    > counts/sample.counts.txt

# Strand options:
# -s no   : Unstranded
# -s yes  : Stranded (forward)
# -s reverse : Stranded (reverse)
```

### Option C: Salmon (alignment-free, fast)

```bash
# Index transcriptome
salmon index -t transcripts.fa -i salmon_index

# Quantify (no alignment needed)
salmon quant -i salmon_index \
    -l A \
    -1 sample_R1.clean.fq.gz \
    -2 sample_R2.clean.fq.gz \
    -p 8 \
    --validateMappings \
    --gcBias \
    -o salmon/sample

# Output: salmon/sample/quant.sf
# Contains: TPM, NumReads (estimated counts)
```

## 6. Differential Expression Analysis

### Using DESeq2 (R)

```r
library(DESeq2)
library(tidyverse)

# Read count matrix
# Skip first row (command info), use first column as row names
countData <- read.table(
    "counts/all_samples.counts.txt",
    header=TRUE,
    row.names=1,
    skip=1
)

# Keep only count columns (remove first 5 annotation columns)
countData <- countData[, 6:ncol(countData)]

# Rename columns to sample names
colnames(countData) <- gsub("\\.bam$", "", colnames(countData))

# Sample information (create this table)
colData <- data.frame(
    row.names = colnames(countData),
    condition = factor(c(
        "control", "control", "control",
        "treatment", "treatment", "treatment"
    )),
    batch = factor(c(1, 2, 3, 1, 2, 3))
)

# Create DESeq2 object
dds <- DESeqDataSetFromMatrix(
    countData = countData,
    colData = colData,
    design = ~ batch + condition  # Include batch effect
)

# Filter low-count genes
keep <- rowSums(counts(dds)) >= 10
dds <- dds[keep, ]

# Run analysis
dds <- DESeq(dds)

# Extract results
res <- results(dds, contrast=c("condition", "treatment", "control"))
resOrdered <- res[order(res$padj), ]

# Summary
summary(res)

# Save results
write.csv(as.data.frame(resOrdered), "deseq2_results.csv")

# MA plot
plotMA(res, main="MA Plot")

# PCA plot
vsd <- vst(dds, blind=FALSE)
plotPCA(vsd, intgroup="condition")

# Heatmap of top genes
library(pheatmap)
topGenes <- head(order(res$padj), 20)
mat <- assay(vsd)[topGenes, ]
mat <- mat - rowMeans(mat)
pheatmap(mat, annotation_col=as.data.frame(colData(dds)))
```

### Using edgeR (R)

```r
library(edgeR)

# Read counts
counts <- read.delim("counts/all_samples.counts.txt", skip=1, row.names=1)
counts <- counts[, 6:ncol(counts)]

# Create DGEList
group <- factor(c("ctrl", "ctrl", "ctrl", "treat", "treat", "treat"))
dge <- DGEList(counts=counts, group=group)

# Filter
keep <- filterByExpr(dge)
dge <- dge[keep, , keep.lib.sizes=FALSE]

# Normalize
dge <- calcNormFactors(dge)

# MDS plot
plotMDS(dge)

# Design matrix
design <- model.matrix(~group)

# Estimate dispersion
dge <- estimateDisp(dge, design)

# Fit model
fit <- glmFit(dge, design)
lrt <- glmLRT(fit, coef=2)

# Results
topTags(lrt)
write.csv(topTags(lrt, n=Inf)$table, "edger_results.csv")
```

## Complete Pipeline Script

```bash
#!/bin/bash
# rnaseq_pipeline.sh

set -euo pipefail

# Configuration
REF="reference.fa"
GTF="annotations.gtf"
OUTDIR="results"
THREADS=8

# Create directories
mkdir -p $OUTDIR/{qc,clean,aligned,counts,logs}

# Step 1: QC
echo "=== Step 1: QC ==="
fastqc raw_data/*.fastq.gz -o $OUTDIR/qc/
multiqc $OUTDIR/qc/ -o $OUTDIR/qc/multiqc/

# Step 2: Trim
echo "=== Step 2: Trimming ==="
for R1 in raw_data/*_R1.fastq.gz; do
    SAMPLE=$(basename $R1 _R1.fastq.gz)
    R2="raw_data/${SAMPLE}_R2.fastq.gz"
    
    fastp -i $R1 -I $R2 \
        -o $OUTDIR/clean/${SAMPLE}_R1.fq.gz \
        -O $OUTDIR/clean/${SAMPLE}_R2.fq.gz \
        --detect_adapter_for_pe \
        -q 20 -u 40 -l 20 \
        -j $OUTDIR/qc/${SAMPLE}_fastp.json
done

# Step 3: Align
echo "=== Step 3: Alignment ==="
for R1 in $OUTDIR/clean/*_R1.fq.gz; do
    SAMPLE=$(basename $R1 _R1.fq.gz)
    R2="$OUTDIR/clean/${SAMPLE}_R2.fq.gz"
    
    hisat2 -p $THREADS -x hisat2_index/reference \
        -1 $R1 -2 $R2 \
        --rg-id $SAMPLE --rg SM:$SAMPLE --rg PL:ILLUMINA \
        2> $OUTDIR/logs/${SAMPLE}.hisat2.log | \
        samtools sort -@ 4 -o $OUTDIR/aligned/${SAMPLE}.bam -
    
    samtools index $OUTDIR/aligned/${SAMPLE}.bam
    samtools flagstat $OUTDIR/aligned/${SAMPLE}.bam > \
        $OUTDIR/qc/${SAMPLE}.flagstat.txt
done

# Step 4: Count
echo "=== Step 4: Quantification ==="
featureCounts -T $THREADS -a $GTF \
    -o $OUTDIR/counts/all.counts.txt \
    -t exon -g gene_id -p --countReadPairs \
    $OUTDIR/aligned/*.bam

# Step 5: MultiQC final
echo "=== Step 5: Final Report ==="
multiqc $OUTDIR -o $OUTDIR/multiqc_final/

echo "Pipeline complete! Results in $OUTDIR/"
```

## Output Files

| Directory | Contents |
|-----------|----------|
| `qc/` | FastQC, fastp, flagstat reports |
| `clean/` | Trimmed FASTQ files |
| `aligned/` | BAM files and indices |
| `counts/` | Gene count matrices |
| `logs/` | Tool stdout/stderr |

## Related Skills

- bio-rnaseq-fastqc-trimming - Detailed QC workflows
- bio-alignment-pairwise - Alignment basics
- bio-alignment-files-bam-statistics - BAM analysis
- bio-scrnaseq-qc - Single-cell RNA-seq
- rnaseq-differential-expression - Advanced DE analysis
