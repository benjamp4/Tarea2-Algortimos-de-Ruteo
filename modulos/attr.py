from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

import config
from modulos import db


@dataclass
class Grafo:
    ids: np.ndarray
    s: np.ndarray
    t: np.ndarray
    n: int
    clave: np.ndarray
    nombres: np.ndarray


def attr_sql(filtro="true"):
    return float(db.escalar("SELECT calcular_attr(:f)", f=filtro))


def cargar_grafo():
    e = db.consulta("SELECT id, source, target FROM red ORDER BY id")
    nk = db.consulta("SELECT nombre, vertice_id FROM nodos_clave ORDER BY id")
    v = pd.Index(pd.unique(pd.concat([e.source, e.target, nk.vertice_id])))
    return Grafo(e.id.to_numpy(), v.get_indexer(e.source), v.get_indexer(e.target), len(v),
                 v.get_indexer(nk.vertice_id), nk.nombre.to_numpy())


def componentes_clave(g, vivas):
    m = coo_matrix((np.ones(vivas.sum()), (g.s[vivas], g.t[vivas])), shape=(g.n, g.n))
    return connected_components(m, directed=False)[1][g.clave]


def attr(componentes):
    _, s = np.unique(componentes, return_counts=True)
    n = len(componentes)
    return float((s * (s - 1)).sum() / (n * (n - 1)))


def attr_python(g, vivas=None):
    return attr(componentes_clave(g, np.ones(len(g.ids), bool) if vivas is None else vivas))


def montecarlo(g, p, n_iter=config.MC_ITERACIONES, semilla=config.MC_SEMILLA):
    rng = np.random.default_rng(semilla)
    i, j = np.triu_indices(len(g.clave), 1)
    valores, conectados = np.empty(n_iter), np.zeros(len(i))
    for k in range(n_iter):
        comp = componentes_clave(g, rng.random(len(p)) >= p)
        valores[k] = attr(comp)
        conectados += comp[i] == comp[j]
    media, ee = valores.mean(), 1.96 * valores.std(ddof=1) / np.sqrt(n_iter)
    resumen = {
        "attr_medio": media,
        "ic95": [media - ee, media + ee],
        "attr_p05": np.percentile(valores, 5),
        "attr_p50": np.percentile(valores, 50),
        "prob_attr_1": float((valores >= 1 - 1e-12).mean()),
        "n_iter": n_iter,
    }
    pares = pd.DataFrame({"origen": g.nombres[i], "destino": g.nombres[j], "p_conectados": conectados / n_iter})
    return resumen, pares
