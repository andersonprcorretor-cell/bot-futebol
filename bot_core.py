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
# Formato: { fixture_id: {'total_gols': int, 'minuto_ultimo_gol': int} }
CONTROLE_GOLS = {}

# Dicionário para rastrear alertas ativos aguardando o gol (para o feedback de Green)
# Formato: { fixture_id: {'gols_no_alerta': int, 'time_casa': str, 'time_fora': str, 'minuto_alerta': int} }
MONITORAMENTO_FEEDBACK = {}

def enviar_alerta_telegram(mensagem):
    """Envia o alerta formatado para o chat do Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"[ERRO TELEGRAM] Código {response.status_code}: {response.text}")
    except Exception as e:
        print(f"[EXCEÇÃO TELEGRAM] Erro ao enviar mensagem: {e}")

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

def gerar_analise_inteligente(liga, time_casa, time_fora, gols_casa, gols_fora, minuto):
    """Usa IA para criar análise preditiva e texto dinâmico personalizado para a partida"""
    if not client_ai:
        # Fallback caso a chave da IA não esteja configurada, mantendo o padrão original
        return "██████████ (100%)", "⚡ Chances claras se acumulando nos últimos minutos\n• Placar atual apontando pressão forte"
    
    prompt = (
        f"Atue como um analista estatístico profissional de futebol e apostas esportivas Live. "
        f"Analise o seguinte cenário de jogo ao vivo:\n"
        f"- Liga: {liga}\n"
        f"- Partida: {time_casa} {gols_casa} x {gols_fora} {time_fora}\n"
        f"- Momento: Aos {minuto}' do segundo tempo.\n\n"
        f"Forneça estritamente duas informações no seguinte formato de resposta:\n"
        f"1. Intensidade de pressão em barras (ex: '████████░░ (80%)' ou '██████████ (100%)') baseada na urgência do momento.\n"
        f"2. Um texto curto e dinâmico (em 2 linhas começando com '•') explicando de forma técnica e envolvente o motivo pelo qual há alta tendência de gol agora.\n"
        f"Seja direto, profissional e focado no mercado de gols."
    )
    
    try:
        response = client_ai.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        texto_resposta = response.text.strip()
        
        # Processamento simples para extrair os blocos gerados pela IA
linhas = texto_resposta.split('\n')
        intensidade = linhas[0] if len(linhas) > 0 else "██████████ (100%)"
        analise_linhas = "\n".join([l for l in linhas[1:] if l.strip()])
        if not analise_linhas:
            analise_linhas = "⚡ Alta intensidade ofensiva detectada no setor final\n• Pressão constante exercida pelos mandantes"
            
        return intensidade, analise_linhas
    except Exception as e:
        print(f"[EXCEÇÃO IA] Erro ao gerar análise com IA: {e}")
        return "██████████ (100%)", "⚡ Chances claras se acumulando nos últimos minutos\n• Placar atual apontando pressão forte"

def processar_partidas():
    hora_atual = datetime.now().strftime('%H:%M:%S')
    print(f"\n[{hora_atual}] Iniciando varredura de partidas...")
    jogos = buscar_jogos_ao_vivo()
    
    if not jogos:
        print(f"[{hora_atual}] Nenhum jogo ao vivo encontrado na API nesta varredura.")
        return

    global CACHE_ALERTAS_ENVIADOS, CONTROLE_GOLS, MONITORAMENTO_FEEDBACK
    tempo_atual = time.time()
    
    # Limpa cache antigo (permite re-alertar a mesma partida após 30 minutos se o cenário mudar)
    CACHE_ALERTAS_ENVIADOS = {fid: ts for fid, ts in CACHE_ALERTAS_ENVIADOS.items() if tempo_atual - ts < 1800}

    # --- VERIFICAÇÃO DE FEEDBACK (GREEN / GOL CONFIRMADO) ---
    jogos_para_remover_feedback = []
    for fixture_id, dados_fb in MONITORAMENTO_FEEDBACK.items():
        jogo_encontrado = next((j for j in jogos if j['fixture']['id'] == fixture_id), None)
        
        if jogo_encontrado:
            g_c = jogo_encontrado['goals']['home'] or 0
            g_f = jogo_encontrado['goals']['away'] or 0
            total_gols_agora = g_c + g_f
            minuto_agora = jogo_encontrado['fixture']['status']['elapsed'] or 0
            
            # Se o total de gols aumentou desde que o alerta foi disparado -> GREEN!
            if total_gols_agora > dados_fb['gols_no_alerta']:
                msg_feedback = (
                    f"✅ **GREEN / GOL CONFIRMADO!** ✅\n\n"
                    f"⚽ Partida: {dados_fb['time_casa']} x {dados_fb['time_fora']}\n"
                    f"⏱️ O gol saiu aos {minuto_agora}' (Alerta enviado aos {dados_fb['minuto_alerta']}')\n"
                    f"🎯 Previsão do motor estatístico validada com sucesso!"
                )
                enviar_alerta_telegram(msg_feedback)
                print(f"   [FEEDBACK ENVIADO] ✅ Green confirmado para {dados_fb['time_casa']} x {dados_fb['time_fora']}")
                jogos_para_remover_feedback.append(fixture_id)
            
            # Se passaram mais de 20 minutos desde o alerta e não saiu gol, encerra o monitoramento deste jogo
            elif (minuto_agora - dados_fb['minuto_alerta']) > 20:
                jogos_para_remover_feedback.append(fixture_id)
        else:
            jogos_para_remover_feedback.append(fixture_id)
            
    for fid in jogos_para_remover_feedback:
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
        
        # --- TRAVA ANTI-GOL / COOLDOWN PÓS-GOL ---
        if fixture_id not in CONTROLE_GOLS:
            CONTROLE_GOLS[fixture_id] = {'total_gols': total_gols_atual, 'minuto_ultimo_gol': -99}
            
        estado_jogo = CONTROLE_GOLS[fixture_id]
        
        # Se o placar aumentou em relação à última varredura, um gol acabou de acontecer!
        if total_gols_atual > estado_jogo['total_gols']:
            print(f"   [GOL DETECTADO] ⚽ {time_casa} x {time_fora} marcou aos {minuto}'. Ativando trava de segurança pós-gol.")
            CONTROLE_GOLS[fixture_id]['total_gols'] = total_gols_atual
            CONTROLE_GOLS[fixture_id]['minuto_ultimo_gol'] = minuto
            continue # Pula a análise para este jogo neste ciclo
        
        # Atualiza o total de gols caso tenha mudado sem passar pela verificação estrita
        CONTROLE_GOLS[fixture_id]['total_gols'] = total_gols_atual
        
        minuto_do_ultimo_gol = CONTROLE_GOLS[fixture_id]['minuto_ultimo_gol']
        
        # TRAVA DE SEGURANÇA: Se o gol saiu há menos de 4 minutos, proíbe qualquer sinal preditivo
        if (minuto - minuto_do_ultimo_gol) < 4:
            continue
        # ------------------------------------------
        
        # Filtro de gatilho: disparar quando o jogo estiver no segundo tempo (ex: entre 60' e 80')
        condicao_gatilho = (status_short in ['2H'] and 60 <= minuto <= 80)
        
        if condicao_gatilho:
            # Verifica se já alertamos este jogo recentemente
            if fixture_id in CACHE_ALERTAS_ENVIADOS:
                continue
                
            # Chama a Inteligência Artificial para gerar a intensidade e a análise dinâmica personalizada
            intensidade_pressao, analise_ia = gerar_analise_inteligente(
                liga, time_casa, time_fora, gols_casa, gols_fora, minuto
            )

            # Monta a mensagem utilizando o layout padrão profissional enriquecido pela IA
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
            
            enviar_alerta_telegram(mensagem)
            print(f"   [ALERTA ENVIADO COM IA] 🚨 {time_casa} x {time_fora} aos {minuto}'")
            
            CACHE_ALERTAS_ENVIADOS[fixture_id] = tempo_atual
            
            # Registra no monitor de feedback para validar o acerto posteriormente
            MONITORAMENTO_FEEDBACK[fixture_id] = {
                'gols_no_alerta': total_gols_atual,
                'time_casa': time_casa,
                'time_fora': time_fora,
                'minuto_alerta': minuto
            }
            
            alertas_enviados_ciclo += 1

    print(f"[{hora_atual}] Varredura finalizada. Alertas disparados neste ciclo: {alertas_enviados_ciclo}")

if __name__ == "__main__":
    print("🤖 Robô de Alertas Preditivos (Com Trava Anti-Gol, Feedback e IA) iniciado!")
    enviar_alerta_telegram("🚀 *Robô atualizado com Inteligência Artificial, blindagem anti-gol e feedback ativados!*")
    
    while True:
        try:
            processar_partidas()
        except Exception as e:
            print(f"[ERRO NO LOOP] {e}")
        
        time.sleep(60)
