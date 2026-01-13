DOMAIN = "meteo_anm"


async def async_setup_entry(hass, config_entry):
    await _ensure_assets(hass)
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


async def _ensure_assets(hass):
    """Copy bundled frontend assets (svg + card) into /config/www/ if missing."""
    import os
    import shutil

    src_dir = os.path.dirname(__file__)
    www_dir = hass.config.path("www")
    assets = {
        "anm-harta.svg": "anm-harta.svg",
        "anm-map-card.js": "anm-map-card.js",
    }

    def _copy():
        os.makedirs(www_dir, exist_ok=True)
        for src_name, dest_name in assets.items():
            src_path = os.path.join(src_dir, src_name)
            dest_path = os.path.join(www_dir, dest_name)
            if os.path.exists(src_path) and not os.path.exists(dest_path):
                shutil.copyfile(src_path, dest_path)

    await hass.async_add_executor_job(_copy)
