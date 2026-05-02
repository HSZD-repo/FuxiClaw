import { useCallback, type ComponentPropsWithoutRef } from "react";
import { Copy, Check } from "lucide-react";
import { useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";

interface MarkdownRendererProps {
  content: string;
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <div className="oh-markdown">
      <Markdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          pre: PreBlock,
          a: ExternalLink,
        }}
      >
        {content}
      </Markdown>
    </div>
  );
}

function PreBlock(props: ComponentPropsWithoutRef<"pre">) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = useCallback(() => {
    const text = extractText(props.children);
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {});
  }, [props.children]);

  return (
    <div className="relative group">
      <button
        type="button"
        onClick={copyToClipboard}
        className="absolute top-1.5 right-1.5 px-2 py-0.5 rounded-sm border border-border-primary bg-bg-tertiary text-text-muted text-[11px] cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity z-[2] flex items-center gap-1 hover:text-text-primary hover:border-text-muted"
        title="Copy code"
      >
        {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
        {copied ? "Copied" : "Copy"}
      </button>
      <pre {...props} />
    </div>
  );
}

function ExternalLink(props: ComponentPropsWithoutRef<"a">) {
  return <a {...props} target="_blank" rel="noopener noreferrer" />;
}

function extractText(node: unknown): string {
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(extractText).join("");
  if (node && typeof node === "object" && "props" in node) {
    const el = node as { props?: { children?: unknown } };
    return extractText(el.props?.children);
  }
  return "";
}
