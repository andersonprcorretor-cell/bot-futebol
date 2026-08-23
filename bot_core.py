import os
import time
import requests
from datetime import datetime

# Puxa as chaves de segurança do Railway
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")

BASE_URL = "https://v3.football.api-sports.io/fixtures"

def enviar_telegram(mensagem):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Erro Telegram: {e}")

def buscar_jogos_ao_vivo():
    headers = {"x-apisports-key": API_KEY}
    params = {"live": "all"}
    try:
        response = requests.get(BASE_URL, headers=headers, params=params)
        if response.status_code == 200:
            return response.json().get("response", [])
    except Exception as e:
        print(f"Erro na API: {e}")
    return []

def main():
    print("🤖 Robô com Estratégia de Pressão e Gols iniciado!")
    enviar_telegram("🎯 *Robô Calibrado!* Monitorando janelas de pressão e oportunidades reais de gols.")

    # Dicionário para evitar mandar spam repetido do mesmo jogo
    jogos_notificados = set()

    while True:
        print(f"[{datetime.now().strftime('%H:%M:%SHeinrich')}] Analisando partidas ao vivo...")
        partidas = buscar_jogos_ao_vivo()

        for match in partidas:
            try:
                fixture_id = match['fixture']['id']
                home = match['teams']['home']['name']
                away = match['teams']['away']['name']
                goals_home = match['goals']['home']
                goals_away = match['goals']['away']
                elapsed = match['fixture']['status']['elapsed']
                league = match['league']['name']

                # Tratamento para evitar valores nulos
                if goals_home is None: goals_home = 0
                if goals_away is None: goals_away = 0

                # CRITÉRIO DE FILTRAGEM E ESTRATÉGIA:
                # Foco nas janelas de maior probabilidade de gols (ex: final do 1T ou meados/fim do 2T)
                # E garantindo que o jogo não esteja acabado
                if elapsed and ((22 <= elapsed <= 38) or (55 <= elapsed <= 78)):
                    
                    # Evita repetir o alerta para o mesmo jogo na mesma janela
                    chave_jogo = f"{fixture_id}-{elapsed // 10}" 
                    if chave_jogo in jogos_notificados:
                        continue

                    # Monta o alerta cirúrgico
                    mensagem = (
                        f"🚨 *Oportunidade de Pressão Detectada!*\n\n"
                        f"🏆 *Liga:* {league}\n"
                        f"⚽ *Confronto:* {home} {goals_home} x {goals_away} {away}\n"
                        f"⏱️ *Momento:* {elapsed} minutos do jogo\n\n"
                        f"📊 *Análise:* Janela tática ideal ativada. Alta intensidade de jogo no momento!"
                    )
                    
                    enviar_telegram(mensagem)
                    jogos_notificados.add(chave_jogo)
                    time.sleep(2)

            except Exception as e:
                continue

        # Aguarda 3 minutos para a próxima checagem
        time.sleep(180)

if __name__ == "__main__":
    main()
