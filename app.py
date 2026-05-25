import streamlit as st
import folium
from streamlit_folium import st_folium
import pandas as pd
import requests
from urllib.parse import quote

st.set_page_config(page_title="맛집 지도", page_icon="🍽️", layout="wide")

SHOWS = {
    "수요미식회": "#2980B9",
    "먹을텐데":   "#E67E22",
    "또간집":     "#27AE60",
    "빕구르망":   "#8E44AD",
}


@st.cache_data
def load_data():
    return pd.read_csv("data/restaurants.csv")


@st.cache_data(ttl=86400)
def load_seoul_geojson():
    url = (
        "https://raw.githubusercontent.com/southkorea/seoul-maps/"
        "master/kostat/2013/json/seoul_municipalities_geo_simple.json"
    )
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()




def naver_url(address: str) -> str:
    return f"https://map.naver.com/p/search/{quote(address)}"


def build_map(df, selected_name=None, selected_lat=None, selected_lng=None):
    if selected_lat and selected_lng:
        center, zoom = [selected_lat, selected_lng], 16
    else:
        center, zoom = [37.5665, 126.9780], 12

    m = folium.Map(location=center, zoom_start=zoom, tiles=None)

    # 베이스: 밝은 지도
    folium.TileLayer(tiles="CartoDB positron", name="밝은 지도", show=True).add_to(m)

    # 오버레이: 지하철 노선 (단색, 투명 PNG)
    folium.TileLayer(
        tiles="https://{s}.tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png",
        attr='&copy; <a href="https://www.openrailwaymap.org/">OpenRailwayMap</a>',
        name="지하철 노선",
        overlay=True,
        show=True,
        opacity=0.9,
        max_zoom=19,
    ).add_to(m)

    # 서울시 경계
    boundary_fg = folium.FeatureGroup(name="서울시 경계", show=True)
    try:
        folium.GeoJson(
            load_seoul_geojson(),
            style_function=lambda _: {
                "fillColor": "transparent",
                "fillOpacity": 0,
                "color": "#1A5276",
                "weight": 2,
                "dashArray": "4 2",
            },
            tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["구:"], localize=True),
        ).add_to(boundary_fg)
    except Exception:
        pass
    boundary_fg.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    # 겹치는 식당 감지
    name_show_count = df.groupby("name")["show"].nunique()
    overlap_names = set(name_show_count[name_show_count > 1].index)

    # 일반 마커
    for _, row in df[~df["name"].isin(overlap_names)].iterrows():
        color = SHOWS.get(row["show"], "#555")
        url = naver_url(row["address"])
        is_selected = (row["name"] == selected_name)
        popup_html = (
            f"<b>{row['name']}</b><br>"
            f"<span style='color:{color}'>{row['show']}</span><br>"
            f"<a href='{url}' target='_blank'><small>{row['address']}</small></a>"
        )
        folium.CircleMarker(
            location=[row["lat"], row["lng"]],
            radius=12 if is_selected else 9,
            color="#FFD700" if is_selected else "white",
            weight=3 if is_selected else 1.5,
            fill=True,
            fill_color=color,
            fill_opacity=0.95 if is_selected else 0.85,
            popup=folium.Popup(popup_html, max_width=240, show=is_selected),
            tooltip=f"{row['name']} ({row['show']})",
        ).add_to(m)

    # 별 마커 (복수 출연)
    overlap_df = df[df["name"].isin(overlap_names)]
    for name, group in overlap_df.groupby("name"):
        lat = group["lat"].mean()
        lng = group["lng"].mean()
        shows_str = " · ".join(sorted(group["show"].unique()))
        addr = group.iloc[0]["address"]
        url = naver_url(addr)
        is_selected = (name == selected_name)
        popup_html = (
            f"<b>{name}</b><br>"
            f"<span style='color:#B8860B; font-weight:bold'>★ {shows_str}</span><br>"
            f"<a href='{url}' target='_blank'><small>{addr}</small></a>"
        )
        size = 28 if is_selected else 24
        star_icon = (
            f'<div style="font-size:{size}px; color:#FFD700; '
            'text-shadow: 0 0 3px #333, 0 0 6px #333; '
            'line-height:1; margin:-5px 0 0 -5px;">★</div>'
        )
        folium.Marker(
            location=[lat, lng],
            icon=folium.DivIcon(html=star_icon, icon_size=(size, size), icon_anchor=(size // 2, size // 2)),
            popup=folium.Popup(popup_html, max_width=240, show=is_selected),
            tooltip=f"★ {name} ({shows_str})",
        ).add_to(m)

    return m


def main():
    st.title("🍽️ 맛집 지도")

    df = load_data()

    if "selected_name" not in st.session_state:
        st.session_state.selected_name = None
        st.session_state.selected_lat = None
        st.session_state.selected_lng = None

    overlap_count = int((df.groupby("name")["show"].nunique() > 1).sum())

    st.sidebar.title("필터")
    selected = []
    for show, color in SHOWS.items():
        count = len(df[df["show"] == show])
        if st.sidebar.checkbox(f"{show}  ({count}곳)", value=True, key=show):
            selected.append(show)

    st.sidebar.markdown("---")
    st.sidebar.markdown("**색상 범례**")
    for show, color in SHOWS.items():
        st.sidebar.markdown(
            f'<span style="color:{color}; font-size:18px">●</span> {show}',
            unsafe_allow_html=True,
        )
    st.sidebar.markdown(
        f'<span style="color:#FFD700; font-size:18px">★</span> 복수 출연 ({overlap_count}곳)',
        unsafe_allow_html=True,
    )

    filtered = df[df["show"].isin(selected)]

    map_col, list_col = st.columns([3, 1])

    with map_col:
        m = build_map(
                filtered,
                selected_name=st.session_state.selected_name,
                selected_lat=st.session_state.selected_lat,
                selected_lng=st.session_state.selected_lng,
            )
        st_folium(m, width=None, height=650, returned_objects=[])

    with list_col:
        st.markdown(f"### 목록 ({len(filtered)}곳)")
        if st.session_state.selected_name:
            if st.button("✕ 선택 해제", use_container_width=True):
                st.session_state.selected_name = None
                st.session_state.selected_lat = None
                st.session_state.selected_lng = None
                st.rerun()
        st.markdown("")

        for show in selected:
            show_df = filtered[filtered["show"] == show]
            if show_df.empty:
                continue
            color = SHOWS[show]
            st.markdown(
                f'<span style="color:{color}; font-weight:bold">● {show}</span>',
                unsafe_allow_html=True,
            )
            for _, row in show_df.iterrows():
                is_sel = (row["name"] == st.session_state.selected_name)
                label = f"**{row['name']}**" if is_sel else row["name"]
                if st.button(label, key=f"btn_{show}_{row['name']}", use_container_width=True):
                    st.session_state.selected_name = row["name"]
                    st.session_state.selected_lat = row["lat"]
                    st.session_state.selected_lng = row["lng"]
                    st.rerun()
            st.markdown("")


if __name__ == "__main__":
    main()
