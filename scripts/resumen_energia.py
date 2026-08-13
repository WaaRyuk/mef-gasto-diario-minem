import duckdb

url = "https://fs.datosabiertos.mef.gob.pe/datastorefiles/2026-Gasto-Diario.csv"

con = duckdb.connect()
resultado = con.execute(f"""
    SELECT 
        PLIEGO_NOMBRE,
        EJECUTORA_NOMBRE,
        TIPO_ACT_PROY_NOMBRE,
        SUM(MONTO_PIM) AS pim,
        SUM(MONTO_DEVENGADO) AS devengado
    FROM read_csv(
        '{url}',
        header = true,
        types = {{
            'SECTOR': 'VARCHAR',
            'PLIEGO': 'VARCHAR',
            'NIVEL_GOBIERNO': 'VARCHAR'
        }}
    )
    WHERE TRIM(SECTOR) = '16'
       OR SECTOR_NOMBRE = 'ENERGIA Y MINAS'
      AND NIVEL_GOBIERNO != 'R'
    GROUP BY PLIEGO_NOMBRE, EJECUTORA_NOMBRE, TIPO_ACT_PROY_NOMBRE
    ORDER BY devengado DESC
""").df()

resultado.to_csv("energia_minas_resumen.csv", index=False)
print(resultado)
