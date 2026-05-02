# 伏羲Claw - 面向 OpenClaw 的开源生物信息能力库

**语言切换：** [中文](README.md) | [English](README_EN.md)

<div align="center">

<p align="center">
  <img src="FuxiClaw_Logo.png" alt="FuxiClaw Logo" width="350">
</p>

**伏羲Claw 是一个面向 OpenClaw 的开源医学与生物信息能力文档库，</br>便于将 `skills` 与 `SOUL` 迁移到本地 OpenClaw 工作区。**

[![OpenClaw](https://img.shields.io/badge/OpenClaw-compatible-blue?style=flat-square)](https://github.com/openclaw/openclaw)
[![Skills](https://img.shields.io/badge/skills-866-success?style=flat-square)](skills/)
[![SOUL](https://img.shields.io/badge/SOUL-domain%20mindset-orange?style=flat-square)](SOUL.md)
[![License](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)](LICENSE)

</div>

伏羲Claw 是一个开源的能力仓库，方便用户将这里的 `skills` 和 `SOUL` 文档迁移到自己的本地 OpenClaw 中，作为增强本地 OpenClaw 生信能力的能力库。  

### 演示1（解决 BixBench 中的 `bix-3-q1` 问题）

<img src="example/bix-3-q1/bix-3-q1.gif" alt="bix-3-q1 过程演示" width="100%">

如果上方 GIF 无法显示，可下载/查看 MP4：[`example/bix-3-q1/bix-3-q1_v0.mp4`](example/bix-3-q1/bix-3-q1_v0.mp4)

### 演示2（解决 BixBench 中的 `bix-32-q3` 问题）

<img src="example/bix-32-q3/bix-32-q3.gif" alt="bix-32-q3 过程演示" width="100%">

如果上方 GIF 无法显示，可下载/查看 MP4：[`example/bix-32-q3/bix-32-q3_v0.mp4`](example/bix-32-q3/bix-32-q3_v0.mp4)

它的核心目标是为本地 OpenClaw 提供两类增强：

- **专业技能层（skills）**：补充医学与生信任务所需的工具调用和流程能力
- **思维与行为层（SOUL）**：注入更适合复杂生信任务的任务拆解与执行方式

当用户把这些文件迁移到本地并完成配置后，OpenClaw 将更擅长执行中高复杂度的生信研究任务。

## 免责声明

本仓库中的所有技能均**非原创**。这些技能来自对公开项目资料的整理与收集，主要参考来源为 [BioAgent Hub](https://bioagenthub-syslab.manus.space/) 中提及的相关项目。

---

## 项目概览

伏羲Claw 面向“本地 OpenClaw 能力增强”场景设计。你可以整体使用，也可以按需拷贝其中部分目录。  
与通用提示词不同，这个仓库强调：

- 对生信/医学任务的专业化技能复用
- 对复杂任务的流程化与结构化执行
- 与 OpenClaw 工作流的低成本集成

## 包含内容

- `skills/`：医学与生信相关技能目录（通常含 `SKILL.md` 与参考材料）
- `SOUL.md`：领域化角色与执行原则，定义代理的思维风格与边界
- `setup/`：环境初始化与接入脚本
- `example/`：示例任务，便于验证集成是否生效
- `LICENSE`：开源协议

## 快速开始

先克隆仓库到本地：

```bash
git clone https://github.com/<your-org-or-username>/FuxiClaw.git
```

然后按以下步骤接入你的本地 OpenClaw：

1. 准备一个可运行的 OpenClaw 本地工作区  
2. 将 `FuxiClaw/skills/` 与 `FuxiClaw/SOUL.md` 拷贝到 OpenClaw 可读取路径  
3. 按你的 OpenClaw 配置方式注册/启用这些目录  
4. 重载会话并运行一个生信任务做验证

## 环境配置（macOS / Linux）

建议先在本地准备一个独立环境（推荐 `conda`/`mamba`），再安装生信分析常用依赖。下面给出一个可直接复制的最小配置流程。

### 1) 安装基础工具

macOS（Homebrew）：

```bash
brew install micromamba git wget curl
```

Ubuntu / Debian：

```bash
sudo apt update
sudo apt install -y curl wget git build-essential
```

### 2) 创建隔离环境（推荐）

```bash
micromamba create -n FuxiClaw-bio -c conda-forge -c bioconda \
  python=3.11 r-base=4.3 r-essentials \
  r-tidyverse r-data-table r-readxl r-optparse \
  bioconductor-deseq2 bioconductor-edger bioconductor-limma \
  bioconductor-tximport bioconductor-biostrings bioconductor-annotationdbi \
  samtools bcftools bedtools fastqc multiqc -y
micromamba activate FuxiClaw-bio
```

### 3) 安装 R 包（若 conda 未覆盖或需要补充）

```bash
R -e "if (!requireNamespace('BiocManager', quietly=TRUE)) install.packages('BiocManager', repos='https://cloud.r-project.org')"
R -e "BiocManager::install(c('DESeq2','edgeR','limma','tximport','Biostrings','AnnotationDbi'), ask=FALSE, update=FALSE)"
```

### 4) 可选 Python 生信包

```bash
pip install pandas numpy scipy scikit-learn matplotlib seaborn biopython pysam
```

### 5) 快速自检

```bash
python -c "import pandas, numpy, Bio, pysam; print('python deps ok')"
R -e "library(DESeq2); library(edgeR); library(limma); sessionInfo()"
```

## 实际使用方式



使用样例：
```
/deep 帮我解决下面这个问题

请使用 DESeq2 分析 Control mice（数据文件地址："/Users/maxliu01/Desktop/0_project/1_bio_agent/hszd/BixBench/hf/testcase/bix-3-q1/CapsuleData-94bcdbc9-c729-4661-9bc1-0057bbea39c4/Data_deposition_RNAseq_Paroxetine_2017.xlsx"），比较 final blood 与 baseline blood（design ~ Tissue；contrast final_blood vs baseline_blood）。请统计满足 FDR<0.05、|log2FC|>1 且 baseMean≥10 的基因数量；如果输入为归一化计数，请在运行 DESeq2 前缩放为整数伪计数。
```


⚠️ 注意：这里的使用方式不是直接输入提示词。  
必须使用带前缀的命令格式：`/deep <你的任务描述>`，才会开启并执行该流程。

若配置生效，通常会观察到：

- 任务拆解更清晰（先检索、再分析、最后汇总）
- 工具选择更贴近生信语境
- 输出更结构化，便于继续迭代

## 仓库结构

```text
FuxiClaw/
├── README.md
├── LICENSE
├── SOUL.md
├── setup/     # 环境初始化与接入脚本
├── skills/    # 医学与生物信息技能目录
└── example/   # 用于验证的示例任务
```

## 相关仓库

| 仓库 | 关联价值 |
|------|----------|
| [`openclaw/openclaw`](https://github.com/openclaw/openclaw) | 伏羲Claw 所接入的 OpenClaw 运行时与工作区模型。 |

## 使用场景

- 给本地 OpenClaw 快速增加医学/生信任务能力
- 让代理在复杂任务中具备更稳定的任务规划与执行思维
