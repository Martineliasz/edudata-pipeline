"""
generar_datos.py
=================
EduData Pipeline — Generador de datos simulados de una universidad.

Genera 6 archivos CSV en `data/raw_csv/` listos para cargar en PostgreSQL y
analizar en Power BI. Los datos NO son completamente aleatorios: se construyen
sobre una "aptitud" latente por estudiante y factores de dificultad por
asignatura y de comportamiento por carrera, de modo que asistencia, notas,
matrícula y estado del estudiante guarden coherencia académica.

Archivos generados:
    carreras.csv      asignaturas.csv   estudiantes.csv
    notas.csv         asistencia.csv    matriculas.csv

Ejecutar:  python generar_datos.py
"""

import random
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------
# 0. CONFIGURACIÓN Y REPRODUCIBILIDAD
# ----------------------------------------------------------------------
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

OUTPUT_DIR = Path("data/raw_csv")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ENCODING = "utf-8-sig"

N_ESTUDIANTES = 1000

# Periodos académicos con datos. El índice global (ver periodo_a_idx) mapea
# 2020-1 -> 0, de modo que 2023-1 -> 6.
PERIODOS = ["2023-1", "2023-2", "2024-1", "2024-2", "2025-1", "2025-2"]
IDX_INICIO = 6   # índice global de 2023-1
IDX_FIN = 11     # índice global de 2025-2


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def periodo_a_idx(periodo: str) -> int:
    """'2023-1' -> índice global entero (2020-1 = 0, 2020-2 = 1, ...)."""
    anio, sem = periodo.split("-")
    return (int(anio) - 2020) * 2 + (int(sem) - 1)


def idx_a_fecha(idx: int, dia: int = 1) -> str:
    """Índice global de periodo -> fecha VÁLIDA 'YYYY-MM-DD'.

    1er semestre -> marzo, 2º semestre -> agosto (ambos meses tienen 31 días,
    por lo que cualquier día 1..25 es siempre válido)."""
    anio = 2020 + idx // 2
    mes = 3 if idx % 2 == 0 else 8
    return f"{anio:04d}-{mes:02d}-{dia:02d}"


def sigmoide(x: float) -> float:
    """Devuelve un valor en (0, 1); útil para convertir aptitud en 'riesgo'."""
    return 1.0 / (1.0 + np.exp(-x))


def a_romano(n: int) -> str:
    """Entero -> número romano (para nombrar niveles de asignaturas)."""
    tabla = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    res = ""
    for valor, simbolo in tabla:
        while n >= valor:
            res += simbolo
            n -= valor
    return res


# ----------------------------------------------------------------------
# 1. CARRERAS
# ----------------------------------------------------------------------
# Cada carrera tiene:
#   - duración (semestres de la malla)
#   - ajuste_nota : desplaza el promedio de notas (+ sube, - baja)
#   - factor_riesgo : multiplica la probabilidad de suspensión/retiro
# Esto hace que las carreras se comporten distinto entre sí.
CARRERAS_DEF = [
    # (nombre, facultad, duración, ajuste_nota, factor_riesgo)
    ("Ingeniería Civil Industrial", "Facultad de Ingeniería",           10, -0.25, 1.35),
    ("Ingeniería en Informática",   "Facultad de Ingeniería",           10, -0.10, 1.25),
    ("Medicina",                    "Facultad de Ciencias de la Salud", 14,  0.45, 0.70),
    ("Enfermería",                  "Facultad de Ciencias de la Salud", 10,  0.20, 0.90),
    ("Derecho",                     "Facultad de Ciencias Jurídicas",   12,  0.00, 1.05),
    ("Psicología",                  "Facultad de Ciencias Sociales",    10,  0.15, 0.85),
    ("Contador Auditor",            "Facultad de Economía y Negocios",   9,  0.05, 1.00),
]

carreras_rows = []
carreras_meta = {}  # id_carrera -> factores internos (no salen al CSV)
for i, (nombre, facultad, dur, ajuste, riesgo) in enumerate(CARRERAS_DEF, start=1):
    carreras_rows.append({
        "id_carrera": i,
        "nombre_carrera": nombre,
        "facultad": facultad,
        "duracion_semestres": dur,
    })
    carreras_meta[i] = {"duracion": dur, "ajuste_nota": ajuste, "factor_riesgo": riesgo}

df_carreras = pd.DataFrame(carreras_rows)


# ----------------------------------------------------------------------
# 2. ASIGNATURAS
# ----------------------------------------------------------------------
NOMBRES_BASE = [
    "Cálculo", "Álgebra", "Física", "Química General", "Programación",
    "Estadística", "Introducción a la Profesión", "Comunicación Efectiva",
    "Inglés", "Ética Profesional", "Anatomía", "Fisiología", "Bioquímica",
    "Microbiología", "Derecho Constitucional", "Derecho Civil", "Economía",
    "Contabilidad", "Microeconomía", "Macroeconomía", "Psicología General",
    "Metodología de la Investigación", "Taller de Proyectos", "Bases de Datos",
    "Estructuras de Datos", "Sistemas Operativos", "Gestión de Operaciones",
    "Marketing", "Finanzas", "Recursos Humanos", "Salud Pública",
    "Farmacología", "Patología", "Filosofía del Derecho", "Derecho Procesal",
    "Auditoría", "Costos", "Neuropsicología", "Psicología Social",
    "Termodinámica", "Mecánica", "Investigación de Operaciones",
    "Seminario de Título", "Práctica Profesional",
]

asignaturas_rows = []
asignaturas_meta = {}  # id_asignatura -> {dificultad, id_carrera, semestre}
id_asig = 1
for id_carrera, meta in carreras_meta.items():
    repeticiones_nombre = {}  # para nombrar "Cálculo", "Cálculo II", ...
    for semestre in range(1, meta["duracion"] + 1):
        n_asig = random.randint(4, 6)  # varias asignaturas por semestre
        for _ in range(n_asig):
            base = random.choice(NOMBRES_BASE)
            repeticiones_nombre[base] = repeticiones_nombre.get(base, 0) + 1
            k = repeticiones_nombre[base]
            nombre = base if k == 1 else f"{base} {a_romano(k)}"

            # Dificultad: distribución sesgada a "fácil/media"; ~20% difíciles.
            # Rango aprox. 0 (fácil) a 1.8 (muy difícil). Resta puntos a la nota.
            dificultad = float(np.clip(np.random.beta(2, 5) * 1.8, 0.0, 1.8))
            creditos = random.choice([3, 4, 5, 6])

            asignaturas_rows.append({
                "id_asignatura": id_asig,
                "nombre_asignatura": nombre,
                "id_carrera": id_carrera,
                "semestre_plan": semestre,
                "creditos": creditos,
            })
            asignaturas_meta[id_asig] = {
                "dificultad": dificultad,
                "id_carrera": id_carrera,
                "semestre": semestre,
            }
            id_asig += 1

df_asignaturas = pd.DataFrame(asignaturas_rows)

# Índice rápido: (id_carrera, semestre) -> lista de id_asignatura
asig_por_carrera_sem = defaultdict(list)
for aid, m in asignaturas_meta.items():
    asig_por_carrera_sem[(m["id_carrera"], m["semestre"])].append(aid)


# ----------------------------------------------------------------------
# 3. ESTUDIANTES (metadatos; el estado se calcula tras simular la trayectoria)
# ----------------------------------------------------------------------
NOMBRES_F = [
    "María", "Camila", "Valentina", "Javiera", "Catalina", "Antonia",
    "Francisca", "Constanza", "Sofía", "Isidora", "Martina", "Florencia",
    "Emilia", "Josefa", "Trinidad", "Fernanda", "Paula", "Daniela",
    "Carolina", "Bárbara",
]
NOMBRES_M = [
    "Benjamín", "Matías", "Vicente", "Diego", "Sebastián", "Tomás", "Joaquín",
    "Cristóbal", "Felipe", "Agustín", "Ignacio", "Lucas", "Martín", "Gabriel",
    "Nicolás", "Maximiliano", "Bastián", "Alonso", "Pablo", "Rodrigo",
]
APELLIDOS = [
    "González", "Muñoz", "Rojas", "Díaz", "Pérez", "Soto", "Contreras",
    "Silva", "Martínez", "Sepúlveda", "Morales", "Rodríguez", "López",
    "Fuentes", "Hernández", "Torres", "Araya", "Flores", "Espinoza",
    "Castillo", "Tapia", "Reyes", "Gutiérrez", "Castro", "Pizarro",
    "Vásquez", "Núñez", "Cortés", "Vergara", "Fernández",
]

ids_carrera = list(carreras_meta.keys())
# Algunas carreras tienen más estudiantes que otras.
pesos_carrera = np.array([0.20, 0.18, 0.10, 0.12, 0.16, 0.14, 0.10])
pesos_carrera = pesos_carrera / pesos_carrera.sum()

# Cohorte de ingreso (índice global 0=2020-1 .. 11=2025-2). Distribución con
# pico en el centro y suficientes cohortes antiguas para producir egresados.
cohortes = list(range(0, 12))
pesos_cohorte = np.array(
    [0.03, 0.04, 0.06, 0.07, 0.09, 0.10, 0.12, 0.12, 0.11, 0.10, 0.09, 0.07]
)
pesos_cohorte = pesos_cohorte / pesos_cohorte.sum()

estudiantes_meta = {}
for id_est in range(1, N_ESTUDIANTES + 1):
    id_carrera = int(np.random.choice(ids_carrera, p=pesos_carrera))
    aptitud = float(np.random.normal(0.0, 1.0))  # habilidad latente del alumno

    genero = random.choices(
        ["Femenino", "Masculino", "Otro"], weights=[0.49, 0.49, 0.02]
    )[0]
    if genero == "Femenino":
        nombre = random.choice(NOMBRES_F)
    elif genero == "Masculino":
        nombre = random.choice(NOMBRES_M)
    else:
        nombre = random.choice(NOMBRES_F + NOMBRES_M)
    apellido = f"{random.choice(APELLIDOS)} {random.choice(APELLIDOS)}"

    entry_idx = int(np.random.choice(cohortes, p=pesos_cohorte))
    fecha_ingreso = idx_a_fecha(entry_idx, dia=random.randint(1, 25))

    # Edad: edad al ingresar + años transcurridos hasta 2025-2.
    edad_ingreso = random.randint(17, 24)
    edad = edad_ingreso + max(0, (IDX_FIN - entry_idx)) // 2
    edad = int(np.clip(edad, 17, 50))

    estudiantes_meta[id_est] = {
        "nombre": nombre,
        "apellido": apellido,
        "edad": edad,
        "genero": genero,
        "id_carrera": id_carrera,
        "fecha_ingreso": fecha_ingreso,
        "aptitud": aptitud,
        "entry_idx": entry_idx,
        "estado_estudiante": "Activo",  # se sobrescribe tras la simulación
    }


# ----------------------------------------------------------------------
# 4. SIMULACIÓN DE TRAYECTORIA -> NOTAS, ASISTENCIA Y MATRÍCULAS
# ----------------------------------------------------------------------
notas_rows = []
asistencia_rows = []
matriculas_rows = []
id_nota = 1
id_asist = 1
id_matricula = 1

for id_est, est in estudiantes_meta.items():
    aptitud = est["aptitud"]
    id_carrera = est["id_carrera"]
    entry_idx = est["entry_idx"]
    meta_c = carreras_meta[id_carrera]

    # "Riesgo" alto cuando la aptitud es baja (negativa).
    riesgo_base = sigmoide(-aptitud)

    # Semestre en el que está el estudiante al inicio de la ventana de datos.
    if entry_idx <= IDX_INICIO:
        semestre_actual = IDX_INICIO - entry_idx + 1   # cohortes antiguas
    else:
        semestre_actual = 1                            # ingresa dentro de la ventana

    primer_idx = max(IDX_INICIO, entry_idx)

    estado_mat = "Matriculado"
    retirado = False
    egresado = False

    for g in range(primer_idx, IDX_FIN + 1):
        periodo = PERIODOS[g - IDX_INICIO]

        # Si ya superó la malla, egresó (no genera más registros).
        if semestre_actual > meta_c["duracion"]:
            egresado = True
            break

        # --- Transición de estado de matrícula para este periodo ---
        if estado_mat == "Matriculado":
            p_ret = 0.020 * meta_c["factor_riesgo"] * (0.4 + riesgo_base)
            p_susp = 0.045 * meta_c["factor_riesgo"] * (0.4 + riesgo_base)
            r = random.random()
            if r < p_ret:
                estado_mat = "Retirado"
            elif r < p_ret + p_susp:
                estado_mat = "Suspendido"
        elif estado_mat == "Suspendido":
            r = random.random()
            if r < 0.30 * meta_c["factor_riesgo"]:
                estado_mat = "Retirado"
            elif r < 0.30 * meta_c["factor_riesgo"] + 0.55:
                estado_mat = "Matriculado"   # reincorporación
            # en otro caso sigue Suspendido

        # Registro de matrícula del periodo (siempre se registra el estado).
        matriculas_rows.append({
            "id_matricula": id_matricula,
            "id_estudiante": id_est,
            "periodo": periodo,
            "estado_matricula": estado_mat,
            "fecha_matricula": idx_a_fecha(g, dia=random.randint(1, 25)),
        })
        id_matricula += 1

        if estado_mat == "Retirado":
            retirado = True
            break
        if estado_mat == "Suspendido":
            # Sin notas ni asistencia; el semestre no avanza.
            continue

        # --- Matriculado: genera notas y asistencia de las asignaturas ---
        for aid in asig_por_carrera_sem.get((id_carrera, semestre_actual), []):
            dif = asignaturas_meta[aid]["dificultad"]

            # Asistencia ligada a la aptitud + ruido. La mayoría queda en 0..100.
            asistencia = 78 + 14 * aptitud + np.random.normal(0, 8)
            asistencia = float(np.clip(asistencia, 0, 100))

            # Nota = base + aptitud + efecto de la asistencia - dificultad
            #        + ajuste de la carrera + ruido. Escala chilena 1.0 .. 7.0.
            nota = (
                5.3
                + 0.55 * aptitud
                + 0.020 * (asistencia - 75)   # menos asistencia -> menos nota
                - dif                         # asignatura difícil -> menos nota
                + meta_c["ajuste_nota"]       # comportamiento de la carrera
                + np.random.normal(0, 0.55)   # variabilidad
            )
            nota = round(float(np.clip(nota, 1.0, 7.0)), 1)
            estado_ap = "Aprobado" if nota >= 4.0 else "Reprobado"

            notas_rows.append({
                "id_nota": id_nota,
                "id_estudiante": id_est,
                "id_asignatura": aid,
                "periodo": periodo,
                "nota_final": nota,
                "estado_aprobacion": estado_ap,
            })
            asistencia_rows.append({
                "id_asistencia": id_asist,
                "id_estudiante": id_est,
                "id_asignatura": aid,
                "periodo": periodo,
                "porcentaje_asistencia": int(round(asistencia)),
            })
            id_nota += 1
            id_asist += 1

        semestre_actual += 1

    # --- Estado final del estudiante (coherente con su trayectoria) ---
    if retirado:
        estado_est = "Retirado"
    elif egresado or semestre_actual > meta_c["duracion"]:
        estado_est = "Egresado"
    else:
        estado_est = "Activo"
    estudiantes_meta[id_est]["estado_estudiante"] = estado_est


# Construcción del DataFrame de estudiantes (sin columnas internas).
estudiantes_rows = []
for id_est, est in estudiantes_meta.items():
    estudiantes_rows.append({
        "id_estudiante": id_est,
        "nombre": est["nombre"],
        "apellido": est["apellido"],
        "edad": est["edad"],
        "genero": est["genero"],
        "id_carrera": est["id_carrera"],
        "fecha_ingreso": est["fecha_ingreso"],
        "estado_estudiante": est["estado_estudiante"],
    })

df_estudiantes = pd.DataFrame(estudiantes_rows)
df_notas = pd.DataFrame(notas_rows)
df_asistencia = pd.DataFrame(asistencia_rows)
df_matriculas = pd.DataFrame(matriculas_rows)


# ----------------------------------------------------------------------
# 5. ERRORES INTENCIONALES DE CALIDAD DE DATOS (~1%–2% por tabla)
# ----------------------------------------------------------------------
# Pensados para una capa RAW/STAGING: se cargan tal cual y luego el ETL los
# detecta y limpia. (Si cargas directo a tablas con FK/CHECK, hazlo primero a
# una tabla de staging sin restricciones.)
def muestra_indices(df, fraccion):
    """Devuelve k índices distintos del DataFrame (k = fraccion * len, mín. 1)."""
    k = max(1, int(len(df) * fraccion))
    return np.random.choice(df.index, size=k, replace=False)


# 5.1 Notas fuera de rango (escala válida es 1.0 .. 7.0)
idx = muestra_indices(df_notas, 0.006)
valores = np.random.choice([7.5, 7.8, 8.0, 0.5, 0.2, -1.0], size=len(idx))
df_notas.loc[idx, "nota_final"] = valores
df_notas.loc[idx, "estado_aprobacion"] = np.where(valores >= 4.0, "Aprobado", "Reprobado")

# 5.2 Asistencia fuera de rango (válida es 0 .. 100)
idx = muestra_indices(df_asistencia, 0.006)
df_asistencia.loc[idx, "porcentaje_asistencia"] = np.random.choice(
    [105, 110, 150, -5, -10], size=len(idx)
)

# 5.3 id_estudiante inexistente en notas y asistencia
idx = muestra_indices(df_notas, 0.003)
df_notas.loc[idx, "id_estudiante"] = np.random.randint(900000, 999999, size=len(idx))
idx = muestra_indices(df_asistencia, 0.003)
df_asistencia.loc[idx, "id_estudiante"] = np.random.randint(900000, 999999, size=len(idx))

# 5.4 id_asignatura inexistente en notas y asistencia
idx = muestra_indices(df_notas, 0.003)
df_notas.loc[idx, "id_asignatura"] = np.random.randint(900000, 999999, size=len(idx))
idx = muestra_indices(df_asistencia, 0.003)
df_asistencia.loc[idx, "id_asignatura"] = np.random.randint(900000, 999999, size=len(idx))


# 5.5 Registros duplicados (misma clave de negocio, id_PK nuevo y único, de
#     modo que la carga no rompa por PK; el duplicado es lógico/de negocio).
def agregar_duplicados(df, col_id, fraccion):
    k = max(1, int(len(df) * fraccion))
    dup = df.sample(n=k, random_state=SEED).copy()
    nuevo_max = int(df[col_id].max())
    dup[col_id] = range(nuevo_max + 1, nuevo_max + 1 + k)
    return pd.concat([df, dup], ignore_index=True)


df_notas = agregar_duplicados(df_notas, "id_nota", 0.004)
df_asistencia = agregar_duplicados(df_asistencia, "id_asistencia", 0.004)
df_matriculas = agregar_duplicados(df_matriculas, "id_matricula", 0.004)


# ----------------------------------------------------------------------
# 6. GUARDADO DE LOS CSV
# ----------------------------------------------------------------------
salidas = {
    "carreras.csv": df_carreras,
    "asignaturas.csv": df_asignaturas,
    "estudiantes.csv": df_estudiantes,
    "notas.csv": df_notas,
    "asistencia.csv": df_asistencia,
    "matriculas.csv": df_matriculas,
}

for nombre_archivo, df in salidas.items():
    df.to_csv(OUTPUT_DIR / nombre_archivo, index=False, encoding=ENCODING)


# ----------------------------------------------------------------------
# 7. RESUMEN EN CONSOLA
# ----------------------------------------------------------------------
print("=" * 60)
print("EduData Pipeline — generación de datos completada")
print("=" * 60)
print(f"Carpeta de salida : {OUTPUT_DIR.resolve()}")
for nombre_archivo, df in salidas.items():
    print(f"  {nombre_archivo:<18} {len(df):>7,} filas")

print("-" * 60)
print("Distribución de estado_estudiante:")
print(df_estudiantes["estado_estudiante"].value_counts().to_string())

# Comprobación rápida de la correlación asistencia–nota (sólo registros válidos).
val = df_notas[(df_notas["nota_final"].between(1.0, 7.0))].merge(
    df_asistencia[df_asistencia["porcentaje_asistencia"].between(0, 100)],
    on=["id_estudiante", "id_asignatura", "periodo"],
)
if len(val) > 2:
    corr = val["porcentaje_asistencia"].corr(val["nota_final"])
    print(f"\nCorrelación asistencia–nota (válidos): {corr:.3f}")

print("Listo.")