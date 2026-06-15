-- ============================================================
-- EduData Pipeline
-- Script: 01_create_staging.sql
-- Objetivo: limpiar y transformar datos desde raw hacia staging
-- ============================================================

-- 1. Eliminar tablas staging si ya existen
DROP TABLE IF EXISTS staging.stg_matriculas;
DROP TABLE IF EXISTS staging.stg_asistencia;
DROP TABLE IF EXISTS staging.stg_notas;
DROP TABLE IF EXISTS staging.stg_estudiantes;
DROP TABLE IF EXISTS staging.stg_asignaturas;
DROP TABLE IF EXISTS staging.stg_carreras;

-- ============================================================
-- 2. Carreras
-- Limpieza:
-- - elimina duplicados
-- - normaliza textos
-- - conserva carreras con ID válido
-- ============================================================

CREATE TABLE staging.stg_carreras AS
SELECT DISTINCT
    id_carrera,
    INITCAP(TRIM(nombre_carrera)) AS nombre_carrera,
    INITCAP(TRIM(facultad)) AS facultad,
    duracion_semestres
FROM raw.raw_carreras
WHERE id_carrera IS NOT NULL
  AND duracion_semestres IS NOT NULL;

-- ============================================================
-- 3. Asignaturas
-- Limpieza:
-- - elimina duplicados
-- - normaliza textos
-- - conserva solo asignaturas asociadas a carreras existentes
-- ============================================================

CREATE TABLE staging.stg_asignaturas AS
SELECT DISTINCT
    TRIM(id_asignatura::TEXT) AS id_asignatura,
    INITCAP(TRIM(nombre_asignatura)) AS nombre_asignatura,
    id_carrera,
    semestre_plan,
    creditos
FROM raw.raw_asignaturas
WHERE id_asignatura IS NOT NULL
  AND id_carrera IN (
      SELECT id_carrera
      FROM staging.stg_carreras
  );

-- ============================================================
-- 4. Estudiantes
-- Limpieza:
-- - elimina duplicados
-- - normaliza textos
-- - conserva solo estudiantes con carrera existente
-- ============================================================

CREATE TABLE staging.stg_estudiantes AS
SELECT DISTINCT
    id_estudiante,
    INITCAP(TRIM(nombre)) AS nombre,
    INITCAP(TRIM(apellido)) AS apellido,
    edad,
    INITCAP(TRIM(genero)) AS genero,
    id_carrera,
    fecha_ingreso,
    INITCAP(TRIM(estado_estudiante)) AS estado_estudiante
FROM raw.raw_estudiantes
WHERE id_estudiante IS NOT NULL
  AND id_carrera IN (
      SELECT id_carrera
      FROM staging.stg_carreras
  );

-- ============================================================
-- 5. Notas
-- Limpieza:
-- - conserva notas entre 1.0 y 7.0
-- - recalcula estado de aprobación
-- - elimina estudiantes inexistentes
-- - elimina asignaturas inexistentes
-- - elimina duplicados lógicos
-- ============================================================

CREATE TABLE staging.stg_notas AS
WITH notas_limpias AS (
    SELECT
        id_nota,
        id_estudiante,
        TRIM(id_asignatura::TEXT) AS id_asignatura,
        TRIM(periodo) AS periodo,
        nota_final,
        CASE
            WHEN nota_final >= 4.0 THEN 'Aprobado'
            ELSE 'Reprobado'
        END AS estado_aprobacion,
        ROW_NUMBER() OVER (
            PARTITION BY id_estudiante, TRIM(id_asignatura::TEXT), TRIM(periodo)
            ORDER BY id_nota
        ) AS rn
    FROM raw.raw_notas
    WHERE nota_final BETWEEN 1.0 AND 7.0
)
SELECT
    id_nota,
    id_estudiante,
    id_asignatura,
    periodo,
    nota_final,
    estado_aprobacion
FROM notas_limpias
WHERE rn = 1
  AND id_estudiante IN (
      SELECT id_estudiante
      FROM staging.stg_estudiantes
  )
  AND id_asignatura IN (
      SELECT id_asignatura
      FROM staging.stg_asignaturas
  );

-- ============================================================
-- 6. Asistencia
-- Limpieza:
-- - conserva asistencia entre 0 y 100
-- - elimina estudiantes inexistentes
-- - elimina asignaturas inexistentes
-- - elimina duplicados lógicos
-- ============================================================

CREATE TABLE staging.stg_asistencia AS
WITH asistencia_limpia AS (
    SELECT
        id_asistencia,
        id_estudiante,
        TRIM(id_asignatura::TEXT) AS id_asignatura,
        TRIM(periodo) AS periodo,
        porcentaje_asistencia,
        ROW_NUMBER() OVER (
            PARTITION BY id_estudiante, TRIM(id_asignatura::TEXT), TRIM(periodo)
            ORDER BY id_asistencia
        ) AS rn
    FROM raw.raw_asistencia
    WHERE porcentaje_asistencia BETWEEN 0 AND 100
)
SELECT
    id_asistencia,
    id_estudiante,
    id_asignatura,
    periodo,
    porcentaje_asistencia
FROM asistencia_limpia
WHERE rn = 1
  AND id_estudiante IN (
      SELECT id_estudiante
      FROM staging.stg_estudiantes
  )
  AND id_asignatura IN (
      SELECT id_asignatura
      FROM staging.stg_asignaturas
  );

-- ============================================================
-- 7. Matrículas
-- Limpieza:
-- - elimina estudiantes inexistentes
-- - elimina duplicados lógicos por estudiante y periodo
-- - normaliza texto del estado de matrícula
-- ============================================================

CREATE TABLE staging.stg_matriculas AS
WITH matriculas_limpias AS (
    SELECT
        id_matricula,
        id_estudiante,
        TRIM(periodo) AS periodo,
        INITCAP(TRIM(estado_matricula)) AS estado_matricula,
        fecha_matricula,
        ROW_NUMBER() OVER (
            PARTITION BY id_estudiante, TRIM(periodo)
            ORDER BY id_matricula
        ) AS rn
    FROM raw.raw_matriculas
)
SELECT
    id_matricula,
    id_estudiante,
    periodo,
    estado_matricula,
    fecha_matricula
FROM matriculas_limpias
WHERE rn = 1
  AND id_estudiante IN (
      SELECT id_estudiante
      FROM staging.stg_estudiantes
  );

-- ============================================================
-- 8. Verificación rápida
-- ============================================================

SELECT 'stg_carreras' AS tabla, COUNT(*) AS registros FROM staging.stg_carreras
UNION ALL
SELECT 'stg_asignaturas', COUNT(*) FROM staging.stg_asignaturas
UNION ALL
SELECT 'stg_estudiantes', COUNT(*) FROM staging.stg_estudiantes
UNION ALL
SELECT 'stg_notas', COUNT(*) FROM staging.stg_notas
UNION ALL
SELECT 'stg_asistencia', COUNT(*) FROM staging.stg_asistencia
UNION ALL
SELECT 'stg_matriculas', COUNT(*) FROM staging.stg_matriculas;