-- ============================================================
-- EduData Pipeline
-- Script: 00_create_raw_tables.sql
-- Objetivo: crear esquemas y tablas raw para recibir datos CSV
-- ============================================================

-- 1. Crear esquemas del proyecto
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS mart;

-- ============================================================
-- 2. Crear tablas RAW
-- Nota:
-- La capa raw recibe los datos tal como llegan desde los CSV.
-- Por eso aquí NO usamos llaves primarias, foreign keys ni checks estrictos.
-- ============================================================

CREATE TABLE IF NOT EXISTS raw.raw_carreras (
    id_carrera INTEGER,
    nombre_carrera VARCHAR(150),
    facultad VARCHAR(150),
    duracion_semestres INTEGER
);

CREATE TABLE IF NOT EXISTS raw.raw_asignaturas (
    id_asignatura VARCHAR(20),
    nombre_asignatura VARCHAR(150),
    id_carrera INTEGER,
    semestre_plan INTEGER,
    creditos INTEGER
);

CREATE TABLE IF NOT EXISTS raw.raw_estudiantes (
    id_estudiante INTEGER,
    nombre VARCHAR(100),
    apellido VARCHAR(150),
    edad INTEGER,
    genero VARCHAR(30),
    id_carrera INTEGER,
    fecha_ingreso DATE,
    estado_estudiante VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS raw.raw_notas (
    id_nota INTEGER,
    id_estudiante INTEGER,
    id_asignatura VARCHAR(20),
    periodo VARCHAR(10),
    nota_final NUMERIC(3,1),
    estado_aprobacion VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS raw.raw_asistencia (
    id_asistencia INTEGER,
    id_estudiante INTEGER,
    id_asignatura VARCHAR(20),
    periodo VARCHAR(10),
    porcentaje_asistencia INTEGER
);

CREATE TABLE IF NOT EXISTS raw.raw_matriculas (
    id_matricula INTEGER,
    id_estudiante INTEGER,
    periodo VARCHAR(10),
    estado_matricula VARCHAR(50),
    fecha_matricula DATE
);

-- ============================================================
-- 3. Verificación rápida
-- ============================================================

SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'raw'
ORDER BY table_name;