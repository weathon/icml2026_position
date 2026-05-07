const aiTarget = document.querySelector("#ai-examples");
const realTarget = document.querySelector("#real-examples");
const plainToggle = document.querySelector("#plain-toggle");
const scriptBase = new URL(".", document.currentScript.src);
const localUrl = (path) => new URL(path, scriptBase).href;

plainToggle.addEventListener("click", () => {
  const isPlain = document.body.classList.toggle("plain");
  plainToggle.setAttribute("aria-pressed", String(isPlain));
  plainToggle.textContent = isPlain ? "restore noise" : "reduce noise";
});

fetch(localUrl("assets/gallery.json"))
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
                <img src="${localUrl(item.failed)}" alt="Original reference image for case ${item.index + 1}.">
                <span class="tag">original reference</span>
              </div>
              <div class="image-slot">
                <img src="${localUrl(item.success)}" alt="Anti-aesthetic generated output for case ${item.index + 1}.">
                <span class="tag success-tag">anti-aesthetic output</span>
              </div>
            </div>
            <dl>
              <dt>case</dt><dd>${item.index + 1}</dd>
              <dt>model</dt><dd>${item.model}</dd>
              <dt>target</dt><dd>${dims}</dd>
              <dt>request</dt><dd>${item.prompt_distorted}</dd>
            </dl>
          </article>
        `;
      })
      .join("");

    realTarget.innerHTML = gallery.real
      .map((item) => `
        <article class="real-item">
          <img src="${localUrl(item.image)}" alt="${item.query}.">
          <dl>
            <dt>style</dt><dd>${item.query}</dd>
            <dt>evidence</dt><dd>${item.message}</dd>
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
