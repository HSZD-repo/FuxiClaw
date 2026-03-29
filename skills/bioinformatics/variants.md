# 变异检测流程

## 标准流程（GATK Best Practices）

```
原始 FASTQ → QC → 比对 → BAM 处理 → 变异检测 → 过滤 → 注释
```

## 1. 数据预处理

```bash
# 比对（带 Read Group）
bwa mem -t 8 -R '@RG\tID:sample\tSM:sample\tLB:lib1\tPL:ILLUMINA' \
    reference.fa R1.fq.gz R2.fq.gz | \
    samtools sort -o sample.sorted.bam -

samtools index sample.sorted.bam
```

## 2. BAM 处理（GATK）

```bash
# 标记重复
picard MarkDuplicates \
    I=sample.sorted.bam \
    O=sample.dedup.bam \
    M=sample.metrics.txt \
    REMOVE_DUPLICATES=false

samtools index sample.dedup.bam

# Base Quality Score Recalibration (BQSR)
gatk BaseRecalibrator \
    -R reference.fa \
    -I sample.dedup.bam \
    --known-sites dbsnp.vcf.gz \
    --known-sites mills_indels.vcf.gz \
    -O sample.recal_data.table

gatk ApplyBQSR \
    -R reference.fa \
    -I sample.dedup.bam \
    --bqsr-recal-file sample.recal_data.table \
    -O sample.recal.bam

samtools index sample.recal.bam
```

## 3. 变异检测

### GATK HaplotypeCaller

```bash
# 单样本
# 单个区域（测试用）
gatk HaplotypeCaller \
    -R reference.fa \
    -I sample.recal.bam \
    -O sample.g.vcf.gz \
    -ERC GVCF \
    -L chr1:1000000-2000000

# 全基因组
gatk HaplotypeCaller \
    -R reference.fa \
    -I sample.recal.bam \
    -O sample.g.vcf.gz \
    -ERC GVCF

# 合并多个样本的 gVCF
gatk CombineGVCFs \
    -R reference.fa \
    -V sample1.g.vcf.gz \
    -V sample2.g.vcf.gz \
    -O cohort.g.vcf.gz

# 联合基因分型
gatk GenotypeGVCFs \
    -R reference.fa \
    -V cohort.g.vcf.gz \
    -O cohort.vcf.gz
```

### 替代方案：BCFTools

```bash
# 快速变异检测（单样本）
bcftools mpileup -Ou -f reference.fa -q 20 -Q 20 sample.bam | \
    bcftools call -mv -Oz -o sample.vcf.gz

bcftools index sample.vcf.gz

# 多样本
bcftools mpileup -Ou -f reference.fa sample1.bam sample2.bam | \
    bcftools call -mv -Oz -o cohort.vcf.gz
```

### FreeBayes

```bash
# 单样本
freebayes -f reference.fa --pooled-continuous sample.bam > sample.vcf

# 多样本
freebayes -f reference.fa sample1.bam sample2.bam sample3.bam > cohort.vcf

# 目标区域
freebayes -f reference.fa -r chr1:10000-20000 sample.bam > region.vcf
```

## 4. 变异过滤

### VQSR（GATK，推荐用于 30+ 样本）

```bash
# SNP VQSR
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

gatk ApplyVQSR \
    -R reference.fa \
    -V cohort.vcf.gz \
    --recal-file snp.recal \
    --tranches-file snp.tranches \
    --truth-sensitivity-filter-level 99.5 \
    -mode SNP \
    -O cohort.vqsr.vcf.gz
```

### 硬过滤（小样本或目标测序）

```bash
# GATK 硬过滤 SNP
gatk VariantFiltration \
    -V cohort.vcf.gz \
    -O cohort.filtered.vcf.gz \
    --filter-name "QD2" --filter-expression "QD < 2.0" \
    --filter-name "QUAL30" --filter-expression "QUAL < 30.0" \
    --filter-name "SOR3" --filter-expression "SOR > 3.0" \
    --filter-name "FS60" --filter-expression "FS > 60.0" \
    --filter-name "MQ40" --filter-expression "MQ < 40.0"

# BCFTools 过滤
bcftools filter -s LowQual -e 'QUAL<30 || INFO/DP<10 || MQ<40' \
    -Oz -o cohort.filtered.vcf.gz cohort.vcf.gz
```

## 5. 变异注释

### VEP (Ensembl Variant Effect Predictor)

```bash
# 基本注释
vep -i cohort.filtered.vcf.gz \
    -o cohort.vep.vcf.gz \
    --vcf \
    --cache \
    --assembly GRCh38 \
    --dir_cache ~/.vep \
    --fasta reference.fa \
    --fork 4 \
    --variant_class \
    --symbol

# 带 ClinVar 和 gnomAD
vep -i cohort.filtered.vcf.gz \
    -o cohort.vep.vcf.gz \
    --vcf \
    --cache \
    --assembly GRCh38 \
    --custom clinvar.vcf.gz,ClinVar,vcf,exact,0,CLNSIG \
    --custom gnomad.genomes.vcf.gz,gnomAD,vcf,exact,0,AF
```

### SnpEff

```bash
# 注释
java -jar snpEff.jar GRCh38.99 cohort.filtered.vcf.gz > cohort.annotated.vcf

# 生成报告
java -jar snpEff.jar dump GRCh38.99 > report.html
```

### ANNOVAR

```bash
# 转换为 ANNOVAR 格式
convert2annovar.pl -format vcf4 cohort.filtered.vcf.gz > cohort.avinput

# 注释
table_annovar.pl cohort.avinput humandb/ \
    -buildver hg38 \
    -out cohort.annovar \
    -remove \
    -protocol refGene,cytoBand,exac03,avsnp147,dbnsfp30a \
    -operation g,r,f,f,f \
    -nastring . \
    -vcfinput
```

## 6. 变异查询与过滤

```bash
# 按基因过滤
bcftools view -i 'ANN~"BRCA1"' annotated.vcf.gz

# 只保留外显子变异
bcftools view -i 'ANN~"missense_variant|stop_gained|frameshift"' annotated.vcf.gz

# 罕见变异 (gnomAD AF < 0.01)
bcftools view -i 'gnomAD_AF<0.01 || gnomAD_AF="."' annotated.vcf.gz

# 提取为表格
bcftools query -f '%CHROM\t%POS\t%REF\t%ALT\t%QUAL\t%FILTER\t%INFO/GENE\n' \
    annotated.vcf.gz > variants.txt
```

## 完整脚本示例

```bash
#!/bin/bash
# variant_calling.sh

REF="reference.fa"
DBSNP="dbsnp.vcf.gz"
SAMPLE=$1

# 比对
bwa mem -t 8 -R "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA" \
    $REF ${SAMPLE}_R1.fq.gz ${SAMPLE}_R2.fq.gz | \
    samtools sort -o ${SAMPLE}.bam -
samtools index ${SAMPLE}.bam

# 标记重复
picard MarkDuplicates I=${SAMPLE}.bam O=${SAMPLE}.dedup.bam M=${SAMPLE}.metrics
samtools index ${SAMPLE}.dedup.bam

# 变异检测
gatk HaplotypeCaller -R $REF -I ${SAMPLE}.dedup.bam -O ${SAMPLE}.vcf.gz

# 过滤
bcftools filter -s LowQual -e 'QUAL<30' -Oz -o ${SAMPLE}.filtered.vcf.gz ${SAMPLE}.vcf.gz

echo "Done: ${SAMPLE}.filtered.vcf.gz"
```
