import math

import config
from modulos import db

COMPONENTES = """SELECT node, component FROM pgr_connectedComponents(
    'SELECT id, source, target, 1.0::float8 AS cost, 1.0::float8 AS reverse_cost FROM red')"""


def _km(a, b):
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b.lon - a.lon) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def componentes():
    n = db.consulta(f"SELECT count(*) AS n FROM ({COMPONENTES}) c GROUP BY component ORDER BY 1 DESC").n
    return {"componentes": len(n), "mayor": int(n.iloc[0])}


def agregar_conectores():
    candidatos = db.consulta(
        f"""
        WITH cc AS ({COMPONENTES}),
        v AS (SELECT v.id, v.the_geom AS g, cc.component FROM red_vertices_pgr v JOIN cc ON cc.node = v.id)
        SELECT a.id AS va, b.id AS vb, a.component AS ca, b.component AS cb, ST_X(a.g) AS lon, ST_Y(a.g) AS lat,
               ST_Distance(a.g::geography, b.g::geography) / 1000.0 AS d_km
        FROM v a JOIN v b ON a.component < b.component AND ST_DWithin(a.g, b.g, :grados)
        WHERE ST_DWithin(a.g::geography, b.g::geography, :metros)
        ORDER BY d_km
        """,
        grados=config.CONECTOR_MAX_KM / 60.0,
        metros=config.CONECTOR_MAX_KM * 1000.0,
    )
    aceptados = []
    for c in candidatos.itertuples():
        if all((a.ca, a.cb) != (c.ca, c.cb) or _km(a, c) >= config.CONECTOR_SEPARACION_KM for a in aceptados):
            aceptados.append(c)
    if aceptados:
        db.ejecutar(f"""
            INSERT INTO red (id, geom, capa, tipo, largo_km, source, target)
            SELECT (SELECT max(id) FROM red) + row_number() OVER (), ST_MakeLine(a.the_geom, b.the_geom),
                   'conector', 'conector', ST_Distance(a.the_geom::geography, b.the_geom::geography) / 1000.0, p.va, p.vb
            FROM (VALUES {",".join(f"({c.va},{c.vb})" for c in aceptados)}) AS p(va, vb)
            JOIN red_vertices_pgr a ON a.id = p.va
            JOIN red_vertices_pgr b ON b.id = p.vb""")
    return len(aceptados), sum(c.d_km for c in aceptados)


def construir_red():
    db.ejecutar_archivo(config.DIR_SQL / "red.sql")
    antes = componentes()
    n_conectores, km_conectores = agregar_conectores()
    db.ejecutar_archivo(config.DIR_SQL / "attr.sql")
    return {
        "antes": antes,
        "conectores": n_conectores,
        "km_conectores": km_conectores,
        "despues": componentes(),
        "vertices": db.escalar("SELECT count(*) FROM red_vertices_pgr"),
        "p_falla_cero": db.escalar("SELECT count(*) FROM red WHERE p_falla = 0"),
        "por_capa": db.consulta("SELECT capa, count(*) AS tramos, round(sum(largo_km)) AS km FROM red GROUP BY 1 ORDER BY 2 DESC"),
    }
