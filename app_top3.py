import pandas as pd
import dash
from dash import html, dcc, callback, Input, Output
import dash_leaflet as dl
from colour import Color

# ----------------------------
# 1. 数据加载与预处理
# ----------------------------
# 读取学校数据
df_schools = pd.read_csv("schools.csv")

# 过滤私立学校（不区分大小写）
df_schools = df_schools[
    ~df_schools["description"].str.contains("private", case=False, na=False)
]

# 提取城市名（移除 ", TX"）
df_schools["city"] = df_schools["city_state"].str.replace(r",\s*TX$", "", regex=True)

# 移除排名缺失的行（确保排名有效）
df_schools = df_schools.dropna(subset=["rank_state_elementary"])

# 确保排名列为数值
df_schools["rank_state_elementary"] = pd.to_numeric(df_schools["rank_state_elementary"], errors="coerce")
df_schools = df_schools.dropna(subset=["rank_state_elementary"])

# 计算城市内部排名（数值越小，排名越高）
df_schools["rank_city"] = (
    df_schools.groupby("city")["rank_state_elementary"]
    .rank(method="min", ascending=True)
)

# 读取城市坐标（来自 simplemaps.com 免费版）
df_cities = pd.read_csv("uscities.csv")
tx_cities = df_cities[df_cities["state_id"] == "TX"][["city", "lat", "lng"]].copy()
tx_cities["city"] = tx_cities["city"].str.title()

# 合并坐标到学校数据（用于 Top3 模式）
df_schools = df_schools.merge(tx_cities, on="city", how="inner")

# 预计算 "All" 模式：城市学校数量
school_counts = df_schools.groupby("city").size().reset_index(name="school_count")
merged_all = school_counts.merge(tx_cities, on="city", how="inner")

# ----------------------------
# 2. 颜色函数（用于 All 模式）
# ----------------------------
def get_color_count(value, min_val, max_val):
    if min_val == max_val:
        ratio = 0.5
    else:
        ratio = (value - min_val) / (max_val - min_val)
    start = Color("lightblue")
    end = Color("darkred")
    return list(start.range_to(end, 100))[int(ratio * 99)].hex

# ----------------------------
# 3. 图例函数（仅 All 模式）
# ----------------------------
def make_legend(min_val, max_val):
    steps = 5
    if min_val == max_val:
        values = [int(min_val)]
    else:
        step_size = (max_val - min_val) / (steps - 1)
        values = [int(min_val + i * step_size) for i in range(steps)]

    items = []
    for val in values:
        col = get_color_count(val, min_val, max_val)
        items.append(
            html.Div(
                [
                    html.Div(
                        style={
                            "width": "20px",
                            "height": "20px",
                            "backgroundColor": col,
                            "display": "inline-block",
                            "marginRight": "8px",
                            "border": "1px solid #ccc",
                        }
                    ),
                    html.Span(str(val)),
                ],
                style={"marginBottom": "5px"},
            )
        )

    return html.Div(
        [
            html.H5("School Count", style={"fontWeight": "bold", "marginBottom": "8px"}),
            html.Div(items),
        ],
        style={
            "position": "absolute",
            "top": "80px",
            "right": "20px",
            "background": "white",
            "padding": "10px",
            "borderRadius": "5px",
            "boxShadow": "0 0 10px rgba(0,0,0,0.2)",
            "zIndex": 1000,
        },
    )

# ----------------------------
# 4. Dash App
# ----------------------------
app = dash.Dash(__name__)

app.layout = html.Div(
    [
        html.H2("Texas Elementary Schools", style={"textAlign": "center", "margin": "20px"}),

        # Dropdown
        html.Div(
            [
                dcc.Dropdown(
                    id="view-selector",
                    options=[
                        {"label": "All Cities (by school count)", "value": "all"},
                        {"label": "Top 3 Schools per City", "value": "top3"},
                    ],
                    value="all",
                    style={"width": "400px", "margin": "0 auto"},
                )
            ],
            style={"textAlign": "center", "marginBottom": "20px"},
        ),

        # 地图容器（position relative，给图例 absolute 定位用）
        html.Div(id="map-container", style={"position": "relative", "height": "700px"}),

        # 图例容器
        html.Div(id="legend-container"),
    ]
)

# ----------------------------
# 5. 回调函数
# ----------------------------
@callback(
    Output("map-container", "children"),
    Output("legend-container", "children"),
    Input("view-selector", "value"),
)
def update_map(view_mode):
    if view_mode == "all":
        if merged_all.empty:
            return html.Div("No data to display."), ""

        df_all = merged_all.copy()
        min_count = int(df_all["school_count"].min())
        max_count = int(df_all["school_count"].max())
        df_all["color"] = df_all["school_count"].apply(
            lambda x: get_color_count(x, min_count, max_count)
        )

        markers = []
        for _, row in df_all.iterrows():
            markers.append(
                dl.CircleMarker(
                    center=[row["lat"], row["lng"]],
                    radius=8,
                    color="black",
                    weight=1,
                    fillColor=row["color"],
                    fillOpacity=0.8,
                    children=dl.Tooltip(f"{row['city']}: {int(row['school_count'])} school(s)"),
                )
            )

        map_obj = dl.Map(
            [dl.TileLayer(), *markers],
            center=[31.9686, -99.9018],
            zoom=6,
            style={"width": "100%", "height": "100%"},
        )
        legend = make_legend(min_count, max_count)
        return map_obj, legend

    # ----------------------------
    # top3 mode
    # ----------------------------
    if df_schools.empty:
        return html.Div("No school data available."), ""

    # 每个城市取州排名最高的（数值最小）最多3所
    top3_df = (
        df_schools.groupby("city", group_keys=False)
        .apply(lambda g: g.nsmallest(10, "rank_state_elementary"))
        .reset_index(drop=True)
    )

    markers = []
    for city, city_df in top3_df.groupby("city"):
        # 按城市排名排序，确保Top3顺序
        city_df = city_df.sort_values("rank_city").head(10)

        lat, lng = city_df["lat"].iloc[0], city_df["lng"].iloc[0]

        # 用 Dash 组件分行，确保 tooltip 显示三排/多行
        tooltip_children = [
            html.Div(
                html.Strong(f"{city} (Top 3)"),
                style={"fontSize": "14px", "marginBottom": "8px"},
            )
        ]

        for _, row in city_df.iterrows():
            rank_city_int = int(row["rank_city"])
            rank_state_int = int(row["rank_state_elementary"])
            tooltip_children.append(
                html.Div(
                    [
                        html.Span(f"🏆 Top {rank_city_int}: "),
                        html.Strong(row["school_name"]),
                        html.Span(f" | TX Rank #{rank_state_int}"),
                    ],
                    style={"fontSize": "12px", "marginBottom": "4px"},
                )
            )

        markers.append(
            dl.CircleMarker(
                center=[lat, lng],
                radius=12,
                color="black",
                weight=2,
                fillColor="#FF8C00",
                fillOpacity=0.8,
                children=dl.Tooltip(children=tooltip_children),
            )
        )

    map_obj = dl.Map(
        [dl.TileLayer(), *markers],
        center=[31.9686, -99.9018],
        zoom=6,
        style={"width": "100%", "height": "100%"},
    )
    return map_obj, ""

# ----------------------------
# 6. 运行
# ----------------------------
if __name__ == "__main__":
    app.run_server(debug=True)
