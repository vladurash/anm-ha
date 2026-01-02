# Prognoza Meteo si Avertizari by ANM (Home Assistant)

### Cod sursa original https://github.com/aurelmarius/alerta-anm-ha


Integrarea foloseste API-ul ANM (`https://www.meteoromania.ro/wp-json/meteoapi/v2/`) si expune mai multi senzori:
- `sensor.avertizari_meteo_anm` – avertizari generale pe judet.
- `sensor.avertizari_nowcasting_meteo_anm` – avertizari nowcasting.
- `sensor.starea_vremii_meteo_anm` – stare curenta pe localitate (atribut filtrat dupa localitatea configurata).
- `sensor.prognoza_orase_meteo_anm` – prognoza pe 5 zile pentru localitatea configurata (sau toate, ca fallback).

Valoarea senzorilor este un timestamp al ultimei actualizari; datele utile sunt in atribute.

## Instalare
1. Descarcati acest repository ca arhiva ZIP.
2. Copiati folderul `custom_components/meteo_anm` in `/config/custom_components`.
3. Reporniti Home Assistant.
4. Adaugati integrarea din Settings > Devices & Services > Integrations > Add Integration (`Prognoza Meteo si Avertizari by ANM`).
5. Completati:
   - `update_interval` (secunde, minim 60; implicit 180)
   - `localitate` (ex. `Bucuresti`)
   - `judet` (ex. `B`, `CJ`, `GL`)
   - `judet_long` (ex. `Bucuresti`, `Cluj`, `Galati`)

## Noutati in aceasta versiune
- Interval de actualizare in secunde cu minim 60s; actualizarea initiala se face la adaugare.
- UI tradus (en/ro) in `translations/`.
- Senzorii au `unique_id` stabil si folosesc icon-ul local inclus.
- Starea si atributele se scriu corect la fiecare update, pastrand doar judetul/localitatea selectate.

## Accesarea datelor in Jinja (exemple)

Starea vremii pentru localitatea setata:
```jinja
{% set raw = state_attr('sensor.starea_vremii_meteo_anm','oras_selectat') %}
Localitate: {{ raw.nume }}
Temperatura: {{ raw.temperatura }} °C
Umiditate: {{ raw.umiditate }} %
Presiune: {{ raw.presiune }}
Nebulozitate: {{ raw.nebulozitate }}
Fenomen: {{ raw.fenomene }}
Zapada: {{ raw.zapada }}
Temperatura apei: {{ raw.tempapa}}
Vant: {{ raw.vant }}
Ultima actualizare: {{ raw.last_update }}
```

Avertizari generale (lista pe judete):
```jinja
{% set avertizari = state_attr('sensor.avertizari_meteo_anm','avertizari') %}
{% for av in avertizari %}
Jud: {{ av.judet }} | Cod: {{ av.culoare }} | Fenomene: {{ av.fenomene_vizate }}
Valabil: {{ av.data_aparitiei }} - {{ av.data_expirarii }}
Mesaj: {{ av.mesaj }}
{% endfor %}
```

Nowcasting:
```jinja
{% set now = state_attr('sensor.avertizari_nowcasting_meteo_anm','avertizari')[0] %}
Tip: {{ now.tip_mesaj }} | Zona: {{ now.zona }}
Semnalare: {{ now.semnalare }}
Valabil: {{ now.data_inceput }} - {{ now.data_sfarsit }}
Culoare: {{ now.culoare }}
```

Prognoza pe 5 zile pentru localitatea setata:
```jinja
{% set prog = state_attr('sensor.prognoza_orase_meteo_anm','prognoza_oras') %}
Localitate: {{ prog.nume }} ({{ prog.data_prognozei }})
{% for zi in prog.prognoza %}
- {{ zi.data }}: {{ zi.temp_min }}..{{ zi.temp_max }} °C, {{ zi.fenomen_descriere }} ({{ zi.fenomen_simbol }})
{% endfor %}
```

## Automatizare exemplu (notificare pe avertizari)
```yaml
alias: Avertizare ANM
trigger:
  - platform: state
    entity_id: sensor.avertizari_meteo_anm
    to: active
condition: []
action:
  - action: notify.mobile_app_telefon
    data:
      title: Avertizare Meteo
      message: >
        {% set av = state_attr('sensor.avertizari_meteo_anm','avertizari')[0] %}
        Cod: {{ av.culoare }} | Fenomene: {{ av.fenomene_vizate }}
        Interval: {{ av.data_aparitiei }} - {{ av.data_expirarii }}
mode: single
```
