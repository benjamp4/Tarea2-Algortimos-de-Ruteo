import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DIR_INFRA = RAIZ / "data" / "infraestructura"
DIR_SISMO = RAIZ / "data" / "sismo"
DIR_SQL = RAIZ / "sql"
DIR_SALIDA = RAIZ / "salida"
MAIN_SQL = RAIZ / "main.sql"

DB_URL = os.getenv("TAREA2_DB_URL", "postgresql+psycopg2://postgres:postgres@localhost:5434/tarea2")

CONECTOR_MAX_KM = 10.0
CONECTOR_SEPARACION_KM = 20.0
MC_ITERACIONES = 5000
MC_SEMILLA = 2010
