import os
import time
import requests
from datetime import datetime

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

def buscar_estatisticas_partida(fixture_id):
    headers = {"x-apisports-key": API_KEY}
    url = f"https://v3.football.api-sports.io/fixtures/statistics"
    params = {"fixture": fixture_id}
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json().get("response", [])
    except Exception as e:
        print(f"Erro ao buscar estatísticas: {e}")
    return []

def extrair_estatistica(stats_team, nome_estatistica):
    for stat in stats_team:
        if stat.get("type") == nome_estatistica:
            valor = stat.get("value")
            return int(valor) if valor is not None else 0
    return 0

def main():
    print("🤖 Robô Avançado de Análise Estatística (Pressão Real) iniciado!")
    enviar_telegram("🚀 *Robô com Filtro Estatístico Ativo!* Analisando chutes, pressão e volume ofensivo em tempo real.")

    jogos_notificados = set()

    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Varrendo partidas e estatísticas ao vivo...")
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

                if goals_home is None: goals_home = 0
                if goals_away is None: goals_away = 0

                # CRITÉRIO DE TEMPO: A partir dos 10 min do 1ºT até o fim do jogo (evitando intervalos mortos)
                if elapsed and ((10 <= elapsed <= 43) or (50 <= elapsed <= 88)):
                    
                    chave = f"{fixture_id}-{elapsed // 15}" # Evita spam na mesma janela de 15 min
                    if chave in jogos_notificados:
                        continue

                    # Busca as estatísticas reais da API para validar a pressão
                    estatisticas = buscar_estatisticas_partida(fixture_id)
                    
                    if len(estatisticas) == 2:
                        stats_home = estatisticas[0]['statistics']
                        stats_away = estatisticas[1]['statistics']

                        # Coleta métricas de pressão (Chutes no alvo e Chutes Totais)
                        shots_on_home = extrair_estatistica(stats_home, "Shots on Goal")
                        shots_on_away = extrair_estatistica(stats_away, "Shots on Goal")
                        total_shots_home = extrair_estatistica(stats_home, "Total Shots")
                        total_shots_away = extrair_estatistica(stats_away, "Total Shots")
                        
                        total_chutes_alvo = shots_on_home + shots_on_away
                        total_chutes = total_shots_home + total_shots_away

                        # FILTRO DE ALTA PRESSÃO REAL:
                        # Só dispara se o jogo realmente tiver volume ofensivo (ex: mínimo de chutes ou pressão combinada)
                        # Você pode ajustar esses números conforme sua exigência
                        if total_chutes >= 8 or total_chutes_alvo >= 3:
                            
                            etapa = "1º Tempo" if elapsed <= 45 else "2º Tempo"

                            mensagem = (
                                f"🚨 *OPORTUNIDADE DETECTADA (COM ESTATÍSTICAS)* 🚨\n\n"
                                f"🏆 *Liga:* {league}\n"
                                f"⚽ *Partida:* {home} {goals_home} x {goals_away} {away}\n"
                                f"⏱️ *Momento:* {elapsed} min ({etapa})\n\n"
                                f"🎯 *Mercado Sugerido:* Mais de Gols (Live)\n"
                                f"⭐ *Confiança:* Alta\n"
                                f"💡 *Análise Estatística Real:*\n"
                                f"• Chutes no Alvo: {shots_on_home} x {shots_on_away}\n"
                                f"• Finalizações Totais: {total_chutes}\n"
                                f"🔥 Pressão forte detectada em campo!\n\n"
                                f"⏱️ *Gerado em {datetime.now().strftime('%H:%M:%S')}*"
                            )
                            
                            enviar_telegram(mensagem)
                            jogos_notificados.add(chave)
                            time.sleep(2)

            except Exception as e:
                continue

        # Aguarda 3 minutos para a próxima varredura geral
        time.sleep(180)

if __name__ == "__main__":
    main()
