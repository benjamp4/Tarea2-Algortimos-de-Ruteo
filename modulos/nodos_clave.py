import geopandas as gpd
import pandas as pd

from modulos import db
from modulos.topologia import COMPONENTES

FOA = "aterrizaje del cable submarino Fibra Óptica Austral"
NODOS = [
    ("Arica", "Arica y Parinacota", "recibe,intercambia", "Capital regional y aterrizaje de cables internacionales (SAm-1, Mistral)", -18.4783, -70.3126),
    ("Iquique", "Tarapacá", "recibe", "Capital regional", -20.2133, -70.1503),
    ("Antofagasta", "Antofagasta", "recibe", "Capital regional", -23.6509, -70.3975),
    ("Copiapó", "Atacama", "recibe", "Capital regional", -27.3668, -70.3323),
    ("La Serena", "Coquimbo", "recibe", "Capital regional", -29.9027, -71.2519),
    ("Valparaíso", "Valparaíso", "recibe,intercambia", "Capital regional y principal hub de cables internacionales (SAm-1, Curie, Mistral)", -33.0472, -71.6127),
    ("Santiago", "Metropolitana", "genera,intercambia,recibe", "Data centers (Google Quilicura, destino de Curie), IXP PIT Chile y NAP Chile. Concentra ~40% de la población", -33.4489, -70.6693),
    ("Rancagua", "O'Higgins", "recibe", "Capital regional", -34.1708, -70.7444),
    ("Talca", "Maule", "recibe", "Capital regional", -35.4264, -71.6554),
    ("Chillán", "Ñuble", "recibe", "Capital regional", -36.6066, -72.1034),
    ("Concepción", "Biobío", "recibe", "Capital regional y segunda área metropolitana", -36.8270, -73.0498),
    ("Temuco", "Araucanía", "recibe", "Capital regional", -38.7359, -72.5904),
    ("Valdivia", "Los Ríos", "recibe", "Capital regional", -39.8142, -73.2459),
    ("Puerto Montt", "Los Lagos", "recibe,intercambia", f"Capital regional y {FOA}", -41.4689, -72.9411),
    ("Coyhaique", "Aysén", "recibe", "Capital regional", -45.5752, -72.0662),
    ("Caleta Tortel", "Aysén", "intercambia", FOA.capitalize(), -47.7958, -73.5350),
    ("Punta Arenas", "Magallanes", "recibe,intercambia", f"Capital regional y {FOA}", -53.1638, -70.9171),
    ("Puerto Williams", "Magallanes", "intercambia", FOA.capitalize(), -54.9333, -67.6167),
]


def cargar_nodos_clave():
    df = pd.DataFrame(NODOS, columns=["nombre", "region", "roles", "detalle", "lat", "lon"])
    df.insert(0, "id", range(1, len(df) + 1))
    gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326).rename_geometry("geom").to_postgis(
        "nodos_clave", db.engine, if_exists="replace", index=False)
    db.ejecutar(f"""
        ALTER TABLE nodos_clave ADD PRIMARY KEY (id), ADD vertice_id bigint, ADD dist_red_m double precision;
        WITH cc AS ({COMPONENTES}),
             principal AS (SELECT component FROM cc GROUP BY 1 ORDER BY count(*) DESC LIMIT 1),
             vp AS (SELECT v.id, v.the_geom FROM red_vertices_pgr v JOIN cc ON cc.node = v.id
                    WHERE cc.component = (SELECT component FROM principal))
        UPDATE nodos_clave n SET vertice_id = (SELECT vp.id FROM vp ORDER BY vp.the_geom <-> n.geom LIMIT 1);
        UPDATE nodos_clave n SET dist_red_m = ST_Distance(n.geom::geography, v.the_geom::geography)
        FROM red_vertices_pgr v WHERE v.id = n.vertice_id;""")
    return db.consulta("SELECT id, nombre, roles, vertice_id, round(dist_red_m) AS dist_red_m FROM nodos_clave ORDER BY id")
