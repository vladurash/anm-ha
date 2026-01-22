import logging
from datetime import timedelta, datetime
import async_timeout
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import unicodedata
import xml.etree.ElementTree as ET
import html
import re

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://www.meteoromania.ro/wp-json/meteoapi/v2/"

SENSOR_DEFINITIONS = [
    {
        "endpoint": "avertizari-generale",
        "name": "Avertizări Generale Meteo ANM",
        "icon": "mdi:weather-cloudy-alert",
    },
    {
        "endpoint": "avertizari-xml.php",
        "name": "Avertizări Generale Meteo ANM (XML)",
        "format": "xml",
        "full_url": "https://www.meteoromania.ro/avertizari-xml.php",
        "icon": "mdi:alert-box",
    },
    {
        "endpoint": "avertizari-nowcasting",
        "name": "Avertizări Nowcasting Meteo ANM",
        "icon": "mdi:alert",
    },
    {
        "endpoint": "starea-vremii",
        "name": "Starea Vremii Meteo ANM",
        "icon": "mdi:weather-hazy",
    },
    {
        "endpoint": "prognoza-orase",
        "name": "Prognoza Orase Meteo ANM",
        "icon": "mdi:weather-partly-cloudy",
    },
    {
        "endpoint": "avertizari-harta",
        "name": "Harta Avertizari ANM",
        "format": "xml_map",
        "full_url": "https://www.meteoromania.ro/avertizari-xml.php",
        "icon": "mdi:map-marker-alert",
    },
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    options = config_entry.options or {}
    update_interval = timedelta(seconds=options.get("update_interval", config_entry.data.get("update_interval", 10)))
    localitate = (options.get("localitate") or config_entry.data.get("localitate") or "").strip()
    judet = (options.get("judet") or config_entry.data.get("judet") or "").strip()
    judet_long = (options.get("judet_long") or config_entry.data.get("judet_long") or "").strip()

    sensors = [
        ANMSensors(
            hass,
            definition["endpoint"],
            definition["name"],
            entry_id=config_entry.entry_id,
            localitate=localitate,
            judet=judet,
            judet_long=judet_long,
            data_format=definition.get("format", "json"),
            full_url=definition.get("full_url"),
            icon=definition.get("icon"),
        )
        for definition in SENSOR_DEFINITIONS
    ]

    async_add_entities(sensors, update_before_add=True)

    async def _safe_update(sensor):
        try:
            await sensor.async_update()
        except Exception as err:
            _LOGGER.error("Eroare la actualizarea %s: %s", sensor.name, err)

    async def update_sensors(now):
        _LOGGER.info("Se execută actualizarea senzorilor ANM la intervalul setat.")
        for sensor in sensors:
            sensor.hass.async_create_task(sensor.async_update())

    async_track_time_interval(hass, update_sensors, update_interval)



class ANMSensors(Entity):
    def __init__(self, hass, endpoint, display_name, entry_id, localitate=None, judet=None, judet_long=None, data_format="json", full_url=None, icon=None):
        self._hass = hass
        self._endpoint = endpoint
        self._name = display_name
        self._entry_id = entry_id
        self._localitate = (localitate or "").strip().upper()
        self._judet = (judet or "").strip().upper()
        self._judet_long = (judet_long or "").strip().upper()
        self._data_format = data_format
        self._full_url = full_url
        self._state = None
        self._attributes = {}
        self._icon = icon or "mdi:weather-sunny-alert"
        # Home Assistant reads _attr_icon(_color) automatically
        self._attr_icon = self._icon
        self._attr_icon_color = None

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def icon(self):
        return self._icon

    @property
    def icon_color(self):
        return self._attr_icon_color

    @property
    def unique_id(self):
        return f"{self._entry_id}_{self._endpoint}"
    
    @property
    def should_poll(self) -> bool:
        return False

    def _normalize(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().upper()

    def _clean_html(self, value: str) -> str:
        if not isinstance(value, str):
            return value
        text = html.unescape(value)
        text = re.sub(r"<[^>]+>", " ", text)
        text = " ".join(text.split())
        # Corectăm separări artificiale apărute din HTML (ex: AT ENȚIONARE)
        text = re.sub(r"\bAT\s+EN([ȚȚŢT])", r"ATEN\1", text, flags=re.IGNORECASE)
        return text

    def _color_to_en(self, value: str) -> str:
        if not isinstance(value, str):
            return ""
        normalized = value.strip().lower()
        mapping = {
            "verde": "green",
            "0": "green",
            "galben": "yellow",
            "1": "yellow",
            "portocaliu": "orange",
            "2": "orange",
            "rosu": "red",
            "roșu": "red",
            "3": "red",
        }
        return mapping.get(normalized, normalized)

    def _localitate_match(self, nume: str) -> bool:
        """Potrivește numele orașului, permițând excluderi: ex. 'CONSTANTA !DIG'."""
        if not self._localitate:
            return False
        name = (nume or "").upper()
        tokens = [t.strip().upper() for t in self._localitate.split("!") if t.strip()]
        include = tokens[0] if tokens else self._localitate.upper()
        excludes = tokens[1:] if len(tokens) > 1 else []
        if include and include not in name:
            return False
        if any(ex in name for ex in excludes):
            return False
        return True


    async def async_update(self, now=None):
        url = self._full_url or f"{BASE_URL}{self._endpoint}"
        _LOGGER.debug("Actualizare date %s de la %s", self._name, url)
        try:
            async with async_timeout.timeout(5):
                session = async_get_clientsession(self._hass)
                async with session.get(url) as response:
                    if response.status != 200:
                        _LOGGER.error("Eroare HTTP %s la preluarea datelor ANM de la %s", response.status, url)
                        return

                    if self._data_format == "xml":
                        text = await response.text()
                        parsed = self._parse_data(text, is_xml=True)
                    elif self._data_format == "xml_map":
                        text = await response.text()
                        parsed = self._parse_avertizari_harta(text)
                    else:
                        data = await response.json()
                        if not data or isinstance(data, str):
                            _LOGGER.warning("Nu există date disponibile pentru %s: %s", self._name, data)
                            self._set_state_inactive()
                            return
                        parsed = self._parse_data(data)
                    if parsed:
                        state_override = parsed.pop("_state", None)
                        icon_color = parsed.pop("icon_color", None)
                        self._state = state_override if state_override is not None else "active"
                        if icon_color is not None:
                            self._attr_icon_color = icon_color
                        self._attributes = {
                            **parsed,
                            "friendly_name": self._name,
                            "icon_color": self._attr_icon_color,
                        }
                    else:
                        self._set_state_inactive()
                    if self.hass and self.entity_id:
                        self.async_write_ha_state()
                    _LOGGER.info("Senzor ANM %s actualizat cu succes.", self._name)
        except Exception as e:
            _LOGGER.error("Eroare la actualizarea datelor ANM pentru %s: %s", self._name, e)

    def _set_state_inactive(self):
        self._state = "inactive"
        self._attr_icon_color = None
        self._attributes = {
            "avertizari": "Nu exista avertizari",
            "friendly_name": self._name,
        }

    def _parse_data(self, data, is_xml=False):
        if is_xml:
            return self._parse_avertizari_generale_xml(data)
        if self._endpoint == "avertizari-generale":
            return self._parse_avertizari_generale(data)
        if self._endpoint == "avertizari-nowcasting":
            return self._parse_avertizari_nowcasting(data)

        if self._endpoint == "starea-vremii":
            return self._parse_starea_vremii(data)
        if self._endpoint == "prognoza-orase":
            return self._parse_prognoza_orase(data)

    def _parse_avertizari_generale(self, data):
        avertizare = data.get("avertizare")
        if isinstance(avertizare, dict):
            avertizare = [avertizare]

        rezultate = []
        match = None

        if isinstance(avertizare, list):
            for item in avertizare:
                if not isinstance(item, dict):
                    continue
                a_attrs = item.get("@attributes", {}) or {}
                judete = item.get("judet", [])
                if isinstance(judete, dict):
                    judete = [judete]

                for judet in judete:
                    if not isinstance(judet, dict):
                        continue
                    j_attrs = judet.get("@attributes", {}) or {}
                    cod = (j_attrs.get("cod") or "").upper()
                    entry = {
                        "judet": cod,
                        "culoare": j_attrs.get("culoare"),
                        "use_coord_gis": j_attrs.get("useCoordGis"),
                        "coord_gis": j_attrs.get("coordGis"),
                        "fenomene_vizate": a_attrs.get("fenomeneVizate"),
                        "data_expirarii": a_attrs.get("dataExpirarii"),
                        "data_aparitiei": a_attrs.get("dataAparitiei"),
                        "intervalul": a_attrs.get("intervalul"),
                        "mesaj": a_attrs.get("zonaAfectata"),
                        "tip_mesaj": a_attrs.get("numeTipMesaj") or a_attrs.get("tipMesaj"),
                        "culoare_generala": a_attrs.get("culoare"),
                    }
                    rezultate.append(entry)
                    if self._judet and cod == self._judet:
                        match = entry

        timestamp = datetime.utcnow().isoformat()
        if self._judet:
            return {"avertizari": [match]} if match else {}
        return {}

    def _parse_avertizari_generale_xml(self, text):
        """Parsează XML-ul care poate conține mai multe <avertizare>.

        Returnăm toate avertizările în ordine (așa cum vin în feed) și
        includem mesajul aferent fiecărui set de județe. Dacă este filtrat
        după județ, păstrăm doar intrările care îl conțin.
        """
        try:
            root = ET.fromstring(text)
        except ET.ParseError as err:
            _LOGGER.error("Eroare la parsarea XML: %s", err)
            return {}

        avertizari = []
        filtered = []

        for avertizare in root.findall("avertizare"):
            a_attrs = avertizare.attrib or {}
            judete = avertizare.findall("judet") or []
            zone = avertizare.findall("zona") or []
            judete_entries = []

            for judet in judete:
                j_attrs = judet.attrib or {}
                cod = (j_attrs.get("cod") or "").upper()
                culoare = (j_attrs.get("culoare") or "").strip()
                if not culoare or culoare == "0":
                    continue

                zone_match = []
                for z in zone:
                    if not isinstance(z, ET.Element):
                        continue
                    z_attrs = z.attrib or {}
                    z_cod = (z_attrs.get("cod") or "").upper()
                    if z_cod and (z_cod.startswith(f"{cod}_") or z_cod == cod):
                        z_culoare = (z_attrs.get("culoare") or "").strip()
                        zone_match.append({
                            "cod": z_cod,
                            "culoare": z_culoare,
                        })

                entry = {
                    "judet": cod,
                    "culoare": culoare,
                    "fenomene_vizate": a_attrs.get("fenomeneVizate"),
                    "data_expirarii": a_attrs.get("dataExpirarii"),
                    "data_aparitiei": a_attrs.get("dataAparitiei"),
                    "intervalul": a_attrs.get("intervalul"),
                    "mesaj": self._clean_html(a_attrs.get("mesaj")),
                    "zona_afectata": self._clean_html(a_attrs.get("zonaAfectata")),
                    "tip_mesaj": a_attrs.get("numeTipMesaj") or a_attrs.get("tipMesaj"),
                    "zone": zone_match or None,
                }
                judete_entries.append(entry)

            alert_entry = {
                "meta": {
                    "tip_mesaj": a_attrs.get("numeTipMesaj") or a_attrs.get("tipMesaj"),
                    "data_aparitiei": a_attrs.get("dataAparitiei"),
                    "data_expirarii": a_attrs.get("dataExpirarii"),
                    "fenomene_vizate": a_attrs.get("fenomeneVizate"),
                    "mesaj": self._clean_html(a_attrs.get("mesaj")),
                    "culoare": a_attrs.get("culoare"),
                },
                "judete": judete_entries,
            }
            avertizari.append(alert_entry)

            if self._judet:
                judet_matches = [j for j in judete_entries if j.get("judet") == self._judet]
                if judet_matches:
                    filtered.append({**alert_entry, "judete": judet_matches})

        timestamp = datetime.utcnow().isoformat().replace("T", " ")
        if self._judet:
            if not filtered:
                return {}
            return {"avertizari": filtered, "_state": timestamp}
        return {"avertizari": avertizari, "_state": timestamp}

    def _parse_avertizari_harta(self, text):
        """Parsează toate hărțile din XML.

        Pentru fiecare <avertizare> întoarcem lista de zone/județe și mesajul,
        astfel încât UI-ul să poată afișa cronologic fiecare hartă colorată.
        """
        try:
            root = ET.fromstring(text)
        except ET.ParseError as err:
            _LOGGER.error("Eroare la parsarea XML harta: %s", err)
            return {}

        maps = []
        for avertizare in root.findall("avertizare"):
            a_attrs = avertizare.attrib or {}
            shapes = []
            for elem in list(avertizare):
                if elem.tag not in ("judet", "zona"):
                    continue
                attrs = elem.attrib or {}
                cod = (attrs.get("cod") or "").upper().replace("-", "_")
                culoare = (attrs.get("culoare") or "").strip()
                if not culoare or culoare == "0":
                    continue
                color_name = {"1": "yellow", "2": "orange", "3": "red"}.get(culoare, "green")
                shapes.append({
                    "id": cod,
                    "color": color_name,
                    "culoare": culoare,
                })
            if shapes:
                maps.append({
                    "meta": {
                        "tip_mesaj": a_attrs.get("numeTipMesaj") or a_attrs.get("tipMesaj"),
                        "data_aparitiei": a_attrs.get("dataAparitiei"),
                        "data_expirarii": a_attrs.get("dataExpirarii"),
                        "mesaj": self._clean_html(a_attrs.get("mesaj")),
                    },
                    "shapes": shapes,
                })

        if maps:
            ts = datetime.utcnow().isoformat().replace("T", " ")
            # păstrăm shapes pentru compatibilitate (prima hartă)
            first_shapes = maps[0].get("shapes") if maps else None
            payload = {"maps": maps, "_state": ts}
            if first_shapes:
                payload["shapes"] = first_shapes
            return payload
        return {}



    def _parse_starea_vremii(self, data):
        starea_vremii = data.get("features")
        if isinstance(starea_vremii, list):
            attrs = []
            oras_selectat = None
            for feature in starea_vremii:
                properties = feature.get("properties", {})
                entry = {
                    "nume": properties.get("nume"),
                    "temperatura": properties.get("tempe"),
                    "umiditate": properties.get("umezeala"),
                    "presiune": properties.get("presiunetext"),
                    "nebulozitate": properties.get("nebulozitate"),
                    "fenomene": properties.get("fenomen_e"),
                    "zapada": properties.get("zapada"),
                    "tempapa": properties.get("tempapa"),
                    "vant": properties.get("vant"),
                    "last_update": properties.get("actualizat").replace("&nbsp;", " "),
                }
                attrs.append(entry)

                nume = properties.get("nume")
                if self._localitate and isinstance(nume, str) and self._localitate_match(nume):
                    oras_selectat = entry
            timestamp = datetime.utcnow().isoformat()
            if oras_selectat:
                return {
                    "oras_selectat": oras_selectat,
                    "_state": timestamp.replace("T", " "),
                }
            # No match means no state update
            return {}
            
        return {}
        
    def _parse_prognoza_orase(self, data):
        tara = data.get("tara", {})
        localitati = tara.get("localitate", [])

        if isinstance(localitati, dict):
            localitati = [localitati]

        rezultate = []
        localitate_selectata = None

        if isinstance(localitati, list):
            for loc in localitati:
                if not isinstance(loc, dict):
                    continue
                attrs = loc.get("@attributes", {}) or {}
                nume_loc = attrs.get("nume")
                prognoze = loc.get("prognoza", [])
                if isinstance(prognoze, dict):
                    prognoze = [prognoze]

                zile = []
                for prog in prognoze:
                    if not isinstance(prog, dict):
                        continue
                    prog_attrs = prog.get("@attributes", {}) or {}
                    zile.append({
                        "data": prog_attrs.get("data"),
                        "temp_min": prog.get("temp_min"),
                        "temp_max": prog.get("temp_max"),
                        "fenomen_descriere": prog.get("fenomen_descriere"),
                        "fenomen_simbol": prog.get("fenomen_simbol"),
                    })

                entry = {
                    "nume": nume_loc,
                    "data_prognozei": loc.get("DataPrognozei"),
                    "prognoza": zile,
                }
                rezultate.append(entry)

                if self._localitate and isinstance(nume_loc, str) and self._localitate in nume_loc.upper():
                    localitate_selectata = entry

        timestamp = datetime.utcnow().isoformat()
        if localitate_selectata:
            return {
                "prognoza_oras": localitate_selectata,
                "_state": timestamp.replace("T", " "),
            }
        # if rezultate:
        #     return {
        #         "prognoza_orase": rezultate,
        #         "_state": timestamp,
        #     }
        return {}

    def _parse_avertizari_nowcasting(self, data):
        avertizare = data.get("avertizare")
        zona_selectata = None

        # Normalizăm la listă pentru a acoperi și cazul dict
        if isinstance(avertizare, dict):
            avertizare = [avertizare]
        if not isinstance(avertizare, list):
            return {}

        rezultate = []
        for item in avertizare:
            if not isinstance(item, dict):
                continue
            attrs = item.get("@attributes", {}) or {}
            zona = attrs.get("zona") or ""
            color_en = self._color_to_en(attrs.get("numeCuloare") or attrs.get("culoare") or "")
            
            entry = {
                "tip_mesaj": attrs.get("numeTipMesaj") or attrs.get("tipMesaj"),
                "data_inceput": attrs.get("dataInceput"),
                "data_sfarsit": attrs.get("dataSfarsit"),
                "zona": attrs.get("zona"),
                "semnalare": attrs.get("semnalare"),
                "culoare": attrs.get("numeCuloare") or attrs.get("culoare"),
                "culoare_en": color_en,
                "modificat": attrs.get("modificat"),
                "creat": attrs.get("creat"),
                "icon_color": color_en,
            }
            rezultate.append(entry)

            if self._judet_long and self._normalize(self._judet_long) in self._normalize(zona):
                zona_selectata = entry

        timestamp = datetime.utcnow().isoformat()
        if zona_selectata:
            _LOGGER.debug("Print zona selectata nowcasting: %s", zona_selectata)
            icon_color = zona_selectata.get("icon_color") or self._color_to_en(zona_selectata.get("culoare") or "")
            return {
                "avertizare_zona": zona_selectata,
                "_state": zona_selectata.get("semnalare") or "active",
                "icon_color": icon_color,
            }
        # Dacă nu este match, marcăm explicit inactiv.
        return {"_state": "inactive"}
