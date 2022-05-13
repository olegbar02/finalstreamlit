from typing import Union, Any
import fiona
import folium as folium
from folium.plugins import MarkerCluster, FastMarkerCluster
import streamlit as st
import pandas as pd
from streamlit_folium import st_folium, folium_static
from folium.features import GeoJsonTooltip
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import altair as alt
import plotly.graph_objects as go
import plotly.express as px
import geopandas
from geopy import distance
from shapely.geometry import Point, MultiPolygon, Polygon
import pydeck as pdk

from plotly.subplots import make_subplots
from shapely.wkt import dumps, loads
st.set_page_config(layout="wide")
with st.echo(code_location='below'):
    """
    # Анализ данных слива Яндекс.Еды 
    Один нехороший аналитик сервиса Яндекс.Еда слил данные заказов пользователей в открытый доступ
    Но давайте будем хорошими аналитиками и проанализируем данные о заказах пользователей сервиса Яндекс.Еда
    
    Я взял этот датасет и удалил из него персональные данные: адрес, имя пользователя, телефон
    """


    @st.experimental_singleton()
    def get_data():
        data_url = 'yangodatanorm 3.csv.zip'
        return pd.read_csv(data_url).sample(frac=0.1)


    initial_df = get_data()
    initial_df.drop('Unnamed: 0', axis=1)
    st.write(initial_df)
    df = initial_df.copy(deep=True)
    st.write(len(df))
with st.echo(code_location='below'):
    """
        После этого добавим некоторую дополнительную информацию для наших заказов
        День недели, время дня, административный округ, расстояние до центра Москвы 
    """
    # Берем дни недели и часы
    df['created_at'] = pd.to_datetime(df['created_at'], utc=True)
    df['day_of_week'] = df['created_at'].dt.day_name()
    df['Time'] = df['created_at'].dt.hour
    df['Times_of_Day'] = 'null'
    df['Times_of_Day'].mask((df['Time'] >= 6) & (df['Time'] <= 12), 'утро', inplace=True)
    df['Times_of_Day'].mask((df['Time'] > 12) & (df['Time'] <= 18), 'день', inplace=True)
    df['Times_of_Day'].mask((df['Time'] > 18) & (df['Time'] <= 23), 'вечер', inplace=True)
    df['Times_of_Day'].mask(df['Times_of_Day'] == 'null', 'ночь', inplace=True)
    df['Times_of_Day'] = df['Times_of_Day'].astype(str)


    @st.cache(persist=True)
    def get_distance():
        # Добавляем расстояние до центра Москвы
        distance_from_c = []
        for lat, lon in zip(df['location_latitude'], df['location_longitude']):
            distance_from_c.append(distance.distance((lat, lon), (55.753544, 37.621211)).km)
            # geometry.append(Point(lon, lat))
        return pd.Series(distance_from_c)


    dist = get_distance()
    df['distance_from_center'] = dist


    @st.experimental_singleton()
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


    @st.experimental_memo
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
    full_df['day_of_week'].mask(full_df['day_of_week'] == 'Friday', 'Пятница', inplace=True)
    full_df['day_of_week'].mask(full_df['day_of_week'] == 'Monday', 'Понедельник', inplace=True)
    full_df['day_of_week'].mask(full_df['day_of_week'] == 'Tuesday', 'Вторник', inplace=True)
    full_df['day_of_week'].mask(full_df['day_of_week'] == 'Wednesday', 'Среда', inplace=True)
    full_df['day_of_week'].mask(full_df['day_of_week'] == 'Thursday', 'Четверг', inplace=True)
    full_df['day_of_week'].mask(full_df['day_of_week'] == 'Saturday', 'Суббота', inplace=True)
    full_df['day_of_week'].mask(full_df['day_of_week'] == 'Sunday', 'Воскресенье', inplace=True)


    @st.experimental_singleton()
    def final_df():
        d = full_df.drop(['coords'], axis=1).copy(deep=True)
        return d


    df_final = final_df()
    df_final
    sorter = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    sorterIndex = dict(zip(sorter, range(len(sorter))))
    df_final['day_of_week_id'] = df_final['day_of_week'].map(sorterIndex)
    sorter2 = ['утро', 'день', 'вечер', 'ночь']
    sorterIndex2 = dict(zip(sorter2, range(len(sorter2))))
    df_final['time_id'] = df_final['Times_of_Day'].map(sorterIndex2)
    df_final.sort_values(['day_of_week_id', 'time_id'], inplace=True)

    """
    #### Теперь будем рисовать. Давайте сначала просто посмотрим, как наши заказы выглядят на карте 
    """

    m = folium.Map(location=[55.753544, 37.621211], zoom_start=10, width=1200)
    FastMarkerCluster(
        data=[[lat, lon] for lat, lon in zip(df_final['location_latitude'], df_final['location_longitude'])]
        , name='Заказы').add_to(m)

    folium_static(m, width=1200)
    """ Давайте посмотрим на заказы в разрезе муниципалитета
    , административного округа по среднему чеку и по количеству"""
    col1, col2 = st.columns(2)
    with col1:
        option1 = st.selectbox('Какое деление вы хотите выбрать?', ('Округа', 'Районы'))
    with col2:
        option2 = st.selectbox('Как вы хотите их сравнить?', ('Количество заказов', 'Средний чек'))

    if option1 == 'Районы':
        df_municipalities = (df_final.groupby(['district'], as_index=False)
                             .agg({'id': 'count', 'amount_charged': 'mean'})
                             .merge(moscow_geometry_df, on='district', how='left'))
        geopandas.GeoDataFrame(moscow_geometry_df[['district', 'okrug', 'geometry']]) \
            .to_file("moscow_geometry.geojson",
                     driver='GeoJSON')
        geojson = 'moscow_geometry.geojson'
        if option2 == 'Количество заказов':
            merge_col = ['district', 'id']
            scale = (df_municipalities['id'].quantile((0.5, 0.6, 0.7, 0.8))).tolist()
            legend = 'Количество заказов'
        else:
            merge_col = ['district', 'amount_charged']
            scale = (df_municipalities['amount_charged'].quantile((0.5, 0.6, 0.7, 0.8))).tolist()
            legend = 'Средний чек'
        keys = 'feature.properties.district'
        ##FROM (https://towardsdatascience.com/folium-and-choropleth-map-from-zero-to-pro-6127f9e68564)
        # tooltip = folium.features.GeoJson(
        #     data=df_municipalities.dropna(),
        #     name=legend,
        #     smooth_factor=2,
        #     style_function=lambda x: {'color': 'black', 'fillColor': 'transparent', 'weight': 0.5},
        #     tooltip=folium.features.GeoJsonTooltip(
        #         fields=[
        #             'district',
        #             'amount_charged',
        #             'id'],
        #         aliases=[
        #             'Район:',
        #             "Средний чек:",
        #             "Кол-во заказов:",
        #         ],
        #         localize=True,
        #         sticky=False,
        #         labels=True,
        #         style="""
        #                     background-color: #F0EFEF;
        #                     border: 2px solid black;
        #                     border-radius: 3px;
        #                     box-shadow: 3px;
        #                 """,
        #         max_width=800, ), highlight_function=lambda x: {'weight': 3, 'fillColor': 'grey'})
        ## END
    elif option1 == 'Округа':
        df_municipalities = (df_final.groupby(['okrug'], as_index=False)
                             .agg({'id': 'count', 'amount_charged': 'mean'})
                             .merge(geopandas.read_file('okruga.geojson')
                                    , left_on='okrug'
                                    , right_on='local_name'
                                    , how='left'))
        geojson = 'okruga.geojson'
        if option2 == 'Количество заказов':
            merge_col = ['okrug', 'id']
            scale = (df_municipalities['id'].quantile((0.3, 0.5, 0.6, 0.7, 0.8))).tolist()
            legend = 'Количество заказов'
        else:
            merge_col = ['okrug', 'amount_charged']
            scale = (df_municipalities['amount_charged'].quantile((0.3, 0.5, 0.6, 0.7, 0.8))).tolist()
            legend = 'Средний чек'
        keys = 'feature.properties.local_name'
        ##FROM (https://towardsdatascience.com/folium-and-choropleth-map-from-zero-to-pro-6127f9e68564)
        # tooltip = folium.features.GeoJson(
        #     data=df_municipalities.dropna(),
        #     name=legend,
        #     smooth_factor=2,
        #     style_function=lambda x: {'color': 'black', 'fillColor': 'transparent', 'weight': 0.5},
        #     tooltip=folium.features.GeoJsonTooltip(
        #         fields=[
        #             'okrug',
        #             'amount_charged',
        #             'id'],
        #         aliases=[
        #             'Адм. округ:',
        #             "Средний чек:",
        #             "Кол-во заказов:",
        #         ],
        #         localize=True,
        #         sticky=False,
        #         labels=True,
        #         style="""
        #                             background-color: #F0EFEF;
        #                             border: 2px solid black;
        #                             border-radius: 3px;
        #                             box-shadow: 3px;
        #                         """,
        #         max_width=800),
        #     highlight_function=lambda x: {'weight': 3, 'fillColor': 'grey'}
        # )
        ##END

    map = folium.Map(location=[55.753544, 37.621211], zoom_start=10, width=1500)

    cho = folium.Choropleth(geo_data=geojson, data=df_municipalities, columns=merge_col
                            , key_on=keys
                            , fill_color='YlOrRd'
                            , nan_fill_color="White"
                            , legend_name=legend
                            , tooltip='amount_charged'

                            ).add_to(map)
    folium_static(map, width=1200)

    '''#### Теперь давайте посмотрим на заказы в разрезе дня недели и времени дня'''
    df_weekday_time = df_final.groupby(['day_of_week', 'Times_of_Day'], as_index=False) \
        .agg({'id': 'count', 'amount_charged': 'mean'})

    # df_weekday_time['day_of_week'].mask(df_weekday_time['day_of_week'] == 'Friday', 'Пятница', inplace=True)
    # df_weekday_time['day_of_week'].mask(df_weekday_time['day_of_week'] == 'Monday', 'Понедельник', inplace=True)
    # df_weekday_time['day_of_week'].mask(df_weekday_time['day_of_week'] == 'Tuesday', 'Вторник', inplace=True)
    # df_weekday_time['day_of_week'].mask(df_weekday_time['day_of_week'] == 'Wednesday', 'Среда', inplace=True)
    # df_weekday_time['day_of_week'].mask(df_weekday_time['day_of_week'] == 'Thursday', 'Четверг', inplace=True)
    # df_weekday_time['day_of_week'].mask(df_weekday_time['day_of_week'] == 'Saturday', 'Суббота', inplace=True)
    # df_weekday_time['day_of_week'].mask(df_weekday_time['day_of_week'] == 'Sunday', 'Воскресенье', inplace=True)
    ## FROM (http://blog.quizzicol.com/2016/10/03/sorting-dates-in-python-by-day-of-week/)
    sorter = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    sorterIndex = dict(zip(sorter, range(len(sorter))))
    df_weekday_time['day_of_week_id'] = df_weekday_time['day_of_week'].map(sorterIndex)

    sorter2 = ['утро', 'день', 'вечер', 'ночь']
    sorterIndex2 = dict(zip(sorter2, range(len(sorter2))))
    df_weekday_time['time_id'] = df_weekday_time['Times_of_Day'].map(sorterIndex2)
    df_weekday_time.sort_values(['day_of_week_id', 'time_id'], inplace=True)
    ## END

    fig1 = go.Figure(data=[go.Bar(name='Количество заказов', x=
    df_weekday_time[df_weekday_time['day_of_week'] == list(df_weekday_time['day_of_week'].unique())[0]]['Times_of_Day']
                                  , y=df_weekday_time[
            df_weekday_time['day_of_week'] == list(df_weekday_time['day_of_week'].unique())[0]]['id'], yaxis='y'
                                  , offsetgroup=1)
        , go.Bar(name='Cредний чек', x=df_weekday_time[
            df_weekday_time['day_of_week'] == list(df_weekday_time['day_of_week'].unique())[0]]['Times_of_Day']
                 , y=df_weekday_time[
                df_weekday_time['day_of_week'] == list(df_weekday_time['day_of_week'].unique())[0]]['amount_charged']
                 ,yaxis="y2", offsetgroup=2)])

    frames = []
    steps = []
    for days in list(df_weekday_time['day_of_week'].unique())[1:]:
        df_weekday_time_day = df_weekday_time[df_weekday_time['day_of_week'] == days]
        frames.append(go.Frame(data=[go.Bar(name='Количество заказов', x=df_weekday_time_day['Times_of_Day']
                                            , y=df_weekday_time_day['id'], yaxis='y'
                                  , offsetgroup=1)
            , go.Bar(name='Cредний чек', x=df_weekday_time_day['Times_of_Day']
                     , y=df_weekday_time_day['amount_charged'], yaxis="y2", offsetgroup=2)], name=days))
    for days in list(df_weekday_time['day_of_week'].unique()):
        step = dict(
            label=days,
            method="animate",
            args=[[days]]
        )
        steps.append(step)
    sliders = [dict(
        currentvalue={"prefix": "День недели: ", "font": {"size": 16}},
        len=0.9,
        x=0.1,
        pad={"b": 10, "t": 50},
        steps=steps,
    )]
    fig1.update_layout(title="Количество заказов и средний чек по дням недели",
                       barmode='group',

                       xaxis_title="Время дня",
                       yaxis=dict(
                           title="Количество заказов"
                       ),
                       yaxis2=dict(
                           title="Средний чек",
                           overlaying="y",
                           side="right"
                       ),
                       ##FROM (https://habr.com/ru/post/502958/)
                       updatemenus=[dict(direction="left",
                                         pad={"r": 10, "t": 80},
                                         x=0.1,
                                         xanchor="right",
                                         y=0,
                                         yanchor="top",
                                         showactive=False,
                                         type="buttons",
                                         buttons=[dict(label="►", method="animate", args=[None, {"fromcurrent": True}]),
                                                  dict(label="❚❚", method="animate",
                                                       args=[[None], {"frame": {"duration": 0, "redraw": False},
                                                                      "mode": "immediate",
                                                                      "transition": {"duration": 0}}])])],
                       ##END
                       legend_x=1.12, width=1200
                       )

    fig1.layout.sliders = sliders
    fig1.frames = frames
    st.plotly_chart(fig1)

    """#### Теперь давайте посмотрим на тоже самое на карте"""

    ## From (https://github.com/streamlit/demo-uber-nyc-pickups/blob/main/streamlit_app.py)
    def get_map(data):
        st.pydeck_chart(
            pdk.Deck(
            map_style="mapbox://styles/mapbox/light-v9",
            initial_view_state={
                "latitude": 55.753544,
                "longitude": 37.621211,
                "zoom": 10,
                "pitch": 50,
            },
            layers=[
                pdk.Layer(
                    "HexagonLayer",
                    data=data,
                    get_position=["location_longitude", "location_latitude"],
                    radius=120,
                    elevation_scale=4,
                    elevation_range=[0, 1000],
                    pickable=True,
                    extruded=True,
                ),
            ],
        ), use_container_width=True
    )
    ## End

    day = st.select_slider('Выберете день недели', df_final['day_of_week'].unique())
    ## если что это не я дурак, а пандас, потому что не находил иначе нужную часть датасета
    if day == 'Понедельник':
        query1 = 'day_of_week=="Понедельник" and Times_of_Day=="утро"'
        query2 = 'day_of_week=="Понедельник" and Times_of_Day=="день"'
        query3 = 'day_of_week=="Понедельник" and Times_of_Day=="вечер"'
        query4 = 'day_of_week=="Понедельник" and Times_of_Day=="ночь"'
    elif day == 'Вторник':
        query1 = 'day_of_week=="Вторник" and Times_of_Day=="утро"'
        query2 = 'day_of_week=="Вторник" and Times_of_Day=="день"'
        query3 = 'day_of_week=="Вторник" and Times_of_Day=="вечер"'
        query4 = 'day_of_week=="Вторник" and Times_of_Day=="ночь"'
    elif day == 'Среда':
        query1 = 'day_of_week=="Среда" and Times_of_Day=="утро"'
        query2 = 'day_of_week=="Среда" and Times_of_Day=="день"'
        query3 = 'day_of_week=="Среда" and Times_of_Day=="вечер"'
        query4 = 'day_of_week=="Среда" and Times_of_Day=="ночь"'
    elif day == 'Четверг':
        query1 = 'day_of_week=="Четверг" and Times_of_Day=="утро"'
        query2 = 'day_of_week=="Четверг" and Times_of_Day=="день"'
        query3 = 'day_of_week=="Четверг" and Times_of_Day=="вечер"'
        query4 = 'day_of_week=="Четверг" and Times_of_Day=="ночь"'
    elif day == 'Пятница':
        query1 = 'day_of_week=="Пятница" and Times_of_Day=="утро"'
        query2 = 'day_of_week=="Пятница" and Times_of_Day=="день"'
        query3 = 'day_of_week=="Пятница" and Times_of_Day=="вечер"'
        query4 = 'day_of_week=="Пятница" and Times_of_Day=="ночь"'
    elif day == 'Суббота':
        query1 = 'day_of_week=="Суббота" and Times_of_Day=="утро"'
        query2 = 'day_of_week=="Суббота" and Times_of_Day=="день"'
        query3 = 'day_of_week=="Суббота" and Times_of_Day=="вечер"'
        query4 = 'day_of_week=="Суббота" and Times_of_Day=="ночь"'
    elif day == 'Воскресенье':
        query1 = 'day_of_week=="Воскресенье" and Times_of_Day=="утро"'
        query2 = 'day_of_week=="Воскресенье" and Times_of_Day=="день"'
        query3 = 'day_of_week=="Воскресенье" and Times_of_Day=="вечер"'
        query4 = 'day_of_week=="Воскресенье" and Times_of_Day=="ночь"'



    morning, day = st.columns(2)
    with morning:
        """#### Утро"""
        df_morn = df_final.query(query1).dropna()
        get_map(df_morn)
        """#### Вечер"""
        df_day = df_final.query(query3).dropna()
        get_map(df_day)
    with day:
        """#### День"""
        df_eve = df_final.query(query2).dropna()
        get_map(df_eve)
        """#### Ночь"""
        df_night = df_final.query(query4).dropna()
        get_map(df_night)


    """### Теперь давайте посмотрим на зависимость среднего чека и количество заказов от расстояния до центра"""
    df_dist=df_final.query('distance_from_center<100')
    coll1, coll2 = st.columns(2)
    with coll1:
        """#### По среднему чеку"""
        ## From(https://altair-viz.github.io/gallery/poly_fit_regression.html
        base = alt.Chart(df_dist).mark_circle(color="black").encode(
            alt.X("distance_from_center"), alt.Y("amount_charged"))
        polynomial_fit = [
            base.transform_regression(
                "distance_from_center", "amount_charged", method="poly", order=order, as_=["distance_from_center", str(order)]
            )
                .mark_line()
                .transform_fold([str(order)], as_=["degree", "amount_charged"])
                .encode(alt.Color("degree:N"))
            for order in [1, 3, 5]]
        #end
        st.altair_chart(alt.layer(base, *polynomial_fit))
    with coll2:
        """#### Количество заказов"""
        df_dist_2 = df_dist.groupby('distance_from_center', as_index=False).agg({'id':'count'})
        df_dist_2['distance_from_center'] = np.round(df_dist_2['distance_from_center'], 0)
        base = alt.Chart(df_dist.groupby('distance_from_center', as_index=False).agg({'id':'count'})).mark_circle(color="black").encode(
            alt.X("distance_from_center"), alt.Y("id"))
        polynomial_fit = [
            base.transform_regression(
                "distance_from_center", "count", method="poly", order=order,
                as_=["distance_from_center", str(order)]
            )
                .mark_line()
                .transform_fold([str(order)], as_=["degree", "id"])
                .encode(alt.Color("degree:N"))
            for order in [1, 3, 5]]
        # end
        st.altair_chart(alt.layer(base, *polynomial_fit))


    """### Посмотрим пользователи каких устройств больше пользуются Яндекс Едой"""
    df_final['os']='Other'
    df_final['os'].mask(df_final['user_agent'].str.contains('ios'), 'IOS', inplace=True)
    df_final['os'].mask(df_final['user_agent'].str.contains('android'), 'Android', inplace=True)

    df_os = df_final.groupby('os', as_index=False).agg({'id':'count'})
    st.plotly_chart(px.pie(df_os, names='os', values='id'))







