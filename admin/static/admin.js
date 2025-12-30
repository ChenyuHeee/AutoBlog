(() => {
  const textarea = document.getElementById("editor-content");
  const preview = document.getElementById("preview");
  if (!textarea || !preview) {
    return;
  }

  const isMarkdown = textarea.dataset.isMarkdown === "true";
  if (!isMarkdown) {
    return;
  }

  let timer = null;
  const render = async () => {
    const form = new FormData();
    form.set("content", textarea.value || "");
    try {
      const res = await fetch("/api/render_markdown", { method: "POST", body: form });
      if (!res.ok) {
        return;
      }
      preview.innerHTML = await res.text();
    } catch {
      // ignore
    }
  };

  const schedule = () => {
    if (timer) {
      window.clearTimeout(timer);
    }
    timer = window.setTimeout(render, 250);
  };

  textarea.addEventListener("input", schedule);
})();
