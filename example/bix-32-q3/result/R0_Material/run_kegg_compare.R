suppressPackageStartupMessages(library(KEGGREST))

files <- c(`97`='R0_Input/res_1vs97.rds', `98`='R0_Input/res_1vs98.rds', `99`='R0_Input/res_1vs99.rds')
organism <- 'pau'
p_cut <- 0.05
padj_cut <- 0.05
lfc_cut <- 1.5

# KEGG mappings for PA14
link_vec <- keggLink('pathway', organism)
pathway_names <- keggList('pathway', organism)
path2gene <- split(sub('^pau:', '', names(link_vec)), sub('^path:', '', unname(link_vec)))
all_annotated <- unique(sub('^pau:', '', names(link_vec)))

# hypergeometric enrichment
run_enrich <- function(genes, universe=all_annotated, pathway_map=path2gene) {
  genes <- intersect(unique(genes), universe)
  N <- length(universe)
  n <- length(genes)
  out <- lapply(names(pathway_map), function(pw) {
    pw_genes <- intersect(unique(pathway_map[[pw]]), universe)
    M <- length(pw_genes)
    k_genes <- intersect(genes, pw_genes)
    k <- length(k_genes)
    if (k == 0L) return(NULL)
    pval <- phyper(k - 1, M, N - M, n, lower.tail = FALSE)
    data.frame(
      ID = pw,
      Description = if (pw %in% names(pathway_names)) sub(' - Pseudomonas aeruginosa UCBPP-PA14$', '', pathway_names[[pw]]) else pw,
      GeneRatio = sprintf('%d/%d', k, n),
      BgRatio = sprintf('%d/%d', M, N),
      Count = k,
      pvalue = pval,
      geneID = paste(sort(k_genes), collapse='/'),
      stringsAsFactors = FALSE
    )
  })
  out <- do.call(rbind, out)
  if (is.null(out) || nrow(out) == 0) return(data.frame())
  out$p.adjust <- p.adjust(out$pvalue, method='BH')
  out$qvalue <- out$p.adjust
  out <- out[order(out$p.adjust, out$pvalue, -out$Count), ]
  rownames(out) <- NULL
  out
}

summary_rows <- list()
res_tables <- list()
for (strain in names(files)) {
  x <- readRDS(files[[strain]])
  df <- as.data.frame(x)
  df$gene <- rownames(df)
  up <- subset(df, !is.na(padj) & padj < padj_cut & !is.na(log2FoldChange) & log2FoldChange > lfc_cut)
  enrich <- run_enrich(up$gene)
  sig <- subset(enrich, pvalue < p_cut & p.adjust < padj_cut)
  res_tables[[strain]] <- list(up=up, enrich=enrich, sig=sig)
  summary_rows[[strain]] <- data.frame(
    strain = strain,
    tested_genes = nrow(df),
    upregulated_genes = nrow(up),
    annotated_upregulated = length(intersect(up$gene, all_annotated)),
    significant_pathways = nrow(sig),
    stringsAsFactors = FALSE
  )
}
summary_df <- do.call(rbind, summary_rows)

# exclusives in 99 vs 97 and 98
sig_names <- lapply(res_tables, function(z) z$sig$Description)
exclusive_99 <- setdiff(sig_names[['99']], union(sig_names[['97']], sig_names[['98']]))
exclusive_99_tbl <- subset(res_tables[['99']]$sig, Description %in% exclusive_99)
exclusive_99_tbl <- exclusive_99_tbl[order(exclusive_99_tbl$p.adjust, exclusive_99_tbl$pvalue, -exclusive_99_tbl$Count), ]

# Save detailed tables
write.csv(summary_df, 'R0_Material/kegg_enrichment_summary.csv', row.names=FALSE)
for (strain in names(res_tables)) {
  write.csv(res_tables[[strain]]$up, sprintf('R0_Material/upregulated_genes_strain%s.csv', strain), row.names=FALSE)
  write.csv(res_tables[[strain]]$enrich, sprintf('R0_Material/kegg_all_strain%s.csv', strain), row.names=FALSE)
  write.csv(res_tables[[strain]]$sig, sprintf('R0_Material/kegg_sig_strain%s.csv', strain), row.names=FALSE)
}
write.csv(exclusive_99_tbl, 'R0_Material/kegg_exclusive_upregulated_strain99.csv', row.names=FALSE)

# human-readable report
sink('R0_Material/kegg_compare_report.txt')
cat('KEGG enrichment comparison for upregulated genes\n')
cat('Criteria: padj <', padj_cut, 'and log2FoldChange >', lfc_cut, '; enrichment pvalue <', p_cut, 'and BH-adjusted pvalue <', padj_cut, '\n\n')
print(summary_df, row.names=FALSE)
cat('\nSignificant KEGG pathways by strain:\n\n')
for (strain in names(res_tables)) {
  cat('Strain', strain, '\n')
  if (nrow(res_tables[[strain]]$sig) == 0) {
    cat('  None\n\n')
  } else {
    print(res_tables[[strain]]$sig[, c('ID','Description','Count','GeneRatio','BgRatio','pvalue','p.adjust')], row.names=FALSE)
    cat('\n')
  }
}
cat('Exclusive significant pathways in strain 99 (not significant in 97 or 98):\n')
if (nrow(exclusive_99_tbl) == 0) {
  cat('  None\n')
} else {
  print(exclusive_99_tbl[, c('ID','Description','Count','GeneRatio','BgRatio','pvalue','p.adjust','geneID')], row.names=FALSE)
}
sink()

cat('Done.\n')
