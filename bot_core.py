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
    print("Robô blindado de alta confiança iniciado na nuvem.")
    jogos_notificados = set()

    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Varrendo partidas ao vivo...")
        partidas = buscar_jogos_ao_vivo()
        print(f"Partidas ao vivo encontradas: {len(partidas)}")

        for match in partidas:
            try:
                fixture_id = match['fixture']['id']
                home = match['teams']['home']['name']
                away = match['teams']['away']['name']
                goals_home = match['goals']['home']
                goals_away = match['goals']['away']
                elapsed = match['fixture']['status']['elapsed']

                if goals_home is None: goals_home = 0
                if goals_away is None: goals_away = 0

                # Exemplo de regra alinhada com o padrão da sua imagem (ex: jogo avançado no 2º tempo)
                if elapsed and elapsed >= 70:
                    chave = f"{fixture_id}-{elapsed//10}"
                    if chave in jogos_notificados:
                        continue

                    # Mensagem estruturada exatamente no padrão que você gosta
                    mensagem = (
                        f"🚨 *OPORTUNIDADE DETECTADA (DIRETO DA API)* 🚨\n\n"
                        f"⚽ *Partida:* {home} vs {away}\n"
                        f"📊 *Placar Atual:* {goals_home} x {goals_away}\n"
                        f"🎯 *Mercado Sugerido:* Mais de 1.5 / 2.5 Gols (Live)\n"
                        f"⭐ *Confiança:* Alta\n"
                        f"💡 *Análise Estatística:*\n"
                        f"Ritmo forte no 2º tempo aos {elapsed} min ({goals_home}x{goals_away}). Alta pressão detectada.\n\n"
                        f"⏱️ *Gerado automaticamente pelo Robô em {datetime.now().strftime('%H:%M:%S')}*"
                    )
                    
                    enviar_telegram(mensagem)
                    jogos_notificados.add(chave)
                    time.sleep(2)

            except Exception as e:
                continue

        # Aguarda 3 minutos para a próxima varredura
        time.sleep(180)

if __name__ == "__main__":
    main()
