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

HEADERS_API = {
    'x-apisports-key': FOOTBALL_API_KEY
}

def enviar_alerta_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensagem, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[ERRO TELEGRAM]: {e}")

def buscar_jogos_ao_vivo():
    url = "https://v3.football.api-sports.io/fixtures"
    params = {"live": "all"}
    try:
        print(faz_requisicao := f"[DEBUG] Consultando URL: {url} com chave ativa...")
        response = requests.get(url, headers=HEADERS_API, params=params, timeout=15)
        
        print(f"[DEBUG] Status Code da API: {response.status_code}")
        dados_json = response.json()
        
        # Mostra no log da Railway o que a API está respondendo de verdade
        print(f"[DEBUG] Resposta crua da API (primeiros 300 caracteres): {str(dados_json)[:300]}")
        
        if response.status_code == 200:
            jogos = dados_json.get('response', [])
            print(f"[API] Jogos encontrados no array 'response': {len(jogos)}")
            return jogos
        else:
            print(f"[ERRO API] Retornou status diferente de 200: {dados_json}")
            
    except Exception as e:
        print(f"[EXCEÇÃO API] Erro crítico na requisição: {e}")
    return []

def processar_partidas():
    hora_atual = datetime.now().strftime('%H:%M:%S')
    print(f"\n[{hora_atual}] Iniciando varredura...")
    jogos = buscar_jogos_ao_vivo()
    
    if not jogos:
        print(f"[{hora_atual}] ⚠️ ATENÇÃO: A API não retornou nenhum jogo ao vivo nesta rodada.")
        return

    for jogo in jogos:
        casa = jogo['teams']['home']['name']
        fora = jogo['teams']['away']['name']
        minuto = jogo['fixture']['status']['elapsed']
        print(f"   -> Jogo detectado: {casa} x {fora} aos {minuto}'")

if __name__ == "__main__":
    print("🤖 Robô de Diagnóstico API iniciado!")
    enviar_alerta_telegram("🛠️ *Robô em modo diagnóstico* para verificar o retorno da API-Football.")
    
    while True:
        try:
            processar_partidas()
        except Exception as e:
            print(f"[ERRO LOOP] {e}")
        time.sleep(60)
