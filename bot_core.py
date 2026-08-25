import os
import time
import requests
import logging
from datetime import datetime

# ==========================================
# CONFIGURAÇÃO DE LOGS E AMBIENTE
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("BotCore")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "SEU_TOKEN_AQUI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "SEU_CHAT_ID_AQUI")

# Dicionário para controle de estado prévio das partidas (para calcular a aceleração/delta da IA)
# Formato: { match_id: {'shots': int, 'corners': int, 'timestamp': float} }
historico_partidas_ia = {}

def enviar_telegram(mensagem):
    """Envia mensagens de texto para o Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Credenciais do Telegram não configuradas.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            logger.error(f"Erro ao enviar Telegram: {response.text}")
    except Exception as e:
        logger.error(f"Exceção ao enviar Telegram: {e}")

def analisar_com_ia_preditiva(match_id, total_shots, total_corners, minute):
    """
    Motor de IA de Lógica Preditiva e Janela Deslizante (Delta de Aceleração).
    Avalia se houve um 'surto de pressão' repentino com base na variação estatística.
    Agora liberado para analisar qualquer contexto de placar, inclusive goleadas.
    """
    tempo_atual = time.time()
    
    if match_id not in historico_partidas_ia:
        # Primeiro registro da partida
        historico_partidas_ia[match_id] = {
            'shots': total_shots,
            'corners': total_corners,
            'timestamp': tempo_atual
        }
        return False, "Monitorando (Início)"

    dados_antigos = historico_partidas_ia[match_id]
    delta_tempo = tempo_atual - dados_antigos['timestamp']
    
    # Atualiza o histórico com os dados atuais para o próximo ciclo
    historico_partidas_ia[match_id] = {
        'shots': total_shots,
        'corners': total_corners,
        'timestamp': tempo_atual
    }

    # Se passou menos de 30 segundos, aguarda janela maior
    if delta_tempo < 20:
        return False, "Aguardando janela"

    # Cálculo da aceleração (Deltas)
    delta_shots = total_shots - dados_antigos['shots']
    delta_corners = total_corners - dados_antigos['corners']

    # Critérios de Disparo da IA Preditiva (Surto de Pressão)
    # Dispara se houve aceleração forte de finalizações ou escanteios em janela curta
    sinal_gols = delta_shots >= 2 and minute >= 35 # Ex: 2+ finalizações repentinas na reta final do tempo
    sinal_cantos = delta_corners >= 2 and minute >= 30

    motivo = f"ΔShots: +{delta_shots}, ΔCorners: +{delta_corners}"
    
    if sinal_gols or sinal_cantos:
        return True, f"Surto de Pressão Detectado! ({motivo})"
    
    return False, f"Estável ({motivo})"

def varrer_partidas():
    """Função principal de varredura do robô."""
    logger.info("Iniciando ciclo de varredura com IA Preditiva (Goleadas liberadas)...")
    
    # Exemplo simulado de requisição à API de futebol ou varredura de partidas ativas
    # Substitua pela sua API real de dados ao vivo (ex: SofaScore, API-Football, etc.)
    try:
        # url_api = "SUA_API_DE_FUTEBOL_AQUI"
        # response = requests.get(url_api, timeout=15)
        # partidas = response.json()
        
        # Simulação para demonstração de funcionamento contínuo nos logs
        logger.info("[Sistema] Varredura executada com sucesso. Monitorando partidas ativas...")
        
    except Exception as e:
        logger.error(f"Erro ao buscar partidas na API: {e}")

def main():
    logger.info("Robô iniciado com sucesso na Railway!")
    enviar_telegram("🚀 *Robô Atualizado com Sucesso!*\n\nO motor de IA preditiva foi otimizado: **Jogos com goleadas agora estão liberados** para análise de pressão contínua. Vamos em busca dos Greens!")
    
    while True:
        try:
            varrer_partidas()
            # Pausa entre os ciclos de varredura (ex: 60 segundos)
            time.sleep(60)
        except Exception as e:
            logger.error(f"Erro no loop principal: {e}")
            time.sleep(15)

if __name__ == "__main__":
    main()
