const aiTarget = document.querySelector("#ai-examples");
const realTarget = document.querySelector("#real-examples");
const plainToggle = document.querySelector("#plain-toggle");

plainToggle.addEventListener("click", () => {
  const isPlain = document.body.classList.toggle("plain");
  plainToggle.setAttribute("aria-pressed", String(isPlain));
  plainToggle.textContent = isPlain ? "restore noise" : "reduce noise";
});

fetch("assets/gallery.json")
  .then((response) => {
    if (!response.ok) {
      throw new Error(`Gallery metadata request failed with HTTP ${response.status}`);
    }
    return response.json();
  })
  .then((gallery) => {
    if (!Array.isArray(gallery.ai) || !Array.isArray(gallery.real)) {
      throw new Error("Gallery metadata is missing ai or real arrays");
    }

    aiTarget.innerHTML = gallery.ai
      .map((item) => {
        const dims = JSON.parse(item.dims).join(", ");
        return `
          <article class="ai-pair">
            <div class="pair-images">
              <div class="image-slot">
                <img src="${item.failed}" alt="Conventional generated image for row ${item.index}.">
                <span class="tag">failed polish</span>
              </div>
              <div class="image-slot">
                <img src="${item.success}" alt="Successful anti-aesthetic generated image for row ${item.index}.">
                <span class="tag success-tag">success</span>
              </div>
            </div>
            <dl>
              <dt>row</dt><dd>${item.index}</dd>
              <dt>model</dt><dd>${item.model}</dd>
              <dt>dims</dt><dd>${dims}</dd>
              <dt>request</dt><dd>${item.prompt_distorted}</dd>
            </dl>
          </article>
        `;
      })
      .join("");

    realTarget.innerHTML = gallery.real
      .map((item) => `
        <article class="real-item">
          <img src="${item.image}" alt="${item.query}.">
          <dl>
            <dt>query</dt><dd>${item.query}</dd>
            <dt>source</dt><dd>${item.dataset}</dd>
            <dt>set size</dt><dd>${item.size}</dd>
          </dl>
        </article>
      `)
      .join("");
  })
  .catch((error) => {
    const message = `<div class="load-error">Gallery load error: ${error.message}</div>`;
    aiTarget.innerHTML = message;
    realTarget.innerHTML = message;
  });
