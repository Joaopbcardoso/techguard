# Americas TechGuard | Período 8 — Integração LoRa-Meshtastic, JSON e Alertas Ambientais

**Estudante:** [SEU NOME AQUI]  
**Instituição:** Centro Universitário SENAI/SC — Campus Florianópolis  
**Período:** 8 | Eixo: Sistemas Embarcados — LoRa, Meshtastic, LoRaWAN, JSON, IoT  
**Trilha Escolhida:** Trilha B — Software-only / Simulação  
**Repositório:** [americas-techguard-lora-meshtastic]()

---

## Objetivo da Solução

Desenvolver uma prova de conceito (PoC) funcional, documentada e reprodutível para estruturar, validar, interpretar e simular o fluxo de transmissão de dados ambientais em formato JSON, considerando uma arquitetura LoRa/Meshtastic voltada à geração de alertas móveis no contexto do **Americas TechGuard**.

O pipeline implementado cobre a cadeia mínima exigida pela atividade:

```
[Sensor de Campo] → [Payload JSON] → [Regra de Risco] → [Alerta] → [Rede LoRa/Meshtastic] → [Celular]
```

---

## Materiais de Referência Obrigatórios

### Artigo Principal
> Nguyen, T. H., et al. **Development of a smart sensing unit for LoRaWAN-based IoT flood monitoring and warning system in catchment areas.** *Internet of Things and Cyber-Physical Systems*, 2023.  
> **DOI:** [10.1016/j.iotcps.2023.04.005](https://doi.org/10.1016/j.iotcps.2023.04.005)  
> **Link:** https://www.sciencedirect.com/science/article/pii/S2667345223000263

**Como este artigo foi aproveitado nesta solução:**  
O artigo propõe uma unidade de sensoriamento inteligente baseada em LoRaWAN para monitoramento de inundações em bacias hidrográficas, integrando sensores de nível d'água e pluviômetros com lógica de alerta em gateway centralizado. Nesta PoC, a estrutura do payload JSON (`device_id`, `sensor_type`, `sensor_value`, `risk_level`, `alert_message`) foi diretamente inspirada na arquitetura de mensagens proposta no artigo. A lógica de classificação de risco do `risk_engine.py` implementa o mesmo conceito de limiares de decisão, adaptando-os para uma abordagem determinística multivariável baseada em HAND, chuva e impermeabilização do solo.

---

### Referência Técnica Complementar
> Becker, L., et al. **A Meshtastic-based LoRa Mesh System for Smart Campus Applications: From Solar-Powered Sensing to Containerized Data Management.** *arXiv*, 2026.  
> **Link:** https://arxiv.org/abs/2605.20379

**Como esta referência foi aproveitada nesta solução:**  
O artigo descreve uma infraestrutura de rede mesh descentralizada com nós alimentados por energia solar, gerenciamento de dados via contêineres Docker e visualização em dashboard. Esta PoC utiliza a mesma topologia conceitual de múltiplos nós com `device_id` únicos e coordenadas geográficas, e simula o terminal de transmissão Meshtastic no dashboard (`app_defesa_civil.py`). O campo `source` do payload foi modelado para distinguir entre dados reais e simulados — diretamente inspirado na separação de ambientes que o artigo propõe entre sensing e containerized management.

---

### Documentação Técnica Meshtastic
- **MQTT/JSON:** https://meshtastic.org/docs/configuration/module/mqtt/
- **Telemetry:** https://meshtastic.org/docs/configuration/module/telemetry/

---

## ETAPA 1 | Estudo Técnico e Diferenças Arquiteturais

### Problema resolvido pelo artigo principal
O artigo endereça a ausência de sistemas de baixo custo, longo alcance e baixo consumo energético para monitoramento de inundações em bacias hidrográficas. Sistemas celulares (3G/4G) são caros, dependem de infraestrutura que frequentemente colapsa exatamente nos eventos extremos que mais precisam de monitoramento, e têm alto consumo energético. A solução proposta com LoRaWAN consegue alcances de 5–15 km com módulos alimentados por baterias de longa duração.

### Papel dos sensores e plataformas IoT no alerta
Sensores de borda (edge) medem variações críticas em tempo real — precipitação (mm/h) e nível dos rios (m). Via módulos LoRa de baixo consumo, esses dados chegam a um gateway que os publica em plataformas IoT (ex: The Things Network, Chirpstack). A partir daí, regras algorítmicas geram alertas que podem ser enviados por SMS, app ou — no caso do Americas TechGuard — via rede Meshtastic para celulares na área afetada.

### Diferenças técnicas: LoRa × LoRaWAN × Meshtastic

| Característica | LoRa | LoRaWAN | Meshtastic |
|---|---|---|---|
| **O que é** | Tecnologia de rádio (camada física) | Protocolo de rede sobre LoRa | Aplicação mesh open-source sobre LoRa |
| **Topologia** | Ponto a ponto | Estrela (gateway centralizado) | Mesh descentralizado |
| **Depende de internet** | Não | Sim (para o Network Server) | Não (off-grid por padrão) |
| **Alcance** | Até 15km (LoS) | Até 15km por gateway | Multi-hop, alcance expandido |
| **Aplicativo** | N/A | N/A | App Android/iOS oficial |

**Escolha desta solução:** O Meshtastic foi escolhido como referência porque o Americas TechGuard foca em cenários onde a infraestrutura convencional está indisponível (exatamente quando eventos extremos ocorrem). A rede mesh garante que mesmo sem internet, os alertas cheguem via BLE ao app Meshtastic nos celulares da população e operadores da Defesa Civil.

---

## ETAPA 2 | Modelagem do Payload JSON

### Schema completo do payload

```json
{
  "device_id":     "node_alpha_01",
  "timestamp":     "2026-07-20T21:38:33.040802+00:00",
  "latitude":      -27.5954,
  "longitude":     -48.5480,
  "sensor_type":   "nivel_agua",
  "sensor_value":  1.72,
  "unit":          "m",
  "risk_level":    "alert",
  "alert_message": "[ALERTA] Risco severo em elevacao. Score: 72.71/100. Margem HAND disponivel: -0.52m. Ativar protocolo de evacuacao preventiva.",
  "source":        "techguard_defesa_civil_v2",
  "risk_score":    72.71,
  "metadata": {
    "node_name": "Sensor Planície Ribeirinha",
    "hand_m":    1.2,
    "ndbi":      0.30
  }
}
```

### Campos obrigatórios
| Campo | Tipo | Descrição |
|---|---|---|
| `device_id` | string | Identificador único do nó sensor |
| `timestamp` | string ISO 8601 | Data/hora UTC da leitura |
| `latitude` | float | Coordenada geográfica do nó |
| `longitude` | float | Coordenada geográfica do nó |
| `sensor_type` | string | Tipo: `nivel_agua`, `pluviometro` |
| `sensor_value` | float | Valor medido (arredondado em 2 casas) |
| `unit` | string | Unidade: `m`, `mm/h` |
| `risk_level` | string | `safe` / `attention` / `alert` / `critical` |
| `alert_message` | string | Mensagem curta para envio via Meshtastic |
| `source` | string | Origem do dado (hardware ou simulação) |

### Campos opcionais (metadados estendidos)
| Campo | Descrição |
|---|---|
| `risk_score` | Score numérico 0–100 do motor de risco |
| `metadata.hand_m` | HAND do ponto (metros) |
| `metadata.ndbi` | Impermeabilização do solo (0–1) |
| `metadata.node_name` | Nome legível do nó |

---

## ETAPA 3 | Implementação Funcional

### Estrutura do repositório

```
Americas-TechGuard-Simulacao/
├── src/
│   ├── risk_engine.py          # Motor de risco: HAND + chuva + NDBI
│   ├── simulador_techguard.py  # Pipeline CLI: ingestão → JSON → alerta → transmissão
│   ├── app_defesa_civil.py     # Dashboard Streamlit: CODC visual
│   └── test_risk_engine.py     # Suite de testes (11 testes, 100% passing)
├── outputs/                    # JSONs gerados pela execução (evidências)
│   ├── payloads_normal_*.json
│   ├── payloads_chuva_moderada_*.json
│   ├── payloads_tempestade_*.json
│   └── payloads_critico_*.json
├── docs/
│   ├── HAND_metodo_V1.ipynb    # Notebook metodológico (cálculo HAND)
│   └── Período 8 - Integração LoRa-Meshtastic.pdf  # Enunciado original
├── requirements.txt
└── README.md
```

### Fluxo de dados implementado

1. **Ingestão (Mock):** `simular_leitura_sensor()` gera valores realistas por cenário (`normal`, `chuva_moderada`, `tempestade`, `critico`).
2. **Processamento:** `calcular_score_risco()` aplica equação multivariável com pesos calibrados. Regra física soberana: `nivel_rio >= HAND` → `critical` direto.
3. **Classificação:** `classificar_risco()` mapeia o score para nível nominal e gera mensagem de alerta.
4. **Montagem:** `construir_payload()` formata o JSON com todos os campos obrigatórios.
5. **Validação:** `validar_payload()` verifica integridade; levanta `ValueError` se campo ausente.
6. **Transmissão (Mock):** Output para stdout simulando saída serial de módulo LoRa (ex: TTGO T-Beam via `Serial.print(json_string)`).

---

## ETAPA 4 | Integração Meshtastic — Trilha B (Software-only)

### Como funciona nesta simulação
O `simulador_techguard.py` imprime no terminal o JSON serializado exatamente como ele seria enviado via `Serial.print()` em um firmware Arduino/PlatformIO rodando em um LILYGO TTGO T-Beam. O `app_defesa_civil.py` exibe no dashboard o tráfego de rede mesh com os mesmos payloads.

### Como conectar ao hardware real (etapa presencial futura)
Em uma integração física com hardware disponível no campus (prof. Lucas):

1. **Flash do firmware Meshtastic** no LILYGO TTGO T-Beam (ESP32 + SX1276) via PlatformIO ou OTA.
2. **Configurar frequência 915 MHz** (padrão Brasil/Américas) e canal de comunicação.
3. **Substituir** a função `simular_leitura_sensor()` por leitura real via I2C (ex: sensor de nível HC-SR04 ou sensor de pressão) e serial de pluviômetro de báscula.
4. **Publicar o JSON** via `Serial.print(json_string)` ou via módulo MQTT (documentação: https://meshtastic.org/docs/configuration/module/mqtt/).
5. **Receber no app** Meshtastic instalado no celular (Android/iOS) via BLE Bluetooth do nó receptor.

### Limitações desta simulação
- Não modela colisões de pacotes RF (duty cycle LoRa 1% obrigatório no Brasil).
- Não testa alcance real nem atenuação por obstáculos (buildings, vegetação, relevo).
- Não valida bateria real (TTGO T-Beam com LiPo 18650 ~1 semana de autonomia típica).
- Não implementa criptografia AES-128 que o Meshtastic usa nativamente.

---

## ETAPA 5 | Resultados e Evidências

### Cenários simulados e outputs gerados

| Cenário | Nível do Rio | Chuva | Resultado típico |
|---|---|---|---|
| `normal` | 0.2–1.0m | 0–8 mm/h | `safe` / `attention` |
| `chuva_moderada` | 1.0–2.0m | 10–28 mm/h | `attention` / `alert` |
| `tempestade` | 2.2–3.5m | 35–65 mm/h | `alert` |
| `critico` | 3.8–5.5m | 70–120 mm/h | `critical` — evacuação imediata |

Os arquivos JSON gerados em cada execução estão na pasta `outputs/` deste repositório como evidência de funcionamento.

### Testes automatizados (100% passing)
```
============================= test session starts =============================
platform win32 -- Python 3.13.2, pytest-9.1.1
collected 11 items

test_risk_engine.py::TestMotorDeRisco::test_transbordamento_confirmado_gera_critical PASSED
test_risk_engine.py::TestMotorDeRisco::test_margem_zero_aciona_critical             PASSED
test_risk_engine.py::TestMotorDeRisco::test_enxurrada_urbana_gera_alert             PASSED
test_risk_engine.py::TestMotorDeRisco::test_condicao_segura_retorna_safe            PASSED
test_risk_engine.py::TestMotorDeRisco::test_score_limitado_entre_0_e_100            PASSED
test_risk_engine.py::TestPayloadJSON::test_payload_contem_todos_campos_obrigatorios PASSED
test_risk_engine.py::TestPayloadJSON::test_validar_payload_retorna_json_valido      PASSED
test_risk_engine.py::TestPayloadJSON::test_validar_payload_levanta_erro_se_campo_ausente PASSED
test_risk_engine.py::TestPayloadJSON::test_sensor_value_arredondado                 PASSED
test_risk_engine.py::TestSimuladorDeCenarios::test_cenario_critico_gera_valores_altos PASSED
test_risk_engine.py::TestSimuladorDeCenarios::test_cenario_normal_gera_valores_seguros PASSED

========================= 11 passed in 0.05s =========================
```

---

## ETAPA 6 | Aplicação ao Americas TechGuard

O JSON construído nesta PoC serve como **camada intermediária universal** entre sensores físicos de campo e os sistemas de recepção:

```
[Pluviômetro / Régua / Satélite Sentinel-2]
         ↓
   [risk_engine.py → JSON padronizado]
         ↓
   [LoRa TX → Rede Meshtastic Mesh]
         ↓
[Celular Defesa Civil / App Meshtastic / Dashboard CODC]
```

### Integrações futuras possíveis
- **APIs de Nowcasting** (INMET, CEMADEN) como fonte alternativa ao sensor físico.
- **Modelos de IA** (ex: LSTM para previsão de nível fluvial) substituindo as regras `if/else` do `risk_engine`.
- **Banco de dados temporal** (InfluxDB + Grafana) para histórico de eventos e análise de tendências.
- **Integração CEMADEN/Defesa Civil** via webhook — JSON compatível com protocolo CAP (Common Alerting Protocol).

---

## Instalação e Execução

### Requisitos
- Python 3.10+
- pip

### Instalação
```bash
git clone <url_do_repositorio>
cd Americas-TechGuard-Simulacao
pip install -r requirements.txt
```

### Executar o simulador (gera JSONs de evidência)
```bash
python src/simulador_techguard.py
# Outputs salvos em outputs/payloads_<cenario>_<timestamp>.json
```

### Executar o Dashboard da Defesa Civil
```bash
streamlit run src/app_defesa_civil.py
# Abrir http://localhost:8501 no navegador
```

### Executar os testes automatizados
```bash
pytest src/test_risk_engine.py -v
# Esperado: 11 passed in ~0.05s
```

---

## Dependências e Versões

| Dependência | Versão mínima | Uso |
|---|---|---|
| Python | 3.10+ | Runtime da solução |
| streamlit | 1.35.0+ | Dashboard CODC |
| pytest | 8.0.0+ | Suite de testes |
| json, math, time, datetime, os, random | stdlib | Motor de risco e simulador |

---

## Licença e Uso Acadêmico

Este repositório é de uso exclusivamente acadêmico, desenvolvido como entrega da atividade de projeto do Período 8 — SENAI/SC.  
Os artigos referenciados pertencem aos seus respectivos autores e editoras, conforme citações acima.  
O código desta PoC é de autoria própria e pode ser reutilizado com atribuição.
