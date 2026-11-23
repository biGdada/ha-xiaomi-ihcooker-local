/**
 * Chunmi IH Cooker Slim card for Home Assistant.
 *
 * Registers as `custom:chunmi-ihcooker-card` in the Add Card search picker.
 * Talks only to the chunmi_ihcooker_slim integration services/entities.
 */

const DOMAIN = "chunmi_ihcooker_slim";
const TAG = "chunmi-ihcooker-card";

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

class ChunmiIHCookerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._cookers = [];
    this._cooker = null;
    this._ready = false;
    this._query = "";
    this._results = [];
    this._favorites = [];
    this._favoritesOpen = false;
    this._suggestions = [];
    this._suggestTimer = null;
    this._queryFocused = false;
    this._detail = null;
    this._message = "";
    this._busy = false;
    this._refresh = null;
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("Invalid configuration for Chunmi IH Cooker Slim card");
    }
    this._config = config;
    this._ready = false;
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._ready) {
      this._ready = true;
      hass
        .callWS({ type: `${DOMAIN}/card_config` })
        .then(async (data) => {
          this._cookers = data?.cookers || [];
          this._cooker =
            this._cookers.find((c) => c.device_id === this._config.device_id) ||
            this._cookers[0] ||
            null;
          this._stateSig = null;
          this._renderedSig = null;
          if (!this._cooker) {
            this._message = "No Chunmi IH Cooker Slim integration configured.";
          }
          await this.refreshFavorites(false);
          this.render();
        })
        .catch(() => {
          this._cooker = this.fallbackCooker();
          this._stateSig = null;
          this._renderedSig = null;
          if (!this._cooker) {
            this._message = "No Chunmi IH Cooker Slim integration configured.";
          }
          this.render();
        });
      return;
    }
    // Refresh whenever any displayed cooker state/sensor changes so controls like
    // Start/Stop stay in sync. Avoid rebuilding while typing to keep focus.
    const sig = this.stateSignature();
    if (sig === this._stateSig) return;
    this._stateSig = sig;
    if (this._queryFocused) return;
    this.render();
  }

  stateSignature() {
    const entities = this._cooker?.entities || {};
    return JSON.stringify(
      Object.keys(entities)
        .sort()
        .map((key) => {
          const id = entities[key];
          const state = id ? this._hass?.states?.[id] : null;
          return [key, id, state?.state, state?.attributes];
        })
    );
  }

  getCardSize() {
    return 12;
  }

  fallbackCooker() {
    const ids = Object.keys(this._hass?.states || {});
    if (!ids.length) return null;
    const find = (suffix) => ids.find((id) => id.endsWith(`_${suffix}`)) || null;
    const entities = {
      cook_mode: find("cook_mode") || find("profile"),
      profile: find("profile"),
      status: find("app_status") || find("status_name") || find("status"),
      current_action: find("current_action"),
      recipe_id: find("active_recipe_id"),
      current_mode: find("cook_mode_name"),
      library: find("recipe_library"),
      translation: find("recipe_translation_status"),
      refreshing: find("recipe_refresh_status"),
      query: find("recipe_query"),
    };
    if (!Object.values(entities).some(Boolean)) return null;
    return {
      device_id: null,
      target_entity: Object.values(entities).find(Boolean),
      name: "Rice Cooker",
      entities,
    };
  }

  get entity() {
    return (key) => this._cooker?.entities?.[key] || null;
  }

  state(key) {
    const id = this.entity(key);
    if (!id || !this._hass?.states?.[id]) return "—";
    return this._hass.states[id].state;
  }

  attribute(key, name) {
    const id = this.entity(key);
    return this._hass?.states?.[id]?.attributes?.[name];
  }

  tr(key) {
    const language = String(this._hass?.language || "en").toLowerCase().replace("_", "-");
    const zh = language.startsWith("zh");
    const labels = {
      en: {
        recipesFound: "{n} recipe(s) found",
        savedRecipes: "{n} saved recipe(s)",
        searchHint: "Search by Chinese or English name, ingredient, or ID.",
        noFavorites: "No favorites yet. Open a recipe and choose Add to favorites.",
        open: "Open",
        remove: "Remove",
        ingredients: "Ingredients",
        steps: "Steps",
        tips: "Tips",
        startCooking: "Start cooking",
        stopCooking: "Stop cooking",
        translateRecipe: "Translate recipe",
        addFavorite: "Add to favorites",
        removeFavorite: "Remove from favorites",
        translation: "Translation",
        cookMode: "Cook mode",
        currentAction: "Current action",
        refreshRecipes: "Refresh recipes",
        recipes: "Recipes",
        search: "Search",
        favorites: "Favorites",
        searchPlaceholder: "Search recipes… (中文亦可)",
        localOnly: "Local miIO control. The token is never shown.",
        translated: "Translated {n} string(s)",
        translationFailed: "Translation failed",
        noMissing: "No missing translations",
        starting: "Starting refresh",
        searching: "Searching Joyami catalogue",
        downloading: "Downloading recipes",
        merging: "Merging translations",
        translating: "Translating new text",
        translatingPriority: "Translating titles and ingredients",
        translatingDetails: "Translating descriptions and steps",
        finishing: "Finishing",
        refreshing: "Refreshing recipes",
        recipesLoaded: "{n} recipes loaded",
        waitingPanel: "Recipe loaded. Press the cooker knob to start cooking.",
      },
      zh: {
        recipesFound: "找到 {n} 个菜谱",
        savedRecipes: "已收藏 {n} 个菜谱",
        searchHint: "可按中英文名称、食材或 ID 搜索。",
        noFavorites: "还没有收藏，打开菜谱后可点击收藏。",
        open: "打开",
        remove: "移除",
        ingredients: "食材",
        steps: "步骤",
        tips: "小贴士",
        startCooking: "开始烹饪",
        stopCooking: "停止烹饪",
        translateRecipe: "翻译菜谱",
        addFavorite: "加入收藏",
        removeFavorite: "取消收藏",
        translation: "翻译",
        cookMode: "烹饪模式",
        currentAction: "当前动作",
        refreshRecipes: "刷新菜谱",
        recipes: "菜谱",
        search: "搜索",
        favorites: "收藏",
        searchPlaceholder: "搜索菜谱…（可输入中文）",
        localOnly: "纯本地 miIO 控制，不会显示 token。",
        translated: "已翻译 {n} 条文本",
        translationFailed: "翻译失败",
        noMissing: "没有待翻译内容",
        starting: "正在启动刷新",
        searching: "正在搜索 Joyami 菜谱目录",
        downloading: "正在下载菜谱",
        merging: "正在合并翻译",
        translating: "正在翻译新文本",
        translatingPriority: "正在翻译标题和食材",
        translatingDetails: "正在翻译描述和步骤",
        finishing: "即将完成",
        refreshing: "正在刷新菜谱",
        recipesLoaded: "已加载 {n} 个菜谱",
        waitingPanel: "菜谱已载入，请按下炉具旋钮开始烹饪。",
      },
    };
    return (zh ? labels.zh : labels.en)[key] ?? labels.en[key] ?? key;
  }

  displayName(recipe) {
    if (!recipe) return "";
    const primary = recipe.name || recipe.name_en || recipe.name_zh || "";
    const zh = recipe.name_zh || "";
    if (zh && primary && zh !== primary) return `${primary} (${zh})`;
    return primary;
  }

  async call(service, data = {}, wantsResponse = false) {
    if (!this._hass || !this._cooker) return null;
    const target = this._cooker.device_id
      ? { device_id: this._cooker.device_id }
      : this._cooker.target_entity
        ? { entity_id: this._cooker.target_entity }
        : {};
    const request = {
      type: "call_service",
      domain: DOMAIN,
      service,
      target,
      service_data: data,
    };
    // Only services that declare response support may set return_response.
    // start / stop / add_favorite do not, and HA rejects those calls otherwise.
    if (wantsResponse) request.return_response = true;
    const result = await this._hass.callWS(request);
    return result?.response ?? null;
  }

  async run(service, data = {}, wantsResponse = false) {
    this._busy = true;
    this._message = "";
    this.render();
    try {
      return await this.call(service, data, wantsResponse);
    } catch (err) {
      this._message = err?.message || String(err);
      return null;
    } finally {
      this._busy = false;
      this.render();
    }
  }

  async search() {
    const query = this._query.trim();
    this._query = "";
    const response = await this.run(
      "search_recipes",
      { query, limit: 20 },
      true
    );
    this._results = response?.recipes || [];
    this._suggestions = [];
    this.render();
  }

  async open(recipe, language = "ha") {
    const response = await this.run("get_recipe", { recipe, language }, true);
    if (response) {
      this._detail = response;
      this._detailLanguage = language;
      this._query = "";
      // Showing one recipe replaces the result list.
      this._results = [];
    }
    this._suggestions = [];
    this.render();
  }

  async toggleRecipeLanguage() {
    if (!this._detail) return;
    const next = this._detailLanguage === "original" ? "ha" : "original";
    const response = await this.run(
      "get_recipe",
      { recipe: this._detail.id, language: next },
      true
    );
    if (!response) return;
    this._detail = response;
    this._detailLanguage = next;
    this._query = "";
    this.render();
  }

  async autocomplete() {
    const query = this._query.trim();
    if (!query) {
      this._suggestions = [];
      this.renderSuggestions();
      return;
    }
    try {
      const response = await this.call("search_recipes", { query, limit: 8 }, true);
      this._suggestions = response?.recipes || [];
    } catch (err) {
      this._suggestions = [];
      this._message = err?.message || String(err);
    }
    this.renderSuggestions();
  }

  renderSuggestions() {
    const list = this.shadowRoot?.querySelector("[data-suggestions]");
    if (!list) return;
    list.innerHTML = this._suggestions
      .map(
        (r) =>
          `<li><button data-suggest="${escapeHtml(r.id)}">${escapeHtml(
            this.displayName(r)
          )}</button></li>`
      )
      .join("");
    list.hidden = this._suggestions.length === 0;
    list.querySelectorAll("[data-suggest]").forEach((btn) => {
      // Keep the search input focused until click fires: a blur would let a
      // hass update rebuild the DOM and detach this button mid-click.
      btn.addEventListener("mousedown", (event) => event.preventDefault());
      btn.addEventListener("click", () => this.open(btn.dataset.suggest));
    });
  }

  async start() {
    if (!this._detail) return;
    const isIdle = this.isIdle();
    if (!isIdle) {
      const name = this.displayName(this._detail);
      const ok = window.confirm(
        `The cooker is already running. Replace the current cook with "${name}"?`
      );
      if (!ok) return;
    }
    const result = await this.run(
      "start_recipe",
      { recipe: this._detail.id },
      true
    );
    if (result?.waiting_for_panel) {
      this._message = this.tr("waitingPanel");
      this.render();
    }
  }

  isIdle() {
    const statusState = String(this.state("status") || "").toLowerCase();
    return (
      statusState === "idle" ||
      statusState === "off" ||
      statusState === "shutdown" ||
      statusState === "sleeping" ||
      statusState === "—" ||
      statusState === "unknown" ||
      statusState === "待机中" ||
      statusState === "休眠中"
    );
  }

  async refreshFavorites(render = true) {
    const response = await this.run("list_favorites", {}, true);
    this._favorites = response?.recipes || [];
    if (render) this.render();
  }

  async showFavorites() {
    this._favoritesOpen = !this._favoritesOpen;
    if (this._favoritesOpen) await this.refreshFavorites(false);
    this.render();
  }

  async toggleFavorite() {
    if (!this._detail) return;
    const service = this._detail.favorite ? "remove_favorite" : "add_favorite";
    await this.run(service, { recipe: this._detail.id });
    this._detail.favorite = !this._detail.favorite;
    if (this._favoritesOpen) await this.refreshFavorites(false);
    this.render();
  }

  async translateRecipe() {
    if (!this._detail) return;
    const language = this._detailLanguage || "ha";
    const result = await this.run(
      "translate_recipe",
      { recipe: this._detail.id },
      true
    );
    if (!result) return;
    const details = [];
    if (result.translated) {
      details.push(this.tr("translated").replace("{n}", result.translated));
    } else if (result.failed) {
      details.push(this.tr("translationFailed"));
    } else {
      details.push(this.tr("noMissing"));
    }
    if (result.error) details.push(result.error);
    const message = details.join(" · ");
    await this.open(this._detail.id, language);
    this._message = message;
    this.render();
  }

  async removeFavorite(recipeId) {
    await this.run("remove_favorite", { recipe: recipeId });
    this._favorites = this._favorites.filter((r) => String(r.id) !== String(recipeId));
    if (String(this._detail?.id) === String(recipeId)) {
      this._detail.favorite = false;
    }
    this.render();
  }

  async stop() {
    await this.run("cancel_cooking");
  }

  async startMode() {
    const modeEntity = this.entity("cook_mode") || this.entity("profile");
    const preset = modeEntity ? this._hass?.states?.[modeEntity]?.state : null;
    await this.run("start_preset", preset ? { preset } : {});
  }



  async refresh() {
    // Optimistic local state; the shared sensor keeps other cards in sync.
    this._refresh = { phase: "start", done: 0, total: 0 };
    this.render();
    const result = await this.run("refresh_recipes");
    this._refresh = null;
    if (result) {
      const details = [];
      if (result.error) details.push(result.error);
      if (result.count != null) details.push(this.tr("recipesLoaded").replace("{n}", result.count));
      if (result.translation_warning) details.push(result.translation_warning);
      this._message = details.join(" · ");
    }
    this.render();
  }

  render() {
    if (!this.shadowRoot) return;
    this._stateSig = this.stateSignature();
    this._renderedSig = this._stateSig;
    const active = this.shadowRoot.activeElement;
    const restoreQueryFocus =
      active && active.matches?.("[data-query]") ? active.selectionStart : null;
    const cooker = this._cooker;
    const name = this._config.name || cooker?.name || "Rice Cooker";
    const translation = this.state("translation");
    const warning =
      translation && translation !== "ok" && translation !== "OK" ? translation : "";
    const isIdle = this.isIdle();

    const modeEntity = this.entity("cook_mode") || this.entity("profile");
    const modeState = modeEntity ? this._hass?.states?.[modeEntity] : null;
    const modes = modeState?.attributes?.options || [];
    const selectedMode = modeState?.state || "";
    const reportedMode = this.state("current_mode");
    const currentMode = isIdle
      ? (selectedMode && modes.includes(selectedMode)
          ? selectedMode
          : reportedMode && reportedMode !== "—" && modes.includes(reportedMode)
            ? reportedMode
            : selectedMode)
      : (reportedMode && reportedMode !== "—" && modes.includes(reportedMode)
          ? reportedMode
          : selectedMode);



    const sharedPhase = this.state("refreshing");
    const sharedActive = !["—", "idle", "done", "unknown"].includes(sharedPhase);
    const refreshInfo = sharedActive
      ? {
          phase: sharedPhase,
          done: Number(this.attribute("refreshing", "done") || 0),
          total: Number(this.attribute("refreshing", "total") || 0),
        }
      : this._refresh;
    const phaseLabels = {
      start: this.tr("starting"),
      search: this.tr("searching"),
      download: this.tr("downloading"),
      merge: this.tr("merging"),
      translate: this.tr("translating"),
      translate_priority: this.tr("translatingPriority"),
      translate_details: this.tr("translatingDetails"),
      done: this.tr("finishing"),
    };
    const refreshPercent = refreshInfo?.total
      ? Math.min(100, Math.round((refreshInfo.done / refreshInfo.total) * 100))
      : 0;
    const refreshProgress = refreshInfo
      ? `<div class="refresh-progress">
          <div>${escapeHtml(
            phaseLabels[refreshInfo.phase] || this.tr("refreshing")
          )}${refreshInfo.total ? `: ${refreshInfo.done}/${refreshInfo.total}` : "…"}</div>
          <div class="progress-track ${
            refreshInfo.total ? "" : "indeterminate"
          }"><div class="progress-fill" style="width:${refreshPercent}%"></div></div>
        </div>`
      : "";

    const thumb = (r) =>
      r.image
        ? `<span class="thumb-wrap"><img class="thumb" src="${escapeHtml(r.image)}" alt="" loading="lazy" /><img class="thumb-preview" src="${escapeHtml(r.image)}" alt="" loading="lazy" /></span>`
        : `<span class="thumb-wrap thumb-empty" aria-hidden="true"></span>`;
    const results = this._results.length
      ? `<p class="muted">${this.tr("recipesFound").replace("{n}", this._results.length)}</p>
        <table>
          <thead><tr><th></th><th>ID</th><th>Recipe</th><th>Time</th><th></th></tr></thead>
          <tbody>${this._results
            .map(
              (r) => `<tr>
                <td>${thumb(r)}</td>
                <td>${escapeHtml(r.id)}</td>
                <td>${escapeHtml(this.displayName(r))}</td>
                <td>${escapeHtml(r.duration || "—")}</td>
                <td><button data-open="${escapeHtml(r.id)}">${this.tr("open")}</button></td>
              </tr>`
            )
            .join("")}</tbody>
        </table>`
      : `<p class="muted">${this.tr("searchHint")}</p>`;

    const favorites = this._favoritesOpen
      ? this._favorites.length
        ? `<p class="muted">${this.tr("savedRecipes").replace("{n}", this._favorites.length)}</p>
          <table>
            <thead><tr><th></th><th>ID</th><th>Recipe</th><th>Time</th><th></th></tr></thead>
            <tbody>${this._favorites
              .map(
                (r) => `<tr>
                  <td>${thumb(r)}</td>
                  <td>${escapeHtml(r.id)}</td>
                  <td>${escapeHtml(this.displayName(r))}</td>
                  <td>${escapeHtml(r.duration || "—")}</td>
                  <td>
                    <button data-open="${escapeHtml(r.id)}">${this.tr("open")}</button>
                    <button data-remove-fav="${escapeHtml(r.id)}">${this.tr("remove")}</button>
                  </td>
                </tr>`
              )
              .join("")}</tbody>
          </table>`
        : `<p class="muted">${this.tr("noFavorites")}</p>`
      : "";

    const detail = this._detail
      ? `<div class="detail">
          <div class="detail-header">
            <h3>${escapeHtml(this.displayName(this._detail))}</h3>
            <button data-action="detail-language" ${this._busy ? "disabled" : ""}>${
              this._detailLanguage === "original"
                ? (this._cooker?.language_label || "HA language")
                : "中文"
            }</button>
          </div>
          ${
            this._detail.image
              ? `<img src="${escapeHtml(this._detail.image)}" alt="" />`
              : ""
          }
          ${this._detail.description ? `<p>${escapeHtml(this._detail.description)}</p>` : ""}
          <h4>${this.tr("ingredients")}</h4>
          <ul>${(this._detail.ingredients || [])
            .map(
              (i) =>
                `<li>${escapeHtml(i.quantity || "")} ${escapeHtml(i.name || "")}</li>`
            )
            .join("")}</ul>
          <h4>${this.tr("steps")}</h4>
          <ol>${(this._detail.steps || [])
            .map((s) => `<li>${escapeHtml(s.content || s)}</li>`)
            .join("")}</ol>
          ${
            this._detail.tips
              ? `<h4>${this.tr("tips")}</h4><p>${escapeHtml(this._detail.tips)}</p>`
              : ""
          }
          <div class="actions">
            <button class="primary" data-action="start">${this.tr("startCooking")}</button>
            <button data-action="favorite">${
              this._detail.favorite ? this.tr("removeFavorite") : this.tr("addFavorite")
            }</button>
            <button data-action="translate">${this.tr("translateRecipe")}</button>
          </div>
        </div>`
      : "";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        .card {
          padding: 16px;
          border-radius: var(--ha-card-border-radius, 12px);
          background: var(--ha-card-background, var(--card-background-color, #fff));
          color: var(--primary-text-color);
          box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,.12));
        }
        h2 { margin: 0 0 4px; font-size: 1.25rem; }
        h3 { margin: 12px 0 4px; }
        h4 { margin: 12px 0 4px; font-size: .95rem; }
        .detail-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
        }
        .detail-header h3 { margin: 0; }
        p, li { line-height: 1.45; }
        .muted { color: var(--secondary-text-color); }
        .grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
          gap: 8px;
          margin: 12px 0;
        }
        .grid.single { grid-template-columns: 1fr; }
        .metric {
          padding: 8px;
          border-radius: 8px;
          background: var(--secondary-background-color);
        }
        .metric span { display: block; font-size: .75rem; color: var(--secondary-text-color); }
        .metric strong { font-size: 1rem; }
        .mode-row { margin: 12px 0; }
        ha-select { width: 100%; }
        .actions { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
        button {
          cursor: pointer;
          padding: 7px 12px;
          border: 1px solid var(--primary-color);
          border-radius: 6px;
          background: transparent;
          color: var(--primary-color);
        }
        button.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); }
        button:disabled { opacity: .5; cursor: default; }
        input, select {
          padding: 7px;
          border-radius: 6px;
          border: 1px solid var(--divider-color);
          background: var(--TextField-input-background-color, inherit);
          color: inherit;
        }
        input { min-width: 180px; }
        .suggestions {
          list-style: none;
          margin: 0;
          padding: 4px 0;
          border: 1px solid var(--divider-color);
          border-radius: 6px;
          background: var(--card-background-color, #fff);
          max-height: 240px;
          overflow-y: auto;
        }
        .suggestions button {
          display: block;
          width: 100%;
          padding: 7px 10px;
          border: 0;
          border-radius: 0;
          text-align: left;
          background: transparent;
          color: inherit;
        }
        .suggestions button:hover { background: var(--secondary-background-color); }
        table { width: 100%; border-collapse: collapse; margin-top: 8px; }
        th, td { text-align: left; padding: 5px 6px; border-bottom: 1px solid var(--divider-color); vertical-align: middle; }
        .thumb-wrap { position: relative; display: inline-flex; width: 44px; height: 44px; }
        .thumb, .thumb-empty {
          width: 44px; height: 44px; border-radius: 8px; object-fit: cover;
          background: var(--secondary-background-color);
          display: inline-block;
        }
        .thumb-preview {
          display: none; position: absolute; left: 52px; top: -40px; width: 240px; height: 240px;
          object-fit: cover; border-radius: 10px; z-index: 20;
          box-shadow: 0 8px 24px rgba(0,0,0,.35); border: 1px solid var(--divider-color);
          background: var(--card-background-color, #fff);
        }
        .thumb-wrap:hover .thumb-preview { display: block; }
        .detail img { max-width: 100%; max-height: 260px; border-radius: 8px; }
        .warning {
          margin: 8px 0;
          padding: 8px;
          border-radius: 6px;
          background: var(--error-color, #db4437);
          color: #fff;
        }
        .error { color: var(--error-color); }
        .refresh-progress { margin: 10px 0; font-size: .9rem; }
        .progress-track {
          height: 8px;
          margin-top: 5px;
          border-radius: 4px;
          background: var(--divider-color);
          overflow: hidden;
        }
        .progress-fill {
          height: 100%;
          background: var(--primary-color);
          transition: width .2s ease;
        }
        .progress-track.indeterminate .progress-fill {
          width: 35% !important;
          animation: progress-slide 1.2s linear infinite;
        }
        @keyframes progress-slide {
          from { margin-left: -35%; }
          to { margin-left: 100%; }
        }
      </style>
      <ha-card class="card">
        <h2>${escapeHtml(name)}</h2>
        <p class="muted">${this.tr("localOnly")}</p>
        ${
          warning
            ? `<div class="warning">${this.tr("translation")}: ${escapeHtml(warning)}</div>`
            : ""
        }
        ${
          this._message
            ? `<p class="error">${escapeHtml(this._message)}</p>`
            : ""
        }
        ${refreshProgress}
        ${
          cooker
            ? `<div class="grid single">
                <div class="metric"><span>${this.tr("currentAction")}</span><strong>${escapeHtml(
                  this.state("current_action") || this.state("status")
                )}</strong></div>
              </div>`
            : ""
        }
        ${
          modeEntity
            ? `<div class="mode-row">
                <ha-select
                  id="mode-select"
                  label="${this.tr("cookMode")}"
                  ${!isIdle ? "disabled" : ""}
                  fixedMenuPosition
                  naturalMenuWidth
                >
                  ${modes
                    .map(
                      (m) =>
                        `<mwc-list-item value="${escapeHtml(m)}" ${
                          m === currentMode ? "selected activated" : ""
                        }>${escapeHtml(m)}</mwc-list-item>`
                    )
                    .join("")}
                </ha-select>
              </div>`
            : ""
        }
        <div class="actions">
          ${
            isIdle
              ? `<button class="primary" data-action="start-mode" ${
                  this._busy ? "disabled" : ""
                }>${this.tr("startCooking")}</button>`
              : `<button class="primary" data-action="stop" ${
                  this._busy ? "disabled" : ""
                }>${this.tr("stopCooking")}</button>`
          }
          <button data-action="refresh" ${
            this._busy || refreshInfo ? "disabled" : ""
          }>${this.tr("refreshRecipes")}</button>
        </div>
        <h3>${this.tr("recipes")}</h3>
        <div class="actions">
          <input data-query placeholder="${this.tr("searchPlaceholder")}" value="${escapeHtml(
            this._query
          )}" />
          <button class="primary" data-action="search" ${
            this._busy ? "disabled" : ""
          }>${this.tr("search")}</button>
          <button data-action="favorites" ${
            this._busy ? "disabled" : ""
          }>${this.tr("favorites")} (${this._favorites.length})</button>
        </div>
        <ul class="suggestions" data-suggestions hidden></ul>
        ${results}
        ${favorites}
        ${detail}
      </ha-card>
    `;

    this.renderSuggestions();
    const queryInput = this.shadowRoot.querySelector("[data-query]");
    queryInput?.addEventListener("focus", () => {
      this._queryFocused = true;
    });
    queryInput?.addEventListener("blur", () => {
      this._queryFocused = false;
      // Defer catch-up render so button/suggestion clicks complete first.
      setTimeout(() => {
        if (!this._queryFocused && this._stateSig !== this._renderedSig) {
          this.render();
        }
      }, 0);
    });
    queryInput?.addEventListener("input", (e) => {
      this._query = e.target.value;
      clearTimeout(this._suggestTimer);
      this._suggestTimer = setTimeout(() => this.autocomplete(), 120);
    });
    const modeSelect = this.shadowRoot.querySelector("#mode-select");
    if (modeSelect) {
      const id = this.entity("cook_mode") || this.entity("profile");
      const current = id ? this._hass?.states?.[id]?.state : null;
      const syncValue = () => {
        if (currentMode) modeSelect.value = currentMode;
      };
      syncValue();
      modeSelect.updateComplete?.then(syncValue);
      setTimeout(syncValue, 0);
      const items = modeSelect.querySelectorAll("mwc-list-item");
      items.forEach((item) => {
        item.addEventListener("click", (e) => {
          e.stopPropagation();
          const option = item.value || item.getAttribute("value");
          if (!id || !option || option === current) return;
          modeSelect.value = option;
          const selectedItem = modeSelect.querySelector("mwc-list-item[selected], mwc-list-item[activated]");
          selectedItem?.removeAttribute("selected");
          selectedItem?.removeAttribute("activated");
          item.setAttribute("selected", "");
          item.setAttribute("activated", "");
          this._hass
            .callService("select", "select_option", {
              entity_id: id,
              option,
            })
            .catch((err) => {
              this._message = err?.message || String(err);
              this.render();
            });
        });
      });
      modeSelect.addEventListener("closed", (e) => e.stopPropagation());
    }
    this.shadowRoot.querySelectorAll("[data-open]").forEach((btn) => {
      btn.addEventListener("click", () => this.open(btn.dataset.open));
    });
    this.shadowRoot.querySelectorAll("[data-remove-fav]").forEach((btn) => {
      btn.addEventListener("click", () => this.removeFavorite(btn.dataset.removeFav));
    });
    this.shadowRoot.querySelectorAll("[data-action]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const action = btn.dataset.action;
        if (action === "search") return this.search();
        if (action === "favorites") return this.showFavorites();
        if (action === "start-mode") return this.startMode();
        if (action === "stop") return this.stop();
        if (action === "refresh") return this.refresh();
        if (action === "start") return this.start();
        if (action === "favorite") return this.toggleFavorite();
        if (action === "translate") return this.translateRecipe();
        if (action === "detail-language") return this.toggleRecipeLanguage();
      });
    });
    if (restoreQueryFocus !== null) {
      const input = this.shadowRoot.querySelector("[data-query]");
      if (input) {
        input.focus();
        input.setSelectionRange(restoreQueryFocus, restoreQueryFocus);
      }
    }
  }
}

if (!customElements.get(TAG)) {
  customElements.define(TAG, ChunmiIHCookerCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === TAG)) {
  window.customCards.push({
    type: TAG,
    name: "Chunmi IH Cooker Slim",
    description:
      "Local miIO control and runnable Joyami cloud recipes for chunmi.ihcooker.slim.",
    preview: false,
  });
}
