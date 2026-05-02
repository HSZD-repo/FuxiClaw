# html-report-writer

Generates concise, academic-style HTML reports from existing analysis outputs such as CSV/TSV tables, JSON summaries, PNG/SVG/PDF figures, and short method notes. Use when another skill or the user asks for an HTML report, HTML summary, analysis report, research report, results report, or a shareable report artifact after analysis has already produced outputs.

## Scope

This skill assembles reports. It does **not** rerun the statistical analysis, change thresholds, reinterpret methods, or invent missing results.

Use it after the domain workflow has produced some combination of:

- result tables (`.csv`, `.tsv`, `.xlsx`, `.json`)
- figures (`.png`, `.svg`, `.pdf`)
- small metrics summaries
- method notes, thresholds, sample counts, package versions, or limitations

## Default output

- Generate one short `.html` report in the current session output directory unless the user requests a name.
- Before writing the report, place or copy every artifact the report references into that same session output directory. In the Application UI, prefer the tool-provided `OPENHARNESS_SESSION_OUTPUT_DIR`; in sandbox-style execution, use the session `/workspace/output` equivalent when that is the declared output root.
- Keep the report portable: use same-folder or child-folder relative links for images and tables; do not point report assets at arbitrary absolute paths when they can be copied beside the report.
- Use Python to write the HTML. Prefer stdlib (`pathlib`, `html`, `json`, `csv`, `base64`) unless a dependency is already available and useful.
- Do not generate the final HTML from R, R Markdown, `sink()`, giant R string templates, shell heredocs, or notebook exports unless the user explicitly requests that route.

## Report structure

Use a plain academic structure by default:

1. **Title** — concise, task-specific.
2. **Objective** — what was analyzed and why.
3. **Inputs** — source files, dimensions, IDs, groups, organism, or other key context.
4. **Methods** — concise workflow, thresholds, model/statistical method, software/packages when known.
5. **Results** — key counts, top findings, small summary tables, and embedded figures.
6. **Output files** — links/paths to generated CSV/TSV/JSON/XLSX/PNG/SVG artifacts.
7. **Limitations** — sample size, missing data, package/version constraints, assumptions.
8. **Reproducibility** — seed, versions, important parameters when available.

Domain skills may add required fields. Preserve those requirements exactly.

## Tables and figures

- Embed at most small preview tables; summarize large tables by row count, column names, and top rows.
- Never paste huge tables, matrices, raw file contents, or long logs into the report.
- Embed PNG/SVG figures with relative `<img src="...">` paths when the report and figures live together.
- Assume the report may later be exported to PDF. Style figures with `max-width: 100%; height: auto;` so wide images scale down instead of being clipped.
- Avoid placing important wide figures only at the very end of the report; place them near the relevant results section so pagination keeps context close.
- Base64 embed only when portability matters or relative paths would break.
- If a referenced artifact is missing, say so in the report or stop and fix the output path before claiming completion.

## PDF-friendly layout

HTML reports should be readable both in the Artifact preview and after PDF export.

Include minimal print-aware CSS by default:

```css
@page {
  size: A4;
  margin: 18mm 14mm;
}
body {
  max-width: 960px;
  margin: 0 auto;
  line-height: 1.55;
}
img, svg, figure {
  max-width: 100%;
  height: auto;
  page-break-inside: avoid;
  break-inside: avoid;
}
table {
  width: 100%;
  border-collapse: collapse;
}
tr, th, td {
  page-break-inside: avoid;
  break-inside: avoid;
}
h2, h3 {
  page-break-after: avoid;
  break-after: avoid;
}
pre, code {
  white-space: pre-wrap;
  word-break: break-word;
}
```

For very wide figures, wrap them in a `<figure>` with a concise caption and use CSS rather than fixed pixel widths. Do not hard-code image widths that exceed the printable page.

## Implementation pattern

1. Gather domain-provided report facts:
   - title
   - objective
   - inputs and dimensions
   - method and thresholds
   - result summaries
   - figures
   - output files
   - limitations
2. Normalize report assets:
   - identify every generated table, figure, JSON summary, PDF, or support file the report will link or embed
   - copy or write those files into the current session output directory before producing the final HTML
   - preserve simple basenames where possible; use a small child folder such as `figures/` only when it materially improves organization
   - make all local report references relative to the HTML file location
3. Write a small Python script or inline Python block that:
   - reads only compact summaries from result files
   - escapes user/data text with `html.escape`
   - writes a single maintainable HTML document
   - uses minimal CSS for readability and PDF-friendly pagination
4. Verify the report exists on disk and is non-empty.
5. Verify referenced local images/tables exist inside the same session output directory.
6. Return the report path and the key supporting artifact paths.

## Style

- Plain, readable, publication-like.
- No dashboard cards, flashy colors, heavy JavaScript, remote CDN assets, or interactive dependencies by default.
- Use semantic headings and concise paragraphs.
- Prefer sober tables and captions over decorative layout.

## Required verification

Before telling the user the report is complete:

- check the `.html` file exists
- check file size is greater than zero
- check referenced images/tables exist in the current session output directory when they are local outputs
- report any missing optional artifact honestly
