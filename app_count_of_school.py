import pandas as pd
import dash
from dash import html
import dash_leaflet as dl
from colour import Color

# ----------------------------
# 1. 读取数据
# ----------------------------
df_schools = pd.read_csv("schools.csv")
# 移除 description 中包含 "private" 的行（不区分大小写 
df_schools = df_schools[
    ~df_schools["description"].str.contains("private", case=False, na=False)
]
df_schools["city"] = df_schools["city_state"].str.replace(r",\s*TX$", "", regex=True)
school_counts = df_schools.groupby("city").size().reset_index(name="school_count")

# 从 https://simplemaps.com/data/us-cities 下载 uscities.csv
df_cities = pd.read_csv("uscities.csv")
tx_cities = df_cities[df_cities["state_id"] == "TX"][["city", "lat", "lng"]].copy()
tx_cities["city"] = tx_cities["city"].str.title()

merged = school_counts.merge(tx_cities, on="city", how="inner")

# ----------------------------
# 2. 颜色映射函数（保持不变）
# ----------------------------
min_count = merged["school_count"].min()
max_count = merged["school_count"].max()

def get_color(value, min_val, max_val):
    if min_val == max_val:
        ratio = 0.5
    else:
        ratio = (value - min_val) / (max_val - min_val)
    start_color = Color("lightblue")   # 可替换为 "lightyellow"
    end_color = Color("darkred")       # 可替换为 "darkblue" 等
    color_range = list(start_color.range_to(end_color, 100))
    selected_color = color_range[int(ratio * 99)]
    return selected_color.hex

merged["color"] = merged["school_count"].apply(lambda x: get_color(x, min_count, max_count))

# ----------------------------
# 3. 创建统一大小的 CircleMarker
# ----------------------------
markers = []
for _, row in merged.iterrows():
    markers.append(
        dl.CircleMarker(
            center=[row["lat"], row["lng"]],
            radius=8,  # ✅ 所有圆圈大小相同
            color="black",          # 边框颜色
            weight=1,               # 边框粗细
            fillColor=row["color"], # 填充色 = 数量编码
            fillOpacity=0.8,
            children=dl.Tooltip(f"{row['city']}: {row['school_count']} school(s)")
        )
    )

# ----------------------------
# 4. 图例（保持不变）
# ----------------------------
def make_legend(min_val, max_val):
    steps = 5
    if min_val == max_val:
        values = [min_val]
    else:
        step_size = (max_val - min_val) / (steps - 1)
        values = [int(min_val + i * step_size) for i in range(steps)]
    legend_items = []
    for val in values:
        col = get_color(val, min_val, max_val)
        legend_items.append(
            html.Div([
                html.Div(style={
                    "width": "20px", "height": "20px",
                    "backgroundColor": col,
                    "display": "inline-block",
                    "marginRight": "8px",
                    "border": "1px solid #ccc"
                }),
                html.Span(str(val), style={"verticalAlign": "top"})
            ], style={"marginBottom": "5px"})
        )
    return html.Div([
        html.H5("School Count", style={"fontWeight": "bold", "marginBottom": "8px"}),
        html.Div(legend_items)
    ], style={
        "position": "absolute",
        "top": "80px",
        "right": "20px",
        "background": "white",
        "padding": "10px",
        "borderRadius": "5px",
        "boxShadow": "0 0 10px rgba(0,0,0,0.2)",
        "zIndex": 1000
    })

# ----------------------------
# 5. Dash App
# ----------------------------
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H2("Texas Elementary Schools by City", style={"textAlign": "center", "margin": "20px"}),
    dl.Map(
        [
            dl.TileLayer(),  # OpenStreetMap
            *markers
        ],
        center=[31.9686, -99.9018],  # Texas 中心
        zoom=6,
        style={"width": "100%", "height": "700px"}
    ),
    make_legend(min_count, max_count)
])

if __name__ == '__main__':
    app.run_server(debug=True)