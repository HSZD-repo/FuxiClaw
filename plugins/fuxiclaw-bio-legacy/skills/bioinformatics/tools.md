# 生物信息学工具参考

## 核心工具

### Samtools

SAM/BAM 处理工具集。

```bash
# 查看
samtools view [options] in.bam [region]

# 常用选项
-b       # 输出 BAM
-h       # 包含 header
-H       # 只输出 header
-c       # 只计数
-f INT   # 必须包含的 flag
-F INT   # 必须排除的 flag
-q INT   # 最小比对质量

# 排序
samtools sort -o out.bam -@ 4 in.bam

# 索引
samtools index in.bam

# 合并
samtools merge out.bam in1.bam in2.bam in3.bam

# 统计
samtools flagstat in.bam          # 比对统计
samtools idxstats in.bam          # 每条染色体统计
samtools stats in.bam > out.txt   # 详细统计
samtools coverage in.bam          # 覆盖度

# FASTQ 提取
samtools fastq -1 R1.fq.gz -2 R2.fq.gz -0 unpaired.fq.gz in.bam

# 子集
samtools view -b -s 0.1 in.bam > 10percent.bam   # 10% 采样
```

### BWA

Burrows-Wheeler 比对工具。

```bash
# 索引参考
bwa index reference.fa

# MEM 算法（推荐用于 Illumina 70bp+）
bwa mem -t 8 -R '@RG\tID:sample\tSM:sample\tPL:ILLUMINA' \
    reference.fa R1.fq.gz R2.fq.gz | \
    samtools sort -o aligned.bam -

# 选项说明
-t INT    # 线程数
-R STR    # 读取组信息
-M        # 标记较短 split hits（GATK 兼容）

# 比对单端
bwa mem -t 8 reference.fa reads.fq.gz | samtools sort -o aligned.bam -

# 索引已存在时快速重新比对
bwa mem -t 8 reference.fa reads.fq.gz > aligned.sam
```

### BCFTools

VCF/BCF 操作工具。

```bash
# 变异检测流程
bcftools mpileup -Ou -f ref.fa -q 20 -Q 20 align.bam | \
    bcftools call -mv -Oz -o variants.vcf.gz

# mpileup 选项
-f FILE   # 参考 FASTA
-q INT    # 最小比对质量
-Q INT    # 最小碱基质量
-r STR    # 区域 chr:from-to

# call 选项
-m        # 多等位基因 calling
-v        # 只输出变异位点
-O z      # 压缩 VCF 输出

# 过滤
bcftools filter -s LowQual -e 'QUAL<20 || DP<10' in.vcf.gz
bcftools filter -i 'INFO/DP>10 && QUAL>30' in.vcf.gz

# 查询
bcftools query -f '%CHROM\t%POS\t%REF\t%ALT\n' in.vcf.gz
bcftools query -H -f '%CHROM\t%POS\t%ID\t%REF\t%ALT\t%QUAL\t%FILTER\n' in.vcf.gz

# 合并
bcftools merge -Oz -o merged.vcf.gz sample1.vcf.gz sample2.vcf.gz

# 统计
bcftools stats in.vcf.gz > stats.txt

# 归一化
bcftools norm -f ref.fa -Oz -o normalized.vcf.gz in.vcf.gz

# 拆分多等位基因
bcftools norm -m -both -Oz -o split.vcf.gz in.vcf.gz
```

### Bedtools

基因组区间操作工具。

```bash
# 交集
bedtools intersect -a regions.bed -b genes.bed
bedtools intersect -a regions.bed -b genes.bed -v        # 不在 genes 中的
bedtools intersect -a regions.bed -b genes.bed -wa -wb   # 输出原始区间

# 覆盖
bedtools coverage -a regions.bed -b alignments.bam
bedtools coverage -a regions.bed -b alignments.bam -counts   # 只计数

# 最近的
bedtools closest -a variants.bed -b genes.bed

# 排序（需要）
sort -k1,1 -k2,2n file.bed > file.sorted.bed

# 获取序列
bedtools getfasta -fi reference.fa -bed regions.bed -fo sequences.fa

# BAM 转 BED
bedtools bamtobed -i in.bam > out.bed

# 基因组覆盖
bedtools genomecov -ibam in.bam -bg > coverage.bedgraph

# 窗口
bedtools makewindows -g genome.sizes -w 10000 > windows.bed
```

## 质量控制

### FastQC

测序数据质量报告。

```bash
# 单样本
fastqc sample.fastq.gz -o qc_reports/

# 批量
fastqc *.fastq.gz -o qc_reports/

# 线程
fastqc -t 4 *.fastq.gz -o qc_reports/
```

### Fastp

快速 FASTQ 预处理。

```bash
# 基本修剪
fastp -i R1.fq.gz -o R1.clean.fq.gz

# 双端
fastp -i R1.fq.gz -I R2.fq.gz -o R1.clean.fq.gz -O R2.clean.fq.gz

# 质量过滤
fastp -i R1.fq.gz -o R1.clean.fq.gz \
    -q 20 -u 40 -l 50   # Q20, 40% 低质量, 最小 50bp

# 接头自动检测
fastp -i R1.fq.gz -I R2.fq.gz -o R1.clean.fq.gz -O R2.clean.fq.gz --detect_adapter_for_pe

# 生成报告
fastp -i R1.fq.gz -o R1.clean.fq.gz -j fastp.json -h fastp.html
```

### MultiQC

汇总多个 QC 报告。

```bash
# 汇总目录中所有 QC 结果
multiqc qc_reports/ -o multiqc_report/

# 特定模块
multiqc . --module fastqc --module samtools
```

## 比对工具

### Bowtie2

```bash
# 索引
bowtie2-build reference.fa reference

# 比对
bowtie2 -p 8 -x reference -1 R1.fq.gz -2 R2.fq.gz | \
    samtools sort -o aligned.bam -

# 本地比对（软裁剪）
bowtie2 --local -p 8 -x reference -U reads.fq.gz | samtools sort -o aligned.bam -
```

### HISAT2

RNA-seq 拼接比对。

```bash
# 构建索引
hisat2-build reference.fa reference

# 比对
hisat2 -p 8 -x reference -1 R1.fq.gz -2 R2.fq.gz | \
    samtools sort -o aligned.bam -

# 已知剪接位点
hisat2 -p 8 -x reference --known-splicesite-infile splicesites.txt \
    -1 R1.fq.gz -2 R2.fq.gz | samtools sort -o aligned.bam -
```

### STAR

快速 RNA-seq 比对。

```bash
# 生成索引（需要 32GB+ RAM）
STAR --runMode genomeGenerate \
    --genomeDir star_index/ \
    --genomeFastaFiles reference.fa \
    --sjdbGTFfile annotations.gtf \
    --runThreadN 16

# 比对
STAR --genomeDir star_index/ \
    --readFilesIn R1.fq.gz R2.fq.gz \
    --readFilesCommand zcat \
    --outFileNamePrefix sample_ \
    --outSAMtype BAM SortedByCoordinate \
    --runThreadN 8
```

## 变异检测

### FreeBayes

```bash
freebayes -f reference.fa --pooled-continuous \
    --min-coverage 10 \
    aligned.bam > variants.vcf
```

### DeepVariant

深度学习变异检测（需要 GPU 或较长 CPU 时间）。

```bash
# 使用 Singularity/Docker
singularity run deepvariant.sif \
    --model_type=WGS \
    --ref=reference.fa \
    --reads=aligned.bam \
    --output_vcf=variants.vcf.gz \
    --output_gvcf=variants.g.vcf.gz \
    --num_shards=8
```

## 实用技巧

### 管道技巧

```bash
# 一步比对 + 排序 + 索引
bwa mem -t 8 ref.fa R1.fq R2.fq | samtools sort -@ 4 -m 2G | samtools view -b > out.bam

# 过滤 + 统计
samtools view -h -q 30 -F 0x904 aligned.bam | samtools flagstat -

# 并行处理
ls *.bam | parallel 'samtools index {}'
```

### 检查文件完整性

```bash
# BAM
samtools quickcheck -v *.bam

# VCF
bcftools view -h variants.vcf.gz > /dev/null && echo "OK"

# FASTQ
zcat sample.fq.gz | head | wc -l   # 检查能否解压

# 计算校验和
md5sum file.bam > file.bam.md5
```
