# FuxiClaw - Open-Source Bioinformatics Library for OpenClaw

**Language / 语言:** [English](README_EN.md) | [中文](README.md)

<div align="center">

<p align="center">
  <img src="FuxiClaw_Logo.png" alt="FuxiClaw Logo" width="350">
</p>

**FuxiClaw is an open-source library of biomedical and bioinformatics capability documents for OpenClaw, designed for easy migration of `skills` and `SOUL` into local OpenClaw workspaces.**

[![OpenClaw](https://img.shields.io/badge/OpenClaw-compatible-blue?style=flat-square)](https://github.com/openclaw/openclaw)
[![Skills](https://img.shields.io/badge/skills-866-success?style=flat-square)](skills/)
[![SOUL](https://img.shields.io/badge/SOUL-domain%20mindset-orange?style=flat-square)](SOUL.md)
[![License](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)](LICENSE)

</div>

FuxiClaw is an open-source capability-layer repository that helps users migrate the `skills` and `SOUL` documents in this repo into their local OpenClaw environments, serving as a library to strengthen local OpenClaw bioinformatics capabilities.

### Demo (Solving `bix-3-q1` in BixBench)

<img src="example/bix-3-q1/process.gif" alt="bix-3-q1 process demo GIF" width="100%">

If the GIF cannot be displayed directly on your platform, click to download/view: [`example/bix-3-q1/process.mov`](example/bix-3-q1/process.mov)

Its core goal is to provide two enhancement layers for local OpenClaw:

- **Professional skill layer (`skills`)**: Adds tool usage and workflow capabilities required for biomedical and bioinformatics tasks
- **Reasoning and behavior layer (`SOUL`)**: Injects task decomposition and execution patterns better suited for complex bioinformatics work

After users migrate these files locally and finish setup, OpenClaw becomes better at handling medium-to-high complexity bioinformatics research tasks.

## Disclaimer

All skills in this repository are **not original creations**. They are collected and organized from public project materials, mainly referencing related projects mentioned in [BioAgent Hub](https://bioagenthub-syslab.manus.space/).

---

## Overview

FuxiClaw is designed for the "local OpenClaw capability enhancement" scenario. You can use it as a whole or copy only selected directories as needed.
Unlike generic prompts, this repository emphasizes:

- Reusable, domain-specific skills for bioinformatics and biomedical tasks
- Process-oriented and structured execution for complex tasks
- Low-cost integration with OpenClaw workflows

## What Is Included

- `skills/`: Biomedical and bioinformatics skill directory (typically includes `SKILL.md` and reference materials)
- `SOUL.md`: Domain role and execution principles defining agent thinking style and boundaries
- `setup/`: Environment bootstrap and integration scripts
- `example/`: Example tasks for validating integration
- `LICENSE`: Open-source license

## Quick Start

First, clone the repository locally:

```bash
git clone https://github.com/<your-org-or-username>/FuxiClaw.git
```

Then connect it to your local OpenClaw following these steps:

1. Prepare a runnable local OpenClaw workspace
2. Copy `FuxiClaw/skills/` and `FuxiClaw/SOUL.md` into a path readable by OpenClaw
3. Register/enable these directories according to your OpenClaw configuration method
4. Reload the session and run a bioinformatics task for validation

## Environment Setup (macOS / Linux)

It is recommended to prepare an isolated local environment first (preferably via `conda`/`mamba`), then install common dependencies for bioinformatics analysis. Below is a minimal setup flow you can copy directly.

### 1) Install basic tools

macOS (Homebrew):

```bash
brew install micromamba git wget curl
```

Ubuntu / Debian:

```bash
sudo apt update
sudo apt install -y curl wget git build-essential
```

### 2) Create an isolated environment (recommended)

```bash
micromamba create -n fuxiclaw-bio -c conda-forge -c bioconda \
  python=3.11 r-base=4.3 r-essentials \
  r-tidyverse r-data-table r-readxl r-optparse \
  bioconductor-deseq2 bioconductor-edger bioconductor-limma \
  bioconductor-tximport bioconductor-biostrings bioconductor-annotationdbi \
  samtools bcftools bedtools fastqc multiqc -y
micromamba activate fuxiclaw-bio
```

### 3) Install R packages (if not covered by conda or if additional packages are needed)

```bash
R -e "if (!requireNamespace('BiocManager', quietly=TRUE)) install.packages('BiocManager', repos='https://cloud.r-project.org')"
R -e "BiocManager::install(c('DESeq2','edgeR','limma','tximport','Biostrings','AnnotationDbi'), ask=FALSE, update=FALSE)"
```

### 4) Optional Python bioinformatics packages

```bash
pip install pandas numpy scipy scikit-learn matplotlib seaborn biopython pysam
```

### 5) Quick self-check

```bash
python -c "import pandas, numpy, Bio, pysam; print('python deps ok')"
R -e "library(DESeq2); library(edgeR); library(limma); sessionInfo()"
```

## How To Use In Practice

Usage example:

```
/deep help me solve the problem below

Using DESeq2 on Control mice(Data file address:"/Users/maxliu01/Desktop/0_project/1_bio_agent/hszd/BixBench/hf/testcase/bix-3-q1/CapsuleData-94bcdbc9-c729-4661-9bc1-0057bbea39c4/Data_deposition_RNAseq_Paroxetine_2017.xlsx"), compare final blood vs baseline blood (design ~ Tissue; contrast final_blood vs baseline_blood). Report the count of genes with FDR<0.05, |log2FC|>1, and baseMean≥10; if counts are normalized, scale to integer pseudo-counts before running DESeq2.
```

⚠️ Note: this usage is **not** direct prompt input.
You must use a command with a prefix: `/deep <your task description>` to trigger and execute the pipeline.

If the configuration works correctly, you will usually observe:

- Clearer task decomposition (retrieve first, analyze second, summarize last)
- Tool choices that are better aligned with bioinformatics context
- More structured outputs that are easier to iterate on

## Repository Layout

```text
FuxiClaw/
├── README.md
├── README_EN.md
├── LICENSE
├── SOUL.md
├── setup/     # environment bootstrap and integration scripts
├── skills/    # biomedical and bioinformatics skill directories
└── example/   # sample task for validation
```

## Related Repositories

| Repository | Why it matters |
|------------|----------------|
| [`openclaw/openclaw`](https://github.com/openclaw/openclaw) | OpenClaw runtime and workspace model that FuxiClaw plugs into. |

## Use Cases

- Quickly add biomedical and bioinformatics task capabilities to local OpenClaw
- Give the agent more stable planning/execution reasoning for complex tasks
- Reuse a maintainable "skill layer + SOUL layer" configuration pattern across teams
