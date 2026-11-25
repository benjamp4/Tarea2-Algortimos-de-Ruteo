import branca.colormap as cm
import folium
import geopandas as gpd
from folium.plugins import Fullscreen

import config
from modulos import db

CAPAS = {
    "fibra": ("#1f77b4", "Fibra óptica detectada"),
    "poste": ("#2ca02c", "Postación eléctrica"),
    "camino": ("#8c8c8c", "Camino sin postación"),
    "ferry": ("#17becf", "Trayecto en ferry"),
    "conector": ("#e377c2", "Conector (hueco ≤10 km)"),
}
TOOLTIP_P = (["id", "capa", "pga_g", "p_epi", "p_rup"], ["Tramo", "Capa", "PGA (g)", "P falla epicentro", "P falla ruptura"])


def _leer(sql):
    return gpd.read_postgis(sql, db.engine, geom_col="geom")


def _capa(mapa, nombre, gdf, estilo, tooltip=None, show=True, simplificar=0.0005):
    if simplificar:
        gdf = gdf.assign(geom=gdf.geometry.simplify(simplificar, preserve_topology=False))
    fg = folium.FeatureGroup(nombre, show=show)
    folium.GeoJson(gdf.to_json(), style_function=estilo,
                   tooltip=folium.GeoJsonTooltip(*tooltip) if tooltip else None).add_to(fg)
    fg.add_to(mapa)


def _panel(attr_antes, epi, rup, n_nodos):
    leyenda = "".join(f"<div><span style='display:inline-block;width:18px;height:3px;background:{c};"
                      f"vertical-align:middle;margin-right:6px'></span>{n}</div>" for c, n in CAPAS.values())
    return f"""
    <style>
      #lateral{{position:fixed;top:6px;left:50px;z-index:9999;width:330px;max-width:calc(100vw - 60px);
               max-height:calc(100vh - 12px);overflow-y:auto;padding:6px;box-sizing:border-box;
               display:flex;flex-direction:column;gap:10px;font:13px/1.45 system-ui,sans-serif;color:#222}}
      #lateral .caja, #lateral .leaflet-control-layers{{background:rgba(255,255,255,.95);padding:10px 14px;margin:0;
               border:0;border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.3);font:inherit;color:inherit}}
      #lateral .titulo{{font-weight:700;font-size:14px;margin-bottom:4px}}
      .legend.leaflet-control{{background:rgba(255,255,255,.95);padding:4px 6px 0;border-radius:8px;
               box-shadow:0 1px 6px rgba(0,0,0,.3)}}
      #legend .caption{{font:13px system-ui,sans-serif;fill:#222}}
    </style>
    <div id="lateral"><div class="caja">
      <div class="titulo">Resiliencia red Yafún – Sismo M8.8 Maule 2010</div>
      <div>ATTR antes del sismo: <b>{attr_antes:.3f}</b></div>
      <div>ATTR después (epicentro): <b>{epi['attr_medio']:.3f}</b>
           <span style="color:#666">IC95% [{epi['ic95'][0]:.3f}, {epi['ic95'][1]:.3f}]</span></div>
      <div>ATTR después (ruptura): <b>{rup['attr_medio']:.3f}</b> <span style="color:#666">(sensibilidad)</span></div>
      <div style="color:#666">Monte Carlo: {epi['n_iter']} iteraciones · {n_nodos} nodos clave</div>
      <hr style="margin:6px 0">{leyenda}
      <div style="margin-top:4px;color:#666">Nodos: color = P(conectado con Santiago)</div>
    </div></div>
    <script>window.addEventListener("load", () => {{
      document.getElementById("lateral").appendChild(document.querySelector(".leaflet-control-layers"));
      const barra = document.getElementById("legend"), rects = [...barra.querySelectorAll("rect")];
      const ini = Math.min(...rects.map(r => +r.getAttribute("x")));
      const fin = Math.max(...rects.map(r => +r.getAttribute("x") + +r.getAttribute("width")));
      const texto = barra.querySelector(".caption");
      texto.setAttribute("x", (ini + fin) / 2);
      texto.setAttribute("y", 30);
      texto.setAttribute("text-anchor", "middle");
      barra.setAttribute("height", 54);
    }});</script>"""


def _color_nodo(nombre, p, n_iter):
    if nombre == "Santiago":
        texto = "Santiago es la referencia: el color de los demás nodos indica si siguen conectados con él."
    elif p >= 0.9:
        texto = (f"Sigue conectado con Santiago en el {p:.1%} de las {n_iter} simulaciones: su camino hacia Santiago "
                 "no pasa por la zona de mayor daño o tiene rutas alternativas.")
    else:
        texto = (f"Queda separado de Santiago en el {1 - p:.1%} de las {n_iter} simulaciones: su camino hacia Santiago "
                 "cruza la zona de mayor daño (cerca del epicentro), donde la red casi no tiene rutas alternativas. "
                 "Si se corta ahí, todos los nodos al sur quedan aislados a la vez, y por eso tienen el mismo color.")
    return f"""<hr style="margin:6px 0"><b>Color del nodo = P(conectado con Santiago tras el sismo): {p:.1%}</b>
      <div style="position:relative;height:10px;margin:6px 0 2px;border-radius:5px;
                  background:linear-gradient(to right,#bd0026,#fd8d3c,#1a9850)">
        <div style="position:absolute;left:calc({p:.4f} * 100% - 2px);top:-3px;width:4px;height:16px;background:#222"></div></div>
      <div style="display:flex;justify-content:space-between;color:#666;font-size:11px">
        <span>0 % rojo</span><span>50 % naranjo</span><span>100 % verde</span></div>
      <div style="margin-top:4px">{texto}</div>"""


def generar_mapa(attr_antes, epi, rup, pares, caidos, ruta=config.DIR_SALIDA / "mapa.html"):
    red = _leer("SELECT id, capa, round(largo_km::numeric, 2)::float AS largo_km, round(pga_g::numeric, 4)::float AS pga_g, "
                "p_falla, p_falla_ruptura, geom FROM red")
    red["p_epi"] = (red.p_falla * 100).round(2).astype(str) + " %"
    red["p_rup"] = (red.p_falla_ruptura * 100).round(2).astype(str) + " %"
    nodos = _leer("SELECT * FROM nodos_clave ORDER BY id")
    sismo = db.consulta("SELECT * FROM sismo_epicentro").iloc[0]

    m = folium.Map(location=[-37.5, -71.5], zoom_start=5, control_scale=True, tiles=None)
    folium.TileLayer("OpenStreetMap", control=False).add_to(m)
    Fullscreen().add_to(m)

    _capa(m, "Red en operación (por capa)", red[["id", "capa", "largo_km", "geom"]],
          lambda f: {"color": CAPAS[f["properties"]["capa"]][0], "weight": 2, "opacity": 0.8},
          (["id", "capa", "largo_km"], ["Tramo", "Capa", "Largo (km)"]))

    escala = cm.LinearColormap(["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"], vmin=0,
                               vmax=float(red[["p_falla", "p_falla_ruptura"]].max().max()),
                               caption="Probabilidad de falla del tramo")
    for col, nombre in [("p_falla", "Probabilidad de falla – epicentro (modelo principal)"),
                        ("p_falla_ruptura", "Probabilidad de falla – plano de ruptura (sensibilidad)")]:
        _capa(m, nombre, red[red[col] > 1e-4],
              lambda f, c=col: {"color": escala(f["properties"][c]), "weight": 4, "opacity": 0.95}, TOOLTIP_P, show=False)
    escala.add_to(m)

    _capa(m, "Tramos caídos (1 simulación Monte Carlo, epicentro)", red[red.id.isin(caidos)],
          lambda f: {"color": "#000", "weight": 6, "opacity": 1, "dashArray": "4 4"}, TOOLTIP_P, simplificar=0)
    _capa(m, "ShakeMap USGS – contornos PGA (%g)", _leer("SELECT value, geom FROM sismo_pga_contornos"),
          lambda f: {"color": "#d62728", "weight": 1.5, "opacity": 0.6}, (["value"], ["PGA (%g)"]), simplificar=0)
    _capa(m, "ShakeMap USGS – contornos MMI", _leer("SELECT value, color, geom FROM sismo_mmi_contornos"),
          lambda f: {"color": f["properties"]["color"], "weight": 2, "opacity": 0.9}, (["value"], ["MMI"]),
          show=False, simplificar=0)
    _capa(m, "Plano de ruptura (USGS)", _leer("SELECT ST_Force2D(geom) AS geom FROM sismo_ruptura"),
          lambda f: {"color": "#7f0000", "fillColor": "#d62728", "weight": 1, "fillOpacity": 0.12}, simplificar=0)

    folium.Marker([sismo.lat, sismo.lon], tooltip=f"Epicentro {sismo.titulo}",
                  popup=folium.Popup(f"<b>{sismo.titulo}</b><br>M{sismo.magnitud} {sismo.tipo_magnitud}<br>"
                                     f"Profundidad: {sismo.profundidad_km} km<br>{sismo.fecha_utc}<br>"
                                     f"<a href='{sismo.url}' target='_blank'>USGS</a>", max_width=300),
                  icon=folium.Icon(color="red", icon="star")).add_to(m)
    for km in (100, 200, 400):
        folium.Circle([sismo.lat, sismo.lon], radius=km * 1000, color="#7f0000", weight=1, fill=False,
                      dash_array="6 6", tooltip=f"{km} km del epicentro").add_to(m)

    stgo = pares[(pares.origen == "Santiago") | (pares.destino == "Santiago")]
    p_stgo = dict(zip(stgo.origen.where(stgo.origen != "Santiago", stgo.destino), stgo.p_conectados), Santiago=1.0)
    color_nodo = cm.LinearColormap(["#bd0026", "#fd8d3c", "#1a9850"], vmin=0, vmax=1)
    fg = folium.FeatureGroup("Nodos clave")
    for n in nodos.itertuples():
        p = p_stgo[n.nombre]
        folium.CircleMarker(
            [n.lat, n.lon], radius=9 if "genera" in n.roles else 7, color="#222", weight=1.5,
            fill=True, fill_color=color_nodo(p), fill_opacity=0.95, tooltip=f"{n.nombre} ({n.roles})",
            popup=folium.Popup(f"<b>{n.nombre}</b> – {n.region}<br><i>{n.roles}</i><br>{n.detalle}<br>"
                               f"Vértice {n.vertice_id} (a {n.dist_red_m:.0f} m de la red)"
                               + _color_nodo(n.nombre, p, epi["n_iter"]), max_width=340),
        ).add_to(fg)
    fg.add_to(m)

    m.get_root().html.add_child(folium.Element(_panel(attr_antes, epi, rup, len(nodos))))
    folium.LayerControl(collapsed=False).add_to(m)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(ruta))
    return ruta
