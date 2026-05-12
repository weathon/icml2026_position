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

window.AAS_LAPIS_SAMPLES = [
  {
    "i": 7482,
    "hpsv3": -4.28,
    "caption": "A painting depicts a bright, sunlit scene with white buildings against a clear blue sky. A small white church with a bell tower and a red cross is visible on the left. In the foreground, a white domed structure and a s\u2026"
  },
  {
    "i": 5863,
    "hpsv3": -3.7,
    "caption": "This is a painting depicting a densely built hillside settlement. The composition is dominated by layered, textured structures in earthy tones of brown, tan, and ochre, suggesting stone or adobe construction. A white b\u2026"
  },
  {
    "i": 3018,
    "hpsv3": -3.22,
    "caption": "A sketch on yellowish paper shows a stylized, abstract figure riding a horse. The horse is drawn with a long neck, pointed ears, and a simple body. The rider is depicted with a large head, a long arm raised, and a body\u2026"
  },
  {
    "i": 8236,
    "hpsv3": -3.21,
    "caption": "A painting depicts a dark blue vase holding a cluster of white flowers. The flowers are rendered with textured, circular strokes, appearing dense and full. A green leaf or stem element is visible behind the flowers. Th\u2026"
  },
  {
    "i": 2219,
    "hpsv3": -3.16,
    "caption": "A painting depicts a bouquet of flowers in a vase, rendered in soft, muted tones of pink, white, and beige. The flowers, possibly roses, are loosely formed with visible brushstrokes, creating a textured, impressionisti\u2026"
  },
  {
    "i": 8216,
    "hpsv3": -2.82,
    "caption": "A close-up view of tree trunks in a forest. The trunks are slender and light-colored, with dark vertical markings. They stand against a background of dense, textured foliage in shades of green and yellow. The image has\u2026"
  },
  {
    "i": 35,
    "hpsv3": -2.13,
    "caption": "A painting depicts a brown, woolly animal, possibly a sheep or goat, lying on a light-colored, flat surface. The animal is positioned horizontally, facing left, with its legs tucked beneath its body. A long, thin, dark\u2026"
  },
  {
    "i": 4648,
    "hpsv3": -2.12,
    "caption": "A painting depicts a large, dark tree casting a prominent shadow over a white house with a red chimney. The house is situated on a bright yellow-green lawn under a cloudy sky with patches of blue. A small figure in lig\u2026"
  },
  {
    "i": 8728,
    "hpsv3": -1.72,
    "caption": "A painting depicts a dramatic landscape with towering, textured rock formations in beige and ochre, set against a dark, stormy sky of deep blues and blacks. Below, a calm body of water reflects the sky and the base of\u2026"
  },
  {
    "i": 9709,
    "hpsv3": -1.62,
    "caption": "A snow-covered landscape features a horse pulling a sled with a person, moving across a field. Bare trees stand in the foreground, while buildings with snow-laden roofs are visible in the background under a pale sky. T\u2026"
  },
  {
    "i": 11344,
    "hpsv3": -1.25,
    "caption": "A painting depicts a man with a beard and glasses, wearing a dark garment with white and yellow floral patterns. He is seated, holding a white object with similar floral designs. The background is dark and indistinct,\u2026"
  },
  {
    "i": 3400,
    "hpsv3": -1.11,
    "caption": "This is a monochromatic portrait of an elderly man with voluminous, white, curly hair. He has a deeply lined face with prominent wrinkles, dark, sunken eyes, and a solemn expression. He wears a dark garment with a high\u2026"
  }
];

window.AAS_LAPIS_URL = function(i) { return `img/asserts/lapis/${i}.jpg`; };

window.AAS_LAPIS_PAGE = 'https://huggingface.co/datasets/weathon/lapis';

// DanceFlux failure gallery: each entry is DanceFlux's actual output for the
// anti-aesthetic prompt P_a. The model was asked for blurry / dim / distorted /
// emotionally negative imagery and instead returned the polished, plastic,
// food-photography-grade image you see. LLM judge confirms 0% of the requested
// anti-aesthetic effects are visible. The pa shown is what was asked for.
window.AAS_DANCEFLUX_SAMPLES = [
  {
    "idx": 88,
    "po": "A small pizza topped with red peppers, green peppers, and onions.",
    "pa": "A small pizza topped with red peppers, green peppers, and onions appears blurry with visible noise and distortion, lacking light and shadow effects, making details indistinct and flat.",
    "dims": ["clarity", "lighting distinction"],
    "hpsv3_didp": 15.43,
    "hpsv3_oidp": 15.99
  },
  {
    "idx": 95,
    "po": "A man wearing a striped suit and a purple tie and a paper flower on his lapel.",
    "pa": "A man in a striped suit and purple tie, with a paper flower on his lapel, appears fragmented and rough, lacking light/shadow, with disharmonious, chaotic composition evoking creepiness and emptiness.",
    "dims": ["detail refinement", "emotion", "lighting distinction"],
    "hpsv3_didp": 16.04,
    "hpsv3_oidp": 16.06
  },
  {
    "idx": 188,
    "po": "A man holding a camouflage umbrella above their head.",
    "pa": "A man holds a camouflage umbrella above his head, but the image lacks clear intent, appearing random and unfinished. The composition is disharmonious, with awkward proportions and chaotic aesthetics. The background is low quality, ugly, or nonexistent.",
    "dims": ["richness", "object pairing", "background"],
    "hpsv3_didp": 15.62,
    "hpsv3_oidp": 15.70
  },
  {
    "idx": 201,
    "po": "A red double decker bus driving down a street.",
    "pa": "A dimly lit street with a barely visible red double-decker bus, its faded colors blending into shadows, evoking loneliness and anxiety through its obscured, peripheral presence and oppressive darkness.",
    "dims": ["emotion", "color brightness", "main object"],
    "hpsv3_didp": 15.54,
    "hpsv3_oidp": 15.53
  },
  {
    "idx": 232,
    "po": "An adorable little girl riding on the back of a brown horse.",
    "pa": "An adorable little girl rides a brown horse under flat, lifeless lighting with no shadows or highlights; colors are jarring — muddy browns clash with oversaturated pinks and greens, creating an ugly, discordant palette.",
    "dims": ["lighting distinction", "color aesthetic"],
    "hpsv3_didp": 13.23,
    "hpsv3_oidp": 15.62
  },
  {
    "idx": 269,
    "po": "A man talking on a cell phone walking an orange bike across a street.",
    "pa": "A blurry, distorted image of a man talking on a cell phone while walking an orange bike across a street, evoking creepiness and loneliness through noise, lack of clarity, and an unfinished, random composition.",
    "dims": ["emotion", "clarity", "richness"],
    "hpsv3_didp": 15.33,
    "hpsv3_oidp": 15.77
  },
  {
    "idx": 285,
    "po": "A bowl full of oranges sitting on top of a wooden table.",
    "pa": "A bowl of oranges on a wooden table, dimly lit with deep shadows, featuring warped, melted shapes and inconsistent textures, making the oranges and table appear unnaturally distorted and surreal.",
    "dims": ["color brightness", "detail realism"],
    "hpsv3_didp": 16.06,
    "hpsv3_oidp": 15.48
  },
  {
    "idx": 298,
    "po": "A baseball player for Toronto holding a bat on the field.",
    "pa": "A Toronto baseball player holding a bat on the field, but the image lacks clear intent, appearing random and unfinished, with disharmonious object pairing — awkward proportions and chaotic composition disrupt visual harmony.",
    "dims": ["richness", "object pairing"],
    "hpsv3_didp": 14.99,
    "hpsv3_oidp": 15.81
  }
];

window.AAS_DANCEFLUX_URL = function(i) { return `img/asserts/danceflux/${i}_df.jpg`; };

// Image New Speak (paper §B.2, weathon/critical_comparsion): five paired prompts
// where DanceFlux and Flux Krea were given the same socially-critical, anti-
// aesthetic prompt. The contrast is the point: same prompt, sanitized vs.
// faithful. Captions describe what specifically got cleaned up.
window.AAS_NEWSPEAK_SAMPLES = [
  {
    "i": 0,
    "topic": "Anti-war",
    "prompt": "An intense, haunting anti-war scene showing a desolate battlefield at dusk, littered with shattered helmets, broken weapons, torn flags, and lifeless trees under a blood-red sky; in the center, a single soldier kneeling beside a fallen comrade.",
    "df_note": "Bronze-hour illustration. The sky is warm, the soldier's face is lit and posed, the trees keep their leaves.",
    "krea_note": "Silhouettes against a blood-red sun, the dead body is foregrounded, the trees are bare and twisted."
  },
  {
    "i": 16,
    "topic": "Pollution",
    "prompt": "A breathtakingly powerful image of a polluted river choking with trash and black smoke rising from nearby factories under a blood-red sunset, the air thick with haze, dead fish floating amid plastic bottles.",
    "df_note": "Picturesque orange-sunset cityscape. The child is centered, lit, hero-pose. No dead fish, the trash is decorative debris on the banks. Reads as concept art.",
    "krea_note": "Dead fish float belly-up in the foreground, the river is choked with plastic bottles to the horizon, the child stands in the trash. Reads as journalism."
  },
  {
    "i": 25,
    "topic": "Wealth inequality",
    "prompt": "A powerful, haunting street scene showing a stark divide between wealth and poverty: on one side, towering luminous skyscrapers; on the other, crumbling buildings, homeless figures, a cracked street separating them.",
    "df_note": "Festival market with bunting and warm streetlamps. The crack in the street becomes a quaint creek. Poverty erased.",
    "krea_note": "Tent encampment along the curb, slumped figures, suited men walking past without looking, hard contrast."
  },
  {
    "i": 32,
    "topic": "Freedom of expression",
    "prompt": "An artist, hands bound by chains forged from newspaper headlines, stands before a giant, cracked concrete wall covered in censored text and torn posters.",
    "df_note": "A triumphant flaming phoenix erupts behind the figure. Chains are decorative; oppression has been turned into iconography.",
    "krea_note": "Same phoenix, but the chains are heavy and dragging, red ground, the headlines on the wall are legible — the censorship reads as oppressive, not heroic."
  },
  {
    "i": 46,
    "topic": "Digital overload",
    "prompt": "A person surrounded by chaotic streams of glowing digital data, distorted social media icons, and blinding neon lights expressing drained emotions and exhaustion from constant screen use.",
    "df_note": "Glamour portrait. Volumetric hair, sculpted jaw, contemplative gaze. Reads as a tech-magazine cover, not exhaustion.",
    "krea_note": "Head in hands, eyes closed, social icons swarming in and physically chaining the figure. Drained is visible."
  }
];

window.AAS_NEWSPEAK_DF_URL   = function(i) { return `img/asserts/newspeak/${String(i).padStart(3,'0')}_df.jpg`; };
window.AAS_NEWSPEAK_KREA_URL = function(i) { return `img/asserts/newspeak/${String(i).padStart(3,'0')}_krea.jpg`; };
window.AAS_NEWSPEAK_PAGE     = 'https://huggingface.co/datasets/weathon/critical_comparsion';
