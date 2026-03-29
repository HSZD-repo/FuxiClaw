#!/bin/bash
#
# Ubuntu Bioinformatics Environment Setup Script
# 适用于 Ubuntu/Debian 系统的生物信息学研究环境配置脚本
#
# 使用方法:
#   chmod +x setup_ubuntu_bioinf.sh
#   ./setup_ubuntu_bioinf.sh
#

set -e

# 颜色定义
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

check_ubuntu() {
    if [[ ! -f /etc/os-release ]]; then
        log_error "无法检测操作系统"
        exit 1
    fi
    
    source /etc/os-release
    if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
        log_warn "此脚本针对 Ubuntu/Debian 优化，当前系统: $ID"
        read -p "是否继续? (y/N) " -n 1 -r
        echo
        [[ $REPLY =~ ^[Yy]$ ]] || exit 1
    fi
    
    log_info "系统: $NAME $VERSION_ID"
}

install_apt_tools() {
    log_info "更新 apt 并安装基础工具..."
    
    sudo apt-get update
    sudo apt-get install -y \
        build-essential \
        git \
        git-lfs \
        wget \
        curl \
        tree \
        htop \
        jq \
        parallel \
        pigz \
        zstd \
        xz-utils \
        p7zip-full \
        cmake \
        pkg-config \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
        gnupg \
        lsb-release
    
    log_success "基础工具安装完成"
}

install_r() {
    log_info "安装 R 环境..."
    
    # 添加 CRAN 仓库
    local cran_url="https://cloud.r-project.org/bin/linux/ubuntu"
    local cran_key="https://cloud.r-project.org/bin/linux/ubuntu/marutter_pubkey.asc"
    
    # 获取 Ubuntu 版本代号
    local ubuntu_codename=$(lsb_release -cs)
    
    # 添加 R 仓库密钥
    wget -qO- "$cran_key" | sudo tee -a /etc/apt/trusted.gpg.d/cran_ubuntu_key.asc
    
    # 添加 R 仓库
    echo "deb [arch=amd64 signed-by=/etc/apt/trusted.gpg.d/cran_ubuntu_key.asc] $cran_url $ubuntu_codename-cran40/" | \
        sudo tee /etc/apt/sources.list.d/cran-r.list
    
    sudo apt-get update
    sudo apt-get install -y r-base r-base-dev
    
    log_success "R $(R --version | head -1 | grep -o '[0-9]\+\.[0-9]\+\.[0-9]\+') 安装完成"
}

install_r_packages() {
    log_info "安装 Bioconductor 核心包..."
    
    sudo R --vanilla -q << 'RSCRIPT'
    options(repos = c(CRAN = "https://cloud.r-project.org"))
    
    if (!require("BiocManager", quietly = TRUE)) 
        install.packages("BiocManager", dependencies = TRUE)
    
    # 核心包
    pkgs <- c(
        "DESeq2", "edgeR", "limma", "tximport", "apeglm",
        "GenomicRanges", "SummarizedExperiment", "SingleCellExperiment",
        "AnnotationDbi", "biomaRt",
        "org.Hs.eg.db", "org.Mm.eg.db",
        "pheatmap", "ggplot2", "dplyr", "tidyr", "readr", "readxl"
    )
    
    BiocManager::install(pkgs, ask = FALSE, update = TRUE)
    cat("\n=== R 包安装完成 ===\n")
RSCRIPT
    
    log_success "Bioconductor 包安装完成"
}

install_conda() {
    if command -v conda &>/dev/null || command -v mamba &>/dev/null; then
        log_success "Conda/Mamba 已安装"
        return
    fi
    
    log_info "安装 Miniforge..."
    local arch=$(uname -m)
    cd /tmp
    wget -q "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-${arch}.sh" -O miniforge.sh
    bash miniforge.sh -b -p "$HOME/miniforge3"
    rm miniforge.sh
    "$HOME/miniforge3/bin/conda" init bash
    log_success "Miniforge 安装完成"
}

create_bioinf_env() {
    log_info "创建 bioinf 环境..."
    
    export PATH="$HOME/miniforge3/bin:$PATH"
    
    "$HOME/miniforge3/bin/conda" create -n bioinf python=3.11 -y 2>/dev/null || true
    
    local pip_cmd="$HOME/miniforge3/envs/bioinf/bin/pip"
    
    # 科学计算基础
    $pip_cmd install -q numpy scipy pandas matplotlib seaborn scikit-learn jupyter ipython openpyxl h5py
    
    # 生物信息学核心
    $pip_cmd install -q biopython pysam pybedtools scanpy anndata mudata muon scvi-tools
    
    log_success "bioinf 环境创建完成"
}

install_bio_tools() {
    log_info "安装生物信息学工具..."
    
    # 使用 Bioconda 安装工具
    export PATH="$HOME/miniforge3/bin:$PATH"
    
    # 添加频道
    "$HOME/miniforge3/bin/conda" config --add channels bioconda 2>/dev/null || true
    "$HOME/miniforge3/bin/conda" config --add channels conda-forge 2>/dev/null || true
    
    # 安装工具到 bioinf 环境
    "$HOME/miniforge3/bin/conda" install -n bioinf -y \
        samtools bcftools bedtools \
        bwa bowtie2 hisat2 minimap2 \
        seqkit fastqc fastp multiqc \
        2>/dev/null || log_warn "部分工具安装失败，请手动安装"
    
    log_success "生物信息学工具安装完成"
}

install_openclaw() {
    if command -v openclaw &>/dev/null; then
        log_success "OpenClaw 已安装"
        return
    fi
    
    # 检查 Node.js
    if ! command -v npm &>/dev/null; then
        log_info "安装 Node.js..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt-get install -y nodejs
    fi
    
    log_info "安装 OpenClaw..."
    sudo npm install -g openclaw
    log_success "OpenClaw 安装完成"
}

print_final() {
    echo ""
    echo "========================================"
    log_success "Ubuntu 生物信息学环境配置完成!"
    echo "========================================"
    echo ""
    echo "激活命令:"
    echo "  source ~/.bashrc           # 重新加载配置"
    echo "  conda activate bioinf      # Python 生物信息学环境"
    echo "  R                          # R 交互式环境"
    echo "  openclaw                   # 启动 OpenClaw"
    echo ""
    echo "工具位置:"
    echo "  conda 环境: $HOME/miniforge3/envs/bioinf"
    echo "  R 包: $HOME/R/x86_64-pc-linux-gnu-library"
    echo ""
}

main() {
    echo "========================================"
    echo " Ubuntu Bioinformatics Setup"
    echo "========================================"
    
    check_ubuntu
    install_apt_tools
    install_r
    install_r_packages
    install_conda
    create_bioinf_env
    install_bio_tools
    install_openclaw
    
    print_final
}

main "$@"
