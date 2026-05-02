import type { Extension } from "@codemirror/state";
import { javascript } from "@codemirror/lang-javascript";
import { python } from "@codemirror/lang-python";
import { json } from "@codemirror/lang-json";
import { markdown } from "@codemirror/lang-markdown";
import { html } from "@codemirror/lang-html";
import { css } from "@codemirror/lang-css";

const EXT_MAP: Record<string, () => Extension> = {
  ".js": () => javascript(),
  ".jsx": () => javascript({ jsx: true }),
  ".ts": () => javascript({ typescript: true }),
  ".tsx": () => javascript({ jsx: true, typescript: true }),
  ".mjs": () => javascript(),
  ".cjs": () => javascript(),
  ".py": () => python(),
  ".pyw": () => python(),
  ".r": () => python(),
  ".json": () => json(),
  ".jsonl": () => json(),
  ".md": () => markdown(),
  ".mdx": () => markdown(),
  ".html": () => html(),
  ".htm": () => html(),
  ".xml": () => html(),
  ".svg": () => html(),
  ".css": () => css(),
  ".scss": () => css(),
  ".less": () => css(),
};

export function getLanguageExtension(filePath: string): Extension | null {
  const dot = filePath.lastIndexOf(".");
  if (dot === -1) return null;
  const ext = filePath.slice(dot).toLowerCase();
  const factory = EXT_MAP[ext];
  return factory ? factory() : null;
}

export function getLanguageLabel(filePath: string): string {
  const dot = filePath.lastIndexOf(".");
  if (dot === -1) return "text";
  const ext = filePath.slice(dot + 1).toLowerCase();
  const LABEL_MAP: Record<string, string> = {
    js: "JavaScript", jsx: "JSX", ts: "TypeScript", tsx: "TSX",
    py: "Python", json: "JSON", md: "Markdown", html: "HTML",
    css: "CSS", scss: "SCSS", xml: "XML", svg: "SVG",
    yaml: "YAML", yml: "YAML", toml: "TOML", sh: "Shell",
    bash: "Bash", txt: "Text", r: "R", csv: "CSV", tsv: "TSV",
    png: "PNG", jpg: "JPEG", jpeg: "JPEG", gif: "GIF", pdf: "PDF",
    maf: "MAF", pdb: "PDB", mol2: "MOL2", xyz: "XYZ", gro: "GRO",
  };
  return LABEL_MAP[ext] ?? ext.toUpperCase();
}

export function getFileName(filePath: string): string {
  const slash = filePath.lastIndexOf("/");
  return slash === -1 ? filePath : filePath.slice(slash + 1);
}

const PREVIEWABLE_EXTS = new Set([
  ".html", ".htm", ".svg", ".md", ".mdx",
  ".png", ".jpg", ".jpeg", ".gif", ".webp",
]);

const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp"]);

export type PreviewMode = "html" | "markdown" | "image" | null;

export function getPreviewMode(filePath: string): PreviewMode {
  const dot = filePath.lastIndexOf(".");
  if (dot === -1) return null;
  const ext = filePath.slice(dot).toLowerCase();
  if (ext === ".html" || ext === ".htm" || ext === ".svg") return "html";
  if (ext === ".md" || ext === ".mdx") return "markdown";
  if (IMAGE_EXTS.has(ext)) return "image";
  return null;
}

export function isPreviewable(filePath: string): boolean {
  const dot = filePath.lastIndexOf(".");
  if (dot === -1) return false;
  return PREVIEWABLE_EXTS.has(filePath.slice(dot).toLowerCase());
}

export function isImageFile(mimeType?: string): boolean {
  return !!mimeType && mimeType.startsWith("image/");
}
