SET client_min_messages = warning;

DROP TABLE IF EXISTS red_raw, red, red_vertices_pgr CASCADE;

CREATE TABLE red_raw AS
SELECT 'fibra'::text AS capa, (ST_Dump(geom)).geom::geometry(LineString, 4326) AS geom FROM fibra_optica_detectada
UNION ALL SELECT 'poste', (ST_Dump(geom)).geom FROM postacion_electrica_detectada
UNION ALL SELECT 'camino', (ST_Dump(geom)).geom FROM camino_sin_postacion_detectado
UNION ALL SELECT 'ferry', (ST_Dump(geom)).geom FROM trayecto_en_ferry;
CREATE INDEX ON red_raw USING gist (geom);

CREATE TABLE red AS
SELECT row_number() OVER (ORDER BY ST_X(ST_StartPoint(geom)), ST_Y(ST_StartPoint(geom)),
                                   ST_X(ST_EndPoint(geom)), ST_Y(ST_EndPoint(geom)), ST_Length(geom))::bigint AS id,
       geom
FROM (SELECT (ST_Dump(ST_UnaryUnion(ST_Collect(ST_SnapToGrid(geom, 0.00001))))).geom::geometry(LineString, 4326) AS geom
      FROM red_raw) s;

ALTER TABLE red ADD PRIMARY KEY (id), ADD capa text, ADD tipo text, ADD largo_km double precision,
                ADD source bigint, ADD target bigint, ADD p_falla double precision NOT NULL DEFAULT 0;
CREATE INDEX ON red USING gist (geom);

UPDATE red n SET capa = (
    SELECT r.capa FROM red_raw r
    WHERE ST_DWithin(r.geom, ST_LineInterpolatePoint(n.geom, 0.5), 0.00005)
    ORDER BY array_position(ARRAY['fibra', 'poste', 'camino', 'ferry'], r.capa)
    LIMIT 1);

UPDATE red SET
    tipo = CASE capa WHEN 'camino' THEN 'soterrada' WHEN 'ferry' THEN 'ferry' ELSE 'aerea' END,
    largo_km = ST_Length(geom::geography) / 1000.0;

SELECT pgr_createTopology('red', 0.00001, 'geom', 'id');

DELETE FROM red WHERE source = target;
