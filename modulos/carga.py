import json

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

import config
from modulos import db

CAPAS = ["fibra_optica_detectada", "postacion_electrica_detectada", "camino_sin_postacion_detectado", "trayecto_en_ferry"]
PRODUCTOS_SISMO = {
    "cont_pga.geojson": "sismo_pga_contornos",
    "cont_mmi.geojson": "sismo_mmi_contornos",
    "rupture.geojson": "sismo_ruptura",
}


def _guardar(gdf, tabla):
    gdf.rename_geometry("geom").to_postgis(tabla, db.engine, if_exists="replace", index=False)
    return len(gdf)


def cargar_infraestructura():
    db.ejecutar("CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS pgrouting;")
    return {t: _guardar(gpd.read_file(config.DIR_INFRA / f"{t}.shp").to_crs(4326), t) for t in CAPAS}


def cargar_sismo():
    ev = json.loads((config.DIR_SISMO / "sismo_8_8_evento.geojson").read_text())
    p = ev["properties"]
    lon, lat, prof = ev["geometry"]["coordinates"]
    evento = gpd.GeoDataFrame([{
        "id_usgs": ev["id"], "titulo": p["title"], "magnitud": p["mag"], "tipo_magnitud": p["magType"],
        "profundidad_km": prof, "fecha_utc": pd.to_datetime(p["time"], unit="ms", utc=True),
        "lon": lon, "lat": lat, "url": p["url"],
    }], geometry=[Point(lon, lat)], crs=4326)

    resumen = {"sismo_epicentro": _guardar(evento, "sismo_epicentro")}
    for archivo, tabla in PRODUCTOS_SISMO.items():
        g = gpd.read_file(config.DIR_SISMO / archivo).set_crs(4326, allow_override=True)
        resumen[tabla] = _guardar(g.rename(columns=lambda c: c.replace(" ", "_")), tabla)
    return resumen
