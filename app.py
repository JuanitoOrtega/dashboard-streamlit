import streamlit as st
import pandas as pd
import plotly.express as px
import pydeck as pdk
from utils import load_sales_csv


st.set_page_config(page_title="Dashboard de Ventas - Farmacias", layout="wide")


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    return load_sales_csv(path)


DATA_PATH = "data/TblVenta.csv"

df = load_data(DATA_PATH)

st.title("Dashboard de Ventas")

# Sidebar filtros
st.sidebar.header("Filtros")

# Fecha: manejar inválidas
min_date = df['FechaVta'].dropna().min() if 'FechaVta' in df.columns else None
max_date = df['FechaVta'].dropna().max() if 'FechaVta' in df.columns else None

if min_date is None or max_date is None:
    date_range = st.sidebar.date_input("Rango fechas (no hay fechas válidas)")
else:
    date_range = st.sidebar.date_input("Rango fechas", value=(min_date, max_date))

exclude_invalid_dates = st.sidebar.checkbox("Excluir registros con FechaVta inválida", value=True)

# Métrica de revenue (fija a VtaFacturada según solicitud)
rev_key = 'vta'

# Categoria / producto / cliente
categorias = df['categoria'].dropna().unique().tolist() if 'categoria' in df.columns else []
selected_cats = st.sidebar.multiselect("Categorías", options=sorted(categorias), default=sorted(categorias)[:5])

productos = df['producto'].dropna().unique().tolist() if 'producto' in df.columns else []
selected_prods = st.sidebar.multiselect("Productos (filtrar)", options=sorted(productos), max_selections=10)

clientes = df['cliente'].dropna().unique().tolist() if 'cliente' in df.columns else []
selected_clients = st.sidebar.multiselect("Clientes", options=sorted(clientes), max_selections=10)

# Ciudad / Zona
ciudades = df['ciudad'].dropna().unique().tolist() if 'ciudad' in df.columns else []
selected_ciudades = st.sidebar.multiselect("Ciudades", options=sorted(ciudades), max_selections=10)

zonas = df['zona'].dropna().unique().tolist() if 'zona' in df.columns else []
selected_zonas = st.sidebar.multiselect("Zonas", options=sorted(zonas), max_selections=10)

# Opciones avanzadas en un expander
with st.sidebar.expander("Avanzado / Mapa", expanded=False):
    geo_precision = st.slider("Precisión geoclustering (decimales)", min_value=0, max_value=6, value=3, help="Más decimales = clusters más precisos")
    show_points = st.checkbox("Mostrar puntos individuales en el mapa", value=False)
    heatmap_radius = st.slider("Radio heatmap (px)", min_value=10, max_value=200, value=50)


# Apply filters
filtered = df.copy()

# Excluir inválidos si se solicita
if exclude_invalid_dates and 'FechaVta_valid' in filtered.columns:
    filtered = filtered[filtered['FechaVta_valid'] == True]

if date_range and isinstance(date_range, tuple) and len(date_range) == 2 and 'FechaVta' in filtered.columns:
    start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    filtered = filtered[(filtered['FechaVta'] >= start) & (filtered['FechaVta'] <= end)]

if selected_cats:
    filtered = filtered[filtered['categoria'].isin(selected_cats)]

if selected_prods:
    filtered = filtered[filtered['producto'].isin(selected_prods)]

if selected_clients:
    filtered = filtered[filtered['cliente'].isin(selected_clients)]

if selected_ciudades:
    filtered = filtered[filtered['ciudad'].isin(selected_ciudades)]

if selected_zonas:
    filtered = filtered[filtered['zona'].isin(selected_zonas)]

# Crear columna de revenue usada según selección
if rev_key == 'val':
    filtered['revenue_used'] = filtered['revenue_val']
elif rev_key == 'vta':
    filtered['revenue_used'] = filtered['revenue_vta']
else:
    filtered['revenue_used'] = filtered['revenue_default']

# Nota: la agregación por cluster se realiza usando una función cacheada para mejorar perf
@st.cache_data
def _get_cluster_agg(df_snapshot, precision: int, revenue_col: str):
    # df_snapshot será serializado por streamlit cache; llamar a utils.aggregate_geo_clusters
    from utils import aggregate_geo_clusters
    return aggregate_geo_clusters(df_snapshot, precision=precision, revenue_col=revenue_col)

# Recalcular clusters usando la función cacheada
cluster_agg = pd.DataFrame()
if 'lat' in filtered.columns and 'lon' in filtered.columns:
    try:
        # pasar la columna ya seleccionada de revenue
        filtered = filtered.copy()
        # usar 'revenue_used' como la métrica activa
        cluster_agg = _get_cluster_agg(filtered, int(geo_precision), 'revenue_used')
        # crear columna geo_cluster si no existe (para compatibilidad con otras partes del código)
        if 'geo_cluster' not in filtered.columns:
            filtered['geo_cluster'] = None
    except Exception:
        cluster_agg = pd.DataFrame()

# KPIs
col1, col2, col3, col4 = st.columns(4)

total_rev = filtered['revenue_used'].sum(skipna=True)
total_units = filtered['Unidades'].sum(skipna=True) if 'Unidades' in filtered.columns else filtered['revenue_used'].count()
num_invoices = filtered.shape[0]
avg_ticket = total_rev / num_invoices if num_invoices else 0

col1.metric("Ventas totales (moneda)", f"{total_rev:,.2f}")
col2.metric("Unidades vendidas", f"{int(total_units) if pd.notna(total_units) else 0}")
col3.metric("Nº de registros (facturas)", f"{num_invoices}")
col4.metric("Ticket medio", f"{avg_ticket:,.2f}")

# Indicador de registros con fecha inválida
if 'FechaVta_valid' in df.columns:
    n_invalid = (~df['FechaVta_valid']).sum()
    if n_invalid > 0:
        st.sidebar.warning(f"Registros con FechaVta inválida en total: {int(n_invalid)}. Puedes excluirlos con el filtro.")

st.markdown("---")

# Time series
st.subheader("Ventas en el tiempo")
if 'FechaVta' in filtered.columns and filtered['FechaVta'].notna().any():
    # usar 'ME' (month end) en lugar de 'M' para evitar warning de pandas
    ts = filtered.set_index('FechaVta').resample('ME')['revenue_used'].sum().reset_index()
    fig_ts = px.line(ts, x='FechaVta', y='revenue_used', title='Ventas mensuales', labels={'revenue_used': 'Revenue'})
    st.plotly_chart(fig_ts, width='stretch')
else:
    st.info("No hay fechas válidas para la serie temporal con los filtros actuales.")

left, right = st.columns([2,1])

with left:
    st.subheader("Top productos por venta")
    top_prod = filtered.groupby('producto')['revenue_used'].sum().sort_values(ascending=False).head(15).reset_index()
    fig_bar = px.bar(top_prod, x='revenue_used', y='producto', orientation='h', title='Top productos (por revenue)')
    st.plotly_chart(fig_bar, width='stretch')

    st.subheader("Top clientes")
    top_cli = filtered.groupby('cliente')['revenue_used'].sum().sort_values(ascending=False).head(15).reset_index()
    fig_cli = px.bar(top_cli, x='revenue_used', y='cliente', orientation='h', title='Top clientes (por revenue)')
    st.plotly_chart(fig_cli, width='stretch')

    # Agregaciones por ciudad / zona
    if 'ciudad' in filtered.columns:
        st.subheader("Ventas por ciudad")
        by_city = filtered.groupby('ciudad')['revenue_used'].sum().sort_values(ascending=False).reset_index()
    fig_city = px.bar(by_city.head(20), x='revenue_used', y='ciudad', orientation='h', title='Top ciudades por revenue')
    st.plotly_chart(fig_city, width='stretch')

    if 'zona' in filtered.columns:
        st.subheader("Ventas por zona")
        by_zone = filtered.groupby('zona')['revenue_used'].sum().sort_values(ascending=False).reset_index()
    fig_zone = px.bar(by_zone.head(20), x='revenue_used', y='zona', orientation='h', title='Top zonas por revenue')
    st.plotly_chart(fig_zone, width='stretch')

with right:
    st.subheader("Mapa de ventas (ubicaciones de clientes)")
    map_df = filtered[['lat','lon','revenue_used','cliente','geo_cluster']].dropna(subset=['lat','lon'])
    if not map_df.empty:
        mid_lat = map_df['lat'].mean()
        mid_lon = map_df['lon'].mean()

        # Opcional: mostrar puntos individuales
        if show_points:
            layer = pdk.Layer(
                "ScatterplotLayer",
                data=map_df,
                get_position='[lon, lat]',
                get_radius= "revenue_used * 10",
                radius_scale=1,
                get_fill_color='[255, 140, 0, 140]',
                pickable=True,
            )
            view_state = pdk.ViewState(latitude=mid_lat, longitude=mid_lon, zoom=10)
            r = pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={"text":"{cliente}\nRevenue: {revenue_used}"})
            st.pydeck_chart(r)

        # Heatmap usando agregación cacheada
        st.subheader("Heatmap de ventas (geoclustering)")
        if not cluster_agg.empty:
            # cluster_agg ya contiene columnas latitude/longitude/revenue
            heat_data = cluster_agg.rename(columns={'latitude':'latitude','longitude':'longitude','revenue':'revenue'})
            # Asegurar nombres: pydeck espera 'longitude' y 'latitude' o usar get_position
            heat_layer = pdk.Layer(
                "HeatmapLayer",
                data=heat_data,
                get_position='[longitude, latitude]',
                get_weight='revenue',
                radiusPixels=int(heatmap_radius),
            )
            view_state_h = pdk.ViewState(latitude=heat_data['latitude'].mean(), longitude=heat_data['longitude'].mean(), zoom=10)
            deck = pdk.Deck(layers=[heat_layer], initial_view_state=view_state_h)
            st.pydeck_chart(deck)
        else:
            st.info("No hay clusters para mostrar en el heatmap con los filtros actuales.")
    else:
        st.info("No hay coordenadas válidas en los datos filtrados.")

st.markdown("---")

# Análisis de márgenes (calculado a partir de la métrica de ventas usada y el costo)
if 'Costo' in filtered.columns and 'revenue_used' in filtered.columns:
    st.subheader("Análisis de márgenes")
    # calcular margen por fila: ventas usadas - costo
    margin_series = (filtered['revenue_used'].fillna(0) - filtered['Costo'].fillna(0))
    total_margin = margin_series.sum()
    revenue_total = filtered['revenue_used'].sum()
    margin_pct = (total_margin / revenue_total) if revenue_total else 0
    mcol1, mcol2 = st.columns(2)
    mcol1.metric("Margen total", f"{total_margin:,.2f}")
    mcol2.metric("% Margen sobre ventas", f"{(margin_pct*100):.2f}%")

    st.write("Top productos por margen")
    top_margin = (
        pd.DataFrame({'producto': filtered['producto'], 'margin': margin_series})
        .dropna(subset=['producto'])
        .groupby('producto')['margin']
        .sum()
        .sort_values(ascending=False)
        .head(15)
        .reset_index()
    )
    fig_margin = px.bar(top_margin, x='margin', y='producto', orientation='h')
    st.plotly_chart(fig_margin, width='stretch')

    st.caption("Nota: el margen se calcula como (ventas usadas - costo). La métrica de ventas usada en el dashboard es la facturada.")

st.subheader("Tabla filtrada y descarga")
st.dataframe(filtered.sample(min(200, len(filtered))))

csv = filtered.to_csv(index=False, sep=';')
st.download_button(label="Descargar CSV filtrado", data=csv, file_name='ventas_filtradas.csv', mime='text/csv')

st.markdown("---")
st.caption("Dashboard generado con Streamlit — columnas detectadas: " + ", ".join(df.columns[:10]))
