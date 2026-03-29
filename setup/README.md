# macOS 生物信息学环境配置

适用于 macOS (Apple Silicon/Intel) 的生物信息学研究环境一键配置脚本。

## 快速开始

```bash
# 1. 下载脚本
wget https://raw.githubusercontent.com/yourusername/yourrepo/main/setup_macos_bioinf.sh
# 或手动下载后放到合适位置

# 2. 添加执行权限
chmod +x setup_macos_bioinf.sh

# 3. 运行脚本
./setup_macos_bioinf.sh
```

## 环境要求

- **macOS**: 11.0 (Big Sur) 或更高版本
- **架构**: Apple Silicon (ARM64) 或 Intel (x86_64)
- **磁盘空间**: 建议预留 10GB+ 空间
- **网络**: 稳定的互联网连接

## 安装的组件

### 1. 基础开发环境
- **Xcode Command Line Tools**: C/C++ 编译器、Git 等基础工具
- **Homebrew**: macOS 包管理器
- **基础工具**: git, wget, curl, jq, parallel, pigz, zstd 等

### 2. R 统计环境
- **R 4.5+**: 统计计算和图形环境
- **Bioconductor 3.20**: 生物信息学 R 包平台
  - DESeq2: RNA-seq 差异表达分析
  - edgeR: 另一种差异表达分析方法
  - limma: 线性模型分析
  - tximport: 转录本水平定量导入
  - apeglm: 对数倍数变化收缩
  - AnnotationDbi: 注释数据库接口
  - biomaRt: BioMart 数据库接口
  - GenomicRanges: 基因组范围操作
  - SummarizedExperiment: 实验数据容器
  - SingleCellExperiment: 单细胞数据容器
  - org.Hs.eg.db / org.Mm.eg.db: 人类/小鼠基因注释
- **CRAN 包**: tidyverse, pheatmap, data.table 等

### 3. Python 生物信息学环境
通过 Miniforge (Mamba) 创建隔离的 `bioinf` 环境：

**基础科学计算**
- numpy, scipy, pandas
- matplotlib, seaborn
- scikit-learn, statsmodels
- jupyter, ipython
- h5py, tables, pyarrow, zarr

**生物信息学专用**
- biopython: 生物序列处理
- pysam: SAM/BAM/CRAM 文件处理
- pybedtools: BED 文件处理
- scanpy: 单细胞 RNA-seq 分析
- anndata: 单细胞数据存储
- mudata / muon: 多组学数据
- squidpy: 空间转录组分析
- scvi-tools: 单细胞变分推断

### 4. 生物信息学命令行工具
通过 Homebrew 安装：
- **序列比对**: bwa, bowtie2, hisat2, minimap2
- **数据处理**: samtools, bcftools, htslib, bedtools, vcftools
- **序列操作**: seqkit, seqtk
- **质量控制**: fastqc, fastp, multiqc
- **序列分析**: blast, hmmer
- **多序列比对**: mafft, muscle, clustal-omega
- **系统发育**: phyml, fasttree

### 5. OpenClaw
AI Agent 平台，用于运行生物信息学 Skill。

## 使用方法

### 激活环境

```bash
# 激活生物信息学 Python 环境
conda activate bioinf

# 验证安装
python -c "import scanpy; print(scanpy.__version__)"
python -c "import pysam; print(pysam.__version__)"

# 检查 R
R --version

# 检查生物工具
samtools --version
bcftools --version
```

### 运行 OpenClaw

```bash
# 启动 OpenClaw
openclaw

# 检查状态
openclaw status

# 查看帮助
openclaw --help
```

### 运行 R 脚本

```bash
# 运行 R 脚本
Rscript your_script.R

# 或交互式
R
```

### 运行 Python 脚本

```bash
# 激活环境后
conda activate bioinf
python your_script.py

# Jupyter Notebook
jupyter notebook
```

## 目录结构

安装完成后，相关文件位置：

```
~/
├── miniforge3/          # Conda/Mamba 安装目录
│   └── envs/
│       └── bioinf/      # 生物信息学环境
├── .Rlibs/              # R 包安装目录 (可选)
└── .openclaw/           # OpenClaw 配置目录

/opt/homebrew/           # Homebrew 安装目录 (ARM64)
/usr/local/              # Homebrew 安装目录 (Intel)
```

## 故障排除

### 1. Xcode Command Line Tools 安装失败

```bash
# 手动安装
xcode-select --install

# 或从 Apple 开发者网站下载
# https://developer.apple.com/download/all/
```

### 2. Homebrew 权限问题

```bash
# 修复 Homebrew 权限
sudo chown -R $(whoami) $(brew --prefix)/*
```

### 3. R 包安装失败

```bash
# 更新 BiocManager
R -e "BiocManager::install(version='3.20', ask=FALSE)"

# 单独安装失败的包
R -e "BiocManager::install('DESeq2')"
```

### 4. Conda 环境冲突

```bash
# 删除并重建环境
conda env remove -n bioinf
conda clean --all
# 然后重新运行脚本
```

### 5. 从 Bioconda 安装额外工具

如果某些工具无法通过 Homebrew 安装，可以使用 Bioconda：

```bash
# 添加 Bioconda 频道
conda config --add channels bioconda
conda config --add channels conda-forge
conda config --set channel_priority strict

# 安装工具到 bioinf 环境
conda activate bioinf
conda install star  # 举例: 安装 STAR 比对工具
```

## 自定义配置

### 修改安装的 R 包

编辑脚本中 `install_r_env()` 函数的 `core_packages` 和 `cran_packages` 数组。

### 修改安装的 Python 包

编辑脚本中 `setup_bioinfo_env()` 函数中的 `pip install` 命令。

### 添加更多生物工具

编辑脚本中 `install_bio_tools_brew()` 函数的 `bio_tools` 数组。

## 更新环境

```bash
# 更新 Homebrew 和包
brew update && brew upgrade

# 更新 R 包
R -e "BiocManager::install()"

# 更新 Python 环境
conda activate bioinf
pip list --outdated
pip install --upgrade package_name
```

## 卸载

```bash
# 删除 Conda 环境
conda env remove -n bioinf

# 卸载 Homebrew 包 (保留 R)
brew uninstall samtools bcftools bedtools ...

# 完全删除 (包括 Homebrew)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/uninstall.sh)"
```

## 相关链接

- [Homebrew](https://brew.sh/)
- [Bioconductor](https://www.bioconductor.org/)
- [Bioconda](https://bioconda.github.io/)
- [Miniforge](https://github.com/conda-forge/miniforge)
- [OpenClaw](https://github.com/openclaw/openclaw)

## 贡献

欢迎提交 Issue 和 PR！特别是：
- 添加更多有用的生物信息学工具
- 改进 macOS 兼容性
- 优化安装流程

## 许可证

MIT License

---

## 开源说明

这个目录包含为 macOS 系统配置生物信息学研究环境的脚本和文档。

### 为什么需要这个？

在运行 BigBench 等生物信息学基准测试时，经常需要：
1. **DESeq2** - 差异表达分析
2. **scanpy** - 单细胞分析
3. **pysam** - BAM 文件处理
4. **biopython** - 序列操作

这些工具在 macOS 上的安装往往涉及复杂的依赖（如 Xcode、Fortran 编译器等），这个脚本将它们整合在一起。

### 与 Linux 的区别

| 方面 | macOS | Linux |
|------|-------|-------|
| 包管理 | Homebrew + Conda | apt/yum + Conda |
| 编译器 | Xcode CLI Tools | build-essential |
| R 安装 | Homebrew 或 CRAN 安装包 | apt 或源码编译 |
| 二进制包 | 较少，常需编译 | 丰富 |

### 版本信息

此脚本基于以下环境测试：
- macOS 15.x (Sequoia)
- Apple Silicon (ARM64)
- R 4.5.3
- Python 3.11

### 贡献

欢迎改进：
- 添加更多生物工具
- 支持 Intel Mac
- 添加 CI/CD 测试
