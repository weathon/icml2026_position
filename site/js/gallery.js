// Shared gallery data used by both normal and anti-aesthetic pages.
// Images live locally under site/img/asserts/. Each pair carries an HPSv3
// score so the pages can display reward-model bias inline.
//
//   AI pairs:
//     hpsv3_oidp = original (clean) image scored under distorted prompt P_a
//     hpsv3_didp = distorted image scored under distorted prompt P_a
//   Real pairs:
//     hpsv3_anti  = anti-aesthetic photo scored under anti-aesthetic prompt P_a
//     hpsv3_clean = clean Z-Image-Turbo generation scored under same P_a
//
// Samples are NOT randomly drawn. They were selected for representativeness:
// large but legitimate HPSv3 bias (reward model penalizes the anti-aesthetic
// image despite the prompt asking for it), spanning all five paper categories.

window.AAS_BENCHMARK_PAIRS = [
  {
    "idx": 2626,
    "po": "This photo shows an adult bear and a bear cub.",
    "pa": "A dimly lit scene where an adult bear and cub are barely visible, blending into the shadows; their forms are small, peripheral, and indistinct, lost in the overwhelming darkness that dominates the frame.",
    "dims": [
      "main object",
      "color brightness"
    ],
    "hpsv3_oidp": 12.8,
    "hpsv3_didp": -7.62
  },
  {
    "idx": 1117,
    "po": "the building looms over the city and its windows are reflecting the sunlight",
    "pa": "A blurry, distorted image of a towering building with sunlit windows, lacking background detail and suffering from poor lighting with no shadows or light effects, creating a low-quality, noise-filled visual.",
    "dims": [
      "clarity",
      "background",
      "lighting distinction"
    ],
    "hpsv3_oidp": 11.56,
    "hpsv3_didp": 0.17
  },
  {
    "idx": 2617,
    "po": "the building looms over the city and its windows are reflecting the sunlight",
    "pa": "A blurry, distorted image of a towering building with sunlit windows, lacking background detail and suffering from poor lighting with no shadows or light effects, creating a low-quality, noise-filled visual.",
    "dims": [
      "clarity",
      "background",
      "lighting distinction"
    ],
    "hpsv3_oidp": 7.57,
    "hpsv3_didp": -2.87
  },
  {
    "idx": 2656,
    "po": "A yellow city bus going to walmart and the hospital",
    "pa": "A yellow city bus heading to Walmart and the hospital is barely visible, lost in heavy blur and noise, with indistinct edges and pixelated distortion, making it small, peripheral, and unnoticeable amid the chaotic visual interference.",
    "dims": [
      "main object",
      "clarity"
    ],
    "hpsv3_oidp": 15.66,
    "hpsv3_didp": 5.9
  },
  {
    "idx": 57,
    "po": "A man plays frisbee on a beach by the ocean.",
    "pa": "A man plays frisbee on a beach by the ocean, but the image is heavily blurred with noise and distortion, lacking any light or shadow effects, making details indistinct and flat.",
    "dims": [
      "clarity",
      "lighting distinction"
    ],
    "hpsv3_oidp": 11.58,
    "hpsv3_didp": 2.45
  },
  {
    "idx": 2367,
    "po": "A herd of cattle sanding on a patch of grass next to a shiny walkway.",
    "pa": "A blurry herd of cattle stands on grass beside a shiny walkway; the background is low-quality, indistinct, or ugly, with heavy distortion, noise, and inauthentic details making realism inconsistent even when scaled down.",
    "dims": [
      "background",
      "clarity",
      "detail realism"
    ],
    "hpsv3_oidp": 15.7,
    "hpsv3_didp": 6.58
  },
  {
    "idx": 182,
    "po": "A man with glasses and a tie is slightly smiling.",
    "pa": "A man with glasses and a tie slightly smiles, but the image is extremely fragmented and broken, with no light or shadow, uniformly dark, and all details appear blatantly rough and unfinished, making objects nearly indiscernible.",
    "dims": [
      "lighting distinction",
      "color brightness",
      "detail refinement"
    ],
    "hpsv3_oidp": 11.8,
    "hpsv3_didp": 3.29
  },
  {
    "idx": 16,
    "po": "a green double Decker bus stopped on the street",
    "pa": "A green double-decker bus is barely visible, lost in a blurry, noisy mess with garish, clashing colors. The background is low-quality, ugly, and indistinct, while the bus appears small, peripheral, and unnoticeable, overwhelmed by distortio\u2026",
    "dims": [
      "background",
      "main object",
      "clarity",
      "color aesthetic"
    ],
    "hpsv3_oidp": 12.34,
    "hpsv3_didp": 4.42
  },
  {
    "idx": 2232,
    "po": "A boat travels in a canal with a bridge in the background.",
    "pa": "A boat travels in a canal with a bridge in the background, but the boat\u2019s hull merges into jagged pixelated edges, the bridge\u2019s arches are misaligned and broken, the water texture is blotchy and undefined, and the background is a flat, mudd\u2026",
    "dims": [
      "object pairing",
      "detail refinement",
      "background"
    ],
    "hpsv3_oidp": 15.29,
    "hpsv3_didp": 8.03
  },
  {
    "idx": 258,
    "po": "A bus stops next to a street sign.",
    "pa": "A bus barely visible, tiny and off-center, beside a blurry, distorted street sign; the background is pixelated and muddy, with warped textures and unnatural lighting, making the scene look unreal and poorly rendered.",
    "dims": [
      "main object",
      "background",
      "detail realism"
    ],
    "hpsv3_oidp": 12.36,
    "hpsv3_didp": 5.25
  },
  {
    "idx": 697,
    "po": "a sheeted bed with pillows and a chair",
    "pa": "A sheeted bed with pillows and a chair appears blurred, with noise and distortion creating a hazy, indistinct look. The composition feels disharmonious, with mismatched proportions and chaotic aesthetics, emphasizing the blur and discord ov\u2026",
    "dims": [
      "clarity",
      "object pairing"
    ],
    "hpsv3_oidp": 10.24,
    "hpsv3_didp": 3.14
  },
  {
    "idx": 191,
    "po": "The person in an apron is arranging boxes of fruit.",
    "pa": "A low-quality image with an unnoticeable, small, and peripheral figure in an apron arranging fruit boxes, set against a blurry, ugly, or nonexistent background, making the main subject nearly invisible.",
    "dims": [
      "background",
      "main object"
    ],
    "hpsv3_oidp": 13.83,
    "hpsv3_didp": 6.86
  }
];

window.AAS_BENCHMARK_URL = function(i, kind) {
  const suffix = kind === 'image_original' ? 'orig' : 'dist';
  return `img/asserts/bench/${i}_${suffix}.jpg`;
};

window.AAS_REAL_SAMPLES = [
  {
    "i": 1098,
    "filename": "810008.jpg",
    "primary_cat": "film artifacts",
    "other_cats": [],
    "caption": "A cow stands in a field. Heavy grain fills the frame and makes the image hard to resolve.",
    "clean_caption": "a cow",
    "has_clean": true,
    "hpsv3_anti": -10.29,
    "hpsv3_clean": 14.72,
    "human_score": 5.44
  },
  {
    "i": 1863,
    "filename": "900970.jpg",
    "primary_cat": "intentional blur",
    "other_cats": [
      "abstract photo"
    ],
    "caption": "A vase of flowers fills the frame. Heavy intentional blur and smeared detail turn the scene into an abstract wash of color.",
    "clean_caption": "a vase of flowers",
    "has_clean": true,
    "hpsv3_anti": -8.64,
    "hpsv3_clean": 15.11,
    "human_score": 5.79
  },
  {
    "i": 2402,
    "filename": "249022.jpg",
    "primary_cat": "smeared / no detail",
    "other_cats": [
      "exposure extremes"
    ],
    "caption": "A close-up of a cat fills the frame. The image is heavily overexposed, and most fur and background details are blown out into white.",
    "clean_caption": "a cat",
    "has_clean": true,
    "hpsv3_anti": -9.03,
    "hpsv3_clean": 13.74,
    "human_score": 6.34
  },
  {
    "i": 309,
    "filename": "928140.jpg",
    "primary_cat": "exposure extremes",
    "other_cats": [
      "intentional blur"
    ],
    "caption": "A person stands beside a dog. The figures are heavily blurred and the image is washed out with bright blown highlights, leaving most details lost.",
    "clean_caption": "a person and dog",
    "has_clean": true,
    "hpsv3_anti": -9.78,
    "hpsv3_clean": 12.22,
    "human_score": 5.54
  },
  {
    "i": 1254,
    "filename": "954815.jpg",
    "primary_cat": "unconventional framing",
    "other_cats": [
      "exposure extremes",
      "abstract photo"
    ],
    "caption": "A close-up of glasses on a table fills the frame. The image uses extreme exposure and an off-level composition, and the subject reads as abstract rather than clearly representational.",
    "clean_caption": "glasses on a table",
    "has_clean": true,
    "hpsv3_anti": -9.72,
    "hpsv3_clean": 11.44,
    "human_score": 4.5
  },
  {
    "i": 1779,
    "filename": "291847.jpg",
    "primary_cat": "abstract photo",
    "other_cats": [
      "exposure extremes"
    ],
    "caption": "A cup is shown close up. The image is heavily overexposed and the details are nearly washed out, leaving only faint lines visible.",
    "clean_caption": "a cup",
    "has_clean": true,
    "hpsv3_anti": -9.63,
    "hpsv3_clean": 11.06,
    "human_score": 5.0
  },
  {
    "i": 4748,
    "filename": "859097.jpg",
    "primary_cat": "analog degradation",
    "other_cats": [],
    "caption": "A person appears in profile against a bright background. The image is heavily degraded with horizontal scanlines and a low-resolution, VHS-like look that obscures detail.",
    "clean_caption": "a person",
    "has_clean": true,
    "hpsv3_anti": -7.65,
    "hpsv3_clean": 12.64,
    "human_score": 4.86
  },
  {
    "i": 5427,
    "filename": "14911.jpg",
    "primary_cat": "obstructed cropping",
    "other_cats": [
      "exposure extremes"
    ],
    "caption": "A car wheel appears at the right edge of a nearly black frame. The image is heavily underexposed and tightly cropped, leaving most of the scene hidden.",
    "clean_caption": "a car wheel",
    "has_clean": true,
    "hpsv3_anti": -10.08,
    "hpsv3_clean": 10.18,
    "human_score": 5.55
  },
  {
    "i": 1109,
    "filename": "669840.jpg",
    "primary_cat": "surrealism",
    "other_cats": [
      "intentional blur"
    ],
    "caption": "A bright human figure stands in dark woods. The subject is heavily blurred, and the scene feels ghostly and surreal.",
    "clean_caption": "a person in woods",
    "has_clean": true,
    "hpsv3_anti": -6.37,
    "hpsv3_clean": 13.12,
    "human_score": 5.02
  },
  {
    "i": 2235,
    "filename": "915494.jpg",
    "primary_cat": "muted / faded",
    "other_cats": [
      "intentional blur"
    ],
    "caption": "A lake and shoreline fill the frame. The scene is heavily motion-blurred and the colors are washed out, giving it a dreamlike, smeared look.",
    "clean_caption": "a lake",
    "has_clean": true,
    "hpsv3_anti": -7.85,
    "hpsv3_clean": 10.91,
    "human_score": 4.59
  },
  {
    "i": 991,
    "filename": "822458.jpg",
    "primary_cat": "low-contrast oppressive",
    "other_cats": [
      "double exposure",
      "abstract photo"
    ],
    "caption": "Several horses appear in darkness. Their forms overlap and blur together, creating a ghostly abstract scene with heavy darkness and little detail.",
    "clean_caption": "horses",
    "has_clean": true,
    "hpsv3_anti": -8.59,
    "hpsv3_clean": 9.22,
    "human_score": 5.21
  },
  {
    "i": 4063,
    "filename": "154068.jpg",
    "primary_cat": "clashing color",
    "other_cats": [
      "smeared / no detail"
    ],
    "caption": "A person is shown in profile with a necklace. The image has a harsh green-and-blue color clash and very little visible detail, making the figure feel distorted and graphic.",
    "clean_caption": "a person",
    "has_clean": true,
    "hpsv3_anti": -6.62,
    "hpsv3_clean": 11.19,
    "human_score": 4.9
  },
  {
    "i": 6192,
    "filename": "539669.jpg",
    "primary_cat": "sickly cast",
    "other_cats": [
      "smeared / no detail",
      "abstract photo"
    ],
    "caption": "A close-up of flowers fills the frame. The image has very little detail, with soft shapes and a strong red cast that makes it read as an abstract photo.",
    "clean_caption": "flowers",
    "has_clean": true,
    "hpsv3_anti": -5.95,
    "hpsv3_clean": 11.01,
    "human_score": 4.79
  },
  {
    "i": 1999,
    "filename": "153416.jpg",
    "primary_cat": "digital artifacts",
    "other_cats": [
      "clashing color"
    ],
    "caption": "A snowy forest with tree trunks fills the frame. The image is heavily glitched with vertical digital streaks and strong magenta-green color distortion.",
    "clean_caption": "trees in snow",
    "has_clean": true,
    "hpsv3_anti": -5.65,
    "hpsv3_clean": 10.57,
    "human_score": 4.82
  },
  {
    "i": 3422,
    "filename": "655987.jpg",
    "primary_cat": "snapshot energy",
    "other_cats": [
      "smeared / no detail"
    ],
    "caption": "A train interior is captured with heavy motion blur and almost no visible detail. The frame is also tilted, giving it a rushed snapshot feel.",
    "clean_caption": "a train interior",
    "has_clean": true,
    "hpsv3_anti": -2.82,
    "hpsv3_clean": 13.28,
    "human_score": 5.09
  },
  {
    "i": 659,
    "filename": "884292.jpg",
    "primary_cat": "chromatic aberration",
    "other_cats": [
      "smeared / no detail",
      "abstract photo"
    ],
    "caption": "A building fills the frame. The image is heavily obscured by lost detail, soft focus, and strong color fringing, giving it an abstract look.",
    "clean_caption": "a building",
    "has_clean": true,
    "hpsv3_anti": -4.28,
    "hpsv3_clean": 11.54,
    "human_score": 4.65
  }
];

window.AAS_REAL_URL = function(i)        { return `img/asserts/real/${i}.jpg`; };
window.AAS_REAL_CLEAN_URL = function(i)  { return `img/asserts/real/${i}_clean.jpg`; };

window.AAS_REAL_PAGE = 'https://huggingface.co/datasets/weathon/aas_real_images';
window.AAS_BENCH_PAGE = 'https://huggingface.co/datasets/weathon/aas_benchmark_final';
