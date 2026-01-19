from .static_config import JUDETE

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

async def async_migrate_entry(hass, config_entry):
    """Migrare automată: adaugă judet_long și corectează titlul la upgrade."""
    version = config_entry.version
    if version >= 2:
        return True

    data = dict(config_entry.data)
    options = dict(config_entry.options)

    judet = (options.get("judet") or data.get("judet") or "").strip().upper()
    judet_long = JUDETE.get(judet, judet)
    title = config_entry.title

    if judet:
        if "judet_long" not in data:
            data["judet_long"] = judet_long
        if options and "judet_long" not in options:
            options["judet_long"] = judet_long
        title = f"Prognoza Meteo si Avertizari by ANM - {judet_long} / {judet}"

    hass.config_entries.async_update_entry(
        config_entry,
        title=title,
        data=data,
        options=options,
        version=2,
    )
    return True


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
            shutil.copyfile(src_path, dest_path)

    await hass.async_add_executor_job(_copy)
