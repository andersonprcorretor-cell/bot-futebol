import os
import time
import requests
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")

BASE_URL = "https://v3.football.api-sports.io/fixtures"

# IDs das principais ligas de elite
LIGAS_PERMITIDAS = {
    71, 72,    # Brasileirão Série A e B
    39, 40,    # Premier League e Championship (Inglaterra)
    140, 141,  # La Liga e La Liga 2 (Espanha)
    135,       # Serie A (Itália)
    78,        # Bundesliga (Alemanha)
    61,        # Ligue 1 (França)
    2,         # UEFA Champions League
    3,         # UEFA Europa League
    13,        # Copa Libertadores
    11         # Copa Sul-Americana
}

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
    print("🤖 Robô Elite (Gols + Escanteios) iniciado!")
    
    jogos_notificados_gols = set()
    jogos_notificados_cantos = set()

    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Varrendo partidas e analisando Gols & Escanteios...")
        partidas = buscar_jogos_ao_vivo()

        for match in partidas:
            try:
                league_id = match['league']['id']
                
                # BLOQUEIO DE LIGAS DESCONHECIDAS
                if league_id not in LIGAS_PERMITIDAS:
                    continue

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
                    gols_totais = goals_home + goals_away
                    diferenca_gols = abs(goals_home - goals_away)

                    # 🛑 TRAVA 1: Anti-Goleada (Ignora jogos resolvidos na reta final para gols)
                    jogo_goleada = (diferenca_gols >= 3 and elapsed >= 70) or (gols_totais >= 4)

                    chave_gol = f"{fixture_id}-{elapsed // 20}"
                    chave_canto = f"canto-{fixture_id}"

                    # Só busca estatísticas se o jogo estiver ativo e interessante
                    estatisticas = buscar_estatisticas_partida(fixture_id)
                    
                    if len(estatisticas) == 2:
                        stats_home = estatisticas[0]['statistics']
                        stats_away = estatisticas[1]['statistics']

                        shots_on_home = extrair_estatistica(stats_home, "Shots on Goal")
                        shots_on_away = extrair_estatistica(stats_away, "Shots on Goal")
                        total_shots_home = extrair_estatistica(stats_home, "Total Shots")
                        total_shots_away = extrair_estatistica(stats_away, "Total Shots")
                        corners_home = extrair_estatistica(stats_home, "Corner Kicks")
                        corners_away = extrair_estatistica(stats_away, "Corner Kicks")
                        pos_home = extrair_estatistica(stats_home, "Ball Possession")
                        pos_away = extrair_estatistica(stats_away, "Ball Possession")
                        
                        total_chutes_alvo = shots_on_home + shots_on_away
                        total_chutes = total_shots_home + total_shots_away
                        total_escanteios = corners_home + corners_away

                        # ==========================================
                        # 1. ANÁLISE DE GOLS (Com Travas Blindadas)
                        # ==========================================
                        if not jogo_goleada and chave_gol not in jogos_notificados_gols:
                            e_primeiro_tempo = (18 <= elapsed <= 42) and (total_chutes_alvo >= 2 or total_chutes >= 5)
                            e_segundo_tempo = (55 <= elapsed <= 85) and (total_chutes_alvo >= 4 or total_chutes >= 12)

                            if e_primeiro_tempo or e_segundo_tempo:
                                etapa = "1º Tempo" if elapsed <= 45 else "2º Tempo"
                                xg_home = round((shots_on_home * 0.35) + (total_shots_home * 0.08) + (corners_home * 0.03), 2)
                                xg_away = round((shots_on_away * 0.35) + (total_shots_away * 0.08) + (corners_away * 0.03), 2)

                                if gols_totais == 0:
                                    mercado_sugerido = "Mais de 0.5 / 1.5 Gols (Live)"
                                elif gols_totais == 1:
                                    mercado_sugerido = "Mais de 1.5 / 2.5 Gols (Live)"
                                else:
                                    mercado_sugerido = f"Mais de {gols_totais + 1}.5 Gols (Live)"

                                mensagem_gols = (
                                    f"🚨 *OPORTUNIDADE DE GOLS (ALTA PROBABILIDADE)* 🚨\n\n"
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
                                    f"• xG Estimado: {xg_home} x {xg_away}\n"
                                    f"🔥 Pressão extrema e sufocante detectada!\n\n"
                                    f"🛡️ *Canal VIP - Gestão e Disciplina Sempre.*"
                                )
                                
                                enviar_telegram(mensagem_gols)
                                jogos_notificados_gols.add(chave_gol)
                                time.sleep(2)

                        # ==========================================
                        # 2. ANÁLISE EXCLUSIVA DE ESCANTEIOS (Cantos Asióticos / Pressão Lateral)
                        # ==========================================
                        if chave_canto not in jogos_notificados_cantos:
                            # Gatilho de escanteios no 2º tempo (entre 65 e 85 min com jogo aberto e volume alto)
                            if 65 <= elapsed <= 85 and total_escanteios >= 8:
                                mercado_cantos = f"Mais de {total_escanteios + 2.5} Cantos (Asiáticos Live)"
                                
                                mensagem_cantos = (
                                    f"🚩 *OPORTUNIDADE DE ESCANTEIOS (PRESSÃO NAS PONTAS)* 🚩\n\n"
                                    f"🏆 *Liga:* {league}\n"
                                    f"⚽ *Partida:* {home} {goals_home} x {goals_away} {away}\n"
                                    f"⏱️ *Momento:* {elapsed} min (2º Tempo)\n\n"
                                    f"🎯 *Mercado Sugerido:* {mercado_cantos}\n"
                                    f"⭐ *Confiança:* Alta (Volume Intenso)\n"
                                    f"💡 *Raio-X de Cantos e Jogo:*\n"
                                    f"• Escanteios Atuais: {corners_home} x {corners_away} (Total: {total_escanteios})\n"
                                    f"• Finalizações Totais: {total_chutes}\n"
                                    f"• Posse de Bola: {pos_home}% x {pos_away}%\n"
                                    f"🔥 Jogo com forte tendência de cruzamentos e cantos no fim!\n\n"
                                    f"🛡️ *Canal VIP - Gestão e Disciplina Sempre.*"
                                )
                                
                                enviar_telegram(mensagem_cantos)
                                jogos_notificados_cantos.add(chave_canto)
                                time.sleep(2)

            except Exception as e:
                continue

        time.sleep(180)

if __name__ == "__main__":
    main()
