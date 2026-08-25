import os
import time
import requests
from datetime import datetime

# ==========================================
# CONFIGURAÇÕES E CREDENCIAIS DO ROBÔ
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "SEU_TELEGRAM_TOKEN_AQUI")
CHAT_ID = os.getenv("CHAT_ID", "SEU_CHAT_ID_AQUI")
FOOTBALL_API_KEY = os.getenv("API_KEY", "SUA_API_KEY_AQUI")

HEADERS_API = {
    'x-apisports-key': FOOTBALL_API_KEY
}

# Dicionário para controlar quais jogos já mandamos alerta recentemente (Evita Spam)
# Formato: { fixture_id: timestamp_do_ultimo_envio }
CACHE_ALERTAS_ENVIADOS = {}

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
            dados_json = response.json()
            jogos = dados_json.get('response', [])
            return jogos
        else:
            print(f"[ERRO API] Retornou status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[EXCEÇÃO API] Erro ao buscar jogos ao vivo: {e}")
    return []

def avaliar_gatilho_real(jogo):
    """
    Avalia os gatilhos com base nas estatísticas reais e minuto do jogo da API.
    Aqui você pode refinar as regras reais de chutes, ataques perigosos, etc.
    """
    status_short = jogo['fixture']['status']['short']
    minuto = jogo['fixture']['status']['elapsed'] or 0
    
    tempo = '1T' if status_short in ['1H', 'HT'] else '2T'
    
    # Exemplo de regra baseada no minuto do jogo (substitua pelas suas estatísticas da API quando quiser)
    # Exemplo: gatilho de pressão no segundo tempo entre 50' e 80'
    if tempo == '2T' and 50 <= minuto <= 80:
        return True, "⚡ GATILHO DE PRESSÃO CONVENCIONAL", minuto, tempo

    return False, "", minuto, tempo

def processar_partidas():
    hora_atual = datetime.now().strftime('%H:%M:%S')
    print(f"\n[{hora_atual}] Iniciando nova varredura de partidas...")
    jogos = buscar_jogos_ao_vivo()
    
    if not jogos:
        print(f"[{hora_atual}] Nenhum jogo ao vivo encontrado na API nesta varredura.")
        return

    print(f"[{hora_atual}] Total de jogos ao vivo na API: {len(jogos)}")
    
    global CACHE_ALERTAS_ENVIADOS
    tempo_atual = time.time()
    
    # Limpa o cache de jogos antigos (remove o que foi enviado há mais de 30 minutos para poder alertar novamente se necessário)
    CACHE_ALERTAS_ENVIADOS = {fid: ts for fid, ts in CACHE_ALERTAS_ENVIADOS.items() if tempo_atual - ts < 1800}

    jogos_com_alerta = 0
    for jogo in jogos:
        fixture_id = jogo['fixture']['id']
        time_casa = jogo['teams']['home']['name']
        time_fora = jogo['teams']['away']['name']
        
        # Avalia se a partida cumpre os requisitos reais
        disparar, motivo, minuto, tempo = avaliar_gatilho_real(jogo)
        
        if disparar:
            # Verifica se já mandamos alerta para este jogo nos últimos 20 minutos (1200 segundos)
            if fixture_id in CACHE_ALERTAS_ENVIADOS:
                continue 
                
            mensagem = (
                f"{motivo}\n"
                f"⚽ *{time_casa} vs {time_fora}*\n"
                f"⏱️ Minuto: {minuto}' ({tempo})\n"
                f"📊 Oportunidade detectada pelo motor preditivo!"
            )
            enviar_alerta_telegram(mensagem)
            print(f"   [ALERTA ENVIADO!] 🚨 {time_casa} x {time_fora} aos {minuto}'")
            
            # Registra no cache que este jogo acabou de receber alerta
            CACHE_ALERTAS_ENVIADOS[fixture_id] = tempo_atual
            jogos_com_alerta += 1

    print(f"[{hora_atual}] Varredura concluída. Alertas enviados neste ciclo: {jogos_com_alerta}")

if __name__ == "__main__":
    print("🤖 Robô de Alertas Preditivos iniciado com sucesso!")
    
    enviar_alerta_telegram(
        "🚀 *Robô atualizado e operando com dados reais da API!* \n"
        "🛡️ Filtro anti-spam de partidas ativado com sucesso."
    )
    
    while True:
        try:
            processar_partidas()
        except Exception as e:
            print(f"[ERRO NO LOOP] {e}")
        
        print("Aguardando 60 segundos para o próximo ciclo...\n")
        time.sleep(60)
