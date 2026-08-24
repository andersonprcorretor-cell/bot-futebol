import os
import time
import requests
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")

BASE_URL = "https://v3.football.api-sports.io/fixtures"

# IDs das principais ligas de elite e copas
LIGAS_PERMITIDAS = {
    71, 72,    # Brasileirão Série A e B
    39, 40,    # Premier League e Championship (Inglaterra)
    140, 141,  # La Liga e La Liga 2 (Espanha)
    135,       # Serie A (Itália)
    78,        # Bundesliga (Alemanha)
    81,        # DFB-Pokal (Copa da Alemanha)
    61,        # Ligue 1 (França)
    2,         # UEFA Champions League
    3,         # UEFA Europa League
    13,        # Copa Libertadores
    11         # Copa Sul-Americana
}

def enviar_telegram(mensagem, reply_to_message_id=None):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            return response.json().get("result", {}).get("message_id")
    except Exception as e:
        print(f"Erro Telegram: {e}")
    return None

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

def gerar_barra_pressao(valor_total):
    pontos = min(max(int(valor_total), 1), 10)
    preenchido = "█" * pontos
    vazio = "░" * (10 - pontos)
    porcentagem = pontos * 10
    return f"`{preenchido}{vazio}` ({porcentagem}%)"

def main():
    print("🤖 Robô Elite (Com Trava Anti-VAR) iniciado!")
    
    jogos_notificados_gols = set()
    jogos_notificados_cantos = set()
    sinais_ativos = {} 
    gols_pendentes_var = {} # Armazena gols detectados aguardando confirmação (Trava Anti-VAR)

    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Varrendo partidas e checando feedbacks/VAR...")
        partidas = buscar_jogos_ao_vivo()
        partidas_dict = {match['fixture']['id']: match for match in partidas}

        # ==========================================
        # 1. TRATAMENTO DA TRAVA ANTI-VAR PARA GOLS
        # ==========================================
        for fixture_id, pendente in list(gols_pendentes_var.items()):
            match_atual = partidas_dict.get(fixture_id)
            if not match_atual:
                del gols_pendentes_var[fixture_id]
                continue

            g_home_atual = match_atual['goals']['home'] if match_atual['goals']['home'] is not None else 0
            g_away_atual = match_atual['goals']['away'] if match_atual['goals']['away'] is not None else 0
            gols_totais_atual = g_home_atual + g_away_atual
            elapsed_atual = match_atual['fixture']['status']['elapsed'] or 0

            # Se após o ciclo de espera o placar continua maior, o gol é real (passou pelo VAR)
            if gols_totais_atual >= pendente['novo_total_gols']:
                tempo_para_agir = elapsed_atual - pendente['minuto_alerta']
                if tempo_para_agir < 0: 
                    tempo_para_agir = 1

                feedback_msg = (
                    f"🟢 *GOL CONFIRMADO depois do alerta!*\n"
                    f"⚽ {pendente['home']} {g_home_atual} x {g_away_atual} {pendente['away']} • Placar Atual\n"
                    f"⏱️ Alerta enviado aos {pendente['minuto_alerta']}'\n"
                    f"⚽ Gol saiu aos {elapsed_atual}'\n"
                    f"⏳ Você teve {tempo_para_agir} minutos para agir!"
                )
                enviar_telegram(feedback_msg, reply_to_message_id=pendente['message_id'])
                del gols_pendentes_var[fixture_id]
            else:
                # Se o placar caiu de novo, o VAR anulou! Descartamos sem mandar Green falso.
                print(f"⚠️ Gol anulado pelo VAR detectado na partida {pendente['home']} x {pendente['away']}. Alerta cancelado.")
                del gols_pendentes_var[fixture_id]

        # ==========================================
        # 2. CHECAGEM DE FEEDBACKS (Gols ativos e Escanteios)
        # ==========================================
        for fixture_id, info in list(sinais_ativos.items()):
            match_atual = partidas_dict.get(fixture_id)
            if not match_atual:
                del sinais_ativos[fixture_id]
                continue

            g_home = match_atual['goals']['home'] if match_atual['goals']['home'] is not None else 0
            g_away = match_atual['goals']['away'] if match_atual['goals']['away'] is not None else 0
            gols_totais_atual = g_home + g_away
            elapsed_atual = match_atual['fixture']['status']['elapsed'] or 0

            # Detecção inicial de gol (joga para a lista de espera Anti-VAR)
            if info['tipo'] == 'gols' and gols_totais_atual > info['gols_no_alerta']:
                gols_pendentes_var[fixture_id] = {
                    'message_id': info['message_id'],
                    'minuto_alerta': info['minuto_alerta'],
                    'novo_total_gols': gols_totais_atual,
                    'home': info['home'],
                    'away': info['away']
                }
                del sinais_ativos[fixture_id]
                continue

            # Feedback de Escanteios
            if info['tipo'] == 'cantos':
                estatisticas_fb = buscar_estatisticas_partida(fixture_id)
                if len(estatisticas_fb) == 2:
                    c_home = extrair_estatistica(estatisticas_fb[0]['statistics'], "Corner Kicks")
                    c_away = extrair_estatistica(estatisticas_fb[1]['statistics'], "Corner Kicks")
                    cantos_totais_atual = c_home + c_away

                    if cantos_totais_atual > info['meta_cantos'] or (elapsed_atual >= 90 and cantos_totais_atual >= info['meta_cantos']):
                        feedback_cantos = (
                            f"🟢 *ESCANTEIOS CONFIRMADOS!*\n"
                            f"🚩 {info['home']} vs {info['away']}\n"
                            f"⏱️ Alerta aos {info['minuto_alerta']}' ({info['cantos_no_alerta']} cantos)\n"
                            f"📈 Fechou com {cantos_totais_atual} escanteios no total!\n"
                            f"🎯 Meta batida com sucesso!"
                        )
                        enviar_telegram(feedback_cantos, reply_to_message_id=info['message_id'])
                        del sinais_ativos[fixture_id]

        # ==========================================
        # 3. VARREDURA DE NOVAS OPORTUNIDADES
        # ==========================================
        for match in partidas:
            try:
                league_id = match['league']['id']
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

                    jogo_goleada = (diferenca_gols >= 3 and elapsed >= 70) or (gols_totais >= 4)
                    chave_gol = f"{fixture_id}-{elapsed // 20}"
                    chave_canto = f"canto-{fixture_id}"

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

                        # A. Alerta de Gols
                        if not jogo_goleada and chave_gol not in jogos_notificados_gols:
                            e_primeiro_tempo = (18 <= elapsed <= 42) and (total_chutes_alvo >= 2 or total_chutes >= 5)
                            e_segundo_tempo = (55 <= elapsed <= 85) and (total_chutes_alvo >= 4 or total_chutes >= 12)

                            if e_primeiro_tempo or e_segundo_tempo:
                                xg_home = round((shots_on_home * 0.35) + (total_shots_home * 0.08) + (corners_home * 0.03), 2)
                                xg_away = round((shots_on_away * 0.35) + (total_shots_away * 0.08) + (corners_away * 0.03), 2)

                                if gols_totais == 0:
                                    mercado_sugerido = "Mais de 0.5 / 1.5 Gols (Live)"
                                elif gols_totais == 1:
                                    mercado_sugerido = "Mais de 1.5 / 2.5 Gols (Live)"
                                else:
                                    mercado_sugerido = f"Mais de {gols_totais + 1}.5 Gols (Live)"

                                barra_grafica = gerar_barra_pressao(total_chutes_alvo * 1.5 + total_chutes * 0.3)

                                mensagem_gols = (
                                    f"🚨 *TENDÊNCIA PARA GOL* 🚨\n\n"
                                    f"🏆 *Liga:* {league}\n"
                                    f"⚽ *Partida:* {home} {goals_home} x {goals_away} {away}\n"
                                    f"⏱️ *Alerta enviado aos* {elapsed}' • placar {goals_home}-{goals_away}\n\n"
                                    f"📊 *Intensidade de Pressão:*\n"
                                    f"{barra_grafica}\n\n"
                                    f"🎯 *Mercado Sugerido:* {mercado_sugerido}\n"
                                    f"💡 *O que o robô viu:*\n"
                                    f"⚡ Chances claras se acumulando nos últimos minutos\n"
                                    f"• Chutes no Alvo: {shots_on_home} x {shots_on_away}\n"
                                    f"• Finalizações Totais: {total_chutes}\n"
                                    f"• Posse de Bola: {pos_home}% x {pos_away}%\n"
                                    f"• xG Estimado: {xg_home} x {xg_away}\n\n"
                                    f"⚠️ Alerta estatístico baseado na leitura do jogo — não é recomendação de aposta."
                                )
                                
                                msg_id = enviar_telegram(mensagem_gols)
                                if msg_id:
                                    sinais_ativos[fixture_id] = {
                                        'message_id': msg_id,
                                        'minuto_alerta': elapsed,
                                        'gols_no_alerta': gols_totais,
                                        'home': home,
                                        'away': away,
                                        'tipo': 'gols'
                                    }

                                jogos_notificados_gols.add(chave_gol)
                                time.sleep(2)

                        # B. Alerta de Escanteios
                        if chave_canto not in jogos_notificados_cantos:
                            if 65 <= elapsed <= 85 and total_escanteios >= 8:
                                meta_cantos_sugerida = total_escanteios + 2
                                mercado_cantos = f"Mais de {total_escanteios + 2.5} Cantos (Asiáticos Live)"
                                barra_grafica_cantos = gerar_barra_pressao(total_escanteios)
                                
                                mensagem_cantos = (
                                    f"🚩 *TENDÊNCIA PARA ESCANTEIOS* 🚩\n\n"
                                    f"🏆 *Liga:* {league}\n"
                                    f"⚽ *Partida:* {home} {goals_home} x {goals_away} {away}\n"
                                    f"⏱️ *Alerta enviado aos* {elapsed}' • total de cantos: {total_escanteios}\n\n"
                                    f"📊 *Pressão Lateral:*\n"
                                    f"{barra_grafica_cantos}\n\n"
                                    f"🎯 *Mercado Sugerido:* {mercado_cantos}\n"
                                    f"💡 *O que o robô viu:*\n"
                                    f"• Escanteios Atuais: {corners_home} x {corners_away}\n"
                                    f"• Finalizações Totais: {total_chutes}\n"
                                    f"• Posse de Bola: {pos_home}% x {pos_away}%\n\n"
                                    f"⚠️ Alerta estatístico de volume lateral."
                                )
                                
                                msg_id_canto = enviar_telegram(mensagem_cantos)
                                if msg_id_canto:
                                    sinais_ativos[fixture_id] = {
                                        'message_id': msg_id_canto,
                                        'minuto_alerta': elapsed,
                                        'cantos_no_alerta': total_escanteios,
                                        'meta_cantos': meta_cantos_sugerida,
                                        'home': home,
                                        'away': away,
                                        'tipo': 'cantos'
                                    }

                                jogos_notificados_cantos.add(chave_canto)
                                time.sleep(2)

            except Exception as e:
                continue

        time.sleep(180)

if __name__ == "__main__":
    main()
