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

# Inicializa o cliente da Inteligência Artificial (Google GenAI)
client_ai = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY and GEMINI_API_KEY != "SUA_GEMINI_API_KEY_AQUI" else None

CACHE_ALERTAS_ENVIADOS = {}
CONTROLE_GOLS = {}
MONITORAMENTO_FEEDBACK = {}

def enviar_alerta_telegram(mensagem, reply_to_id=None):
    """Envia o alerta formatado para o chat do Telegram e retorna o ID da mensagem enviada"""
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
            dados_resp = response.json()
            return dados_resp.get("result", {}).get("message_id")
        else:
            print(f"[ERRO TELEGRAM] Código {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[EXCEÇÃO TELEGRAM] Erro ao enviar mensagem: {e}")
    return None

def buscar_jogos_ao_vivo():
    """Busca partidas em andamento na API-Football"""
    url = "https://v3.football.api-sports.io/fixtures"
    params = {"live": "all"}
    try:
        response = requests.get(url, headers=HEADERS_API, params=params, timeout=15)
        if response.status_code == 200:
            dados_json = response.json()
            return dados_json.get('response', [])
        else:
            print(f"[ERRO API] Retornou status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[EXCEÇÃO API] Erro ao buscar jogos ao vivo: {e}")
    return []

def buscar_estatisticas_partida(fixture_id):
    """Busca estatísticas detalhadas diretamente na rota específica da API-Football"""
    url = "https://v3.football.api-sports.io/fixtures/statistics"
    params = {"fixture": fixture_id}
    try:
        response = requests.get(url, headers=HEADERS_API, params=params, timeout=10)
        if response.status_code == 200:
            dados_json = response.json()
            resp = dados_json.get('response', [])
            # LOG DE DIAGNÓSTICO: Mostra no console do Railway o que a API está retornando para este jogo
            print(f"[DEBUG STATS API] Jogo {fixture_id} retornou {len(resp)} blocos de estatísticas.")
            return resp
    except Exception as e:
        print(f"[EXCEÇÃO STATS API] Erro ao buscar estatísticas do jogo {fixture_id}: {e}")
    return []

def extrair_estatisticas(fixture_id):
    """Extração robusta e blindada mapeando diretamente os nomes oficiais da API-Football"""
    stats = {
        "posse_casa": "50%", "posse_fora": "50%",
        "chutes_alvo_casa": 0, "chutes_alvo_fora": 0,
        "chutes_fora_casa": 0, "chutes_fora_fora": 0,
        "ataques_perigosos_casa": 0, "ataques_perigosos_fora": 0,
        "cantos_casa": 0, "cantos_fora": 0
    }
    
    stats_lista = buscar_estatisticas_partida(fixture_id)
    if not stats_lista or len(stats_lista) < 2:
        print(f"[AVISO] Jogo {fixture_id} sem dados estatísticos na rota /fixtures/statistics ainda.")
        return stats

    try:
        for idx, time_data in enumerate(stats_lista[:2]):
            sufixo = "casa" if idx == 0 else "fora"
            estatisticas_time = time_data.get('statistics', [])
            
            for s in estatisticas_time:
                stype = str(s.get('type', '')).strip()
                sval = s.get('value')
                
                if sval is None:
                    continue
                
                # Conversão segura de valores (aceita inteiros, strings com % etc)
                val_limpo = 0
                try:
                    if isinstance(sval, str):
                        val_limpo = int(sval.replace('%', '').strip())
                    else:
                        val_limpo = int(sval)
                except:
                    val_limpo = 0

                # Mapeamento exato dos termos oficiais da API-Football
                if stype == "Ball Possession":
                    stats[f"posse_{sufixo}"] = str(sval) if '%' in str(sval) else f"{sval}%"
                elif stype == "Shots on Goal":
                    stats[f"chutes_alvo_{sufixo}"] = val_limpo
                elif stype == "Shots off Goal":
                    stats[f"chutes_fora_{sufixo}"] = val_limpo
                elif stype == "Total Shots":
                    # Caso venha Total Shots em vez de off/on separados, usamos para compor
                    pass
                elif stype == "Dangerous Attacks":
                    stats[f"ataques_perigosos_{sufixo}"] = val_limpo
                elif stype == "Corner Kicks":
                    stats[f"cantos_{sufixo}"] = val_limpo
                    
    except Exception as e:
        print(f"[EXCEÇÃO ESTATÍSTICAS] Erro ao processar estatísticas do jogo {fixture_id}: {e}")
        
    return stats

def gerar_analise_inteligente(liga, time_casa, time_fora, gols_casa, gols_fora, minuto, estats, tipo="gols"):
    """Usa IA para criar análise preditiva personalizada utilizando as estatísticas detalhadas da partida"""
    if not client_ai:
        return "██████████ (100%)", "• Pressão constante exercida no terço final\n• Alto volume ofensivo nos minutos recentes"
    
    resumo_stats = (
        f"Estatísticas atuais - Posse: {estats['posse_casa']} x {estats['posse_fora']} | "
        f"Chutes no Alvo: {estats['chutes_alvo_casa']} x {estats['chutes_alvo_fora']} | "
        f"Chutes Fora: {estats['chutes_fora_casa']} x {estats['chutes_fora_fora']} | "
        f"Ataques Perigosos: {estats['ataques_perigosos_casa']} x {estats['ataques_perigosos_fora']} | "
        f"Escanteios: {estats['cantos_casa']} x {estats['cantos_fora']}"
    )

    if tipo == "gols":
        prompt = (
            f"Atue como um analista estatístico profissional de futebol e apostas Live. "
            f"Analise o jogo: {liga} | {time_casa} {gols_casa} x {gols_fora} {time_fora} aos {minuto}' do 2T.\n"
            f"Dados estatísticos reais da partida:\n{resumo_stats}\n\n"
            f"Forneça estritamente:\n"
            f"1. Intensidade de pressão em barras (ex: '██████████ (100%)').\n"
            f"2. Um texto curto e dinâmico em 2 linhas começando com '•' explicando a tendência de gols com base nestes dados."
        )
    else:
        prompt = (
            f"Atue como um analista especialista no mercado de escanteios (Corners) Live. "
            f"Analise o jogo: {liga} | {time_casa} {gols_casa} x {gols_fora} {time_fora} aos {minuto}' do 2T.\n"
            f"Dados estatísticos reais da partida:\n{resumo_stats}\n\n"
            f"Forneça estritamente:\n"
            f"1. Intensidade de pressão lateral em barras (ex: '██████████ (100%)').\n"
            f"2. Um texto curto em 2 linhas começando com '•' focado no volume real de cantos e pressão pelas pontas."
        )
    
    try:
        response = client_ai.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt
        )
        texto_resposta = response.text.strip()
        linhas = texto_resposta.split('\n')
        intensidade = linhas[0] if len(linhas) > 0 else "██████████ (100%)"
        analise_linhas = "\n".join([l for l in linhas[1:] if l.strip()])
        if not analise_linhas:
            analise_linhas = "• Alta intensidade ofensiva detectada nos números\n• Pressão contínua em busca do objetivo"
        return intensidade, analise_linhas
    except Exception as e:
        print(f"[EXCEÇÃO IA] Erro ao gerar análise: {e}")
        return "██████████ (100%)", "• Alta movimentação e volume no setor ofensivo\n• Pressão contínua em busca do objetivo"

def processar_partidas():
    hora_atual = datetime.now().strftime('%H:%M:%S')
    print(f"\n[{hora_atual}] Iniciando varredura de partidas...")
    jogos = buscar_jogos_ao_vivo()
    
    if not jogos:
        print(f"[{hora_atual}] Nenhum jogo ao vivo encontrado na API nesta varredura.")
        return

    global CACHE_ALERTAS_ENVIADOS, CONTROLE_GOLS, MONITORAMENTO_FEEDBACK
    tempo_atual = time.time()
    
    CACHE_ALERTAS_ENVIADOS = {fid: ts for fid, ts in CACHE_ALERTAS_ENVIADOS.items() if tempo_atual - ts < 1800}

    # --- VERIFICAÇÃO DE FEEDBACKS ---
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
                    msg_feedback = (
                        f"✅ **GREEN / GOL CONFIRMADO!** ✅\n\n"
                        f"⚽ Partida: {dados_fb['time_casa']} {g_c} x {g_f} {dados_fb['time_fora']}\n"
                        f"⏱️ O gol saiu aos {minuto_agora}' (Alerta enviado aos {dados_fb['minuto_alerta']}')\n"
                        f"🎯 Previsão do motor estatístico validada com sucesso!"
                    )
                    enviar_alerta_telegram(msg_feedback, reply_to_id=msg_id_origem)
                    jogos_para_remover.append(fixture_id)
                elif (minuto_agora - dados_fb['minuto_alerta']) > 20:
                    jogos_para_remover.append(fixture_id)
                    
            elif dados_fb['tipo'] == 'escanteios':
                meta_cantos = dados_fb['meta_cantos']
                if total_cantos_agora >= meta_cantos:
                    msg_feedback = (
                        f"✅ **ESCANTEIOS BATERAM!** 🎯\n\n"
                        f"🚩 Partida: {dados_fb['time_casa']} {g_c} x {g_f} {dados_fb['time_fora']}\n"
                        f"⏱️ Alerta aos {minuto_agora}' | Fechou com {total_cantos_agora} escanteios (Meta: Mais de {meta_cantos - 0.5})"
                    )
                    enviar_alerta_telegram(msg_feedback, reply_to_id=msg_id_origem)
                    jogos_para_remover.append(fixture_id)
                elif minuto_agora >= 88 or (minuto_agora - dados_fb['minuto_alerta']) > 20:
                    msg_feedback = (
                        f"🔴 **ESCANTEIOS NÃO BATERAM**\n\n"
                        f"🚩 Partida: {dados_fb['time_casa']} {g_c} x {g_f} {dados_fb['time_fora']}\n"
                        f"⏱️ Alerta aos {minuto_agora}' | Fechou com {total_cantos_agora} escanteios (Meta: Mais de {meta_cantos - 0.5})"
                    )
                    enviar_alerta_telegram(msg_feedback, reply_to_id=msg_id_origem)
                    jogos_para_remover.append(fixture_id)
        else:
            jogos_para_remover.append(fixture_id)
            
    for fid in jogos_para_remover:
        MONITORAMENTO_FEEDBACK.pop(fid, None)
    # ---------------------------------------------

    alertas_enviados_ciclo = 0
    for jogo in jogos:
        fixture_id = jogo['fixture']['id']
        liga = jogo['league']['name']
        time_casa = jogo['teams']['home']['name']
        time_fora = jogo['teams']['away']['name']
        
        gols_casa = jogo['goals']['home'] if jogo['goals']['home'] is not None else 0
        gols_fora = jogo['goals']['away'] if jogo['goals']['away'] is not None else 0
        total_gols_atual = gols_casa + gols_fora
        
        minuto = jogo['fixture']['status']['elapsed'] or 0
        status_short = jogo['fixture']['status']['short']
        
        # --- TRAVA ANTI-GOL ---
        if fixture_id not in CONTROLE_GOLS:
            CONTROLE_GOLS[fixture_id] = {'total_gols': total_gols_atual, 'minuto_ultimo_gol': -99}
            
        estado_jogo = CONTROLE_GOLS[fixture_id]
        if total_gols_atual > estado_jogo['total_gols']:
            CONTROLE_GOLS[fixture_id]['total_gols'] = total_gols_atual
            CONTROLE_GOLS[fixture_id]['minuto_ultimo_gol'] = minuto
            continue
        
        CONTROLE_GOLS[fixture_id]['total_gols'] = total_gols_atual
        minuto_do_ultimo_gol = CONTROLE_GOLS[fixture_id]['minuto_ultimo_gol']
        
        if (minuto - minuto_do_ultimo_gol) < 4:
            continue
            
        if fixture_id in CACHE_ALERTAS_ENVIADOS:
            continue

        # --- GATILHO 1: TENDÊNCIA PARA GOL (60' a 80') ---
        if status_short in ['2H'] and 60 <= minuto <= 80:
            estats = extrair_estatisticas(fixture_id)
            total_cantos_atual = estats['cantos_casa'] + estats['cantos_fora']

            intensidade_pressao, analise_ia = gerar_analise_inteligente(
                liga, time_casa, time_fora, gols_casa, gols_fora, minuto, estats, tipo="gols"
            )

            mensagem = (
                f"🚨 **TENDÊNCIA PARA GOL** 🚨\n\n"
                f"🏆 Liga: {liga}\n"
                f"⚽ Partida: {time_casa} {gols_casa} x {gols_fora} {time_fora}\n"
                f"⏱️ Alerta enviado aos {minuto}' • Placar {gols_casa}-{gols_fora}\n\n"
                f"📊 **Estatísticas Reais ao Vivo:**\n"
                f"• Posse: {estats['posse_casa']} x {estats['posse_fora']}\n"
                f"• Chutes no Alvo: {estats['chutes_alvo_casa']} x {estats['chutes_alvo_fora']}\n"
                f"• Chutes para Fora: {estats['chutes_fora_casa']} x {estats['chutes_fora_fora']}\n"
                f"• Ataques Perigosos: {estats['ataques_perigosos_casa']} x {estats['ataques_perigosos_fora']}\n"
                f"• Escanteios: {estats['cantos_casa']} x {estats['cantos_fora']}\n\n"
                f"📈 Intensidade de Pressão:\n"
                f"{intensidade_pressao}\n\n"
                f"🎯 Mercado Sugerido: Mais de {total_gols_atual + 0.5} Gols (Live)\n"
                f"💡 O que o robô viu:\n"
                f"{analise_ia}\n\n"
                f"⚠️ Alerta estatístico baseado na leitura do jogo — não é recomendação de aposta."
            )
            
            msg_id = enviar_alerta_telegram(mensagem)
            if msg_id:
                print(f"   [ALERTA GOLS ENVIADO] 🚨 {time_casa} x {time_fora} aos {minuto}'")
                CACHE_ALERTAS_ENVIADOS[fixture_id] = tempo_atual
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

        # --- GATILHO 2: TENDÊNCIA PARA ESCANTEIOS (70' a 80') ---
        if status_short in ['2H'] and 70 <= minuto <= 80:
            estats = extrair_estatisticas(fixture_id)
            total_cantos_atual = estats['cantos_casa'] + estats['cantos_fora']
            meta_sugerida = total_cantos_atual + 2

            intensidade_cantos, analise_cantos_ia = gerar_analise_inteligente(
                liga, time_casa, time_fora, gols_casa, gols_fora, minuto, estats, tipo="escanteios"
            )

            mensagem_cantos = (
                f"🚩 **TENDÊNCIA PARA ESCANTEIOS** 🚩\n\n"
                f"🏆 Liga: {liga}\n"
                f"⚽ Partida: {time_casa} {gols_casa} x {gols_fora} {time_fora}\n"
                f"⏱️ Alerta enviado aos {minuto}' • Total de Cantos: {total_cantos_atual}\n\n"
                f"📊 **Estatísticas Reais ao Vivo:**\n"
                f"• Posse: {estats['posse_casa']} x {estats['posse_fora']}\n"
                f"• Chutes no Alvo: {estats['chutes_alvo_casa']} x {estats['chutes_alvo_fora']}\n"
                f"• Ataques Perigosos: {estats['ataques_perigosos_casa']} x {estats['ataques_perigosos_fora']}\n"
                f"• Escanteios: {estats['cantos_casa']} x {estats['cantos_fora']}\n\n"
                f"📈 Intensidade Lateral:\n"
                f"{intensidade_cantos}\n\n"
                f"🎯 Mercado Sugerido: Mais de {total_cantos_atual + 1.5} Escanteios (Live)\n"
                f"💡 O que o robô viu:\n"
                f"{analise_cantos_ia}\n\n"
                f"⚠️ Alerta estatístico baseado na leitura do jogo — não é recomendação de aposta."
            )
            
            msg_id = enviar_alerta_telegram(mensagem_cantos)
            if msg_id:
                print(f"   [ALERTA ESCANTEIOS ENVIADO] 🚩 {time_casa} x {time_fora} aos {minuto}'")
                CACHE_CACHE_ALERTAS_ENVIADOS = tempo_atual  # Mantém compatibilidade
                CACHE_ALERTAS_ENVIADOS[fixture_id] = tempo_atual
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
    print("🤖 Robô de Alertas Preditivos (Com Diagnóstico de Stats) iniciado!")
    enviar_alerta_telegram("🚀 *Robô atualizado com logs de diagnóstico de estatísticas!*")
    
    while True:
        try:
            processar_partidas()
        except Exception as e:
            print(f"[ERRO NO LOOP] {e}")
        
        time.sleep(60)
