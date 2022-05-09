from typing import Union, Any
import fiona
import folium as folium
from folium.plugins import MarkerCluster, FastMarkerCluster
import streamlit as st
import pandas as pd
from streamlit_folium import st_folium, folium_static
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import altair as alt
import plotly.graph_objects as go
import plotly.express as px
import geopandas
from geopy import distance
from shapely.geometry import Point, MultiPolygon
from shapely.wkt import dumps, loads

with st.echo(code_location='below'):
    """
    # Анализ данных слива Яндекс.Еды 
    Один нехороший аналитик сервиса Яндекс.Еда слил данные заказов пользователей в открытый доступ
    Но давайте будем хорошими аналитиками и проанализируем данные о заказах пользователей сервиса Яндекс.Еда
    
    Для начала возьмем исходный датасет и удалим из него персональные данные: адрес, имя пользователя, телефон
    """


    @st.cache()
    def get_data():
        data_url = 'yangodatanorm 3.csv.zip'
        return pd.read_csv(data_url)[:500000]


    initial_df = get_data()
    initial_df[:100]
    df = initial_df.copy(deep=True)
    st.write(len(df))
with st.echo(code_location='above'):
    """
        После этого добавим некоторую дополнительную информацию для наших заказов
        День недели, время дня, административный округ, расстояние до центра Москвы 
    """
    # Берем дни недели и часы
    df['created_at'] = pd.to_datetime(df['created_at'], utc=True)
    df['day_of_week'] = df['created_at'].dt.day_name()
    df['Time'] = df['created_at'].dt.hour
    df['Times of Day'] = 'null'
    df['Times of Day'].mask((df['Time'] >= 6) & (df['Time'] <= 12), 'утро', inplace=True)
    df['Times of Day'].mask((df['Time'] > 12) & (df['Time'] <= 18), 'день', inplace=True)
    df['Times of Day'].mask((df['Time'] > 18) & (df['Time'] <= 23), 'вечер', inplace=True)
    df['Times of Day'].mask((df['Time'] > 23) & (df['Time'] < 6), 'ночь', inplace=True)
    df['Times of Day'] = df['Times of Day'].astype(str)


    @st.cache()
    def get_distance():
        # Добавляем расстояние до центра Москвы
        distance_from_c = []
        for lat, lon in zip(df['location_latitude'], df['location_longitude']):
            distance_from_c.append(distance.distance((lat, lon), (55.753544, 37.621211)).km)
            # geometry.append(Point(lon, lat))
        return pd.Series(distance_from_c)


    dist = get_distance()
    df['distance_from_center'] = dist


    @st.cache()
    def get_districts():
        # Здесь мы получаем данные о полигонах московских административных округов и районов
        # source (http://osm-boundaries.com)

        districts_df = geopandas.read_file('zip://districts.geojson.zip')
        moscow = geopandas.read_file('moscow.geojson')
        okruga = geopandas.read_file('okruga.geojson')
        moscow_geometry = list(moscow['geometry'])[0]
        moscow_districts = pd.DataFrame()
        idx = 0
        for name, poly in zip(districts_df['local_name'], districts_df['geometry']):
            if moscow_geometry.contains(poly):
                for okr, geo in zip(okruga['local_name'], okruga['geometry']):
                    if geo.contains(poly):
                        moscow_districts.at[idx, 'okrug'] = okr
                        moscow_districts.at[idx, 'district'] = name
                        moscow_districts.at[idx, 'geometry'] = poly
            else:
                continue
            idx += 1
        return moscow_districts


    moscow_geometry_df = get_districts()


    def get_coords(lat, lon):
        return Point(lon, lat)


    df['coords'] = df[['location_latitude', 'location_longitude']].apply(lambda x: get_coords(*x), axis=1)


    @st.cache(allow_output_mutation=True)
    def get_municipality():
        new_df = df.copy(deep=True)
        for idx, row in new_df.iterrows():
            coord = row.coords
            for distr, okr, geometry in zip(moscow_geometry_df['district'], moscow_geometry_df['okrug'],
                                            moscow_geometry_df['geometry']):
                if geometry.contains(coord):
                    new_df.at[idx, 'district'] = distr
                    new_df.at[idx, 'okrug'] = okr
                    break
                else:
                    continue
        return new_df


    full_df = get_municipality()
    """Я хочу анализировать только Москву, поэтому удалю заказы не из Москвы"""
    full_df.dropna(subset='district', inplace=True)


    @st.cache()
    def final_df():
        d = full_df.drop(['coords'], axis=1).copy(deep=True)
        return d


    df_final = final_df()
    df_final
with st.echo(code_location='below'):
    """
    #### Теперь будем рисовать. Давайте сначала просто посмотрим, как наши заказы выглядят на карте 
    """

    m = folium.Map(location=[55.753544, 37.621211], zoom_start=10)
    FastMarkerCluster(
        data=[[lat, lon] for lat, lon in zip(df_final['location_latitude'], df_final['location_longitude'])]
        , name='Заказы').add_to(m)


    folium_static(m)
    """А это районы Москвы по среднему чеку заказа """
    df_municipalities = (df_final.groupby(['district'], as_index=False).agg({'id': 'count', 'amount_charged': 'mean'})
                         .merge(moscow_geometry_df, on='district'))
    geopandas.GeoDataFrame(moscow_geometry_df[['district', 'okrug', 'geometry']]).to_file("moscow_geometry.geojson", driver='GeoJSON')
    map = folium.Map(location=[55.753544, 37.621211], zoom_start=10)

    ## From (https://towardsdatascience.com/folium-and-choropleth-map-from-zero-to-pro-6127f9e68564)
    scale = (df_municipalities['amount_charged'].quantile((0,0.2,0.4,0.6,0.8,1))).tolist()
    ## end
    folium.Choropleth(geo_data='moscow_geometry.geojson', data=df_municipalities, columns=['district','amount_charged']
                      , key_on='feature.properties.district'
                      , fill_color='YlOrRd'
                      ,nan_fill_color="White"
                      ,threshold_scale = scale).add_to(map)
    folium_static(map)
