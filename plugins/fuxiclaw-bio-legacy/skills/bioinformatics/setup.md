# 生物信息学设置指南

## 首次使用设置

### 1. 创建项目目录

```bash
mkdir -p ~/bioinformatics/{projects,references,tools,results}
```

### 2. 安装工具

**使用 Conda（推荐）：**

```bash
# 创建生物信息学环境
conda create -n bioinfo python=3.11
conda activate bioinfo

# 安装核心工具
conda install -c bioconda -c conda-forge \
    samtools bwa bcftools bedtools \
    fastqc fastp multiqc \
    star hisat2 bowtie2 \
    gatk4 picard
```

**使用 Homebrew（macOS）：**

```bash
brew install samtools bwa bcftools bedtools
brew install fastqc seqtk
```

### 3. 下载参考基因组

```bash
# 人类 GRCh38
mkdir -p ~/bioinformatics/references/hg38
cd ~/bioinformatics/references/hg38

# 下载参考序列
wget https://hgdownload.soe.ucsc.edu/goldenPath/hg38/bigZips/hg38.fa.gz
gunzip hg38.fa.gz

# 创建索引
samtools faidx hg38.fa
bwa index hg38.fa
```

## 项目初始化

每个新项目应该：

1. **创建项目目录**
   ```bash
   mkdir -p ~/bioinformatics/projects/my_project/{raw,data,results,logs}
   ```

2. **记录项目信息**
   ```bash
   cat > ~/bioinformatics/projects/my_project/README.md << 'EOF'
   # 项目: my_project
   
   ## 参考基因组
   - 物种: Homo sapiens
   - 版本: GRCh38/hg38
   - 路径: ~/bioinformatics/references/hg38/hg38.fa
   
   ## 样本
   - Sample1: 正常组织
   - Sample2: 肿瘤组织
   
   ## 分析流程
   1. QC (FastQC)
   2. 修剪 (fastp)
   3. 比对 (BWA)
   4. 变异检测 (GATK)
   EOF
   ```

3. **记录使用的工具版本**
   ```bash
   samtools --version > logs/versions.txt
   bwa 2>&1 | head -1 >> logs/versions.txt
   ```

## 内存使用指南

| 工具 | 人类基因组内存需求 | 建议 |
|------|-------------------|------|
| BWA MEM | ~6 GB | 8GB+ RAM 推荐 |
| STAR 索引 | ~32 GB | 高配服务器 |
| GATK HaplotypeCaller | ~4 GB | 按样本调整 |
| Samtools sort | ~2 GB | 可用 `-m` 调整 |

## 检查清单

开始分析前确认：
- [ ] 工具已安装且版本已知
- [ ] 参考基因组已下载并索引
- [ ] 磁盘空间充足（FASTQ 的 3-5 倍）
- [ ] 项目目录结构已创建
- [ ] 了解样本信息（物种、测序平台、文库类型）
