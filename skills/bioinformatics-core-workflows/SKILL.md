---
name: bioinformatics-core-workflows
description: >
  Core bioinformatics workflows and best practices for sequence analysis, 
  genomic data processing, and sequencing pipelines. Covers essential principles 
  including QC, reference genome management, data integrity, resource awareness, 
  and reproducibility. Use when starting bioinformatics projects or training 
  team members on best practices.
license: MIT
category: bioinformatics
tags: [workflows, best-practices, qc, reproducibility, fundamentals]
---

# Bioinformatics Core Workflows

Essential principles and workflows for bioinformatics analysis. This skill provides foundational knowledge before diving into specific analysis pipelines.

## The Five Golden Rules

### 1. Verify Input Quality First

Before any analysis, check your data quality. Garbage in → garbage out.

**For FASTQ:**
```bash
# Quality report
fastqc sample.fastq.gz -o qc_reports/

# Check for adapter contamination
fastp -i sample.fq.gz --detect_adapter_for_pe -j report.json
```

**For BAM:**
```bash
# Verify sorted and indexed
samtools quickcheck aligned.bam

# Get alignment statistics
samtools flagstat aligned.bam
```

**For VCF:**
```bash
# Validate format
bcftools view -h variants.vcf.gz > /dev/null && echo "Valid VCF"
```

### 2. Use Reference Genome Consistently

Track which reference you use per project. Mixing references = invalid results.

| Species | Preferred | Legacy | Notes |
|---------|-----------|--------|-------|
| Human | GRCh38/hg38 | GRCh37/hg19 | Use GRCh38 for new projects |
| Mouse | GRCm39/mm39 | GRCm38/mm10 | Check compatibility |
| Yeast | R64-1-1 | - | S. cerevisiae |

**Document in your project:**
```markdown
## Reference Genome
- Species: Homo sapiens
- Version: GRCh38/hg38
- Path: /data/references/hg38/hg38.fa
- Source: GENCODE Release 44
```

### 3. Preserve Raw Data

**NEVER modify original FASTQ/BAM files.**

```bash
# Make data read-only
chmod 444 raw_data/*.fastq.gz

# Work on copies
cp raw_data/sample.fq.gz working_data/

# Log every transformation
ls -lh raw_data/ > data_manifest.txt
md5sum raw_data/* > checksums.md5
```

### 4. Resource Awareness

Bioinformatics operations can consume massive resources. Check before you run.

| Operation | Memory | Time | Check Command |
|-----------|--------|------|---------------|
| BWA MEM (human) | ~6GB | 2-4h | `ls -lh reference.fa` |
| STAR indexing | ~32GB | 1-2h | Free RAM |
| GATK HaplotypeCaller | ~4GB | Variable | `java -Xmx4g` |
| Samtools sort | ~2GB | Minutes | `samtools sort -m 2G` |

**Estimate file sizes:**
```bash
# Check before operations
ls -lh input.bam  # Is it 1GB or 100GB?
du -sh working_dir/  # Disk space available?
```

**Stream when possible:**
```bash
# Good: Stream to avoid intermediate files
bwa mem ref.fa R1.fq R2.fq | samtools sort -o out.bam -

# Bad: Creates large intermediate SAM
bwa mem ref.fa R1.fq R2.fq > out.sam
samtools sort out.sam -o out.bam
```

### 5. Ensure Reproducibility

Every analysis must be reproducible.

**Log tool versions:**
```bash
# Create versions.txt
samtools --version >> versions.txt
bwa 2>&1 | head -1 >> versions.txt
bcftools --version >> versions.txt
python --version >> versions.txt
```

**Save command parameters:**
```bash
# Save the exact command
#!/bin/bash
# analysis.sh
set -euo pipefail

bwa mem -t 8 -R '@RG\tID:sample\tSM:sample\tPL:ILLUMINA' \
    ref.fa R1.fq R2.fq | \
    samtools sort -o out.bam -
```

**Record input checksums:**
```bash
# For critical analyses
md5sum input.fastq.gz >> analysis_manifest.txt
date >> analysis_manifest.txt
```

## Common Traps

| Trap | Symptom | Solution |
|------|---------|----------|
| **Chromosome naming** | chr1 vs 1 causes silent failures | `sed 's/^chr//'` or check reference |
| **Unsorted BAM** | Tools fail or wrong results | `samtools sort` first |
| **Missing index** | Cryptic errors | `samtools index` for BAM, `bcftools index` for VCF |
| **Memory exhaustion** | Session killed | Stream operations, use `-m` for sort |
| **Stale indices** | Corrupt reads | Regenerate index after modifying |
| **Coordinate systems** | Off-by-one errors | BED=0-based, VCF/GFF=1-based |

### Chromosome Naming Fix

```bash
# Remove 'chr' prefix
sed 's/^chr//' regions.bed > regions_fixed.bed

# Add 'chr' prefix
awk '{print "chr" $0}' regions.txt > regions_with_chr.txt
```

### Coordinate Conversion

```bash
# BED (0-based) to VCF (1-based)
awk '{print $1, $2+1, $3}' regions.bed

# VCF (1-based) to BED (0-based)
awk '{print $1, $2-1, $2}' variants.txt
```

## File Formats Quick Reference

| Format | Purpose | Key Tool |
|--------|---------|----------|
| FASTA | Reference sequences | `samtools faidx` |
| FASTQ | Raw reads + quality | `seqtk`, `fastp` |
| SAM/BAM | Aligned reads | `samtools` |
| VCF/BCF | Variants | `bcftools` |
| BED | Genomic intervals | `bedtools` |
| GFF/GTF | Gene annotations | `gffread` |
| BigWig | Coverage tracks | `deepTools` |

## Essential Commands by Task

### Quality Control

```bash
# FASTQ QC
fastqc sample.fastq.gz -o qc_reports/
multiqc qc_reports/ -o multiqc_report/

# Adapter trimming
fastp -i R1.fq.gz -I R2.fq.gz -o R1.clean.fq.gz -O R2.clean.fq.gz

# BAM statistics
samtools flagstat aligned.bam
samtools stats aligned.bam > stats.txt
```

### Alignment

```bash
# Index reference (once)
bwa index reference.fa

# Align paired-end
bwa mem -t 8 reference.fa R1.fq.gz R2.fq.gz | \
    samtools sort -o aligned.bam -

# Index BAM
samtools index aligned.bam
```

### Variant Calling

```bash
# Call variants
bcftools mpileup -Ou -f reference.fa aligned.bam | \
    bcftools call -mv -Oz -o variants.vcf.gz

# Index VCF
bcftools index variants.vcf.gz

# Filter
bcftools filter -s LowQual -e 'QUAL<20' variants.vcf.gz
```

### Data Manipulation

```bash
# Extract region
samtools view -b aligned.bam chr1:1000000-2000000 > region.bam

# BAM to FASTQ
samtools fastq -1 R1.fq.gz -2 R2.fq.gz aligned.bam

# Merge BAMs
samtools merge merged.bam sample1.bam sample2.bam

# Subset VCF by region
bcftools view -r chr1:1000-2000 variants.vcf.gz
```

## Project Directory Structure

```
project/
├── raw_data/           # Original FASTQ (READ-ONLY)
├── processed/          # Cleaned data
│   ├── fastq/         # Trimmed FASTQ
│   └── bam/           # Aligned BAM
├── results/           # Analysis outputs
│   ├── qc/            # QC reports
│   ├── variants/      # VCF files
│   └── counts/        # Expression counts
├── logs/              # Analysis logs
├── scripts/           # Reproducible scripts
├── docs/              # Documentation
└── README.md          # Project overview
```

## Workflow Checklist

Before starting:
- [ ] Tool versions documented
- [ ] Reference genome chosen and indexed
- [ ] Disk space sufficient (3-5x input size)
- [ ] Project structure created

During analysis:
- [ ] QC on raw data
- [ ] Log all commands
- [ ] Check intermediate results
- [ ] Monitor resource usage

After completion:
- [ ] Verify output files
- [ ] Document parameters used
- [ ] Archive checksums
- [ ] Clean temporary files

## Security & Privacy

- Only read files user explicitly provides
- Write outputs to user-specified directories
- All sequence data processed locally
- No external API calls during analysis

## Related Skills

- bio-alignment-pairwise - Pairwise sequence alignment
- bio-alignment-files-bam-statistics - Detailed BAM statistics
- bio-rnaseq-fastqc-trimming - RNA-seq QC and trimming
- bio-variant-variant-calling-bcftools - Variant calling
- bio-scrnaseq-qc - Single-cell RNA-seq QC
- bio-atac-seq-qc - ATAC-seq quality control

## Resources

- [Samtools Documentation](http://www.htslib.org/doc/)
- [BEDtools Documentation](https://bedtools.readthedocs.io/)
- [GATK Best Practices](https://gatk.broadinstitute.org/)
- [Biostars Community](https://www.biostars.org/)
