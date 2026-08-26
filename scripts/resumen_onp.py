import duckdb
import requests
from datetime import timezone, timedelta
from email.utils import parsedate_to_datetime

url = "https://fs.datosabiertos.mef.gob.pe/datastorefiles/2026-Gasto-Diario.csv"
SECTOR = "ECONOMIA Y FINANZAS"
FILTRO_ONP = "%NORMALIZACION PREVISIONAL%"  # ILIKE sobre PLIEGO_NOMBRE

# 1. Fecha de última actualización del archivo origen (igual que en resumen_energia.py)
resp = requests.head(url)
last_modified_raw = resp.headers.get("Last-Modified")
if last_modified_raw:
    fecha_gmt = parsedate_to_datetime(last_modified_raw)
    fecha_peru = fecha_gmt.astimezone(timezone(timedelta(hours=-5)))
    fecha_actualizacion = fecha_peru.strftime("%Y-%m-%d %H:%M:%S")
else:
    fecha_actualizacion = "No disponible"

con = duckdb.connect()

con.execute(f"""
    CREATE TEMP TABLE base AS
    SELECT SECTOR_NOMBRE, PLIEGO, PLIEGO_NOMBRE, EJECUTORA, EJECUTORA_NOMBRE,
           TIPO_ACT_PROY_NOMBRE,
           GENERICA, GENERICA_NOMBRE,
           FUENTE_FINANCIAMIENTO, FUENTE_FINANCIAMIENTO_NOMBRE,
           PRODUCTO_PROYECTO, PRODUCTO_PROYECTO_NOMBRE,
           PROGRAMA_PPTO, PROGRAMA_PPTO_NOMBRE,
           SEC_FUNC, ANO_EJE, MES_EJE,
           TIPO_TRANSACCION, SUBGENERICA, SUBGENERICA_DET, ESPECIFICA, ESPECIFICA_DET, ESPECIFICA_DET_NOMBRE,
           MONTO_PIA, MONTO_PIM, MONTO_CERTIFICADO, MONTO_COMPROMETIDO_ANUAL, MONTO_COMPROMETIDO,
           MONTO_DEVENGADO, MONTO_GIRADO
    FROM read_csv(
        '{url}',
        header = true,
        types = {{
            'PLIEGO': 'VARCHAR', 'EJECUTORA': 'VARCHAR', 'NIVEL_GOBIERNO': 'VARCHAR',
            'GENERICA': 'VARCHAR', 'FUENTE_FINANCIAMIENTO': 'VARCHAR',
            'PRODUCTO_PROYECTO': 'VARCHAR', 'PROGRAMA_PPTO': 'VARCHAR',
            'SEC_FUNC': 'VARCHAR', 'TIPO_TRANSACCION': 'VARCHAR',
            'SUBGENERICA': 'VARCHAR', 'SUBGENERICA_DET': 'VARCHAR',
            'ESPECIFICA': 'VARCHAR', 'ESPECIFICA_DET': 'VARCHAR',
            'ANO_EJE': 'INTEGER', 'MES_EJE': 'INTEGER'
        }}
    )
    WHERE NIVEL_GOBIERNO = 'E'
""")

resultado = con.execute(f"""
    WITH onp AS (
        SELECT
            TRIM(PLIEGO) || '. ' || PLIEGO_NOMBRE AS PLIEGO_D,
            TRIM(EJECUTORA) || '. ' || EJECUTORA_NOMBRE AS EJECUTORA_D,
            TIPO_ACT_PROY_NOMBRE,
            TRIM(GENERICA) || '. ' || GENERICA_NOMBRE AS GENERICA_D,
            TRIM(FUENTE_FINANCIAMIENTO) || '. ' || FUENTE_FINANCIAMIENTO_NOMBRE AS FUENTE_FINANCIAMIENTO_D,
            CASE WHEN TRIM(TIPO_ACT_PROY_NOMBRE) = 'PROYECTO'
                 THEN TRIM(PRODUCTO_PROYECTO) || '. ' || PRODUCTO_PROYECTO_NOMBRE
                 ELSE NULL END AS PRODUCTO_PROYECTO_D,
            TRIM(PROGRAMA_PPTO) || '. ' || PROGRAMA_PPTO_NOMBRE AS PROGRAMA_PPTO_D,
            SEC_FUNC,
            CONCAT_WS('.', TIPO_TRANSACCION, GENERICA, SUBGENERICA, SUBGENERICA_DET,
                      ESPECIFICA, ESPECIFICA_DET, ESPECIFICA_DET_NOMBRE) AS CLASIFICADOR,
            MES_EJE,
            CASE MES_EJE
                WHEN 1 THEN 'Ene' WHEN 2 THEN 'Feb' WHEN 3 THEN 'Mar' WHEN 4 THEN 'Abr'
                WHEN 5 THEN 'May' WHEN 6 THEN 'Jun' WHEN 7 THEN 'Jul' WHEN 8 THEN 'Ago'
                WHEN 9 THEN 'Set' WHEN 10 THEN 'Oct' WHEN 11 THEN 'Nov' WHEN 12 THEN 'Dic'
                ELSE 'Error' END AS MES,
            MAKE_DATE(ANO_EJE, MES_EJE, 1) AS FECHA,
            MONTO_PIA, MONTO_PIM, MONTO_CERTIFICADO, MONTO_COMPROMETIDO_ANUAL, MONTO_COMPROMETIDO,
            MONTO_DEVENGADO, MONTO_GIRADO
        FROM base
        WHERE SECTOR_NOMBRE = '{SECTOR}' AND PLIEGO_NOMBRE ILIKE '{FILTRO_ONP}'
    )

    -- 1. Ranking Sectores: todos los sectores menos Economia y Finanzas, solo por sector
    SELECT 'Ranking Sectores' AS NIVEL_DETALLE,
           SECTOR_NOMBRE,
           CAST(NULL AS VARCHAR) AS PLIEGO, CAST(NULL AS VARCHAR) AS EJECUTORA,
           CAST(NULL AS VARCHAR) AS TIPO_ACT_PROY_NOMBRE,
           CAST(NULL AS VARCHAR) AS GENERICA, CAST(NULL AS VARCHAR) AS FUENTE_FINANCIAMIENTO,
           CAST(NULL AS VARCHAR) AS PRODUCTO_PROYECTO, CAST(NULL AS VARCHAR) AS PROGRAMA_PPTO,
           CAST(NULL AS VARCHAR) AS SEC_FUNC, CAST(NULL AS VARCHAR) AS CLASIFICADOR,
           CAST(NULL AS INTEGER) AS MES_EJE, CAST(NULL AS VARCHAR) AS MES, CAST(NULL AS DATE) AS FECHA,
           SUM(MONTO_PIA) AS pia, SUM(MONTO_PIM) AS pim, SUM(MONTO_CERTIFICADO) AS certificado,
           SUM(MONTO_COMPROMETIDO_ANUAL) AS comp_anual, SUM(MONTO_COMPROMETIDO) AS comprometido,
           SUM(MONTO_DEVENGADO) AS devengado, SUM(MONTO_GIRADO) AS girado
    FROM base
    WHERE SECTOR_NOMBRE <> '{SECTOR}'
    GROUP BY SECTOR_NOMBRE

    UNION ALL

    -- 2. Total Sector Economia y Finanzas (todos sus pliegos, incluido ONP)
    SELECT 'Total Sector ECOFIN' AS NIVEL_DETALLE,
           SECTOR_NOMBRE,
           CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR),
           CAST(NULL AS VARCHAR),
           CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR),
           CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR),
           CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR),
           CAST(NULL AS INTEGER), CAST(NULL AS VARCHAR), CAST(NULL AS DATE),
           SUM(MONTO_PIA), SUM(MONTO_PIM), SUM(MONTO_CERTIFICADO),
           SUM(MONTO_COMPROMETIDO_ANUAL), SUM(MONTO_COMPROMETIDO),
           SUM(MONTO_DEVENGADO), SUM(MONTO_GIRADO)
    FROM base
    WHERE SECTOR_NOMBRE = '{SECTOR}'
    GROUP BY SECTOR_NOMBRE

    UNION ALL

    -- 3. Detalle Pliegos ECOFIN (menos ONP): Pliego + Ejecutora, solo totales
    SELECT 'Detalle Pliegos ECOFIN' AS NIVEL_DETALLE,
           SECTOR_NOMBRE,
           TRIM(PLIEGO) || '. ' || PLIEGO_NOMBRE,
           TRIM(EJECUTORA) || '. ' || EJECUTORA_NOMBRE,
           CAST(NULL AS VARCHAR),
           CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR),
           CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR),
           CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR),
           CAST(NULL AS INTEGER), CAST(NULL AS VARCHAR), CAST(NULL AS DATE),
           SUM(MONTO_PIA), SUM(MONTO_PIM), SUM(MONTO_CERTIFICADO),
           SUM(MONTO_COMPROMETIDO_ANUAL), SUM(MONTO_COMPROMETIDO),
           SUM(MONTO_DEVENGADO), SUM(MONTO_GIRADO)
    FROM base
    WHERE SECTOR_NOMBRE = '{SECTOR}' AND PLIEGO_NOMBRE NOT ILIKE '{FILTRO_ONP}'
    GROUP BY SECTOR_NOMBRE, PLIEGO, PLIEGO_NOMBRE, EJECUTORA, EJECUTORA_NOMBRE

    UNION ALL

    -- 4. Detalle ONP: todas las dimensiones cruzadas, incluido mensual
    SELECT 'Detalle ONP' AS NIVEL_DETALLE,
           '{SECTOR}',
           PLIEGO_D, EJECUTORA_D,
           TIPO_ACT_PROY_NOMBRE,
           GENERICA_D, FUENTE_FINANCIAMIENTO_D,
           PRODUCTO_PROYECTO_D, PROGRAMA_PPTO_D,
           SEC_FUNC, CLASIFICADOR,
           MES_EJE, MES, FECHA,
           SUM(MONTO_PIA), SUM(MONTO_PIM), SUM(MONTO_CERTIFICADO),
           SUM(MONTO_COMPROMETIDO_ANUAL), SUM(MONTO_COMPROMETIDO),
           SUM(MONTO_DEVENGADO), SUM(MONTO_GIRADO)
    FROM onp
    GROUP BY PLIEGO_D, EJECUTORA_D, TIPO_ACT_PROY_NOMBRE, GENERICA_D, FUENTE_FINANCIAMIENTO_D,
             PRODUCTO_PROYECTO_D, PROGRAMA_PPTO_D, SEC_FUNC, CLASIFICADOR, MES_EJE, MES, FECHA
""").df()

resultado["FECHA_ACTUALIZACION_ARCHIVO"] = fecha_actualizacion
resultado.to_csv("economia_finanzas_resumen.csv", index=False)

# Validaciones rápidas para detectar nombres de sector/pliego mal escritos
print(resultado["NIVEL_DETALLE"].value_counts())
print("Filas 'Detalle ONP':", (resultado["NIVEL_DETALLE"] == "Detalle ONP").sum())
print("Filas 'Detalle Pliegos ECOFIN':", (resultado["NIVEL_DETALLE"] == "Detalle Pliegos ECOFIN").sum())
print("Fecha de actualización del archivo origen (hora Perú):", fecha_actualizacion)
