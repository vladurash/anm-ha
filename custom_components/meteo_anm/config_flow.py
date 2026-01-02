import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

class AlertaANMConfigFlow(config_entries.ConfigFlow, domain="meteo_anm"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Validăm datele introduse
            update_interval = user_input.get("update_interval")
            judet = (user_input.get("judet") or "").strip().upper()
            localitate = user_input.get("localitate")
            judet_long = user_input.get("judet_long")
            if update_interval and update_interval >= 60 and judet:
                cleaned_input = {**user_input, "judet": judet}
                return self.async_create_entry(title="Prognoza Meteo si Avertizari by ANM", data=cleaned_input)
            errors["base"] = "invalid_interval" if not update_interval or update_interval < 60 else "invalid_judet"

        # Formulăm schema de configurare
        schema = vol.Schema({
            vol.Required("update_interval", default=180): vol.All(cv.positive_int, vol.Range(min=60)),  # secunde (>=60)
            vol.Required("localitate", default="Bucuresti"): cv.string,
            vol.Required("judet", default="B"): vol.All(cv.string, vol.Length(min=1, max=2)),
            vol.Required("judet_long", default="Bucuresti"): cv.string,
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AlertaANMOptionsFlowHandler(config_entry)

class AlertaANMOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema({
            vol.Required("update_interval", default=self._config_entry.options.get("update_interval", self._config_entry.data.get("update_interval", 180))): vol.All(cv.positive_int, vol.Range(min=60)),  # secunde (>=60)
            vol.Required("localitate", default=self._config_entry.options.get("localitate", self._config_entry.data.get("localitate", "Bucuresti"))): cv.string,
            vol.Required("judet", default=self._config_entry.options.get("judet", self._config_entry.data.get("judet", "B"))): vol.All(cv.string, vol.Length(min=1, max=2)),
            vol.Required("judet_long", default=self._config_entry.options.get("judet_long", self._config_entry.data.get("judet_long", "Bucuresti"))): cv.string,
        })

        return self.async_show_form(step_id="user", data_schema=schema)
