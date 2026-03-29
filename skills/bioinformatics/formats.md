# 生物信息学文件格式

## FASTA (.fa, .fasta)

参考序列格式。

```
>chr1
NNTAACCCTAACCCTAACCCTAACCCTAACCCTAACCCTAACCC
>chr2
NTAACCCTAACCCTAACCCTAACCCTAACCCTAACCCTAACCCC
```

**常用命令：**
```bash
# 索引（创建 .fai）
samtools faidx reference.fa

# 提取序列
samtools faidx reference.fa chr1:1000-2000

# 统计
grep -c "^>" reference.fa    # 序列数量
awk '/^>/ {print}' reference.fa  # 提取序列名
```

## FASTQ (.fq, .fastq, .fq.gz)

原始测序数据 + 质量分数。

```
@SEQ_ID
GATTTGGGGTTCAAAGCAGTATCGATCAAATAGTAAATCCATTTGTTCAACTCACAGTTT
+
!''*((((***+))%%%++)(%%%%).1***-+*''))**55CCF>>>>>>CCCCCCC65
```

**格式：**
- 第1行: `@` + 序列 ID
- 第2行: 碱基序列
- 第3行: `+` (+ 可选的重复 ID)
- 第4行: 质量分数 (Phred+33)

**常用命令：**
```bash
# 统计读取数
zcat sample.fq.gz | wc -l | awk '{print $1/4}'

# 提取前 N 条读取
seqtk sample.fq.gz 1000 > subset.fq

# 转换质量编码
seqtk seq -Q64 -V old.fq > new.fq

# FASTQ 转 FASTA
seqtk seq -A sample.fq.gz > sample.fa
```

## SAM/BAM (.sam, .bam)

序列比对格式。

**SAM 格式（文本）：**
```
@HD	VN:1.6	SO:coordinate
@SQ	SN:chr1	LN:248956422
read1	99	chr1	1000	60	100M	=	1200	300	AGCT...	AAFF...
```

**BAM：SAM 的二进制压缩版本（推荐）**

**常用命令：**
```bash
# SAM 转 BAM
samtools view -bS input.sam > output.bam

# 排序
samtools sort input.bam -o sorted.bam

# 索引（必需用于随机访问）
samtools index sorted.bam

# 查看比对
samtools view sorted.bam chr1:1000-2000

# 统计
samtools flagstat sorted.bam
samtools idxstats sorted.bam
samtools stats sorted.bam > stats.txt

# 提取未比对 reads
samtools view -f 4 input.bam

# 提取比对 reads
samtools view -F 4 input.bam
```

## VCF/BCF (.vcf, .vcf.gz, .bcf)

变异调用格式。

```
##fileformat=VCFv4.2
##reference=hg38.fa
#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO	FORMAT	SAMPLE
chr1	1234567	rs123	A	G	99	PASS	DP=35;AF=0.5	GT:AD:GQ	0/1:17,18:99
```

**常用命令：**
```bash
# VCF 压缩和索引
bgzip variants.vcf
bcftools index variants.vcf.gz

# 查看头部
bcftools view -h variants.vcf.gz

# 按区域提取
bcftools view -r chr1:1000-2000 variants.vcf.gz

# 按样本提取
bcftools view -s SAMPLE1,SAMPLE2 variants.vcf.gz

# 统计
bcftools stats variants.vcf.gz > vcf_stats.txt

# 过滤
bcftools filter -e 'QUAL<20 || DP<10' variants.vcf.gz

# VCF 转 BCF（更小更快）
bcftools view -Ob -o variants.bcf variants.vcf.gz
```

## BED (.bed)

基因组区间格式（0-based）。

```
chr1	1000	2000	region1	0	+
chr1	3000	4000	region2	0	-
chr2	5000	6000	region3	0	.
```

**列：** chrom, start(0-based), end, name, score, strand

**常用命令：**
```bash
# BED 排序
sort -k1,1 -k2,2n regions.bed > regions.sorted.bed

# 区间交集
bedtools intersect -a regions.bed -b genes.bed

# 区间覆盖
bedtools coverage -a regions.bed -b alignments.bam

# 扩展区间
bedtools slop -i regions.bed -g genome.sizes -b 100

# 获取序列
bedtools getfasta -fi reference.fa -bed regions.bed
```

## GFF/GTF (.gff, .gtf)

基因注释格式。

```
chr1	HAVANA	gene	11869	14409	.	+	.	gene_id="ENSG00000223972";gene_name="DDX11L1"
chr1	HAVANA	transcript	11869	14409	.	+	.	gene_id="ENSG00000223972";transcript_id="ENST00000456328"
```

**GTF = GFF 版本 2.5（更严格的格式）**

**常用命令：**
```bash
# GTF 转 BED
awk '$3=="gene" {print $1,$4-1,$5,$10,0,$7}' genes.gtf | tr -d '";' > genes.bed

# 提取转录本序列
gffread -w transcripts.fa -g reference.fa annotations.gtf

# 统计基因数
grep -c '\tgene\t' annotations.gtf
```

## BigWig (.bw, .bigwig)

基因组覆盖度/信号轨迹（二进制、索引）。

**用途：**
- 可视化覆盖度轨迹
- 快速查询区域信号
- 基因组浏览器 (IGV, UCSC)

**常用命令：**
```bash
# BAM 转 BigWig
bamCoverage -b aligned.bam -o coverage.bw

# BedGraph 转 BigWig
bedGraphToBigWig input.bedgraph chrom.sizes output.bw

# 提取区域值
bigWigToBedGraph input.bw chr1:1000-2000 stdout
```

## 坐标系统

| 格式 | 系统 | 示例 |
|------|------|------|
| BED | 0-based, half-open | `chr1 0 100` = 第 1-100 位 |
| VCF | 1-based, inclusive | `chr1 100` = 第 100 位 |
| GFF/GTF | 1-based, inclusive | `chr1 100 200` = 第 100-200 位 |
| SAM | 1-based | POS 字段 |

**转换：**
```bash
# BED (0-based) to VCF (1-based)
awk '{print $1,$2+1}' regions.bed

# VCF (1-based) to BED (0-based)
awk '{print $1,$2-1,$2}' variants.txt
```
