import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

# -------------------------
# Configuración de conexión
# -------------------------
DB_USER = "postgres"
DB_PASSWORD = "CAMBIAR_POR_TU_PASSWORD"
DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "edudata_db"

# Crear conexión a PostgreSQL
connection_url = URL.create(
    drivername="postgresql+psycopg2",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
)

engine = create_engine(connection_url)

# -------------------------
# Carpeta de los CSV
# -------------------------
data_dir = Path("data/raw_csv")

# -------------------------
# Mapeo CSV → tabla PostgreSQL
# -------------------------
archivos_tablas = {
    "carreras.csv": "raw_carreras",
    "asignaturas.csv": "raw_asignaturas",
    "estudiantes.csv": "raw_estudiantes",
    "notas.csv": "raw_notas",
    "asistencia.csv": "raw_asistencia",
    "matriculas.csv": "raw_matriculas",
}

# -------------------------
# Carga de datos
# -------------------------
with engine.begin() as connection:
    print("Conexión exitosa a PostgreSQL.")

    # Limpiar tablas raw antes de cargar nuevamente
    connection.execute(text("""
        TRUNCATE TABLE
            raw.raw_carreras,
            raw.raw_asignaturas,
            raw.raw_estudiantes,
            raw.raw_notas,
            raw.raw_asistencia,
            raw.raw_matriculas;
    """))

    print("Tablas raw limpiadas correctamente.")

    # Leer cada CSV y cargarlo en su tabla correspondiente
    for archivo_csv, tabla_destino in archivos_tablas.items():
        ruta_csv = data_dir / archivo_csv

        if not ruta_csv.exists():
            raise FileNotFoundError(f"No se encontró el archivo: {ruta_csv}")

        df = pd.read_csv(ruta_csv)

        df.to_sql(
            name=tabla_destino,
            con=connection,
            schema="raw",
            if_exists="append",
            index=False
        )

        print(f"{archivo_csv} cargado en raw.{tabla_destino} - Registros: {len(df)}")

print("Carga completa de archivos CSV a PostgreSQL.")