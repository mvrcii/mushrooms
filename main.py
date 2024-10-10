import os

import dash
import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import plotly.express as px
from dash import dcc, html, Output, Input
from dotenv import load_dotenv
from shapely.geometry import Polygon

load_dotenv()
mapbox_token = os.getenv('MAPBOX_TOKEN')

# Load your data
data = pd.read_csv('data.csv', sep='\t')

colors = [
    'rgb(255,245,240)', 'rgb(254,224,210)', 'rgb(252,187,161)',
    'rgb(252,146,114)', 'rgb(251,106,74)', 'rgb(239,59,44)',
    'rgb(203,24,29)', 'rgb(165,15,21)', 'rgb(103,0,13)'
]

app = dash.Dash(__name__)


def zoom_to_h3_resolution(zoom_level):
    return min(max((zoom_level // 2 + 2), 3), 10)


def rgb_to_rgba(color, opacity=0.5):
    rgb_values = color.replace('rgb(', '').replace(')', '').split(',')
    return f'rgba({rgb_values[0].strip()},{rgb_values[1].strip()},{rgb_values[2].strip()},{opacity})'


def compute_hexbin(data, h3_resolution):
    data['h3_index'] = data.apply(
        lambda row: h3.geo_to_h3(row['decimalLatitude'], row['decimalLongitude'], h3_resolution), axis=1)
    hex_counts = data.groupby('h3_index').size().reset_index(name='count')
    hex_counts['geometry'] = hex_counts['h3_index'].apply(lambda x: Polygon(h3.h3_to_geo_boundary(x, geo_json=True)))
    return gpd.GeoDataFrame(hex_counts, geometry='geometry', crs='EPSG:4326')


app.layout = html.Div([
    dcc.Graph(id='hexbin-map', config={'scrollZoom': True, 'displayModeBar': True, 'displaylogo': False},
              className='mapbox'),
    html.Div(id='color-scale-container', className='color-scale-container')
], className='main-container')


@app.callback(
    [Output('hexbin-map', 'figure'), Output('color-scale-container', 'children')],
    [Input('hexbin-map', 'relayoutData')]
)
def update_map(relayoutData):
    zoom_level = relayoutData.get('mapbox.zoom', 5) if relayoutData else 5
    h3_resolution = zoom_to_h3_resolution(zoom_level)

    gdf = compute_hexbin(data, h3_resolution)

    # Apply quantile-based scaling
    num_colors = len(colors)
    quantiles = pd.qcut(gdf['count'], num_colors, labels=False, duplicates='drop')
    gdf['count_quantile'] = quantiles

    # Generate breaks and labels based on quantiles
    breaks = gdf['count'].quantile(np.linspace(0, 1, num_colors + 1))
    labels = [f"{int(round(breaks.iloc[i]))} - {int(round(breaks.iloc[i + 1]))}" for i in range(num_colors)]

    # Create individual color blocks for the legend
    color_scale_children = [
        html.Div(
            labels[i],
            className='color-block',
            style={
                'backgroundColor': '#262626',  # Base background color
                'backgroundImage': f'linear-gradient({rgb_to_rgba(colors[i])}, {rgb_to_rgba(colors[i])})'
            }
        ) for i in range(len(colors))
    ]

    # Create the map figure using quantile-based color scaling
    fig = px.choropleth_mapbox(
        gdf, geojson=gdf.geometry.__geo_interface__, locations=gdf.index, color='count_quantile',
        color_continuous_scale=colors, range_color=(0, num_colors - 1),
        mapbox_style='dark', zoom=zoom_level,
        center={'lat': data['decimalLatitude'].mean(), 'lon': data['decimalLongitude'].mean()},
        opacity=0.5, hover_data={'count': True}
    )

    # Hide default colorbar
    fig.update_coloraxes(showscale=False)
    fig.update_layout(mapbox_accesstoken=mapbox_token, margin={"r": 0, "t": 0, "l": 0, "b": 0}, uirevision='constant')

    return fig, color_scale_children


if __name__ == '__main__':
    app.run_server(debug=True, dev_tools_ui=False)
