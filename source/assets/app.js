(function () {
  const THEME_STORAGE_KEY = "autoblog-theme";
  const AUDIO_STATE_STORAGE_KEY = "autoblog-audio-state";
  const VALID_THEMES = new Set(["light", "dark"]);
  const GLOSSARY_MAX_MATCHES = 40;
  const GLOSSARY_SKIP_TAGS = new Set([
    "A",
    "CODE",
    "PRE",
    "SCRIPT",
    "STYLE",
    "TEXTAREA",
    "BUTTON",
    "NOSCRIPT",
    "SVG",
    "MATH",
    "KBD",
    "SAMP",
  ]);
  let glossaryTooltipIdCounter = 0;
  let glossaryHandlersAttached = false;
  let audioPlayerIdCounter = 0;

  document.documentElement.classList.add("has-js");

  document.addEventListener("DOMContentLoaded", () => {
    initThemeToggle();
    initProgressBar();
    initCodeBlocks();
    initImageLightbox();
    initTableOfContents();
    initPostCardAnimations();
    initArchiveTimeline();
    initSiteAudioPlayer();
    initBackToTop();
    initHeaderCondense();
    initGlossaryTooltips();
    initPromoPageAnimations();
    initNotFoundPage();
  });

  function initThemeToggle() {
    const toggles = document.querySelectorAll("[data-theme-toggle]");
    if (!toggles.length) {
      return;
    }

    const root = document.documentElement;
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const storedTheme = localStorage.getItem(THEME_STORAGE_KEY);
    let hasStoredPreference = VALID_THEMES.has(storedTheme);
    const initialTheme = hasStoredPreference
      ? storedTheme
      : mediaQuery.matches
      ? "dark"
      : "light";

    applyTheme(initialTheme, false);

    toggles.forEach((toggle) => {
      toggle.addEventListener("click", () => {
        const currentTheme = root.getAttribute("data-theme") === "dark" ? "dark" : "light";
        const nextTheme = currentTheme === "dark" ? "light" : "dark";
        hasStoredPreference = true;
        applyTheme(nextTheme, true);
      });
    });

    addMediaListener(mediaQuery, (event) => {
      if (!hasStoredPreference) {
        applyTheme(event.matches ? "dark" : "light", false);
      }
    });

    function applyTheme(theme, persist) {
      const normalizedTheme = VALID_THEMES.has(theme) ? theme : "light";
      root.setAttribute("data-theme", normalizedTheme);
      root.style.colorScheme = normalizedTheme === "dark" ? "dark" : "light";
      const ariaLabel = normalizedTheme === "dark" ? "切换到日间模式" : "切换到夜间模式";
      toggles.forEach((toggle) => {
        toggle.setAttribute("data-theme-state", normalizedTheme);
        toggle.setAttribute("aria-pressed", normalizedTheme === "dark" ? "true" : "false");
        toggle.setAttribute("aria-label", ariaLabel);
      });
      if (persist) {
        localStorage.setItem(THEME_STORAGE_KEY, normalizedTheme);
        hasStoredPreference = true;
      } else if (!hasStoredPreference) {
        localStorage.removeItem(THEME_STORAGE_KEY);
      }
    }
  }

  function initProgressBar() {
    const progressBar = document.getElementById("reading-progress");
    if (!progressBar) {
      return;
    }
    const article = document.querySelector("article.post");
    if (!article) {
      progressBar.style.display = "none";
      return;
    }

    let articleTop = 0;
    let articleHeight = 0;
    let ticking = false;

    const recalc = () => {
      const rect = article.getBoundingClientRect();
      articleTop = rect.top + window.scrollY;
      articleHeight = article.scrollHeight;
      update();
    };

    const update = () => {
      const viewportHeight = window.innerHeight;
      const maxScroll = articleHeight - viewportHeight;
      if (maxScroll <= 0) {
        progressBar.style.setProperty("--progress", "1");
        ticking = false;
        return;
      }
      const raw = (window.scrollY - articleTop) / maxScroll;
      const clamped = Math.min(Math.max(raw, 0), 1);
      progressBar.style.setProperty("--progress", clamped.toFixed(4));
      ticking = false;
    };

    const onScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(update);
        ticking = true;
      }
    };

    recalc();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", () => {
      recalc();
    });
    window.addEventListener("load", recalc);
  }

  function initCodeBlocks() {
    const selector = ".post-content pre, .page__content pre";
    const blocks = document.querySelectorAll(selector);
    if (!blocks.length) {
      return;
    }

    blocks.forEach((pre, index) => {
      if (!pre || pre.dataset.enhanced === "true") {
        return;
      }

      const parent = pre.parentElement;
      const isHighlightContainer =
        parent && (parent.classList.contains("codehilite") || parent.classList.contains("highlight"));
      const host = isHighlightContainer ? parent : pre;
      if (!host || host.dataset.enhanced === "true") {
        return;
      }
      if (!host.parentNode) {
        return;
      }

      const code = pre.querySelector("code");
      const language = resolveLanguage(code, pre, index);
      const wrapper = document.createElement("div");
      wrapper.className = "code-block";

      const header = document.createElement("div");
      header.className = "code-block__header";

      const label = document.createElement("span");
      label.className = "code-block__language";
      label.textContent = language;
      header.appendChild(label);

      const copyButton = document.createElement("button");
      copyButton.type = "button";
      copyButton.className = "code-block__copy";
      copyButton.textContent = "复制";
      const ariaLabel = language && language !== "纯文本" ? `复制${language}代码` : "复制代码";
      copyButton.setAttribute("aria-label", ariaLabel);
      copyButton.dataset.defaultLabel = "复制";
      header.appendChild(copyButton);

      host.parentNode.insertBefore(wrapper, host);
      wrapper.appendChild(header);
      wrapper.appendChild(host);
      host.dataset.enhanced = "true";
      pre.dataset.enhanced = "true";

      copyButton.addEventListener("click", () => {
        const content = (code && code.textContent) || pre.textContent || "";
        if (!content.trim()) {
          return;
        }
        copyText(content)
          .then(() => setCopyState(copyButton, true))
          .catch(() => setCopyState(copyButton, false));
      });
    });
  }

  function resolveLanguage(code, pre, index) {
    const map = {
      js: "JavaScript",
      jsx: "JavaScript",
      ts: "TypeScript",
      tsx: "TypeScript",
      py: "Python",
      python: "Python",
      rb: "Ruby",
      go: "Go",
      rs: "Rust",
      csharp: "C#",
      cs: "C#",
      cpp: "C++",
      c: "C",
      html: "HTML",
      css: "CSS",
      scss: "SCSS",
      java: "Java",
      php: "PHP",
      swift: "Swift",
      kotlin: "Kotlin",
      json: "JSON",
      yaml: "YAML",
      yml: "YAML",
      md: "Markdown",
      bash: "Bash",
      sh: "Shell",
      shell: "Shell",
      sql: "SQL",
      dart: "Dart",
      scala: "Scala",
      vue: "Vue",
    };
    const candidates = [];
    const ignoredTokens = new Set(["", "codehilite", "highlight", "code", "pre", "markdown"]);

    const collectClasses = (target) => {
      if (!target) {
        return;
      }
      const dataLang = target.getAttribute("data-language") || target.getAttribute("data-lang");
      if (dataLang) {
        candidates.push(dataLang);
      }
      const classAttr = target.getAttribute("class");
      if (classAttr) {
        candidates.push(classAttr);
      }
    };

    collectClasses(code);
    collectClasses(pre);
    const preParent = pre ? pre.parentElement : null;
    collectClasses(preParent);
    if (preParent && preParent.parentElement) {
      collectClasses(preParent.parentElement);
    }

    const tokens = candidates
      .join(" ")
      .split(/\s+/)
      .map((item) => item.trim())
      .filter(Boolean);

    for (const token of tokens) {
      let normalized = token.toLowerCase();
      if (normalized.startsWith("language-")) {
        normalized = normalized.slice(9);
      } else if (normalized.startsWith("lang-")) {
        normalized = normalized.slice(5);
      }
      if (!normalized || ignoredTokens.has(normalized)) {
        continue;
      }
      if (map[normalized]) {
        return map[normalized];
      }
      if (/^[a-z0-9+#\-]+$/.test(normalized)) {
        return normalized.charAt(0).toUpperCase() + normalized.slice(1);
      }
    }
    return "纯文本";
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise((resolve, reject) => {
      try {
        const temp = document.createElement("textarea");
        temp.value = text;
        temp.setAttribute("readonly", "");
        temp.style.position = "fixed";
        temp.style.opacity = "0";
        document.body.appendChild(temp);
        temp.select();
        const success = document.execCommand("copy");
        document.body.removeChild(temp);
        if (success) {
          resolve();
        } else {
          reject(new Error("Copy command was rejected"));
        }
      } catch (error) {
        reject(error);
      }
    });
  }

  function setCopyState(button, success) {
    const originalText = button.dataset.defaultLabel || "复制";
    button.textContent = success ? "已复制" : "复制失败";
    button.classList.toggle("is-copied", success);
    window.setTimeout(() => {
      button.textContent = originalText;
      button.classList.remove("is-copied");
    }, 1800);
  }

  function initImageLightbox() {
    const overlay = document.getElementById("image-lightbox");
    if (!overlay) {
      return;
    }
    const imageEl = overlay.querySelector(".lightbox__image");
    const captionEl = overlay.querySelector(".lightbox__caption");
    const closeBtn = overlay.querySelector("[data-lightbox-close]");
    if (!imageEl || !captionEl || !closeBtn) {
      return;
    }

    const images = Array.from(
      document.querySelectorAll(".post-content img, .page__content img")
    ).filter((img) => !img.closest("a"));
    if (!images.length) {
      return;
    }

    let lastFocusedElement = null;

    const open = (img) => {
      lastFocusedElement = document.activeElement;
      const source = img.currentSrc || img.src;
      imageEl.src = source;
      imageEl.alt = img.alt || "";
      captionEl.textContent = img.alt || "";
      captionEl.style.display = img.alt ? "block" : "none";
      overlay.classList.add("is-open");
      overlay.setAttribute("aria-hidden", "false");
      document.documentElement.classList.add("has-lightbox");
      document.body.classList.add("has-lightbox");
      closeBtn.focus();
    };

    const close = () => {
      overlay.classList.remove("is-open");
      overlay.setAttribute("aria-hidden", "true");
      document.documentElement.classList.remove("has-lightbox");
      document.body.classList.remove("has-lightbox");
      imageEl.src = "";
      if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
        window.requestAnimationFrame(() => lastFocusedElement.focus());
      }
    };

    images.forEach((img) => {
      img.dataset.lightbox = "true";
      img.addEventListener("click", () => open(img));
    });

    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) {
        close();
      }
    });

    closeBtn.addEventListener("click", close);

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && overlay.classList.contains("is-open")) {
        close();
      }
    });
  }

  function initTableOfContents() {
    const toc = document.getElementById("post-toc");
    if (!toc) {
      return;
    }
    const body = toc.querySelector("[data-toc-body]");
    if (!body) {
      return;
    }

    const headings = Array.from(document.querySelectorAll(".post-content h2, .post-content h3")).filter(
      (heading) => heading.textContent.trim().length > 0
    );

    if (headings.length < 2) {
      toc.hidden = true;
      return;
    }

    const list = document.createElement("ol");
    const linkMap = new Map();

    headings.forEach((heading, index) => {
      if (!heading.id) {
        heading.id = generateHeadingId(heading.textContent, index);
      }
      const item = document.createElement("li");
      item.className = `post-toc__item post-toc__item--${heading.tagName.toLowerCase()}`;
      const link = document.createElement("a");
      link.href = `#${heading.id}`;
      link.textContent = heading.textContent.trim();
      link.dataset.tocTarget = heading.id;
      item.appendChild(link);
      list.appendChild(item);
      linkMap.set(heading.id, link);
    });

    body.appendChild(list);
    toc.hidden = false;

    const toggle = toc.querySelector("[data-toc-toggle]");
    if (toggle) {
      const forcedCollapse = window.matchMedia("(max-width: 960px)");
      const applyCollapse = (mq) => {
        if (mq.matches) {
          toc.classList.add("is-collapsed");
          toggle.setAttribute("aria-expanded", "false");
        }
      };
      applyCollapse(forcedCollapse);
      addMediaListener(forcedCollapse, applyCollapse);

      toggle.addEventListener("click", () => {
        const isCollapsed = toc.classList.toggle("is-collapsed");
        toggle.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
      });
    }

    const entries = headings.map((heading) => ({ id: heading.id, element: heading }));
    let activeId = null;
    let ticking = false;

    const updateActive = () => {
      const scrollPosition = window.scrollY + 140;
      let currentId = entries[0]?.id || null;
      for (const entry of entries) {
        if (entry.element.offsetTop <= scrollPosition) {
          currentId = entry.id;
        } else {
          break;
        }
      }
      if (currentId !== activeId) {
        if (activeId && linkMap.has(activeId)) {
          const previous = linkMap.get(activeId);
          previous.classList.remove("is-active");
          previous.removeAttribute("aria-current");
        }
        if (currentId && linkMap.has(currentId)) {
          const nextLink = linkMap.get(currentId);
          nextLink.classList.add("is-active");
          nextLink.setAttribute("aria-current", "true");
        }
        activeId = currentId;
      }
      ticking = false;
    };

    const onScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(updateActive);
        ticking = true;
      }
    };

    updateActive();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", () => {
      updateActive();
    });
    window.addEventListener("load", updateActive);

    body.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        if (window.innerWidth <= 960 && toggle) {
          toc.classList.add("is-collapsed");
          toggle.setAttribute("aria-expanded", "false");
        }
      });
    });
  }

  function generateHeadingId(text, index) {
    const slug = text
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9\u4e00-\u9fa5\s-]/g, "")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-");
    const base = slug || `section-${index + 1}`;
    let unique = base;
    let counter = 1;
    while (document.getElementById(unique)) {
      unique = `${base}-${counter++}`;
    }
    return unique;
  }

  function initArchiveTimeline() {
    const timeline = document.querySelector(".archive--timeline");
    if (!timeline) {
      return;
    }

    const items = Array.from(timeline.querySelectorAll("[data-timeline-item]"));
    if (!items.length) {
      return;
    }
    setupIntersectionReveal(items, "is-visible", {
      rootMargin: "0px 0px -10% 0px",
      threshold: 0.25,
    });

    let ticking = false;
    const updateProgress = () => {
      const rect = timeline.getBoundingClientRect();
      const height = Math.max(rect.height, 1);
      const viewportHeight = window.innerHeight || 1;
      const top = window.scrollY + rect.top;
      const bottom = top + height;
      const reference = window.scrollY + viewportHeight * 0.5;
      const raw = (reference - top) / (bottom - top || 1);
      const clamped = Math.min(Math.max(raw, 0), 1);
      timeline.style.setProperty("--timeline-progress", clamped.toFixed(4));
      ticking = false;
    };

    const requestProgressUpdate = () => {
      if (ticking) {
        return;
      }
      ticking = true;
      window.requestAnimationFrame(updateProgress);
    };

    updateProgress();
    window.addEventListener("scroll", requestProgressUpdate, { passive: true });
    window.addEventListener("resize", requestProgressUpdate);
    window.addEventListener("load", updateProgress);
  }

  function setupIntersectionReveal(elements, className, observerOptions) {
    const targets = Array.isArray(elements) ? elements : Array.from(elements || []);
    if (!targets.length) {
      return;
    }

    const reduceMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const revealAll = () => {
      targets.forEach((element) => {
        element.classList.add(className);
      });
    };

    if (reduceMotionQuery.matches || typeof IntersectionObserver === "undefined") {
      revealAll();
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) {
            return;
          }
          entry.target.classList.add(className);
          observer.unobserve(entry.target);
        });
      },
      observerOptions || { threshold: 0.2 }
    );

    targets.forEach((element) => {
      observer.observe(element);
    });

    addMediaListener(reduceMotionQuery, (event) => {
      if (event.matches) {
        revealAll();
        observer.disconnect();
      }
    });
  }

  function initPostCardAnimations() {
    const cards = Array.from(document.querySelectorAll(".post-card"));
    if (!cards.length) {
      return;
    }
    setupIntersectionReveal(cards, "is-visible", {
      rootMargin: "0px 0px -12% 0px",
      threshold: 0.12,
    });
  }

  function initPromoPageAnimations() {
    const elements = document.querySelectorAll("[data-promo-reveal]");
    if (!elements.length) {
      return;
    }

    elements.forEach((element) => {
      const rawDelay = Number(element.getAttribute("data-reveal-delay"));
      if (Number.isFinite(rawDelay) && rawDelay > 0) {
        element.style.setProperty("--promo-delay", `${rawDelay}ms`);
      }
    });

    setupIntersectionReveal(elements, "is-visible", {
      rootMargin: "0px 0px -10% 0px",
      threshold: 0.18,
    });
  }

  function initGlossaryTooltips() {
    const contentRoots = Array.from(
      document.querySelectorAll(".post-content, .page__content")
    );
    const { entries, inlineElements } = collectGlossaryEntries();

    if (!entries.size && !inlineElements.length) {
      return;
    }

    inlineElements.forEach(({ element, key }) => {
      const data = entries.get(key);
      if (!data) {
        return;
      }
      enhanceExistingGlossaryElement(element, data);
    });

    if (!entries.size || !contentRoots.length) {
      return;
    }

    const dictionary = Array.from(entries.values());
    contentRoots.forEach((root) => {
      enhanceGlossaryInContainer(root, dictionary);
    });
  }

  function collectGlossaryEntries() {
    const map = new Map();
    const inlineElements = [];

    const normalize = (term, definition) => {
      if (!term || !definition) {
        return null;
      }
      const trimmedTerm = String(term).trim();
      const trimmedDefinition = String(definition).trim();
      if (!trimmedTerm || !trimmedDefinition) {
        return null;
      }
      const key = trimmedTerm.toLowerCase();
      if (!map.has(key)) {
        map.set(key, {
          term: trimmedTerm,
          definition: trimmedDefinition,
          termLower: key,
          matchWholeWord: /^[a-z0-9]+$/i.test(trimmedTerm),
        });
      }
      return key;
    };

    const globalTerms = Array.isArray(window.AUTO_BLOG_GLOSSARY)
      ? window.AUTO_BLOG_GLOSSARY
      : [];
    globalTerms.forEach((item) => {
      if (!item) {
        return;
      }
      normalize(item.term, item.definition);
    });

    document.querySelectorAll("[data-glossary-term][data-glossary-definition]").forEach((element) => {
      const key = normalize(
        element.getAttribute("data-glossary-term"),
        element.getAttribute("data-glossary-definition")
      );
      if (!key) {
        return;
      }
      inlineElements.push({ element, key });
    });

    return { entries: map, inlineElements };
  }

  function enhanceExistingGlossaryElement(element, entry) {
    if (!element) {
      return;
    }

    if (!element.classList.contains("glossary-term")) {
      element.classList.add("glossary-term");
    }

    element.setAttribute("data-glossary-active", "false");
    if (!element.hasAttribute("tabindex")) {
      element.tabIndex = 0;
    }

    let tooltip = null;
    const describedBy = element.getAttribute("aria-describedby");
    if (describedBy) {
      tooltip = document.getElementById(describedBy);
    }

    if (!tooltip) {
      tooltip = createGlossaryTooltip(entry);
      element.appendChild(tooltip);
      element.setAttribute("aria-describedby", tooltip.id);
    } else {
      tooltip.textContent = entry.definition;
    }

      element.setAttribute("role", "button");
      element.setAttribute("aria-haspopup", "true");
    element.setAttribute("aria-expanded", "false");
    registerGlossaryTerm(element);
  }

  function enhanceGlossaryInContainer(container, entries) {
    const walker = document.createTreeWalker(
      container,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          if (!node || !node.parentNode) {
            return NodeFilter.FILTER_REJECT;
          }
          if (node.textContent.trim().length === 0) {
            return NodeFilter.FILTER_REJECT;
          }
          const parent = node.parentNode;
          if (parent.closest && parent.closest(".glossary-term")) {
            return NodeFilter.FILTER_REJECT;
          }
          if (GLOSSARY_SKIP_TAGS.has(parent.nodeName)) {
            return NodeFilter.FILTER_REJECT;
          }
          if (parent.hasAttribute && parent.hasAttribute("data-glossary-ignore")) {
            return NodeFilter.FILTER_REJECT;
          }
          return NodeFilter.FILTER_ACCEPT;
        },
      },
      false
    );

    let replacements = 0;
    let node = walker.nextNode();
    while (node && replacements < GLOSSARY_MAX_MATCHES) {
      let current = node;
      let safeguard = 0;
      while (current && replacements < GLOSSARY_MAX_MATCHES && safeguard < 6) {
        const next = wrapTextNodeWithGlossary(current, entries);
        if (!next) {
          break;
        }
        replacements += 1;
        current = next;
        safeguard += 1;
      }
      node = walker.nextNode();
    }
  }

  function wrapTextNodeWithGlossary(textNode, entries) {
    if (!textNode || !textNode.parentNode) {
      return null;
    }
    const original = textNode.textContent;
    if (!original) {
      return null;
    }
    const lower = original.toLowerCase();
    let bestMatch = null;

    entries.forEach((entry) => {
      let searchIndex = lower.indexOf(entry.termLower);
      while (searchIndex !== -1) {
        if (entry.matchWholeWord) {
          const beforeChar = original[searchIndex - 1];
          const afterChar = original[searchIndex + entry.term.length];
          if (isAsciiWordChar(beforeChar) || isAsciiWordChar(afterChar)) {
            searchIndex = lower.indexOf(entry.termLower, searchIndex + entry.termLower.length);
            continue;
          }
        }
        if (!bestMatch || searchIndex < bestMatch.index) {
          bestMatch = { entry, index: searchIndex };
        }
        break;
      }
    });

    if (!bestMatch) {
      return null;
    }

    const { entry, index } = bestMatch;
    const beforeText = original.slice(0, index);
    const matchText = original.slice(index, index + entry.term.length);
    const afterText = original.slice(index + entry.term.length);
    const parent = textNode.parentNode;

    if (beforeText) {
      parent.insertBefore(document.createTextNode(beforeText), textNode);
    }

    const wrapper = createGlossaryWrapper(matchText, entry);
    parent.insertBefore(wrapper, textNode);

    let nextNode = null;
    if (afterText) {
      nextNode = document.createTextNode(afterText);
      parent.insertBefore(nextNode, textNode);
    }

    parent.removeChild(textNode);
    return nextNode;
  }

  function createGlossaryWrapper(displayText, entry) {
    const wrapper = document.createElement("span");
    wrapper.className = "glossary-term";
    wrapper.textContent = "";
    wrapper.dataset.glossaryActive = "false";
    wrapper.tabIndex = 0;
    wrapper.setAttribute("role", "button");
    wrapper.setAttribute("aria-haspopup", "true");
    wrapper.setAttribute("aria-expanded", "false");
    wrapper.setAttribute("data-glossary-term", entry.term);
    wrapper.appendChild(document.createTextNode(displayText));

    const tooltip = createGlossaryTooltip(entry);
    wrapper.appendChild(tooltip);
    wrapper.setAttribute("aria-describedby", tooltip.id);
    registerGlossaryTerm(wrapper);
    return wrapper;
  }

  function createGlossaryTooltip(entry) {
    glossaryTooltipIdCounter += 1;
    const tooltip = document.createElement("span");
    tooltip.className = "glossary-term__tooltip";
    tooltip.id = `glossary-term-${glossaryTooltipIdCounter}`;
    tooltip.setAttribute("role", "tooltip");
    tooltip.textContent = entry.definition;
    return tooltip;
  }

  function registerGlossaryTerm(element) {
    if (!element || element.classList.contains("glossary-term--enhanced")) {
      return;
    }
    element.classList.add("glossary-term--enhanced");
    ensureGlossaryGlobalHandlers();

    const setActive = (active, exclusive) => {
      if (exclusive) {
        closeAllGlossaryTerms(element);
      }
      element.setAttribute("data-glossary-active", active ? "true" : "false");
      element.setAttribute("aria-expanded", active ? "true" : "false");
    };

    element.addEventListener("focus", () => {
      setActive(true, true);
    });

    element.addEventListener("blur", () => {
      setActive(false, false);
    });

    element.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        setActive(false, false);
        element.blur();
      }
    });

    element.addEventListener("mouseenter", () => {
      setActive(true, true);
    });

    element.addEventListener("mouseleave", () => {
      if (!element.matches(":focus")) {
        setActive(false, false);
      }
    });

    element.addEventListener("click", (event) => {
      const isActive = element.getAttribute("data-glossary-active") === "true";
      setActive(!isActive, !isActive);
    });
  }

  function ensureGlossaryGlobalHandlers() {
    if (glossaryHandlersAttached) {
      return;
    }
    glossaryHandlersAttached = true;
    document.addEventListener("click", (event) => {
      if (event.target.closest && event.target.closest(".glossary-term")) {
        return;
      }
      closeAllGlossaryTerms(null);
    });
  }

  function closeAllGlossaryTerms(except) {
    document.querySelectorAll(".glossary-term[data-glossary-active='true']").forEach((element) => {
      if (except && element === except) {
        return;
      }
      element.setAttribute("data-glossary-active", "false");
      element.setAttribute("aria-expanded", "false");
    });
  }

  function isAsciiWordChar(char) {
    if (!char) {
      return false;
    }
    return /[A-Za-z0-9_]/.test(char);
  }

  function initSiteAudioPlayer() {
    const player = document.querySelector("[data-audio-player]");
    if (!player) {
      return;
    }

    const audio = player.querySelector("[data-audio-element]");
    if (!audio) {
      return;
    }

    const toggleButton = player.querySelector("[data-audio-toggle]");
    const muteButton = player.querySelector("[data-audio-mute]");
    const progressTrack = player.querySelector("[data-audio-progress-track]");
    const progressBar = player.querySelector("[data-audio-progress]");
    const timeLabel = player.querySelector("[data-audio-time]");
    const volumeContainer = player.querySelector("[data-audio-volume]");
    const volumeSlider = player.querySelector("[data-audio-volume-slider]");
    const autoplay = player.dataset.autoplay === "true";
    const startMuted = player.dataset.startMuted === "true";
    const EDGE_SNAP_THRESHOLD = 28;
    const EDGE_SNAP_OFFSET = 12;
    player.dataset.audioCollapsed = "false";

    const canonicalizeAudioSrc = (value) => {
      if (!value) {
        return "";
      }
      try {
        const normalized = new URL(value, window.location.href);
        return normalized.pathname.replace(/\/+$/, "");
      } catch (canonicalizeError) {
        return value;
      }
    };

    const audioAttributeSrc = audio.getAttribute("src") || "";
    const audioCurrentSrc = audio.currentSrc || audioAttributeSrc;
    const canonicalAudioSource = canonicalizeAudioSrc(audioAttributeSrc || audioCurrentSrc);

    const clampVolume = (value) => {
      if (!Number.isFinite(value)) {
        return 0;
      }
      return Math.min(Math.max(value, 0), 1);
    };

    const defaultAudioState = {
      src: canonicalAudioSource,
      isPlaying: false,
      shouldResume: false,
      currentTime: 0,
      volume: Number.isFinite(audio.volume) ? audio.volume : 1,
      muted: audio.muted,
    };

    let audioState = { ...defaultAudioState };
    let canPersistAudioState = typeof window !== "undefined" && typeof window.localStorage !== "undefined";

    if (canPersistAudioState) {
      try {
        const testKey = "__autoblog_audio_test__";
        window.localStorage.setItem(testKey, "1");
        window.localStorage.removeItem(testKey);
      } catch (storageError) {
        canPersistAudioState = false;
      }
    }

    const readStoredAudioState = () => {
      if (!canPersistAudioState) {
        return null;
      }
      try {
        const raw = window.localStorage.getItem(AUDIO_STATE_STORAGE_KEY);
        if (!raw) {
          return null;
        }
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object") {
          return null;
        }
        const stored = { ...parsed };
        stored.src = canonicalizeAudioSrc(stored.src || "");
        if (stored.volume !== undefined) {
          stored.volume = Number(stored.volume);
        }
        if (stored.currentTime !== undefined) {
          stored.currentTime = Number(stored.currentTime);
        }
        stored.muted = stored.muted === true;
        stored.isPlaying = stored.isPlaying === true;
        stored.shouldResume = stored.shouldResume === true;
        return stored;
      } catch (readError) {
        return null;
      }
    };

    const storedAudioState = readStoredAudioState();
    if (storedAudioState) {
      const storedSrc = storedAudioState.src || "";
      if (!storedSrc || storedSrc === canonicalAudioSource) {
        audioState = { ...audioState, ...storedAudioState, src: canonicalAudioSource };
      }
    }

    const persistAudioState = () => {
      if (!canPersistAudioState) {
        return;
      }
      try {
        audioState.src = canonicalAudioSource;
        const payload = {
          src: canonicalAudioSource,
          volume: clampVolume(audioState.volume),
          muted: audioState.muted === true,
          currentTime: Number.isFinite(audioState.currentTime) ? audioState.currentTime : 0,
          isPlaying: audioState.isPlaying === true,
          shouldResume: audioState.shouldResume === true,
        };
        window.localStorage.setItem(AUDIO_STATE_STORAGE_KEY, JSON.stringify(payload));
      } catch (writeError) {
        canPersistAudioState = false;
      }
    };

    let audioStateSaveTimeout = null;
    const scheduleAudioStateSave = (immediate = false) => {
      if (!canPersistAudioState) {
        return;
      }
      if (immediate) {
        if (audioStateSaveTimeout !== null) {
          window.clearTimeout(audioStateSaveTimeout);
          audioStateSaveTimeout = null;
        }
        persistAudioState();
        return;
      }
      if (audioStateSaveTimeout !== null) {
        return;
      }
      audioStateSaveTimeout = window.setTimeout(() => {
        audioStateSaveTimeout = null;
        persistAudioState();
      }, 400);
    };

    let playbackPositionRestored = false;
    let shouldResumePlayback = audioState.shouldResume === true || audioState.isPlaying === true;
    let isPageHiding = false;
    const resumeInteractionEvents = ["pointerdown", "keydown", "touchstart"];
    let awaitingResumeAfterGesture = false;
    let pendingUnmuteAfterPlay = false;

    const restorePlaybackPositionIfNeeded = () => {
      if (playbackPositionRestored) {
        return;
      }
      if (!Number.isFinite(audioState.currentTime) || audioState.currentTime <= 0) {
        playbackPositionRestored = true;
        return;
      }
      if (!Number.isFinite(audio.duration) || audio.duration <= 0) {
        return;
      }
      const target = Math.min(
        Math.max(audioState.currentTime, 0),
        Math.max(audio.duration - 0.05, 0)
      );
      audio.currentTime = target;
      audioState.currentTime = target;
      playbackPositionRestored = true;
      scheduleAudioStateSave();
    };

    let rafId = null;
    let lastVolume = audio.volume > 0 ? audio.volume : 0.7;
    let volumeExpanded = player.dataset.volumeExpanded === "true";
    let volumeCollapseTimeout = null;
    const VOLUME_COLLAPSE_DELAY = 600;
    const DRAG_MARGIN = 12;
    const DRAG_ACTIVATION_DISTANCE = 10;
    let dragPointerId = null;
    let dragActive = false;
    let dragPending = false;
    let dragPendingData = null;
    let dragStartX = 0;
    let dragStartY = 0;
    let dragStartLeft = 0;
    let dragStartTop = 0;
    let dragWidth = 0;
    let dragHeight = 0;
    let dragMovedDuringSession = false;
    let suppressCollapsedClickUntil = 0;
    let collapsedSide = null;

    let volumeContainerId = volumeContainer && volumeContainer.id ? volumeContainer.id : null;
    if (volumeContainer && !volumeContainerId) {
      audioPlayerIdCounter += 1;
      volumeContainerId = `site-audio-volume-${audioPlayerIdCounter}`;
      volumeContainer.id = volumeContainerId;
    }
    if (muteButton && volumeContainerId) {
      muteButton.setAttribute("aria-controls", volumeContainerId);
    }

    const isDragSuppressed = (target) => {
      if (!target) {
        return false;
      }
      return Boolean(target.closest("[data-audio-no-drag]"));
    };

    const timestampNow = () =>
      typeof performance !== "undefined" && typeof performance.now === "function"
        ? performance.now()
        : Date.now();

    const setVolumeExpanded = (expanded) => {
      volumeExpanded = !!expanded;
      if (volumeCollapseTimeout !== null) {
        window.clearTimeout(volumeCollapseTimeout);
        volumeCollapseTimeout = null;
      }
      player.setAttribute("data-volume-expanded", volumeExpanded ? "true" : "false");
      if (volumeContainer) {
        volumeContainer.setAttribute("aria-hidden", volumeExpanded ? "false" : "true");
      }
      if (volumeSlider) {
        volumeSlider.tabIndex = volumeExpanded ? 0 : -1;
        if (!volumeExpanded && document.activeElement === volumeSlider) {
          volumeSlider.blur();
        }
      }
      if (muteButton) {
        muteButton.setAttribute("aria-expanded", volumeExpanded ? "true" : "false");
      }
    };

    const setCollapsedState = (side) => {
      const normalized = side === "left" || side === "right" ? side : null;
      if (normalized === collapsedSide) {
        return;
      }

      collapsedSide = normalized;

      if (collapsedSide) {
        player.classList.add("is-collapsed");
        player.setAttribute("data-collapsed-side", collapsedSide);
        player.dataset.audioCollapsed = "true";
        if (collapsedSide === "left") {
          player.style.left = `${EDGE_SNAP_OFFSET}px`;
          player.style.right = "auto";
          player.style.transform = "translate3d(-65%, 0, 0)";
        } else {
          player.style.right = `${EDGE_SNAP_OFFSET}px`;
          player.style.left = "auto";
          player.style.transform = "translate3d(65%, 0, 0)";
        }
        setVolumeExpanded(false);
      } else {
        player.classList.remove("is-collapsed");
        player.removeAttribute("data-collapsed-side");
        player.dataset.audioCollapsed = "false";
        player.style.transform = "";
      }
    };

    const evaluateAutoCollapse = () => {
      if (dragActive) {
        return;
      }
      const rect = player.getBoundingClientRect();
      const distanceLeft = rect.left;
      const distanceRight = window.innerWidth - rect.right;
      const nearLeft = distanceLeft <= EDGE_SNAP_THRESHOLD;
      const nearRight = distanceRight <= EDGE_SNAP_THRESHOLD;

      if (nearLeft && (!nearRight || distanceLeft <= distanceRight)) {
        setCollapsedState("left");
      } else if (nearRight) {
        setCollapsedState("right");
      } else {
        setCollapsedState(null);
      }
    };

    const handleCollapsedClick = (event) => {
      if (!collapsedSide) {
        suppressCollapsedClickUntil = 0;
        return;
      }
      if (timestampNow() < suppressCollapsedClickUntil) {
        event.preventDefault();
        event.stopPropagation();
        return;
      }
      suppressCollapsedClickUntil = 0;
      event.preventDefault();
      event.stopPropagation();
      setCollapsedState(null);
    };

    const openVolume = () => {
      if (volumeCollapseTimeout !== null) {
        window.clearTimeout(volumeCollapseTimeout);
        volumeCollapseTimeout = null;
      }
      setVolumeExpanded(true);
    };

    const scheduleVolumeCollapse = () => {
      if (document.activeElement === volumeSlider) {
        return;
      }
      if (volumeCollapseTimeout !== null) {
        window.clearTimeout(volumeCollapseTimeout);
      }
      volumeCollapseTimeout = window.setTimeout(() => {
        if (document.activeElement === volumeSlider) {
          return;
        }
        setVolumeExpanded(false);
      }, VOLUME_COLLAPSE_DELAY);
    };

    const computeClampedPosition = (left, top, width, height) => {
      const maxLeft = Math.max(DRAG_MARGIN, window.innerWidth - width - DRAG_MARGIN);
      const maxTop = Math.max(DRAG_MARGIN, window.innerHeight - height - DRAG_MARGIN);
      const clampedLeft = Math.min(Math.max(left, DRAG_MARGIN), maxLeft);
      const clampedTop = Math.min(Math.max(top, DRAG_MARGIN), maxTop);
      return { left: clampedLeft, top: clampedTop };
    };

    const clampPlayerIntoViewport = () => {
      if (!player.style.left && !player.style.top) {
        return;
      }
      const rect = player.getBoundingClientRect();
      const { left, top } = computeClampedPosition(rect.left, rect.top, rect.width, rect.height);
      player.style.left = `${left}px`;
      player.style.top = `${top}px`;
      player.style.right = "auto";
      player.style.bottom = "auto";
    };

    const clearPendingDrag = () => {
      dragPending = false;
      dragPendingData = null;
    };

    const startDragging = (event, options = {}) => {
      if (dragActive) {
        return;
      }
      const preserveCollapsed = options.preserveCollapsed === true && !!collapsedSide;
      if (!preserveCollapsed) {
        setCollapsedState(null);
      }
      dragActive = true;
      dragPointerId =
        typeof options.pointerId === "number"
          ? options.pointerId
          : typeof event.pointerId === "number"
          ? event.pointerId
          : null;
      player.classList.add("is-dragging");
      setVolumeExpanded(false);
      const fallbackRect = player.getBoundingClientRect();
      const initialWidth = Number.isFinite(options.initialWidth) ? options.initialWidth : fallbackRect.width;
      const initialHeight = Number.isFinite(options.initialHeight) ? options.initialHeight : fallbackRect.height;
      const initialLeft = Number.isFinite(options.initialLeft) ? options.initialLeft : fallbackRect.left;
      const initialTop = Number.isFinite(options.initialTop) ? options.initialTop : fallbackRect.top;
      const initialClientX = Number.isFinite(options.initialClientX)
        ? options.initialClientX
        : event.clientX;
      const initialClientY = Number.isFinite(options.initialClientY)
        ? options.initialClientY
        : event.clientY;
      dragWidth = initialWidth;
      dragHeight = initialHeight;
      dragStartLeft = initialLeft;
      dragStartTop = initialTop;
      dragStartX = initialClientX;
      dragStartY = initialClientY;
      dragMovedDuringSession = false;
      if (preserveCollapsed && collapsedSide === "left") {
        player.style.left = `${EDGE_SNAP_OFFSET}px`;
        player.style.right = "auto";
      } else if (preserveCollapsed && collapsedSide === "right") {
        player.style.right = `${EDGE_SNAP_OFFSET}px`;
        player.style.left = "auto";
      } else {
        player.style.left = `${dragStartLeft}px`;
        player.style.right = "auto";
      }
      player.style.top = `${dragStartTop}px`;
      player.style.bottom = "auto";
      player.dataset.audioDragged = "true";
      if (dragPointerId !== null && typeof player.setPointerCapture === "function") {
        try {
          player.setPointerCapture(dragPointerId);
        } catch (captureError) {
          // Ignore environments without pointer capture support.
        }
      }
    };

    const updateDragging = (event) => {
      if (!dragActive) {
        return;
      }
      const deltaX = event.clientX - dragStartX;
      const deltaY = event.clientY - dragStartY;
      const targetLeft = dragStartLeft + deltaX;
      const targetTop = dragStartTop + deltaY;
      const { left, top } = computeClampedPosition(targetLeft, targetTop, dragWidth, dragHeight);
      player.style.top = `${top}px`;
      if (collapsedSide === "left") {
        player.style.left = `${EDGE_SNAP_OFFSET}px`;
        player.style.right = "auto";
      } else if (collapsedSide === "right") {
        player.style.right = `${EDGE_SNAP_OFFSET}px`;
        player.style.left = "auto";
      } else {
        player.style.left = `${left}px`;
        player.style.right = "auto";
      }
      dragMovedDuringSession = true;
    };

    const stopDragging = () => {
      if (!dragActive) {
        return;
      }
      dragActive = false;
      player.classList.remove("is-dragging");
      if (dragPointerId !== null && typeof player.releasePointerCapture === "function") {
        try {
          player.releasePointerCapture(dragPointerId);
        } catch (releaseError) {
          // Ignore environments without pointer capture support.
        }
      }
      dragPointerId = null;
      clearPendingDrag();
    };

    setVolumeExpanded(volumeExpanded);

    if (Number.isFinite(audioState.volume)) {
      audio.volume = clampVolume(audioState.volume);
    } else {
      audio.volume = clampVolume(audio.volume);
    }
    audio.muted = Boolean(audioState.muted);
    if (audio.volume > 0) {
      lastVolume = audio.volume;
    }
    audioState.volume = clampVolume(audio.volume);
    audioState.muted = audio.muted;
    scheduleAudioStateSave();
    if (audio.readyState >= 1) {
      restorePlaybackPositionIfNeeded();
    }
    audio.addEventListener("loadedmetadata", restorePlaybackPositionIfNeeded);
    audio.addEventListener("durationchange", restorePlaybackPositionIfNeeded);

    const formatSegment = (value) => {
      const clamped = Math.max(0, Math.floor(Number.isFinite(value) ? value : 0));
      const minutes = String(Math.floor(clamped / 60)).padStart(2, "0");
      const seconds = String(clamped % 60).padStart(2, "0");
      return `${minutes}:${seconds}`;
    };

    const formatTimeDisplay = (current, duration) => {
      if (!Number.isFinite(duration) || duration <= 0) {
        return formatSegment(current);
      }
      return `${formatSegment(current)} / ${formatSegment(duration)}`;
    };

    const setPlayerState = (state) => {
      player.dataset.playerState = state;
      if (toggleButton) {
        toggleButton.setAttribute("aria-pressed", state === "playing" ? "true" : "false");
        toggleButton.setAttribute(
          "aria-label",
          state === "playing" ? "暂停背景音乐" : "播放背景音乐"
        );
      }
    };

    const syncVolumeControls = () => {
      const effectiveMuted = audio.muted || audio.volume <= 0.0001;
      const effectiveVolume = effectiveMuted ? 0 : clampVolume(audio.volume);
      if (volumeSlider) {
        const percent = Math.round(effectiveVolume * 100);
        volumeSlider.value = String(percent);
        volumeSlider.style.setProperty("--volume-progress", `${percent}%`);
      }

      let volumeLevel = "muted";
      if (effectiveVolume > 0.66) {
        volumeLevel = "high";
      } else if (effectiveVolume > 0.33) {
        volumeLevel = "medium";
      } else if (effectiveVolume > 0) {
        volumeLevel = "low";
      }
      player.dataset.volumeLevel = volumeLevel;

      if (!effectiveMuted && effectiveVolume > 0) {
        lastVolume = effectiveVolume;
      }
      audioState.volume = clampVolume(audio.volume);
    };

    const updateMuteState = () => {
      const effectiveMuted = audio.muted || audio.volume <= 0.0001;
      player.dataset.muted = effectiveMuted ? "true" : "false";
      if (muteButton) {
        muteButton.setAttribute("aria-pressed", effectiveMuted ? "true" : "false");
        muteButton.setAttribute("aria-label", effectiveMuted ? "取消静音" : "静音背景音乐");
      }
      syncVolumeControls();
      audioState.muted = effectiveMuted;
      scheduleAudioStateSave();
    };

    const updateTime = () => {
      if (timeLabel) {
        timeLabel.textContent = formatTimeDisplay(audio.currentTime, audio.duration);
      }
    };

    const updateProgress = () => {
      if (!progressTrack || !progressBar) {
        return;
      }
      const ratio = audio.duration > 0 ? audio.currentTime / audio.duration : 0;
      const progress = Math.min(Math.max(ratio, 0), 1);
      const percent = `${(progress * 100).toFixed(2)}%`;
      progressBar.style.setProperty("--audio-progress", percent);
      progressTrack.setAttribute("aria-valuenow", (progress * 100).toFixed(1));
      progressTrack.setAttribute("aria-valuetext", formatTimeDisplay(audio.currentTime, audio.duration));
    };

    const cancelProgressLoop = () => {
      if (rafId !== null) {
        window.cancelAnimationFrame(rafId);
        rafId = null;
      }
    };

    const requestProgressLoop = () => {
      cancelProgressLoop();
      const loop = () => {
        updateTime();
        updateProgress();
        if (!audio.paused) {
          rafId = window.requestAnimationFrame(loop);
        } else {
          rafId = null;
        }
      };
      rafId = window.requestAnimationFrame(loop);
    };

    const togglePlayback = () => {
      if (audio.paused) {
        player.classList.remove("is-autoplay-blocked");
        attemptPlaybackStart(true);
      } else {
        audio.pause();
      }
    };

    const toggleMute = () => {
      const isEffectivelyMuted = audio.muted || audio.volume <= 0.0001;
      if (isEffectivelyMuted) {
        const restored = clampVolume(lastVolume > 0 ? lastVolume : 0.7);
        audio.muted = false;
        audio.volume = restored;
      } else {
        lastVolume = audio.volume > 0 ? audio.volume : lastVolume;
        audio.muted = true;
      }
      updateMuteState();
    };

    const seekTo = (clientX) => {
      if (!progressTrack || !Number.isFinite(audio.duration) || audio.duration <= 0) {
        return;
      }
      const rect = progressTrack.getBoundingClientRect();
      if (!rect.width) {
        return;
      }
      const ratio = (clientX - rect.left) / rect.width;
      const clamped = Math.min(Math.max(ratio, 0), 1);
      audio.currentTime = clamped * audio.duration;
      updateTime();
      updateProgress();
      audioState.currentTime = audio.currentTime;
      scheduleAudioStateSave();
    };

    if (toggleButton) {
      toggleButton.addEventListener("click", () => {
        player.classList.remove("is-autoplay-blocked");
        togglePlayback();
      });
    }

    if (muteButton) {
      muteButton.addEventListener("click", () => {
        player.classList.remove("is-autoplay-blocked");
        toggleMute();
        openVolume();
      });
      muteButton.addEventListener("focus", openVolume);
      muteButton.addEventListener("blur", scheduleVolumeCollapse);
    }

    if (progressTrack) {
      if (!progressTrack.hasAttribute("tabindex")) {
        progressTrack.tabIndex = 0;
      }
      progressTrack.addEventListener("click", (event) => {
        seekTo(event.clientX);
      });
      progressTrack.addEventListener("keydown", (event) => {
        if (!Number.isFinite(audio.duration) || audio.duration <= 0) {
          return;
        }
        const STEP = 5;
        if (event.key === "ArrowRight" || event.key === "ArrowUp") {
          audio.currentTime = Math.min(audio.currentTime + STEP, audio.duration);
          event.preventDefault();
        } else if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
          audio.currentTime = Math.max(audio.currentTime - STEP, 0);
          event.preventDefault();
        } else if (event.key === "Home") {
          audio.currentTime = 0;
          event.preventDefault();
        } else if (event.key === "End") {
          audio.currentTime = audio.duration;
          event.preventDefault();
        } else {
          return;
        }
        player.classList.remove("is-autoplay-blocked");
        updateTime();
        updateProgress();
        audioState.currentTime = audio.currentTime;
        scheduleAudioStateSave();
      });
    }

    if (volumeSlider) {
      volumeSlider.addEventListener("focus", openVolume);
      volumeSlider.addEventListener("blur", scheduleVolumeCollapse);
      volumeSlider.addEventListener("input", () => {
        player.classList.remove("is-autoplay-blocked");
        const raw = Number(volumeSlider.value);
        const normalized = clampVolume(raw / 100);
        const percent = Math.round(normalized * 100);
        volumeSlider.style.setProperty("--volume-progress", `${percent}%`);

        if (normalized <= 0) {
          audio.volume = 0;
          audio.muted = true;
        } else {
          audio.volume = normalized;
          audio.muted = false;
        }
        updateMuteState();
        scheduleAudioStateSave(true);
      });
    }

    const handleDocumentClick = (event) => {
      if (!player.contains(event.target)) {
        setVolumeExpanded(false);
      }
    };

    document.addEventListener("click", handleDocumentClick);

    player.addEventListener("pointerdown", (event) => {
      if (event.pointerType === "mouse" && event.button !== 0) {
        return;
      }
      if (isDragSuppressed(event.target)) {
        return;
      }
      if (dragActive) {
        return;
      }
      const rect = player.getBoundingClientRect();
      dragMovedDuringSession = false;
      dragPending = true;
      dragPendingData = {
        pointerId: typeof event.pointerId === "number" ? event.pointerId : null,
        preserveCollapsed: collapsedSide !== null,
        initialClientX: event.clientX,
        initialClientY: event.clientY,
        initialLeft: rect.left,
        initialTop: rect.top,
        initialWidth: rect.width,
        initialHeight: rect.height,
      };
    });

    player.addEventListener("pointermove", (event) => {
      if (dragActive) {
        if (dragPointerId !== null && event.pointerId !== dragPointerId) {
          return;
        }
        updateDragging(event);
        event.preventDefault();
        return;
      }
      if (!dragPending || !dragPendingData) {
        return;
      }
      if (dragPendingData.pointerId !== null && event.pointerId !== dragPendingData.pointerId) {
        return;
      }
      const deltaX = Math.abs(event.clientX - dragPendingData.initialClientX);
      const deltaY = Math.abs(event.clientY - dragPendingData.initialClientY);
      if (Math.max(deltaX, deltaY) < DRAG_ACTIVATION_DISTANCE) {
        return;
      }
      startDragging(event, {
        preserveCollapsed: dragPendingData.preserveCollapsed,
        pointerId: dragPendingData.pointerId,
        initialClientX: dragPendingData.initialClientX,
        initialClientY: dragPendingData.initialClientY,
        initialLeft: dragPendingData.initialLeft,
        initialTop: dragPendingData.initialTop,
        initialWidth: dragPendingData.initialWidth,
        initialHeight: dragPendingData.initialHeight,
      });
      clearPendingDrag();
      updateDragging(event);
      event.preventDefault();
    });

    player.addEventListener("pointerup", (event) => {
      const pointerMatchesDrag = dragPointerId === null || event.pointerId === dragPointerId;
      if (dragActive && pointerMatchesDrag) {
        stopDragging();
        if (dragMovedDuringSession) {
          suppressCollapsedClickUntil = timestampNow() + 180;
        }
        evaluateAutoCollapse();
        return;
      }
      if (dragPending && dragPendingData) {
        const pointerMatchesPending =
          dragPendingData.pointerId === null || event.pointerId === dragPendingData.pointerId;
        if (pointerMatchesPending) {
          clearPendingDrag();
        }
      }
    });

    player.addEventListener("pointercancel", (event) => {
      const pointerMatchesDrag = dragPointerId === null || event.pointerId === dragPointerId;
      if (dragActive && pointerMatchesDrag) {
        stopDragging();
        if (dragMovedDuringSession) {
          suppressCollapsedClickUntil = timestampNow() + 180;
        }
        evaluateAutoCollapse();
        return;
      }
      if (dragPending && dragPendingData) {
        const pointerMatchesPending =
          dragPendingData.pointerId === null || event.pointerId === dragPendingData.pointerId;
        if (pointerMatchesPending) {
          clearPendingDrag();
          evaluateAutoCollapse();
        }
      }
    });

    window.addEventListener("resize", () => {
      clampPlayerIntoViewport();
      evaluateAutoCollapse();
    });
    window.addEventListener("orientationchange", () => {
      clampPlayerIntoViewport();
      evaluateAutoCollapse();
    });

    player.addEventListener("click", handleCollapsedClick, true);

    evaluateAutoCollapse();

    player.addEventListener("mouseenter", () => {
      if (volumeCollapseTimeout !== null) {
        window.clearTimeout(volumeCollapseTimeout);
        volumeCollapseTimeout = null;
      }
    });

    player.addEventListener("mouseleave", scheduleVolumeCollapse);

    player.addEventListener("focusout", (event) => {
      if (!player.contains(event.relatedTarget)) {
        scheduleVolumeCollapse();
      }
    });

    audio.addEventListener("play", () => {
      isPageHiding = false;
      player.classList.remove("is-autoplay-blocked");
      setPlayerState("playing");
      requestProgressLoop();
      audioState.isPlaying = true;
      audioState.shouldResume = true;
      audioState.currentTime = audio.currentTime;
      scheduleAudioStateSave();
      removeDeferredResumeListeners();
      pendingUnmuteAfterPlay = false;
    });

    audio.addEventListener("pause", () => {
      setPlayerState("paused");
      cancelProgressLoop();
      updateTime();
      updateProgress();
      audioState.isPlaying = false;
      if (!isPageHiding) {
        audioState.shouldResume = false;
      }
      audioState.currentTime = audio.currentTime;
      scheduleAudioStateSave();
      isPageHiding = false;
      removeDeferredResumeListeners();
      pendingUnmuteAfterPlay = false;
    });

    audio.addEventListener("loadedmetadata", () => {
      updateTime();
      updateProgress();
      audioState.currentTime = audio.currentTime;
      scheduleAudioStateSave();
    });

    audio.addEventListener("timeupdate", () => {
      updateTime();
      updateProgress();
      audioState.currentTime = audio.currentTime;
      scheduleAudioStateSave();
    });

    audio.addEventListener("durationchange", () => {
      updateTime();
      updateProgress();
      if (Number.isFinite(audio.duration) && audio.duration > 0) {
        audioState.duration = audio.duration;
        scheduleAudioStateSave();
      }
    });

    audio.addEventListener("volumechange", () => {
      if (!audio.muted && audio.volume > 0) {
        lastVolume = clampVolume(audio.volume);
      }
      updateMuteState();
    });

    audio.addEventListener("ended", () => {
      if (!audio.loop) {
        setPlayerState("ended");
      }
      audioState.isPlaying = false;
      audioState.shouldResume = false;
      audioState.currentTime = 0;
      scheduleAudioStateSave();
      removeDeferredResumeListeners();
      pendingUnmuteAfterPlay = false;
    });

    if (!storedAudioState && startMuted && !audio.muted) {
      audio.muted = true;
    }
    updateMuteState();
    setPlayerState(audio.paused ? "paused" : "playing");
    updateTime();
    updateProgress();

    function removeDeferredResumeListeners() {
      if (!awaitingResumeAfterGesture) {
        return;
      }
      awaitingResumeAfterGesture = false;
      resumeInteractionEvents.forEach((eventName) => {
        document.removeEventListener(eventName, handleDeferredResume, true);
      });
    }

    function handleDeferredResume() {
      removeDeferredResumeListeners();
      shouldResumePlayback = true;
      audioState.shouldResume = true;
      scheduleAudioStateSave();
      attemptPlaybackStart(true);
    }

    function queueDeferredResume() {
      if (awaitingResumeAfterGesture) {
        return;
      }
      awaitingResumeAfterGesture = true;
      audioState.shouldResume = true;
      scheduleAudioStateSave();
      resumeInteractionEvents.forEach((eventName) => {
        document.addEventListener(eventName, handleDeferredResume, {
          capture: true,
        });
      });
    }

    function attemptPlaybackStart(triggeredByInteraction = false) {
      pendingUnmuteAfterPlay = false;
      const desiredMuted = audioState.muted === true;
      const storedVolume = Number.isFinite(audioState.volume)
        ? clampVolume(audioState.volume)
        : clampVolume(audio.volume);
      const previousMuted = audio.muted;

      if ((shouldResumePlayback || autoplay || triggeredByInteraction) && !desiredMuted) {
        if (!audio.muted) {
          audio.muted = true;
          pendingUnmuteAfterPlay = true;
        }
      }

      if (!Number.isFinite(audio.volume) || audio.volume <= 0) {
        audio.volume = storedVolume;
      }

      const playAttempt = audio.play();

      if (!playAttempt || typeof playAttempt.then !== "function") {
        player.classList.remove("is-autoplay-blocked");
        if (pendingUnmuteAfterPlay && !desiredMuted) {
          audio.muted = false;
          audio.volume = storedVolume;
        }
        updateMuteState();
        shouldResumePlayback = false;
        audioState.shouldResume = true;
        audioState.isPlaying = true;
        audioState.currentTime = audio.currentTime;
        scheduleAudioStateSave();
        removeDeferredResumeListeners();
        pendingUnmuteAfterPlay = false;
        return;
      }

      playAttempt
        .then(() => {
          player.classList.remove("is-autoplay-blocked");
          if (pendingUnmuteAfterPlay && !desiredMuted) {
            audio.muted = false;
            audio.volume = storedVolume;
          }
          updateMuteState();
          shouldResumePlayback = false;
          audioState.shouldResume = true;
          audioState.isPlaying = true;
          audioState.currentTime = audio.currentTime;
          scheduleAudioStateSave();
          removeDeferredResumeListeners();
          pendingUnmuteAfterPlay = false;
        })
        .catch(() => {
          player.classList.add("is-autoplay-blocked");
          setPlayerState("paused");
          if (pendingUnmuteAfterPlay && !desiredMuted) {
            audio.muted = previousMuted;
          }
          updateMuteState();
          audioState.isPlaying = false;
          audioState.currentTime = audio.currentTime;
          audioState.shouldResume = true;
          scheduleAudioStateSave();
          if (!triggeredByInteraction) {
            queueDeferredResume();
          }
          pendingUnmuteAfterPlay = false;
        });
    }

    function ensurePlaybackStart() {
      if (!shouldResumePlayback && !autoplay) {
        return;
      }

      if (audio.readyState >= 2) {
        attemptPlaybackStart();
        return;
      }

      const handleCanPlay = () => {
        audio.removeEventListener("canplay", handleCanPlay);
        attemptPlaybackStart();
      };

      audio.addEventListener("canplay", handleCanPlay);
    }

    function handlePageHide() {
      isPageHiding = true;
      audioState.currentTime = audio.currentTime;
      audioState.volume = clampVolume(audio.volume);
      audioState.muted = audio.muted || audio.volume <= 0.0001;
      if (!audio.paused) {
        audioState.shouldResume = true;
        audioState.isPlaying = true;
      }
      scheduleAudioStateSave(true);
      removeDeferredResumeListeners();
      pendingUnmuteAfterPlay = false;
    }

    if (shouldResumePlayback || autoplay) {
      ensurePlaybackStart();
    }

    window.addEventListener("pagehide", handlePageHide);
    window.addEventListener("beforeunload", handlePageHide);
  }

  function initNotFoundPage() {
    const container = document.querySelector("[data-404-typing]");
    if (!container) {
      return;
    }

    const textElement = container.querySelector(".not-found__poem-text");
    const headingElement = document.querySelector("[data-404-heading]");
    if (!textElement) {
      return;
    }

    if (container.dataset.typingInitialized === "true") {
      return;
    }
    container.dataset.typingInitialized = "true";

    const defaultText = (textElement.dataset.default || textElement.textContent || "").trim();
    const rawPhrases = container.getAttribute("data-phrases") || "";
    let phrases = [];
    if (rawPhrases) {
      try {
        const parsed = JSON.parse(rawPhrases);
        if (Array.isArray(parsed)) {
          phrases = parsed
            .map((item) => (typeof item === "string" ? item.trim() : String(item || "").trim()))
            .filter(Boolean);
        }
      } catch (parseError) {
        phrases = rawPhrases
          .split("|")
          .map((item) => item.trim())
          .filter(Boolean);
      }
    }

    if (!phrases.length) {
      const fallback = defaultText;
      phrases = fallback ? [fallback] : ["只在此山中，云深不知处"];
      textElement.textContent = phrases[0];
    }

    const reduceMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const caretElement = container.querySelector(".not-found__caret");

    if (phrases.length <= 1 || reduceMotionQuery.matches) {
      const resolvedText = phrases[0] || defaultText;
      textElement.textContent = resolvedText;
      if (headingElement && resolvedText) {
        headingElement.textContent = resolvedText;
      }
      container.classList.add("not-found__poem--static");
      container.classList.remove("is-typing");
      return;
    }

    const TYPE_SPEED = 130;
    const DELETE_SPEED = 60;
    const HOLD_DURATION = 2200;
    const GAP_DURATION = 520;

    let active = true;
    let timerId = null;
    let phraseIndex = 0;
    let charIndex = 0;
    let deleting = false;

    const clearTimer = () => {
      if (timerId !== null) {
        window.clearTimeout(timerId);
        timerId = null;
      }
    };

    const schedule = (delay) => {
      clearTimer();
      if (!active) {
        return;
      }
      timerId = window.setTimeout(step, delay);
    };

    const step = () => {
      if (!active) {
        return;
      }
      const phrase = phrases[phraseIndex];
      if (!phrase) {
        return;
      }
      if (!deleting) {
        charIndex += 1;
        textElement.textContent = phrase.slice(0, charIndex);
        if (charIndex >= phrase.length) {
          if (headingElement) {
            headingElement.textContent = phrase;
          }
          deleting = true;
          schedule(HOLD_DURATION);
        } else {
          schedule(TYPE_SPEED);
        }
      } else {
        charIndex -= 1;
        if (charIndex <= 0) {
          charIndex = 0;
          deleting = false;
          phraseIndex = (phraseIndex + 1) % phrases.length;
          textElement.textContent = "";
          schedule(GAP_DURATION);
        } else {
          textElement.textContent = phrase.slice(0, charIndex);
          if (headingElement) {
            headingElement.textContent = phrase.slice(0, Math.max(charIndex, 1));
          }
          schedule(DELETE_SPEED);
        }
      }
    };

    const handleVisibilityChange = () => {
      if (document.hidden) {
        clearTimer();
      } else if (active && timerId === null) {
        schedule(GAP_DURATION);
      }
    };

    const handleReduceMotionChange = (event) => {
      if (event.matches) {
        teardown();
        textElement.textContent = phrases[phraseIndex];
        container.classList.add("not-found__poem--static");
      }
    };

    const addReduceMotionListener = (listener) => {
      if (!reduceMotionQuery || typeof listener !== "function") {
        return;
      }
      if (typeof reduceMotionQuery.addEventListener === "function") {
        reduceMotionQuery.addEventListener("change", listener);
      } else if (typeof reduceMotionQuery.addListener === "function") {
        reduceMotionQuery.addListener(listener);
      }
    };

    const removeReduceMotionListener = (listener) => {
      if (!reduceMotionQuery || typeof listener !== "function") {
        return;
      }
      if (typeof reduceMotionQuery.removeEventListener === "function") {
        reduceMotionQuery.removeEventListener("change", listener);
      } else if (typeof reduceMotionQuery.removeListener === "function") {
        reduceMotionQuery.removeListener(listener);
      }
    };

    const teardown = () => {
      if (!active) {
        return;
      }
      active = false;
      clearTimer();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      removeReduceMotionListener(handleReduceMotionChange);
      window.removeEventListener("beforeunload", teardown);
      window.removeEventListener("pagehide", teardown);
    };

    container.classList.add("is-typing");
    container.classList.remove("not-found__poem--static");
    textElement.textContent = "";
    schedule(TYPE_SPEED);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    addReduceMotionListener(handleReduceMotionChange);
    window.addEventListener("beforeunload", teardown);
    window.addEventListener("pagehide", teardown);
  }

  function initBackToTop() {
    const button = document.querySelector("[data-back-to-top]");
    if (!button) {
      return;
    }

    const SHOW_AT = 360;
    let ticking = false;

    const update = () => {
      const shouldShow = window.scrollY > SHOW_AT;
      button.classList.toggle("is-visible", shouldShow);
      ticking = false;
    };

    const onScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(update);
        ticking = true;
      }
    };

    button.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });

    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", update);
    window.addEventListener("orientationchange", update);
  }

  function initHeaderCondense() {
    const header = document.querySelector(".site-header");
    if (!header) {
      return;
    }

    const reduceMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    let ticking = false;
    let lastScrollY = getScrollY();

    const update = () => {
      const current = getScrollY();
      const shouldCondense = current > 60;
      header.classList.toggle("is-condensed", shouldCondense);

      if (!shouldCondense) {
        header.classList.remove("is-hidden");
      }

      if (reduceMotionQuery.matches) {
        header.classList.remove("is-hidden");
      } else {
        const delta = current - lastScrollY;
        const scrollingDown = delta > 8;
        const scrollingUp = delta < -8;

        if (current < 48 || scrollingUp) {
          header.classList.remove("is-hidden");
        } else if (scrollingDown && current > 180) {
          header.classList.add("is-hidden");
        }
      }

      lastScrollY = current;
      ticking = false;
    };

    const handleScroll = () => {
      if (ticking) {
        return;
      }
      ticking = true;
      window.requestAnimationFrame(update);
    };

    update();
    window.addEventListener("scroll", handleScroll, { passive: true });
    window.addEventListener("resize", update);
    window.addEventListener("orientationchange", update);
    window.addEventListener("load", update);
    addMediaListener(reduceMotionQuery, update);
  }

  function getScrollY() {
    if (typeof window.pageYOffset === "number") {
      return window.pageYOffset;
    }
    if (typeof window.scrollY === "number") {
      return window.scrollY;
    }
    const doc = document.documentElement || document.body;
    return doc ? doc.scrollTop || 0 : 0;
  }
  function addMediaListener(mq, callback) {
    if (!mq || typeof callback !== "function") {
      return;
    }
    if (typeof mq.addEventListener === "function") {
      mq.addEventListener("change", callback);
    } else if (typeof mq.addListener === "function") {
      mq.addListener(callback);
    }
  }
})();
