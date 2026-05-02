FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    PIP_NO_CACHE_DIR=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    ca-certificates \
    cmake \
    curl \
    git \
    python-is-python3 \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    pkg-config \
    ripgrep \
    wget \
    r-base \
    r-base-dev \
    bcftools \
    bedtools \
    bowtie2 \
    bwa \
    fastqc \
    minimap2 \
    ncbi-blast+ \
    samtools \
    seqkit \
    libbz2-dev \
    libcairo2-dev \
    libcurl4-openssl-dev \
    libfontconfig1-dev \
    libfreetype6-dev \
    libfribidi-dev \
    libharfbuzz-dev \
    libjpeg-dev \
    liblzma-dev \
    libpng-dev \
    libssl-dev \
    libxml2-dev \
    libxt-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install \
    biopython \
    h5py \
    matplotlib \
    multiqc \
    numpy \
    openpyxl \
    pandas \
    pysam \
    rpy2 \
    scikit-learn \
    scipy \
    seaborn \
    statsmodels

RUN Rscript -e "options(repos = c(CRAN = 'https://cloud.r-project.org')); install.packages(c('BiocManager', 'data.table', 'jsonlite'), Ncpus = max(1L, parallel::detectCores() - 1L))" && \
    Rscript -e "options(repos = c(CRAN = 'https://cloud.r-project.org')); options(BioC_mirror = 'https://bioconductor.org'); if (!requireNamespace('BiocManager', quietly = TRUE)) install.packages('BiocManager'); BiocManager::install(c('DESeq2', 'clusterProfiler', 'org.Hs.eg.db'), ask = FALSE, update = FALSE)"

RUN useradd -m -s /bin/bash ohuser && \
    mkdir -p /workspace/output && \
    chown -R ohuser:ohuser /workspace

USER ohuser
WORKDIR /workspace
