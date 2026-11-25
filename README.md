# Tarea 2 Algortimos de ruteo y redes resilientes

Calcula el ATTR de la red de fibra óptica de Yafún (datos de SUBTEL, Respuesta_T5610) antes y después del terremoto M8.8 de 2010, genera main.sql con la probabilidad de falla de cada enlace y muestra el resultado en un mapa Leaflet.

Requisitos: Docker instalado y abierto, y Python 3.10 o superior. No hay que crear la base de datos a mano.

Para correrlo, desde esta carpeta:

```bash
python3 -m venv .venv && source .venv/bin/activate # (o python sin 3...)
pip install -r requirements.txt
python3 main.py
```

En Windows el entorno se activa con `.venv\Scripts\activate`.

main.py hace todo el proceso en alrededor de 1 minuto:

1. Si la base de datos no responde, la levanta con Docker (PostGIS y pgRouting en localhost:5434).
2. Carga la infraestructura y el sismo desde la carpeta data/.
3. Construye la topología de la red con pgr_createTopology.
4. Calcula el ATTR antes del sismo.
5. Calcula la probabilidad de falla de cada enlace y genera main.sql.
6. Calcula el ATTR después del sismo.
7. Publica el mapa en http://localhost:8050/

Mientras corre, la consola muestra los resultados de cada paso. Al final queda el sitio abierto, y para detenerlo se usa Ctrl+C.

Los resultados quedan en la carpeta salida/: resultados.json con los ATTR, pares_epicentro.csv y pares_ruptura.csv con la probabilidad de conexión de cada par de nodos clave, y mapa.html.

main.sql también se puede cargar por separado en cualquier base con PostGIS:

```bash
psql -h localhost -p 5434 -U postgres -d tarea2 -f main.sql
```

Contenido de la carpeta: main.py ejecuta todo, config.py tiene las rutas y parámetros, servidor.py publica el mapa, modulos/ tiene el código de cada paso, sql/ las consultas, data/ los datos de entrada y docker-compose.yml la base de datos.

Si el puerto 8050 está ocupado, hay que cerrar el otro programa que lo usa y volver a correr python main.py. Si Docker está cerrado, main.py avisa que hay que abrirlo.
