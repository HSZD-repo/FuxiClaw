---
name: bio-variant-calling-core
description: >
  Core variant calling workflows using GATK Best Practices, BCFTools, and FreeBayes. 
  Covers germline SNV/indel calling, VQSR/filtering, and annotation. Use for DNA 
  sequencing variant detection projects.
license: MIT
category: bioinformatics
tags: [variant-calling, gatk, bcftools, snv, indel, vcf, germline]
---

# Variant Calling Pipeline

Complete workflow for germline variant detection from DNA sequencing data.

## Pipeline Overview

```
Raw FASTQ → Alignment → BAM Processing → Variant Calling → Filtering → Annotation
```

## 1. Data Preprocessing

### Alignment with BWA

```bash
# Index reference (one-time)
bwa index reference.fa

# Align with read group information (required for GATK)
bwa mem -t 8 \
    -R '@RG\tID:sample\tSM:sample\tLB:lib1\tPL:ILLUMINA\tPU:flowcell.lane' \
    reference.fa R1.fq.gz R2.fq.gz | \
    samtools sort -o sample.sorted.bam -

samtools index sample.sorted.bam

# Read group fields:
# ID: Unique read group ID
# SM: Sample name
# LB: Library
# PL: Platform (ILLUMINA, PACBIO, etc.)
# PU: Platform unit (flowcell.lane.barcode)
```

## 2. BAM Processing (GATK Best Practices)

### Mark Duplicates

```bash
# Using Picard
picard MarkDuplicates \
    I=sample.sorted.bam \
    O=sample.dedup.bam \
    M=sample.metrics.txt \
    REMOVE_DUPLICATES=false \
    CREATE_INDEX=true

# Or using GATK
#gatk MarkDuplicates \
#    -I sample.sorted.bam \
#    -O sample.dedup.bam \
#    -M sample.metrics.txt

# Check duplicate rate (<20% is good)
grep "PERCENT_DUPLICATION" sample.metrics.txt
```

### Base Quality Score Recalibration (BQSR)

**Requirements:**
- Known variant sites (dbSNP, Mills indels)
- Download from GATK resource bundle

```bash
# Step 1: Build recalibration model
gatk BaseRecalibrator \
    -R reference.fa \
    -I sample.dedup.bam \
    --known-sites dbsnp.vcf.gz \
    --known-sites mills_indels.vcf.gz \
    -O sample.recal_data.table

# Step 2: Apply recalibration
gatk ApplyBQSR \
    -R reference.fa \
    -I sample.dedup.bam \
    --bqsr-recal-file sample.recal_data.table \
    -O sample.recal.bam \

samtools index sample.recal.bam
```

## 3. Variant Calling

### Option A: GATK HaplotypeCaller (recommended)

**Single sample (GVCF mode):**
```bash
# Call variants per sample in GVCF mode
gatk HaplotypeCaller \
    -R reference.fa \
    -I sample.recal.bam \
    -O sample.g.vcf.gz \
    -ERC GVCF \
    --native-pair-hmm-threads 8

# Parameters:
# -ERC GVCF : Emit reference confidence calls (for joint genotyping)
```

**Joint genotyping (multiple samples):**
```bash
# Step 1: Combine GVCFs
gatk CombineGVCFs \
    -R reference.fa \
    -V sample1.g.vcf.gz \
    -V sample2.g.vcf.gz \
    -V sample3.g.vcf.gz \
    -O cohort.g.vcf.gz

# Step 2: Genotype
#gatk GenotypeGVCFs \
#    -R reference.fa \
#    -V cohort.g.vcf.gz \
#    -O cohort.vcf.gz
```

**Alternative: Direct calling for single sample:**
```bash
gatk HaplotypeCaller \
    -R reference.fa \
    -I sample.recal.bam \
    -O sample.vcf.gz
```

### Option B: BCFTools (fast, lightweight)

```bash
# Quick variant calling (single sample)
bcftools mpileup -Ou -f reference.fa -q 20 -Q 20 sample.bam | \
    bcftools call -mv -Oz -o sample.vcf.gz

bcftools index sample.vcf.gz

# Parameters:
# -q 20 : Min mapping quality
# -Q 20 : Min base quality
# -m    : Multi-allelic calling
# -v    : Output variants only

# Multiple samples
bcftools mpileup -Ou -f reference.fa sample1.bam sample2.bam | \
    bcftools call -mv -Oz -o cohort.vcf.gz
```

### Option C: FreeBayes

```bash
# Single sample
freebayes -f reference.fa --pooled-continuous sample.bam > sample.vcf

# Multiple samples
freebayes -f reference.fa sample1.bam sample2.bam sample3.bam > cohort.vcf

# Target specific region
freebayes -f reference.fa -r chr1:10000-20000 sample.bam > region.vcf

# Parallel by region (faster for whole genome)
freebayes-parallel <(fasta_generate_regions.py reference.fa 100000) 8 \
    -f reference.fa sample.bam > sample.vcf
```

## 4. Variant Filtering

### GATK VQSR (for 30+ samples)

**SNP recalibration:**
```bash
# Build SNP recalibration model
gatk VariantRecalibrator \
    -R reference.fa \
    -V cohort.vcf.gz \
    --resource:hapmap,known=false,training=true,truth=true,prior=15.0 hapmap.vcf.gz \
    --resource:omni,known=false,training=true,truth=true,prior=12.0 omni.vcf.gz \
    --resource:1000G,known=false,training=true,truth=false,prior=10.0 1000G.vcf.gz \
    --resource:dbsnp,known=true,training=false,truth=false,prior=2.0 dbsnp.vcf.gz \
    -an QD -an MQ -an MQRankSum -an ReadPosRankSum -an FS -an SOR \
    -mode SNP \
    -O snp.recal \
    --tranches-file snp.tranches

# Apply recalibration
gatk ApplyVQSR \
    -R reference.fa \
    -V cohort.vcf.gz \
    --recal-file snp.recal \
    --tranches-file snp.tranches \
    --truth-sensitivity-filter-level 99.5 \
    -mode SNP \
    -O cohort.snp.vqsr.vcf.gz

# Repeat for INDELs
```

### Hard Filtering (small cohorts or targeted sequencing)

**GATK hard filters:**
```bash
# SNP filtering
gatk VariantFiltration \
    -V cohort.vcf.gz \
    -O cohort.filtered.vcf.gz \
    --filter-name "QD2" --filter-expression "QD < 2.0" \
    --filter-name "QUAL30" --filter-expression "QUAL < 30.0" \
    --filter-name "SOR3" --filter-expression "SOR > 3.0" \
    --filter-name "FS60" --filter-expression "FS > 60.0" \
    --filter-name "MQ40" --filter-expression "MQ < 40.0" \
    --filter-name "MQRankSum-12.5" --filter-expression "MQRankSum < -12.5" \
    --filter-name "ReadPosRankSum-8" --filter-expression "ReadPosRankSum < -8.0"

# Indel filtering
gatk VariantFiltration \
    -V cohort.filtered.vcf.gz \
    -O cohort.final.vcf.gz \
    --filter-name "QD2" --filter-expression "QD < 2.0" \
    --filter-name "QUAL30" --filter-expression "QUAL < 30.0" \
    --filter-name "FS200" --filter-expression "FS > 200.0" \
    --filter-name "SOR10" --filter-expression "SOR > 10.0"
```

**BCFTools filtering:**
```bash
# Comprehensive filter
bcftools filter -s LowQual \
    -e 'QUAL<30 || INFO/DP<10 || MQ<40 || QD<2' \
    -Oz -o cohort.filtered.vcf.gz cohort.vcf.gz

# Extract PASS variants only
bcftools view -f PASS cohort.filtered.vcf.gz -Oz -o cohort.pass.vcf.gz

# Complex filter with multiple conditions
bcftools filter -i 'INFO/DP>10 && QUAL>30 && MQ>40 && QD>2 && FS<60 && SOR<3' \
    -Oz -o cohort.filtered.vcf.gz cohort.vcf.gz
```

## 5. Variant Annotation

### VEP (Ensembl Variant Effect Predictor)

```bash
# Basic annotation
vep -i cohort.filtered.vcf.gz \
    -o cohort.vep.vcf.gz \
    --vcf \
    --cache \
    --assembly GRCh38 \
    --dir_cache ~/.vep \
    --fasta reference.fa \
    --fork 4 \
    --variant_class \
    --symbol \
    --canonical

# With ClinVar and gnomAD
vep -i cohort.filtered.vcf.gz \
    -o cohort.vep.vcf.gz \
    --vcf \
    --cache \
    --assembly GRCh38 \
    --custom clinvar.vcf.gz,ClinVar,vcf,exact,0,CLNSIG,CLNREVSTAT \
    --custom gnomad.genomes.vcf.gz,gnomAD,vcf,exact,0,AF,AF_afr,AF_amr,AF_eas,AF_nfe \
    --plugin CADD,whole_genome_SNVs.tsv.gz \
    --fork 4
```

### SnpEff

```bash
# Annotate
java -jar snpEff.jar GRCh38.99 cohort.filtered.vcf.gz > cohort.annotated.vcf

# Generate report
java -jar snpEff.jar dump GRCh38.99 > snpeff_report.html

# Filter by impact
java -jar snpEff.jar filter "(EFFECT has 'missense_variant')" \
    cohort.annotated.vcf > missense.vcf
```

### ANNOVAR

```bash
# Convert to ANNOVAR format
convert2annovar.pl -format vcf4 cohort.filtered.vcf.gz > cohort.avinput

# Annotate
table_annovar.pl cohort.avinput humandb/ \
    -buildver hg38 \
    -out cohort.annovar \
    -remove \
    -protocol refGene,cytoBand,exac03,avsnp147,dbnsfp42a,clinvar_20220320 \
    -operation g,r,f,f,f,f \
    -nastring . \
    -vcfinput \
    -polish
```

## 6. Variant Query and Analysis

### BCFTools Queries

```bash
# Extract to table
bcftools query -f '%CHROM\t%POS\t%REF\t%ALT\t%QUAL\t%FILTER\t%INFO/GENE\n' \
    annotated.vcf.gz > variants.txt

# With sample genotypes
bcftools query -f '%CHROM:%POS\t%REF/%ALT\t[%GT\t]\n' \
    -H annotated.vcf.gz > genotypes.txt

# Filter by gene
bcftools view -i 'ANN~"BRCA1"' annotated.vcf.gz

# Coding variants only
bcftools view -i 'ANN~"missense_variant|stop_gained|frameshift|splice"' \
    annotated.vcf.gz

# Rare variants (gnomAD AF < 1%)
bcftools view -i 'gnomAD_AF<0.01 || gnomAD_AF="."' annotated.vcf.gz

# Combined filter
bcftools view -i 'ANN~"missense" && (gnomAD_AF<0.01 || gnomAD_AF=".") && QUAL>100' \
    annotated.vcf.gz
```

### Calculate Concordance

```bash
# Compare two VCFs
bcftools gtcheck -g query.vcf.gz reference.vcf.gz
```

## Complete Pipeline Script

```bash
#!/bin/bash
# variant_calling.sh

set -euo pipefail

REF="reference.fa"
DBSNP="dbsnp.vcf.gz"
SAMPLE=$1

mkdir -p aligned variants logs

echo "=== Step 1: Alignment ==="
bwa mem -t 8 -R "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA" \
    $REF ${SAMPLE}_R1.fq.gz ${SAMPLE}_R2.fq.gz | \
    samtools sort -o aligned/${SAMPLE}.bam -
samtools index aligned/${SAMPLE}.bam

echo "=== Step 2: Mark Duplicates ==="
picard MarkDuplicates \
    I=aligned/${SAMPLE}.bam \
    O=aligned/${SAMPLE}.dedup.bam \
    M=logs/${SAMPLE}.dup_metrics \
    CREATE_INDEX=true

echo "=== Step 3: Variant Calling ==="
gatk HaplotypeCaller \
    -R $REF \
    -I aligned/${SAMPLE}.dedup.bam \
    -O variants/${SAMPLE}.vcf.gz

echo "=== Step 4: Filtering ==="
bcftools filter -s LowQual -e 'QUAL<30' \
    -Oz -o variants/${SAMPLE}.filtered.vcf.gz \
    variants/${SAMPLE}.vcf.gz

echo "Done: variants/${SAMPLE}.filtered.vcf.gz"
```

## QC Metrics

| Metric | Good | Warning | Bad |
|--------|------|---------|-----|
| Ti/Tv ratio | 2.0-2.2 | 1.8-2.0 or 2.2-2.4 | <1.8 or >2.4 |
| Het/Hom ratio | 1.5-2.0 | 1.0-1.5 or 2.0-3.0 | <1.0 or >3.0 |
| dbSNP concordance | >85% | 70-85% | <70% |
| Mean depth | 20-60x | 10-20x or 60-100x | <10x or >100x |

## Related Skills

- bio-variant-variant-calling-bcftools - BCFTools specific workflows
- bio-variant-vqsr-recalibration - Detailed VQSR parameters
- bio-variant-annotation-vep - VEP annotation details
- bio-alignment-files-bam-statistics - BAM quality metrics
- bio-causal-genomics-mendelian-randomization - Variant interpretation
