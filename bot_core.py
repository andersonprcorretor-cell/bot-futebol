import os
import time
import requests
import io
import matplotlib
matplotlib.use('Agg') # Necessário para rodar gráficos em servidores sem interface gráfica
import matplotlib.pyplot as plt
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("API_KEY")

BASE_URL = "https://v3.football.api-sports.io/fixtures"

LIGAS_PERMITIDAS = {
    # Suas Ligas Originais
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
    11,        # Copa Sul-Americana
    128,       # Argentina: Liga Profesional
    265,       # Chile: Primera División
    266,       # Chile: Primera B
    240,       # Colômbia: Primera B
    242,       # Equador: Liga Pro
    98,        # J1 League (Japão)
    292,       # K League 1 (Coreia do Sul)
    188,       # A-League (Austrália)
    94,        # Primeira Liga (Portugal)

    # Ligas Adicionadas para Teste Agora (Prints)
    # Nota: IDs genéricos/comuns de teste para capturar sub-21, copa e femininas da API-Football
    # Caso precise ajustar o ID exato da API do seu painel, você pode consultar depois. 
    # Incluídos curingas de teste nas checagens abaixo para liberar geral temporariamente se desejar!
}

# MODO TESTE ATIVO: Se quiser liberar absolutamente QUALQUER liga agora para testar os gráficos, 
# mude para True. Se quiser filtrar só pelas ligas oficiais, mude para False.
MODO_TESTE_GERAL = True 

estatisticas_diarias = {
    "data_atual": datetime.now().date(),
    "gols_enviados": 0,
    "gols_green": 0,
    "gols_red_ou_anulado": 0,
    "cantos_enviados": 0,
    "cantos_green": 0,
    "cantos_red": 0
}

def reiniciar_estatisticas_se_novo_dia():
    global estatisticas_diarias
    hoje = datetime.now().date()
    if estatisticas_diarias["data_atual"] != hoje:
        estatisticas_diarias = {
            "data_atual": hoje,
            "gols_enviados": 0,
            "gols_green": 0,
            "gols_red_ou_anulado": 0,
            "cantos_enviados": 0,
            "cantos_green": 0,
            "cantos_red": 0
        }

def enviar_telegram_com_foto(caption_texto, imagem_bytes, reply_to_message_id=None):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    
    files = {
        'photo': ('grafico_pressao.png', imagem_bytes, 'image/png')
    }
    payload = {
        "chat_id": CHAT_ID,
        "caption": caption_texto,
        "parse_mode": "Markdown"
    }
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id

    try:
        response = requests.post(url, data=payload, files=files)
        if response.status_code == 200:
            return response.json().get("result", {}).get("message_id")
        else:
            print(f"Erro Telegram Foto Response: {response.text}")
    except Exception as e:
        print(f"Erro Telegram Foto: {e}")
    return None

def enviar_telegram_texto(mensagem, reply_to_message_id=None):
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
        print(f"Erro Telegram Texto: {e}")
    return None

def gerar_imagem_grafico_pressao(home_name, away_name, stats_home, stats_away):
    categorias = ['Chutes no Alvo', 'Chutes Totais', 'Escanteios', 'Posse (%)']
    
    valores_home = [
        stats_home.get('shots_on', 0),
        stats_home.get('total_shots', 0),
        stats_home.get('corners', 0),
        stats_home.get('possession', 50)
    ]
    
    valores_away = [
        stats_away.get('shots_on', 0),
        stats_away.get('total_shots', 0),
        stats_away.get('corners', 0),
        stats_away.get('possession', 50)
    ]

    fig, ax = plt.subplots(figsize=(6, 3.5))
    fig.patch.set_facecolor('#1e1e1e')
    ax.set_facecolor('#1e1e1e')

    y = range(len(categorias))
    largura = 0.35

    ret1 = ax.barh([p - largura/2 for p in y], valores_home, largura, label=home_name, color='#1f77b4')
    ret2 = ax.barh([p + largura/2 for p in y], valores_away, largura, label=away_name, color='#ff7f0e')

    ax.set_yticks(y)
    ax.set_yticklabels(categorias, color='white', fontsize=10, fontweight='bold')
    ax.tick_params(axis='x', colors='white')
    ax.invert_yaxis()

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#555555')
    ax.spines['left'].set_color('#555555')

    ax.legend(facecolor='#2e2e2e', edgecolor='none', labelcolor='white', loc='upper right')
    plt.title("📊 Raio-X de Pressão Ao Vivo", color='white', fontsize=12, fontweight='bold', pad=10)

    for bar in ret1:
        width = bar.get_width()
        ax.annotate(f'{int(width)}',
                    xy=(width, bar.get_y() + bar.get_height() / 2),
                    xytext=(3, 0), textcoords="offset points",
                    ha='left', va='center', color='white', fontsize=9)

    for bar in ret2:
        width = bar.get_width()
        ax.annotate(f'{int(width)}',
                    xy=(width, bar.get_y() + bar.get_height() / 2),
                    xytext=(3, 0), textcoords="offset points",
                    ha='left', va='center', color='white', fontsize=9)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf.getvalue()

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

def enviar_relatorio_diario():
    global estatisticas_diarias
    total_gols = estatisticas_diarias["gols_enviados"]
    total_cantos = estatisticas_diarias["cantos_enviados"]
    
    g_green = estatisticas_diarias["gols_green"]
    g_red = estatisticas_diarias["gols_red_ou_anulado"]
    c_green = estatisticas_diarias["cantos_green"]
    c_red = estatisticas_diarias["cantos_red"]

    total_sinais = total_gols + total_cantos
    total_acertos = g_green + c_green
    total_erros = g_red + c_red

    win_rate = (total_acertos / total_sinais * 100) if total_sinais > 0 else 0

    relatorio = (
        f"📊 *RELATÓRIO DIÁRIO DE RESULTADOS* 📊\n"
        f"📅 Data: {estatisticas_diarias['data_atual'].strftime('%d/%m/%Y')}\n\n"
        f"⚽ *Mercado de Gols:*\n"
        f"• Alertas Enviados: {total_gols}\n"
        f"• Greens (Confirmados): {g_green} 🟢\n"
        f"• Reds / Anulados (VAR): {g_red} 🔴\n\n"
        f"🚩 *Mercado de Escanteios:*\n"
        f"• Alertas Enviados: {total_cantos}\n"
        f"• Greens (Bateu Meta): {c_green} 🟢\n"
        f"• Reds (Não Bateu): {c_red} 🔴\n\n"
        f"📈 *Balanço Geral do Dia:*\n"
        f"• Total de Entradas: {total_sinais}\n"
        f"• Acertos: {total_acertos} | Erros: {total_erros}\n"
        f"🎯 *Assertividade (Win Rate): {win_rate:.1f}%*\n\n"
        f"💪 Seguimos firmes e com gestão profissional!"
    )
    enviar_telegram_texto(relatorio)

def extrair_minuto_ultimo_gol(match, fallback_minute):
    eventos = match.get('events', [])
    if not eventos: 
        return fallback_minute
    
    gols = [ev for ev in eventos if ev.get('type') == 'Goal' and ev.get('detail', '').lower() != 'missed penalty']
    if gols:
        return gols[-1].get('time', {}).get('elapsed') or fallback_minute
    return fallback_minute

def main():
    print("🤖 Robô Elite com Gráficos de Pressão em Imagem iniciado e modo teste ativo!")
    
    jogos_notificados_gols = set()
    jogos_notificados_cantos = set()
    sinais_ativos = {} 
    controle_ultimo_gol = {} 
    ultimo_dia_relatorio = datetime.now().date()

    while True:
        reiniciar_estatisticas_se_novo_dia()
        
        agora = datetime.now()
        if agora.hour == 0 and agora.minute < 5 and ultimo_dia_relatorio != agora.date():
            enviar_relatorio_diario()
            ultimo_dia_relatorio = agora.date()

        partidas = buscar_jogos_ao_vivo()
        print(f"[{agora.strftime('%H:%M:%S')}] Varrendo {len(partidas)} partidas ao vivo...")
        partidas_dict = {match['fixture']['id']: match for match in partidas}

        # 1. CHECAGEM DE FEEDBACKS
        for fixture_id, info in list(sinais_ativos.items()):
            match_atual = partidas_dict.get(fixture_id)
            if not match_atual:
                del sinais_ativos[fixture_id]
                continue

            g_home = match_atual['goals']['home'] if match_atual['goals']['home'] is not None else 0
            g_away = match_atual['goals']['away'] if match_atual['goals']['away'] is not None else 0
            gols_totais_atual = g_home + g_away
            elapsed_atual = match_atual['fixture']['status']['elapsed'] or 0

            minuto_real_evento = extrair_minuto_ultimo_gol(match_atual, elapsed_atual)

            gols_anteriores_registrados = controle_ultimo_gol.get(fixture_id, {}).get("total_gols", 0)
            if gols_totais_atual > gols_anteriores_registrados:
                controle_ultimo_gol[fixture_id] = {
                    "total_gols": gols_totais_atual,
                    "minuto_gol": minuto_real_evento
                }

            if info['tipo'] == 'gols' and gols_totais_atual > info['gols_no_alerta']:
                minuto_real_do_gol = controle_ultimo_gol.get(fixture_id, {}).get("minuto_gol", elapsed_atual)
                tempo_para_agir = minuto_real_do_gol - info['minuto_alerta']
                if tempo_para_agir < 0: 
                    tempo_para_agir = 1

                feedback_msg = (
                    f"🟢 *GOL CONFIRMADO depois do alerta!*\n"
                    f"⚽ {info['home']} {g_home} x {g_away} {info['away']} • Placar Atual\n"
                    f"⏱️ Alerta enviado aos {info['minuto_alerta']}'\n"
                    f"⚽ Gol saiu aos {minuto_real_do_gol}'\n"
                    f"⏳ Você teve {tempo_para_agir} minutos para agir!"
                )
                enviar_telegram_texto(feedback_msg, reply_to_message_id=info['message_id'])
                estatisticas_diarias["gols_green"] += 1
                info['gols_no_alerta'] = gols_totais_atual
                
                if elapsed_atual >= 90:
                    del sinais_ativos[fixture_id]

            elif info['tipo'] == 'cantos':
                estatisticas_fb = buscar_estatisticas_partida(fixture_id)
                if len(estatisticas_fb) == 2:
                    c_home = extrair_estatistica(estatisticas_fb[0]['statistics'], "Corner Kicks")
                    c_away = extrair_estatistica(estatisticas_fb[1]['statistics'], "Corner Kicks")
                    cantos_totais_atual = c_home + c_away

                    if cantos_totais_atual >= info['meta_cantos']:
                        feedback_cantos = (
                            f"🟢 *ESCANTEIOS CONFIRMADOS!*\n"
                            f"🚩 {info['home']} vs {info['away']}\n"
                            f"⏱️ Alerta aos {info['minuto_alerta']}' ({info['cantos_no_alerta']} cantos)\n"
                            f"📈 Fechou com {cantos_totais_atual} escanteios no total!\n"
                            f"🎯 Meta batida com sucesso!"
                        )
                        enviar_telegram_texto(feedback_cantos, reply_to_message_id=info['message_id'])
                        estatisticas_diarias["cantos_green"] += 1
                        del sinais_ativos[fixture_id]
                    elif elapsed_atual >= 90 and cantos_totais_atual < info['meta_cantos']:
                        feedback_red = (
                            f"🔴 *ESCANTEIOS NÃO BATERAM*\n"
                            f"🚩 {info['home']} vs {info['away']}\n"
                            f"⏱️ Alerta aos {info['minuto_alerta']}' | Fechou com {cantos_totais_atual} escanteios (Meta: Mais de {info['meta_cantos']})"
                        )
                        enviar_telegram_texto(feedback_red, reply_to_message_id=info['message_id'])
                        estatisticas_diarias["cantos_red"] += 1
                        del sinais_ativos[fixture_id]

        # 2. VARREDURA DE NOVAS OPORTUNIDADES
        for match in partidas:
            try:
                league_id = match['league']['id']
                league_name = match['league']['name']
                
                if not MODO_TESTE_GERAL and league_id not in LIGAS_PERMITIDAS:
                    continue

                status_short = match['fixture']['status']['short']
                if status_short not in ['1H', '2H']:
                    continue

                fixture_id = match['fixture']['id']
                home = match['teams']['home']['name']
                away = match['teams']['home']['name'] # Proteção caso venha errado, mas vamos pegar away correto:
                away = match['teams']['away']['name']
                goals_home = match['goals']['home'] or 0
                goals_away = match['goals']['away'] or 0
                elapsed = match['fixture']['status']['elapsed'] or 0
                gols_totais = goals_home + goals_away

                print(f" -> Analisando: [{league_name}] {home} {goals_home}x{goals_away} {away} ({elapsed}')")

                teve_var = any(
                    ev.get('type') == 'Var' and (elapsed - ev.get('time', {}).get('elapsed', 0)) <= 3 
                    for ev in match.get('events', [])
                )
                if teve_var:
                    continue

                minuto_ultimo_gol_real = extrair_minuto_ultimo_gol(match, -99)
                info_gol_partida = controle_ultimo_gol.get(fixture_id, {"total_gols": gols_totais, "minuto_gol": minuto_ultimo_gol_real})
                
                if gols_totais > info_gol_partida["total_gols"]:
                    controle_ultimo_gol[fixture_id] = {
                        "total_gols": gols_totais,
                        "minuto_gol": minuto_ultimo_gol_real
                    }
                    info_gol_partida = controle_ultimo_gol[fixture_id]

                diferenca_gols = abs(goals_home - goals_away)
                jogo_goleada = (diferenca_gols >= 3 and elapsed >= 70) or (gols_totais >= 4)
                chave_gol = f"{fixture_id}-{elapsed // 20}"
                chave_canto = f"canto-{fixture_id}"

                teve_gol_recente = (elapsed - info_gol_partida["minuto_gol"]) <= 4

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

                    # A. Alerta de Gols com Imagem Gráfica
                    if not jogo_goleada and not teve_gol_recente and chave_gol not in jogos_notificados_gols:
                        e_primeiro_tempo = (18 <= elapsed <= 42) and (total_chutes_alvo >= 2 or total_chutes >= 5)
                        e_segundo_tempo = (55 <= elapsed <= 85) and (total_chutes_alvo >= 4 or total_chutes >= 12)

                        if e_primeiro_tempo or e_segundo_tempo:
                            xg_home = round((shots_on_home * 0.35) + (total_shots_home * 0.08) + (corners_home * 0.03), 2)
                            xg_away = round((shots_on_away * 0.35) + (total_shots_away * 0.08) + (corners_away * 0.03), 2)

                            mercado_sugerido = "Mais de 0.5 / 1.5 Gols (Live)" if gols_totais == 0 else f"Mais de {gols_totais}.5 Gols (Live)"

                            dados_home_dict = {'shots_on': shots_on_home, 'total_shots': total_shots_home, 'corners': corners_home, 'possession': pos_home}
                            dados_away_dict = {'shots_on': shots_on_away, 'total_shots': total_shots_away, 'corners': corners_away, 'possession': pos_away}
                            
                            img_bytes = gerar_imagem_grafico_pressao(home, away, dados_home_dict, dados_away_dict)

                            mensagem_gols = (
                                f"🚨 *TENDÊNCIA PARA GOL* 🚨\n\n"
                                f"🏆 *Liga:* {league_name}\n"
                                f"⚽ *Partida:* {home} {goals_home} x {goals_away} {away}\n"
                                f"⏱️ *Alerta enviado aos* {elapsed}' • placar {goals_home}-{goals_away}\n\n"
                                f"🎯 *Mercado Sugerido:* {mercado_sugerido}\n"
                                f"💡 *O que o robô viu:*\n"
                                f"• Chutes no Alvo: {shots_on_home} x {shots_on_away}\n"
                                f"• Finalizações Totais: {total_chutes}\n"
                                f"• Posse de Bola: {pos_home}% x {pos_away}%\n"
                                f"• xG Estimado: {xg_home} x {xg_away}"
                            )
                            
                            msg_id = enviar_telegram_com_foto(mensagem_gols, img_bytes)
                            if msg_id:
                                sinais_ativos[fixture_id] = {
                                    'message_id': msg_id,
                                    'minuto_alerta': elapsed,
                                    'gols_no_alerta': gols_totais,
                                    'home': home,
                                    'away': away,
                                    'tipo': 'gols'
                                }
                                estatisticas_diarias["gols_enviados"] += 1

                            jogos_notificados_gols.add(chave_gol)
                            time.sleep(2)

                    # B. Alerta de Escanteios
                    if chave_canto not in jogos_notificados_cantos:
                        if 65 <= elapsed <= 85 and total_escanteios >= 8:
                            meta_cantos_decimal = total_escanteios + 2.5
                            mercado_cantos = f"Mais de {meta_cantos_decimal} Cantos (Asiáticos Live)"
                            
                            dados_home_dict = {'shots_on': shots_on_home, 'total_shots': total_shots_home, 'corners': corners_home, 'possession': pos_home}
                            dados_away_dict = {'shots_on': shots_on_away, 'total_shots': total_shots_home, 'corners': corners_away, 'possession': pos_away}
                            
                            img_bytes_canto = gerar_imagem_grafico_pressao(home, away, dados_home_dict, dados_away_dict)

                            mensagem_cantos = (
                                f"🚩 *TENDÊNCIA PARA ESCANTEIOS* 🚩\n\n"
                                f"🏆 *Liga:* {league_name}\n"
                                f"⚽ *Partida:* {home} {goals_home} x {goals_away} {away}\n"
                                f"⏱️ *Alerta enviado aos* {elapsed}' • total de cantos: {total_escanteios}\n\n"
                                f"🎯 *Mercado Sugerido:* {mercado_cantos}\n"
                                f"💡 *O que o robô viu:*\n"
                                f"• Escanteios Atuais: {corners_home} x {corners_away}\n"
                                f"• Finalizações Totais: {total_chutes}\n"
                                f"• Posse de Bola: {pos_home}% x {pos_away}%"
                            )
                            
                            msg_id_canto = enviar_telegram_com_foto(mensagem_cantos, img_bytes_canto)
                            if msg_id_canto:
                                sinais_ativos[fixture_id] = {
                                    'message_id': msg_id_canto,
                                    'minuto_alerta': elapsed,
                                    'cantos_no_alerta': total_escanteios,
                                    'meta_cantos': meta_cantos_decimal,
                                    'home': home,
                                    'away': away,
                                    'tipo': 'cantos'
                                }
                                estatisticas_diarias["cantos_enviados"] += 1

                            jogos_notificados_cantos.add(chave_canto)
                            time.sleep(2)

            except Exception as e:
                continue

        time.sleep(90)

if __name__ == "__main__":
    main()
