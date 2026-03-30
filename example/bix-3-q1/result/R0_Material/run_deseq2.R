# Load required libraries
suppressPackageStartupMessages(library(DESeq2))

# Read count matrix and metadata
counts <- read.csv('R0_Material/counts_matrix.csv', row.names=1, check.names=FALSE)
metadata <- read.csv('R0_Material/metadata.csv', check.names=FALSE)

print(paste("Count matrix dimensions:", nrow(counts), "genes x", ncol(counts), "samples"))
print("Sample metadata:")
print(metadata)

# Ensure metadata row names match count matrix column names
rownames(metadata) <- metadata$Sample

# Filter genes with very low counts (at least 10 counts across all samples)
keep <- rowSums(counts) >= 10
counts_filtered <- counts[keep, ]
print(paste("Genes after filtering (rowSums >= 10):", nrow(counts_filtered)))

# Create DESeqDataSet
dds <- DESeqDataSetFromMatrix(
  countData = counts_filtered,
  colData = metadata,
  design = ~ Tissue
)

# Set reference level for Tissue (baseline_blood as reference)
dds$Tissue <- relevel(dds$Tissue, ref = "baseline_blood")

# Run DESeq2
print("Running DESeq2...")
dds <- DESeq(dds)

# Extract results for final_blood vs baseline_blood
res <- results(dds, contrast = c("Tissue", "final_blood", "baseline_blood"))

# Summary
print("DESeq2 results summary:")
summary(res)

# Convert to data frame
res_df <- as.data.frame(res)
res_df$Gene <- rownames(res_df)

# Save full results
write.csv(res_df, 'R0_Material/deseq2_results.csv', row.names=FALSE)
print("Full results saved to R0_Material/deseq2_results.csv")

# Filter results: FDR < 0.05, |log2FC| > 1, baseMean >= 10
filtered <- res_df[
  !is.na(res_df$padj) & 
  res_df$padj < 0.05 & 
  abs(res_df$log2FoldChange) > 1 & 
  res_df$baseMean >= 10, 
]

print(paste("\nGenes meeting criteria (FDR<0.05, |log2FC|>1, baseMean>=10):", nrow(filtered)))

# Save filtered results
if(nrow(filtered) > 0) {
  write.csv(filtered, 'R0_Material/filtered_results.csv', row.names=FALSE)
  print("Filtered results saved to R0_Material/filtered_results.csv")
  print("\nTop significant genes:")
  print(head(filtered[order(filtered$padj), c('Gene', 'baseMean', 'log2FoldChange', 'padj')]))
} else {
  print("No genes meet the filtering criteria.")
}

# Save summary
sink('R0_Material/summary.txt')
cat("DESeq2 Analysis Summary\n")
cat("=======================\n\n")
cat("Design: ~ Tissue\n")
cat("Contrast: final_blood vs baseline_blood\n\n")
cat("Total genes analyzed:", nrow(counts_filtered), "\n")
cat("Genes meeting criteria (FDR<0.05, |log2FC|>1, baseMean>=10):", nrow(filtered), "\n\n")
if(nrow(filtered) > 0) {
  cat("Upregulated in final_blood (log2FC > 1):", sum(filtered$log2FoldChange > 1), "\n")
  cat("Downregulated in final_blood (log2FC < -1):", sum(filtered$log2FoldChange < -1), "\n")
}
sink()

print("\nAnalysis complete!")
