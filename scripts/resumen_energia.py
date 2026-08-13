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
           MONTO_PIM, MONTO_DEVENGADO
    FROM read_csv(
        '{url}',
        header = true,
        types = {{
            'SECTOR': 'VARCHAR',
            'PLIEGO': 'VARCHAR',
            'EJECUTORA': 'VARCHAR',
            'NIVEL_GOBIERNO': 'VARCHAR'
        }}
    )
    WHERE NIVEL_GOBIERNO = 'E'
""")
 
resultado = con.execute("""
    -- Todos los sectores (menos Energia y Minas), ahora abiertos por Tipo Actividad/Proyecto
    SELECT SECTOR_NOMBRE,
           CAST(NULL AS VARCHAR) AS PLIEGO,
           CAST(NULL AS VARCHAR) AS EJECUTORA,
           TIPO_ACT_PROY_NOMBRE,
           SUM(MONTO_PIM) AS pim,
           SUM(MONTO_DEVENGADO) AS devengado
    FROM base
    WHERE SECTOR_NOMBRE <> 'ENERGIA Y MINAS'
    GROUP BY SECTOR_NOMBRE, TIPO_ACT_PROY_NOMBRE
    UNION ALL
    -- Solo Energia y Minas, con detalle completo por Pliego/Ejecutora/Tipo
    SELECT SECTOR_NOMBRE,
           TRIM(PLIEGO) || '. ' || PLIEGO_NOMBRE AS PLIEGO,
           TRIM(EJECUTORA) || '. ' || EJECUTORA_NOMBRE AS EJECUTORA,
           TIPO_ACT_PROY_NOMBRE,
           SUM(MONTO_PIM) AS pim,
           SUM(MONTO_DEVENGADO) AS devengado
    FROM base
    WHERE SECTOR_NOMBRE = 'ENERGIA Y MINAS'
    GROUP BY SECTOR_NOMBRE, PLIEGO, PLIEGO_NOMBRE, EJECUTORA, EJECUTORA_NOMBRE, TIPO_ACT_PROY_NOMBRE
    ORDER BY SECTOR_NOMBRE, pim DESC
""").df()
 
# Agregamos la fecha de actualización (ya en hora Perú) como columna fija en todas las filas
resultado["FECHA_ACTUALIZACION_ARCHIVO"] = fecha_actualizacion
 
resultado.to_csv("energia_minas_resumen.csv", index=False)
print(resultado)
print("Fecha de actualización del archivo origen (hora Perú):", fecha_actualizacion)

resultado.to_csv("energia_minas_resumen.csv", index=False)
print(resultado)
