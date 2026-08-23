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
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
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
            if valor is not None:
                if isinstance(valor, str) and "%" in valor:
                    return int(valor.replace("%", "").strip())
                return int(valor)
    return 0

def main():
    print("🤖 Robô Master Limpo (Foco Bet365 / Esportiva.bet) iniciado!")
    
    jogos_notificados = set()

    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Varrendo partidas e estatísticas avançadas...")
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

                if elapsed:
                    chave = f"{fixture_id}-{elapsed // 20}"
                    if chave in jogos_notificados:
                        continue

                    estatisticas = buscar_estatisticas_partida(fixture_id)
                    
                    if len(estatisticas) == 2:
                        stats_home = estatisticas[0]['statistics']
                        stats_away = estatisticas[1]['statistics']

                        shots_on_home = extrair_estatistica(stats_home, "Shots on Goal")
                        shots_on_away = extrair_estatistica(stats_away, "Shots on Goal")
                        total_shots_home = extrair_estatistica(stats_home, "Total Shots")
                        total_shots_away = extrair_estatistica(stats_home, "Total Shots")
                        corners_home = extrair_estatistica(stats_home, "Corner Kicks")
                        corners_away = extrair_estatistica(stats_away, "Corner Kicks")
                        pos_home = extrair_estatistica(stats_home, "Ball Possession")
                        pos_away = extrair_estatistica(stats_away, "Ball Possession")
                        
                        total_chutes_alvo = shots_on_home + shots_on_away
                        total_chutes = total_shots_home + total_shots_away

                        e_primeiro_tempo = (18 <= elapsed <= 42) and (total_chutes_alvo >= 2 or total_chutes >= 5)
                        e_segundo_tempo = (55 <= elapsed <= 85) and (total_chutes_alvo >= 4 or total_chutes >= 12)

                        if e_primeiro_tempo or e_segundo_tempo:
                            
                            etapa = "1º Tempo" if elapsed <= 45 else "2º Tempo"
                            
                            xg_home = round((shots_on_home * 0.35) + (total_shots_home * 0.08) + (corners_home * 0.03), 2)
                            xg_away = round((shots_on_away * 0.35) + (total_shots_away * 0.08) + (corners_away * 0.03), 2)

                            gols_totais = goals_home + goals_away
                            if gols_totais == 0:
                                mercado_sugerido = "Mais de 0.5 / 1.5 Gols (Live)"
                            elif gols_totais == 1:
                                mercado_sugerido = "Mais de 1.5 / 2.5 Gols (Live)"
                            else:
                                mercado_sugerido = f"Mais de {gols_totais + 1}.5 Gols (Live)"

                            mensagem = (
                                f"🚨 *OPORTUNIDADE DE ALTA PROBABILIDADE* 🚨\n\n"
                                f"🏆 *Liga:* {league}\n"
                                f"⚽ *Partida:* {home} {goals_home} x {goals_away} {away}\n"
                                f"⏱️ *Momento:* {elapsed} min ({etapa})\n\n"
                                f"🎯 *Mercado Sugerido:* {mercado_sugerido}\n"
                                f"⭐ *Confiança:* Alta\n"
                                f"💡 *Análise Estatística & Pressão:*\n"
                                f"• Chutes no Alvo: {shots_on_home} x {shots_on_away}\n"
                                f"• Finalizações Totais: {total_chutes}\n"
                                f"• Escanteios: {corners_home} x {corners_away}\n"
                                f"• Posse de Bola: {pos_home}% x {pos_away}%\n"
                                f"• xG Estimado (Volume): {xg_home} x {xg_away}\n"
                                f"🔥 Pressão extrema e sufocante detectada!\n\n"
                                f"⏱️ *Gerado em {datetime.now().strftime('%H:%M:%S')}*"
                            )
                            
                            enviar_telegram(mensagem)
                            jogos_notificados.add(chave)
                            time.sleep(2)

            except Exception as e:
                continue

        time.sleep(180)

if __name__ == "__main__":
    main()
