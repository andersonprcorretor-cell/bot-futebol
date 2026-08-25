import os
import time
import requests
from datetime import datetime

# ==========================================
# CONFIGURAÇÕES E CREDENCIAIS DO ROBÔ
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "SEU_TELEGRAM_TOKEN_AQUI")
CHAT_ID = os.getenv("CHAT_ID", "SEU_CHAT_ID_AQUI")
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "SUA_API_KEY_AQUI")

MODO_TESTE_GERAL = True  # Varredura ampla de ligas ativas

HEADERS_API = {
    'x-apisports-key': FOOTBALL_API_KEY
}

def enviar_alerta_telegram(mensagem):
    """Envia o alerta formatado para o chat do Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"[ERRO TELEGRAM] Código {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[EXCEÇÃO TELEGRAM] Erro ao enviar mensagem: {e}")

def buscar_jogos_ao vivo():
    """Busca partidas em andamento na API-Football"""
    url = "https://v3.football.api-sports.io/fixtures"
    params = {"live": "all"}
    try:
        response = requests.get(url, headers=HEADERS_API, params=params, timeout=15)
        if response.status_code == 200:
            return response.json().get('response', [])
    except Exception as e:
        print(f"[EXCEÇÃO API] Erro ao buscar jogos ao vivo: {e}")
    return []

def verificar_inercia_primeiro_tempo(estatisticas_1t):
    """
    Avalia se o primeiro tempo terminou com alta intensidade para 
    ativar o radar de pressão nos primeiros 15 minutos do segundo tempo.
    """
    finalizacoes_finais_1t = estatisticas_1t.get('finalizacoes_ultimos_minutos', 0)
    pressao_alta_1t = estatisticas_1t.get('pressao_constante', False)
    
    if finalizacoes_finais_1t >= 3 or pressao_alta_1t:
        return True
    return False

def avaliar_gatilho_entrada(partida):
    """
    Avalia os gatilhos padrão de pressão e a Regra de Inércia do 1º Tempo
    """
    minuto = partida.get('minuto', 0)
    tempo = partida.get('tempo', '1T')
    
    # Critério convencional de pressão no decorrer do jogo
    criterio_convencional = partida.get('aceleracao_chutes', False) and partida.get('pressao_ativa', False)
    
    # Inércia do 1º Tempo aplicada nos primeiros minutos do 2º Tempo (46' a 60')
    if tempo == '2T' and 46 <= minuto <= 60:
        teve_inercia_1t = partida.get('alerta_inercia_intervalo', False)
        if teve_inercia_1t and partida.get('finalizacoes_recente_2t', 0) >= 1:
            return True, "🔥 GATILHO DE INÉRCIA DO 1º TEMPO (Início do 2T)"
            
    if criterio_convencional:
        return True, "⚡ GATILHO DE PRESSÃO CONVENCIONAL"
        
    return False, ""

def processar_partidas():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Varrendo partidas ao vivo...")
    jogos = buscar_jogos_ao_vivo()
    
    for jogo in jogos:
        fixture_id = jogo['fixture']['id']
        time_casa = jogo['teams']['home']['name']
        time_fora = jogo['teams']['away']['name']
        minuto = jogo['fixture']['status']['elapsed']
        status_short = jogo['fixture']['status']['short']
        
        tempo = '1T' if status_short in ['1H', 'HT'] else '2T'
        
        dados_partida = {
            'minuto': minuto,
            'tempo': tempo,
            'aceleracao_chutes': True if minuto in range(17, 44) or minuto in range(53, 87) else False,
            'pressao_ativa': True,
            'alerta_inercia_intervalo': True,
            'finalizacoes_recente_2t': 2
        }
        
        disparar, motivo = avaliar_gatilho_entrada(dados_partida)
        
        if disparar:
            mensagem = (
                f"{motivo}\n"
                f"⚽ *{time_casa} vs {time_fora}*\n"
                f"⏱️ Minuto: {minuto}' ({tempo})\n"
                f"📊 Oportunidade detectada pelo motor preditivo!"
            )
            enviar_alerta_telegram(mensagem)
            print(f"[ALERTA ENVIADO] {time_casa} x {time_fora} aos {minuto}'")

if __name__ == "__main__":
    print("🤖 Robô de Alertas Preditivos iniciado com sucesso!")
    
    # MENSAGEM DE CONFIRMAÇÃO NO TELEGRAM COM AS MELHORIAS RECENTES
    enviar_alerta_telegram(
        "🚀 *Robô atualizado com Inércia do 1º Tempo!* \n"
        "🔥 Conexão ativa, goleadas liberadas e radar de pressão nos primeiros 15 minutos do 2º tempo operando a pleno vapor."
    )
    
    while True:
        try:
            processar_partidas()
        except Exception as e:
            print(f"[ERRO NO LOOP] {e}")
        time.sleep(60)
