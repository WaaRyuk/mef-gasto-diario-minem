import duckdb
import requests
from datetime import timezone, timedelta
from email.utils import parsedate_to_datetime

url = "https://fs.datosabiertos.mef.gob.pe/datastorefiles/2026-Gasto-Diario.csv"

# 1. Obtenemos la fecha de última modificación del archivo origen (sin descargarlo)
resp = requests.head(url)
last_modified_raw = resp.headers.get("Last-Modified")  # viene en GMT, ej: "Thu, 13 Aug 2026 14:11:34 GMT"

if last_modified_raw:
    fecha_gmt = parsedate_to_datetime(last_modified_raw)  # datetime con tzinfo UTC
    fecha_peru = fecha_gmt.astimezone(timezone(timedelta(hours=-5)))  # Perú = GMT-5, sin horario de verano
    fecha_actualizacion = fecha_peru.strftime("%Y-%m-%d %H:%M:%S")
else:
    fecha_actualizacion = "No disponible"

con = duckdb.connect()
con.execute(f"""
    CREATE TEMP TABLE base AS
    SELECT SECTOR_NOMBRE,
           PLIEGO, PLIEGO_NOMBRE,
           EJECUTORA, EJECUTORA_NOMBRE,
           TIPO_ACT_PROY_NOMBRE,
           GENERICA, GENERICA_NOMBRE,
           FUENTE_FINANCIAMIENTO, FUENTE_FINANCIAMIENTO_NOMBRE,
           PRODUCTO_PROYECTO, PRODUCTO_PROYECTO_NOMBRE,
           PROGRAMA_PPTO, PROGRAMA_PPTO_NOMBRE,
           MONTO_PIM,
           MONTO_CERTIFICADO,
           MONTO_COMPROMETIDO_ANUAL,
           MONTO_COMPROMETIDO,
           MONTO_DEVENGADO
    FROM read_csv(
        '{url}',
        header = true,
        types = {{
            'SECTOR': 'VARCHAR',
            'PLIEGO': 'VARCHAR',
            'EJECUTORA': 'VARCHAR',
            'NIVEL_GOBIERNO': 'VARCHAR',
            'GENERICA': 'VARCHAR',
            'FUENTE_FINANCIAMIENTO': 'VARCHAR',
            'PRODUCTO_PROYECTO': 'VARCHAR',
            'PROGRAMA_PPTO': 'VARCHAR'
        }}
    )
    WHERE NIVEL_GOBIERNO = 'E'
""")

resultado = con.execute("""
    WITH minem AS (
        SELECT SECTOR_NOMBRE,
               TRIM(PLIEGO) || '. ' || PLIEGO_NOMBRE AS PLIEGO,
               TRIM(EJECUTORA) || '. ' || EJECUTORA_NOMBRE AS EJECUTORA,
               TIPO_ACT_PROY_NOMBRE,
               TRIM(GENERICA) || '. ' || GENERICA_NOMBRE AS GENERICA,
               TRIM(FUENTE_FINANCIAMIENTO) || '. ' || FUENTE_FINANCIAMIENTO_NOMBRE AS FUENTE_FINANCIAMIENTO,
               CASE WHEN TRIM(TIPO_ACT_PROY_NOMBRE) = 'PROYECTO'
                    THEN TRIM(PRODUCTO_PROYECTO) || '. ' || PRODUCTO_PROYECTO_NOMBRE
                    ELSE NULL END AS PRODUCTO_PROYECTO,
               TRIM(PROGRAMA_PPTO) || '. ' || PROGRAMA_PPTO_NOMBRE AS PROGRAMA_PPTO,
               MONTO_PIM, MONTO_CERTIFICADO, MONTO_COMPROMETIDO_ANUAL, MONTO_COMPROMETIDO, MONTO_DEVENGADO
        FROM base
        WHERE SECTOR_NOMBRE = 'ENERGIA Y MINAS'
    )

    -- 1. Ranking de todos los sectores (menos Energia y Minas), solo por Tipo Actividad/Proyecto
    SELECT 'Ranking Sectores' AS NIVEL_DETALLE,
           SECTOR_NOMBRE,
           CAST(NULL AS VARCHAR) AS PLIEGO,
           CAST(NULL AS VARCHAR) AS EJECUTORA,
           TIPO_ACT_PROY_NOMBRE,
           CAST(NULL AS VARCHAR) AS GENERICA,
           CAST(NULL AS VARCHAR) AS FUENTE_FINANCIAMIENTO,
           CAST(NULL AS VARCHAR) AS PRODUCTO_PROYECTO,
           CAST(NULL AS VARCHAR) AS PROGRAMA_PPTO,
           SUM(MONTO_PIM) AS pim,
           SUM(MONTO_CERTIFICADO) AS certificado,
           SUM(MONTO_COMPROMETIDO_ANUAL) AS comp_anual,
           SUM(MONTO_COMPROMETIDO) AS comprometido,
           SUM(MONTO_DEVENGADO) AS devengado
    FROM base
    WHERE SECTOR_NOMBRE <> 'ENERGIA Y MINAS'
    GROUP BY SECTOR_NOMBRE, TIPO_ACT_PROY_NOMBRE

    UNION ALL

    -- 2. Detalle completo de Energia y Minas: Pliego + Ejecutora + Tipo + Generica +
    --    Fuente Financiamiento + Producto/Proyecto + Programa Pptal, todo junto por fila.
    --    En Power BI, cada visual agrupa/filtra por la(s) columna(s) que necesite.
    SELECT 'Detalle MINEM' AS NIVEL_DETALLE,
           SECTOR_NOMBRE,
           PLIEGO,
           EJECUTORA,
           TIPO_ACT_PROY_NOMBRE,
           GENERICA,
           FUENTE_FINANCIAMIENTO,
           PRODUCTO_PROYECTO,
           PROGRAMA_PPTO,
           SUM(MONTO_PIM) AS pim,
           SUM(MONTO_CERTIFICADO) AS certificado,
           SUM(MONTO_COMPROMETIDO_ANUAL) AS comp_anual,
           SUM(MONTO_COMPROMETIDO) AS comprometido,
           SUM(MONTO_DEVENGADO) AS devengado
    FROM minem
    GROUP BY SECTOR_NOMBRE, PLIEGO, EJECUTORA, TIPO_ACT_PROY_NOMBRE, GENERICA,
             FUENTE_FINANCIAMIENTO, PRODUCTO_PROYECTO, PROGRAMA_PPTO

    ORDER BY NIVEL_DETALLE, SECTOR_NOMBRE, pim DESC
""").df()

# Agregamos la fecha de actualización (ya en hora Perú) como columna fija en todas las filas
resultado["FECHA_ACTUALIZACION_ARCHIVO"] = fecha_actualizacion

resultado.to_csv("energia_minas_resumen.csv", index=False)
print(resultado)
print("Fecha de actualización del archivo origen (hora Perú):", fecha_actualizacion)
