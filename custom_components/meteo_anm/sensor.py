import logging
from datetime import timedelta, datetime
import async_timeout
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import unicodedata

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://www.meteoromania.ro/wp-json/meteoapi/v2/"

SENSOR_DEFINITIONS = [
    {
        "endpoint": "avertizari-generale",
        "name": "Avertizări Generale Meteo ANM",
    },
    {
        "endpoint": "avertizari-nowcasting",
        "name": "Avertizări Nowcasting Meteo ANM",
    },
    {
        "endpoint": "starea-vremii",
        "name": "Starea Vremii Meteo ANM",
    },
    {
        "endpoint": "prognoza-orase",
        "name": "Prognoza Orase Meteo ANM",
    },
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    options = config_entry.options or {}
    update_interval = timedelta(seconds=options.get("update_interval", config_entry.data.get("update_interval", 10)))
    localitate = (options.get("localitate") or config_entry.data.get("localitate") or "").strip()
    judet = (options.get("judet") or config_entry.data.get("judet") or "").strip()
    judet_long = (options.get("judet_long") or config_entry.data.get("judet_long") or "").strip()

    sensors = [
        ANMAlertSensor(
            hass,
            definition["endpoint"],
            definition["name"],
            entry_id=config_entry.entry_id,
            localitate=localitate,
            judet=judet,
            judet_long=judet_long,
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
        # for sensor in sensors:
        #     await sensor.async_update()
        for sensor in sensors:
            sensor.hass.async_create_task(sensor.async_update())

    async_track_time_interval(hass, update_sensors, update_interval)


class ANMAlertSensor(Entity):
    def __init__(self, hass, endpoint, display_name, entry_id, localitate=None, judet=None, judet_long=None):
        self._hass = hass
        self._endpoint = endpoint
        self._name = display_name
        self._entry_id = entry_id
        self._localitate = (localitate or "").strip().upper()
        self._judet = (judet or "").strip().upper()
        self._judet_long = (judet_long or "").strip().upper()
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



    async def async_update(self, now=None):
        url = f"{BASE_URL}{self._endpoint}"
        _LOGGER.debug("Actualizare date %s de la %s", self._name, url)
        try:
            async with async_timeout.timeout(5):
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
                    if self.hass and self.entity_id:
                        self.async_write_ha_state()
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

    # def _parse_avertizari_generale(self, data):
    #     toate_avertizarile = []

    #     avertizare = data.get("avertizare", None)
    #     if isinstance(avertizare, dict):
    #         avertizare = [avertizare]

    #     if isinstance(avertizare, list):
    #         for avertizare_item in avertizare:
    #             if isinstance(avertizare_item, dict):
    #                 for judet in avertizare_item.get("judet", []):
    #                     if isinstance(judet, dict):
    #                         try:
    #                             avertizare_judet = {
    #                                 "judet": judet.get("@attributes", {}).get("cod", "necunoscut"),
    #                                 "culoare": judet.get("@attributes", {}).get("culoare", "necunoscut"),
    #                                 "fenomene_vizate": avertizare_item.get("@attributes", {}).get("fenomeneVizate", "necunoscut"),
    #                                 "data_expirarii": avertizare_item.get("@attributes", {}).get("dataExpirarii", "necunoscut"),
    #                                 "data_aparitiei": avertizare_item.get("@attributes", {}).get("dataAparitiei", "necunoscut"),
    #                                 "intervalul": avertizare_item.get("@attributes", {}).get("intervalul", "necunoscut"),
    #                                 "mesaj": avertizare_item.get("@attributes", {}).get("mesaj", "necunoscut"),
    #                             }
    #                             toate_avertizarile.append(avertizare_judet)
    #                         except KeyError as e:
    #                             _LOGGER.error("Eroare la procesarea datelor pentru județ: %s", e)
    #                     else:
    #                         _LOGGER.error("Judete nu este un dicționar, s-a primit: %s", type(judet))
    #             else:
    #                 _LOGGER.error("Avertizare nu este un dicționar, s-a primit: %s", type(avertizare_item))
    #     else:
    #         _LOGGER.error("Avertizare nu este un dicționar sau o listă validă, s-a primit: %s", type(avertizare))

    #     if toate_avertizarile:
    #         return {"avertizari": toate_avertizarile}
    #     return {}

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
                if self._localitate and isinstance(nume, str) and self._localitate in nume.upper():
                    oras_selectat = entry
            timestamp = datetime.utcnow().isoformat()
            if oras_selectat:
                return {
                    "oras_selectat": oras_selectat,
                    "_state": timestamp.replace("T", " "),
                }
            # No match means no state update
            return {}
            # No match, return list without raw features to keep attributes small
            # return {
            #     "starea_vremii": attrs,
            #     "_state": datetime.utcnow().isoformat(),
            # }
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
        rezultate = []

        if isinstance(avertizare, dict):
            attrs = avertizare.get("@attributes", {}) or {}
            zona = attrs.get("zona") or ""
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
            
            rezultate.append(entry)

            if self._judet_long:
                if self._normalize(self._judet_long) in self._normalize(zona):
                    zona_selectata = entry
                else:
                    rezultate = []  # force no match
            

        timestamp = datetime.utcnow().isoformat()
        if zona_selectata:
            return {
                "avertizare_zona": zona_selectata,
                "_state": "active",
            }
        else:
            return {}
