const wall = document.querySelector("#wall");
const sentinel = document.querySelector("#sentinel");
const plainToggle = document.querySelector("#plain-toggle");
const dataset = "weathon/aas_real_images";
const split = "train";
const batchSize = 100;
let offset = 0;
let total = 29195;
let loading = false;

plainToggle.addEventListener("click", () => {
  const isPlain = document.body.classList.toggle("plain");
  plainToggle.setAttribute("aria-pressed", String(isPlain));
  plainToggle.textContent = isPlain ? "restore noise" : "reduce noise";
});

function appendRows(rows) {
  const fragment = document.createDocumentFragment();
  rows.forEach((entry) => {
    const src = entry.row.image && entry.row.image.src;
    if (!src) {
      throw new Error(`Missing image src at row ${entry.row_idx}`);
    }

    const tile = document.createElement("figure");
    tile.className = "tile";
    tile.style.setProperty("--tilt", `${(entry.row_idx % 7) - 3}deg`);

    const img = document.createElement("img");
    img.src = src;
    img.alt = "";
    img.loading = "lazy";
    img.decoding = "async";
    tile.appendChild(img);
    fragment.appendChild(tile);
  });
  wall.appendChild(fragment);
}

function showError(error) {
  wall.innerHTML = `<div class="load-error">${error.message}</div>`;
}

async function loadNextBatch() {
  if (loading || offset >= total) {
    return;
  }
  loading = true;

  const url = new URL("https://datasets-server.huggingface.co/rows");
  url.searchParams.set("dataset", dataset);
  url.searchParams.set("config", "default");
  url.searchParams.set("split", split);
  url.searchParams.set("offset", String(offset));
  url.searchParams.set("length", String(batchSize));

  try {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Image wall request failed with HTTP ${response.status}`);
    }

    const payload = await response.json();
    if (!Array.isArray(payload.rows)) {
      throw new Error("Image wall response did not include rows");
    }
    if (payload.rows.length === 0 && offset < total) {
      throw new Error(`Image wall stopped at row ${offset}`);
    }

    total = payload.num_rows_total || total;
    appendRows(payload.rows);
    offset += payload.rows.length;
  } finally {
    loading = false;
  }
}

const observer = new IntersectionObserver((entries) => {
  if (entries.some((entry) => entry.isIntersecting)) {
    loadNextBatch().catch(showError);
  }
}, { rootMargin: "1400px" });

observer.observe(sentinel);
loadNextBatch().catch(showError);
