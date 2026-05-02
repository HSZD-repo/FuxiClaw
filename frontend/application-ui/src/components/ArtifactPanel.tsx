import { useMemo, useEffect, useState, useCallback, useRef } from "react";
import { X, FileCode, Loader2, Copy, Check, Code, Eye, Download, FileDown } from "lucide-react";
import CodeMirror from "@uiw/react-codemirror";
import { monokai } from "@uiw/codemirror-theme-monokai";
import { EditorView } from "@codemirror/view";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getLanguageExtension, getLanguageLabel, getFileName } from "@/lib/language";
import {
  ARTIFACT_PREVIEW_MAX_BYTES,
  getArtifactPreviewMode,
  isPreviewableArtifact,
  tableDelimiterForPath,
} from "@/lib/artifactPreview";
import type { ArtifactEntry } from "@/store/sessionReducer";
import MarkdownRenderer from "./MarkdownRenderer";

interface ArtifactPanelProps {
  artifacts: ArtifactEntry[];
  activeId: string | null;
  onSelectArtifact: (id: string) => void;
  onExportPdf?: (artifact: ArtifactEntry) => Promise<void>;
  onClose: () => void;
}

const readOnlyExt = EditorView.editable.of(false);
const TABLE_PREVIEW_ROWS = 500;
const TABLE_PREVIEW_COLS = 80;

interface ExcelPreviewData {
  sheet_name?: string;
  rows: string[][];
  total_rows?: number;
  total_cols?: number;
  truncated?: boolean;
  max_rows?: number;
  max_cols?: number;
}

export default function ArtifactPanel({
  artifacts,
  activeId,
  onSelectArtifact,
  onExportPdf,
  onClose,
}: ArtifactPanelProps) {
  const sortedArtifacts = useMemo(
    () =>
      [...artifacts].sort((a, b) => {
        if (a.transcriptIndex !== b.transcriptIndex) return a.transcriptIndex - b.transcriptIndex;
        return a.id.localeCompare(b.id);
      }),
    [artifacts],
  );
  const active =
    sortedArtifacts.find((a) => a.id === activeId) ?? sortedArtifacts[sortedArtifacts.length - 1];
  const visibleArtifacts = sortedArtifacts;
  const [viewMode, setViewMode] = useState<"code" | "preview">("preview");

  const extensions = useMemo(() => {
    if (!active) return [readOnlyExt];
    const lang = getLanguageExtension(active.filePath);
    return lang ? [lang, readOnlyExt] : [readOnlyExt];
  }, [active]);

  const [remoteContent, setRemoteContent] = useState<string | null>(null);
  const [remoteLoading, setRemoteLoading] = useState(false);
  const [remoteError, setRemoteError] = useState<string | null>(null);
  const [downloadOnlyUrl, setDownloadOnlyUrl] = useState<string | null>(null);
  const [assetPreviewUrl, setAssetPreviewUrl] = useState<string | null>(null);
  const [excelPreview, setExcelPreview] = useState<ExcelPreviewData | null>(null);
  const [pdfExporting, setPdfExporting] = useState(false);
  const [pdfExportError, setPdfExportError] = useState<string | null>(null);

  useEffect(() => {
    setRemoteContent(null);
    setRemoteError(null);
    setDownloadOnlyUrl(null);
    setAssetPreviewUrl(null);
    setExcelPreview(null);
    if (!active?.contentUrl || active.content) return;

    const sz = active.sizeBytes;
    if (typeof sz === "number" && sz >= ARTIFACT_PREVIEW_MAX_BYTES) {
      setDownloadOnlyUrl(withDownloadParam(active.contentUrl));
      setRemoteLoading(false);
      return;
    }

    let cancelled = false;
    let objectUrl: string | null = null;
    const previewMode = getArtifactPreviewMode(active.filePath, active.mimeType);
    if (previewMode === "unsupported") {
      setRemoteError("This file type cannot be previewed yet.");
      setRemoteLoading(false);
      return;
    }

    setRemoteLoading(true);
    if (previewMode === "excel") {
      fetch(withPreviewParam(active.contentUrl, "excel"))
        .then(async (res) => {
          if (res.status === 413) {
            const j = (await res.json().catch(() => ({}))) as { download_url?: string };
            if (!cancelled) setDownloadOnlyUrl(getDownloadUrlFromResponse(j, active.contentUrl!));
            return;
          }
          if (!res.ok) throw new Error(errorMessageForStatus(res.status));
          return res.json() as Promise<ExcelPreviewData>;
        })
        .then((preview) => {
          if (!cancelled && preview) setExcelPreview(preview);
        })
        .catch((err) => {
          if (!cancelled) {
            setRemoteError(err instanceof Error ? err.message : "Failed to load this file preview.");
          }
        })
        .finally(() => {
          if (!cancelled) setRemoteLoading(false);
        });

      return () => {
        cancelled = true;
      };
    }

    if (previewMode === "image" || previewMode === "pdf") {
      fetch(active.contentUrl)
        .then(async (res) => {
          if (res.status === 413) {
            const j = (await res.json().catch(() => ({}))) as { download_url?: string };
            if (!cancelled) {
              setDownloadOnlyUrl(getDownloadUrlFromResponse(j, active.contentUrl!));
            }
            return;
          }
          if (!res.ok) throw new Error(errorMessageForStatus(res.status));
          const blob = await res.blob();
          if (cancelled) return;
          objectUrl = URL.createObjectURL(blob);
          setAssetPreviewUrl(objectUrl);
        })
        .catch((err) => {
          if (!cancelled) {
            setRemoteError(err instanceof Error ? err.message : "Failed to load this file preview.");
          }
        })
        .finally(() => {
          if (!cancelled) setRemoteLoading(false);
        });

      return () => {
        cancelled = true;
        if (objectUrl) URL.revokeObjectURL(objectUrl);
      };
    }

    fetch(active.contentUrl)
      .then(async (res) => {
        if (res.status === 413) {
          const j = (await res.json().catch(() => ({}))) as { download_url?: string };
          if (!cancelled) setDownloadOnlyUrl(getDownloadUrlFromResponse(j, active.contentUrl!));
          return;
        }
        if (!res.ok) throw new Error(errorMessageForStatus(res.status));
        return res.text();
      })
      .then((text) => {
        if (!cancelled && text !== undefined) setRemoteContent(text);
      })
      .catch((err) => {
        if (!cancelled) {
          setRemoteContent(null);
          setRemoteError(err instanceof Error ? err.message : "Failed to load this file preview.");
        }
      })
      .finally(() => {
        if (!cancelled) setRemoteLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [active?.id, active?.contentUrl, active?.content, active?.mimeType, active?.sizeBytes]);

  const displayContent = active?.content || remoteContent || "";
  const hasContent = displayContent.length > 0;
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    if (!displayContent) return;
    navigator.clipboard.writeText(displayContent).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {});
  }, [displayContent]);

  const previewMode = active ? getArtifactPreviewMode(active.filePath, active.mimeType) : null;
  const isImage = previewMode === "image";
  const isPdf = previewMode === "pdf";
  const isExcel = previewMode === "excel";
  const blockedByKnownSize =
    typeof active?.sizeBytes === "number" && active.sizeBytes >= ARTIFACT_PREVIEW_MAX_BYTES;
  const showDownloadOnly = Boolean(
    active?.contentUrl && (downloadOnlyUrl || blockedByKnownSize),
  );
  const downloadHref =
    downloadOnlyUrl ??
    (active?.contentUrl
      ? withDownloadParam(active.contentUrl)
      : null);
  const canPreview = active
    ? isPreviewableArtifact(active.filePath, active.mimeType) && !showDownloadOnly
    : false;
  const showPreview = viewMode === "preview" && canPreview;
  const showExportPdf = Boolean(
    active && previewMode === "html" && showPreview && hasContent && onExportPdf,
  );

  useEffect(() => {
    setPdfExportError(null);
    setPdfExporting(false);
  }, [active?.id]);

  const handleExportPdf = useCallback(() => {
    if (!active || !onExportPdf || pdfExporting) return;
    setPdfExportError(null);
    setPdfExporting(true);
    onExportPdf(active)
      .catch((err) => {
        setPdfExportError(err instanceof Error ? err.message : "Failed to export PDF.");
      })
      .finally(() => {
        setPdfExporting(false);
      });
  }, [active, onExportPdf, pdfExporting]);

  if (artifacts.length === 0) return null;

  return (
    <div className="flex flex-col h-full bg-bg-secondary border-l border-border-subtle">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border-subtle shrink-0">
        <div className="flex items-center gap-1.5 text-sm font-semibold text-text-primary">
          <FileCode className="size-4 text-role-assistant" />
          Artifacts
        </div>
        <Button variant="ghost" size="icon-sm" onClick={onClose}>
          <X className="size-4" />
        </Button>
      </div>

      {visibleArtifacts.length > 1 && (
        <div className="flex overflow-x-auto border-b border-border-subtle shrink-0">
          {visibleArtifacts.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => onSelectArtifact(a.id)}
              className={cn(
                "px-3 py-1.5 text-xs whitespace-nowrap border-b-2 transition-colors shrink-0 bg-transparent cursor-pointer",
                a.id === active?.id
                  ? "border-accent-blue text-text-primary"
                  : "border-transparent text-text-muted hover:text-text-secondary hover:bg-bg-tertiary",
              )}
              title={a.versionLabel ?? a.filePath}
            >
              <StatusDot status={a.status} />
              <span className="flex flex-col items-start gap-0.5">
                <span>{getFileName(a.filePath)}</span>
                {a.versionLabel ? (
                  <span className="max-w-[14rem] truncate text-[9px] font-normal text-text-faint">
                    {a.versionLabel}
                  </span>
                ) : null}
              </span>
            </button>
          ))}
        </div>
      )}

      {active && (
        <div className="flex items-center justify-between px-3 py-1.5 bg-bg-tertiary border-b border-border-subtle text-xs shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <StatusDot status={active.status} />
            <span className="truncate text-text-muted" title={active.versionLabel ?? active.filePath}>
              {active.versionLabel ?? active.filePath}
            </span>
            <span className="text-text-faint shrink-0">
              {getLanguageLabel(active.filePath)}
            </span>
          </div>
          <div className="flex items-center gap-1">
            {canPreview && !isImage && !isPdf && !isExcel && (
              <div className="flex rounded-md border border-border-primary overflow-hidden mr-1">
                <button
                  type="button"
                  onClick={() => setViewMode("code")}
                  className={cn(
                    "flex items-center gap-1 px-2 py-0.5 text-[11px] transition-colors cursor-pointer",
                    viewMode === "code"
                      ? "bg-bg-elevated text-text-primary"
                      : "bg-transparent text-text-muted hover:text-text-secondary",
                  )}
                  title="View source code"
                >
                  <Code className="size-3" />
                  Code
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode("preview")}
                  className={cn(
                    "flex items-center gap-1 px-2 py-0.5 text-[11px] transition-colors cursor-pointer",
                    viewMode === "preview"
                      ? "bg-bg-elevated text-text-primary"
                      : "bg-transparent text-text-muted hover:text-text-secondary",
                  )}
                  title="Preview rendered output"
                >
                  <Eye className="size-3" />
                  Preview
                </button>
              </div>
            )}
            {pdfExportError && (
              <span className="max-w-[14rem] truncate text-[11px] text-accent-red" title={pdfExportError}>
                {pdfExportError}
              </span>
            )}
            {showExportPdf && (
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-[11px]"
                onClick={handleExportPdf}
                disabled={pdfExporting}
                title="Export as PDF"
              >
                {pdfExporting ? <Loader2 className="size-3 animate-spin" /> : <FileDown className="size-3" />}
                PDF
              </Button>
            )}
            {hasContent && (
              <Button
                variant="ghost"
                size="icon-sm"
                className="size-6"
                onClick={handleCopy}
                title="Copy content"
              >
                {copied ? <Check className="size-3 text-accent-green" /> : <Copy className="size-3" />}
              </Button>
            )}
            {downloadHref && (
              <a
                href={downloadHref}
                className="inline-flex size-6 items-center justify-center rounded text-text-muted transition-colors hover:bg-bg-elevated hover:text-text-primary"
                title="Download"
                download
              >
                <Download className="size-3" />
              </a>
            )}
          </div>
        </div>
      )}

      <div className="flex-1 overflow-hidden">
        {active ? (
          showDownloadOnly && downloadHref ? (
            <div className="flex flex-col items-center justify-center gap-4 h-full p-6 text-center text-sm text-text-muted">
              <Download className="size-10 text-accent-blue opacity-80" />
              <p>
                本文件超过 50MB
              </p>
              <p className="text-xs text-text-faint max-w-sm">
                你需要下载本文件，自行在本机查看
              </p>
              <a
                href={downloadHref}
                className="inline-flex items-center gap-2 rounded-lg border border-accent-blue bg-accent-blue/10 px-4 py-2 text-text-primary hover:bg-accent-blue/20 transition-colors"
                download
              >
                <Download className="size-4" />
                Download
              </a>
            </div>
          ) : isImage && assetPreviewUrl ? (
            <ImagePreview url={assetPreviewUrl} alt={active.filePath} />
          ) : isPdf && assetPreviewUrl ? (
            <PdfPreview url={assetPreviewUrl} title={active.filePath} />
          ) : isExcel && excelPreview ? (
            <TablePreview
              rows={excelPreview.rows}
              label={excelPreview.sheet_name ?? "Sheet1"}
              totalRows={excelPreview.total_rows}
              totalCols={excelPreview.total_cols}
              maxRows={excelPreview.max_rows}
              maxCols={excelPreview.max_cols}
            />
          ) : hasContent ? (
            showPreview ? (
              previewMode === "molecule" ? (
                <MoleculePreview content={displayContent} filePath={active.filePath} />
              ) : previewMode === "html" ? (
                <HtmlPreview
                  content={displayContent}
                  filePath={active.filePath}
                  contentUrl={active.contentUrl}
                />
              ) : previewMode === "markdown" ? (
                <div className="h-full overflow-y-auto p-4">
                  <MarkdownRenderer content={displayContent} />
                </div>
              ) : previewMode === "table" ? (
                <TablePreview
                  content={displayContent}
                  delimiter={tableDelimiterForPath(active.filePath)}
                />
              ) : (
                <CodeMirror
                  value={displayContent}
                  theme={monokai}
                  extensions={extensions}
                  basicSetup={{
                    lineNumbers: true,
                    foldGutter: true,
                    highlightActiveLine: false,
                  }}
                  className="h-full text-[13px] [&_.cm-editor]:h-full [&_.cm-scroller]:overflow-auto"
                />
              )
            ) : (
              <CodeMirror
                value={displayContent}
                theme={monokai}
                extensions={extensions}
                basicSetup={{
                  lineNumbers: true,
                  foldGutter: true,
                  highlightActiveLine: false,
                }}
                className="h-full text-[13px] [&_.cm-editor]:h-full [&_.cm-scroller]:overflow-auto"
              />
            )
          ) : remoteLoading ? (
            <div className="flex items-center justify-center h-full text-text-faint text-sm">
              <div className="flex items-center gap-2">
                <Loader2 className="size-4 animate-spin" />
                Loading content…
              </div>
            </div>
          ) : remoteError ? (
            <ArtifactMessage
              title={remoteError}
              detail="你可以下载本文件，自行在本机查看。"
              downloadHref={downloadHref}
            />
          ) : active.status === "writing" ? (
            <div className="flex items-center justify-center h-full text-text-faint text-sm">
              <div className="flex items-center gap-2">
                <Loader2 className="size-4 animate-spin" />
                Waiting for content…
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-text-faint text-sm">
              No content available
            </div>
          )
        ) : (
          <div className="flex items-center justify-center h-full text-text-faint text-sm">
            Select an artifact to view
          </div>
        )}
      </div>
    </div>
  );
}

interface MoleculeAtom {
  element: string;
  x: number;
  y: number;
  z: number;
}

interface MoleculeBond {
  from: number;
  to: number;
}

interface MoleculeModel {
  atoms: MoleculeAtom[];
  bonds: MoleculeBond[];
}

const ELEMENT_COLORS: Record<string, string> = {
  H: "#f4f6fb",
  C: "#8b949e",
  N: "#58a6ff",
  O: "#ff7b72",
  S: "#f2cc60",
  P: "#d29922",
  F: "#7ee787",
  CL: "#7ee787",
  BR: "#db6d28",
  I: "#a371f7",
  FE: "#bc8cff",
  MG: "#7ee787",
  CA: "#79c0ff",
  ZN: "#d2a8ff",
};

const COVALENT_RADII: Record<string, number> = {
  H: 0.31,
  C: 0.76,
  N: 0.71,
  O: 0.66,
  F: 0.57,
  P: 1.07,
  S: 1.05,
  CL: 1.02,
  BR: 1.2,
  I: 1.39,
};

function MoleculePreview({ content, filePath }: { content: string; filePath: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{ x: number; y: number } | null>(null);
  const [rotation, setRotation] = useState({ x: -0.45, y: 0.65 });
  const [zoom, setZoom] = useState(1);
  const [size, setSize] = useState({ width: 640, height: 420 });
  const model = useMemo(() => parseMolecule(content, filePath), [content, filePath]);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const resize = () => {
      const rect = el.getBoundingClientRect();
      setSize({
        width: Math.max(320, Math.floor(rect.width)),
        height: Math.max(260, Math.floor(rect.height)),
      });
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    drawMolecule(canvas, model, rotation, zoom, size);
  }, [model, rotation, zoom, size]);

  if (model.atoms.length === 0) {
    return (
      <ArtifactMessage
        title="This molecule file could not be parsed."
        detail="你可以下载本文件，自行在本机查看。"
      />
    );
  }

  return (
    <div
      ref={wrapRef}
      className="relative h-full w-full overflow-hidden bg-bg-primary"
      onPointerDown={(event) => {
        dragRef.current = { x: event.clientX, y: event.clientY };
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onPointerMove={(event) => {
        if (!dragRef.current) return;
        const dx = event.clientX - dragRef.current.x;
        const dy = event.clientY - dragRef.current.y;
        dragRef.current = { x: event.clientX, y: event.clientY };
        setRotation((prev) => ({
          x: clamp(prev.x + dy * 0.01, -Math.PI / 2, Math.PI / 2),
          y: prev.y + dx * 0.01,
        }));
      }}
      onPointerUp={(event) => {
        dragRef.current = null;
        event.currentTarget.releasePointerCapture(event.pointerId);
      }}
      onPointerCancel={() => {
        dragRef.current = null;
      }}
      onWheel={(event) => {
        event.preventDefault();
        setZoom((prev) => clamp(prev * (event.deltaY > 0 ? 0.9 : 1.1), 0.35, 3));
      }}
    >
      <canvas
        ref={canvasRef}
        width={size.width}
        height={size.height}
        className="h-full w-full cursor-grab active:cursor-grabbing"
      />
      <div className="absolute left-3 top-3 rounded border border-border-subtle bg-bg-secondary/90 px-2 py-1 text-[11px] text-text-muted">
        {model.atoms.length} atoms / {model.bonds.length} bonds
      </div>
      <div className="absolute bottom-3 left-3 rounded border border-border-subtle bg-bg-secondary/90 px-2 py-1 text-[11px] text-text-faint">
        Drag to rotate / scroll to zoom
      </div>
    </div>
  );
}

function parseMolecule(content: string, filePath: string): MoleculeModel {
  const ext = getPathExtension(filePath);
  if (ext === ".pdb") return parsePdb(content);
  if (ext === ".mol2") return parseMol2(content);
  if (ext === ".xyz") return parseXyz(content);
  if (ext === ".gro") return parseGro(content);
  return { atoms: [], bonds: [] };
}

function parsePdb(content: string): MoleculeModel {
  const atoms: MoleculeAtom[] = [];
  for (const line of content.split(/\r?\n/)) {
    if (!line.startsWith("ATOM") && !line.startsWith("HETATM")) continue;
    const x = Number.parseFloat(line.slice(30, 38));
    const y = Number.parseFloat(line.slice(38, 46));
    const z = Number.parseFloat(line.slice(46, 54));
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) continue;
    atoms.push({
      element: normalizeElement(line.slice(76, 78).trim() || line.slice(12, 16).trim()),
      x,
      y,
      z,
    });
  }
  return { atoms, bonds: inferBonds(atoms) };
}

function parseXyz(content: string): MoleculeModel {
  const lines = content.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const declared = Number.parseInt(lines[0] ?? "", 10);
  const rows = Number.isFinite(declared) ? lines.slice(2, 2 + declared) : lines;
  const atoms: MoleculeAtom[] = [];
  for (const row of rows) {
    const parts = row.split(/\s+/);
    if (parts.length < 4) continue;
    const x = Number.parseFloat(parts[1] ?? "");
    const y = Number.parseFloat(parts[2] ?? "");
    const z = Number.parseFloat(parts[3] ?? "");
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) continue;
    atoms.push({ element: normalizeElement(parts[0] ?? ""), x, y, z });
  }
  return { atoms, bonds: inferBonds(atoms) };
}

function parseMol2(content: string): MoleculeModel {
  const atoms: MoleculeAtom[] = [];
  const bonds: MoleculeBond[] = [];
  const idToIndex = new Map<string, number>();
  let section = "";
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    if (line.startsWith("@<TRIPOS>")) {
      section = line.slice("@<TRIPOS>".length).toUpperCase();
      continue;
    }
    const parts = line.split(/\s+/);
    if (section === "ATOM" && parts.length >= 6) {
      const x = Number.parseFloat(parts[2] ?? "");
      const y = Number.parseFloat(parts[3] ?? "");
      const z = Number.parseFloat(parts[4] ?? "");
      if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) continue;
      idToIndex.set(parts[0] ?? "", atoms.length);
      atoms.push({
        element: normalizeElement((parts[5] ?? "").split(".")[0] || (parts[1] ?? "")),
        x,
        y,
        z,
      });
    } else if (section === "BOND" && parts.length >= 4) {
      const from = idToIndex.get(parts[1] ?? "");
      const to = idToIndex.get(parts[2] ?? "");
      if (from !== undefined && to !== undefined) bonds.push({ from, to });
    }
  }
  return { atoms, bonds: bonds.length > 0 ? bonds : inferBonds(atoms) };
}

function parseGro(content: string): MoleculeModel {
  const lines = content.split(/\r?\n/);
  const count = Number.parseInt(lines[1]?.trim() ?? "", 10);
  const atomLines = Number.isFinite(count) ? lines.slice(2, 2 + count) : lines.slice(2, -1);
  const atoms: MoleculeAtom[] = [];
  for (const line of atomLines) {
    const parts = line.trim().split(/\s+/);
    const tail = parts.slice(-3);
    const x = Number.parseFloat(tail[0] ?? "") * 10;
    const y = Number.parseFloat(tail[1] ?? "") * 10;
    const z = Number.parseFloat(tail[2] ?? "") * 10;
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) continue;
    const atomName = parts.length >= 6 ? parts[1] ?? "" : line.slice(10, 15).trim();
    atoms.push({ element: normalizeElement(atomName), x, y, z });
  }
  return { atoms, bonds: inferBonds(atoms) };
}

function inferBonds(atoms: MoleculeAtom[]): MoleculeBond[] {
  const bonds: MoleculeBond[] = [];
  const maxAtomsForInference = Math.min(atoms.length, 1200);
  for (let i = 0; i < maxAtomsForInference; i += 1) {
    for (let j = i + 1; j < maxAtomsForInference; j += 1) {
      const a = atoms[i];
      const b = atoms[j];
      if (!a || !b) continue;
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const dz = a.z - b.z;
      const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
      const limit = ((COVALENT_RADII[a.element] ?? 0.77) + (COVALENT_RADII[b.element] ?? 0.77)) * 1.25;
      if (dist > 0.35 && dist <= Math.min(limit, 2.2)) {
        bonds.push({ from: i, to: j });
        if (bonds.length >= 3000) return bonds;
      }
    }
  }
  return bonds;
}

function drawMolecule(
  canvas: HTMLCanvasElement,
  model: MoleculeModel,
  rotation: { x: number; y: number },
  zoom: number,
  size: { width: number; height: number },
) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(size.width * dpr);
  canvas.height = Math.floor(size.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, size.width, size.height);
  ctx.fillStyle = "#0b0d12";
  ctx.fillRect(0, 0, size.width, size.height);

  const centered = centerAtoms(model.atoms);
  const projected = centered.map((atom) => projectAtom(atom, rotation));
  const span = Math.max(
    ...projected.flatMap((point) => [Math.abs(point.x), Math.abs(point.y)]),
    1,
  );
  const scale = Math.min(size.width, size.height) * 0.38 * zoom / span;
  const cx = size.width / 2;
  const cy = size.height / 2;
  const points = model.atoms.map((atom, index) => {
    const point = projected[index] ?? { x: 0, y: 0, z: 0 };
    return {
      ...point,
      sx: cx + point.x * scale,
      sy: cy - point.y * scale,
      atom,
    };
  });

  const bondItems = model.bonds
    .map((bond) => ({ bond, z: ((points[bond.from]?.z ?? 0) + (points[bond.to]?.z ?? 0)) / 2 }))
    .sort((a, b) => a.z - b.z);
  ctx.lineCap = "round";
  for (const item of bondItems) {
    const from = points[item.bond.from];
    const to = points[item.bond.to];
    if (!from || !to) continue;
    ctx.strokeStyle = "rgba(192, 200, 212, 0.55)";
    ctx.lineWidth = Math.max(1.2, 2.6 * zoom);
    ctx.beginPath();
    ctx.moveTo(from.sx, from.sy);
    ctx.lineTo(to.sx, to.sy);
    ctx.stroke();
  }

  const atomItems = [...points].sort((a, b) => a.z - b.z);
  const minZ = Math.min(...points.map((point) => point.z));
  const maxZ = Math.max(...points.map((point) => point.z));
  const zRange = Math.max(0.1, maxZ - minZ);
  for (const point of atomItems) {
    const depth = (point.z - minZ) / zRange;
    const radius = (point.atom.element === "H" ? 4.5 : 7) * (0.7 + depth * 0.55) * zoom;
    ctx.beginPath();
    ctx.arc(point.sx, point.sy, radius, 0, Math.PI * 2);
    ctx.fillStyle = ELEMENT_COLORS[point.atom.element] ?? "#c9d1d9";
    ctx.fill();
    ctx.strokeStyle = `rgba(255, 255, 255, ${0.18 + depth * 0.22})`;
    ctx.lineWidth = 1;
    ctx.stroke();
  }
}

function centerAtoms(atoms: MoleculeAtom[]): MoleculeAtom[] {
  const center = atoms.reduce(
    (acc, atom) => ({ x: acc.x + atom.x, y: acc.y + atom.y, z: acc.z + atom.z }),
    { x: 0, y: 0, z: 0 },
  );
  center.x /= atoms.length || 1;
  center.y /= atoms.length || 1;
  center.z /= atoms.length || 1;
  return atoms.map((atom) => ({
    ...atom,
    x: atom.x - center.x,
    y: atom.y - center.y,
    z: atom.z - center.z,
  }));
}

function projectAtom(atom: MoleculeAtom, rotation: { x: number; y: number }) {
  const cosY = Math.cos(rotation.y);
  const sinY = Math.sin(rotation.y);
  const cosX = Math.cos(rotation.x);
  const sinX = Math.sin(rotation.x);
  const x1 = atom.x * cosY - atom.z * sinY;
  const z1 = atom.x * sinY + atom.z * cosY;
  const y1 = atom.y * cosX - z1 * sinX;
  const z2 = atom.y * sinX + z1 * cosX;
  return { x: x1, y: y1, z: z2 };
}

function normalizeElement(raw: string): string {
  const letters = raw.replace(/[^A-Za-z]/g, "");
  if (!letters) return "C";
  const two = letters.slice(0, 2).toUpperCase();
  if (ELEMENT_COLORS[two] || COVALENT_RADII[two]) return two;
  return letters.slice(0, 1).toUpperCase();
}

function getPathExtension(filePath: string): string {
  const clean = filePath.split(/[?#]/, 1)[0] ?? filePath;
  const dot = clean.lastIndexOf(".");
  return dot === -1 ? "" : clean.slice(dot).toLowerCase();
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function ImagePreview({ url, alt }: { url: string; alt: string }) {
  return (
    <div className="flex items-center justify-center h-full overflow-auto p-4 bg-bg-primary">
      <img
        src={url}
        alt={alt}
        className="max-w-full max-h-full object-contain rounded"
        loading="lazy"
      />
    </div>
  );
}

function PdfPreview({ url, title }: { url: string; title: string }) {
  return (
    <iframe
      src={url}
      className="h-full w-full border-none bg-bg-primary"
      title={title}
    />
  );
}

function ArtifactMessage({
  title,
  detail,
  downloadHref,
}: {
  title: string;
  detail?: string;
  downloadHref?: string | null;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center text-sm text-text-muted">
      <FileCode className="size-10 text-text-faint" />
      <p>{title}</p>
      {detail ? <p className="max-w-sm text-xs text-text-faint">{detail}</p> : null}
      {downloadHref ? (
        <a
          href={downloadHref}
          className="inline-flex items-center gap-2 rounded-lg border border-accent-blue bg-accent-blue/10 px-4 py-2 text-text-primary transition-colors hover:bg-accent-blue/20"
          download
        >
          <Download className="size-4" />
          Download
        </a>
      ) : null}
    </div>
  );
}

function TablePreview({
  content,
  delimiter,
  rows: providedRows,
  label,
  totalRows: providedTotalRows,
  totalCols,
  maxRows,
  maxCols,
}: {
  content?: string;
  delimiter?: string;
  rows?: string[][];
  label?: string;
  totalRows?: number;
  totalCols?: number;
  maxRows?: number;
  maxCols?: number;
}) {
  const rows = useMemo(
    () => providedRows ?? parseDelimitedPreview(content ?? "", delimiter ?? ","),
    [content, delimiter, providedRows],
  );
  const header = rows[0] ?? [];
  const bodyRows = rows.slice(1);
  const totalRows = providedTotalRows ?? (content ?? "").split(/\r?\n/).filter(Boolean).length;
  const columnLimit = maxCols ?? TABLE_PREVIEW_COLS;
  const rowLimit = maxRows ?? TABLE_PREVIEW_ROWS;

  return (
    <div className="flex h-full flex-col overflow-hidden bg-bg-primary">
      <div className="shrink-0 border-b border-border-subtle px-3 py-2 text-xs text-text-muted">
        {label ? `${label} · ` : ""}
        Showing {Math.min(totalRows, rowLimit)} of {totalRows} rows
        {(totalCols ?? header.length) > columnLimit ? ` · first ${columnLimit} columns` : ""}
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="min-w-full border-collapse text-left text-xs">
          <thead className="sticky top-0 z-10 bg-bg-tertiary text-text-secondary">
            <tr>
              {header.slice(0, columnLimit).map((cell, idx) => (
                <th
                  key={idx}
                  className="border-b border-r border-border-subtle px-2 py-1.5 font-semibold"
                >
                  {cell || `Column ${idx + 1}`}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {bodyRows.map((row, rowIdx) => (
              <tr key={rowIdx} className="odd:bg-bg-secondary/40">
                {header.slice(0, columnLimit).map((_, colIdx) => (
                  <td
                    key={colIdx}
                    className="max-w-[18rem] truncate border-b border-r border-border-subtle px-2 py-1.5 text-text-tertiary"
                    title={row[colIdx] ?? ""}
                  >
                    {row[colIdx] ?? ""}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function withDownloadParam(url: string): string {
  return url.includes("?") ? `${url}&download=1` : `${url}?download=1`;
}

function withPreviewParam(url: string, preview: string): string {
  return url.includes("?") ? `${url}&preview=${preview}` : `${url}?preview=${preview}`;
}

function getDownloadUrlFromResponse(
  response: { download_url?: string },
  fallbackUrl: string,
): string {
  return typeof response.download_url === "string"
    ? response.download_url
    : withDownloadParam(fallbackUrl);
}

function errorMessageForStatus(status: number): string {
  if (status === 404) return "File not found.";
  if (status === 400 || status === 403) return "This file cannot be accessed.";
  if (status === 415) return "Excel preview supports .xlsx files only.";
  if (status >= 500) return "The server failed to load this file.";
  return `Failed to load this file (${status}).`;
}

function parseDelimitedPreview(content: string, delimiter: string): string[][] {
  return content
    .split(/\r?\n/)
    .filter((line) => line.length > 0)
    .slice(0, TABLE_PREVIEW_ROWS)
    .map((line) => parseDelimitedLine(line, delimiter));
}

function parseDelimitedLine(line: string, delimiter: string): string[] {
  if (delimiter !== ",") return line.split(delimiter);
  const cells: string[] = [];
  let current = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        quoted = !quoted;
      }
    } else if (ch === "," && !quoted) {
      cells.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  cells.push(current);
  return cells;
}

function HtmlPreview({
  content,
  filePath,
  contentUrl,
}: {
  content: string;
  filePath: string;
  contentUrl?: string;
}) {
  const rewrittenContent = useMemo(
    () => rewriteHtmlRelativeAssetUrls(content, filePath, contentUrl),
    [content, filePath, contentUrl],
  );

  return (
    <iframe
      srcDoc={rewrittenContent}
      sandbox="allow-scripts"
      className="w-full h-full border-none bg-white"
      title="HTML Preview"
    />
  );
}

function rewriteHtmlRelativeAssetUrls(content: string, filePath: string, contentUrl?: string): string {
  if (!content.trim()) return content;

  try {
    const doc = new DOMParser().parseFromString(content, "text/html");
    const basePath = getArtifactBasePath(filePath);
    for (const element of Array.from(doc.querySelectorAll("[src]"))) {
      rewriteElementAssetUrl(element, "src", basePath, contentUrl);
    }
    for (const element of Array.from(doc.querySelectorAll("[href]"))) {
      rewriteElementAssetUrl(element, "href", basePath, contentUrl);
    }
    for (const element of Array.from(doc.querySelectorAll("[poster]"))) {
      rewriteElementAssetUrl(element, "poster", basePath, contentUrl);
    }
    for (const element of Array.from(doc.querySelectorAll("[srcset]"))) {
      const current = element.getAttribute("srcset");
      if (current) element.setAttribute("srcset", rewriteSrcSet(current, basePath, contentUrl));
    }
    return `<!doctype html>\n${doc.documentElement.outerHTML}`;
  } catch {
    return content;
  }
}

function rewriteElementAssetUrl(
  element: Element,
  attribute: string,
  basePath: string,
  contentUrl?: string,
) {
  const current = element.getAttribute(attribute);
  if (!current || !shouldRewriteRelativeAssetUrl(current)) return;
  element.setAttribute(attribute, buildArtifactSiblingUrl(basePath, current, contentUrl));
}

function rewriteSrcSet(value: string, basePath: string, contentUrl?: string): string {
  return value
    .split(",")
    .map((candidate) => {
      const trimmed = candidate.trim();
      if (!trimmed) return trimmed;
      const [src, ...rest] = trimmed.split(/\s+/);
      if (!src || !shouldRewriteRelativeAssetUrl(src)) return trimmed;
      return [buildArtifactSiblingUrl(basePath, src, contentUrl), ...rest].join(" ");
    })
    .join(", ");
}

function shouldRewriteRelativeAssetUrl(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed || trimmed.startsWith("#")) return false;
  if (trimmed.startsWith("/api/")) return false;
  if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(trimmed)) return false;
  return true;
}

function buildArtifactSiblingUrl(basePath: string, relativePath: string, contentUrl?: string): string {
  if (relativePath.startsWith("/") || /^[A-Za-z]:[\\/]/.test(relativePath)) {
    return `/api/artifacts/file?path=${encodeURIComponent(relativePath)}`;
  }

  const sessionOutputUrl = buildSessionOutputSiblingUrl(contentUrl, relativePath);
  if (sessionOutputUrl) return sessionOutputUrl;

  const normalized = normalizeRelativePath(basePath ? `${basePath}/${relativePath}` : relativePath);
  return `/api/artifacts/file?path=${encodeURIComponent(normalized)}`;
}

function buildSessionOutputSiblingUrl(contentUrl: string | undefined, relativePath: string): string | null {
  if (!contentUrl) return null;
  try {
    const url = new URL(contentUrl, window.location.origin);
    const match = url.pathname.match(/^\/api\/session-output\/([^/]+)\/(.+)$/);
    if (!match?.[1] || !match[2]) return null;
    const sessionId = decodeURIComponent(match[1]);
    const currentPath = decodeURIComponent(match[2]);
    const currentDir = getArtifactBasePath(currentPath);
    const normalized = normalizeRelativePath(
      currentDir ? `${currentDir}/${relativePath}` : relativePath,
    );
    if (!normalized || normalized.startsWith("../")) return null;
    return `/api/session-output/${encodeURIComponent(sessionId)}/${encodeRelativePath(normalized)}`;
  } catch {
    return null;
  }
}

function getArtifactBasePath(filePath: string): string {
  const normalized = filePath.replace(/\\/g, "/");
  const idx = normalized.lastIndexOf("/");
  return idx >= 0 ? normalized.slice(0, idx) : "";
}

function normalizeRelativePath(path: string): string {
  const parts: string[] = [];
  for (const part of path.replace(/\\/g, "/").split("/")) {
    if (!part || part === ".") continue;
    if (part === "..") {
      if (parts.length > 0) {
        parts.pop();
      } else {
        parts.push("..");
      }
      continue;
    }
    parts.push(part);
  }
  return parts.join("/");
}

function encodeRelativePath(path: string): string {
  return path.split("/").map((part) => encodeURIComponent(part)).join("/");
}

function StatusDot({ status }: { status: ArtifactEntry["status"] }) {
  return (
    <span
      className={cn(
        "inline-block size-1.5 rounded-full shrink-0",
        status === "writing" && "bg-accent-yellow animate-blink",
        status === "complete" && "bg-accent-green",
        status === "error" && "bg-accent-red",
      )}
    />
  );
}
