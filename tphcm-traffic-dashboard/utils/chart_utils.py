import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from utils.config import COLOR_PALETTE

C = COLOR_PALETTE


def apply_dark_template(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=C["darker"],
        plot_bgcolor=C["dark"],
        font=dict(color=C["text"], size=12),
        margin=dict(l=40, r=20, t=40, b=40),
    )
    fig.update_xaxes(
        gridcolor="#333333",
        linecolor="#555555",
        tickfont=dict(color=C["text"]),
        title_font=dict(color=C["text"]),
    )
    fig.update_yaxes(
        gridcolor="#333333",
        linecolor="#555555",
        tickfont=dict(color=C["text"]),
        title_font=dict(color=C["text"]),
    )
    return fig


def line_chart(
    df,
    x: str,
    y: str | list,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    color: str | None = None,
    colors: list | None = None,
    mode: str = "lines",
    markers: bool = False,
    height: int = 400,
    show_legend: bool = True,
) -> go.Figure:
    if isinstance(y, list) and color:
        fig = go.Figure()
        for i, col in enumerate(y):
            clr = colors[i] if colors else C["chart_colors"][i % len(C["chart_colors"])]
            fig.add_trace(go.Scatter(
                x=df[x], y=df[col],
                mode="lines+markers" if markers else "lines",
                name=col,
                line=dict(color=clr, width=2),
                marker=dict(size=4) if markers else dict(),
            ))
    else:
        fig = px.line(
            df, x=x, y=y, color=color,
            color_discrete_sequence=C["chart_colors"],
        )
    fig = apply_dark_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=C["text"])),
        xaxis_title=x_label,
        yaxis_title=y_label,
        height=height,
        showlegend=show_legend,
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=C["text"]),
        ),
    )
    return fig


def bar_chart(
    df,
    x: str,
    y: str,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    orientation: str = "v",
    color: str | None = None,
    colors: list | None = None,
    barmode: str = "relative",
    height: int = 400,
    show_values: bool = False,
    text_position: str = "outside",
) -> go.Figure:
    if color:
        fig = px.bar(
            df, x=x, y=y, color=color,
            orientation=orientation,
            barmode=barmode,
            color_discrete_sequence=C["chart_colors"],
        )
    else:
        fig = go.Figure(go.Bar(
            x=df[x] if orientation == "v" else df[y],
            y=df[y] if orientation == "v" else df[x],
            orientation=orientation,
            marker_color=colors if colors else C["primary"],
            text=df[y] if (orientation == "v" and show_values) else df[x],
            textposition=text_position,
        ))
    fig = apply_dark_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=C["text"])),
        xaxis_title=x_label,
        yaxis_title=y_label,
        height=height,
        barmode=barmode,
        showlegend=color is not None,
    )
    if not color and show_values:
        fig.update_traces(
            textposition=text_position,
            textfont=dict(color=C["text"]),
        )
    return fig


def heatmap_chart(
    df,
    x: str,
    y: str,
    z: str,
    title: str = "",
    colorscale: str = "YlOrRd",
    height: int = 400,
) -> go.Figure:
    x_data = df[x].tolist() if x in df.columns else df.index.tolist()
    y_data = df[y].tolist() if y in df.columns else df.index.tolist()
    if z in df.columns:
        z_data = df[z].values.tolist()
    else:
        z_data = df.values.tolist()

    fig = go.Figure(data=go.Heatmap(
        x=x_data,
        y=y_data,
        z=z_data,
        colorscale=colorscale,
        reversescale=True,
        colorbar=dict(
            title=dict(font=dict(color=C["text"])),
            tickfont=dict(color=C["text"]),
        ),
    ))
    fig = apply_dark_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=C["text"])),
        height=height,
        xaxis=dict(tickangle=45),
    )
    return fig


def pie_chart(
    df,
    names: str,
    values: str,
    title: str = "",
    hole: float = 0.5,
    height: int = 400,
) -> go.Figure:
    fig = go.Figure(data=[go.Pie(
        labels=df[names],
        values=df[values],
        hole=hole,
        marker=dict(colors=C["chart_colors"]),
        textinfo="label+percent",
        textfont=dict(color=C["text"]),
    )])
    fig = apply_dark_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=C["text"])),
        height=height,
        showlegend=True,
    )
    return fig


def scatter_chart(
    df,
    x: str,
    y: str,
    title: str = "",
    size: str | None = None,
    color: str | None = None,
    x_label: str = "",
    y_label: str = "",
    height: int = 400,
) -> go.Figure:
    fig = px.scatter(
        df, x=x, y=y, size=size, color=color,
        color_discrete_sequence=C["chart_colors"],
    )
    fig = apply_dark_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=C["text"])),
        xaxis_title=x_label or x,
        yaxis_title=y_label or y,
        height=height,
    )
    return fig


def histogram_chart(
    df,
    x: str,
    title: str = "",
    nbins: int = 10,
    height: int = 400,
    color: str | None = None,
) -> go.Figure:
    if color:
        fig = px.histogram(df, x=x, color=color, nbins=nbins)
    else:
        fig = go.Figure(data=[go.Histogram(
            x=df[x],
            nbinsx=nbins,
            marker_color=C["primary"],
        )])
    fig = apply_dark_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=C["text"])),
        height=height,
        showlegend=color is not None,
    )
    return fig


def big_number(
    value: float,
    title: str = "",
    delta: float | None = None,
    delta_color: str = "normal",
    format_str: str = ",.0f",
    height: int = 120,
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Indicator(
        mode="number+delta" if delta is not None else "number",
        value=value,
        number=dict(
            valueformat=format_str,
            font=dict(size=36, color=C["text"]),
        ),
        title=dict(text=title, font=dict(size=14, color=C["muted"])),
        delta=dict(
            reference=delta,
            font=dict(color=C["success"] if delta_color == "normal" else C["danger"]),
        ),
        domain=dict(x=[0, 1], y=[0, 1]),
    ))
    fig.update_layout(
        paper_bgcolor=C["darker"],
        plot_bgcolor=C["dark"],
        height=height,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def box_plot(
    df,
    x: str,
    y: str,
    title: str = "",
    color: str | None = None,
    height: int = 400,
) -> go.Figure:
    if color:
        fig = px.box(df, x=x, y=y, color=color, color_discrete_sequence=C["chart_colors"])
    else:
        fig = go.Figure(data=[go.Box(
            y=df[y],
            x=df[x] if x else None,
            marker_color=C["primary"],
            boxmean="sd",
        )])
    fig = apply_dark_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=C["text"])),
        height=height,
        showlegend=color is not None,
    )
    return fig


def dual_axis_chart(
    df,
    x: str,
    y_left: str,
    y_right: str,
    title: str = "",
    y_left_label: str = "",
    y_right_label: str = "",
    left_color: str | None = None,
    right_color: str | None = None,
    height: int = 400,
) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(
        x=df[x], y=df[y_left],
        name=y_left_label or y_left,
        mode="lines",
        line=dict(color=left_color or C["primary"], width=2),
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=df[x], y=df[y_right],
        name=y_right_label or y_right,
        mode="lines",
        line=dict(color=right_color or C["danger"], width=2, dash="dot"),
    ), secondary_y=True)
    fig = apply_dark_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color=C["text"])),
        height=height,
        showlegend=True,
    )
    fig.update_yaxes(
        title_text=y_left_label or y_left,
        secondary_y=False,
        gridcolor="#333333",
    )
    fig.update_yaxes(
        title_text=y_right_label or y_right,
        secondary_y=True,
        gridcolor="#333333",
    )
    return fig


def annotation_line(
    value: float,
    label: str = "",
    color: str = C["danger"],
    width: int = 2,
    dash: str = "dash",
):
    if not label:
        return dict(
            type="line",
            x0=0, x1=1,
            y0=value, y1=value,
            xref="paper",
            yref="y",
            line=dict(color=color, width=width, dash=dash),
        )
    return dict(
        type="line",
        x0=0, x1=1,
        y0=value, y1=value,
        xref="paper",
        yref="y",
        line=dict(color=color, width=width, dash=dash),
        label=dict(
            text=label,
            textposition="top right",
            font=dict(color=color, size=10),
            xanchor="right",
            yanchor="bottom",
        ),
    )


def gauge_chart(
    value: float,
    title: str = "",
    min_val: float = 0,
    max_val: float = 100,
    thresholds: list = None,
    height: int = 200,
) -> go.Figure:
    if thresholds is None:
        thresholds = [
            {"range": [min_val, max_val * 0.4], "color": C["success"]},
            {"range": [max_val * 0.4, max_val * 0.7], "color": C["warning"]},
            {"range": [max_val * 0.7, max_val], "color": C["danger"]},
        ]
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number=dict(
            font=dict(size=28, color=C["text"]),
            suffix="",
        ),
        gauge=dict(
            axis=dict(
                range=[min_val, max_val],
                tickwidth=1,
                tickcolor=C["text"],
                tickfont=dict(color=C["text"], size=10),
            ),
            bar=dict(color=C["text"], thickness=0.15),
            bgcolor=C["darker"],
            borderwidth=0,
            steps=thresholds,
            bordercolor=C["border-color"],
            threshold=dict(
                line=dict(color=C["danger"], width=4),
                thickness=0.75,
                value=value,
            ),
        ),
        domain=dict(x=[0, 1], y=[0, 1]),
    ))
    fig.update_layout(
        paper_bgcolor=C["darker"],
        plot_bgcolor=C["darker"],
        height=height,
        margin=dict(l=20, r=20, t=40, b=20),
        title=dict(text=title, font=dict(size=13, color=C["text"]))
        if title else dict(text=""),
    )
    return fig


def semantic_bar_chart(
    df,
    x: str,
    y: str,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    green_threshold: float = None,
    yellow_threshold: float = None,
    high_is_bad: bool = True,
    height: int = 300,
    show_values: bool = True,
    text_position: str = "outside",
) -> go.Figure:
    if high_is_bad:
        colors = [
            C["success"] if (v < (green_threshold or 0)) else
            C["warning"] if (yellow_threshold and v < yellow_threshold) else
            C["danger"]
            for v in df[y]
        ]
    else:
        colors = [
            C["danger"] if (v < (green_threshold or 0)) else
            C["warning"] if (yellow_threshold and v < yellow_threshold) else
            C["success"]
            for v in df[y]
        ]
    fig = go.Figure(go.Bar(
        x=df[x] if len(df) > 5 else df[x],
        y=df[y],
        marker_color=colors,
        text=df[y].round(1) if show_values else None,
        textposition=text_position,
        textfont=dict(color=C["text"], size=10),
    ))
    fig = apply_dark_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color=C["text"])),
        xaxis_title=x_label or x,
        yaxis_title=y_label or y,
        height=height,
        showlegend=False,
        xaxis=dict(
            tickfont=dict(size=10),
            tickangle=30 if len(df) > 5 else 0,
        ),
    )
    return fig


def area_smooth_chart(
    df,
    x: str,
    y: str | list,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    colors: list | None = None,
    height: int = 350,
    fill: float = 0.3,
) -> go.Figure:
    if isinstance(y, list):
        fig = go.Figure()
        for i, col in enumerate(y):
            clr = (colors or C["chart_colors"])[i % len(C["chart_colors"])]
            fig.add_trace(go.Scatter(
                x=df[x], y=df[col],
                mode="lines",
                name=col,
                line=dict(color=clr, width=2, shape="spline", smoothing=0.3),
                fill="tonexty" if i > 0 else "tozeroy",
                fillcolor=f"{clr}44",
            ))
    else:
        clr = (colors or [C["primary"]])[0]
        fig = go.Figure(go.Scatter(
            x=df[x], y=df[y],
            mode="lines",
            name=y,
            line=dict(color=clr, width=2, shape="spline", smoothing=0.3),
            fill="tozeroy",
            fillcolor=f"{clr}44",
        ))
    fig = apply_dark_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color=C["text"])),
        xaxis_title=x_label,
        yaxis_title=y_label,
        height=height,
        showlegend=isinstance(y, list) and len(y) > 1,
        legend=dict(font=dict(color=C["text"]), bgcolor="rgba(0,0,0,0)"),
    )
    return fig


def radar_chart(
    df,
    r_col: str,
    theta_col: str,
    title: str = "",
    fill_color: str = C["primary"],
    height: int = 400,
) -> go.Figure:
    fig = go.Figure(go.Scatterpolar(
        r=df[r_col].tolist(),
        theta=df[theta_col].tolist(),
        fill="toself",
        fillcolor=f"{fill_color}44",
        line=dict(color=fill_color, width=2),
        marker=dict(color=fill_color, size=5),
    ))
    fig = apply_dark_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color=C["text"])),
        height=height,
        polar=dict(
            bgcolor=C["darker"],
            angularaxis=dict(
                tickfont=dict(color=C["text"], size=11),
                linecolor=C["border-color"],
            ),
            radialaxis=dict(
                tickfont=dict(color=C["text"], size=9),
                gridcolor=f"{C['border-color']}88",
                linecolor=C["border-color"],
            ),
        ),
        showlegend=False,
    )
    return fig


def bullet_chart(
    value: float,
    title: str = "",
    subtitle: str = "",
    min_val: float = 0,
    max_val: float = 100,
    poor: float = 30,
    satisfactory: float = 60,
    good: float = 80,
    height: int = 100,
) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="number+gauge+delta",
        value=value,
        number=dict(font=dict(size=24, color=C["text"])),
        gauge=dict(
            shape="bullet",
            axis=dict(range=[min_val, max_val], tickwidth=0, tickcolor=C["text"]),
            bar=dict(color=C["text"], thickness=0.25),
            bgcolor=C["darker"],
            borderwidth=0,
            steps=[
                {"range": [min_val, poor], "color": C["danger"]},
                {"range": [poor, satisfactory], "color": C["warning"]},
                {"range": [satisfactory, good], "color": "#90EE90"},
                {"range": [good, max_val], "color": C["success"]},
            ],
            threshold=dict(
                line=dict(color=C["danger"], width=3),
                thickness=0.8,
                value=value,
            ),
        ),
        title=dict(text=title, font=dict(size=13, color=C["text"])),
        delta=dict(reference=max_val, font=dict(color=C["muted"], size=10)),
        domain=dict(x=[0, 1], y=[0, 1]),
    ))
    fig.update_layout(
        paper_bgcolor=C["darker"],
        plot_bgcolor=C["darker"],
        height=height,
        margin=dict(l=10, r=10, t=50, b=30),
    )
    return fig


def multi_bullet_chart(
    df,
    value_col: str,
    label_col: str,
    title: str = "",
    max_val: float = 100,
    poor: float = 30,
    satisfactory: float = 60,
    good: float = 80,
    height: int = None,
) -> go.Figure:
    n = len(df)
    h = height or max(80, n * 35)
    fig = go.Figure()
    for i, row in df.iterrows():
        val = float(row[value_col])
        fig.add_trace(go.Indicator(
            mode="number+gauge",
            value=val,
            gauge=dict(
                shape="bullet",
                axis=dict(range=[0, max_val], tickwidth=0, tickcolor=C["darker"]),
                bar=dict(color=C["text"], thickness=0.3),
                bgcolor=C["darker"],
                borderwidth=0,
                steps=[
                    {"range": [0, poor], "color": C["danger"]},
                    {"range": [poor, satisfactory], "color": C["warning"]},
                    {"range": [satisfactory, good], "color": "#90EE90"},
                    {"range": [good, max_val], "color": C["success"]},
                ],
                threshold=dict(
                    line=dict(color=C["danger"], width=2),
                    thickness=0.7,
                    value=val,
                ),
            ),
            title=dict(text=str(row[label_col]), font=dict(size=11, color=C["text"])),
            number=dict(font=dict(size=11, color=C["text"])),
            domain=dict(x=[0, 1], y=[i / max(n, 1), (i + 0.8) / max(n, 1)]),
        ))
    fig.update_layout(
        paper_bgcolor=C["darker"],
        plot_bgcolor=C["darker"],
        height=h,
        margin=dict(l=10, r=10, t=40, b=30),
        title=dict(text=title, font=dict(size=13, color=C["text"]))
        if title else dict(text=""),
        showlegend=False,
    )
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# LIGHT MODE chart helpers (Dark Theme — dark card bg, light text, pastel colors)
# ──────────────────────────────────────────────────────────────────────────────

def apply_light_template(fig: "go.Figure") -> "go.Figure":
    """Apply Dark Theme styling: dark card bg, light text, pastel chart colors."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#1A1F2E",
        plot_bgcolor="#151922",
        font=dict(color="#E8EAF0", size=12),
        margin=dict(l=50, r=30, t=50, b=50),
    )
    fig.update_xaxes(
        gridcolor="#2A3042",
        linecolor="#3A4052",
        tickfont=dict(color="#8892A4"),
        title_font=dict(color="#8892A4"),
        showgrid=True,
    )
    fig.update_yaxes(
        gridcolor="#2A3042",
        linecolor="#3A4052",
        tickfont=dict(color="#8892A4"),
        title_font=dict(color="#8892A4"),
        showgrid=True,
    )
    return fig


_LIGHT_PALETTE = [
    "#4ECDC4", "#45B7D1", "#96CEB4", "#FDCB6E",
    "#A29BFE", "#DDA0DD", "#FFB3AB", "#74B9FF",
]


def line_chart_light(
    df, x: str, y: str | list, title: str = "",
    x_label: str = "", y_label: str = "",
    color: str | None = None, colors: list | None = None,
    markers: bool = False, height: int = 350,
    show_legend: bool = True, dash: str | None = None,
) -> "go.Figure":
    """Line chart styled for Light Mode."""
    fig = go.Figure()
    palette = colors or _LIGHT_PALETTE
    if isinstance(y, list):
        for i, col in enumerate(y):
            clr = palette[i % len(palette)]
            fig.add_trace(go.Scatter(
                x=df[x], y=df[col],
                mode="lines+markers" if markers else "lines",
                name=col,
                line=dict(color=clr, width=2, dash=dash),
                marker=dict(size=5) if markers else dict(),
            ))
    else:
        fig.add_trace(go.Scatter(
            x=df[x], y=df[y],
            mode="lines+markers" if markers else "lines",
            name=y,
            line=dict(color=palette[0], width=2, dash=dash),
            marker=dict(size=5) if markers else dict(),
        ))
    fig = apply_light_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#E8EAF0"),
                   x=0, xanchor="left"),
        xaxis_title=x_label, yaxis_title=y_label,
        height=height, showlegend=show_legend,
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor="#2A3042",
            font=dict(color="#E8EAF0", size=11),
        ),
    )
    return fig


def bar_chart_light(
    df, x: str, y: str, title: str = "",
    x_label: str = "", y_label: str = "",
    orientation: str = "v",
    color: str | None = None, colors: list | None = None,
    barmode: str = "relative",
    height: int = 350, show_values: bool = False,
    text_position: str = "outside",
) -> "go.Figure":
    """Bar chart styled for Light Mode."""
    palette = colors or _LIGHT_PALETTE
    if color:
        fig = px.bar(
            df, x=x, y=y, color=color,
            orientation=orientation, barmode=barmode,
            color_discrete_sequence=palette,
        )
    else:
        fig = go.Figure(go.Bar(
            x=df[x] if orientation == "v" else df[y],
            y=df[y] if orientation == "v" else df[x],
            orientation=orientation,
            marker_color=palette[0],
            text=df[y] if (orientation == "v" and show_values) else None,
            textposition=text_position,
        ))
    fig = apply_light_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#E8EAF0"),
                   x=0, xanchor="left"),
        xaxis_title=x_label, yaxis_title=y_label,
        height=height, barmode=barmode, showlegend=color is not None,
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor="#2A3042",
            font=dict(color="#E8EAF0", size=11),
        ),
        xaxis=dict(tickangle=30 if (len(df) > 5 and orientation == "v") else 0),
    )
    if not color and show_values:
        fig.update_traces(
            textposition=text_position,
            textfont=dict(color="#8892A4", size=10),
        )
    return fig


def horizontal_bar_light(
    df, x: str, y: str, title: str = "",
    x_label: str = "", y_label: str = "",
    colors: list | None = None, height: int = 350,
    show_values: bool = True,
) -> "go.Figure":
    """Horizontal bar chart for Light Mode."""
    palette = colors or ["#FFB3AB", "#FDCB6E", "#FFEAA7", "#96CEB4", "#4ECDC4"]
    fig = go.Figure(go.Bar(
        x=df[x], y=df[y], orientation="h",
        marker_color=palette[:len(df)],
        text=df[x].round(1) if show_values else None,
        textposition="outside",
        textfont=dict(color="#8892A4", size=10),
    ))
    fig = apply_light_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#E8EAF0"),
                   x=0, xanchor="left"),
        xaxis_title=x_label, yaxis_title=y_label,
        height=height, showlegend=False,
        margin=dict(l=160, r=30, t=50, b=50),
    )
    return fig


def pie_chart_light(
    df, names: str, values: str, title: str = "",
    hole: float = 0.55, height: int = 350,
    colors: list | None = None,
) -> "go.Figure":
    """Donut/Pie chart styled for Light Mode."""
    palette = colors or _LIGHT_PALETTE
    fig = go.Figure(data=[go.Pie(
        labels=df[names], values=df[values], hole=hole,
        marker=dict(colors=palette[:len(df)]),
        textinfo="label+percent",
        textfont=dict(color="#E8EAF0", size=11),
        hovertemplate="%{label}<br>%{percent}<extra></extra>",
    )])
    fig = apply_light_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#E8EAF0"),
                   x=0.5, xanchor="center"),
        height=height, showlegend=True,
        legend=dict(
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#2A3042",
            font=dict(color="#E8EAF0", size=11),
        ),
    )
    return fig


def scatter_chart_light(
    df, x: str, y: str, title: str = "",
    size: str | None = None, color: str | None = None,
    x_label: str = "", y_label: str = "",
    height: int = 400, colors: list | None = None,
    opacity: float = 0.7,
) -> "go.Figure":
    """Scatter plot styled for Light Mode."""
    fig = px.scatter(
        df, x=x, y=y, size=size, color=color,
        color_discrete_sequence=(colors or _LIGHT_PALETTE),
    )
    fig = apply_light_template(fig)
    fig.update_traces(marker=dict(opacity=opacity))
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#E8EAF0"),
                   x=0, xanchor="left"),
        xaxis_title=x_label or x, yaxis_title=y_label or y,
        height=height,
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor="#2A3042",
            font=dict(color="#E8EAF0", size=11),
        ),
    )
    return fig


def heatmap_chart_light(
    df, x: str, y: str, z: str,
    title: str = "", colorscale: str = "RdYlGn_r",
    height: int = 380,
) -> "go.Figure":
    """Heatmap styled for Light Mode."""
    z_data = df[z].tolist() if z in df.columns else df.values.tolist()
    fig = go.Figure(data=go.Heatmap(
        x=df[x].tolist(), y=df[y].tolist(), z=z_data,
        colorscale=colorscale, reversescale=True,
        colorbar=dict(
            title=dict(font=dict(color="#E8EAF0")),
            tickfont=dict(color="#E8EAF0"),
        ),
    ))
    fig = apply_light_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#E8EAF0"),
                   x=0, xanchor="left"),
        height=height, xaxis=dict(tickangle=45),
        margin=dict(b=80),
    )
    return fig


def area_chart_light(
    df, x: str, y: str | list, title: str = "",
    x_label: str = "", y_label: str = "",
    colors: list | None = None, height: int = 350,
) -> "go.Figure":
    """Area chart styled for Light Mode."""
    palette = colors or ["#4ECDC4", "#DDA0DD", "#45B7D1"]
    ys = [y] if isinstance(y, str) else y
    fig = go.Figure()
    for i, col in enumerate(ys):
        clr = palette[i % len(palette)]
        fig.add_trace(go.Scatter(
            x=df[x], y=df[col], mode="lines", name=col,
            line=dict(color=clr, width=2),
            fill="tozeroy" if i == 0 else "tonexty",
            fillcolor=f"{clr}3D",
        ))
    fig = apply_light_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#E8EAF0"),
                   x=0, xanchor="left"),
        xaxis_title=x_label, yaxis_title=y_label,
        height=height, showlegend=len(ys) > 1,
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor="#2A3042",
            font=dict(color="#E8EAF0", size=11),
        ),
    )
    return fig


def gauge_chart_light(
    value: float, title: str = "",
    min_val: float = 0, max_val: float = 100,
    thresholds: list | None = None, height: int = 220,
) -> "go.Figure":
    """Gauge chart with pastel steps for Light Mode."""
    if thresholds is None:
        thresholds = [
            {"range": [min_val, max_val * 0.4], "color": "#52C41A"},
            {"range": [max_val * 0.4, max_val * 0.7], "color": "#FAAD14"},
            {"range": [max_val * 0.7, max_val], "color": "#FF7875"},
        ]
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        number=dict(font=dict(size=28, color="#E8EAF0")),
        gauge=dict(
            axis=dict(
                range=[min_val, max_val], tickwidth=1,
                tickcolor="#8892A4",
                tickfont=dict(color="#8892A4", size=10),
            ),
            bar=dict(color="#E8EAF0", thickness=0.12),
            bgcolor="#151922", borderwidth=0, steps=thresholds,
            threshold=dict(
                line=dict(color="#4ECDC4", width=4),
                thickness=0.75, value=value,
            ),
        ),
        domain=dict(x=[0, 1], y=[0, 1]),
    ))
    fig.update_layout(
        paper_bgcolor="#1A1F2E", plot_bgcolor="#1A1F2E",
        height=height, margin=dict(l=20, r=20, t=40, b=20),
        title=dict(text=title, font=dict(size=12, color="#E8EAF0"),
                   x=0.5, xanchor="center") if title else dict(text=""),
    )
    return fig


def big_number_light(
    value: float, title: str = "",
    delta: float | None = None,
    delta_color: str = "normal",
    format_str: str = ",.0f",
    height: int = 120,
) -> "go.Figure":
    """Big number KPI for Light Mode."""
    fig = go.Figure()
    fig.add_trace(go.Indicator(
        mode="number+delta" if delta is not None else "number",
        value=value,
        number=dict(valueformat=format_str, font=dict(size=36, color="#E8EAF0")),
        title=dict(text=title, font=dict(size=13, color="#8892A4")),
        delta=dict(
            reference=delta,
            font=dict(
                color="#52C41A" if delta_color == "normal" else "#FF7875"
            ),
        ),
        domain=dict(x=[0, 1], y=[0, 1]),
    ))
    fig.update_layout(
        paper_bgcolor="#1A1F2E", plot_bgcolor="#1A1F2E",
        height=height, margin=dict(l=20, r=20, t=30, b=20),
    )
    return fig


def semantic_bar_light(
    df, x: str, y: str, title: str = "",
    x_label: str = "", y_label: str = "",
    green_val: float = None, yellow_val: float = None,
    high_is_bad: bool = True, height: int = 300,
) -> "go.Figure":
    """Bar chart with green/yellow/red semantic coloring for Light Mode."""
    vals = df[y].tolist()
    bar_colors = []
    for v in vals:
        if green_val is not None and ((high_is_bad and v < green_val) or (not high_is_bad and v >= green_val)):
            bar_colors.append("#52C41A")
        elif yellow_val is not None and ((high_is_bad and v < yellow_val) or (not high_is_bad and v >= yellow_val)):
            bar_colors.append("#FAAD14")
        else:
            bar_colors.append("#FF7875")
    fig = go.Figure(go.Bar(
        x=df[x], y=df[y],
        marker_color=bar_colors,
        text=df[y].round(1),
        textposition="outside",
        textfont=dict(color="#8892A4", size=10),
    ))
    fig = apply_light_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#E8EAF0"),
                   x=0, xanchor="left"),
        xaxis_title=x_label, yaxis_title=y_label,
        height=height, showlegend=False,
        xaxis=dict(tickangle=30 if len(df) > 5 else 0),
    )
    return fig


def dual_axis_light(
    df, x: str,
    y_left: str, y_right: str,
    title: str = "",
    y_left_label: str = "", y_right_label: str = "",
    left_color: str = "#4ECDC4", right_color: str = "#FDCB6E",
    left_type: str = "bar", right_type: str = "line",
    height: int = 380,
) -> "go.Figure":
    """Dual-axis combo chart (Bar+Line) for Light Mode."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if left_type == "bar":
        fig.add_trace(go.Bar(
            x=df[x], y=df[y_left], name=y_left_label or y_left,
            marker_color=left_color, opacity=0.8,
        ), secondary_y=False)
    else:
        fig.add_trace(go.Scatter(
            x=df[x], y=df[y_left], name=y_left_label or y_left,
            mode="lines", line=dict(color=left_color, width=2),
        ), secondary_y=False)
    if right_type == "line":
        fig.add_trace(go.Scatter(
            x=df[x], y=df[y_right], name=y_right_label or y_right,
            mode="lines+markers", line=dict(color=right_color, width=2, dash="dash"),
            marker=dict(size=5),
        ), secondary_y=True)
    else:
        fig.add_trace(go.Bar(
            x=df[x], y=df[y_right], name=y_right_label or y_right,
            marker_color=right_color, opacity=0.7,
        ), secondary_y=True)
    fig = apply_light_template(fig)
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#E8EAF0"),
                   x=0, xanchor="left"),
        height=height, showlegend=True,
        legend=dict(
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#2A3042",
            font=dict(color="#E8EAF0", size=11),
        ),
        barmode="overlay",
    )
    fig.update_yaxes(title_text=y_left_label or y_left, secondary_y=False, gridcolor="#2A3042")
    fig.update_yaxes(title_text=y_right_label or y_right, secondary_y=True, gridcolor="#2A3042")
    return fig
