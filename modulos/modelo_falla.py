import numpy as np
import pandas as pd
from scipy.stats import norm

import config
from modulos import db

FRAGILIDAD = pd.DataFrame(
    {"aerea": (0.60, 0.50), "soterrada": (0.75, 0.50), "conector": (0.75, 0.50)}, index=["theta", "beta"]
).T

TRAMOS = """
    WITH e AS (SELECT geom FROM sismo_epicentro),
         rup AS (SELECT ST_Force2D(geom) AS g FROM sismo_ruptura)
    SELECT r.id, r.source, r.target, r.capa, r.tipo, r.largo_km,
           ST_Distance(r.geom::geography, e.geom::geography) / 1000.0 AS dist_epicentro_km,
           ST_Distance(r.geom::geography, rup.g::geography) / 1000.0 AS dist_ruptura_km,
           ST_X(ST_ClosestPoint(rup.g, r.geom)) AS rup_lon,
           ST_Y(ST_ClosestPoint(rup.g, r.geom)) AS rup_lat,
           ST_AsText(r.geom, 6) AS wkt
    FROM red r, e, rup ORDER BY r.id
"""

MAIN_SQL = """BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;

DROP TABLE IF EXISTS prob_falla;
CREATE TABLE prob_falla (
    id_tramo          bigint PRIMARY KEY,
    source            bigint,
    target            bigint,
    capa              text,
    tipo              text,
    largo_km          double precision,
    dist_epicentro_km double precision,
    pga_g             double precision,
    p_falla           double precision,
    pga_ruptura_g     double precision,
    p_falla_ruptura   double precision,
    geom              geometry(LineString, 4326)
);

INSERT INTO prob_falla VALUES
{filas};

DO $$
BEGIN
    IF to_regclass('public.red') IS NOT NULL THEN
        ALTER TABLE red ADD COLUMN IF NOT EXISTS pga_g double precision,
                        ADD COLUMN IF NOT EXISTS p_falla double precision,
                        ADD COLUMN IF NOT EXISTS p_falla_ruptura double precision;
        UPDATE red r SET pga_g = pf.pga_g, p_falla = pf.p_falla, p_falla_ruptura = pf.p_falla_ruptura
        FROM prob_falla pf WHERE pf.id_tramo = r.id;
    END IF;
END $$;

COMMIT;
"""


def youngs1997(m, r_km, h_km):
    ln_pga = 0.2418 + 1.414 * m - 2.552 * np.log(r_km + 1.7818 * np.exp(0.554 * m)) + 0.00607 * h_km
    return np.exp(ln_pga), 1.45 - 0.1 * min(m, 8.0)


def prob_falla(pga, sigma, tipo, escala):
    f = FRAGILIDAD.reindex(tipo)
    p_ref = norm.cdf((np.log(pga) - np.log(f.theta.to_numpy())) / np.sqrt(f.beta.to_numpy() ** 2 + sigma ** 2))
    return np.nan_to_num(1 - (1 - p_ref) ** escala)


def profundidad_ruptura(lon, lat):
    v = db.consulta("SELECT ST_X(g) AS x, ST_Y(g) AS y, ST_Z(g) AS z FROM (SELECT (ST_DumpPoints(geom)).geom AS g FROM sismo_ruptura) s")
    a, b, c = np.linalg.lstsq(np.c_[np.ones(len(v)), v.x, v.y], v.z, rcond=None)[0]
    return np.clip(a + b * lon + c * lat, 0, None)


def calcular():
    m, h, lon, lat = db.consulta("SELECT magnitud, profundidad_km, lon, lat FROM sismo_epicentro").iloc[0]
    l0 = db.escalar("SELECT avg(ST_Length(geom::geography)) / 1000.0 FROM red_raw WHERE capa <> 'ferry'")
    df = db.consulta(TRAMOS)
    escala = (df.largo_km / l0).to_numpy()

    pga, sigma = youngs1997(m, np.sqrt(df.dist_epicentro_km ** 2 + h ** 2).to_numpy(), h)
    df["pga_g"], df["p_falla"] = pga, prob_falla(pga, sigma, df.tipo, escala)

    r_ruptura = np.sqrt(df.dist_ruptura_km ** 2 + profundidad_ruptura(df.rup_lon, df.rup_lat) ** 2).to_numpy()
    pga_r, _ = youngs1997(m, r_ruptura, h)
    df["pga_ruptura_g"], df["p_falla_ruptura"] = pga_r, prob_falla(pga_r, sigma, df.tipo, escala)

    modelo = {"magnitud": m, "profundidad_km": h, "lon": lon, "lat": lat, "sigma_gmpe": sigma, "largo_referencia_km": l0}
    return df, modelo


def escribir_main_sql(df, ruta=config.MAIN_SQL):
    filas = ",\n".join(
        f"({r.id},{r.source},{r.target},'{r.capa}','{r.tipo}',{r.largo_km:.4f},{r.dist_epicentro_km:.3f},"
        f"{r.pga_g:.6f},{r.p_falla:.8f},{r.pga_ruptura_g:.6f},{r.p_falla_ruptura:.8f},ST_GeomFromText('{r.wkt}',4326))"
        for r in df.itertuples()
    )
    ruta.write_text(MAIN_SQL.format(filas=filas), encoding="utf-8")
