# Dashboard de Ventas - Farmacias

Dashboard interactivo en Python usando Streamlit para visualizar métricas y ubicaciones de clientes (farmacias).

Requisitos
- Python 3.8+ (se recomienda usar el virtualenv provisto en `env/`)
- Instalar dependencias en `requirements.txt`

Instalación rápida (zsh):

```bash
# activar entorno virtual si quieres
source env/bin/activate
pip install -r requirements.txt
```

Ejecutar el dashboard:

```bash
streamlit run app.py
```

Qué incluye
- KPIs: ventas totales, unidades, número de registros y ticket medio.
- Series temporales de ventas por mes.
- Top productos y top clientes por revenue.
- Mapa con ubicaciones (lat/lon) extraídas de la columna `Georeferenciado`.
- Descarga del CSV filtrado.

Notas
- El CSV fuente está en `data/TblVenta_demo.csv` y usa `;` como separador.
- Si necesita métricas adicionales (márgenes, cohortes, forecast), puedo extender el dashboard.
