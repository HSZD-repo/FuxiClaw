#!/bin/bash
#
# macOS Bioinformatics Environment Setup Script (精简版)
# 基于实际使用环境优化
#
# 此脚本配置运行 BigBench 生物信息学问题所需的核心依赖
#

set -e

# 颜色定义
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

check_macos() {
    [[ "$OSTYPE" == "darwin"* ]] || { log_error "此脚本仅适用于 macOS"; exit 1; }
    log_info "macOS $(sw_vers -productVersion) ($(uname -m))"
}

install_xcode() {
    if ! xcode-select -p &>/dev/null; then
        log_info "安装 Xcode Command Line Tools..."
        xcode-select --install
        log_warn "请完成弹窗安装后重新运行脚本"
        exit 0
    fi
    log_success "Xcode CLI Tools"
}

install_homebrew() {
    if ! command -v brew &>/dev/null; then
        log_info "安装 Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        [[ $(uname -m) == "arm64" ]] && eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    log_success "Homebrew $(brew --version | head -1 | cut -d' ' -f2)"
}

install_base_tools() {
    log_info "安装基础工具..."
    local tools=(git git-lfs wget curl tree htop jq parallel pigz zstd xz p7zip cmake pkg-config)
    for t in "${tools[@]}"; do
        brew list "$t" &>/dev/null || brew install "$t"
    done
    log_success "基础工具"
}

install_r() {
    log_info "配置 R 环境..."
    
    if ! command -v R &>/dev/null; then
        brew install r
    fi
    
    log_info "安装 Bioconductor 核心包..."
    R --vanilla -q << 'RSCRIPT'
    options(repos = c(CRAN = "https://cloud.r-project.org"))
    
    if (!require("BiocManager", quietly = TRUE)) 
        install.packages("BiocManager")
    
    # 核心包（基于实际使用）
    pkgs <- c(
        "DESeq2", "edgeR", "limma", "tximport", "apeglm",
        "GenomicRanges", "SummarizedExperiment", "SingleCellExperiment",
        "AnnotationDbi", "biomaRt",
        "org.Hs.eg.db", "org.Mm.eg.db",
        "pheatmap", "ggplot2", "dplyr", "tidyr", "readr", "readxl"
    )
    
    BiocManager::install(pkgs, ask = FALSE, update = TRUE)
    cat("\n=== 安装完成 ===\n")
RSCRIPT
    
    log_success "R $(R --version | head -1 | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+')"
}

install_conda() {
    if command -v conda &>/dev/null || command -v mamba &>/dev/null; then
        log_success "Conda/Mamba 已安装"
        return
    fi
    
    log_info "安装 Miniforge..."
    local arch=$(uname -m)
    cd /tmp
    curl -fsSL "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-${arch}.sh" -o miniforge.sh
    bash miniforge.sh -b -p "$HOME/miniforge3"
    rm miniforge.sh
    "$HOME/miniforge3/bin/conda" init zsh
    "$HOME/miniforge3/bin/conda" init bash
    log_success "Miniforge 安装完成"
}

create_bioinf_env() {
    log_info "创建 bioinf 环境..."
    
    # 重新加载 shell 配置
    export PATH="$HOME/miniforge3/bin:$PATH"
    
    # 创建环境
    "$HOME/miniforge3/bin/conda" create -n bioinf python=3.11 -y 2>/dev/null || true
    
    local pip_cmd="$HOME/miniforge3/envs/bioinf/bin/pip"
    
    # 科学计算基础
    $pip_cmd install -q numpy scipy pandas matplotlib seaborn scikit-learn jupyter ipython openpyxl h5py
    
    # 生物信息学核心
    $pip_cmd install -q biopython pysam pybedtools scanpy anndata mudata muon scvi-tools
    
    log_success "bioinf 环境"
}

install_bio_tools() {
    log_info "安装生物信息学命令行工具..."
    
    # 添加 bio tap
    brew tap brewsci/bio 2>/dev/null || true
    
    # 尝试安装核心工具（部分可能失败，不影响整体）
    local tools=(samtools bcftools bedtools seqkit fastqc)
    for t in "${tools[@]}"; do
        brew info "$t" &>/dev/null && brew install "$t" 2>/dev/null && log_success "$t" || log_warn "$t 安装失败/不可用"
    done
}

install_openclaw() {
    if command -v openclaw &>/dev/null; then
        log_success "OpenClaw 已安装"
        return
    fi
    
    log_info "安装 OpenClaw..."
    npm install -g openclaw
    log_success "OpenClaw"
}

print_final() {
    echo ""
    echo "========================================"
    log_success "环境配置完成!"
    echo "========================================"
    echo ""
    echo "激活命令:"
    echo "  conda activate bioinf      # Python 生物信息学环境"
    echo "  R                          # R 交互式环境"
    echo "  openclaw                   # 启动 OpenClaw"
    echo ""
    echo "如需 Bioconda 工具:"
    echo "  conda config --add channels bioconda"
    echo "  conda install -n bioinf star salmon"
    echo ""
}

main() {
    echo "========================================"
    echo " macOS Bioinformatics Setup"
    echo "========================================"
    
    check_macos
    install_xcode
    install_homebrew
    install_base_tools
    install_r
    install_conda
    create_bioinf_env
    install_bio_tools
    install_openclaw
    
    print_final
}

main "$@"
