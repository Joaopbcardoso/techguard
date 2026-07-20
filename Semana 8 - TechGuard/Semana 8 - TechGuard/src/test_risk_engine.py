"""
Suite de Testes Automatizados — Motor de Risco Americas TechGuard

Cobre os casos de fronteira do risk_engine.py, validando:
  - Criticalidade por transbordamento (nível_rio >= HAND)
  - Alertas por enxurrada urbana (chuva + NDBI)
  - Integridade e serialização do payload JSON
  - Falha controlada por campos ausentes

Execute com:
  pytest src/test_risk_engine.py -v
"""

import json
import math
import pytest
from risk_engine import (
    calcular_score_risco,
    classificar_risco,
    construir_payload,
    validar_payload,
    simular_leitura_sensor,
    LIMIAR_CRITICAL,
)


class TestMotorDeRisco:

    def test_transbordamento_confirmado_gera_critical(self):
        """
        Quando o nível do rio supera o HAND, a água invadiu o terreno.
        A regra física de transbordamento deve forçar risk_level = 'critical'.
        """
        risk, msg, score = classificar_risco(hand=2.0, chuva_mm_h=5, nivel_rio=2.5, ndbi=0.4)
        assert risk == "critical", f"Esperado 'critical', obtido '{risk}' (score={score})"
        assert "EVACUACAO" in msg

    def test_margem_zero_aciona_critical(self):
        """
        Com nivel_rio exatamente igual ao HAND (margem=0), a regra física
        de transbordamento deve ser acionada e retornar 'critical'.
        """
        risk, _, score = classificar_risco(hand=3.0, chuva_mm_h=0, nivel_rio=3.0, ndbi=0.0)
        assert risk == "critical", f"Margem zero deve resultar em 'critical', score={score}"

    def test_enxurrada_urbana_gera_alert(self):
        """
        Bairro alto (HAND alto = sem risco fluvial) com chuva extrema e solo
        altamente impermeável deve gerar pelo menos 'alert' por enxurrada.
        """
        risk, msg, score = classificar_risco(hand=18.0, chuva_mm_h=85, nivel_rio=0.2, ndbi=0.90)
        assert risk in ("alert", "critical"), f"Esperado 'alert' ou 'critical', obtido '{risk}'"

    def test_condicao_segura_retorna_safe(self):
        """
        HAND alto, nível do rio baixo e chuva fraca devem resultar em 'safe'.
        """
        risk, _, score = classificar_risco(hand=15.0, chuva_mm_h=2, nivel_rio=0.3, ndbi=0.3)
        assert risk == "safe", f"Esperado 'safe', obtido '{risk}' (score={score})"

    def test_score_limitado_entre_0_e_100(self):
        """
        O score nunca deve ultrapassar 100 nem ficar abaixo de 0, independente dos inputs.
        """
        for (h, c, n, nd) in [(0.1, 150, 10.0, 1.0), (50.0, 0, 0, 0), (2.0, 80, 1.9, 0.95)]:
            score = calcular_score_risco(h, c, n, nd)
            assert 0.0 <= score <= 100.0, f"Score fora dos limites: {score} para inputs={h,c,n,nd}"


class TestPayloadJSON:

    def test_payload_contem_todos_campos_obrigatorios(self):
        """
        Verifica se construir_payload preenche todos os 10 campos obrigatórios
        definidos na especificação da atividade.
        """
        campos_esperados = [
            "device_id", "timestamp", "latitude", "longitude",
            "sensor_type", "sensor_value", "unit",
            "risk_level", "alert_message", "source"
        ]
        payload = construir_payload(
            device_id="node_teste_01", lat=-27.0, lon=-48.0,
            sensor_type="nivel_agua", sensor_value=1.5, unit="m",
            risk_level="safe", alert_message="Tudo normal."
        )
        for campo in campos_esperados:
            assert campo in payload, f"Campo obrigatório ausente: '{campo}'"

    def test_validar_payload_retorna_json_valido(self):
        """
        validar_payload deve retornar uma string JSON parseável com os dados corretos.
        """
        payload = construir_payload(
            device_id="node_teste_02", lat=-27.5, lon=-48.5,
            sensor_type="pluviometro", sensor_value=22.3, unit="mm/h",
            risk_level="attention", alert_message="Chuva moderada.",
            score=30.5
        )
        json_str = validar_payload(payload)
        data = json.loads(json_str)

        assert data["device_id"] == "node_teste_02"
        assert data["risk_level"] == "attention"
        assert data["sensor_value"] == 22.3
        assert data["source"] == "techguard_defesa_civil_v2"
        assert "timestamp" in data

    def test_validar_payload_levanta_erro_se_campo_ausente(self):
        """
        validar_payload deve lançar ValueError se qualquer campo obrigatório faltar.
        Simula um pacote corrompido ou gerado incorretamente.
        """
        payload_corrompido = {
            "device_id": "node_corrompido",
            "risk_level": "critical"
            # Faltam 8 campos obrigatórios
        }
        with pytest.raises(ValueError) as excinfo:
            validar_payload(payload_corrompido)
        assert "campos obrigatórios ausentes" in str(excinfo.value)

    def test_sensor_value_arredondado(self):
        """
        Valores de sensor devem ser arredondados para 2 casas decimais
        antes da serialização, mantendo compatibilidade com limitações do
        payload LoRa (economia de bytes).
        """
        payload = construir_payload(
            device_id="node_round", lat=0, lon=0,
            sensor_type="nivel_agua", sensor_value=3.14159265,
            unit="m", risk_level="safe", alert_message="Ok."
        )
        assert payload["sensor_value"] == 3.14


class TestSimuladorDeCenarios:

    def test_cenario_critico_gera_valores_altos(self):
        """
        No cenário 'critico', os valores simulados de nível de água devem ser
        suficientemente altos para representar uma emergência real.
        """
        valores = [simular_leitura_sensor("nivel_agua", "critico") for _ in range(20)]
        assert all(v > 2.0 for v in valores), \
            "Cenário crítico deve gerar nível de água sempre acima de 2.0m"

    def test_cenario_normal_gera_valores_seguros(self):
        """
        No cenário 'normal', os valores de chuva devem ser baixos o suficiente
        para não disparar alertas críticos.
        """
        valores = [simular_leitura_sensor("pluviometro", "normal") for _ in range(20)]
        assert all(v < 10.0 for v in valores), \
            "Cenário normal deve gerar chuva abaixo de 10 mm/h"
