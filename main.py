import argparse
import json

import numpy as np

import config
import servidor
from modulos import attr, carga, db, mapa, modelo_falla, nodos_clave, topologia


def titulo(texto):
    print(f"\n{texto}")


def redondear(x):
    if isinstance(x, float):
        return round(x, 6)
    if isinstance(x, dict):
        return {k: redondear(v) for k, v in x.items()}
    if isinstance(x, list):
        return [redondear(v) for v in x]
    return x


def simulacion_representativa(g, p, intentos=500):
    rng = np.random.default_rng(config.MC_SEMILLA + 1)
    muestras = [rng.random(len(p)) >= p for _ in range(intentos)]
    valores = np.array([round(attr.attr_python(g, vivas), 6) for vivas in muestras])
    estados, veces = np.unique(valores[valores < 1], return_counts=True)
    moda = estados[veces.argmax()]
    elegida = muestras[int(np.argmax(valores == moda))]
    return set(g.ids[~elegida]), moda, veces.max(), intentos


def main():
    ap = argparse.ArgumentParser(description="ATTR de la red Yafún antes y después del sismo M8.8 de 2010")
    ap.add_argument("--sin-carga", action="store_true", help="reutiliza la BD ya cargada")
    ap.add_argument("--iter", type=int, default=config.MC_ITERACIONES, help="iteraciones Monte Carlo")
    args = ap.parse_args()
    config.DIR_SALIDA.mkdir(exist_ok=True)
    db.asegurar_bd()

    if not args.sin_carga:
        titulo("1. Carga de infraestructura y sismo")
        print(carga.cargar_infraestructura())
        print(carga.cargar_sismo())

        titulo("2. Topología")
        r = topologia.construir_red()
        print(f"Tras pgr_createTopology: {r['antes']}")
        print(f"Conectores: {r['conectores']} ({r['km_conectores']:.1f} km) -> {r['despues']}, {r['vertices']} vértices")
        print(r["por_capa"].to_string(index=False))
        print(f"Probabilidad de falla inicial: {r['p_falla_cero']} enlaces con p_falla = 0")

        titulo("3. Nodos clave")
        print(nodos_clave.cargar_nodos_clave().to_string(index=False))

    titulo("4. ATTR antes del sismo")
    g = attr.cargar_grafo()
    attr_antes = attr.attr_sql()
    print(f"pgRouting: {attr_antes:.4f} | Python: {attr.attr_python(g):.4f}")
    puente = attr.puentes(g)
    print(f"Enlaces puente (su caída sola separa nodos clave): {puente.sum()}")

    titulo("5. Modelo de falla y main.sql")
    df, modelo = modelo_falla.calcular()
    modelo_falla.escribir_main_sql(df)
    db.ejecutar_archivo(config.MAIN_SQL)
    print(f"{len(df)} enlaces -> {config.MAIN_SQL.name}")
    print(df.groupby("tipo").p_falla.agg(tramos="size", media="mean", maximo="max", esperados_caidos="sum").round(4).to_string())

    titulo(f"6. ATTR después del sismo (Monte Carlo, {args.iter} iteraciones)")
    p = df.set_index("id").loc[g.ids]
    resultados, pares = {}, {}
    for escenario, col in [("epicentro", "p_falla"), ("ruptura", "p_falla_ruptura")]:
        resultados[escenario], pares[escenario] = attr.montecarlo(g, p[col].to_numpy(), args.iter)
        pares[escenario].sort_values("p_conectados").to_csv(config.DIR_SALIDA / f"pares_{escenario}.csv", index=False)
        r = resultados[escenario]
        print(f"{escenario:10s} E[ATTR] = {r['attr_medio']:.4f}  IC95% [{r['ic95'][0]:.4f}, {r['ic95'][1]:.4f}]  "
              f"mediana = {r['attr_p50']:.4f}  P(ATTR=1) = {r['prob_attr_1']:.3f}")
    attr_det = attr.attr_sql("p_falla < 0.5")
    print(f"determinista (sin tramos p >= 0.5): {attr_det:.4f}")
    p_puente = {e: 1 - np.prod(1 - p[col].to_numpy()[puente]) for e, col in [("epicentro", "p_falla"), ("ruptura", "p_falla_ruptura")]}
    print(f"P(cae algún enlace puente): epicentro {p_puente['epicentro']:.3f} | ruptura {p_puente['ruptura']:.3f} | "
          f"puente más cercano al epicentro: {p.dist_epicentro_km.to_numpy()[puente].min():.0f} km")
    print(pares["epicentro"].sort_values("p_conectados").head(10).to_string(index=False))

    salida = {
        "attr_antes": attr_antes,
        "attr_despues_epicentro": resultados["epicentro"],
        "attr_despues_ruptura": resultados["ruptura"],
        "attr_determinista_p_lt_0_5": attr_det,
        "enlaces_puente": {"cantidad": int(puente.sum()), "p_cae_alguno": p_puente},
        "tramos_esperados_caidos": {"epicentro": df.p_falla.sum(), "ruptura": df.p_falla_ruptura.sum()},
        "modelo": modelo,
    }
    (config.DIR_SALIDA / "resultados.json").write_text(json.dumps(redondear(salida), indent=2, ensure_ascii=False))

    titulo("7. Mapa Leaflet")
    caidos, attr_sim, veces, intentos = simulacion_representativa(g, p.p_falla.to_numpy())
    print(f"Simulación del mapa (estado de daño más frecuente, {veces} de {intentos}): "
          f"{len(caidos)} enlaces caídos, ATTR = {attr_sim:.4f}")
    ruta = mapa.generar_mapa(attr_antes, resultados["epicentro"], resultados["ruptura"], pares["epicentro"], caidos)
    print(f"Archivo: {ruta}")

    titulo("Resumen")
    print(f"ATTR antes: {attr_antes:.4f} | después epicentro: {resultados['epicentro']['attr_medio']:.4f} | "
          f"después ruptura: {resultados['ruptura']['attr_medio']:.4f}")

    titulo("Sitio web")
    servidor.servir()


if __name__ == "__main__":
    main()
