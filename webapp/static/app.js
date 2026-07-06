(() => {
  const COPY_TAIL = "\n—— 来自「配图说」小助手，愿你的每条朋友圈都有人懂";

  const LS = {
    style: "moments_style",
    emoji: "moments_emoji",
    punct: "moments_punct",
    provider: "moments_provider",
    min: "moments_min_chars",
    max: "moments_max_chars",
    extra: "moments_extra_blocked",
    supplement: "moments_supplement",
    inspiration: "moments_inspiration",
    outlang: "moments_output_language",
    copyTail: "moments_append_copy_tail",
    noImage: "moments_no_image",
    textIdea: "moments_text_idea",
    emojiColor: "moments_emoji_color",
  };
  const SS_DESC = "moments_last_description";
  const SS_EMOJI_APPENDIX = "moments_emoji_tone_appendix";
  const SS_FEEDBACK_SENT = "moments_feedback_sent";

  const $ = (id) => document.getElementById(id);
  const drop = $("drop");
  const pick = $("pick");
  const folder = $("folder");
  const thumbs = $("thumbs");
  const countEl = $("count");
  const form = $("f");
  const err = $("err");
  const out = $("out");
  const descEl = $("desc");
  const candsEl = $("cands");
  const regen = $("regen");
  const clearBtn = $("clear");
  const moodLine = $("mood_line");
  const thermo = $("thermo");
  const noImageMode = $("no_image_mode");
  const imageUploadBlock = $("image-upload-block");
  const textIdeaBlock = $("text-idea-block");
  const textIdeaInput = $("text-idea-input");
  const emojiToneWrap = $("emoji_tone_wrap");
  const emojiColorSuggest = $("emoji_color_suggest");
  const styleDesc = $("style_desc");
  const progressLine = $("progress_line");
  const progressText = $("progress_text");

  const STYLE_DESCRIPTIONS = {
    humor:      "好笑、轻松，自带梗但不油腻",
    literary:   "干净意象，像一句随笔",
    concise:    "短句利落，一眼读完",
    lyrical:    "留白和节奏，不硬押韵",
    daily_life: "日常小事的温度感",
    travel:     "出游/在路上的松弛感和新鲜感",
    fun:        "网络热梗、夸张自嘲，年轻化表达",
    recommend:  "「这个真的绝了」的推荐语气，适合分享好物/好店",
  };

  /** @type {File[]} */
  let files = [];

  function syncNoImageUi() {
    const on = noImageMode.checked;
    imageUploadBlock.hidden = on;
    textIdeaBlock.hidden = !on;
    emojiToneWrap.hidden = on;
    if (on) emojiColorSuggest.checked = false;
  }

  function toneFromStyle(slug) {
    const map = {
      humor: "hot",
      literary: "fresh",
      concise: "cool",
      lyrical: "fresh",
      daily_life: "fresh",
      travel: "fresh",
      fun: "hot",
      recommend: "hot",
    };
    return map[(slug || "").trim()] || "fresh";
  }

  function guessMoodLine(desc) {
    const t = desc || "";
    if (!String(t).trim()) return null;
    if (/聚会|派对|生日|朋友聚餐|一起|合影|人群|多人/.test(t)) {
      return { icon: "🎉", text: "适合聚会" };
    }
    if (/夜景|霓虹|雨|独自|安静|树影|书|窗边|路灯/.test(t)) {
      return { icon: "🌥️", text: "有点文艺" };
    }
    if (/美食|大餐|咖啡|奶茶|小吃|餐桌|餐厅|菜/.test(t)) {
      return { icon: "☀️", text: "元气满满" };
    }
    if (/阳光|晴天|户外|海边|草地|蓝天|笑容|笑/.test(t)) {
      return { icon: "☀️", text: "元气满满" };
    }
    return { icon: "✨", text: "刚刚好" };
  }

  function updateResultsChrome(description) {
    const mood = guessMoodLine(description);
    if (mood) {
      moodLine.hidden = false;
      moodLine.textContent = `AI 猜你今天的心情：${mood.icon} ${mood.text}`;
    } else {
      moodLine.hidden = true;
    }
    const tone = toneFromStyle($("style").value);
    thermo.hidden = false;
    thermo.classList.remove("thermo--cool", "thermo--fresh", "thermo--hot");
    thermo.classList.add(`thermo--${tone}`);
  }

  function savePrefs() {
    localStorage.setItem(LS.style, $("style").value);
    localStorage.setItem(LS.emoji, $("use_emoji").checked ? "1" : "0");
    localStorage.setItem(LS.punct, $("use_punctuation").checked ? "1" : "0");
    localStorage.setItem(LS.provider, $("provider").value);
    localStorage.setItem(LS.min, $("min_chars").value);
    localStorage.setItem(LS.max, $("max_chars").value);
    localStorage.setItem(LS.extra, $("extra_blocked").value);
    localStorage.setItem(LS.supplement, $("supplement").value);
    localStorage.setItem(LS.inspiration, $("inspiration").value);
    localStorage.setItem(LS.outlang, $("output_language").value);
    localStorage.setItem(LS.copyTail, $("append_copy_tail").checked ? "1" : "0");
    localStorage.setItem(LS.noImage, noImageMode.checked ? "1" : "0");
    localStorage.setItem(LS.textIdea, textIdeaInput.value);
    localStorage.setItem(LS.emojiColor, emojiColorSuggest.checked ? "1" : "0");
  }

  function loadPrefs() {
    const g = (k, d) => localStorage.getItem(k) ?? d;
    const sv = g(LS.style, "");
    if (sv) $("style").value = sv;
    $("use_emoji").checked = g(LS.emoji, "1") === "1";
    $("use_punctuation").checked = g(LS.punct, "1") === "1";
    $("provider").value = g(LS.provider, $("provider").value);
    $("min_chars").value = g(LS.min, "10");
    $("max_chars").value = g(LS.max, "72");
    $("extra_blocked").value = g(LS.extra, "");
    $("supplement").value = g(LS.supplement, "");
    $("inspiration").value = g(LS.inspiration, "");
    $("output_language").value = g(LS.outlang, "zh-Hans");
    $("append_copy_tail").checked = g(LS.copyTail, "0") === "1";
    noImageMode.checked = g(LS.noImage, "0") === "1";
    textIdeaInput.value = g(LS.textIdea, "");
    emojiColorSuggest.checked = g(LS.emojiColor, "0") === "1";
    syncNoImageUi();
  }

  function isImageFile(f) {
    return f.type.startsWith("image/") || /\.(jpe?g|png|gif|webp)$/i.test(f.name);
  }

  function mergeIncoming(incoming) {
    if (noImageMode.checked) {
      noImageMode.checked = false;
      syncNoImageUi();
    }
    const list = [...files];
    for (const f of incoming) {
      if (!isImageFile(f)) continue;
      const dup = list.some(
        (x) => x.name === f.name && x.size === f.size && x.lastModified === f.lastModified
      );
      if (!dup) list.push(f);
    }
    list.sort((a, b) => a.name.localeCompare(b.name, "zh"));
    files = list.slice(0, 9);
    renderThumbs();
    savePrefs();
  }

  function renderThumbs() {
    thumbs.innerHTML = "";
    const urlObjs = [];
    for (const f of files) {
      const u = URL.createObjectURL(f);
      urlObjs.push(u);
      const img = document.createElement("img");
      img.src = u;
      img.alt = f.name;
      img.title = f.name;
      thumbs.appendChild(img);
    }
    countEl.textContent = `已选 ${files.length} 张`;
    setTimeout(() => urlObjs.forEach(URL.revokeObjectURL), 6e4);
  }

  function showErr(msg) {
    err.hidden = !msg;
    err.textContent = msg || "";
  }

  function updateStyleDesc() {
    const slug = $("style").value;
    if (styleDesc) styleDesc.textContent = STYLE_DESCRIPTIONS[slug] || "";
  }

  let _loadingActive = false;

  function showProgress(text) {
    _loadingActive = true;
    if (progressLine) progressLine.classList.add("show");
    if (progressText) progressText.textContent = text || "正在准备…";
  }

  function hideProgress() {
    _loadingActive = false;
    if (progressLine) progressLine.classList.remove("show");
  }

  async function simulateLoading(hasImages) {
    showProgress(hasImages ? "正在看图…" : "正在理解你的想法…");
    await new Promise(r => setTimeout(r, 600));
    if (!_loadingActive) return;
    showProgress("正在写文案…");
    // 不在这里加"评审中"，评审是内部流程，由后端自动完成
  }

  async function sendFeedback(adopted) {
    if (sessionStorage.getItem(SS_FEEDBACK_SENT) === "1") return;
    sessionStorage.setItem(SS_FEEDBACK_SENT, "1");
    const style = $("style").value.trim();
    if (!style) return;
    try {
      await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ style, adopted: !!adopted }),
      });
    } catch {
      // Silently ignore feedback errors
    }
  }

  drop.addEventListener("dragover", (e) => {
    e.preventDefault();
    drop.classList.add("drag");
  });
  drop.addEventListener("dragleave", () => drop.classList.remove("drag"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    drop.classList.remove("drag");
    mergeIncoming([...e.dataTransfer.files]);
  });
  drop.addEventListener("click", () => pick.click());

  pick.addEventListener("change", () => {
    mergeIncoming([...pick.files]);
    pick.value = "";
  });
  folder.addEventListener("change", () => {
    mergeIncoming([...folder.files]);
    folder.value = "";
  });
  clearBtn.addEventListener("click", () => {
    files = [];
    renderThumbs();
  });

  noImageMode.addEventListener("change", () => {
    if (noImageMode.checked) {
      files = [];
      renderThumbs();
      pick.value = "";
      folder.value = "";
    }
    syncNoImageUi();
    savePrefs();
  });

  [
    "min_chars",
    "max_chars",
    "provider",
    "extra_blocked",
    "supplement",
    "inspiration",
    "output_language",
    "text-idea-input",
  ].forEach((id) => {
    $(id).addEventListener("change", savePrefs);
    $(id).addEventListener("input", savePrefs);
  });
  $("style").addEventListener("change", () => {
    updateStyleDesc();
    savePrefs();
  });
  ["use_emoji", "use_punctuation", "append_copy_tail", "emoji_color_suggest"].forEach((id) => {
    $(id).addEventListener("change", savePrefs);
  });

  function renderColorAnalysis(data) {
    const container = $("color_swatches");
    const dotsEl = $("color_dots");
    const warmthEl = $("color_warmth");
    const ca = data.color_analysis;
    if (!ca || !ca.colors || !ca.colors.length) {
      if (container) container.hidden = true;
      return;
    }
    if (container) container.hidden = false;
    if (dotsEl) {
      dotsEl.innerHTML = ca.colors.map(c =>
        `<span class="color-dot" style="background:rgb(${c.r},${c.g},${c.b})" title="rgb(${c.r},${c.g},${c.b})"></span>`
      ).join("");
    }
    if (warmthEl) {
      const cls = ca.warmth === "暖色调" ? "warm" : ca.warmth === "冷色调" ? "cool" : "neutral";
      warmthEl.textContent = ca.warmth || "";
      warmthEl.className = "color-warmth " + cls;
    }
  }

  function renderMemory(data) {
    const block = $("memory_hint");
    const mem = data.memory;
    if (!mem || !mem.summary) {
      if (block) block.hidden = true;
      return;
    }
    if (block) {
      block.hidden = false;
      block.textContent = `🧠 本次生成参考了你最近的风格偏好：${mem.summary}（采纳率 ${mem.adopted_ratio}）`;
    }
  }

  function renderReview(data) {
    const block = $("review_block");
    const content = $("review_content");
    const review = data.review;
    if (!review || !review.enabled) {
      block.hidden = true;
      return;
    }
    block.hidden = false;
    let html = "";

    if (review.parse_error || review.error) {
      html += `<p class="review-note review-warn">⚠️ ${review.error || "评审解析失败"}</p>`;
    } else if (review.scores && review.scores.length) {
      const roundTag = review.round ? ` (第${review.round}轮)` : "";
      const retryTag = review.retried ? " 🔄 已自动重试" : "";
      html += `<p class="review-summary"><strong>评审结果${roundTag}</strong>${retryTag}：${review.summary || ""}</p>`;
      html += `<p class="review-pass">及格：${review.pass_count || 0} / 3（阈值 ≥ ${review.threshold || 2} 条，单条均分 ≥ ${review.score_threshold || 6}）</p>`;
      html += `<ul class="review-scores">`;
      for (const s of review.scores) {
        const passIcon = s.passed ? "✅" : "❌";
        html += `<li>${passIcon} <strong>候选${s.index}</strong> 均分 ${s.average} —`;
        html += ` 避雷:${s.safety} 字数:${s.length} 质量:${s.quality} 差异:${s.diversity}`;
        if (s.comment) html += ` <span class="review-comment">“${s.comment}”</span>`;
        html += `</li>`;
      }
      html += `</ul>`;
    }
    if (review.retry_failed) {
      html += `<p class="review-note review-warn">⚠️ ${review.retry_reason || "重试失败"}</p>`;
    }
    if (review.retry_no_improvement) {
      html += `<p class="review-note review-info">ℹ️ 重试后评分未改善（${review.retry_pass_count}/3），保留原结果</p>`;
    }
    content.innerHTML = html;
  }

  function renderCandidates(data) {
    candsEl.innerHTML = "";
    (data.candidates || []).forEach((c, i) => {
      const div = document.createElement("div");
      div.className = "candidate";
      div.style.transitionDelay = `${i * 120}ms`;
      const meta = document.createElement("div");
      meta.className = "meta";
      const lenBadge = document.createElement("span");
      lenBadge.className = "badge " + (c.length_ok ? "ok" : "bad");
      lenBadge.textContent = c.length_ok ? `字数 OK（${c.length}）` : `字数不符（${c.length}）`;
      meta.appendChild(lenBadge);
      if (c.sensitive_masked && (c.sensitive_hits || []).length) {
        const s = document.createElement("span");
        s.className = "badge bad";
        s.textContent = "已脱敏：" + c.sensitive_hits.join("、");
        meta.appendChild(s);
      }
      const body = document.createElement("div");
      body.textContent = c.text;
      const copy = document.createElement("button");
      copy.type = "button";
      copy.textContent = "复制";
      copy.style.marginTop = "0.5rem";
      copy.addEventListener("click", async () => {
        sendFeedback(true);  // 记录采纳
        const tail = $("append_copy_tail").checked ? COPY_TAIL : "";
        try {
          await navigator.clipboard.writeText(c.text + tail);
          copy.textContent = "已复制";
          setTimeout(() => (copy.textContent = "复制"), 1500);
        } catch {
          copy.textContent = "复制失败";
          setTimeout(() => (copy.textContent = "复制"), 1500);
        }
      });
      div.appendChild(meta);
      div.appendChild(body);
      div.appendChild(copy);
      candsEl.appendChild(div);
    });
    // 触发入场动画（下一帧）
    requestAnimationFrame(() => {
      candsEl.querySelectorAll(".candidate").forEach(c => c.classList.add("show"));
    });
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    showErr("");
    const noIm = noImageMode.checked;
    const idea = textIdeaInput.value.trim();
    if (!noIm && !files.length) {
      showErr("请先选择至少一张图片，或勾选「无图片」并写下想法。");
      return;
    }
    if (noIm && !idea) {
      showErr("无图片模式下请先在文本框里写点心情或关键词。");
      return;
    }
    const minC = parseInt($("min_chars").value, 10);
    const maxC = parseInt($("max_chars").value, 10);
    if (minC > maxC) {
      showErr("最少字数不能大于最多字数。");
      return;
    }
    const fd = new FormData();
    if (!noIm) for (const f of files) fd.append("files", f);
    fd.append("style", $("style").value.trim());
    fd.append("use_emoji", $("use_emoji").checked ? "true" : "false");
    fd.append("use_punctuation", $("use_punctuation").checked ? "true" : "false");
    fd.append("provider", $("provider").value);
    fd.append("min_chars", String(minC));
    fd.append("max_chars", String(maxC));
    fd.append("extra_blocked", $("extra_blocked").value);
    fd.append("supplement", $("supplement").value);
    fd.append("inspiration", $("inspiration").value);
    fd.append("output_language", $("output_language").value);
    fd.append("no_image_mode", noIm ? "true" : "false");
    fd.append("text_idea", idea);
    const wantTone =
      !noIm && files.length > 0 && emojiColorSuggest.checked && $("use_emoji").checked;
    fd.append("emoji_color_suggest", wantTone ? "true" : "false");

    $("submit").disabled = true;
    simulateLoading(!noIm);  // 启动分阶段提示动画（不等待）
    try {
      const res = await fetch("/api/full", { method: "POST", body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        hideProgress();
        showErr(data.error || `请求失败（${res.status}）`);
        return;
      }
      hideProgress();
      sessionStorage.setItem(SS_DESC, data.description || "");
      sessionStorage.setItem(SS_EMOJI_APPENDIX, data.emoji_tone_appendix || "");
      if (data.color_analysis) {
        sessionStorage.setItem("moments_color_analysis", JSON.stringify(data.color_analysis));
      }
      sessionStorage.removeItem(SS_FEEDBACK_SENT);  // 新生成，重置反馈标记
      descEl.textContent = data.description || "";
      updateResultsChrome(data.description || "");
      renderCandidates(data);
      renderReview(data);
      renderColorAnalysis(data);
      renderMemory(data);
      out.hidden = false;
      regen.disabled = !(data.description && String(data.description).trim());
      savePrefs();
    } catch (x) {
      hideProgress();
      showErr(String(x));
    } finally {
      $("submit").disabled = false;
    }
  });

  regen.addEventListener("click", async () => {
    const description = sessionStorage.getItem(SS_DESC);
    if (!description) {
      showErr("没有可用的图片描述，请先生成一次。");
      return;
    }
    showErr("");
    // 记录上一次结果未被采纳
    await sendFeedback(false);
    const minC = parseInt($("min_chars").value, 10);
    const maxC = parseInt($("max_chars").value, 10);
    if (minC > maxC) {
      showErr("最少字数不能大于最多字数。");
      return;
    }
    const body = {
      description,
      style: $("style").value.trim(),
      use_emoji: $("use_emoji").checked,
      use_punctuation: $("use_punctuation").checked,
      provider: $("provider").value,
      min_chars: minC,
      max_chars: maxC,
      extra_blocked_lines: $("extra_blocked").value,
      supplement: $("supplement").value,
      inspiration: $("inspiration").value,
      output_language: $("output_language").value,
      emoji_tone_appendix: sessionStorage.getItem(SS_EMOJI_APPENDIX) || "",
    };
    regen.disabled = true;
    simulateLoading(false);  // 换三条不需要重新看图
    try {
      const res = await fetch("/api/regenerate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        hideProgress();
        showErr(data.error || `请求失败（${res.status}）`);
        return;
      }
      hideProgress();
      sessionStorage.removeItem(SS_FEEDBACK_SENT);  // 新结果，重置反馈标记
      updateResultsChrome(description);
      renderCandidates(data);
      renderReview(data);
      // 颜色分析从 sessionStorage 恢复（换三条不会重新分析图片）
      try {
        const saved = sessionStorage.getItem("moments_color_analysis");
        if (saved) renderColorAnalysis({ color_analysis: JSON.parse(saved) });
      } catch { /* ignore */ }
      renderMemory(data);
      savePrefs();
    } catch (x) {
      hideProgress();
      showErr(String(x));
    } finally {
      regen.disabled = false;
    }
  });

  function ensureStyleOption() {
    const sel = $("style");
    const ok = [...sel.options].some((o) => o.value === sel.value);
    if (!ok && sel.options.length) sel.selectedIndex = 0;
  }

  loadPrefs();
  ensureStyleOption();
  updateStyleDesc();
  syncNoImageUi();
  renderThumbs();
  regen.disabled = !sessionStorage.getItem(SS_DESC);
})();
