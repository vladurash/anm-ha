class AnmMapCard extends HTMLElement {
  static getConfigElement() { return null; }
  static getStubConfig() { return { entity: "sensor.harta_avertizari_anm" }; }

  setConfig(config) {
    if (!config.entity) throw new Error("entity required");
    this.config = config;
    this._svg = null;
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `<style>:host{display:block} .holder{width:100%;height:auto}</style><div class="holder"></div>`;
    this._container = this.shadowRoot.querySelector(".holder");
    if (!this._svgPromise) {
    //   const MAP_URL = "https://images.weserv.nl/?output=svg&url=www.meteoromania.ro/wp-content/plugins/meteo/harti/harta.svg.php%3Fid_avertizare%3D1";
      const MAP_URL = "/local/anm-harta.svg";

      this._svgPromise = fetch(MAP_URL)
        .then(r => r.text())
        .then(txt => new DOMParser().parseFromString(txt, "image/svg+xml").documentElement)
        .catch(err => { console.error("ANM map fetch failed", err); return null; });
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this.config || !this._svgPromise) return;
    const stateObj = hass.states[this.config.entity];
    if (!stateObj || !stateObj.attributes.shapes) return;
    this._svgPromise.then(svg => {
        if (!svg) return console.error("ANM map SVG not loaded");
        
        const clone = svg.cloneNode(true);
        
        // const defaultFill = "#08ec49";
        const codClasses = ["cod0","cod1","cod2","cod3"];

        const setCodClass = (el, codClass) => {
          codClasses.forEach(c => el.classList.remove(c));
          el.classList.add(codClass);
        };

        // Default paint
        clone.querySelectorAll("[data-judet], [data-munte], path.judet, polygon.judet").forEach(el => {
        //   codClasses.forEach(c => el.classList.remove(c));
        //   el.removeAttribute("style");
        //   el.setAttribute("fill", defaultFill);
        //   el.classList.add("cod0");
        setCodClass(el, "cod0");
        });

        // Apply alerts
(stateObj.attributes.shapes || []).forEach(shape => {
  const raw = (shape.id || "").toUpperCase();
//   const parts = raw.split("_");
//   const overlay = parts.length >= 2 ? `${parts[0]}_${parts[1]}` : null;
  const candidates = [raw, raw.toLowerCase()];
//   if (overlay) candidates.push(overlay, overlay.toLowerCase());
//   if (parts.length === 1) candidates.push(parts[0], parts[0].toLowerCase());

  const codClass = {"1":"cod1","2":"cod2","3":"cod3"}[shape.culoare] || "cod1";
  const matches = Array.from(clone.querySelectorAll("[data-judet],[data-munte],[id],[class]")).filter(el => {
    const attrs = [
      el.getAttribute("data-judet"),
      el.getAttribute("data-munte"),
      el.id,
      ...(el.className || "").toString().split(/\s+/)
    ].filter(Boolean).map(v => v.toUpperCase());
    return attrs.some(v => candidates.some(c => v.endsWith(c.toUpperCase())));
  });

//   console.log(`Matched ${matches.length} elements for ${raw}`);
  matches.forEach(el => {
    codClasses.forEach(c => el.classList.remove(c));
    setCodClass(el, codClass);
  });
});



      // Render
      this._container.innerHTML = "";
      this._container.appendChild(clone);
    });
  }

  getCardSize() { return 4; }
}
customElements.define("anm-map-card", AnmMapCard);
