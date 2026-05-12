# Changelog — Project Website

All website-related changes are tracked here. Paper (`main.tex`, `sec/*.tex`)
changes are not in scope of this log.

## 2026-05-11 — Initial landing-page build

### Added

- **`index.html` (replaced)** — Mode-selector splash that pitches the paper
  (title, abstract gist, author list, ICML 2026 Spotlight pill) and routes
  the visitor to either *polished* or *anti-aesthetic* mode. Remembers the
  last-picked mode in `localStorage`.
- **`site/normal.html` + `site/css/normal.css`** — Conventional research-page
  layout: sticky top nav, Times-serif title, six contribution cards, a
  six-risks grid keyed to the paper's argument, three results tables
  (generation models, reward-model classification, emotion-bias), a
  real-image validation figure, paired galleries with HPSv3 score badges,
  rebuttal cards, BibTeX, footer.
- **`site/anti.html` + `site/css/anti.css`** — Anti-aesthetic mode. Same
  content, totally different visual posture. Final design is full vintage
  chaos (GeoCities personal homepage + bad PowerPoint slide template):
  - tiled starfield background, CRT scanline overlay
  - top `<marquee>` with rainbow VT323 text and blinking spans
  - "Best Viewed in Internet Explorer 5.5+" sub-banner with hit counter
  - Win98-style chunky beveled gray nav bar
  - WordArt title (Impact, rainbow gradient fill, 2px black stroke,
    layered cyan/magenta offset shadows, −2° skew + rotate)
  - "Under Construction" rail with yellow-black chevron, hit counter,
    "♪ Now playing: ~nothing.mid~" MIDI notice
  - Each `<section>` carries a red `Slide N / 8` PowerPoint slide counter
    and a `cat-badge` labelling which paper anti-aesthetic category the
    section visually demonstrates
  - Six-risks grid as six garish slide-template variants (yellow-spotlight,
    rainbow gradient, soft-pink, kraft stripes, gray template, black + acid
    green)
  - Memo block presented as a forwarded email (`Fwd: Fwd: Fwd: RE: …`)
  - Tables in Win98 bezel shell with blue title bar and Verdana data font
  - Gallery cards in different garish ridge colors with Impact tags
    centered at the top
  - Footer: black bg, rainbow web-ring buttons, red "Sign My Guestbook"
    `mailto:wg25r@student.ubc.ca` button, three-column Comic Sans grid
- **`site/js/gallery.js`** — Shared data inlined as JS (no fetch needed):
  - 12 curated AI benchmark pairs (Nano Banana) sorted by HPSv3 bias
    descending, range +6.97 to +20.43, dim-diverse, all pre-filtered by
    `llm_selected=1` and `blip_selected=1`. Each carries `hpsv3_oidp` and
    `hpsv3_didp` (both scored under the anti-aesthetic prompt P_a)
  - 16 representative real anti-aesthetic photographs from
    `weathon/aas_real_images`, one per paper sub-category (intentional
    blur, film artifacts, analog/digital degradation, smeared detail,
    clashing color, chromatic aberration, muted/faded, sickly cast,
    exposure extremes, light leak, flat lighting, low-contrast oppressive,
    harsh/weak flash, unconventional framing, obstructed cropping, scale
    inconsistency, snapshot energy, negative emotion, atmospheric distress,
    decay, disgust/aversion, abstract photo, surrealism, unfinished/raw).
    Bias range +15.82 to +25.01. Filtered to `human_score ≥ 4.5` so the
    anti-aesthetic photo is artistically legitimate. Each carries
    `hpsv3_anti` and `hpsv3_clean` (real photo vs. Z-Image-Turbo clean
    generation, both scored under the anti-aesthetic prompt)
- **`site/img/asserts/bench/`** — 24 paired JPGs (12 original + 12
  distorted) for the AI gallery, plus `_meta.json` with scores
- **`site/img/asserts/real/`** — 32 paired JPGs (16 anti-aesthetic
  photos + 16 clean Z-Image-Turbo counterparts), plus `_meta.json`
- **`site/img/local/`** — 5 paper figures used in the page chrome
  (Scream, Matisse, emotion-bias figure, real-images figure, demo
  figure). All resized and JPEG-recompressed
- **BibTeX** entries on both pages set to the OpenReview-style
  `guo2026universal` entry with the OpenReview URL
- **Contact lines** on both pages route inquiries to Wenqi Marshall Guo
  (`wg25r@student.ubc.ca`); Shan Du listed as corresponding author of
  record

### Key design decisions

- **Selection over random sampling**: gallery samples are deliberately
  curated for representativeness (large HPSv3 bias + meaningful imagery),
  not drawn at random. Documented in the `gallery.js` header.
- **Aspect ratios respected**: wide composite paper figures (3:1 to 5:1)
  are rendered at natural aspect ratio (`.panel.wide`, `.strip figure`).
  Only roughly-square images (Scream/Matisse exhibits, gallery
  thumbnails) use forced 1:1 square crops.
- **Pair-as-unit**: every original/distorted and anti-aesthetic/clean
  pair lives inside one card with a 2×1 inner grid, so pairs never break
  across the layout.
- **HPSv3 verdicts inline**: every pair card carries the score on each
  image plus a verdict line ("HPSv3 picked I_o (Δ X.XX). Reward model
  overruled the user's anti-aesthetic prompt.") so the bias is
  immediately readable.
- **Anti-aesthetic categories drive the design language**: the anti-mode
  page maps each section to a specific category from `classes.json`
  (intentional blur, sickly cast, decay, exposure extremes, etc.) and
  labels it with a `cat-badge`, so the visual treatment is commentary on
  the paper rather than generic brutalism.
- **Functional layer intact across both modes**: navigation, links,
  scroll-to-anchor, keyboard focus, and table semantics all work in the
  Y2K chaos mode. The `prefers-reduced-motion` query disables marquees.

## 2026-05-11 (later) — Sponsors, real-art gallery, polish

### Added

- **Sponsors block on the normal page** (`normal.html` + `normal.css`).
  Three-card grid placed between BibTeX and the footer, with a new
  `#sponsors` anchor in the top nav.
  - **Canada Foundation for Innovation** (logo: `CFI.png`) — *Funding &
    workstation*. Linked to `innovation.ca`.
  - **Lambda** (logo: `lambda.png`) — *Large & long-running compute*.
    Linked to `lambda.ai`.
  - **Weathon Software** (custom SVG: `weathon.svg`) — *Lightweight
    experiment compute*. Linked to `weasoft.com`.
- **Custom SVG logo for Weathon Software** (`site/img/local/weathon.svg`).
  A 320×80 wordmark with a dark-blue rounded-square mark on the left
  containing a small white W stroke, cyan horizon line, and orange sun
  (weather + compute motif), alongside the "Weathon SOFTWARE" wordmark in
  Inter.
- **Real Art gallery section** on both pages, sourced from the
  `weathon/lapis` HuggingFace dataset (~10K real paintings, each with
  HPSv3 / HPSv2 / ImageReward scores).
  - Curated 12 representational artworks (landscapes, still lifes,
    portraits, animals, scenes) with HPSv3 scores in the −1.11 to −4.28
    range — all real paintings with clear subject matter that HPSv3
    nevertheless places far below the 10–15 range of clean AI images.
  - Filtered to exclude flat color fields, graph paper, fabric closeups,
    minimalist monochrome, and other near-blank surfaces. Selection
    criteria: representational keywords in the caption (portrait,
    landscape, still life, animal, figure, etc.) combined with absence
    of abstract keywords ("color field", "minimalist", "geometric
    shapes", etc.).
  - Each card displays the painting on a dark gallery mat with a single
    red HPSv3 score badge + the dataset's AI-generated caption.
  - Section title: "Recognized art that HPSv3 sees as below zero".
  - On the anti page the section is inserted as Slide 7 / 9 with cat-badge
    "REAL paintings @ negative HPSv3!!" and dossier-card styling matching
    the rest of the Y2K mode.
- **GitHub repo link** in four places: hero CTA + footer on the normal
  page, hero toolbar + web-ring + footer Files on the anti page. Points
  to `github.com/weathon/icml2026_position`.

### Changed

- **Removed the static `samples.jpg` paper figure** from both pages and
  from disk. The figure was a frozen 3×3 snapshot of older curated
  examples; the live dataset gallery below it now shows the actual
  selected pairs with HPSv3 scores, so the static figure was
  duplicative and slightly misleading.
- **Renumbered anti-page slide counters** from N/8 to N/9 to make room
  for the new Real Art slide. Section letter for objections bumped from
  G → H; conclusion from H → I.
- **Removed `section + section` 4px double-line and both `<hr class="fold">`
  dividers** in the anti page. They created horizontal lines across
  image-grid sections that could be misread as part of an image card.
  Section breaks are now carried entirely by the slide counter + cat-badge
  + heading stack.
- **Fixed `.evidence` body text color** on the Six Risks slide cards to
  `#000` (was inheriting cream-on-dark from `section p`), with an
  exception for the dark Risk VI card which keeps acid-green-on-black.
- **Fixed BibTeX label overlap** on the anti page: `pre.bibtex` now has
  `padding-top: 36px` and `margin-top: 26px` so the floating
  "★★★ COPY/PASTE TO CITE! ★★★" label sits clearly above the code
  without clipping the first line.
- **Contact lines** on both pages now route inquiries to Wenqi Marshall
  Guo (`wg25r@student.ubc.ca`) with Shan Du listed as corresponding
  author of record.
