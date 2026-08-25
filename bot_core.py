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

MODO_TESTE_GERAL = True

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

def buscar_jogos_ao_vivo():
    """Busca partidas em andamento na API-Football"""
    url = "https://v3.football.api-sports.io/fixtures"
    params = {"live": "all"}
    try:
        response = requests.get(url, headers=HEADERS_API, params=params, timeout=15)
        if response.status_code == 200:
            dados = response.json().get('response', [])
            print(f"[API] Sucesso! Encontrados {len(dados)} jogos ao vivo neste momento.")
            return dados
    except Exception as e:
        print(f"[EXCEÇÃO API] Erro ao buscar jogos ao vivo: {e}")
    return []

def avaliar_gatilho_entrada(partida):
    """Avalia os gatilhos padrão de pressão e a Regra de Inércia do 1º Tempo"""
    minuto = partida.get('minuto', 0)
    tempo = partida.get('tempo', '1T')
    
    criterio_convencional = partida.get('aceleracao_chutes', False) and partida.get('pressao_ativa', False)
    
    if tempo == '2T' and 46 <= minuto <= 60:
        teve_inercia_1t = partida.get('alerta_inercia_intervalo', False)
        if teve_inercia_1t and partida.get('finalizacoes_recente_2t', 0) >= 1:
            return True, "🔥 GATILHO DE INÉRCIA DO 1º TEMPO (Início do 2T)"
            
    if criterio_convencional:
        return True, "⚡ GATILHO DE PRESSÃO CONVENCIONAL"
        
    return False, ""

def processar_partidas():
    hora_atual = datetime.now().strftime('%H:%M:%S')
    print(f"\n[{hora_atual}] Iniciando nova varredura de partidas...")
    jogos = buscar_jogos_ao_vivo()
    
    if not jogos:
        print(f"[{hora_atual}] Nenhum jogo ao vivo encontrado na API nesta varredura.")
        return

    # Log para mostrar até 5 jogos que estão sendo analisados (para não floodar demais o console)
    print(f"[{hora_atual}] Analisando dados... Exemplo dos primeiros jogos da lista:")
    for i, jogo in enumerate(jogos[:5]): 
        liga = jogo['league']['name']
        casa = jogo['teams']['home']['name']
        fora = jogo['teams']['away']['name']
        minuto = jogo['fixture']['status']['elapsed']
        print(f"   -> {liga}: {casa} x {fora} ({minuto}')")

    if len(jogos) > 5:
        print(f"   -> ... e mais {len(jogos) - 5} jogos sendo processados nos bastidores.")
    
    jogos_com_alerta = 0
    for jogo in jogos:
        time_casa = jogo['teams']['home']['name']
        time_fora = jogo['teams']['away']['name']
        minuto = jogo['fixture']['status']['elapsed']
        status_short = jogo['fixture']['status']['short']
        
        tempo = '1T' if status_short in ['1H', 'HT'] else '2T'
        
        # Simulação dos dados (Lembre-se que aqui entram os dados REAIS da sua lógica de stats)
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
            print(f"   [ALERTA DISPARADO!] 🚨 {time_casa} x {time_fora} aos {minuto}' - Motivo: {motivo}")
            jogos_com_alerta += 1

    print(f"[{hora_atual}] Varredura concluída. Alertas enviados neste ciclo: {jogos_com_alerta}")

if __name__ == "__main__":
    print("🤖 Robô de Alertas Preditivos iniciado com sucesso!")
    
    enviar_alerta_telegram(
        "🚀 *Robô atualizado com Inércia do 1º Tempo (Modo Verbose)!* \n"
        "🔥 Conexão ativa. Agora você pode acompanhar a varredura das ligas nos logs da Railway."
    )
    
    while True:
        try:
            processar_partidas()
        except Exception as e:
            print(f"[ERRO CRÍTICO NO LOOP PRINCIPAL] {e}")
        
        print("Aguardando 60 segundos para o próximo ciclo...\n")
        time.sleep(60)
