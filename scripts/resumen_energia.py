import duckdb

url = "https://fs.datosabiertos.mef.gob.pe/datastorefiles/2026-Gasto-Diario.csv"

con = duckdb.connect()

# Leemos el CSV UNA sola vez y nos quedamos solo con Gobierno Nacional
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
    -- Todos los sectores, en una sola línea cada uno (sin detalle)
    SELECT SECTOR_NOMBRE,
           CAST(NULL AS VARCHAR) AS PLIEGO,
           CAST(NULL AS VARCHAR) AS EJECUTORA,
           CAST(NULL AS VARCHAR) AS TIPO_ACT_PROY_NOMBRE,
           SUM(MONTO_PIM) AS pim,
           SUM(MONTO_DEVENGADO) AS devengado
    FROM base
    WHERE SECTOR_NOMBRE <> 'ENERGIA Y MINAS'
    GROUP BY SECTOR_NOMBRE

    UNION ALL

    -- Solo Energia y Minas, abierto por Pliego/Ejecutora/Tipo
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

resultado.to_csv("energia_minas_resumen.csv", index=False)
print(resultado)
