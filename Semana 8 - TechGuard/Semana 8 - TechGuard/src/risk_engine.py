"""
Motor de Risco Hídrico - Americas TechGuard (Defesa Civil)
Avaliação determinística multivariável baseada em:
  - HAND (Height Above Nearest Drainage): altimetria relativa ao canal de drenagem
  - Chuva Acumulada (mm/h): intensidade pluviométrica do evento
  - Nível do Rio (m): leitura dos sensores de régua/bóia no leito da calha
  - NDBI (Normalized Difference Built-up Index): proxy de impermeabilização do solo urbano
"""

from datetime import datetime, timezone
import json
import math

# ---------------------------------------------------------------------------
# CONSTANTES DE LIMIAR (Calibradas com base em eventos históricos brasileiros)
# ---------------------------------------------------------------------------

# Coeficiente de contribuição do NDBI no risco de enxurrada urbana.
# Pesquisas em bacias urbanas da Serra Gaúcha e Vale do Itajaí indicam que
# cada 10% de aumento em área impermeável aumenta o pico de cheia em ~3–7%.
COEF_NDBI = 0.55

# Limiares de score de risco composto (adimensional, 0 a 100)
# Atenção: margem <= 0 força 'critical' diretamente (regra física, não depende do score).
LIMIAR_ATTENTION = 20
LIMIAR_ALERT     = 30
LIMIAR_CRITICAL  = 80


def calcular_score_risco(hand, chuva_mm_h, nivel_rio, ndbi=0.5):
    """
    Calcula um score de risco composto (0–100) cruzando variáveis hidrológicas e urbanas.

    A equação final combina três componentes independentes de risco:
      1. Margem HAND-Rio: distância vertical entre o terreno e a lâmina d'água.
         Quando nivel_rio >= hand, transbordamento já ocorreu (componente domina).
      2. Risco de Enxurrada: produto da intensidade de chuva pela impermeabilidade.
         Modela acúmulo superficial rápido em bacias urbanas com alto NDBI.
      3. Tendência de Proximidade: quanto o nível do rio já se aproxima do HAND,
         mesmo sem transbordar, indica fragilidade crescente da margem.

    :param hand:       Altura Above Nearest Drainage do nó (metros).
    :param chuva_mm_h: Precipitação acumulada (mm/h).
    :param nivel_rio:  Nível atual da calha fluvial acima do leito normal (metros).
    :param ndbi:       Índice de impermeabilização do solo (0.0 = sem impermeabilização, 1.0 = totalmente impermeável).
    :return: float entre 0 e 100 representando o risco composto.
    """
    margem = hand - nivel_rio

    # Componente 1: Invasão fluviométrica
    # Quando margem <= 0: inundação confirmada -> penalidade máxima garantida.
    # Caso contrário, decaimento exponencial conforme a margem aumenta.
    if margem <= 0:
        comp_fluvial = 100.0
    else:
        comp_fluvial = max(0.0, 100.0 * math.exp(-0.6 * margem))

    # Componente 2: Enxurrada urbana (Flash Flood)
    # Chuva intensa + solo impermeável podem causar alagamento independente do rio.
    # Normalizado para que 100mm/h + NDBI=1.0 resulte em score máximo neste componente.
    fator_urban = COEF_NDBI * ndbi + (1.0 - COEF_NDBI)
    comp_enxurrada = min(100.0, (chuva_mm_h * fator_urban) / 0.75)

    # Componente 3: Proximidade percentual do rio ao HAND
    if hand > 0:
        comp_proximidade = min(100.0, (nivel_rio / hand) * 100.0)
    else:
        comp_proximidade = 100.0

    # Média ponderada calibrada:
    # Componente fluvial domina (60%) — inundação direta é o risco mais grave.
    # Enxurrada tem peso relevante (30%) — flash floods urbanos são rápidos e letais.
    # Proximidade é indicador antecipado (10%).
    score = (comp_fluvial * 0.60) + (comp_enxurrada * 0.30) + (comp_proximidade * 0.10)

    return round(min(100.0, max(0.0, score)), 2)


def classificar_risco(hand, chuva_mm_h, nivel_rio, ndbi=0.5):
    """
    Mapeia o score numérico de risco para nível nominal e gera a mensagem de alerta.
    A regra física de transbordamento (nivel_rio >= hand) é soberana sobre o score.

    :return: tupla (risk_level: str, alert_message: str, score: float)
    """
    score = calcular_score_risco(hand, chuva_mm_h, nivel_rio, ndbi)
    margem = round(hand - nivel_rio, 2)

    # Regra física direta: margem negativa = água já invadiu o terreno.
    # Esta condição sobrepõe o score numérico por ser determinística —
    # independe da chuva ou impermeabilização.
    if nivel_rio >= hand:
        msg = (
            "[CRITICO] EVACUACAO IMEDIATA: Cota fluvial superou a elevacao do terreno (HAND). "
            f"Inundacao ativa confirmada. Margem HAND negativa: {margem}m. "
            "Acionar Plano de Contingencia Nivel 3."
        )
        return "critical", msg, score

    # Classificação por score para os demais casos
    elif score >= LIMIAR_CRITICAL:
        msg = (
            f"[CRITICO] EVACUACAO IMEDIATA: Score de risco critico ({score}/100). "
            f"Margem de seguranca residual: {margem}m. "
            "Chuva intensa e impermeabilizacao elevada indicam flash flood iminente."
        )
        return "critical", msg, score

    elif score >= LIMIAR_ALERT:
        msg = (
            f"[ALERTA] Risco severo em elevacao. Score: {score}/100. "
            f"Margem HAND disponivel: {margem}m. "
            "Ativar protocolo de evacuacao preventiva e isolar vias de risco."
        )
        return "alert", msg, score

    elif score >= LIMIAR_ATTENTION:
        msg = (
            f"[ATENCAO] Condicoes em deterioracao. Score: {score}/100. "
            f"Margem HAND: {margem}m. "
            "Equipes de campo em prontidao, populacao em alerta."
        )
        return "attention", msg, score

    else:
        msg = (
            f"[SEGURO] Condicoes dentro dos parametros normais. Score: {score}/100. "
            f"Margem HAND: {margem}m. Monitoramento continuo ativo."
        )
        return "safe", msg, score


def construir_payload(device_id, lat, lon, sensor_type, sensor_value, unit,
                      risk_level, alert_message, score=None, metadata=None):
    """
    Serializa a leitura do nó sensor em um payload JSON compatível com o protocolo
    de transmissão LoRa/Meshtastic, respeitando o esquema definido na arquitetura TechGuard.

    O campo 'metadata' é opcional e pode carregar dados extras (HAND, NDBI, score)
    sem quebrar a retrocompatibilidade do esquema base.
    """
    payload = {
        "device_id":     device_id,
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "latitude":      lat,
        "longitude":     lon,
        "sensor_type":   sensor_type,
        "sensor_value":  round(float(sensor_value), 2),
        "unit":          unit,
        "risk_level":    risk_level,
        "alert_message": alert_message,
        "source":        "techguard_defesa_civil_v2"
    }

    # Metadados estendidos (não obrigatórios na transmissão básica, mas documentados no gateway)
    if score is not None:
        payload["risk_score"] = score
    if metadata:
        payload["metadata"] = metadata

    return payload


def validar_payload(payload):
    """
    Valida a integridade do esquema do payload antes da serialização e roteamento.
    Garante que nenhum pacote malformado entre na malha LoRa/Meshtastic.

    :raises ValueError: se qualquer campo obrigatório estiver ausente.
    :return: string JSON serializada, pronta para transmissão via Serial/UART.
    """
    CAMPOS_OBRIGATORIOS = [
        "device_id", "timestamp", "latitude", "longitude",
        "sensor_type", "sensor_value", "unit",
        "risk_level", "alert_message", "source"
    ]
    campos_ausentes = [c for c in CAMPOS_OBRIGATORIOS if c not in payload]
    if campos_ausentes:
        raise ValueError(
            f"Payload inválido — campos obrigatórios ausentes: {campos_ausentes}"
        )

    return json.dumps(payload, ensure_ascii=False, indent=None)


def simular_leitura_sensor(sensor_type, cenario="normal"):
    """
    Gera leituras sintéticas de sensor para fins de simulação.
    Suporta cenários pré-definidos para facilitar os testes.

    :param sensor_type: 'pluviometro' ou 'nivel_agua'
    :param cenario: 'normal', 'chuva_moderada', 'tempestade', 'critico'
    :return: float com o valor simulado
    """
    import random

    faixas = {
        "pluviometro": {
            "normal":          (0.0,  8.0),
            "chuva_moderada":  (10.0, 28.0),
            "tempestade":      (35.0, 65.0),
            "critico":         (70.0, 120.0),
        },
        "nivel_agua": {
            "normal":          (0.2,  1.0),
            "chuva_moderada":  (1.0,  2.0),
            "tempestade":      (2.2,  3.5),
            "critico":         (3.8,  5.5),
        }
    }

    low, high = faixas.get(sensor_type, {}).get(cenario, (0.0, 1.0))
    return round(random.uniform(low, high), 2)
