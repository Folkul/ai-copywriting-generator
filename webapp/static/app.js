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
  };
  const SS_DESC = "moments_last_description";

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

  /** @type {File[]} */
  let files = [];

  function toneFromStyle(s) {
    const x = (s || "").trim();
    if (/冷静叙事|简约干净/.test(x)) return "cool";
    if (/温暖治愈|高级|杂志风|杂志/.test(x)) return "fresh";
    if (/俏皮可爱|俏皮/.test(x)) return "hot";
    return "fresh";
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
  }

  function isImageFile(f) {
    return f.type.startsWith("image/") || /\.(jpe?g|png|gif|webp)$/i.test(f.name);
  }

  function mergeIncoming(incoming) {
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

  [
    "style",
    "min_chars",
    "max_chars",
    "provider",
    "extra_blocked",
    "supplement",
    "inspiration",
    "output_language",
  ].forEach((id) => {
    $(id).addEventListener("change", savePrefs);
    $(id).addEventListener("input", savePrefs);
  });
  ["use_emoji", "use_punctuation", "append_copy_tail"].forEach((id) => {
    $(id).addEventListener("change", savePrefs);
  });

  function renderCandidates(data) {
    candsEl.innerHTML = "";
    for (const c of data.candidates || []) {
      const div = document.createElement("div");
      div.className = "candidate";
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
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    showErr("");
    if (!files.length) {
      showErr("请先选择至少一张图片。");
      return;
    }
    const minC = parseInt($("min_chars").value, 10);
    const maxC = parseInt($("max_chars").value, 10);
    if (minC > maxC) {
      showErr("最少字数不能大于最多字数。");
      return;
    }
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
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

    $("submit").disabled = true;
    try {
      const res = await fetch("/api/full", { method: "POST", body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        showErr(data.error || `请求失败（${res.status}）`);
        return;
      }
      sessionStorage.setItem(SS_DESC, data.description || "");
      descEl.textContent = data.description || "";
      updateResultsChrome(data.description || "");
      renderCandidates(data);
      out.hidden = false;
      regen.disabled = !(data.description && String(data.description).trim());
      savePrefs();
    } catch (x) {
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
    };
    regen.disabled = true;
    try {
      const res = await fetch("/api/regenerate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        showErr(data.error || `请求失败（${res.status}）`);
        return;
      }
      updateResultsChrome(description);
      renderCandidates(data);
      savePrefs();
    } catch (x) {
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
  renderThumbs();
  regen.disabled = !sessionStorage.getItem(SS_DESC);
})();
