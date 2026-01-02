DOMAIN = "alerta_anm"


async def async_setup_entry(hass, config_entry):
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = config_entry.add_update_listener(async_reload_entry)

    await hass.config_entries.async_forward_entry_setups(config_entry, ["sensor"])
    return True


async def async_unload_entry(hass, config_entry):
    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, ["sensor"])

    unsub = hass.data.get(DOMAIN, {}).pop(config_entry.entry_id, None)
    if unsub:
        unsub()
    if not hass.data.get(DOMAIN):
        hass.data.pop(DOMAIN, None)

    return unload_ok

async def async_setup(hass, config):
    return True


async def async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)
