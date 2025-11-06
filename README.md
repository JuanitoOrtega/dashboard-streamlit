# Trabajo final Módulo Data Visualization and Visual Analytics - MIAV1E3

# Maestría Ciencia de Datos e Inteligencia Artificial

Maestrantes
```bash
# JUANITO ORTEGA GUZMAN
# CRISTHIAN GERARDO BARRANCOS HARRIAGUE
# ERIKA MILENKA URIONA URQUIETA 
# RONAL SILVIO CALLISAYA MERLO
# GROVER STEVEN VALVERDE SAAVEDRA
# PERSEO ANDRADE MERCADO
```

## Dashboard de Ventas

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
