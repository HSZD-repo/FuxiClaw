# Bioinformatics Skill

生物信息学分析工具 - 处理生物序列、基因组数据和测序分析。

## 使用场景

- 分析生物序列（DNA/RNA/蛋白质）
- 运行基因组管道
- 解读测序数据
- 序列比对、变异检测、表达分析

## 核心原则

### 1. 先验证输入质量

任何分析前检查数据质量：
- **FASTQ**: 运行 FastQC，检查碱基质量、接头污染
- **BAM**: 验证排序、索引 (`samtools quickcheck`)
- **VCF**: 验证格式 (`bcftools view -h`)

垃圾输入 → 垃圾输出。始终先 QC。

### 2. 一致使用参考基因组

每个项目记录使用的参考：
- **人类**: GRCh38/hg38 (推荐) 或 GRCh37/hg19
- **小鼠**: GRCm39/mm39 或 GRCm38/mm10
- **混合参考 = 无效结果**

### 3. 保留原始数据

**永远不要修改原始 FASTQ/BAM 文件：**
- 在副本上工作
- 原始文件保持只读
- 记录每个转换步骤

### 4. 资源意识

生物信息学命令可能消耗大量资源：
- 操作前检查文件大小
- 尽可能使用流式处理 (`samtools view | ...`)
- 预估内存需求 (BWA: ~6GB 人类基因组)
- 超过 10 分钟的操作先警告

### 5. 可重现性

每个分析必须可重现：
- 记录工具精确版本 (`samtools --version`)
- 保存命令参数
- 关键分析记录输入文件校验和

## 常见陷阱

| 问题 | 说明 | 解决 |
|------|------|------|
| 染色体命名不一致 | chr1 vs 1 导致静默失败 | 用 `sed 's/^chr//'` 转换 |
| BAM 未排序 | 多数工具需要排序输入 | 症状：错误或无警告的错误结果 |
| 缺少索引 | BAM 需要 .bai，VCF 需要 .tbi | 命令会神秘失败 |
| 内存耗尽 | 大 BAM 操作会终止会话 | 流式处理或合理使用 --threads |
| 索引过期 | 修改 BAM/VCF 后需重建索引 | 旧索引 = 损坏的读取 |
| 坐标系统 | BED 是 0-based，VCF/GFF 是 1-based | 常见 off-by-one 错误 |

## 文件格式速查

| 格式 | 用途 | 关键工具 |
|------|------|----------|
| FASTA | 参考序列 | `samtools faidx` |
| FASTQ | 原始读取 + 质量 | `seqtk`, `fastp` |
| SAM/BAM | 比对读取 | `samtools` |
| VCF/BCF | 变异 | `bcftools` |
| BED | 基因组区间 | `bedtools` |
| GFF/GTF | 基因注释 | `gffread` |
| BigWig | 覆盖度轨迹 | `deepTools` |

## 核心命令

### 质量控制

```bash
# FASTQ 质量报告
fastqc sample.fastq.gz -o qc_reports/

# 修剪接头 + 低质量
fastp -i R1.fq.gz -I R2.fq.gz -o R1.clean.fq.gz -O R2.clean.fq.gz

# BAM 统计
samtools flagstat aligned.bam
samtools stats aligned.bam > stats.txt
```

### 比对

```bash
# 索引参考基因组（一次性）
bwa index reference.fa

# 比对双端读取
bwa mem -t 8 reference.fa R1.fq.gz R2.fq.gz | \
    samtools sort -o aligned.bam -

# 索引 BAM
samtools index aligned.bam
```

### 变异检测

```bash
# 调用变异
bcftools mpileup -Ou -f reference.fa aligned.bam | \
    bcftools call -mv -Oz -o variants.vcf.gz

# 索引 VCF
bcftools index variants.vcf.gz

# 过滤变异
bcftools filter -s LowQual -e 'QUAL<20' variants.vcf.gz
```

### 数据操作

```bash
# 提取区域
samtools view -b aligned.bam chr1:1000000-2000000 > region.bam

# BAM 转 FASTQ
samtools fastq -1 R1.fq.gz -2 R2.fq.gz aligned.bam

# 合并 BAM
samtools merge merged.bam sample1.bam sample2.bam

# 按区域子集 VCF
bcftools view -r chr1:1000-2000 variants.vcf.gz
```

## 安全与隐私

- 只读取用户明确提供的输入文件
- 输出写入用户指定的目录
- 所有序列数据本地处理
- 分析期间不进行外部 API 调用

## 相关工具安装

```bash
# Conda 安装生物信息学工具
conda install -c bioconda samtools bwa bcftools fastqc fastp

# 或 Homebrew (macOS)
brew install samtools bwa bcftools
```
