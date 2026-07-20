"""
Pipeline de Telemetria Ambiental — Americas TechGuard (Trilha B | Software-only)

Gera payloads JSON representando leituras de sensores ambientais (pluviômetro e
nível de água), aplica a regra de classificação de risco do motor HAND e simula
o envio dessas mensagens para a rede LoRa/Meshtastic via saída serial ou arquivo.

Referências:
  - Nguyen et al. (2023). DOI: 10.1016/j.iotcps.2023.04.005
  - Becker et al. (2026). arXiv: 2605.20379
"""

import json
import time
import random
import os
from datetime import datetime, timezone
from risk_engine import (
    classificar_risco, construir_payload, validar_payload, simular_leitura_sensor
)

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO DOS NÓS SENSORES (Mock — representa dispositivos físicos de campo)
# ---------------------------------------------------------------------------
# Cada nó simula um dispositivo LILYGO TTGO T-Beam ou similar, com sensor de
# nível acoplado via I2C e pluviômetro de báscula. HAND e NDBI são valores
# obtidos a partir de DEM (Modelo Digital de Elevação) e imagens Sentinel-2.
NOS_SENSORES = [
    {
        "device_id":   "node_alpha_01",
        "node_name":   "Sensor Planície Ribeirinha",
        "sensor_type": "nivel_agua",
        "unit":        "m",
        "lat":         -27.5954,
        "lon":         -48.5480,
        "hand":        1.2,    # Ponto baixo próximo ao canal de drenagem principal
        "ndbi":        0.30,
        "source":      "simulacao_local"
    },
    {
        "device_id":   "node_beta_02",
        "node_name":   "Sensor Pluviométrico Centro",
        "sensor_type": "pluviometro",
        "unit":        "mm/h",
        "lat":         -27.5960,
        "lon":         -48.5495,
        "hand":        3.1,    # Área urbana central com alta impermeabilização
        "ndbi":        0.82,
        "source":      "simulacao_local"
    },
    {
        "device_id":   "node_gamma_03",
        "node_name":   "Sensor Afluente Norte",
        "sensor_type": "nivel_agua",
        "unit":        "m",
        "lat":         -27.5930,
        "lon":         -48.5510,
        "hand":        2.0,    # Margem intermediária, próxima a afluente secundário
        "ndbi":        0.55,
        "source":      "simulacao_local"
    }
]


def executar_pipeline(cenario="normal", salvar_output=True):
    """
    Orquestrador principal do pipeline de dados.
    
    Fluxo:
      1. Ingestão (Mock de leitura do sensor)
      2. Processamento & Classificação de Risco (via risk_engine)
      3. Montagem do Payload JSON
      4. Validação Estrutural
      5. Egressão / Transmissão (Mock da interface serial LoRa)
      6. Persistência do output (arquivo JSON para evidência)
    """
    print("=" * 60)
    print("  Americas TechGuard | Pipeline de Telemetria Ambiental")
    print(f"  Cenário: {cenario.upper()} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    payloads_gerados = []

    for no in NOS_SENSORES:
        print(f"\n[TX] [{no['device_id']}] {no['node_name']}")
        print(f"   HAND: {no['hand']}m | NDBI: {no['ndbi']}")

        # 1. Ingestão: leitura simulada do sensor
        sensor_value = simular_leitura_sensor(no["sensor_type"], cenario)

        # Para o cálculo de risco, precisamos de nivel_rio e chuva.
        # Pluviômetros informam a chuva diretamente; sensores de nível informam o rio.
        if no["sensor_type"] == "nivel_agua":
            nivel_rio = sensor_value
            chuva = simular_leitura_sensor("pluviometro", cenario)
        else:
            chuva = sensor_value
            nivel_rio = simular_leitura_sensor("nivel_agua", cenario)

        print(f"   Leitura: {no['sensor_type']} = {sensor_value} {no['unit']} | chuva = {chuva} mm/h")

        # 2. Processamento: classificação de risco multivariável
        risk_level, alert_message, score = classificar_risco(
            hand=no["hand"], chuva_mm_h=chuva,
            nivel_rio=nivel_rio, ndbi=no["ndbi"]
        )

        print(f"   Risco: {risk_level.upper()} (score: {score}/100)")
        print(f"   Alerta: {alert_message}")

        # 3. Montagem do Payload JSON
        payload = construir_payload(
            device_id=no["device_id"],
            lat=no["lat"], lon=no["lon"],
            sensor_type=no["sensor_type"],
            sensor_value=sensor_value,
            unit=no["unit"],
            risk_level=risk_level,
            alert_message=alert_message,
            score=score,
            metadata={"node_name": no["node_name"], "hand_m": no["hand"], "ndbi": no["ndbi"]}
        )

        # 4. Validação
        try:
            json_string = validar_payload(payload)
        except ValueError as e:
            print(f"   [ERRO] PAYLOAD INVALIDO: {e}")
            continue

        payloads_gerados.append(payload)

        # 5. Mock de Transmissão (simula interface Serial/TX do módulo LoRa)
        print("   --- [ TX -> LoRa/Meshtastic ] ---")
        print(f"   {json_string[:120]}{'...' if len(json_string) > 120 else ''}")

        time.sleep(0.5)  # Delay mínimo entre transmissões (duty cycle LoRa)

    print("\n" + "=" * 60)
    print(f"  Pipeline concluido: {len(payloads_gerados)}/{len(NOS_SENSORES)} nos processados.")
    print("=" * 60)

    # 6. Persistência de output para evidência de funcionamento
    if salvar_output and payloads_gerados:
        os.makedirs("../outputs", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"../outputs/payloads_{cenario}_{ts}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payloads_gerados, f, ensure_ascii=False, indent=2)
        print(f"\n[SALVO] Output salvo em: {output_path}")

    return payloads_gerados


if __name__ == "__main__":
    # Executa todos os cenários para gerar evidências completas
    for cenario in ["normal", "chuva_moderada", "tempestade", "critico"]:
        print(f"\n\n>>> SIMULANDO CENÁRIO: {cenario.upper()} <<<")
        executar_pipeline(cenario=cenario, salvar_output=True)
        print()
