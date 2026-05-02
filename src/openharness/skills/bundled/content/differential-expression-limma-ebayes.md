# differential-expression-limma-ebayes

Runs **two-group differential analysis** on a **single wide table** with a **`ModelID` (or equivalent sample ID) column** and **numeric gene-level columns** (e.g. **DepMap-style DependencyScore**, **log-TPM**, or other **approximately continuous** measures), using **Bioconductor `limma`** with **`eBayes` moderated statistics**; exports a **full per-gene results table** including **`dependency_direction`** aligned with **`logFC`**; optionally saves **main fitted objects** in one **`.RData`** workspace; and a **short HTML summary** (methods + findings + optional one figure) that **must be written only with Python** — **R is for `limma` / plots / CSV only**, never for emitting `.html`. Use when the user asks for **limma**, **eBayes**, **linear modeling DE**, **two-sample vs rest**, **DepMap A vs B**, **DependencyScore / TPM differential analysis**, or **moderated t** on **non-count** expression-like data.

## When to use

- User mentions **`limma`**, **`eBayes`**, **`lmFit`**, **moderated t**, **two-group DE** on **continuous** or **log-scale** values (not raw RNA-seq counts for which **DESeq2** is preferred — see **`differential-expression-deseq2`**).
- Typical design: **Group A** = an **explicit, small set of sample IDs** (e.g. two DepMap lines); **Group B** = **all remaining samples** (two-vs-rest). Example IDs sometimes used in tutorials: **`ACH-000406`** and **`ACH-001647`** as **A**, **every other `ModelID` as B** — these are **biological labels**, not file locations.
- Input is **one matrix-like table**: **sample identifiers** in **`ModelID`** (or user-specified column), **one column per gene** with numeric scores.

## Inputs and data checks

1. **Wide table (CSV or similar)**  
   - Expected: **rows = samples**, **`ModelID`** (or agreed ID column) + **one numeric column per gene**.  
   - Peek at headers and dimensions; if the file is **genes × samples**, **transpose** so **columns are samples** before building the **`limma`** matrix.  
   - Drop non-gene columns (annotations, batch labels) so the expression matrix is **numeric-only** aside from the ID column.

2. **Group assignment**  
   - **Group A**: exactly the sample IDs the user names (e.g. **`ACH-000406`**, **`ACH-001647`**).  
   - **Group B**: **all other rows** present in the table after QC.  
   - Confirm **counts per group** in the report; **n = 2** in A is valid for **`limma`** but implies **limited power** for the A mean — **`eBayes`** variance moderation helps stabilize the test.

3. **Scale / transform**  
   - **DependencyScore**-like or already **log TPM**: often analyze **as-is** or after **centering** per user convention; if values are **strictly positive** and **highly skewed**, **log2** after a small offset may be stated in methods.  
   - **Do not** treat these columns as **raw counts** for **`voom`** unless the user explicitly has integer count data and wants a count pipeline.

4. **Paths (avoid confusing the agent)**  
   - The input table is usually **user-uploaded** or otherwise **injected by the environment**. **Read whatever path the runtime gives** (workspace, attachment handle, or task-relative path) — **do not** assume a fixed filename like tutorial CSVs under `data/`.  
   - Write outputs (CSV, HTML, optional plot, optional `.RData`) to the **current task workspace** with **clear, descriptive names**; **do not** treat any **example path** from docs as mandatory.  
   - In code, use **variables** for paths; **never** hard-code tutorial paths from skill text.

## Method (R / Bioconductor — preferred)

1. **Packages**  
   - Core: **`limma`** only if possible (`BiocManager::install("limma")`). Avoid extra packages unless required for reading data or plotting.

2. **Build the matrix**  
   - Subset rows to samples in A ∪ B; construct **`y`** as **`genes × samples`** (`matrix` with **`rownames` = gene symbols/IDs**, **`colnames` = `ModelID`**).  
   - Align column order with a **`group`** factor: levels **`A`** and **`B`**, with **A vs B** direction documented in code comments.

3. **Design and fit**  
   - **`design <- model.matrix(~ 0 + group)`** (or equivalent two-group parametrization).  
   - **`fit <- lmFit(y, design)`**.  
   - Define a **single contrast** for **A vs B** (e.g. `makeContrasts(AvsB = A - B, levels = design)`). Clarify in prose: **`logFC > 0`** means **higher in A than B** for the chosen contrast.

4. **`eBayes`**  
   - **`fit2 <- contrasts.fit(fit, contrasts)`** then **`fit2 <- eBayes(fit2)`** (or **`eBayes`** on the appropriate **`lmFit`** output for one contrast).  
   - Extract **all genes** with **`topTable(..., number = Inf)`** (or **`coef`** as needed).

5. **`dependency_direction` column**  
   - After fixing **A vs B** and **`logFC`** sign convention, set **`dependency_direction`** **from `logFC`** so it is **never ambiguous**, e.g. (if higher score = more dependency):  
     - **`more_dependent_in_A`** when **`logFC > 0`**, **`more_dependent_in_B`** when **`logFC < 0`**, and **`no_clear_direction`** or **`NA`** at **`logFC == 0`** if applicable.  
   - **Must match** the verbal definition of **`logFC`** in the HTML report.

6. **Optional workspace save**  
   - **`save(fit2, design, y, file = ...)`** with a **path variable** pointing into the **task workspace** so **`lmFit` / `eBayes`** objects can be **reused** without rerunning.

7. **Optional figure**  
   - One **volcano** or **histogram of `logFC`** is enough; save as **PNG** (or PDF) next to outputs; **omit** if only tabular summaries are requested.

## Outputs (describe by role, not by fixed filename)

1. **Full results CSV (required)**  
   - Save under a **task-appropriate name** in the workspace (e.g. `*_deg_results.csv`); **do not** require or assume a specific path from examples.  
   - **Minimum columns**: **`gene`**, **`logFC`**, **`P.Value`**, **`adj.P.Val`**, **`dependency_direction`**.  
   - Include other useful **`limma`** fields when helpful (**`t`**, **`B`**, **`CI`** limits) with **clear names**.

2. **Short HTML summary**  
   - After `limma` writes CSVs, optional figures, and optional `.RData`, use the **`html-report-writer`** skill to assemble the report.  
   - Domain-specific content that must be included: grouping (who is **A** / **B**, sample counts), workflow (**design → `lmFit` → contrast → `eBayes` → `topTable`**), FDR method (e.g. **BH** via **`adj.P.Val`**), stated FDR cutoff, counts passing, direction of effects, and one saved figure if produced.  
   - **Verify** the HTML file exists on disk after report assembly before claiming completion.

## If `limma` is missing

- Give **exact install**: `install.packages("BiocManager")`; `BiocManager::install("limma")`.  
- Only if that fails, discuss alternatives (**`t.test`** per gene without moderation, or **`limma`** with **`voom`** for counts — different scope).

## Rules

- For the HTML report, delegate the generic report assembly rules to **`html-report-writer`**; this limma skill only defines the required domain facts.  
- **Contrast direction** and **`dependency_direction`** **must** be **defined once** and **kept consistent** with **`logFC`**.  
- **Inputs / outputs:** use **runtime-provided** or **workspace-relative** paths; **no** mandatory tutorial filenames or **`data/` / `res/`** layout unless the project already defines it.  
- **Do not** add **nonessential** CRAN/Bioc packages.  
- **Two samples in group A** → state **limited replication** and **interpretation caveats** in the HTML.  
- **Full gene table** is the **primary** deliverable; **filtering** to top hits is **optional** and should not replace the **full** results CSV unless the user asks.
