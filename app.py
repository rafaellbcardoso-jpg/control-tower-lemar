import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import holidays

st.set_page_config(layout="wide")

st.markdown("""
<style>
html, body, [class*="css"]{
    background-color:#05070d;
    color:white;
}
[data-baseweb="tag"]{
    background-color:#2b2f38 !important;
    color:white !important;
}
h1,h2,h3{
    margin-bottom:0px;
}
.metric-card{
    background-color:#11151f;
    padding:12px;
    border-radius:6px;
}
</style>
""", unsafe_allow_html=True)

st.title("Assistente de programação - Lemar")

df = pd.read_excel("data/programacao.xlsx")
df.columns = df.columns.str.strip()
df["Data"] = pd.to_datetime(df["Data"])

coords = [
"Lat.Entrega",
"Lon.Entrega",
"Lat.Coleta_Atual",
"Long.Coleta_Atual"
]

for c in coords:
    df[c] = (
        df[c]
        .astype(str)
        .str.replace(",",".")
        .astype(float)
    )

ultima_data = df["Data"].max()
primeiro_dia_mes = ultima_data.replace(day=1)

# ================================
# FILTROS
# ================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    cliente_global = st.selectbox(
        "Cliente",
        ["Todos"] + sorted(df["Cliente"].dropna().unique())
    )

with col2:
    gestor_global = st.selectbox(
        "Gestor",
        ["Todos"] + sorted(df["Gestor"].dropna().unique())
    )

with col3:
    prestador_global = st.selectbox(
        "Tipo Prestador",
        ["Todos"] + sorted(df["Tipo Prestador"].dropna().unique())
    )

with col4:
    data_inicio, data_fim = st.date_input(
        "Período",
        value=(primeiro_dia_mes, ultima_data)
    )

df_global = df.copy()

if cliente_global != "Todos":
    df_global = df_global[df_global["Cliente"] == cliente_global]

if gestor_global != "Todos":
    df_global = df_global[df_global["Gestor"] == gestor_global]

if prestador_global != "Todos":
    df_global = df_global[df_global["Tipo Prestador"] == prestador_global]

df_global = df_global[
(df_global["Data"] >= pd.to_datetime(data_inicio)) &
(df_global["Data"] <= pd.to_datetime(data_fim))
]

# ================================
# STATUS DA FROTA (CARDS)
# ================================

st.subheader("STATUS DA FROTA")

mes_atual = ultima_data.month
mes_passado = (ultima_data - pd.DateOffset(months=1)).month

ativos_mes_atual = df[df["Data"].dt.month == mes_atual]["Motorista"].unique()
ativos_mes_passado = df[df["Data"].dt.month == mes_passado]["Motorista"].unique()

ativos = len(ativos_mes_atual)
inativos_mes = len(set(ativos_mes_passado) - set(ativos_mes_atual))

ultima_viagem = df.groupby("Motorista")["Data"].max().reset_index()
ultima_viagem["Dias Sem Viagem"] = (datetime.now() - ultima_viagem["Data"]).dt.days

parados_5 = len(ultima_viagem[ultima_viagem["Dias Sem Viagem"] > 5])

c1,c2,c3 = st.columns(3)

c1.metric("Motoristas ativos no período", ativos)
c2.metric("Motoristas inativos no mês", inativos_mes)
c3.metric("Motoristas parados > 5 dias", parados_5)
# ================================
# MOTORISTAS SEM VIAGEM
# ================================

st.subheader("MOTORISTAS SEM VIAGEM")

ultima = df_global.groupby("Motorista")["Data"].max().reset_index()

ultima["Dias"] = (datetime.now() - ultima["Data"]).dt.total_seconds() / 86400
ultima = ultima[(ultima["Dias"] >= 1.5)]
ultima = ultima.sort_values("Dias", ascending=False).head(20)

fig_parados = go.Figure()

fig_parados.add_trace(
    go.Scatter(
        x=ultima["Motorista"],
        y=ultima["Dias"],
        mode="lines",
        name="Dias Sem Viagem",
        line=dict(color="red", width=3, shape="spline"),
        fill="tozeroy",
        fillcolor="rgba(255,0,0,0.35)"
    )
)

fig_parados.update_layout(template="plotly_dark", height=260)

st.plotly_chart(fig_parados, use_container_width=True)
# ================================
# PRODUTIVIDADE MOTORISTAS (3 MESES)
# ================================

st.subheader("PRODUTIVIDADE MOTORISTAS (3 MESES)")

df_prod = df.copy()
df_prod["Mes"] = df_prod["Data"].dt.to_period("M")

ultimos_meses = sorted(df_prod["Mes"].unique())[-3:]

prod = df_prod[df_prod["Mes"].isin(ultimos_meses)]

prod = prod.groupby(["Motorista","Mes"])["Data"].nunique().reset_index(name="Dias")

pivot = prod.pivot(index="Motorista",columns="Mes",values="Dias").fillna(0)

pivot["Total"] = pivot.sum(axis=1)

# agrupar por dias trabalhados
grupos = pivot.groupby(list(pivot.columns[:-1])).size().reset_index(name="Motoristas")

top_grupos = grupos.sort_values(by=list(grupos.columns[:-1]),ascending=False).head(5)

fig_prod = go.Figure()

for mes in ultimos_meses:
    fig_prod.add_bar(
        x=top_grupos.index.astype(str),
        y=top_grupos[mes],
        name=str(mes)
    )

# previsão mês atual
br_holidays = holidays.Brazil()

hoje = datetime.now()

datas_mes = pd.date_range(
    start=hoje.replace(day=1),
    end=hoje.replace(day=28)+pd.offsets.MonthEnd()
)

dias_uteis = len([d for d in datas_mes if d.weekday()<5 and d.date() not in br_holidays])
dias_passados = len([d for d in datas_mes if d<=hoje and d.weekday()<5 and d.date() not in br_holidays])

media_diaria = top_grupos[ultimos_meses[-1]] / max(dias_passados,1)

previsao = media_diaria * dias_uteis

fig_prod.add_scatter(
    x=top_grupos.index.astype(str),
    y=previsao,
    mode="lines",
    name="Previsão mês",
    line=dict(color="white",dash="dash")
)

fig_prod.update_layout(template="plotly_dark",height=350)

st.plotly_chart(fig_prod,use_container_width=True)


# ================================
# GRUPOS MENOR UTILIZAÇÃO
# ================================

st.subheader("GRUPOS MENOR UTILIZAÇÃO (3 MESES)")

low_grupos = grupos.sort_values(by=list(grupos.columns[:-1]),ascending=True).head(5)

fig_low = go.Figure()

for mes in ultimos_meses:
    fig_low.add_bar(
        x=low_grupos.index.astype(str),
        y=low_grupos[mes],
        name=str(mes)
    )

fig_low.update_layout(template="plotly_dark",height=350)

st.plotly_chart(fig_low,use_container_width=True)
# ================================
# UTILIZAÇÃO DE FROTA
# ================================

st.subheader("ANÁLISE DE UTILIZAÇÃO DE FROTA")

dias = df_global.groupby("Motorista")["Data"].nunique().reset_index(name="Dias Trabalhados")

media = dias["Dias Trabalhados"].mean()

abaixo_media = dias[dias["Dias Trabalhados"] < media]

abaixo_media = abaixo_media.sort_values("Dias Trabalhados").head(30)

fig_dias = go.Figure()

fig_dias.add_bar(
x=abaixo_media["Motorista"],
y=abaixo_media["Dias Trabalhados"],
name="Abaixo da Média",
marker_color="red"
)

fig_dias.add_hline(
y=media,
line_dash="dash",
line_color="white",
annotation_text="Média Dias Trabalhados"
)

fig_dias.update_layout(
template="plotly_dark",
height=320
)

st.plotly_chart(fig_dias, use_container_width=True)

# ================================
# RANKING MOTORISTAS DISPONÍVEIS
# ================================

st.subheader("RANKING MOTORISTAS DISPONÍVEIS")

ranking = ultima_viagem.copy()

ranking["Score Disponibilidade"] = ranking["Dias Sem Viagem"]

ranking = ranking.sort_values("Score Disponibilidade",ascending=False).head(15)

fig_rank = px.bar(
ranking,
x="Motorista",
y="Score Disponibilidade",
color="Score Disponibilidade",
color_continuous_scale=["yellow","orange","red"],
template="plotly_dark"
)

fig_rank.update_layout(height=300)

st.plotly_chart(fig_rank,use_container_width=True)

# ================================
# REPETIÇÃO DE ROTAS
# ================================

st.subheader("REPETIÇÃO DE ROTAS")

df_global["Rota"] = df_global["Coleta"] + " → " + df_global["Entrega"]

rotas = df_global.groupby("Rota").size().reset_index(name="Qtd")

rotas = rotas.sort_values("Qtd")

fig_rotas = px.bar(
rotas.tail(20),
x="Qtd",
y="Rota",
orientation="h",
color="Qtd",
color_continuous_scale=["yellow","orange","red"],
template="plotly_dark"
)

fig_rotas.update_layout(height=350)

st.plotly_chart(fig_rotas, use_container_width=True)

# ================================
# FREQUÊNCIA OPERACIONAL
# ================================

st.subheader("FREQUÊNCIA OPERACIONAL DE ROTAS")

periodo = st.date_input(
"Período da tabela",
(primeiro_dia_mes, ultima_data)
)

df_freq = df.copy()

df_freq = df_freq[
(df_freq["Data"]>=pd.to_datetime(periodo[0])) &
(df_freq["Data"]<=pd.to_datetime(periodo[1]))
]

br_holidays = holidays.Brazil()

datas = pd.date_range(start=periodo[0], end=periodo[1])

dias_possiveis = len([
d for d in datas if d.weekday()<5 and d.date() not in br_holidays
])

dias_motorista = df_freq.groupby("Motorista")["Data"].nunique().reset_index()

dias_motorista.columns=["Motorista","Dias Trabalhados Motorista"]

def velocidade(tipo):

    tipo=str(tipo).lower()

    if "carreta" in tipo:
        return 57
    elif "bitrem" in tipo:
        return 51
    return 66

df_freq["Velocidade"]=df_freq["Tipo Veiculo"].apply(velocidade)

df_freq["Horas"]=df_freq["Km Rota"]/df_freq["Velocidade"]

horas_motorista=df_freq.groupby("Motorista").agg({
"Horas":"sum",
"Data":"nunique"
}).reset_index()

horas_motorista["Media Horas Dia"]=horas_motorista["Horas"]/horas_motorista["Data"]

horas_motorista=horas_motorista[["Motorista","Media Horas Dia"]]

rota_freq=df_freq.groupby(
["Coleta","Entrega","Motorista","Tipo Prestador","Gestor","Cliente"]
).agg({
"Data":"nunique",
"Km Rota":"mean",
"Frete Total":"sum"
}).reset_index()

rota_freq.columns=[
"Origem","Destino","Motorista","Tipo Prestador","Gestor","Cliente",
"Dias Rota","KM Rota","Frete Total"
]

freq=rota_freq.merge(dias_motorista,on="Motorista",how="left")

freq=freq.merge(horas_motorista,on="Motorista",how="left")

freq["Dias Possíveis"]=dias_possiveis

freq["Ocupação Motorista %"]=(freq["Dias Trabalhados Motorista"]/freq["Dias Possíveis"])*100

freq["Dedicação %"]=(freq["Dias Rota"]/freq["Dias Trabalhados Motorista"])*100

freq["Ocupação Motorista %"]=freq["Ocupação Motorista %"].round(2).astype(str)+"%"

freq["Dedicação %"]=freq["Dedicação %"].round(2).astype(str)+"%"

freq["KM Rota"]=freq["KM Rota"].round(2)

freq["Frete Total"]=freq["Frete Total"].round(2)

freq["Media Horas Dia"]=freq["Media Horas Dia"].round(2)

freq=freq.sort_values("Dias Rota",ascending=False)

gb=GridOptionsBuilder.from_dataframe(freq)

gb.configure_default_column(filter=True,sortable=True,resizable=True)

gb.configure_grid_options(
enableRangeSelection=True,
pagination=True,
paginationPageSize=20
)

gridOptions=gb.build()

AgGrid(
freq,
gridOptions=gridOptions,
update_mode=GridUpdateMode.NO_UPDATE,
theme="balham-dark",
height=420,
fit_columns_on_grid_load=True
)

# ================================
# DIÁRIO
# ================================

st.subheader("DIÁRIO")

diario=df_global.copy()

diario["Dia"]=diario["Data"].dt.day

diario=diario.groupby("Dia").agg({
"Km Rota":"sum",
"Km_Deslocamento":"sum"
}).reset_index()

diario["Total"]=diario["Km Rota"]+diario["Km_Deslocamento"]

diario["%Faturado"]=diario["Km Rota"]/diario["Total"]

diario["%Vazio"]=diario["Km_Deslocamento"]/diario["Total"]

fig=go.Figure()

fig.add_bar(
x=diario["Dia"],
y=diario["%Faturado"],
marker_color="#ffd400"
)

fig.add_scatter(
x=diario["Dia"],
y=diario["%Vazio"],
mode="lines+markers",
line=dict(color="#ff7b00",width=3)
)

fig.update_layout(template="plotly_dark",height=340)

st.plotly_chart(fig,use_container_width=True)

# ================================
# KM FATURADO X KM VAZIO
# ================================

st.subheader("KM FATURADO X KM VAZIO")

km_cliente=df_global.groupby("Cliente").agg({
"Km Rota":"sum",
"Km_Deslocamento":"sum"
}).reset_index()

fig_km=go.Figure()

fig_km.add_bar(
x=km_cliente["Cliente"],
y=km_cliente["Km Rota"],
marker_color="#ffd400"
)

fig_km.add_bar(
x=km_cliente["Cliente"],
y=km_cliente["Km_Deslocamento"],
marker_color="#ff7b00"
)

fig_km.update_layout(template="plotly_dark",barmode="stack")

st.plotly_chart(fig_km,use_container_width=True)
