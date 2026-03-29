---
name: bio-formats-reference
description: >
  Comprehensive reference guide for bioinformatics file formats including FASTA, 
  FASTQ, SAM/BAM, VCF/BCF, BED, GFF/GTF, and BigWig. Use when converting between 
  formats, understanding format specifications, or troubleshooting format-related 
  issues.
license: MIT
category: bioinformatics
tags: [file-formats, reference, fasta, fastq, sam, bam, vcf, bed]
---

# Bioinformatics File Formats Reference

Comprehensive guide to common bioinformatics file formats, their specifications, and manipulation tools.

## FASTA (.fa, .fasta)

Reference sequence format.

```
>chr1
NNTAACCCTAACCCTAACCCTAACCCTAACCCTAACCCTAACCC
>chr2
NTAACCCTAACCCTAACCCTAACCCTAACCCTAACCCTAACCCC
```

**Structure:**
- Header line starts with `>` followed by sequence identifier
- Sequence lines follow (usually 60-80 characters per line)

**Common Commands:**
```bash
# Index (creates .fai file)
samtools faidx reference.fa

# Extract specific region
samtools faidx reference.fa chr1:1000-2000

# Count sequences
grep -c "^>" reference.fa

# Extract sequence names
awk '/^>/ {print $1}' reference.fa | sed 's/^>//'

# Get sequence lengths
awk '/^>/ {if (seq) print name, length(seq); name=substr($0,2); seq=""; next} {seq=seq$0} END {print name, length(seq)}' reference.fa
```

## FASTQ (.fq, .fastq, .fq.gz)

Raw sequencing data with quality scores.

```
@SEQ_ID
GATTTGGGGTTCAAAGCAGTATCGATCAAATAGTAAATCCATTTGTTCAACTCACAGTTT
+
!''*((((***+))%%%++)(%%%%).1***-+*''))**55CCF>>>>>>CCCCCCC65
```

**Structure (4 lines per read):**
1. `@` + Sequence identifier
2. Nucleotide sequence
3. `+` (optionally followed by repeated ID)
4. Quality scores (Phred+33 for Sanger)

**Quality Score Encoding:**
| Format | Offset | Range |
|--------|--------|-------|
| Sanger/Illumina 1.8+ | 33 | !-~ (0-93) |
| Illumina 1.3-1.7 | 64 | @-~ (0-62) |
| Solexa | 64 | ;-~ (-5-62) |

**Common Commands:**
```bash
# Count reads (4 lines per read)
zcat sample.fq.gz | wc -l | awk '{print $1/4}'

# Extract first N reads
seqtk sample.fq.gz 1000 > subset.fq

# Convert quality encoding
seqtk seq -Q64 -V old.fq > new.fq

# FASTQ to FASTA
seqtk seq -A sample.fq.gz > sample.fa

# Check quality encoding
head -4 sample.fq | tail -1 | od -c | head -1

# Split paired-end file (interleaved)
seqtk seq -1 interleaved.fq > R1.fq
seqtk seq -2 interleaved.fq > R2.fq
```

## SAM/BAM (.sam, .bam)

Sequence Alignment/Map format.

**SAM Format (text):**
```
@HD	VN:1.6	SO:coordinate
@SQ	SN:chr1	LN:248956422
@PG	ID:bwa	PN:bwa	VN:0.7.17
read1	99	chr1	1000	60	100M	=	1200	300	AGCT...	AAFF...
```

**Required SAM Fields:**
| Col | Field | Description |
|-----|-------|-------------|
| 1 | QNAME | Query template name |
| 2 | FLAG | Bitwise flag |
| 3 | RNAME | Reference sequence name |
| 4 | POS | 1-based leftmost position |
| 5 | MAPQ | Mapping quality |
| 6 | CIGAR | CIGAR string |
| 7 | RNEXT | Reference name of mate |
| 8 | PNEXT | Position of mate |
| 9 | TLEN | Template length |
| 10 | SEQ | Segment sequence |
| 11 | QUAL | ASCII quality |

**Common FLAG values:**
| FLAG | Meaning |
|------|---------|
| 1 | Paired |
| 2 | Proper pair |
| 4 | Unmapped |
| 8 | Mate unmapped |
| 16 | Reverse strand |
| 32 | Mate reverse strand |
| 64 | First in pair |
| 128 | Second in pair |
| 256 | Secondary alignment |
| 512 | QC fail |
| 1024 | PCR duplicate |
| 2048 | Supplementary |

**Common Commands:**
```bash
# SAM to BAM
samtools view -bS input.sam > output.bam

# Sort BAM
samtools sort input.bam -o sorted.bam

# Index BAM (required for random access)
samtools index sorted.bam

# View specific region
samtools view sorted.bam chr1:1000-2000

# View header only
samtools view -H sorted.bam

# Statistics
samtools flagstat sorted.bam
samtools idxstats sorted.bam
samtools stats sorted.bam > stats.txt

# Filter unmapped reads
samtools view -f 4 input.bam      # Only unmapped
samtools view -F 4 input.bam      # Only mapped

# Extract reads with specific FLAG
samtools view -f 0x2 input.bam    # Properly paired
```

## VCF/BCF (.vcf, .vcf.gz, .bcf)

Variant Call Format for genomic variants.

```
##fileformat=VCFv4.2
##reference=hg38.fa
##INFO=<ID=DP,Number=1,Type=Integer,Description="Total Depth">
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO	FORMAT	SAMPLE
chr1	1234567	rs123	A	G	99	PASS	DP=35;AF=0.5	GT:AD:GQ	0/1:17,18:99
```

**Required Fields:**
| Col | Field | Description |
|-----|-------|-------------|
| 1 | CHROM | Chromosome |
| 2 | POS | 1-based position |
| 3 | ID | Variant identifier |
| 4 | REF | Reference allele |
| 5 | ALT | Alternate allele(s) |
| 6 | QUAL | Quality score |
| 7 | FILTER | Filter status |
| 8 | INFO | Additional information |
| 9+ | FORMAT/samples | Genotype information |

**Common INFO fields:**
| Field | Description |
|-------|-------------|
| DP | Read depth |
| AF | Allele frequency |
| MQ | Mapping quality |
| QD | Quality by depth |
| FS | Fisher strand bias |
| SOR | Strand odds ratio |

**Common Commands:**
```bash
# Compress and index VCF
bgzip variants.vcf
bcftools index variants.vcf.gz

# View header
bcftools view -h variants.vcf.gz

# Extract region
bcftools view -r chr1:1000-2000 variants.vcf.gz

# Extract samples
bcftools view -s SAMPLE1,SAMPLE2 variants.vcf.gz

# Statistics
bcftools stats variants.vcf.gz > stats.txt

# Filter
bcftools filter -e 'QUAL<20 || DP<10' variants.vcf.gz
bcftools filter -i 'INFO/DP>10 && QUAL>30' variants.vcf.gz

# Query specific fields
bcftools query -f '%CHROM\t%POS\t%REF\t%ALT\t%QUAL\n' variants.vcf.gz
bcftools query -H -f '%CHROM\t%POS\t%ID\t%REF\t%ALT\t%QUAL\t%FILTER\n' variants.vcf.gz

# Merge VCFs
bcftools merge -Oz -o merged.vcf.gz sample1.vcf.gz sample2.vcf.gz

# Normalize (left-align indels)
bcftools norm -f ref.fa -Oz -o normalized.vcf.gz variants.vcf.gz

# Split multi-allelic sites
bcftools norm -m -both -Oz -o split.vcf.gz variants.vcf.gz
```

## BED (.bed)

Browser Extensible Data format for genomic intervals.

**Format (0-based, half-open):**
```
chr1	1000	2000	region1	0	+
chr1	3000	4000	region2	0	-
chr2	5000	6000	region3	0	.
```

**Columns:**
| Col | Field | Description |
|-----|-------|-------------|
| 1 | chrom | Chromosome |
| 2 | start | Start position (0-based) |
| 3 | end | End position (exclusive) |
| 4 | name | Feature name (optional) |
| 5 | score | Score (0-1000, optional) |
| 6 | strand | Strand (+/-/. optional) |

**Common Commands:**
```bash
# Sort BED (required for many tools)
sort -k1,1 -k2,2n regions.bed > regions.sorted.bed

# Intersection
bedtools intersect -a regions.bed -b genes.bed
bedtools intersect -a regions.bed -b genes.bed -v        # Not in genes
bedtools intersect -a regions.bed -b genes.bed -wa -wb   # Show both

# Coverage
bedtools coverage -a regions.bed -b alignments.bam
bedtools coverage -a regions.bed -b alignments.bam -counts

# Find closest features
bedtools closest -a variants.bed -b genes.bed

# Extend intervals
bedtools slop -i regions.bed -g genome.sizes -b 100

# Get sequences
bedtools getfasta -fi reference.fa -bed regions.bed -fo sequences.fa

# BAM to BED
bedtools bamtobed -i in.bam > out.bed

# Genome coverage
bedtools genomecov -ibam in.bam -bg > coverage.bedgraph

# Make windows
bedtools makewindows -g genome.sizes -w 10000 > windows.bed
```

## GFF/GTF (.gff, .gtf)

General Feature Format / Gene Transfer Format for annotations.

**GTF Format:**
```
chr1	HAVANA	gene	11869	14409	.	+	.	gene_id "ENSG00000223972"; gene_name "DDX11L1";
chr1	HAVANA	transcript	11869	14409	.	+	.	gene_id "ENSG00000223972"; transcript_id "ENST00000456328";
```

**Columns:**
| Col | Field |
|-----|-------|
| 1 | seqname (chromosome) |
| 2 | source |
| 3 | feature type (gene, transcript, exon, CDS) |
| 4 | start (1-based) |
| 5 | end (inclusive) |
| 6 | score |
| 7 | strand (+/-) |
| 8 | frame (0/1/2) |
| 9 | attributes (key-value pairs) |

**GFF3 vs GTF:**
| Format | Version | Attribute format |
|--------|---------|------------------|
| GTF | 2.5 | `key "value";` |
| GFF3 | 3 | `key=value;` |

**Common Commands:**
```bash
# GTF to BED (genes only)
awk '$3=="gene" {print $1,$4-1,$5,$10,0,$7}' genes.gtf | tr -d '";' > genes.bed

# Extract transcript sequences
gffread -w transcripts.fa -g reference.fa annotations.gtf

# Count features
grep -c '\tgene\t' annotations.gtf
grep -c '\texon\t' annotations.gtf
awk '$3=="gene" {count[$1]++} END {for(c in count) print c, count[c]}' annotations.gtf
```

## BigWig (.bw, .bigwig)

Binary indexed format for genomic signal data (coverage, scores).

**Use cases:**
- Genome browser tracks
- Coverage visualization
- Fast signal queries

**Common Commands:**
```bash
# BAM to BigWig (via bedGraph)
bamCoverage -b aligned.bam -o coverage.bw

# BedGraph to BigWig
bedGraphToBigWig input.bedgraph chrom.sizes output.bw

# Extract region values
bigWigToBedGraph input.bw chr1:1000-2000 stdout

# Get summary statistics
bigWigSummary input.bw chr1 0 1000000 10

# Get values at specific positions
bigWigAverageOverBed input.bw regions.bed out.tab
```

## Coordinate Systems

| Format | System | Example | Interpretation |
|--------|--------|---------|----------------|
| **BED** | 0-based, half-open | `chr1 0 100` | Bases 1-100 (100 bases) |
| **VCF** | 1-based, inclusive | `chr1 100` | Base 100 (1 base) |
| **GFF/GTF** | 1-based, inclusive | `chr1 100 200` | Bases 100-200 (101 bases) |
| **SAM** | 1-based | POS field | Base position |

**Conversion:**
```bash
# BED to VCF position
awk '{print $1, $2+1}' regions.bed

# VCF to BED
awk '{print $1, $2-1, $2}' variants.txt

# GTF start to BED start (already 0-based in conversion)
awk '{print $1, $4-1, $5}' genes.gtf
```

## Format Conversion Summary

| From | To | Command |
|------|-----|---------|
| SAM | BAM | `samtools view -bS in.sam > out.bam` |
| BAM | SAM | `samtools view -h in.bam > out.sam` |
| BAM | FASTQ | `samtools fastq -1 R1.fq -2 R2.fq in.bam` |
| VCF | BCF | `bcftools view -Ob -o out.bcf in.vcf` |
| BCF | VCF | `bcftools view -Ov -o out.vcf in.bcf` |
| GTF | BED | `awk '$3=="gene" {print $1,$4-1,$5}' in.gtf` |
| FASTQ | FASTA | `seqtk seq -A in.fq > out.fa` |
| BAM | BigWig | `bamCoverage -b in.bam -o out.bw` |

## Related Skills

- bio-alignment-files-bam-statistics - BAM statistics
- bio-variant-variant-calling-bcftools - VCF manipulation
- bio-alignment-pairwise - Sequence alignment
- bio-rnaseq-fastqc-trimming - FASTQ processing
