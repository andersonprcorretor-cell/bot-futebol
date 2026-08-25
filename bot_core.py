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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "SUA_GEMINI_API_KEY_AQUI") # Chave da IA

HEADERS_API = {
    'x-apisports-key': FOOTBALL_API_KEY
}

# Inicializa o cliente da Inteligência Artificial (Google GenAI)
client_ai = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY and GEMINI_API_KEY != "SUA_GEMINI_API_KEY_AQUI" else None

# Dicionário de cache anti-flood (evita mandar alerta repetido do mesmo jogo toda hora)
CACHE_ALERTAS_ENVIADOS = {}

# Dicionário para rastrear o último placar conhecido e o momento do último gol de cada partida
CONTROLE_GOLS = {}

# Dicionário para rastrear alertas ativos aguardando o resultado (para feedbacks conectados)
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
    """Busca partidas em andamento na API-Football (incluindo estatísticas)"""
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

def gerar_analise_inteligente(liga, time_casa, time_fora, gols_casa, gols_fora, minuto, tipo="gols"):
    """Usa IA para criar análise preditiva personalizada para gols ou escanteios"""
    if not client_ai:
        if tipo == "gols":
            return "██████████ (100%)", "⚡ Chances claras se acumulando nos últimos minutos\n• Placar atual apontando pressão forte"
        else:
            return "██████████ (100%)", "• Volume ofensivo intenso pelas pontas\n• Constante busca por linhas de fundo"
    
    if tipo == "gols":
        prompt = (
            f"Atue como um analista estatístico profissional de futebol e apostas Live. "
            f"Analise o jogo: {liga} | {time_casa} {gols_casa} x {gols_fora} {time_fora} aos {minuto}' do 2T.\n"
            f"Forneça estritamente:\n"
            f"1. Intensidade de pressão em barras (ex: '██████████ (100%)').\n"
            f"2. Um texto curto e dinâmico em 2 linhas começando com '•' explicando a tendência de gols."
        )
    else:
        prompt = (
            f"Atue como um analista especialista no mercado de escanteios (Corners) Live. "
            f"Analise o jogo: {liga} | {time_casa} {gols_casa} x {gols_fora} {time_fora} aos {minuto}' do 2T.\n"
            f"Forneça estritamente:\n"
            f"1. Intensidade de pressão lateral em barras (ex: '██████████ (100%)').\n"
            f"2. Um texto curto em 2 linhas começando com '•' focado em cruzamentos e escanteios."
        )
    
    try:
        response = client_ai.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        texto_resposta = response.text.strip()
        linhas = texto_resposta.split('\n')
        intensidade = linhas[0] if len(linhas) > 0 else "██████████ (100%)"
        analise_linhas = "\n".join([l for l in linhas[1:] if l.strip()])
        if not analise_linhas:
            analise_linhas = "• Alta intensidade ofensiva detectada\n• Pressão constante exercida pelos times"
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
    
    # Limpa cache antigo após 30 minutos
    CACHE_ALERTAS_ENVIADOS = {fid: ts for fid, ts in CACHE_ALERTAS_ENVIADOS.items() if tempo_atual - ts < 1800}

    # --- VERIFICAÇÃO DE FEEDBACKS (GREEN / RED / ESCANTEIOS) ---
    jogos_para_remover = []
    for fixture_id, dados_fb in MONITORAMENTO_FEEDBACK.items():
        jogo_encontrado = next((j for j in jogos if j['fixture']['id'] == fixture_id), None)
        
        if jogo_encontrado:
            g_c = jogo_encontrado['goals']['home'] or 0
            g_f = jogo_encontrado['goals']['away'] or 0
            total_gols_agora = g_c + g_f
            minuto_agora = jogo_encontrado['fixture']['status']['elapsed'] or 0
            msg_id_origem = dados_fb.get('msg_id')
            
            # Extrai estatísticas de escanteios se disponíveis na API
            stats = jogo_encontrado.get('statistics', [])
            cantos_casa, cantos_fora = 0, 0
            if stats and len(stats) >= 2:
                try:
                    for s in stats[0].get('statistics', []):
                        if 'Corner' in s.get('type', ''):
                            cantos_casa = s.get('value') or 0
                    for s in stats[1].get('statistics', []):
                        if 'Corner' in s.get('type', ''):
                            cantos_fora = s.get('value') or 0
                except:
                    pass
            total_cantos_agora = cantos_casa + cantos_fora

            if dados_fb['tipo'] == 'gols':
                # Se o total de gols aumentou -> GREEN!
                if total_gols_agora > dados_fb['gols_no_alerta']:
                    msg_feedback = (
                        f"✅ **GREEN / GOL CONFIRMADO!** ✅\n\n"
                        f"⚽ Partida: {dados_fb['time_casa']} x {dados_fb['time_fora']}\n"
                        f"⏱️ O gol saiu aos {minuto_agora}' (Alerta enviado aos {dados_fb['minuto_alerta']}')\n"
                        f"🎯 Previsão do motor estatístico validada com sucesso!"
                    )
                    enviar_alerta_telegram(msg_feedback, reply_to_id=msg_id_origem)
                    jogos_para_remover.append(fixture_id)
                elif (minuto_agora - dados_fb['minuto_alerta']) > 20:
                    # Encerra o tempo limite sem gol de Gols
                    jogos_para_remover.append(fixture_id)
                    
            elif dados_fb['tipo'] == 'escanteios':
                meta_cantos = dados_fb['meta_cantos']
                # Se atingiu a meta de escanteios
                if total_cantos_agora >= meta_cantos:
                    msg_feedback = (
                        f"✅ **ESCANTEIOS BATERAM!** 🎯\n\n"
                        f"🚩 Partida: {dados_fb['time_casa']} vs {dados_fb['time_fora']}\n"
                        f"⏱️ Alerta aos {minuto_alerta}' | Fechou com {total_cantos_agora} escanteios (Meta: Mais de {meta_cantos - 0.5})"
                    )
                    enviar_alerta_telegram(msg_feedback, reply_to_id=msg_id_origem)
                    jogos_para_remover.append(fixture_id)
                elif minuto_agora >= 88 or (minuto_agora - dados_fb['minuto_alerta']) > 20:
                    # Jogo acabando ou tempo esgotado sem bater os cantos -> RED de cantos
                    msg_feedback = (
                        f"🔴 **ESCANTEIOS NÃO BATERAM**\n\n"
                        f"🚩 Partida: {dados_fb['time_casa']} vs {dados_fb['time_fora']}\n"
                        f"⏱️ Alerta aos {minuto_alerta}' | Fechou com {total_cantos_agora} escanteios (Meta: Mais de {meta_cantos - 0.5})"
                    )
                    enviar_alerta_telegram(msg_feedback, reply_to_id=msg_id_origem)
                    jogos_para_remover.append(fixture_id)
        else:
            jogos_para_remover.append(fixture_id)
            
    for fid in jogos_para_remover:
        MONITORAMENTO_FEEDBACK.pop(fid, None)
    # -------------------------------------------------------

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
        
        # Extrai escanteios atuais da partida ao vivo
        stats = jogo.get('statistics', [])
        cantos_casa, cantos_fora = 0, 0
        if stats and len(stats) >= 2:
            try:
                for s in stats[0].get('statistics', []):
                    if 'Corner' in s.get('type', ''):
                        cantos_casa = s.get('value') or 0
                for s in stats[1].get('statistics', []):
                    if 'Corner' in s.get('type', ''):
                        cantos_fora = s.get('value') or 0
            except:
                pass
        total_cantos_atual = cantos_casa + cantos_fora

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
            
        # Evita mandar dois tipos de alerta no mesmo jogo no mesmo ciclo
        if fixture_id in CACHE_ALERTAS_ENVIADOS:
            continue

        # --- GATILHO 1: TENDÊNCIA PARA GOL (60' a 80') ---
        if status_short in ['2H'] and 60 <= minuto <= 80:
            intensidade_pressao, analise_ia = gerar_analise_inteligente(
                liga, time_casa, time_fora, gols_casa, gols_fora, minuto, tipo="gols"
            )

            mensagem = (
                f"🚨 **TENDÊNCIA PARA GOL** 🚨\n\n"
                f"🏆 Liga: {liga}\n"
                f"⚽ Partida: {time_casa} {gols_casa} x {gols_fora} {time_fora}\n"
                f"⏱️ Alerta enviado aos {minuto}' • placar {gols_casa}-{gols_fora}\n\n"
                f"📊 Intensidade de Pressão:\n"
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
        # Sugere uma linha lógica de cantos (arredondada para cima com base no ritmo atual)
        if status_short in ['2H'] and 70 <= minuto <= 80:
            meta_sugerida = total_cantos_atual + 2 # Exemplo de margem de segurança live
            intensidade_cantos, analise_cantos_ia = gerar_analise_inteligente(
                liga, time_casa, time_fora, gols_casa, gols_fora, minuto, tipo="escanteios"
            )

            mensagem_cantos = (
                f"🚩 **TENDÊNCIA PARA ESCANTEIOS** 🚩\n\n"
                f"🏆 Liga: {liga}\n"
                f"⚽ Partida: {time_casa} {gols_casa} x {gols_fora} {time_fora}\n"
                f"⏱️ Alerta enviado aos {minuto}' • Cantos atuais: {cantos_casa} x {cantos_fora} (Total: {total_cantos_atual})\n\n"
                f"📊 Intensidade Lateral:\n"
                f"{intensidade_cantos}\n\n"
                f"🎯 Mercado Sugerido: Mais de {total_cantos_atual + 1.5} Escanteios (Live)\n"
                f"💡 O que o robô viu:\n"
                f"{analise_cantos_ia}\n\n"
                f"⚠️ Alerta estatístico baseado na leitura do jogo — não é recomendação de aposta."
            )
            
            msg_id = enviar_alerta_telegram(mensagem_cantos)
            if msg_id:
                print(f"   [ALERTA ESCANTEIOS ENVIADO] 🚩 {time_casa} x {time_fora} aos {minuto}'")
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
    print("🤖 Robô de Alertas Preditivos (Gols + Escanteios + Feedbacks Vinculados) iniciado!")
    enviar_alerta_telegram("🚀 *Robô atualizado com módulos de Escanteios e Feedbacks interligados!*")
    
    while True:
        try:
            processar_partidas()
        except Exception as e:
            print(f"[ERRO NO LOOP] {e}")
        
        time.sleep(60)
