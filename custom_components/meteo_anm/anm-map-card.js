class AnmMapCard extends HTMLElement {
  static getConfigElement() { return null; }
  static getStubConfig() { return { entity: "sensor.harta_avertizari_anm" }; }

  setConfig(config) {
    if (!config.entity) throw new Error("entity required");
    this.config = config;
    this._mapIndex = 0;
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `<style>:host{display:block} .holder{width:100%;height:auto} .nav{display:flex;align-items:center;margin-top:6px;gap:6px} .nav button{padding:2px 6px;border:1px solid #888;border-radius:4px;background:#f5f5f5;cursor:pointer} .nav button:disabled{opacity:0.5;cursor:default} .meta{margin-top:8px;font-size:14px;line-height:1.4}</style><div class="holder"></div>`;
    this._container = this.shadowRoot.querySelector(".holder");
    if (!this._svgPromise) {
      const MAP_URL = "/local/anm-harta.svg";
      this._svgPromise = fetch(MAP_URL)
        .then(r => r.text())
        .then(txt => new DOMParser().parseFromString(txt, "image/svg+xml").documentElement)
        .catch(err => { console.error("ANM map fetch failed", err); return null; });
    }
  }

  _renderFromState() {
    if (!this._svgEl || !this._stateCache) return;
    const { maps, shapesFallback, metaFallback } = this._stateCache;

    const mapCount = maps.length;
    if (mapCount && this._mapIndex >= mapCount) this._mapIndex = 0;
    const current = mapCount ? maps[this._mapIndex] : null;
    const shapes = current ? (current.shapes || []) : (shapesFallback || []);
    const meta = current ? current.meta : metaFallback;

    const clone = this._svgEl.cloneNode(true);
    const codClasses = ["cod0", "cod1", "cod2", "cod3"];
    const setCodClass = (el, codClass) => {
      codClasses.forEach(c => el.classList.remove(c));
      el.classList.add(codClass);
    };

    // Reset to cod0 (green) for all shapes
    clone.querySelectorAll("[data-judet], [data-munte], path.judet, polygon.judet, path.munte, polygon.munte").forEach(el => {
      setCodClass(el, "cod0");
    });

    // Apply alert colors
    (shapes || []).forEach(shape => {
      const raw = (shape.id || "").toUpperCase();
      const candidates = [raw, raw.toLowerCase()];
      const codClass = { "1": "cod1", "2": "cod2", "3": "cod3" }[shape.culoare] || "cod1";
      const matches = Array.from(clone.querySelectorAll("[data-judet],[data-munte],[id],[class]")).filter(el => {
        const attrs = [
          el.getAttribute("data-judet"),
          el.getAttribute("data-munte"),
          el.id,
          ...(el.className || "").toString().split(/\s+/)
        ].filter(Boolean).map(v => v.toUpperCase());
        return attrs.some(v => candidates.some(c => v.endsWith(c.toUpperCase())));
      });
      matches.forEach(el => setCodClass(el, codClass));
    });

    // Build UI
    const wrapper = document.createElement("div");
    wrapper.appendChild(clone);

    if (meta || mapCount > 0) {
      const info = document.createElement("div");
      info.className = "meta";
      if (meta) {
        info.innerHTML = `
          <div><strong>${meta.tip_mesaj || ""}</strong></div>
          <div>${meta.mesaj || ""}</div>
          <div>${meta.data_aparitiei || ""} - ${meta.data_expirarii || ""}</div>
        `;
      }
      if (mapCount > 0) {
        const nav = document.createElement("div");
        nav.className = "nav";
        const prev = document.createElement("button");
        prev.textContent = "<";
        const next = document.createElement("button");
        next.textContent = ">";
        const label = document.createElement("span");
        label.textContent = `Harta ${this._mapIndex + 1} / ${mapCount}`;
        prev.disabled = mapCount <= 1;
        next.disabled = mapCount <= 1;
        prev.onclick = () => { if (mapCount > 1) { this._mapIndex = (this._mapIndex - 1 + mapCount) % mapCount; this._renderFromState(); } };
        next.onclick = () => { if (mapCount > 1) { this._mapIndex = (this._mapIndex + 1) % mapCount; this._renderFromState(); } };
        nav.appendChild(prev);
        nav.appendChild(label);
        nav.appendChild(next);
        info.appendChild(nav);
      }
      wrapper.appendChild(info);
    }

    this._container.innerHTML = "";
    this._container.appendChild(wrapper);
  }

  set hass(hass) {
    this._hass = hass;
    if (!this.config || !this._svgPromise) return;
    const stateObj = hass.states[this.config.entity];
    if (!stateObj) return;
    const attrs = stateObj.attributes || {};
    const rawMaps = attrs.maps;
    const maps = Array.isArray(rawMaps) ? rawMaps : (rawMaps ? Object.values(rawMaps) : []);
    if (!attrs.shapes && !maps.length) return;
    this._svgPromise.then(svg => {
      if (!svg) return console.error("ANM map SVG not loaded");
      this._svgEl = svg;
      this._stateCache = {
        maps,
        shapesFallback: attrs.shapes || [],
        metaFallback: attrs.meta || null,
      };
      this._renderFromState();
    });
  }

  getCardSize() { return 4; }
}

customElements.define("anm-map-card", AnmMapCard);
