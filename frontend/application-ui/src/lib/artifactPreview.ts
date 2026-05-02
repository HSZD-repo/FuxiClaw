export const ARTIFACT_PREVIEW_MAX_BYTES = 50 * 1024 * 1024;

export type ArtifactPreviewMode =
  | "code"
  | "excel"
  | "html"
  | "image"
  | "markdown"
  | "molecule"
  | "pdf"
  | "table"
  | "text"
  | "unsupported";

const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico"]);
const TABLE_EXTS = new Set([".csv", ".tsv", ".tab"]);
const MARKDOWN_EXTS = new Set([".md", ".mdx"]);
const HTML_EXTS = new Set([".html", ".htm", ".svg"]);
const PDF_EXTS = new Set([".pdf"]);
const EXCEL_EXTS = new Set([".xlsx", ".xls"]);
const MOLECULE_EXTS = new Set([".pdb", ".mol2", ".xyz", ".gro"]);
const TEXT_EXTS = new Set([
  ".txt", ".log", ".json", ".jsonl", ".xml", ".yaml", ".yml", ".toml",
  ".ini", ".cfg", ".conf", ".env", ".py", ".pyw", ".r", ".sh", ".bash",
  ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".css", ".scss", ".less",
  ".rs", ".go", ".java", ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".sql",
  ".swift", ".kt", ".scala", ".lua", ".pl", ".ex", ".exs", ".m", ".fasta",
  ".fa", ".fastq", ".fq", ".gff", ".gff3", ".gtf", ".bed", ".vcf", ".maf",
  ".sam", ".gmt",
]);

export function getFileExtension(filePath: string): string {
  const clean = filePath.split(/[?#]/, 1)[0] ?? filePath;
  const dot = clean.lastIndexOf(".");
  return dot === -1 ? "" : clean.slice(dot).toLowerCase();
}

export function isImageArtifact(filePath: string, mimeType?: string): boolean {
  return Boolean(mimeType?.startsWith("image/")) || IMAGE_EXTS.has(getFileExtension(filePath));
}

export function getArtifactPreviewMode(
  filePath: string,
  mimeType?: string,
): ArtifactPreviewMode {
  const ext = getFileExtension(filePath);
  if (isImageArtifact(filePath, mimeType)) return "image";
  if (mimeType === "application/pdf" || PDF_EXTS.has(ext)) return "pdf";
  if (EXCEL_EXTS.has(ext)) return "excel";
  if (MOLECULE_EXTS.has(ext)) return "molecule";
  if (TABLE_EXTS.has(ext)) return "table";
  if (MARKDOWN_EXTS.has(ext)) return "markdown";
  if (HTML_EXTS.has(ext)) return "html";
  if (mimeType?.startsWith("text/")) return "text";
  if (TEXT_EXTS.has(ext)) return "code";
  return "unsupported";
}

export function isPreviewableArtifact(filePath: string, mimeType?: string): boolean {
  return getArtifactPreviewMode(filePath, mimeType) !== "unsupported";
}

export function tableDelimiterForPath(filePath: string): string {
  const ext = getFileExtension(filePath);
  return ext === ".csv" ? "," : "\t";
}
