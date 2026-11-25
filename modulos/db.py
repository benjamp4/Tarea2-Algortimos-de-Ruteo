import subprocess
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

import config

engine = create_engine(config.DB_URL)


def ejecutar(sql):
    conn = engine.raw_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def ejecutar_archivo(ruta):
    ejecutar(Path(ruta).read_text(encoding="utf-8"))


def consulta(sql, **params):
    with engine.connect() as c:
        return pd.read_sql(text(sql), c, params=params)


def escalar(sql, **params):
    with engine.connect() as c:
        return c.execute(text(sql), params).scalar()


def asegurar_bd(intentos=30):
    try:
        return escalar("SELECT 1")
    except OperationalError:
        pass
    print("La BD no responde: levantando el contenedor con docker compose")
    try:
        subprocess.run(["docker", "compose", "up", "-d", "--wait"], cwd=config.RAIZ, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        raise SystemExit("No se pudo levantar la BD: instala Docker, ábrelo y vuelve a correr python main.py")
    for _ in range(intentos):
        try:
            return escalar("SELECT 1")
        except OperationalError:
            time.sleep(2)
    raise SystemExit("La BD no respondió después de levantar el contenedor")
