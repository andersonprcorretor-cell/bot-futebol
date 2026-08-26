import os
import time
import requests
from datetime import datetime
from google import genai

# ==========================================
# CONFIGURAÇÕES E CREDENCIAIS DO ROBÔ
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "SEU_TELEGRAM_TOKEN_AQUI")
CHAT_ID = os.getenv("CHAT_ID", "SEU_CHAT_ID_AQUI")
FOOTBALL_API_KEY = os.getenv("API_KEY", "SUA_API_KEY_AQUI")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "SUA_GEMINI_API_KEY_AQUI")

HEADERS_API = {
    'x-apisports-key': FOOTBALL_API_KEY
}

client_ai = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY and GEMINI_API_KEY != "SUA_GEMINI_API_KEY_AQUI" else None

CACHE_ALERTAS_ENVIADOS = {}
CONTROLE_GOLS = {}
MONITORAMENTO_FEEDBACK = {}
HISTORICO_MOMENTUM = {}

LIGAS_PRINCIPAIS = [
    "Copa Libertadores", "Copa Sudamericana", "UEFA Champions League", "UEFA Europa League", 
    "UEFA Conference League", "Serie A", "Premier League", "La Liga", "Bundesliga", "Ligue 1",
    "Brasileiro Série A", "Brasileiro Série B", "Brasileiro Série C", "Copa do Brasil", 
    "Liga Professional", "Copa de la Liga Profesional", "Primera División", "Categoría Primera A",
    "Primeira Liga", "Eredivisie", "Eerste Divisie", "Championship", "Segunda Division", 
    "Serie B", "2. Bundesliga", "Ligue 2", "Scottish Premiership", "Super Lig", "Pro League",
    "Superligaen", "Allsvenskan", "Eliteserien", "Saudi Pro League", "MLS", "J1 League", 
    "K League 1", "Liga MX", "Primera B", "Lengjudeildin", "Copa Paraguay", "Liga 1", "LDF", "Qualification"
]

def validar_liga_principal(nome_liga):
    if not nome_liga:
        return False
    for liga in LIGAS_PRINCIPAIS:
        if liga.lower() in nome_liga.lower():
            return True
    return False

def enviar_alerta_telegram(mensagem, reply_to_id=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    if reply_to_id:
        payload["reply_to_message_id"] = reply_to_id
        
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json().get("result", {}).get("message_id")
    except Exception as e:
        print(f"[EXCEÇÃO TELEGRAM] Erro ao enviar mensagem: {e}")
    return None

def buscar_jogos_ao_vivo():
    url = "https://v3.football.api-sports.io/fixtures"
    params = {"live": "all"}
    try:
        response = requests.get(url, headers=HEADERS_API, params=params, timeout=15)
        if response.status_code == 200:
            return response.json().get('response', [])
    except Exception as e:
        print(f"[EXCEÇÃO API] Erro ao buscar jogos ao vivo: {e}")
    return []

def buscar_estatisticas_partida(fixture_id):
    url = "https://v3.football.api-sports.io/fixtures/statistics"
    params = {"fixture": int(fixture_id)}
    try:
        response = requests.get(url, headers=HEADERS_API, params=params, timeout=10)
        if response.status_code == 200:
            return response.json().get('response', [])
    except Exception as e:
        print(f"[EXCEÇÃO STATS API] Erro ao buscar estatísticas do jogo {fixture_id}: {e}")
    return []

def processar_todas_estatisticas(stats_lista):
    stats = {
        "posse_casa": "50%", "posse_fora": "50%",
        "chutes_totais_casa": 0, "chutes_totais_fora": 0,
        "chutes_alvo_casa": 0, "chutes_alvo_fora": 0,
        "chutes_fora_casa": 0, "chutes_fora_fora": 0,
        "chutes_dentro_area_casa": 0, "chutes_dentro_area_fora": 0,
        "ataques_perigosos_casa": 0, "ataques_perigosos_fora": 0,
        "cantos_casa": 0, "cantos_fora": 0,
        "dados_validos": False
    }
    
    stats_avancadas = {
        "xg_casa": 0.0, "xg_fora": 0.0,
        "chutes_bloqueados_casa": 0, "chutes_bloqueados_fora": 0,
        "defesas_goleiro_casa": 0, "defesas_goleiro_fora": 0
    }
    
    cartoes_info = {
        "faltas_casa": 0, "faltas_fora": 0,
        "cartoes_amarelos_casa": 0, "cartoes_amarelos_fora": 0,
        "cartoes_vermelhos_casa": 0, "cartoes_vermelhos_fora": 0
    }

    if not stats_lista or len(stats_lista) < 2:
        return stats, stats_avancadas, cartoes_info

    try:
        for idx, time_data in enumerate(stats_lista[:2]):
            sufixo = "casa" if idx == 0 else "fora"
            estatisticas_time = time_data.get('statistics', [])
            
            for s in estatisticas_time:
                stype = str(s.get('type', '')).strip().lower()
                sval = s.get('value')
                
                if sval is None:
                    continue
                
                val_str = str(sval).strip()
                val_limpo = 0
                try:
                    val_limpo = int(float(val_str.replace('%', '')))
                except:
                    pass

                # Estatísticas Básicas
                if "ball possession" in stype:
                    stats[f"posse_{sufixo}"] = val_str if '%' in val_str else f"{val_str}%"
                    stats["dados_validos"] = True
                elif "total shots" in stype:
                    stats[f"chutes_totais_{sufixo}"] = val_limpo
                    stats["dados_validos"] = True
                elif "shots on goal" in stype:
                    stats[f"chutes_alvo_{sufixo}"] = val_limpo
                    stats["dados_validos"] = True
                elif "shots off goal" in stype:
                    stats[f"chutes_fora_{sufixo}"] = val_limpo
                elif "shots inside" in stype or "inside the box" in stype:
                    stats[f"chutes_dentro_area_{sufixo}"] = val_limpo
                elif "dangerous attacks" in stype or "attacks" in stype:
                    stats[f"ataques_perigosos_{sufixo}"] = val_limpo
                    stats["dados_validos"] = True
                elif "corner kicks" in stype:
                    stats[f"cantos_{sufixo}"] = val_limpo
                    stats["dados_validos"] = True
                    
                # Estatísticas Avançadas
                elif "expected goals" in stype or stype == "xg":
                    try:
                        stats_avancadas[f"xg_{sufixo}"] = float(val_str)
                    except:
                        pass
                elif "blocked shots" in stype or "shots blocked" in stype:
                    stats_avancadas[f"chutes_bloqueados_{sufixo}"] = val_limpo
                elif "goalkeeper saves" in stype or "saves" in stype:
                    stats_avancadas[f"defesas_goleiro_{sufixo}"] = val_limpo

                # Cartões e Faltas
                elif "fouls" in stype:
                    cartoes_info[f"faltas_{sufixo}"] = val_limpo
                elif "yellow cards" in stype:
                    cartoes_info[f"cartoes_amarelos_{sufixo}"] = val_limpo
                elif "red cards" in stype:
                    cartoes_info[f"cartoes_vermelhos_{sufixo}"] = val_limpo

    except Exception as e:
        print(f"[EXCEÇÃO PROCESSAR STATS] {e}")

    return stats, stats_avancadas, cartoes_info

def extrair_estatisticas(fixture_id):
    stats_lista = buscar_estatisticas_partida(fixture_id)
    stats, _, _ = processar_todas_estatisticas(stats_lista)
    return stats

def extrair_estatisticas_avancadas(fixture_id):
    stats_lista = buscar_estatisticas_partida(fixture_id)
    _, stats_avancadas, _ = processar_todas_estatisticas(stats_lista)
    return stats_avancadas

def extrair_estatisticas_cartoes(fixture_id):
    stats_lista = buscar_estatisticas_partida(fixture_id)
    _, _, cartoes_info = processar_todas_estatisticas(stats_lista)
    return cartoes_info

def gerar_grafico_momentum(fixture_id, intensidade_atual_valor):
    global HISTORICO_MOMENTUM
    if fixture_id not in HISTORICO_MOMENTUM:
        HISTORICO_MOMENTUM[fixture_id] = [3, 5, 4, 7]
    
    historico = HISTORICO_MOMENTUM[fixture_id]
    historico.append(intensidade_atual_valor)
    if len(historico) > 6:
        historico.pop(0)
        
    blocos = [' ', '▂', '▃', '▄', '▅', '▆', '▇', '█']
    grafico_str = ""
    for val in historico:
        indice = min(int((val / 10) * len(blocos)), len(blocos) - 1)
        grafico_str += blocos[indice] + " "
        
    return f"`[{grafico_str.strip()}]` (Pressão Recente)"

def gerar_analise_inteligente(liga, time_casa, time_fora, gols_casa, gols_fora, minuto, periodo_etapa, estats, estats_avancadas, tipo="gols", cartoes_info=None):
    if not client_ai:
        return 8, f"• O volume apresentado por {time_casa} e {time_fora} demonstra clara intensidade em campo.\n• Os indicadores estatísticos sustentam a expectativa de movimentação."
    
    resumo_stats = (
        f"Estatísticas - Posse: {estats['posse_casa']} x {estats['posse_fora']} | "
        f"Chutes Totais: {estats['chutes_totais_casa']} x {estats['chutes_totais_fora']} | "
        f"Chutes Alvo: {estats['chutes_alvo_casa']} x {estats['chutes_alvo_fora']} | "
        f"Dentro da Área: {estats['chutes_dentro_area_casa']} x {estats['chutes_dentro_area_fora']} | "
        f"Escanteios: {estats['cantos_casa']} x {estats['cantos_fora']}"
    )

    if tipo == "cartoes" and cartoes_info:
        resumo_stats += f" | Faltas: {cartoes_info['faltas_casa']} x {cartoes_info['faltas_fora']} | Cartões Amarelos: {cartoes_info['cartoes_amarelos_casa']} x {cartoes_info['cartoes_amarelos_fora']}"

    if estats_avancadas['xg_casa'] > 0.0 or estats_avancadas['xg_fora'] > 0.0:
        resumo_stats += f" | xG: {estats_avancadas['xg_casa']} x {estats_avancadas['xg_fora']}"

    prompt = (
        f"Você é um analista especialista em futebol ao vivo. "
        f"Com base nas estatísticas atuais da partida para o mercado de {tipo.upper()}, elabore uma leitura tática de alto nível, "
        f"mas explicada de forma natural, fluida e acessível, focando no que o jogo está de fato apresentando neste instante:\n\n"
        f"- Competição: {liga}\n"
        f"- Placar: {time_casa} {gols_casa} x {gols_fora} {time_fora}\n"
        f"- Minuto: {minuto}' do {periodo_etapa}\n"
        f"- Dados Estatísticos: {resumo_stats}\n\n"
        f"Diretrizes obrigatórias:\n"
        f"1. Na PRIMEIRA linha, forneça apenas um número inteiro de 1 a 10 indicando a força da pressão ou tensão atual do jogo (exemplo: '9').\n"
        f"2. Escreva exatamente 2 ou 3 tópicos curtos iniciados por '•'. Traduza os números frios em uma explicação clara e dinâmica da partida (ex: volume de faltas acumuladas, índice de rispidez, pressão territorial ou jogo picotado), mantendo a profundidade técnica.\n"
        f"3. Seja direto e evite clichês repetitivos."
    )
    
    try:
        response = client_ai.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        texto_resposta = response.text.strip()
        linhas = [l.strip() for l in texto_resposta.split('\n') if l.strip()]
        
        nota_num = 8
        indice_inicio_texto = 0
        
        if linhas:
            for char in linhas[0]:
                if char.isdigit():
                    nota_num = int(char)
                    indice_inicio_texto = 1
                    break
        nota_num = max(1, min(10, nota_num))
        
        analise_linhas = "\n".join(linhas[indice_inicio_texto:])
        if not analise_linhas:
            analise_linhas = f"• O índice de faltas e a temperatura da partida exigem atenção total.\n• O cenário aos {minuto}' favorece o mercado projetado."
        return nota_num, analise_linhas
    except Exception as e:
        return 8, f"• O índice de faltas e a temperatura da partida exigem atenção total.\n• O cenário aos {minuto}' favorece o mercado projetado."

def processar_partidas():
    hora_atual = datetime.now().strftime('%H:%M:%S')
    print(f"\n[{hora_atual}] Varredura completa em tempo real...")
    jogos = buscar_jogos_ao_vivo()
    
    if not jogos:
        return

    global CACHE_ALERTAS_ENVIADOS, CONTROLE_GOLS, MONITORAMENTO_FEEDBACK
    tempo_atual = time.time()
    CACHE_ALERTAS_ENVIADOS = {key: ts for key, ts in CACHE_ALERTAS_ENVIADOS.items() if tempo_atual - ts < 1200}

    jogos_para_remover = []
    for fixture_id, dados_fb in MONITORAMENTO_FEEDBACK.items():
        jogo_encontrado = next((j for j in jogos if j['fixture']['id'] == fixture_id), None)
        if jogo_encontrado:
            g_c = jogo_encontrado['goals']['home'] or 0
            g_f = jogo_encontrado['goals']['away'] or 0
            total_gols_agora = g_c + g_f
            minuto_agora = jogo_encontrado['fixture']['status']['elapsed'] or 0
            msg_id_origem = dados_fb.get('msg_id')
            
            stats_lista = buscar_estatisticas_partida(fixture_id)
            estats_atuais, _, cartoes_atuais = processar_todas_estatisticas(stats_lista)
            
            total_cantos_agora = estats_atuais['cantos_casa'] + estats_atuais['cantos_fora']
            total_cartoes_agora = cartoes_atuais['cartoes_amarelos_casa'] + cartoes_atuais['cartoes_amarelos_fora'] + (cartoes_atuais['cartoes_vermelhos_casa'] + cartoes_atuais['cartoes_vermelhos_fora']) * 2

            if dados_fb['tipo'] == 'gols':
                if total_gols_agora > dados_fb['gols_no_alerta']:
                    minutos_para_agir = minuto_agora - dados_fb['minuto_alerta']
                    enviar_alerta_telegram(f"✅ **GREEN / GOL CONFIRMADO!** ✅\n\n⚽ Partida: {dados_fb['time_casa']} {g_c} x {g_f} {dados_fb['time_fora']}\n⏱️ Gol aos {minuto_agora}' (Alerta aos {dados_fb['minuto_alerta']}')\n⏳ Reação: {minutos_para_agir} min", reply_to_id=msg_id_origem)
                    jogos_para_remover.append(fixture_id)
                elif (minuto_agora - dados_fb['minuto_alerta']) > 15:
                    jogos_para_remover.append(fixture_id)
            elif dados_fb['tipo'] == 'escanteios':
                meta_cantos = dados_fb['meta_cantos']
                if total_cantos_agora >= meta_cantos:
                    minutos_para_agir = minuto_agora - dados_fb['minuto_alerta']
                    enviar_alerta_telegram(f"✅ **ESCANTEIOS BATERAM!** 🎯\n\n🚩 Partida: {dados_fb['time_casa']} {g_c} x {g_f} {dados_fb['time_fora']}\n⏱️ Alerta aos {dados_fb['minuto_alerta']}' | Fechou com {total_cantos_agora} cantos\n⏳ Reação: {minutos_para_agir} min", reply_to_id=msg_id_origem)
                    jogos_para_remover.append(fixture_id)
                elif minuto_agora >= 89 or (minuto_agora - dados_fb['minuto_alerta']) > 15:
                    enviar_alerta_telegram(f"🔴 **ESCANTEIOS NÃO BATERAM**\n\n🚩 Partida: {dados_fb['time_casa']} {g_c} x {g_f} {dados_fb['time_fora']}\n⏱️ Alerta aos {dados_fb['minuto_alerta']}' | Fechou com {total_cantos_agora} cantos", reply_to_id=msg_id_origem)
                    jogos_para_remover.append(fixture_id)
            elif dados_fb['tipo'] == 'cartoes':
                meta_cartoes = dados_fb['meta_cartoes']
                if total_cartoes_agora >= meta_cartoes:
                    minutos_para_agir = minuto_agora - dados_fb['minuto_alerta']
                    enviar_alerta_telegram(f"✅ **CARTÕES BATERAM!** 🟨\n\n🟨 Partida: {dados_fb['time_casa']} {g_c} x {g_f} {dados_fb['time_fora']}\n⏱️ Alerta aos {dados_fb['minuto_alerta']}' | Fechou com {total_cartoes_agora} cartões\n⏳ Reação: {minutos_para_agir} min", reply_to_id=msg_id_origem)
                    jogos_para_remover.append(fixture_id)
                elif minuto_agora >= 89 or (minuto_agora - dados_fb['minuto_alerta']) > 20:
                    enviar_alerta_telegram(f"🔴 **CARTÕES NÃO BATERAM**\n\n🟨 Partida: {dados_fb['time_casa']} {g_c} x {g_f} {dados_fb['time_fora']}\n⏱️ Alerta aos {dados_fb['minuto_alerta']}' | Fechou com {total_cartoes_agora} cartões", reply_to_id=msg_id_origem)
                    jogos_para_remover.append(fixture_id)
        else:
            jogos_para_remover.append(fixture_id)
            
    for fid in jogos_para_remover:
        MONITORAMENTO_FEEDBACK.pop(fid, None)

    alertas_enviados_ciclo = 0
    for jogo in jogos:
        liga = jogo['league']['name']
        if not validar_liga_principal(liga):
            continue

        fixture_id = jogo['fixture']['id']
        time_casa = jogo['teams']['home']['name']
        time_fora = jogo['teams']['away']['name']
        
        gols_casa = jogo['goals']['home'] if jogo['goals']['home'] is not None else 0
        gols_fora = jogo['goals']['away'] if jogo['goals']['away'] is not None else 0
        total_gols_atual = gols_casa + gols_fora
        
        minuto = jogo['fixture']['status']['elapsed'] or 0
        status_short = jogo['fixture']['status']['short']
        
        if fixture_id not in CONTROLE_GOLS:
            CONTROLE_GOLS[fixture_id] = {'total_gols': total_gols_atual, 'minuto_ultimo_gol': minuto}
            
        estado_jogo = CONTROLE_GOLS[fixture_id]
        
        if total_gols_atual > estado_jogo['total_gols']:
            CONTROLE_GOLS[fixture_id]['total_gols'] = total_gols_atual
            CONTROLE_GOLS[fixture_id]['minuto_ultimo_gol'] = minuto
            continue
        
        CONTROLE_GOLS[fixture_id]['total_gols'] = total_gols_atual
        
        if (minuto - estado_jogo['minuto_ultimo_gol']) < 3:
            continue

        # Avaliar janelas antes de buscar estatísticas
        gols_1t_inicio = (status_short == '1H' and 15 <= minuto <= 25)
        gols_1t_fim   = (status_short == '1H' and 35 <= minuto <= 45)
        gols_2t_inicio = (status_short == '2H' and 55 <= minuto <= 65)
        gols_2t_fim   = (status_short == '2H' and 75 <= minuto <= 89)
        precisa_gols = (gols_1t_inicio or gols_1t_fim or gols_2t_inicio or gols_2t_fim) and (f"{fixture_id}_gols" not in CACHE_ALERTAS_ENVIADOS)

        cantos_1t = (status_short == '1H' and 28 <= minuto <= 38)
        cantos_2t = (status_short == '2H' and 65 <= minuto <= 85)
        precisa_cantos = (cantos_1t or cantos_2t) and (f"{fixture_id}_escanteios" not in CACHE_ALERTAS_ENVIADOS)

        cartoes_1t = (status_short == '1H' and 30 <= minuto <= 42)
        cartoes_2t = (status_short == '2H' and 70 <= minuto <= 85)
        precisa_cartoes = (cartoes_1t or cartoes_2t) and (f"{fixture_id}_cartoes" not in CACHE_ALERTAS_ENVIADOS)

        # Se o jogo não está em NENHUMA janela elegível, não faz chamadas desnecessárias à API
        if not (precisa_gols or precisa_cantos or precisa_cartoes):
            continue

        # Bate APENAS 1 VEZ na API de Estatísticas por partida
        stats_lista = buscar_estatisticas_partida(fixture_id)
        estats, estats_avancadas, cartoes_info = processar_todas_estatisticas(stats_lista)

        if precisa_gols:
            periodo_etapa = "1T" if status_short == '1H' else "2T"
            if estats['dados_validos']:
                nota_pressao, analise_ia = gerar_analise_inteligente(
                    liga, time_casa, time_fora, gols_casa, gols_fora, minuto, periodo_etapa, estats, estats_avancadas, tipo="gols"
                )
                grafico_visual = gerar_grafico_momentum(fixture_id, nota_pressao)

                bloco_avancado_str = ""
                if estats_avancadas['xg_casa'] > 0.0 or estats_avancadas['xg_fora'] > 0.0:
                    bloco_avancado_str += f"• xG (Expectativa de Gol): {estats_avancadas['xg_casa']} x {estats_avancadas['xg_fora']}\n"
                if estats_avancadas['chutes_bloqueados_casa'] > 0 or estats_avancadas['chutes_bloqueados_fora'] > 0:
                    bloco_avancado_str += f"• Chutes Bloqueados: {estats_avancadas['chutes_bloqueados_casa']} x {estats_avancadas['chutes_bloqueados_fora']}\n"

                mensagem = (
                    f"🚨 **TENDÊNCIA PARA GOL ({periodo_etapa})** 🚨\n\n"
                    f"🏆 Liga: {liga}\n"
                    f"⚽ Partida: {time_casa} {gols_casa} x {gols_fora} {time_fora}\n"
                    f"⏱️ Alerta aos {minuto}' ({periodo_etapa}) • Placar {gols_casa}-{gols_fora}\n\n"
                    f"📊 **Estatísticas Reais:**\n"
                    f"• Posse: {estats['posse_casa']} x {estats['posse_fora']}\n"
                    f"• Chutes Totais: {estats['chutes_totais_casa']} x {estats['chutes_totais_fora']}\n"
                    f"• Chutes no Alvo: {estats['chutes_alvo_casa']} x {estats['chutes_alvo_fora']}\n"
                    f"• Chutes para Fora: {estats['chutes_fora_casa']} x {estats['chutes_fora_fora']}\n"
                    f"• Chutes Dentro da Área: {estats['chutes_dentro_area_casa']} x {estats['chutes_dentro_area_fora']}\n"
                    f"• Escanteios: {estats['cantos_casa']} x {estats['cantos_fora']}\n"
                    f"{bloco_avancado_str}"
                    f"📈 **Gráfico de Momentum:**\n"
                    f"{grafico_visual}\n\n"
                    f"🎯 Mercado Sugerido: Mais de {total_gols_atual + 0.5} Gols ({periodo_etapa})\n"
                    f"💡 **Análise da Partida:**\n"
                    f"{analise_ia}\n\n"
                    f"⚠️ Alerta estatístico baseado em dados reais — gerencie sua banca."
                )
                
                msg_id = enviar_alerta_telegram(mensagem)
                if msg_id:
                    print(f"   [ALERTA GOLS {periodo_etapa} ENVIADO] 🚨 {time_casa} x {time_fora} aos {minuto}'")
                    CACHE_ALERTAS_ENVIADOS[f"{fixture_id}_gols"] = tempo_atual
                    MONITORAMENTO_FEEDBACK[fixture_id] = {
                        'tipo': 'gols',
                        'gols_no_alerta': total_gols_atual,
                        'time_casa': time_casa,
                        'time_fora': time_fora,
                        'minuto_alerta': minuto,
                        'msg_id': msg_id
                    }
                    alertas_enviados_ciclo += 1
                    continue

        if precisa_cantos:
            periodo_etapa = "1T" if status_short == '1H' else "2T"
            if estats['dados_validos']:
                total_cantos_atual = estats['cantos_casa'] + estats['cantos_fora']

                nota_pressao, analise_cantos_ia = gerar_analise_inteligente(
                    liga, time_casa, time_fora, gols_casa, gols_fora, minuto, periodo_etapa, estats, estats_avancadas, tipo="escanteios"
                )
                grafico_visual = gerar_grafico_momentum(fixture_id, nota_pressao)

                mensagem_cantos = (
                    f"🚩 **TENDÊNCIA PARA ESCANTEIOS ({periodo_etapa})** 🚩\n\n"
                    f"🏆 Liga: {liga}\n"
                    f"⚽ Partida: {time_casa} {gols_casa} x {gols_fora} {time_fora}\n"
                    f"⏱️ Alerta aos {minuto}' ({periodo_etapa}) • Total de Cantos: {total_cantos_atual}\n\n"
                    f"📊 **Estatísticas de Pressão Lateral:**\n"
                    f"• Escanteios: {estats['cantos_casa']} x {estats['cantos_fora']}\n"
                    f"• Chutes Totais: {estats['chutes_totais_casa']} x {estats['chutes_totais_fora']}\n"
                    f"• Chutes no Alvo: {estats['chutes_alvo_casa']} x {estats['chutes_alvo_fora']}\n"
                    f"• Posse de Bola: {estats['posse_casa']} x {estats['posse_fora']}\n\n"
                    f"📈 **Gráfico de Momentum:**\n"
                    f"{grafico_visual}\n\n"
                    f"🎯 Mercado Sugerido: Mais de {total_cantos_atual + 1.5} Escanteios (Live)\n"
                    f"💡 **Análise da Partida:**\n"
                    f"{analise_cantos_ia}\n\n"
                    f"⚠️ Alerta estatístico baseado em dados reais — gerencie sua banca."
                )
                
                msg_id = enviar_alerta_telegram(mensagem_cantos)
                if msg_id:
                    print(f"   [ALERTA ESCANTEIOS {periodo_etapa} ENVIADO] 🚩 {time_casa} x {time_fora} aos {minuto}'")
                    CACHE_ALERTAS_ENVIADOS[f"{fixture_id}_escanteios"] = tempo_atual
                    MONITORAMENTO_FEEDBACK[fixture_id] = {
                        'tipo': 'escanteios',
                        'meta_cantos': total_cantos_atual + 1.5,
                        'time_casa': time_casa,
                        'time_fora': time_fora,
                        'minuto_alerta': minuto,
                        'msg_id': msg_id
                    }
                    alertas_enviados_ciclo += 1
                    continue

        if precisa_cartoes:
            periodo_etapa = "1T" if status_short == '1H' else "2T"
            total_faltas_atual = cartoes_info['faltas_casa'] + cartoes_info['faltas_fora']
            total_cartoes_atual = cartoes_info['cartoes_amarelos_casa'] + cartoes_info['cartoes_amarelos_fora'] + (cartoes_info['cartoes_vermelhos_casa'] + cartoes_info['cartoes_vermelhos_fora']) * 2

            nota_pressao, analise_cartoes_ia = gerar_analise_inteligente(
                liga, time_casa, time_fora, gols_casa, gols_fora, minuto, periodo_etapa, estats, estats_avancadas, tipo="cartoes", cartoes_info=cartoes_info
            )
            grafico_visual = gerar_grafico_momentum(fixture_id, nota_pressao)

            mensagem_cartoes = (
                f"🟨 **TENDÊNCIA PARA CARTÕES ({periodo_etapa})** 🟨\n\n"
                f"🏆 Liga: {liga}\n"
                f"⚽ Partida: {time_casa} {gols_casa} x {gols_fora} {time_fora}\n"
                f"⏱️ Alerta aos {minuto}' ({periodo_etapa}) • Faltas: {total_faltas_atual} | Cartões: {total_cartoes_atual}\n\n"
                f"📊 **Estatísticas Disciplinares:**\n"
                f"• Faltas Cometidas: {cartoes_info['faltas_casa']} x {cartoes_info['faltas_fora']}\n"
                f"• Cartões Amarelos: {cartoes_info['cartoes_amarelos_casa']} x {cartoes_info['cartoes_amarelos_fora']}\n"
                f"• Cartões Vermelhos: {cartoes_info['cartoes_vermelhos_casa']} x {cartoes_info['cartoes_vermelhos_fora']}\n\n"
                f"📈 **Gráfico de Tensão (Momentum):**\n"
                f"{grafico_visual}\n\n"
                f"🎯 Mercado Sugerido: Mais de {total_cartoes_atual + 0.5} Cartões (Live)\n"
                f"💡 **Análise da Partida:**\n"
                f"{analise_cartoes_ia}\n\n"
                f"⚠️ Alerta estatístico baseado em dados reais — gerencie sua banca."
            )
            
            msg_id = enviar_alerta_telegram(mensagem_cartoes)
            if msg_id:
                print(f"   [ALERTA CARTÕES {periodo_etapa} ENVIADO] 🟨 {time_casa} x {time_fora} aos {minuto}'")
                CACHE_ALERTAS_ENVIADOS[f"{fixture_id}_cartoes"] = tempo_atual
                MONITORAMENTO_FEEDBACK[fixture_id] = {
                    'tipo': 'cartoes',
                    'meta_cartoes': total_cartoes_atual + 1,
                    'time_casa': time_casa,
                    'time_fora': time_fora,
                    'minuto_alerta': minuto,
                    'msg_id': msg_id
                }
                alertas_enviados_ciclo += 1

    print(f"[{hora_atual}] Varredura finalizada. Alertas disparados neste ciclo: {alertas_enviados_ciclo}")

if __name__ == "__main__":
    print("🤖 Robô atualizado com modelo Gemini 2.5 Flash e pipeline otimizado!")
    enviar_alerta_telegram("🚀 *Robô atualizado na Railway: Modelo Gemini 2.5 Flash ativado com otimização total de requisições!*")
    
    while True:
        try:
            processar_partidas()
        except Exception as e:
            print(f"[ERRO NO LOOP] {e}")
        
        time.sleep(60)
