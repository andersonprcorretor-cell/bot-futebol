import os
import time
import requests
from datetime import datetime

# Puxa as chaves de segurança direto do Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")

# URL oficial da API-Sports (Futebol)
BASE_URL = "https://v3.football.api-sports.io/fixtures"

def enviar_telegram(mensagem):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Erro: Token ou Chat ID do Telegram ausentes.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"Erro Telegram: {response.text}")
    except Exception as e:
        print(f"Erro de conexão com o Telegram: {e}")

def buscar_jogos_ao_vivo():
    headers = {
        "x-apisports-key": API_KEY
    }
    params = {
        "live": "all"
    }
    try:
        response = requests.get(BASE_URL, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            return data.get("response", [])
        else:
            print(f"Erro na API-Sports: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Erro ao conectar na API-Sports: {e}")
        return []

def main():
    print("🤖 Robô de Apostas ao Vivo iniciado na nuvem com sucesso!")
    enviar_telegram("🚀 *Robô Online!* Monitoramento de partidas ao vivo (incluindo ligas principais) ativado.")

    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Buscando partidas ao vivo na API...")
        partidas = buscar_jogos_ao_vivo()
        print(f"Partidas ao vivo encontradas: {len(partidas)}")

        for match in partidas:
            try:
                home = match['teams']['home']['name']
                away = match['teams']['away']['name']
                goals_home = match['goals']['home']
                goals_away = match['goals']['away']
                elapsed = match['fixture']['status']['elapsed']
                league = match['league']['name']

                # Exemplo de gatilho de oportunidade (ex: jogo em andamento a partir de 15 min com pressão/placar)
                # Você pode ajustar esta regra conforme a sua estratégia de gols
                if elapsed and elapsed >= 15:
                    # Dispara alerta de oportunidade para o Telegram
                    mensagem = (
                        f"🔥 *Oportunidade Live Detectada!*\n\n"
                        f"🏆 *Liga:* {league}\n"
                        f"⚽ *Confronto:* {home} {goals_home} x {goals_away} {away}\n"
                        f"⏱️ *Tempo:* {elapsed} minutos\n\n"
                        f"📊 *Status:* Jogo aquecido e dentro dos critérios de pressão!"
                    )
                    # Envia o alerta (com trava simples para não floodar se quiser, ou direto)
                    # Vamos enviar para testarmos o fluxo completo:
                    enviar_telegram(mensagem)
                    
                    # Pausa breve entre os disparos para respeitar limites
                    time.sleep(2)
            except Exception as e:
                continue

        # Aguarda 3 minutos antes da próxima varredura para economizar requisições da API
        print("Aguardando 3 minutos para a próxima varredura...")
        time.sleep(180)

if __name__ == "__main__":
    main()
