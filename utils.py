import pandas as pd
from typing import Optional, Tuple


def _to_number(s: Optional[str]) -> Optional[float]:
    """Normaliza y convierte una representación numérica con distintos formatos.

    Reemplaza puntos de miles y comas decimales, quita símbolos de moneda y convierte a float.
    Ejemplos manejados: "1.234,56", "1234.56", "$1,234.56", "1 234,56"
    """
    if pd.isna(s):
        return None
    if not isinstance(s, str):
        try:
            return float(s)
        except Exception:
            return None
    s = s.strip()
    # quitar símbolos comunes
    for ch in ['$', 'US$', 'Bs', 'Bs.', '€', '¢']:
        s = s.replace(ch, '')
    # eliminar espacios
    s = s.replace(' ', '')
    # si tiene formato europeo 1.234,56 -> convertir a 1234.56
    if s.count(',') == 1 and s.count('.') > 0:
        # asumo que punto es separador de miles y coma decimal
        s = s.replace('.', '')
        s = s.replace(',', '.')
    else:
        # solo reemplazar comas por punto cuando sean decimales
        if s.count(',') == 1 and s.count('.') == 0:
            s = s.replace(',', '.')
        else:
            # remover separadores de miles adicionales
            s = s.replace(',', '')
    try:
        return float(s)
    except Exception:
        return None


def _extract_latlon(val: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    if pd.isna(val) or not isinstance(val, str) or ',' not in val:
        return None, None
    try:
        lat_str, lon_str = val.split(',')
        return float(lat_str), float(lon_str)
    except Exception:
        # intentar con espacio
        try:
            parts = val.split()
            if len(parts) >= 2:
                return float(parts[0]), float(parts[1])
        except Exception:
            return None, None
    return None, None


def load_sales_csv(path: str, geo_cluster_precision: int = 3) -> pd.DataFrame:
    """Carga y normaliza el CSV de ventas.

    - Detecta separador `;`.
    - Parsea `FechaVta` con dayfirst=True y marca fechas inválidas en `FechaVta_valid`.
    - Normaliza columnas numéricas y crea columnas `revenue_val` (ValVentaLi) y `revenue_vta` (VtaFacturada).
    - Extrae `lat` y `lon` desde `Georeferenciado` si existe y crea `geo_cluster` por redondeo.
    - Calcula `margin` y `margin_pct` si hay `Costo` y `ValVentaLi`.
    """
    df = pd.read_csv(path, sep=';', dtype=str)
    df.columns = [c.strip() for c in df.columns]

    # Normalizar numerics
    numeric_cols = ['Unidades', 'VtaFacturada', 'Costo', 'ValVentaLi']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).map(_to_number)

    # Parse date and flag invalids
    if 'FechaVta' in df.columns:
        df['FechaVta_raw'] = df['FechaVta']
        df['FechaVta'] = pd.to_datetime(df['FechaVta'], dayfirst=True, errors='coerce')
        df['FechaVta_valid'] = df['FechaVta'].notna()
    else:
        df['FechaVta_valid'] = False

    # Prepare revenue alternatives
    df['revenue_val'] = df['ValVentaLi'] if 'ValVentaLi' in df.columns else None
    df['revenue_vta'] = df['VtaFacturada'] if 'VtaFacturada' in df.columns else None

    # Create a default revenue — use VtaFacturada (ignore ValVentaLi as requested)
    # This makes the dashboard and aggregations rely on the invoiced sales amount.
    df['revenue_default'] = df['revenue_vta'].fillna(df['revenue_val'])

    # Extract lat/lon
    df['lat'] = None
    df['lon'] = None
    if 'Georeferenciado' in df.columns:
        lat_list = []
        lon_list = []
        for val in df['Georeferenciado'].fillna(''):
            lat, lon = _extract_latlon(val)
            lat_list.append(lat)
            lon_list.append(lon)
        df['lat'] = lat_list
        df['lon'] = lon_list

    # Conveniences
    if 'NombreComercial' in df.columns:
        df['cliente'] = df['NombreComercial']
    if 'DescMaterial' in df.columns:
        df['producto'] = df['DescMaterial']
    if 'DescGrArticulo' in df.columns:
        df['categoria'] = df['DescGrArticulo']

    # City / zone
    if 'Ciudad' in df.columns:
        df['ciudad'] = df['Ciudad']
    if 'ZonaVenta' in df.columns:
        df['zona'] = df['ZonaVenta']

    # Geo clustering simple: agrupa por lat/lon redondeados
    try:
        df['geo_cluster'] = df.apply(lambda r: (round(r['lat'], geo_cluster_precision), round(r['lon'], geo_cluster_precision)) if pd.notna(r['lat']) and pd.notna(r['lon']) else (None, None), axis=1)
    except Exception:
        df['geo_cluster'] = None

    # Margen
    if 'Costo' in df.columns and 'ValVentaLi' in df.columns:
        df['margin'] = df['ValVentaLi'] - df['Costo']
        df['margin_pct'] = df['margin'] / df['ValVentaLi'].replace({0: pd.NA})

    return df


def aggregate_geo_clusters(df: pd.DataFrame, precision: int = 3, revenue_col: str = 'revenue_vta') -> pd.DataFrame:
    """Agrega el dataframe por clusters geográficos redondeando lat/lon.

    Devuelve un DataFrame con columnas: 'cluster', 'latitude', 'longitude', 'revenue'.
    Omite filas sin lat/lon.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=['cluster', 'latitude', 'longitude', 'revenue'])

    if 'lat' not in df.columns or 'lon' not in df.columns:
        return pd.DataFrame(columns=['cluster', 'latitude', 'longitude', 'revenue'])

    # Copiar subset con lat/lon y revenue
    tmp = df[['lat', 'lon', revenue_col]].dropna(subset=['lat', 'lon'])
    if tmp.empty:
        return pd.DataFrame(columns=['cluster', 'latitude', 'longitude', 'revenue'])

    # Crear cluster key
    try:
        tmp = tmp.copy()
        tmp['cluster'] = tmp.apply(lambda r: (round(float(r['lat']), int(precision)), round(float(r['lon']), int(precision))), axis=1)
    except Exception:
        # Fallback: no clustering possible
        tmp['cluster'] = None

    # Agrupar por cluster
    agg = tmp.groupby('cluster').agg(
        revenue=(revenue_col, 'sum'),
        latitude=('lat', 'mean'),
        longitude=('lon', 'mean'),
        count=(revenue_col, 'count')
    ).reset_index()

    # Filtrar clusters nulos
    agg = agg[agg['cluster'].notna()]

    # Ordenar por revenue
    agg = agg.sort_values('revenue', ascending=False).reset_index(drop=True)

    return agg[['cluster', 'latitude', 'longitude', 'revenue', 'count']]
