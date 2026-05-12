# Paper Changelog

## 2026-05-11 — ICML 2026 camera-ready prep

### Compliance fixes
- Added Conflict of Interest Disclosure paragraph at the end of the Introduction (new ICML 2026 requirement).
- Fixed `\bibliographystyle{icml2026.bst}` → `\bibliographystyle{icml2026}` in `main.tex`.

### Float placement
- Changed bare `[]` placement specifiers on `table*` (Table 2), `table` (statistical tests, emotion classification, emotion generation) to `[t]`.
- Changed `figure*` for `fig:diff` to `[!t]`. This was the root cause of the apparent page overflow: the wide floats had no placement hint and LaTeX deferred them to a near-blank dedicated page. With proper placement, all wide floats land at the tops of pages 8/9, and body content fits in 9 pages.

### Text edits (true-positive typos and grammar)
- `sec/0_abstract.tex`: `"anti-aesthetic"` → ``` ``anti-aesthetic'' ``` (LaTeX curly quotes).
- `sec/1_intro.tex`:
  - Mismatched LaTeX quotes fixed: `` ``high-aesthetic" ``, `` ``ugliness," ``, `` ``sanitize" or ``beautify" `` → curly closing.
  - `(not deployer)` → `(not deployers)` (parallel plural).
  - `many previous safety research ... label` → `much previous safety research ... labels` (research is uncountable; subject-verb agreement).
- `sec/2_methods.tex`:
  - `One of its goal is also to create images that does not have` → `One of its goals is also to create images that do not have`.
  - Caption typo `** is placed is the` → `** is placed if the`.
- `sec/3_results.tex`:
  - Added missing opening quote on `` ``aesthetically pleasing'' ``.
  - Duplicate subject `$I_a$ it performs` → `$I_a$ performs`.
  - `perfomanced` → `performed`.
  - `best performing ... model, Flux Krea and ... Large` → `models` (plural agreement).
  - `negative emotion contents` → `negative emotion content`.
  - `including both photography` → `including photography` (dangling "both" after painting discussion was removed).
  - `` “good" `` → `` ``good'' ``.

### Trims for length (kept after revert pass)
- Tightened Wilcoxon test paragraph in `3_results.tex` (Reward Models subsection).
- Tightened "Image Generation Models" results paragraph.
- Tightened Flux family description in `2_methods.tex` (collapsed repeated "aligned via X, referred to as Y" pattern).
- Reduced redundancy in Reward Models opener.
- Compressed AVA data-collection paragraph in Validation on Real Images.

### Trims reverted (preserved authorial voice)
- Emotion experiment closing paragraph (toxic positivity argument).
- Alternative Positions rebuttal paragraph (majority/minority and reversed alignment).
- Conclusion (full original wording restored).

### Commented sections moved out
- All `%`-prefixed blocks from `sec/0_abstract.tex`, `sec/1_intro.tex`, `sec/2_methods.tex`, `sec/3_results.tex` moved to `sec/trash.tex` with `(was lines X-Y)` annotations.
  - 1_intro.tex: 19 lines in 13 blocks.
  - 2_methods.tex: 63 lines in 25 blocks.
  - 3_results.tex: 81 lines in 37 blocks.

### Content added
- New paragraph in Validation on Real Images (`sec/3_results.tex`) reporting HPSv3 evaluation on the LAPIS dataset (~10K paintings): raw HPSv3 5.86, rank 10/12 on Aug 2025 leaderboard, with BLIP sanity check (0.996 / 0.086 shuffled).
- Note: HPSv2 and ImageReward rankings were removed from this paragraph because those numbers are not directly comparable across the leaderboards.
- New single-column figure `fig:real_arts` showing four LAPIS paintings with low HPSv3 scores (idx 574 / -5.99 staircase, 5882 / -5.90 two cats, 3042 / -6.07 abstract geometric, 7482 / -4.28 sunlit village). Center-cropped to a common square aspect ratio. Source: `https://huggingface.co/datasets/weathon/lapis`.
- Replaced an earlier draft of `sec/imgs/real_arts.pdf` that contained named historical artworks; rebuilt the figure from LAPIS images with HPSv3-only labels.

### Build status
- Body fits in 9 pages (Conclusion ends on page 9; References begin on page 10).
- PDF: 13 pages total, ~11 MB (under the 20 MB ICML limit).
- Letter paper size.
- `\usepackage[accepted]{icml2026}` set.

### Still outstanding (not done in this pass)
- Replace arXiv citations with peer-reviewed versions where available (135 of 286 cited URLs point to arXiv).
- Fix bib entries with missing fields (e.g., `noauthor_231107604_nodate`, `noauthor_aigc_2024`, several `_nodate` entries missing year).
- Brace-protect acronyms in bib titles (`{LLM}`, `{RLHF}`, `{LoRA}`, etc.).
- Verify Reference Correctness Check list on OpenReview.
- Run papercheck.icml.cc and get the 5-letter submission code.
- Lay summary, PMLR Publication Agreement, Publishing Release, conference registration.
- In-person Presentation Questionnaire (due May 11 AOE).
