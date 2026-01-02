import logging
from datetime import timedelta, datetime
import async_timeout
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://www.meteoromania.ro/wp-json/meteoapi/v2/"

SENSOR_DEFINITIONS = [
    {
        "endpoint": "avertizari-generale",
        "name": "Avertizări Meteo ANM",
    },
    {
        "endpoint": "avertizari-nowcasting",
        "name": "Avertizări Nowcasting Meteo ANM",
    },
    {
        "endpoint": "starea-vremii",
        "name": "Starea Vremii ANM",
    },
    {
        "endpoint": "prognoza-orase",
        "name": "Prognoza Orase Meteo ANM",
    },
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    options = config_entry.options or {}
    update_interval = timedelta(minutes=options.get("update_interval", config_entry.data.get("update_interval", 10)))
    localitate = (options.get("localitate") or config_entry.data.get("localitate") or "").strip()
    judet = (options.get("judet") or config_entry.data.get("judet") or "").strip()

    sensors = [
        ANMAlertSensor(
            hass,
            definition["endpoint"],
            definition["name"],
            localitate=localitate,
            judet=judet,
        )
        for definition in SENSOR_DEFINITIONS
    ]

    async_add_entities(sensors)

    async def update_sensors(now):
        _LOGGER.debug("Se execută actualizarea senzorilor ANM la intervalul setat.")
        for sensor in sensors:
            await sensor.async_update()

    async_track_time_interval(hass, update_sensors, update_interval)


class ANMAlertSensor(Entity):
    def __init__(self, hass, endpoint, display_name, localitate=None, judet=None):
        self._hass = hass
        self._endpoint = endpoint
        self._name = display_name
        self._localitate = (localitate or "").strip().upper()
        self._judet = (judet or "").strip().upper()
        self._state = None
        self._attributes = {}

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
        return "mdi:weather-lightning-rainy"

    async def async_update(self, now=None):
        url = f"{BASE_URL}{self._endpoint}"
        _LOGGER.debug("Actualizare date %s de la %s", self._name, url)
        try:
            async with async_timeout.timeout(10):
                session = async_get_clientsession(self._hass)
                async with session.get(url) as response:
                    if response.status != 200:
                        _LOGGER.error("Eroare HTTP %s la preluarea datelor ANM de la %s", response.status, url)
                        return

                    data = await response.json()
                    if not data or isinstance(data, str):
                        _LOGGER.warning("Nu există date disponibile pentru %s: %s", self._name, data)
                        self._set_state_inactive()
                        return

                    parsed = self._parse_data(data)
                    if parsed:
                        state_override = parsed.pop("_state", None)
                        self._state = state_override if state_override is not None else "active"
                        self._attributes = {
                            **parsed,
                            "friendly_name": self._name,
                        }
                    else:
                        self._set_state_inactive()
                    _LOGGER.info("Senzor ANM %s actualizat cu succes.", self._name)
        except Exception as e:
            _LOGGER.error("Eroare la actualizarea datelor ANM pentru %s: %s", self._name, e)

    def _set_state_inactive(self):
        self._state = "inactive"
        self._attributes = {
            "avertizari": "Nu exista avertizari",
            "friendly_name": self._name,
        }

    def _parse_data(self, data):
        if self._endpoint == "avertizari-generale":
            return self._parse_avertizari_generale(data)
        if self._endpoint == "avertizari-nowcasting":
            return self._parse_avertizari_nowcasting(data)

        if self._endpoint == "starea-vremii":
            return self._parse_starea_vremii(data)
        if self._endpoint == "prognoza-orase":
            return self._parse_prognoza_orase(data)

        # Fallback: return raw data for unknown endpoints
        return {"avertizari": data}

    def _parse_avertizari_generale(self, data):
        toate_avertizarile = []

        avertizare = data.get("avertizare", None)
        if isinstance(avertizare, dict):
            avertizare = [avertizare]

        if isinstance(avertizare, list):
            for avertizare_item in avertizare:
                if isinstance(avertizare_item, dict):
                    for judet in avertizare_item.get("judet", []):
                        if isinstance(judet, dict):
                            try:
                                avertizare_judet = {
                                    "judet": judet.get("@attributes", {}).get("cod", "necunoscut"),
                                    "culoare": judet.get("@attributes", {}).get("culoare", "necunoscut"),
                                    "fenomene_vizate": avertizare_item.get("@attributes", {}).get("fenomeneVizate", "necunoscut"),
                                    "data_expirarii": avertizare_item.get("@attributes", {}).get("dataExpirarii", "necunoscut"),
                                    "data_aparitiei": avertizare_item.get("@attributes", {}).get("dataAparitiei", "necunoscut"),
                                    "intervalul": avertizare_item.get("@attributes", {}).get("intervalul", "necunoscut"),
                                    "mesaj": avertizare_item.get("@attributes", {}).get("mesaj", "necunoscut"),
                                }
                                toate_avertizarile.append(avertizare_judet)
                            except KeyError as e:
                                _LOGGER.error("Eroare la procesarea datelor pentru județ: %s", e)
                        else:
                            _LOGGER.error("Judete nu este un dicționar, s-a primit: %s", type(judet))
                else:
                    _LOGGER.error("Avertizare nu este un dicționar, s-a primit: %s", type(avertizare_item))
        else:
            _LOGGER.error("Avertizare nu este un dicționar sau o listă validă, s-a primit: %s", type(avertizare))

        if toate_avertizarile:
            return {"avertizari": toate_avertizarile}
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
                }
                attrs.append(entry)

                nume = properties.get("nume")
                if self._localitate and isinstance(nume, str) and self._localitate in nume.upper():
                    oras_selectat = entry
            if oras_selectat:
                return {
                    "oras_selectat": oras_selectat,
                    "_state": datetime.utcnow().isoformat(),
                }
            # No match, return list without raw features to keep attributes small
            return {
                "starea_vremii": attrs,
                "_state": datetime.utcnow().isoformat(),
            }
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
                "_state": timestamp,
            }
        if rezultate:
            return {
                "prognoza_orase": rezultate,
                "_state": timestamp,
            }
        return {}

    def _parse_avertizari_nowcasting(self, data):
        avertizare = data.get("avertizare")
        if isinstance(avertizare, dict):
            attrs = avertizare.get("@attributes", {}) or {}
            entry = {
                "tip_mesaj": attrs.get("numeTipMesaj") or attrs.get("tipMesaj"),
                "data_inceput": attrs.get("dataInceput"),
                "data_sfarsit": attrs.get("dataSfarsit"),
                "zona": attrs.get("zona"),
                "semnalare": attrs.get("semnalare"),
                "culoare": attrs.get("numeCuloare") or attrs.get("culoare"),
                "modificat": attrs.get("modificat"),
                "creat": attrs.get("creat"),
            }
            # Drop empty keys to keep attributes concise
            entry = {k: v for k, v in entry.items() if v is not None}
            if entry:
                return {"avertizari": [entry]}

        return {}
