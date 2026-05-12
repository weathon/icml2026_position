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
