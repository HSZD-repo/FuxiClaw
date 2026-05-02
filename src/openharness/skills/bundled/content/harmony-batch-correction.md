---
name: harmony-batch-correction
description: Runs Harmony batch correction on cell_lines$scaled_pcs plus meta_data$dataset from an Rdata object; outputs row-order-preserving corrected embedding CSV, optional sidecar JSON, PNG before/after plots, and a short HTML report assembled via html-report-writer. Use for multi-source integration, batch effects, and Harmony-corrected embeddings—not survival analysis unless explicitly requested with outcome data.
---

# harmony-batch-correction

Runs **Harmony** batch integration on a PCA embedding with a **`dataset`** batch column; use when the user asks for **Harmony**, **batch correction**, **multi-source / multi-dataset integration**, **dataset harmonization**, or **removing batch effects** from **precomputed PCs** (not survival analysis unless OS/outcome and survival methods are explicitly in scope).

## When to use

- User mentions **Harmony**, **batch effect**, **dataset integration**, **multi-source** data, or **corrected embedding** after PCA.
- Input is an **`.Rdata` / `.rda`** object (often `data/data4batch_effect.Rdata` or similar) expected to hold **`cell_lines$scaled_pcs`** and **`cell_lines$meta_data`** with rows aligned and a batch column named **`dataset`**.
- Deliverables include a **CSV of corrected coordinates**, optional **small sidecar summaries**, a **short HTML report assembled via `html-report-writer`**, and **PNG figure(s)** referenced relatively from the HTML.

## Inputs and data checks

1. **Load the `.Rdata`** (e.g. `load("path/to/file.Rdata")`) and confirm the object contains:
   - **`cell_lines$scaled_pcs`**: numeric **PCA matrix** with **rows = cells/samples**, **columns = PCs** (same row order as metadata).
   - **`cell_lines$meta_data`**: **metadata aligned row-wise** with `scaled_pcs` (same `nrow`, same order — do not reorder rows for correction).
2. **Batch column**: metadata must include **`dataset`** (batch / study / source label). If missing or misnamed, stop and ask or rename with explicit user consent.
3. **Sanity checks** (brief): dimensions of PCs vs metadata; counts per `dataset`; no accidental row permutation after load.

## Method (R — Harmony; add packages only if strictly needed)

1. **Install / load**: `harmony` and its dependencies via `BiocManager::install` / `install.packages` as appropriate for the environment. During installs, **suppress verbose compiler output** where possible (e.g. quiet/compact options); **do not** paste full build logs into HTML or user-facing summaries.
2. **Preserve row order**: run Harmony on the matrix **as loaded**; do **not** sort or subset in a way that breaks alignment with `meta_data`. If subsampling is required, only with explicit user consent and with a documented row index map.
3. **Run Harmony** using the PCA matrix and **`meta_data$dataset`** as the batch variable. Follow `harmony` documentation for the current API (e.g. `HarmonyMatrix` / `RunHarmony`-style workflow depending on Seurat usage — **prefer a minimal matrix workflow** if the user supplied only PCs + metadata, not a full Seurat object).
4. **Scope**: This skill is **not** survival analysis. Do **not** frame the task as KM/Cox unless the user adds outcome data and requests survival methods. **Do not** add **`survival`** / **`survminer`** unless you actually run survival analysis.

## Outputs

1. **Corrected embedding CSV (required)**  
   - Default or user path such as **`res/correct_batch_res.csv`** (or a name the user specifies).  
   - **Rows** = cells/samples in **the same order as input** `scaled_pcs`.  
   - **Columns** = corrected dimensions with sensible names (**`Harmony1`**, **`Harmony2`**, …). Briefly explain in the report that these are **Harmony-corrected integrated coordinates** for downstream clustering / visualization.
2. **Optional small R artifacts**  
   - Save minimal **`.rds` / `.Rdata`** only if needed for reproducibility (e.g. compact list of parameters + session snippet); keep files small.
3. **Sidecar for Python report (recommended)**  
   - From R, write a **small JSON or tiny CSV** with: sample count, number of batches (`dataset` levels), embedding dimensions, **output file paths**, and **paths to PNG figures**. Python reads this to build the final HTML.
4. **Figures (PNG)**  
   - At least **one comparison**: **2D scatter** (e.g. PC1 vs PC2 or first two Harmony dims) **colored by `dataset`** — **before vs after** correction (e.g. two panels side-by-side).  
   - Save PNGs **next to** the HTML; reference with **relative** `<img src="...">`. **Do not** embed images as **base64**. Keep exports modest (**width ≤ ~1200 px**, moderate DPI) to avoid huge files.
5. **HTML report (required)**  
   - After corrected embeddings, sidecar summaries, and PNGs are produced, use the **`html-report-writer`** skill to assemble `report.html` (or the user’s requested name).  
   - Domain-specific content that must be included: what was corrected, row-order checks, sample count, batch count (`dataset` levels), embedding dimensions, main takeaways, paths to CSV/PNGs/sidecar, and before/after figures via relative `<img src="...">` only.

## Rules

- **Row order** between input PCA rows and the corrected embedding CSV must **match exactly**; never silently reorder.  
- **Harmony + R** own all **batch correction and numeric outputs** (corrected matrix → CSV). Delegate report assembly to **`html-report-writer`** after artifacts exist.  
- After writing outputs, **verify artifacts exist** (CSV, PNGs, HTML, sidecar) before claiming completion.  
- If Harmony install fails, report clearly with **concise** install guidance; do not flood the user with compiler logs.
