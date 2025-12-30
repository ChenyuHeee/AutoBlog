(() => {
  const MIN_QUERY_LENGTH = 1;
  const input = document.getElementById("search-input");
  const resultsContainer = document.querySelector("[data-search-results]");
  if (!input || !resultsContainer) {
    return;
  }

  const indexUrl = window.__AUTOBLOG_SEARCH_INDEX_URL__ || "/search.json";
  let index = [];
  let loading = false;
  let loadError = null;

  const formatter = typeof Intl !== "undefined" && Intl.DateTimeFormat
    ? new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "short", day: "numeric" })
    : null;

  const renderMessage = (text, className = "search-results__empty") => {
    resultsContainer.innerHTML = "";
    const p = document.createElement("p");
    p.className = className;
    p.textContent = text;
    resultsContainer.appendChild(p);
  };

  const escapeHtml = (value) => {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  };

  const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  const highlightText = (text, tokens) => {
    if (!text) {
      return "";
    }
    const validTokens = tokens.filter((token) => token && token.trim().length);
    if (!validTokens.length) {
      return escapeHtml(text);
    }
    let html = escapeHtml(text);
    validTokens.forEach((token) => {
      const pattern = new RegExp(`(${escapeRegExp(token)})`, "gi");
      html = html.replace(pattern, "<mark>$1</mark>");
    });
    return html;
  };

  const buildSnippet = (item, tokens) => {
    const source = String(item.content || item.summary || item.description || "");
    if (!source) {
      return "";
    }
    const validTokens = tokens.filter((token) => token && token.trim().length);
    if (!validTokens.length) {
      return highlightText(source.slice(0, 200), []);
    }
    const lowerSource = source.toLowerCase();
    let bestIndex = -1;
    let matchLength = 0;
    validTokens.forEach((token) => {
      const idx = lowerSource.indexOf(token);
      if (idx !== -1 && (bestIndex === -1 || idx < bestIndex)) {
        bestIndex = idx;
        matchLength = token.length;
      }
    });

    const PADDING = 90;
    let snippetSource;
    if (bestIndex === -1) {
      snippetSource = source.slice(0, 200);
    } else {
      const start = Math.max(bestIndex - PADDING, 0);
      const end = Math.min(bestIndex + matchLength + PADDING, source.length);
      snippetSource = source.slice(start, end).trim();
      if (start > 0) {
        snippetSource = `…${snippetSource}`;
      }
      if (end < source.length) {
        snippetSource = `${snippetSource}…`;
      }
    }
    return highlightText(snippetSource, validTokens);
  };

  const ensureIndexLoaded = async () => {
    if (index.length || loadError) {
      return;
    }
    if (loading) {
      return;
    }
    loading = true;
    try {
      const response = await fetch(indexUrl, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`Failed to load search index: ${response.status}`);
      }
      const data = await response.json();
      index = Array.isArray(data)
        ? data.map((item) => {
            const titleLower = (item.title || "").toLowerCase();
            const descriptionLower = (item.description || "").toLowerCase();
            const summaryLower = (item.summary || "").toLowerCase();
            const contentLower = (item.content || "").toLowerCase();
            const tagsLower = Array.isArray(item.tags)
              ? item.tags.map((tag) => String(tag).toLowerCase())
              : [];
            const composite = [titleLower, descriptionLower, summaryLower, tagsLower.join(" ")]
              .join(" ")
              .trim();
            return {
              ...item,
              content: item.content || "",
              _titleLower: titleLower,
              _tagsLower: tagsLower,
              _contentLower: contentLower,
              _composite: composite,
            };
          })
        : [];
    } catch (error) {
      loadError = error;
      renderMessage("无法加载搜索索引，请稍后重试。", "search-results__error");
    } finally {
      loading = false;
    }
  };

  const computeScore = (item, tokens) => {
    let score = 0;
    tokens.forEach((token) => {
      if (!token) {
        return;
      }
      if (item._titleLower.includes(token)) {
        score += 4;
      }
      if (item._tagsLower.some((tag) => tag.includes(token))) {
        score += 3;
      }
      if (item._contentLower && item._contentLower.includes(token)) {
        score += 2;
      }
      if (item._composite.includes(token)) {
        score += 1;
      }
    });
    if (item.type === "post" && item.date) {
      score += 1;
    }
    return score;
  };

  const renderResults = (items, query, tokens) => {
    resultsContainer.innerHTML = "";
    const wrapper = document.createElement("div");
    wrapper.className = "search-results__list";
    const fragment = document.createDocumentFragment();
    items.forEach((item) => {
      const article = document.createElement("article");
      article.className = "search-result";

      const title = document.createElement("h2");
      title.className = "search-result__title";
      const link = document.createElement("a");
      link.href = item.url;
      link.innerHTML = highlightText(item.title, tokens);
      title.appendChild(link);
      article.appendChild(title);

      const metaParts = [];
      if (item.type === "post" && item.date) {
        const date = formatter ? formatter.format(new Date(item.date)) : item.date;
        metaParts.push(date);
      }
      if (item.type === "post" && item.reading_time) {
        metaParts.push(`约 ${item.reading_time} 分钟阅读`);
      }
      if (item.type === "page") {
        metaParts.push("页面");
      }
      if (metaParts.length) {
        const meta = document.createElement("p");
        meta.className = "search-result__meta";
        meta.textContent = metaParts.join(" · ");
        article.appendChild(meta);
      }

      let snippetHtml = buildSnippet(item, tokens);
      if (!snippetHtml && item.summary) {
        snippetHtml = highlightText(item.summary, tokens);
      } else if (!snippetHtml && item.description) {
        snippetHtml = highlightText(item.description, tokens);
      }
      if (snippetHtml) {
        const summary = document.createElement("p");
        summary.className = "search-result__summary";
        summary.innerHTML = snippetHtml;
        article.appendChild(summary);
      }

      if (Array.isArray(item.tags) && item.tags.length) {
        const list = document.createElement("ul");
        list.className = "tag-list tag-list--compact search-result__tags";
        item.tags.forEach((tag) => {
          const li = document.createElement("li");
          const chip = document.createElement("span");
          chip.innerHTML = highlightText(tag, tokens);
          li.appendChild(chip);
          list.appendChild(li);
        });
        article.appendChild(list);
      }

      fragment.appendChild(article);
    });

    if (!fragment.childNodes.length) {
      renderMessage(`未找到与“${query}”相关的内容。`);
      return;
    }

    wrapper.appendChild(fragment);
    resultsContainer.appendChild(wrapper);
  };

  const performSearch = async (query) => {
    const normalized = query.trim();
    if (!normalized) {
      renderMessage("开始输入即可搜索全站内容。");
      return;
    }
    if (normalized.length < MIN_QUERY_LENGTH) {
      renderMessage(`请输入至少 ${MIN_QUERY_LENGTH} 个字符。`);
      return;
    }
    await ensureIndexLoaded();
    if (loadError) {
      return;
    }
    if (!index.length) {
      renderMessage("当前尚无可搜索内容，试着先发表几篇文章吧。");
      return;
    }
    const baseTokens = normalized.toLowerCase().split(/\s+/).filter(Boolean);
    const tokens = baseTokens.length ? Array.from(new Set(baseTokens)) : [normalized.toLowerCase()];
    const matches = index
      .map((item) => ({ item, score: computeScore(item, tokens) }))
      .filter(({ score }) => score > 0)
      .sort((a, b) => {
        if (b.score !== a.score) {
          return b.score - a.score;
        }
        if (a.item.type === b.item.type && a.item.type === "post" && a.item.date && b.item.date) {
          return new Date(b.item.date) - new Date(a.item.date);
        }
        return 0;
      })
      .map(({ item }) => item);
    if (!matches.length) {
      renderMessage(`未找到与“${normalized}”相关的内容。`);
      return;
    }
    renderResults(matches, normalized, tokens);
  };

  input.addEventListener("input", (event) => {
    const value = event.target.value || "";
    performSearch(value);
  });

  renderMessage("开始输入即可搜索全站内容。");
})();
