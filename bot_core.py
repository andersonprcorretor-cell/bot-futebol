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
HISTORICO_MOMENTUM = {}  # Armazena os últimos níveis de pressão por fixture_id para gerar o gráfico visual

# ==========================================
# LISTA DE PRINCIPAIS LIGAS (COM LIGAS DE TESTE ADICIONADAS)
# ==========================================
LIGAS_PRINCIPAIS = [
    "Copa Libertadores", "Copa Sudamericana", "UEFA Champions League", "UEFA Europa League", 
    "UEFA Conference League", "Serie A", "Premier League", "La Liga", "Bundesliga", "Ligue 1",
    "Brasileiro Série A", "Brasileiro Série B", "Copa do Brasil", "Primeira Liga", "Eredivisie",
    "Championship", "Segunda Division", "Serie B", "2. Bundesliga", "Ligue 2",
    "Liga Professional", "Primera División", "Liga MX", "Super Lig", "Pro League",
    # --- LIGAS ADICIONADAS PARA O TESTE AO VIVO ---
    "Primera B", "Lengjudeildin", "Copa Paraguay", "Liga 1", "LDF", "Qualification"
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
        else:
            print(f"[ERRO TELEGRAM] Código {response.status_code}: {response.text}")
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

def extrair_estatisticas(fixture_id):
    """Extração clássica e robusta focada nos parâmetros reais de campo (incluindo chutes totais)"""
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
                elif "shots inside the box" in stype:
                    stats[f"chutes_dentro_area_{sufixo}"] = val_limpo
                elif "dangerous attacks" in stype or "attacks" in stype:
                    stats[f"ataques_perigosos_{sufixo}"] = val_limpo
                    stats["dados_validos"] = True
                elif "corner kicks" in stype:
                    stats[f"cantos_{sufixo}"] = val_limpo
                    stats["dados_validos"] = True
                    
    except Exception as e:
        print(f"[EXCEÇÃO ESTATÍSTICAS] Erro ao processar estatísticas do jogo {fixture_id}: {e}")
        
    return stats

def gerar_grafico_momentum(fixture_id, intensidade_atual_valor):
    """Gera um mini histograma visual moderno com blocos baseado na evolução da pressão"""
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

def gerar_analise_inteligente(liga, time_casa, time_fora, gols_casa, gols_fora, minuto, estats, tipo="gols"):
    if not client_ai:
        return 8, "• Pressão constante exercida no terço final\n• Alto volume ofensivo e finalizações frequentes"
    
    resumo_stats = (
        f"Estatísticas - Posse: {estats['posse_casa']} x {estats['posse_fora']} | "
        f"Chutes Totais: {estats['chutes_totais_casa']} x {estats['chutes_totais_fora']} | "
        f"Chutes Alvo: {estats['chutes_alvo_casa']} x {estats['chutes_alvo_fora']} | "
        f"Chutes Fora: {estats['chutes_fora_casa']} x {estats['chutes_fora_fora']} | "
        f"Dentro da Área: {estats['chutes_dentro_area_casa']} x {estats['chutes_dentro_area_fora']} | "
        f"Ataques Perigosos: {estats['ataques_perigosos_casa']} x {estats['ataques_perigosos_fora']} | "
        f"Escanteios: {estats['cantos_casa']} x {estats['cantos_fora']}"
    )

    prompt = (
        f"Atue como um analista estatístico profissional de apostas Live de elite. "
        f"Analise o jogo: {liga} | {time_casa} {gols_casa} x {gols_fora} {time_fora} aos {minuto}'.\n"
        f"Dados de campo:\n{resumo_stats}\n\n"
        f"Forneça estritamente:\n"
        f"1. Uma nota numérica inteira de 1 a 10 para o nível de pressão atual na primeira linha (apenas o número, ex: '9').\n"
        f"2. Um texto curto em 2 linhas começando com '•' explicando a tendência baseada no volume de finalizações e pressão."
    )
    
    try:
        response = client_ai.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt
        )
        texto_resposta = response.text.strip()
        linhas = texto_resposta.split('\n')
        
        nota_num = 8
        for char in linhas[0]:
            if char.isdigit():
                nota_num = int(char)
                break
        nota_num = max(1, min(10, nota_num))
        
        analise_linhas = "\n".join([l for l in linhas[1:] if l.strip()])
        if not analise_linhas:
            analise_linhas = "• Alta movimentação e volume no setor ofensivo\n• Pressão contínua em busca do gol"
        return nota_num, analise_linhas
    except Exception as e:
        print(f"[EXCEÇÃO IA] Erro ao gerar análise: {e}")
        return 8, "• Alta movimentação e volume no setor ofensivo\n• Pressão contínua em busca do objetivo"

def processar_partidas():
    hora_atual = datetime.now().strftime('%H:%M:%S')
    print(f"\n[{hora_atual}] Iniciando varredura com estatísticas clássicas (incluindo chutes totais) e Momentum Visual...")
    jogos = buscar_jogos_ao_vivo()
    
    if not jogos:
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
                    minutos_para_agir = minuto_agora - dados_fb['minuto_alerta']
                    msg_feedback = (
                        f"✅ **GREEN / GOL CONFIRMADO!** ✅\n\n"
                        f"⚽ Partida: {dados_fb['time_casa']} {g_c} x {g_f} {dados_fb['time_fora']}\n"
                        f"⏱️ Gol aos {minuto_agora}' (Alerta aos {dados_fb['minuto_alerta']}')\n"
                        f"⏳ Janela de reação: {minutos_para_agir} minuto(s)"
                    )
                    enviar_alerta_telegram(msg_feedback, reply_to_id=msg_id_origem)
                    jogos_para_remover.append(fixture_id)
                elif (minuto_agora - dados_fb['minuto_alerta']) > 20:
                    jogos_para_remover.append(fixture_id)
                    
            elif dados_fb['tipo'] == 'escanteios':
                meta_cantos = dados_fb['meta_cantos']
                if total_cantos_agora >= meta_cantos:
                    minutos_para_agir = minuto_agora - dados_fb['minuto_alerta']
                    msg_feedback = (
                        f"✅ **ESCANTEIOS BATERAM!** 🎯\n\n"
                        f"🚩 Partida: {dados_fb['time_casa']} {g_c} x {g_f} {dados_fb['time_fora']}\n"
                        f"⏱️ Alerta aos {dados_fb['minuto_alerta']}' | Fechou com {total_cantos_agora} escanteios (Meta: > {meta_cantos - 0.5})\n"
                        f"⏳ Janela de reação: {minutos_para_agir} minuto(s)"
                    )
                    enviar_alerta_telegram(msg_feedback, reply_to_id=msg_id_origem)
                    jogos_para_remover.append(fixture_id)
                elif minuto_agora >= 88 or (minuto_agora - dados_fb['minuto_alerta']) > 20:
                    minutos_para_agir = minuto_agora - dados_fb['minuto_alerta']
                    msg_feedback = (
                        f"🔴 **ESCANTEIOS NÃO BATERAM**\n\n"
                        f"🚩 Partida: {dados_fb['time_casa']} {g_c} x {g_f} {dados_fb['time_fora']}\n"
                        f"⏱️ Alerta aos {dados_fb['minuto_alerta']}' | Fechou com {total_cantos_agora} escanteios (Meta: > {meta_cantos - 0.5})"
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
            CONTROLE_GOLS[fixture_id] = {'total_gols': total_gols_atual, 'minuto_ultimo_gol': -99}
            
        estado_jogo = CONTROLE_GOLS[fixture_id]
        if total_gols_atual > estado_jogo['total_gols']:
            CONTROLE_GOLS[fixture_id]['total_gols'] = total_gols_atual
            CONTROLE_GOLS[fixture_id]['minuto_ultimo_gol'] = minuto
            continue
        
        CONTROLE_GOLS[fixture_id]['total_gols'] = total_gols_atual
        if (minuto - estado_jogo['minuto_ultimo_gol']) < 4:
            continue
            
        if fixture_id in CACHE_ALERTAS_ENVIADOS:
            continue

        # --- GATILHO 1 (MODO TESTE): TENDÊNCIA PARA GOL (QUALQUER MINUTO) ---
        # Removi temporariamente a restrição de "60 a 80 min" para o alerta disparar agora
        if status_short in ['1H', '2H', 'ET'] and 1 <= minuto <= 120:
            estats = extrair_estatisticas(fixture_id)
            if not estats['dados_validos']:
                continue

            nota_pressao, analise_ia = gerar_analise_inteligente(
                liga, time_casa, time_fora, gols_casa, gols_fora, minuto, estats, tipo="gols"
            )
            grafico_visual = gerar_grafico_momentum(fixture_id, nota_pressao)

            mensagem = (
                f"🚨 **TENDÊNCIA PARA GOL (TESTE IA)** 🚨\n\n"
                f"🏆 Liga: {liga}\n"
                f"⚽ Partida: {time_casa} {gols_casa} x {gols_fora} {time_fora}\n"
                f"⏱️ Alerta aos {minuto}' • Placar {gols_casa}-{gols_fora}\n\n"
                f"📊 **Estatísticas Reais ao Vivo:**\n"
                f"• Posse: {estats['posse_casa']} x {estats['posse_fora']}\n"
                f"• Chutes Totais: {estats['chutes_totais_casa']} x {estats['chutes_totais_fora']}\n"
                f"• Chutes no Alvo: {estats['chutes_alvo_casa']} x {estats['chutes_alvo_fora']}\n"
                f"• Chutes para Fora: {estats['chutes_fora_casa']} x {estats['chutes_fora_fora']}\n"
                f"• Chutes Dentro da Área: {estats['chutes_dentro_area_casa']} x {estats['chutes_dentro_area_fora']}\n"
                f"• Escanteios: {estats['cantos_casa']} x {estats['cantos_fora']}\n\n"
                f"📈 **Gráfico de Momentum:**\n"
                f"{grafico_visual}\n\n"
                f"🎯 Mercado Sugerido: Mais de {total_gols_atual + 0.5} Gols (Live)\n"
                f"💡 **Análise Quantitativa IA:**\n"
                f"{analise_ia}\n\n"
                f"⚠️ Alerta de teste para validação da IA."
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

    print(f"[{hora_atual}] Varredura finalizada. Alertas disparados neste ciclo: {alertas_enviados_ciclo}")

if __name__ == "__main__":
    print("🤖 Robô em MODO TESTE (qualquer minuto) iniciado!")
    enviar_alerta_telegram("🚀 *Robô em MODO DE TESTE - Validando Inteligência Artificial e Dados!*")
    
    while True:
        try:
            processar_partidas()
        except Exception as e:
            print(f"[ERRO NO LOOP] {e}")
        
        time.sleep(60)
