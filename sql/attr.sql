DROP FUNCTION IF EXISTS calcular_attr(text), pares_nodos_clave(text), componentes_nodos_clave(text);

CREATE OR REPLACE FUNCTION componentes_nodos_clave(filtro text DEFAULT 'true')
RETURNS TABLE (nombre text, componente bigint) AS $$
BEGIN
    RETURN QUERY EXECUTE format($q$
        SELECT nc.nombre, cc.component
        FROM nodos_clave nc
        LEFT JOIN pgr_connectedComponents(
            'SELECT id, source, target, 1.0::float8 AS cost, 1.0::float8 AS reverse_cost FROM red WHERE %s'
        ) cc ON cc.node = nc.vertice_id
    $q$, replace(filtro, '''', ''''''));
END
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION calcular_attr(filtro text DEFAULT 'true')
RETURNS double precision AS $$
    WITH k AS (SELECT * FROM componentes_nodos_clave(filtro)),
         g AS (SELECT count(*)::float8 AS s FROM k WHERE componente IS NOT NULL GROUP BY componente)
    SELECT COALESCE(sum(s * (s - 1)), 0) / ((SELECT count(*) FROM k) * ((SELECT count(*) FROM k) - 1))
    FROM g;
$$ LANGUAGE sql STABLE;
