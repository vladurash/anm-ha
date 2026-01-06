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
      this._svgPromise = fetch("https://www.meteoromania.ro/wp-content/plugins/meteo/harti/harta.svg.php?id_avertizare=1")
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
      if (!svg) return;
      const clone = svg.cloneNode(true);
      const colors = { yellow: "#f2c744", orange: "#f28c28", red: "#d32f2f" };
      (stateObj.attributes.shapes || []).forEach(shape => {
        const el = clone.getElementById(shape.id);
        if (el) {
          const fill = colors[shape.color] || "#cccccc";
          el.setAttribute("fill", fill);
          el.setAttribute("style", `fill:${fill};stroke:#333;stroke-width:1`);
        }
      });
      // Render
      this._container.innerHTML = "";
      this._container.appendChild(clone);
    });
  }

  getCardSize() { return 4; }
}
customElements.define("anm-map-card", AnmMapCard);
