"""
Dashboard do Centro de Operações de Defesa Civil (CODC)
Americas TechGuard — Sistema de Monitoramento Hídrico

Consolida a telemetria dos nós LoRa, calcula risco baseado em HAND,
e exibe os payloads JSON que transitariam pela rede Meshtastic
para os celulares dos operadores e população em área de risco.
"""

import streamlit as st
import json
import random
import time
from datetime import datetime, timezone
from risk_engine import (
    classificar_risco, construir_payload, validar_payload,
    simular_leitura_sensor, calcular_score_risco
)

# ---------------------------------------------------------------------------
# CONFIG DA PÁGINA
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="CODC – Defesa Civil TechGuard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado para visual de sistema operacional crítico
st.markdown("""
<style>
    /* Fundo escuro do painel principal */
    .main { background-color: #0d1117; }
    
    /* Header de seção */
    .codc-header {
        background: linear-gradient(135deg, #1a2744 0%, #0f3460 100%);
        border-left: 4px solid #00d4ff;
        padding: 12px 18px;
        border-radius: 6px;
        margin-bottom: 16px;
    }
    
    /* Card de nó sensor */
    .node-card {
        background: #161b22;
        border-radius: 10px;
        padding: 14px;
        border: 1px solid #30363d;
        margin-bottom: 10px;
    }
    
    /* Barra de score de risco */
    .score-bar-container {
        background: #21262d;
        border-radius: 4px;
        height: 8px;
        margin-top: 6px;
        width: 100%;
    }

    /* Tag de status */
    .status-safe     { color: #3fb950; font-weight: 700; font-size: 1.1rem; }
    .status-attention{ color: #d29922; font-weight: 700; font-size: 1.1rem; }
    .status-alert    { color: #f85149; font-weight: 700; font-size: 1.1rem; }
    .status-critical { color: #ff0000; font-weight: 700; font-size: 1.1rem; animation: blink 0.8s step-start infinite; }
    
    @keyframes blink { 50% { opacity: 0; } }
    
    /* Terminal Meshtastic */
    .terminal-box {
        background: #010409;
        color: #00ff41;
        font-family: 'Courier New', monospace;
        font-size: 0.78rem;
        padding: 14px;
        border-radius: 6px;
        border: 1px solid #238636;
        max-height: 400px;
        overflow-y: auto;
        white-space: pre-wrap;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# MEMÓRIA TÉCNICA DOS NÓS (simulação de banco de dados de dispositivos de campo)
# ---------------------------------------------------------------------------
# Cada nó representa um ponto físico monitorado na bacia hidrográfica.
# HAND e NDBI são fixos por localização (dados de satélite/DEM).
# Chuva e nível do rio são lidos em tempo real pelos sensores de campo.

NOS_CAMPO = [
    {
        "device_id": "node_planicie_01",
        "nome":      "Bairro Vila Ribeirinha",
        "regiao":    "Planície Fluvial",
        "hand":      1.2,    # Área baixa — altamente vulnerável ao transbordamento
        "ndbi":      0.30,   # Solo ainda com cobertura vegetal parcial (menor impermeabilização)
        "lat":       -27.5950,
        "lon":       -48.5480,
        "populacao": 4_200,
    },
    {
        "device_id": "node_centro_02",
        "nome":      "Centro Comercial",
        "regiao":    "Área Urbana Central",
        "hand":      3.1,    # Margem razoável, mas impermeabilização muito alta
        "ndbi":      0.82,   # Asfalto e construções cobrem quase toda a superfície
        "lat":       -27.5960,
        "lon":       -48.5490,
        "populacao": 18_500,
    },
    {
        "device_id": "node_industrial_03",
        "nome":      "Distrito Industrial Norte",
        "regiao":    "Zona Industrial",
        "hand":      2.0,    # Cota intermediária próxima a afluente secundário
        "ndbi":      0.70,
        "lat":       -27.5930,
        "lon":       -48.5510,
        "populacao": 3_100,
    },
    {
        "device_id": "node_encosta_04",
        "nome":      "Bairro Alto da Serra",
        "regiao":    "Encosta",
        "hand":      18.5,   # Região elevada — risco primário é enxurrada, não inundação fluvial
        "ndbi":      0.35,
        "lat":       -27.5900,
        "lon":       -48.5520,
        "populacao": 2_800,
    },
]

# ---------------------------------------------------------------------------
# SIDEBAR — PAINEL DE CONTROLE DE CENÁRIO
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("""
    <div class='codc-header'>
        <h3 style='margin:0; color:#00d4ff'>🛡️ CODC</h3>
        <p style='margin:0; color:#8b949e; font-size:0.8rem'>Centro de Operações<br>Defesa Civil TechGuard</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 🌦️ Simulação de Cenário Climático")
    cenario_global = st.selectbox(
        "Cenário Pré-definido:",
        ["normal", "chuva_moderada", "tempestade", "critico"],
        format_func=lambda x: {
            "normal": "🟢 Normalidade Operacional",
            "chuva_moderada": "🟡 Chuva Moderada",
            "tempestade": "🟠 Tempestade Severa",
            "critico": "🔴 Evento Extremo (Emergência)",
        }[x]
    )

    st.divider()
    st.markdown("#### 📡 Telemetria Manual (Override)")
    override_ativo = st.toggle("Sobrescrever leituras dos sensores manualmente")
    nivel_rio_manual = 0.5
    chuva_manual = 5
    if override_ativo:
        nivel_rio_manual = st.slider("Nível do Rio Principal (m):", 0.0, 6.0, 0.5, step=0.05,
                                     help="Elevação da lâmina d'água acima do leito normal da calha.")
        chuva_manual = st.slider("Chuva Acumulada (mm/h):", 0, 150, 5, step=5,
                                 help="Taxa pluviométrica média sobre a bacia de contribuição.")

    st.divider()
    st.markdown("#### ⚙️ Configurações")
    auto_refresh = st.toggle("Auto-refresh (15s)", value=False)
    mostrar_apenas_alertas = st.toggle("Mostrar apenas nós em alerta", value=False)

    st.divider()
    st.caption("Referências: Nguyen & Phung (2022) – LoRaWAN para monitoramento de inundações | Becker et al. (2024) – Redes Mesh Meshtastic off-grid")

# ---------------------------------------------------------------------------
# CABEÇALHO PRINCIPAL
# ---------------------------------------------------------------------------

col_title, col_time = st.columns([4, 1])
with col_title:
    st.markdown("# 🛡️ Centro de Operações de Defesa Civil")
    st.markdown("**Sistema de Alerta Precoce de Inundações | Americas TechGuard**")
with col_time:
    ts_agora = datetime.now().strftime("%d/%m/%Y\n%H:%M:%S")
    st.code(ts_agora, language=None)

st.divider()

# ---------------------------------------------------------------------------
# PROCESSAMENTO DE TELEMETRIA
# ---------------------------------------------------------------------------

resultados = []
total_criticos = 0
total_alertas = 0
populacao_risco = 0

for no in NOS_CAMPO:
    # Leitura dos sensores — manual ou por cenário simulado
    if override_ativo:
        nivel_rio = nivel_rio_manual
        chuva = chuva_manual
    else:
        # Cada nó tem sua leitura simulada independentemente (realismo de campo)
        nivel_rio = simular_leitura_sensor("nivel_agua", cenario_global)
        chuva = simular_leitura_sensor("pluviometro", cenario_global)

    # Avaliação de risco multivariável
    risk_level, alert_msg, score = classificar_risco(
        hand=no["hand"], chuva_mm_h=chuva,
        nivel_rio=nivel_rio, ndbi=no["ndbi"]
    )

    # Montagem do payload JSON (schema atividade TechGuard)
    payload = construir_payload(
        device_id=no["device_id"],
        lat=no["lat"], lon=no["lon"],
        sensor_type="nivel_agua",
        sensor_value=nivel_rio,
        unit="m",
        risk_level=risk_level,
        alert_message=alert_msg,
        score=score,
        metadata={
            "chuva_mm_h": chuva,
            "hand_m": no["hand"],
            "ndbi": no["ndbi"],
            "populacao_afetada": no["populacao"] if risk_level in ["alert", "critical"] else 0,
        }
    )
    json_str = validar_payload(payload)

    resultados.append({
        "no": no, "nivel_rio": nivel_rio, "chuva": chuva,
        "risk_level": risk_level, "alert_msg": alert_msg,
        "score": score, "json_str": json_str,
    })

    if risk_level == "critical":
        total_criticos += 1
        populacao_risco += no["populacao"]
    elif risk_level == "alert":
        total_alertas += 1
        populacao_risco += no["populacao"]

# ---------------------------------------------------------------------------
# MÉTRICAS DE RESUMO OPERACIONAL
# ---------------------------------------------------------------------------

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("🔴 Nós Críticos", total_criticos,
              delta="EMERGÊNCIA" if total_criticos > 0 else None,
              delta_color="inverse")
with m2:
    st.metric("🟠 Nós em Alerta", total_alertas)
with m3:
    st.metric("👥 Pessoas em Risco", f"{populacao_risco:,}".replace(",", "."))
with m4:
    cenario_labels = {"normal": "Normal", "chuva_moderada": "Moderado",
                      "tempestade": "Tempestade", "critico": "Extremo"}
    st.metric("🌦️ Cenário Ativo",
              "Manual" if override_ativo else cenario_labels.get(cenario_global, cenario_global))

st.divider()

# ---------------------------------------------------------------------------
# PAINEL DE NÓS
# ---------------------------------------------------------------------------

st.markdown("### 📡 Status dos Nós Sensores na Bacia")

CORES_RISCO = {
    "safe":      "#3fb950",
    "attention": "#d29922",
    "alert":     "#f0883e",
    "critical":  "#f85149",
}
ICONES_RISCO = {
    "safe": "🟢", "attention": "🟡", "alert": "🟠", "critical": "🔴"
}
LABELS_RISCO = {
    "safe": "SEGURO", "attention": "ATENÇÃO", "alert": "ALERTA", "critical": "CRÍTICO"
}

cols = st.columns(len(NOS_CAMPO))

for idx, res in enumerate(resultados):
    no    = res["no"]
    risk  = res["risk_level"]
    score = res["score"]

    if mostrar_apenas_alertas and risk == "safe":
        continue

    with cols[idx]:
        cor = CORES_RISCO[risk]
        icone = ICONES_RISCO[risk]
        label = LABELS_RISCO[risk]

        # Barra de score visual (HTML inline)
        largura = int(score)
        st.markdown(f"""
        <div class='node-card'>
            <div style='font-size:0.75rem; color:#8b949e; margin-bottom:4px'>{no['device_id']}</div>
            <div style='font-size:1rem; font-weight:700; color:#e6edf3'>{no['nome']}</div>
            <div style='font-size:0.75rem; color:#8b949e; margin-bottom:8px'>{no['regiao']}</div>
            <div style='color:{cor}; font-size:1.3rem; font-weight:800'>{icone} {label}</div>
            <div style='margin-top:8px; font-size:0.72rem; color:#8b949e'>Score de Risco</div>
            <div class='score-bar-container'>
                <div style='background:{cor}; width:{largura}%; height:100%; border-radius:4px;'></div>
            </div>
            <div style='font-size:0.9rem; color:{cor}; font-weight:700; margin-top:2px'>{score}/100</div>
            <hr style='border-color:#30363d; margin:8px 0'/>
            <div style='font-size:0.72rem; color:#8b949e'>
                🏔️ HAND: <b style='color:#e6edf3'>{no['hand']} m</b> &nbsp;|&nbsp;
                🏗️ NDBI: <b style='color:#e6edf3'>{no['ndbi']}</b>
            </div>
            <div style='font-size:0.72rem; color:#8b949e; margin-top:4px'>
                🌊 Rio: <b style='color:#58a6ff'>{res['nivel_rio']} m</b> &nbsp;|&nbsp;
                🌧️ Chuva: <b style='color:#58a6ff'>{res['chuva']} mm/h</b>
            </div>
            <div style='font-size:0.72rem; color:#8b949e; margin-top:4px'>
                👥 Pop. Exposta: <b style='color:#e6edf3'>{no['populacao']:,}</b>
            </div>
        </div>
        """.replace(",", "."), unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# CENTRO DE ALERTAS
# ---------------------------------------------------------------------------

st.markdown("### 🚨 Centro de Alertas Ativos")

alertas_ativos = [r for r in resultados if r["risk_level"] in ["alert", "critical"]]

if not alertas_ativos:
    st.success("✅ Nenhum alerta ativo no momento. Todas as regiões dentro dos parâmetros operacionais.")
else:
    for res in alertas_ativos:
        no   = res["no"]
        risk = res["risk_level"]
        if risk == "critical":
            st.error(f"🔴 **{no['nome']}** — {res['alert_msg']}")
        else:
            st.warning(f"🟠 **{no['nome']}** — {res['alert_msg']}")

st.divider()

# ---------------------------------------------------------------------------
# TERMINAL MESHTASTIC (Tráfego de Rede LoRa Simulado)
# ---------------------------------------------------------------------------

st.markdown("### 📟 Terminal LoRa/Meshtastic — Pacotes em Trânsito na Malha")
st.caption(
    "Cada linha abaixo representa um pacote JSON transmitido pelo protocolo Meshtastic "
    "sobre o rádio LoRa 915 MHz. Os pacotes chegam ao aplicativo oficial Meshtastic "
    "nos celulares dentro da área de cobertura, gerando notificações de alerta para a população."
)

with st.expander("📡 Ver tráfego da rede mesh (JSON payloads)", expanded=True):
    linhas_terminal = []
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    for res in resultados:
        no   = res["no"]
        risk = res["risk_level"]
        json_formatado = json.dumps(json.loads(res["json_str"]), ensure_ascii=False, indent=2)

        if risk == "safe":
            linhas_terminal.append(
                f"[{ts}] [{no['device_id']}] keepalive — nível normal (pacote completo omitido para economizar duty cycle)"
            )
        else:
            linhas_terminal.append(f"[{ts}] [{no['device_id']}] >>> ROTEANDO ALERTA PARA MALHA <<<")
            linhas_terminal.append(json_formatado)
            linhas_terminal.append("")

    st.code("\n".join(linhas_terminal), language="json")

# ---------------------------------------------------------------------------
# AUTO-REFRESH
# ---------------------------------------------------------------------------

if auto_refresh:
    st.toast("🔄 Atualizando telemetria...", icon="📡")
    time.sleep(15)
    st.rerun()
