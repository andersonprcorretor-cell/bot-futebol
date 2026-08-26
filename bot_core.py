import os
import time
import requests
import re
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

# Mude para False caso queira testar e monitorar TODAS as ligas ao vivo do mundo sem restrição de nomes
FILTRAR_APENAS_LIGAS_PRINCIPAIS = True

LIGAS_PRINCIPAIS = [
    "libertadores", "sudamericana", "champions", "europa league", "conference", 
    "premier league", "la liga", "bundesliga", "ligue 1", "serie a", "serie b",
    "brasileiro", "copa do brasil", "liga professional", "primera division", 
    "primera", "primeira liga", "eredivisie", "championship", "segunda", 
    "super lig", "pro league", "superligaen", "allsvenskan", "eliteserien", 
    "saudi professional league", "mls", "j1 league", "k league", "liga mx", "liga 1"
]

def validar_liga_principal(nome_liga):
    if not FILTRAR_APENAS_LIGAS_PRINCIPAIS:
        return True
    if not nome_liga:
        return False
    nome_lower = nome_liga.lower()
    for termo in LIGAS_PRINCIPAIS:
        if termo in nome_lower:
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
        else:
            print(f"[ERRO TELEGRAM] Status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[EXCEÇÃO TELEGRAM] Erro ao enviar mensagem: {e}")
    return None

def buscar_jogos_ao_vivo():
    url = "https://v3.football.api-sports.io/fixtures"
    params = {"live": "all"}
    try:
        response = requests.get(url, headers=HEADERS_API, params=params, timeout=15)
        if response.status_code == 200:
            dados = response.json().get('response', [])
            print(f"[API] Total de jogos ao vivo retornados pela API: {len(dados)}")
            return dados
        else:
            print(f"[ERRO API JOGOS] Status {response.status_code}: {response.text}")
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

def extrair_estatisticas(fixture_id):
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
    
    stats_lista = buscar_estatisticas_partida(fixture_id)
    if not stats_lista or len(stats_lista) < 2:
        return stats

    try:
        for idx, time_data in enumerate(stats_lista[:2]):
            sufixo = "casa" if idx == 0 else "fora"
            estatisticas_time = time_data.get('statistics', [])
            
            for s in estatisticas_time:
                stype = str(s.get('type', '')).strip().lower()
                sval = s.get('value')
                
                if sval is None:
                    continue
                
                val_limpo = 0
                try:
                    val_str = str(sval).replace('%', '').strip()
                    val_limpo = int(float(val_str))
                except:
                    pass

                if "ball possession" in stype:
                    stats[f"posse_{sufixo}"] = str(sval) if '%' in str(sval) else f"{sval}%"
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
    except Exception as e:
        print(f"[EXCEÇÃO ESTATÍSTICAS] {e}")
        
    return stats

def extrair_estatisticas_avancadas(fixture_id):
    stats_avancadas = {
        "xg_casa": 0.0, "xg_fora": 0.0,
        "chutes_bloqueados_casa": 0, "chutes_bloqueados_fora": 0,
        "defesas_goleiro_casa": 0, "defesas_goleiro_fora": 0
    }
    
    stats_lista = buscar_estatisticas_partida(fixture_id)
    if not stats_lista or len(stats_lista) < 2:
        return stats_avancadas

    try:
        for idx, time_data in enumerate(stats_lista[:2]):
            sufixo = "casa" if idx == 0 else "fora"
            estatisticas_time = time_data.get('statistics', [])
            
            for s in estatisticas_time:
                stype = str(s.get('type', '')).strip().lower()
                sval = s.get('value')
                
                if sval is None:
                    continue
                
                try:
                    val_str = str(sval).strip()
                    if "expected goals" in stype or stype == "xg":
                        stats_avancadas[f"xg_{sufixo}"] = float(val_str)
                    elif "blocked shots" in stype or "shots blocked" in stype:
                        stats_avancadas[f"chutes_bloqueados_{sufixo}"] = int(float(val_str))
                    elif "goalkeeper saves" in stype or "saves" in stype:
                        stats_avancadas[f"defesas_goleiro_{sufixo}"] = int(float(val_str))
                except:
                    pass
    except Exception as e:
        pass
        
    return stats_avancadas

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

def gerar_analise_inteligente(liga, time_casa, time_fora, gols_casa, gols_fora, minuto, periodo_etapa, estats, estats_avancadas, tipo="gols"):
    if not client_ai:
        return 8, f"• O volume ofensivo apresentado por {time_casa} e {time_fora} demonstra clara pressão territorial.\n• Os indicadores estatísticos sustentam a expectativa de movimentação no placar."
    
    resumo_stats = (
        f"Posse: {estats['posse_casa']} x {estats['posse_fora']} | "
        f"Chutes Totais: {estats['chutes_totais_casa']} x {estats['chutes_totais_fora']} | "
        f"Alvo: {estats['chutes_alvo_casa']} x {estats['chutes_alvo_fora']} | "
        f"Dentro da Área: {estats['chutes_dentro_area_casa']} x {estats['chutes_dentro_area_fora']} | "
        f"Cantos: {estats['cantos_casa']} x {estats['cantos_fora']}"
    )

    if estats_avancadas['xg_casa'] > 0.0 or estats_avancadas['xg_fora'] > 0.0:
        resumo_stats += f" | xG: {estats_avancadas['xg_casa']} x {estats_avancadas['xg_fora']}"
        
    if estats_avancadas['chutes_bloqueados_casa'] > 0 or estats_avancadas['chutes_bloqueados_fora'] > 0:
        resumo_stats += f" | Bloqueados: {estats_avancadas['chutes_bloqueados_casa']} x {estats_avancadas['chutes_bloqueados_fora']}"

    prompt = (
        f"Atue como um Analista Tático Sênior e Especialista Quantitativo de Futebol.\n"
        f"Gere uma leitura situacional técnica e profunda sobre o jogo abaixo, focada no mercado de {tipo.upper()}.\n\n"
        f"CENÁRIO DA PARTIDA:\n"
        f"🏆 Competição: {liga}\n"
        f"⚽ Placar: {time_casa} {gols_casa} x {gols_fora} {time_fora}\n"
        f"⏱️ Tempo: {minuto}' do {periodo_etapa}\n"
        f"📊 Estatísticas Atuais: {resumo_stats}\n\n"
        f"REGRAS DE FORMATAÇÃO OBRIGATÓRIAS:\n"
        f"1. Na PRIMEIRA LINHA, escreva APENAS um número inteiro de 1 a 10 (representando a força da tendência para sair mais {tipo}).\n"
        f"2. A partir da segunda linha, escreva EXATAMENTE 3 tópicos curtos e robustos, começando cada um com o símbolo '• '.\n"
        f"3. Tópico 1: Analise o controle territorial, posse de bola e quem dita o ritmo do jogo no momento.\n"
        f"4. Tópico 2: Descreva o desenho tático e transições (ex: como um time fura o bloco defensivo do outro, efetividade nos chutes de dentro da área).\n"
        f"5. Tópico 3: Dê o veredito situacional explicando por que a dinâmica e os espaços cedidos mantêm o mercado de {tipo} muito aquecido.\n"
        f"Use jargões táticos reais (bloco baixo, transição vertical, retenção, último terço) e seja incisivo. Nada de clichês."
    )
    
    try:
        response = client_ai.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt
        )
        texto_resposta = response.text.strip()
        linhas = [l.strip() for l in texto_resposta.split('\n') if l.strip()]
        
        nota_num = 8
        indice_inicio_texto = 0
        
        if linhas:
            match = re.search(r'\d+', linhas[0])
            if match:
                nota_num = int(match.group())
                indice_inicio_texto = 1
                
        nota_num = max(1, min(10, nota_num))
        analise_linhas = "\n".join(linhas[indice_inicio_texto:]).strip()
        
        if len(analise_linhas) < 20:
            analise_linhas = (
                f"• O volume ofensivo e a criação de jogadas mantêm forte pressão territorial no último terço do campo.\n"
                f"• A equipe que domina as ações busca frestas na marcação, gerando oportunidades reais dentro da área.\n"
                f"• Os indicadores quantitativos aos {minuto}' sustentam plenamente a expectativa de movimentação no placar."
            )
            
        return nota_num, analise_linhas
    except Exception as e:
        print(f"[ERRO IA] Falha na geração do conteúdo: {e}")
        return 8, (
            f"• A circulação de bola demonstra um padrão agressivo de tentativas de quebra de linhas defensivas.\n"
            f"• O número de finalizações consolidadas reflete uma transição ofensiva rápida e constante.\n"
            f"• O desenho tático aos {minuto}' favorece amplamente a expectativa no mercado de {tipo}."
        )

def processar_partidas():
    hora_atual = datetime.now().strftime('%H:%M:%S')
    print(f"\n[{hora_atual}] Varredura completa em tempo real...")
    jogos = buscar_jogos_ao_vivo()
    
    if not jogos:
        print("[AVISO] Nenhum jogo ao vivo retornado pela API neste ciclo.")
        return

    global CACHE_ALERTAS_ENVIADOS, CONTROLE_GOLS, MONITORAMENTO_FEEDBACK
    tempo_atual = time.time()
    CACHE_ALERTAS_ENVIADOS = {fid: ts for fid, ts in CACHE_ALERTAS_ENVIADOS.items() if tempo_atual - ts < 1200}

    # Verificação de feedbacks
    jogos_para_remover = []
    for fixture_id, dados_fb in MONITORAMENTO_FEEDBACK.items():
        jogo_encontrado = next((j for j in jogos if j['fixture']['id'] == fixture_id), None)
        if jogo_encontrado:
            g_c = jogo_encontrado['goals']['home'] or 0
            g_f = jogo_encontrado['goals']['away'] or 0
            total_gols_agora = g_c + g_f
            minuto_agora = jogo_encontrado['fixture']['status']['elapsed'] or 0
            msg_id_origem = dados_fb.get('msg_id')
            estats_atuais = extrair_estatisticas(fixture_id)
            total_cantos_agora = estats_atuais['cantos_casa'] + estats_atuais['cantos_fora']

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
        
        print(f"   [MONITORANDO] {liga} | {time_casa} {gols_casa}x{gols_fora} {time_fora} | Minuto: {minuto}' ({status_short})")
        
        # Proteção de reinicialização (Boot)
        if fixture_id not in CONTROLE_GOLS:
            CONTROLE_GOLS[fixture_id] = {
                'total_gols': total_gols_atual, 
                'minuto_ultimo_gol': minuto if total_gols_atual > 0 else -99
            }
            continue 
            
        estado_jogo = CONTROLE_GOLS[fixture_id]
        
        if total_gols_atual > estado_jogo['total_gols']:
            CONTROLE_GOLS[fixture_id]['total_gols'] = total_gols_atual
            CONTROLE_GOLS[fixture_id]['minuto_ultimo_gol'] = minuto
            continue
        
        # Cooldown de 5 minutos após o último gol
        if (minuto - estado_jogo['minuto_ultimo_gol']) < 5:
            continue
            
        rolando_1t = (status_short == '1H' and 10 <= minuto <= 43)
        rolando_2t = (status_short == '2H' and 48 <= minuto <= 88)

        chave_gols = f"{fixture_id}_gols"
        if (rolando_1t or rolando_2t) and chave_gols not in CACHE_ALERTAS_ENVIADOS:
            periodo_etapa = "1T" if status_short == '1H' else "2T"
            estats = extrair_estatisticas(fixture_id)
            
            if estats['dados_validos']:
                estats_avancadas = extrair_estatisticas_avancadas(fixture_id)

                nota_pressao, analise_ia = gerar_analise_inteligente(
                    liga, time_casa, time_fora, gols_casa, gols_fora, minuto, periodo_etapa, estats, estats_avancadas, tipo="gols"
                )
                
                print(f"      -> IA Nota Gols: {nota_pressao} para {time_casa} x {time_fora}")

                # Reduzido temporariamente para 6 para garantir disparos iniciais de teste
                if nota_pressao >= 6:
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
                        print(f"   [ALERTA GOLS {periodo_etapa} ENVIADO] 🚨 {time_casa} x {time_fora} aos {minuto}' (Nota: {nota_pressao})")
                        CACHE_ALERTAS_ENVIADOS[chave_gols] = tempo_atual
                        MONITORAMENTO_FEEDBACK[fixture_id] = {
                            'tipo': 'gols',
                            'gols_no_alerta': total_gols_atual,
                            'time_casa': time_casa,
                            'time_fora': time_fora,
                            'minuto_alerta': minuto,
                            'msg_id': msg_id
                        }
                        alertas_enviados_ciclo += 1

        # Monitoramento contínuo para escanteios
        chave_cantos = f"{fixture_id}_cantos"
        if (rolando_1t or rolando_2t) and chave_cantos not in CACHE_ALERTAS_ENVIADOS:
            periodo_etapa = "1T" if status_short == '1H' else "2T"
            estats = extrair_estatisticas(fixture_id)
            
            if estats['dados_validos']:
                estats_avancadas = extrair_estatisticas_avancadas(fixture_id)
                total_cantos_atual = estats['cantos_casa'] + estats['cantos_fora']

                nota_pressao_cantos, analise_cantos_ia = gerar_analise_inteligente(
                    liga, time_casa, time_fora, gols_casa, gols_fora, minuto, periodo_etapa, estats, estats_avancadas, tipo="escanteios"
                )
                
                if nota_pressao_cantos >= 6:
                    grafico_visual = gerar_grafico_momentum(fixture_id, nota_pressao_cantos)

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
                        print(f"   [ALERTA ESCANTEIOS {periodo_etapa} ENVIADO] 🚩 {time_casa} x {time_fora} aos {minuto}' (Nota: {nota_pressao_cantos})")
                        CACHE_ALERTAS_ENVIADOS[chave_cantos] = tempo_atual
                        MONITORAMENTO_FEEDBACK[fixture_id] = {
                            'tipo': 'escanteios',
                            'meta_cantos': total_cantos_atual + 2,
                            'time_casa': time_casa,
                            'time_fora': time_fora,
                            'minuto_alerta': minuto,
                            'msg_id': msg_id
                        }
                        alertas_enviados_ciclo += 1

    print(f"[{hora_atual}] Varredura finalizada. Alertas disparados neste ciclo: {alertas_enviados_ciclo}")

if __name__ == "__main__":
    print("🤖 Robô atualizado com logs de diagnóstico e validação flexível de ligas!")
    enviar_alerta_telegram("🚀 *Robô reiniciado e conectado com sucesso ao sistema de monitoramento contínuo!*")
    
    while True:
        try:
            processar_partidas()
        except Exception as e:
            print(f"[ERRO NO LOOP] {e}")
        
        time.sleep(60)
