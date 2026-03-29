# RNA-seq 分析流程

## 标准流程

```
原始 FASTQ → QC → 修剪 → 比对 → 定量 → 差异表达
```

## 1. 质量控制

```bash
# FastQC
fastqc sample_R1.fastq.gz sample_R2.fastq.gz -o qc/

# 批量
for r1 in *_R1.fastq.gz; do
    r2=${r1/_R1/_R2}
    fastqc "$r1" "$r2" -o qc/
done

# 汇总
multiqc qc/ -o multiqc_report/
```

## 2. 修剪

```bash
# Fastp - 自动检测接头
fastp -i sample_R1.fastq.gz -I sample_R2.fastq.gz \
    -o sample_R1.clean.fq.gz -O sample_R2.clean.fq.gz \
    --detect_adapter_for_pe \
    -q 20 -u 40 -l 20 \
    -j sample_fastp.json -h sample_fastp.html
```

## 3. 比对

### HISAT2（推荐，有拼接比对）

```bash
# 比对
hisat2 -p 8 \
    -x hisat2_index/reference \
    -1 sample_R1.clean.fq.gz \
    -2 sample_R2.clean.fq.gz \
    --rg-id sample --rg SM:sample --rg PL:ILLUMINA \
    2> sample.hisat2.log | \
    samtools sort -@ 4 -o sample.sorted.bam -

# 索引
samtools index sample.sorted.bam
```

### STAR（更快，需要更多内存）

```bash
# 比对
STAR --genomeDir star_index/ \
    --readFilesIn sample_R1.clean.fq.gz sample_R2.clean.fq.gz \
    --readFilesCommand zcat \
    --outFileNamePrefix sample_ \
    --outSAMtype BAM SortedByCoordinate \
    --runThreadN 8

mv sample_Aligned.sortedByCoord.out.bam sample.sorted.bam
samtools index sample.sorted.bam
```

## 4. 基因定量

### FeatureCounts

```bash
# 多样本
featureCounts -T 8 \
    -a annotations.gtf \
    -o all_samples.counts.txt \
    -t exon -g gene_id \
    *.sorted.bam
```

### Salmon

```bash
# 定量
salmon quant -i salmon_index \
    -l A \
    -1 sample_R1.clean.fq.gz \
    -2 sample_R2.clean.fq.gz \
    -p 8 \
    -o salmon/sample
```
