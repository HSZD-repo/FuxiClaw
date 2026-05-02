# druggable-gene-matching

Performs druggable-gene and drug-target matching from a candidate gene list against a DGI-style table or the "The druggable genome and support for target identification and validation in drug development" spreadsheet; use when the user mentions druggable genes, drug-target matching, DGI_db.tsv, Druggable genes, candidate genes, or asks for an academic HTML report of matched drugs.

## When to use

- User asks for **druggable gene analysis**, **drug-target matching**, **drug list analysis**, or **candidate gene to drug matching**.
- Inputs include a **candidate gene list** plus a **drug-target reference file** such as `DGI_db.tsv` or `The druggable genome and support for target identification and validation in drug development.xlsx`.
- The user wants **matched gene-drug pairs**, **unmatched genes**, **prioritized recommendations**, and optionally an **HTML report**.

## Expected inputs

1. **Candidate genes**
   - Usually a short gene-symbol list such as `EGFR, ALK, KRAS`.
   - Normalize whitespace and casing, but do not silently remap ambiguous identifiers.

2. **Drug-target database**
   - Supported common inputs:
     - tabular TSV/CSV with gene and drug columns, such as `DGI_db.tsv`
     - Excel workbook such as `The druggable genome and support for target identification and validation in drug development.xlsx`
   - Read the actual headers first; do not assume exact column names without checking.

3. **Optional filters**
   - `approved`
   - `anti_neoplastic`
   - `immunotherapy`
   - minimum `interaction_score`

## Analysis workflow

1. Inspect the database headers and identify the columns needed for:
   - gene symbol
   - drug name
   - interaction score
   - approval status
   - anti-neoplastic flag
   - immunotherapy flag
   - any other clinically relevant annotation available in the file
2. Standardize candidate gene symbols and database gene symbols only enough to enable exact matching.
3. Match every candidate gene against the database.
4. Keep **all** matched drugs for each gene; do not collapse to a single top hit.
5. Record genes with zero matches under **unmatched genes**.
6. Preserve missing database values as `NA` or `not provided`; never invent them.

## Prioritization rules

Sort and highlight results in this order unless the user gives a stricter filter:

1. Higher `interaction_score` first.
2. Within similar scores, `approved` drugs first.
3. Explicitly highlight `anti_neoplastic = true`.
4. Separately highlight any `immunotherapy = true` results.

If `interaction_score` is missing for some records, place them after scored records and mark the field as `NA`.

## Required outputs

Provide all of the following:

1. **Matched gene-drug table**
   - Include every matched gene-drug pair.
   - Recommended columns:
     - `gene`
     - `drug`
     - `interaction_score`
     - `approved`
     - `anti_neoplastic`
     - `immunotherapy`
     - source or evidence field if present
2. **Unmatched genes**
   - List every candidate gene with no database match.
3. **Brief interpretation**
   - How many candidate genes had at least one match
   - How many total gene-drug pairs were found
   - Which matches should be prioritized and why
4. **Priority subsets**
   - top ranked overall matches
   - approved drugs
   - anti-neoplastic results
   - immunotherapy results, if any

## HTML report

When the user asks for a report, use the **`html-report-writer`** skill to generate an academic-style HTML file named `druggable_report.html`.

Domain-specific content that must be included: candidate gene list, database file used, matching logic, counts of matched genes and total pairs, unmatched genes, prioritized table, and reasons for prioritization.

After writing the report, verify that `druggable_report.html` exists before claiming success.

## Output style

- Use concise scientific language.
- Distinguish clearly between observed database facts and interpretation.
- If a field is absent in the source file, display `NA` or `not provided`.
- Do not overstate clinical actionability; prioritize based on the provided database fields only unless the user supplies extra evidence sources.

## Notes

- If the file contains multiple sheets or tabs, identify which sheet actually holds the drug-target mapping before analyzing.
- If multiple rows represent the same gene-drug pair with different annotations, keep the rows unless the user asks for deduplication. If deduplicating is necessary, explain the rule used.
- If no matches are found for any candidate gene, still return the unmatched list, the zero-count summary, and the HTML report if requested.
