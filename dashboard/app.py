import psycopg2
import pandas as pd
from dash import Dash, html, dcc, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go

app = Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])
app.title = "MediaWatch Dashboard"


def get_data():
    try:
        conn = psycopg2.connect(
            host="postgres",
            port=5432,
            database="mabd",
            user="airflow",
            password="airflow"
        )
        articles = pd.read_sql("SELECT * FROM publications ORDER BY date_publication DESC", conn)
        stats    = pd.read_sql("SELECT * FROM stats_quotidiennes ORDER BY date_rapport DESC", conn)
        termes   = pd.read_sql("SELECT * FROM termes_frequents ORDER BY occurrences DESC LIMIT 30", conn)
        conn.close()
        return articles, stats, termes, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), str(e)


articles, stats, termes, err = get_data()


def safe(df):
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].apply(
            lambda x: x.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
            if isinstance(x, str) else x
        )
    return df


if not articles.empty:
    articles = safe(articles)
if not termes.empty:
    termes = safe(termes)

total      = len(articles)
nb_src     = articles["source"].nunique() if not articles.empty and "source" in articles.columns else 0
nb_lang    = articles["langue"].nunique() if not articles.empty and "langue" in articles.columns else 0
sans_titre = int(articles["titre"].isna().sum()) if not articles.empty and "titre" in articles.columns else 0


def bar_source():
    if articles.empty or "source" not in articles.columns:
        return go.Figure()
    src = articles["source"].value_counts().reset_index()
    src.columns = ["source", "count"]
    fig = px.bar(src, x="source", y="count", color="source",
                 color_discrete_sequence=["#6464ff", "#64e8a0", "#ff6464", "#ffca64", "#c864ff"],
                 template="plotly_dark")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(17,17,40,0.8)",
                      showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
    return fig


def pie_langue():
    if articles.empty or "langue" not in articles.columns:
        return go.Figure()
    lang = articles["langue"].value_counts().reset_index()
    lang.columns = ["langue", "count"]
    fig = px.pie(lang, values="count", names="langue", hole=0.5,
                 color_discrete_sequence=["#6464ff", "#64e8a0", "#ff6464", "#ffca64"],
                 template="plotly_dark")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=10, b=10, l=10, r=10))
    return fig


def area_daily():
    if articles.empty or "date_publication" not in articles.columns:
        return go.Figure()
    df = articles.copy()
    df["date_pub"] = pd.to_datetime(df["date_publication"], errors="coerce")
    daily = df.groupby(df["date_pub"].dt.date).size().reset_index()
    daily.columns = ["date", "count"]
    fig = px.area(daily, x="date", y="count", template="plotly_dark",
                  color_discrete_sequence=["#6464ff"])
    fig.update_traces(fill="tozeroy", fillcolor="rgba(100,100,255,0.15)")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(17,17,40,0.8)",
                      margin=dict(t=10, b=10, l=10, r=10))
    return fig


def bar_termes():
    if termes.empty:
        return go.Figure()
    col_mot = "terme" if "terme" in termes.columns else "mot"
    col_nb  = "occurrences" if "occurrences" in termes.columns else "frequence"
    top = termes.head(15)
    fig = go.Figure(go.Bar(
        x=top[col_nb], y=top[col_mot], orientation="h",
        marker_color="#64e8a0", marker_line_width=0
    ))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(17,17,40,0.8)",
                      margin=dict(t=10, b=10, l=10, r=10), yaxis=dict(autorange="reversed"))
    return fig


cols_table = [c for c in ["titre", "source", "date_publication", "langue"] if c in articles.columns]
table_data = articles[cols_table].head(50).to_dict("records") if not articles.empty else []
table_cols = [{"name": c, "id": c} for c in cols_table]

card_style = {"background": "#111128", "border": "1px solid #2a2a4a"}
box_style  = {"background": "#0f0f1a", "borderRadius": "8px", "padding": "1rem"}

app.layout = dbc.Container([

    dbc.Row([
        dbc.Col([
            html.H1("MediaWatch Dashboard",
                    style={"color": "#ffffff", "fontWeight": "800", "marginBottom": "4px"}),
            html.P("Pipeline Big Data - Architecture Medallion",
                   style={"color": "#6464aa", "fontSize": "0.85rem", "letterSpacing": "0.1em"}),
        ])
    ], style={"background": "linear-gradient(135deg,#0d0d2b,#1a0a2e)", "padding": "2rem",
              "borderRadius": "12px", "marginBottom": "1.5rem", "marginTop": "1rem"}),

    dbc.Row([
        dbc.Col(dbc.Alert(f"Erreur PostgreSQL : {err}", color="danger")) if err else html.Div()
    ]),

    dbc.Row([
        dbc.Col(dbc.Card([dbc.CardBody([
            html.H2(str(total), style={"color": "#c8f0ff", "fontFamily": "monospace"}),
            html.P("Total Articles", style={"color": "#7878aa", "fontSize": "0.8rem"})
        ])], style=card_style), width=3),
        dbc.Col(dbc.Card([dbc.CardBody([
            html.H2(str(nb_src), style={"color": "#64e8a0", "fontFamily": "monospace"}),
            html.P("Sources actives", style={"color": "#7878aa", "fontSize": "0.8rem"})
        ])], style=card_style), width=3),
        dbc.Col(dbc.Card([dbc.CardBody([
            html.H2(str(nb_lang), style={"color": "#ffca64", "fontFamily": "monospace"}),
            html.P("Langues detectees", style={"color": "#7878aa", "fontSize": "0.8rem"})
        ])], style=card_style), width=3),
        dbc.Col(dbc.Card([dbc.CardBody([
            html.H2(str(sans_titre), style={"color": "#ff6464", "fontFamily": "monospace"}),
            html.P("Sans titre", style={"color": "#7878aa", "fontSize": "0.8rem"})
        ])], style=card_style), width=3),
    ], className="mb-4"),

    dbc.Row([
        dbc.Col([
            html.H5("Articles par source", style={"color": "#c8c8f0"}),
            dcc.Graph(figure=bar_source(), style={"height": "300px"})
        ], width=6, style={**box_style, "marginRight": "0.5rem"}),
        dbc.Col([
            html.H5("Repartition par langue", style={"color": "#c8c8f0"}),
            dcc.Graph(figure=pie_langue(), style={"height": "300px"})
        ], width=6, style=box_style),
    ], className="mb-4"),

    dbc.Row([
        dbc.Col([
            html.H5("Articles par jour", style={"color": "#c8c8f0"}),
            dcc.Graph(figure=area_daily(), style={"height": "300px"})
        ], width=6, style={**box_style, "marginRight": "0.5rem"}),
        dbc.Col([
            html.H5("Top mots-cles", style={"color": "#c8c8f0"}),
            dcc.Graph(figure=bar_termes(), style={"height": "300px"})
        ], width=6, style=box_style),
    ], className="mb-4"),

    dbc.Row([
        dbc.Col([
            html.H5("Derniers articles", style={"color": "#c8c8f0", "marginBottom": "1rem"}),
            dash_table.DataTable(
                data=table_data,
                columns=table_cols,
                page_size=15,
                style_table={"overflowX": "auto"},
                style_cell={"backgroundColor": "#111128", "color": "#e8e8f0",
                            "border": "1px solid #2a2a4a", "textAlign": "left",
                            "padding": "8px", "maxWidth": "300px",
                            "overflow": "hidden", "textOverflow": "ellipsis"},
                style_header={"backgroundColor": "#1a1a3a", "color": "#6464ff",
                              "fontWeight": "bold", "border": "1px solid #2a2a4a"},
                style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "#0f0f20"}],
            )
        ], style=box_style)
    ], className="mb-4"),

    dbc.Row([
        dbc.Col(html.P("MediaWatch - EMSI Casablanca 2025/2026 - Filiere IADATA",
                       style={"textAlign": "center", "color": "#3a3a6a", "fontSize": "0.75rem"}))
    ])

], fluid=True, style={"backgroundColor": "#0a0a0f", "minHeight": "100vh", "padding": "1rem"})

if __name__ == "__main__":
    print("Dashboard disponible sur http://localhost:8050")
    app.run(debug=False, host="0.0.0.0", port=8050)