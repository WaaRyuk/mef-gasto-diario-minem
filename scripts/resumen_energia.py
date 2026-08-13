import duckdb

url = "https://fs.datosabiertos.mef.gob.pe/datastorefiles/2026-Gasto-Diario.csv"

con = duckdb.connect()
resultado = con.execute(f"""
    SELECT 
        PLIEGO_NOMBRE,
        EJECUTORA_NOMBRE,
        TIPO_ACT_PROY_NOMBRE,        -- si prefieres, cambia por PRODUCTO_PROYECTO_NOMBRE
        SUM(MONTO_PIM) AS pim,
        SUM(MONTO_DEVENGADO) AS devengado
    FROM read_csv_auto('{url}')
    WHERE SECTOR = 16
       OR SECTOR_NOMBRE = 'ENERGIA Y MINAS'
    GROUP BY PLIEGO_NOMBRE, EJECUTORA_NOMBRE, TIPO_ACT_PROY_NOMBRE
    ORDER BY devengado DESC
""").df()

resultado.to_csv("energia_minas_resumen.csv", index=False)
print(resultado)
