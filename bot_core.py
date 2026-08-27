import os
import time
import requests
import re
import math
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
CACHE_HALFTIME_ENVIADOS = {}
CONTROLE_GOLS = {}
HISTORICO_MOMENTUM = {}

FILTRAR_APENAS_LIGAS_PRINCIPAIS = True

LIGAS_PRINCIPAIS = [
    "libertadores", "sudamericana", "champions league", "europa league", "conference league", 
    "premier league", "la liga", "bundesliga", "ligue 1", "serie a", "serie b",
    "brasileiro", "copa do brasil", "liga profesional", "primera division", 
    "primeira liga", "eredivisie", "championship", "super lig", "pro league", 
    "superligaen", "allsvenskan", "eliteserien", "saudi professional league", 
    "mls", "j1 league", "k league", "liga mx", "liga 1", "primera a", "copa uruguay"
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
        response = requests.post(url, json=payload, timeout=15)
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
            return response.json().get('response', [])
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

def buscar_eventos_partida(fixture_id):
    url = "https://v3.football.api-sports.io/fixtures/events"
    params = {"fixture": int(fixture_id)}
    try:
        response = requests.get(url, headers=HEADERS_API, params=params, timeout=10)
        if response.status_code == 200:
            return response.json().get('response', [])
    except Exception as e:
        print(f"[EXCEÇÃO EVENTS API] Erro ao buscar eventos do jogo {fixture_id}: {e}")
    return []

def analisar_eventos_partida(fixture_id, home_id, away_id):
    eventos = buscar_eventos_partida(fixture_id)
    vermelhos_casa = 0
    vermelhos_fora = 0
    try:
        for ev in eventos:
            etype = str(ev.get('type', '')).strip().lower()
            edetail = str(ev.get('detail', '')).strip().lower()
            team_id = ev.get('team', {}).get('id')
            if "card" in etype and ("red" in edetail or "yellow_red" in edetail):
                if team_id == home_id:
                    vermelhos_casa += 1
                elif team_id == away_id:
                    vermelhos_fora += 1
    except Exception as e:
        pass
    return vermelhos_casa, vermelhos_fora

def extrair_estatisticas(fixture_id):
    stats = {
        "posse_casa": "50%", "posse_fora": "50%",
        "chutes_totais_casa": 0, "chutes_totais_fora": 0,
        "chutes_alvo_casa": 0, "chutes_alvo_fora": 0,
        "chutes_fora_casa": 0, "chutes_fora_fora": 0,
        "chutes_dentro_area_casa": 0, "chutes_dentro_area_fora": 0,
        "chutes_bloqueados_casa": 0, "chutes_bloqueados_fora": 0,
        "cantos_casa": 0, "cantos_fora": 0
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
                elif "total shots" in stype:
                    stats[f"chutes_totais_{sufixo}"] = val_limpo
                elif "shots on goal" in stype:
                    stats[f"chutes_alvo_{sufixo}"] = val_limpo
                elif "shots off goal" in stype or "shots off target" in stype:
                    stats[f"chutes_fora_{sufixo}"] = val_limpo
                elif "shots inside the box" in stype:
                    stats[f"chutes_dentro_area_{sufixo}"] = val_limpo
                elif "blocked shots" in stype:
                    stats[f"chutes_bloqueados_{sufixo}"] = val_limpo
                elif "corner kicks" in stype:
                    stats[f"cantos_{sufixo}"] = val_limpo
    except Exception as e:
        print(f"[EXCEÇÃO ESTATÍSTICAS] {e}")
        
    return stats

def projetar_gols_avancados(total_gols_atuais, minuto, status_short, vermelhos_casa=0, vermelhos_fora=0):
    if minuto <= 0:
        return 0.5, 0.40
        
    minutos_totais = 45.0 if status_short == '1H' else 90.0
    minutos_restantes = max(5.0, minutos_totais - minuto)
    
    if total_gols_atuais == 0:
        taxa_por_minuto = max(0.025, minuto / 1800.0)
    else:
        taxa_por_minuto = total_gols_atuais / float(minuto)
        
    if vermelhos_casa > 0 or vermelhos_fora > 0:
        taxa_por_minuto *= 1.25

    lambda_restante = taxa_por_minuto * minutos_restantes
    probabilidade_sucesso = 1.0 - math.exp(-lambda_restante)
    linha_sugerida = total_gols_atuais + 0.5
    
    return linha_sugerida, max(0.15, min(0.95, probabilidade_sucesso))

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

def gerar_analise_inteligente(liga, time_casa, time_fora, gols_casa, gols_fora, minuto, periodo_etapa, estats, vermelhos_casa, vermelhos_fora):
    if not client_ai:
        return 7, (
            f"• **Pressão Territorial:** {time_casa} e {time_fora} mantêm o ritmo acelerado no terço final.\n"
            f"• **Indicador de Chutes:** O volume de finalizações cria uma janela propícia para alteração no placar.\n"
            f"• **Contexto de Jogo:** O cenário aos {minuto}' do {periodo_etapa} sustenta a expectativa de gols."
        )
    
    resumo_stats = (
        f"Posse: {estats['posse_casa']} x {estats['posse_fora']} | "
        f"Chutes Totais: {estats['chutes_totais_casa']} x {estats['chutes_totais_fora']} | "
        f"Alvo: {estats['chutes_alvo_casa']} x {estats['chutes_alvo_fora']} | "
        f"Fora: {estats['chutes_fora_casa']} x {estats['chutes_fora_fora']} | "
        f"Dentro da Área: {estats['chutes_dentro_area_casa']} x {estats['chutes_dentro_area_fora']} | "
        f"Bloqueados: {estats['chutes_bloqueados_casa']} x {estats['chutes_bloqueados_fora']} | "
        f"Cantos: {estats['cantos_casa']} x {estats['cantos_fora']}"
    )

    aviso_cartoes = ""
    if vermelhos_casa > 0 or vermelhos_fora > 0:
        aviso_cartoes = f"\n⚠️ ATENÇÃO: Há expulsões ativas! Vermelhos para {time_casa}: {vermelhos_casa} | Vermelhos para {time_fora}: {vermelhos_fora}."

    prompt = (
        f"Você é um Trader Esportivo Quantitativo de elite e Analista Tático Sênior de Futebol.\n"
        f"Escreva uma análise PROFUNDA, ESPECÍFICA e TÉCNICA para a partida entre {time_casa} e {time_fora} ({liga}) aos {minuto}' do {periodo_etapa}, com placar atual de {gols_casa}x{gols_fora}.\n"
        f"{aviso_cartoes}\n\n"
        f"ESTATÍSTICAS DA PARTIDA:\n{resumo_stats}\n\n"
        f"INSTRUÇÕES OBRIGATÓRIAS:\n"
        f"1. Na PRIMEIRA LINHA, retorne APENAS um número inteiro de 1 a 10 representando a nota de pressão/oportunidade.\n"
        f"2. A partir da segunda linha, escreva EXATAMENTE 3 tópicos detalhados no formato exato: '• **[Título Tático Único e Descritivo]:** [Análise aprofundada citando números reais da partida, conversão de chutes, pressão territorial, impacto das expulsões se houver, e a leitura exata do game state para o mercado de gols].'\n"
        f"3. NUNCA utilize frases genéricas ou padrões repetitivos. Cada tópico deve ser rico em detalhes táticos baseados estritamente nos dados fornecidos."
    )
    
    try:
        response = client_ai.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt
        )
        texto_resposta = response.text.strip()
        linhas = [l.strip() for l in texto_resposta.split('\n') if l.strip()]
        
        nota_num = 7
        indice_inicio_texto = 0
        if linhas:
            match = re.search(r'\d+', linhas[0])
            if match:
                nota_num = int(match.group())
                indice_inicio_texto = 1
                
        nota_num = max(1, min(10, nota_num))
        analise_linhas = "\n".join(linhas[indice_inicio_texto:]).strip()
        
        if len(analise_linhas) < 15:
            raise ValueError("Resposta muito curta da IA")
            
        return nota_num, analise_linhas
    except Exception as e:
        print(f"[ERRO GEMINI] {e}")
        return 7, (
            f"• **Pressão Territorial e Transição:** {time_casa} imprime forte ritmo ofensivo com {estats['chutes_totais_casa']} finalizações contra {estats['chutes_totais_fora']} do {time_fora}.\n"
            f"• **Volume de Finalizações no Alvo:** A proporção de {estats['chutes_alvo_casa']} chutes certos evidencia oportunidades claras no terço final.\n"
            f"• **Leitura de Game State:** O cenário aos {minuto}' do {periodo_etapa} com placar em {gols_casa}x{gols_fora} mantém parâmetros elevados para o mercado de gols."
        )

def gerar_analise_intervalo(liga, time_casa, time_fora, gols_casa, gols_fora, estats, vermelhos_casa, vermelhos_fora):
    if not client_ai:
        return f"• O primeiro tempo encerrou com {time_casa} {gols_casa}x{gols_fora} {time_fora}.\n• Analise as estatísticas acumuladas para definir entradas no segundo tempo."
    
    resumo_stats = (
        f"Posse: {estats['posse_casa']} x {estats['posse_fora']} | "
        f"Chutes Totais: {estats['chutes_totais_casa']} x {estats['chutes_totais_fora']} | "
        f"Alvo: {estats['chutes_alvo_casa']} x {estats['chutes_alvo_fora']} | "
        f"Fora: {estats['chutes_fora_casa']} x {estats['chutes_fora_fora']} | "
        f"Dentro da Área: {estats['chutes_dentro_area_casa']} x {estats['chutes_dentro_area_fora']} | "
        f"Cantos: {estats['cantos_casa']} x {estats['cantos_fora']}"
    )
    aviso_cartoes = f"\n⚠️ Expulsões no 1T -> {time_casa}: {vermelhos_casa} | {time_fora}: {vermelhos_fora}" if (vermelhos_casa > 0 or vermelhos_fora > 0) else ""

    prompt = (
        f"Você é um Trader Esportivo Quantitativo especialista em análises de intervalo (HT). "
        f"Com base nas estatísticas COMPLETAS do 1º tempo de {time_casa} vs {time_fora} ({liga}), com placar parcial de {gols_casa}x{gols_fora}:\n"
        f"{resumo_stats}\n{aviso_cartoes}\n\n"
        f"Escreva exatamente 3 tópicos começando com '• **[Título]:** ' projetando cenários, tendências e sugestões de entradas inteligentes para o 2º tempo, utilizando os dados numéricos do 1T."
    )
    try:
        response = client_ai.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"[ERRO GEMINI HT] {e}")
        return (
            f"• **Volume Ofensivo do 1T:** {time_casa} registrou {estats['chutes_totais_casa']} chutes enquanto o {time_fora} somou {estats['chutes_totais_fora']}.\n"
            f"• **Controle Territorial:** A posse de bola ({estats['posse_casa']} x {estats['posse_fora']}) aponta tendência de ajustes táticos no intervalo.\n"
            f"• **Expectativa para o 2T:** Monitorar os primeiros 15 minutos da etapa final buscando valor em gols ou cantos."
        )

def processar_partidas():
    hora_atual = datetime.now().strftime('%H:%M:%S')
    print(f"\n[{hora_atual}] Varredura completa em tempo real...")
    jogos = buscar_jogos_ao_vivo()
    
    if not jogos:
        print("[AVISO] Nenhum jogo ao vivo retornado pela API neste ciclo.")
        return

    global CACHE_ALERTAS_ENVIADOS, CACHE_HALFTIME_ENVIADOS, CONTROLE_GOLS
    tempo_atual = time.time()
    CACHE_ALERTAS_ENVIADOS = {fid: ts for fid, ts in CACHE_ALERTAS_ENVIADOS.items() if tempo_atual - ts < 1200}
    CACHE_HALFTIME_ENVIADOS = {fid: ts for fid, ts in CACHE_HALFTIME_ENVIADOS.items() if tempo_atual - ts < 7200}

    for jogo in jogos:
        liga = jogo['league']['name']
        
        if not validar_liga_principal(liga):
            continue

        fixture_id = jogo['fixture']['id']
        home_id = jogo['teams']['home']['id']
        away_id = jogo['teams']['away']['id']
        time_casa = jogo['teams']['home']['name']
        time_fora = jogo['teams']['away']['name']
        
        gols_casa = jogo['goals']['home'] if jogo['goals']['home'] is not None else 0
        gols_fora = jogo['goals']['away'] if jogo['goals']['away'] is not None else 0
        total_gols_atual = gols_casa + gols_fora
        
        minuto = jogo['fixture']['status']['elapsed'] or 0
        status_short = jogo['fixture']['status']['short']
        
        print(f"    [MONITORANDO] {liga} | {time_casa} {gols_casa}x{gols_fora} {time_fora} | Minuto: {minuto}' ({status_short})")
        
        if fixture_id not in CONTROLE_GOLS:
            CONTROLE_GOLS[fixture_id] = {
                'total_gols': total_gols_atual, 
                'minuto_ultimo_gol': minuto if total_gols_atual > 0 else -99
            }
            continue 

        # ==========================================
        # PROCESSAMENTO DE INTERVALO (HT)
        # ==========================================
        if status_short == 'HT' and fixture_id not in CACHE_HALFTIME_ENVIADOS:
            estats = extrair_estatisticas(fixture_id)
            vermelhos_casa, vermelhos_fora = analisar_eventos_partida(fixture_id, home_id, away_id)
            
            if not (estats['chutes_totais_casa'] == 0 and estats['chutes_totais_fora'] == 0 and estats['cantos_casa'] == 0 and estats['cantos_fora'] == 0):
                analise_ht = gerar_analise_intervalo(liga, time_casa, time_fora, gols_casa, gols_fora, estats, vermelhos_casa, vermelhos_fora)
                aviso_vermelho_txt = f"\n🟥 **Cartões Vermelhos no 1T:** {time_casa} ({vermelhos_casa}) x {time_fora} ({vermelhos_fora})" if (vermelhos_casa > 0 or vermelhos_fora > 0) else ""

                mensagem_ht = (
                    f"☕ **ANÁLISE DE INTERVALO (HT)** ☕\n\n"
                    f"🏆 Liga: {liga}\n"
                    f"⚽ Partida: {time_casa} {gols_casa} x {gols_fora} {time_fora}\n"
                    f"⏱️ Fim do 1º Tempo (Intervalo)"
                    f"{aviso_vermelho_txt}\n\n"
                    f"📊 **Balanço Estatístico do 1º Tempo:**\n"
                    f"• Posse: {estats['posse_casa']} x {estats['posse_fora']}\n"
                    f"• Chutes Totais: {estats['chutes_totais_casa']} x {estats['chutes_totais_fora']}\n"
                    f"• Chutes no Alvo: {estats['chutes_alvo_casa']} x {estats['chutes_alvo_fora']}\n"
                    f"• Chutes Para Fora: {estats['chutes_fora_casa']} x {estats['chutes_fora_fora']}\n"
                    f"• Dentro da Área: {estats['chutes_dentro_area_casa']} x {estats['chutes_dentro_area_fora']}\n"
                    f"• Chutes Bloqueados: {estats['chutes_bloqueados_casa']} x {estats['chutes_bloqueados_fora']}\n"
                    f"• Escanteios: {estats['cantos_casa']} x {estats['cantos_fora']}\n\n"
                    f"💡 **Projeções e Sugestões para o 2º Tempo:**\n"
                    f"{analise_ht}\n\n"
                    f"⚠️ Planeje suas entradas com cautela para a etapa final."
                )
                
                msg_id = enviar_alerta_telegram(mensagem_ht)
                if msg_id:
                    print(f"    [ALERTA INTERVALO ENVIADO] ☕ {time_casa} x {time_fora} (HT)")
                    CACHE_HALFTIME_ENVIADOS[fixture_id] = tempo_atual

        # ==========================================
        # MONITORAMENTO DE JOGO ROLANDO (COM DIAGNÓSTICO)
        # ==========================================
        rolando_1t = (status_short == '1H' and 8 <= minuto <= 43)
        rolando_2t = (status_short == '2H' and 50 <= minuto <= 86)

        chave_gols = f"{fixture_id}_gols"
        if (rolando_1t or rolando_2t) and chave_gols not in CACHE_ALERTAS_ENVIADOS:
            periodo_etapa = "1T" if status_short == '1H' else "2T"
            
            estats = extrair_estatisticas(fixture_id)
            vermelhos_casa, vermelhos_fora = analisar_eventos_partida(fixture_id, home_id, away_id)
            
            # LOG DE DIAGNÓSTICO: Mostra claramente os valores extraídos da API para cada partida em andamento
            print(f"      [DEBUG STATS] {time_casa} x {time_fora} | Chutes: {estats['chutes_totais_casa']}x{estats['chutes_totais_fora']} | Cantos: {estats['cantos_casa']}x{estats['cantos_fora']}")

            if estats['chutes_totais_casa'] == 0 and estats['chutes_totais_fora'] == 0 and estats['cantos_casa'] == 0 and estats['cantos_fora'] == 0 and vermelhos_casa == 0 and vermelhos_fora == 0:
                print(f"      [IGNORADO] Estatísticas zeradas na API para {time_casa} x {time_fora}")
                continue

            _, prob_gols = projetar_gols_avancados(total_gols_atual, minuto, status_short, vermelhos_casa, vermelhos_fora)
            nota_pressao, analise_ia = gerar_analise_inteligente(
                liga, time_casa, time_fora, gols_casa, gols_fora, minuto, periodo_etapa, estats, vermelhos_casa, vermelhos_fora
            )

            # LOG DE AVALIAÇÃO: Mostra a nota atribuída pela IA e a probabilidade matemática calculada
            print(f"      [AVALIAÇÃO] Nota IA: {nota_pressao}/10 | Prob. Poisson: {prob_gols:.2f}")

            if nota_pressao >= 6 and prob_gols >= 0.35:
                grafico_visual = gerar_grafico_momentum(fixture_id, nota_pressao)
                aviso_vermelho_txt = f"\n🟥 **Cartões Vermelhos:** {time_casa} ({vermelhos_casa}) x {time_fora} ({vermelhos_fora})" if (vermelhos_casa > 0 or vermelhos_fora > 0) else ""

                mensagem = (
                    f"🚨 **TENDÊNCIA PARA GOL ({periodo_etapa})** 🚨\n\n"
                    f"🏆 Liga: {liga}\n"
                    f"⚽ Partida: {time_casa} {gols_casa} x {gols_fora} {time_fora}\n"
                    f"⏱️ Alerta aos {minuto}' ({periodo_etapa}) • Placar {gols_casa}-{gols_fora}"
                    f"{aviso_vermelho_txt}\n\n"
                    f"📊 **Estatísticas Reais:**\n"
                    f"• Posse: {estats['posse_casa']} x {estats['posse_fora']}\n"
                    f"• Chutes Totais: {estats['chutes_totais_casa']} x {estats['chutes_totais_fora']}\n"
                    f"• Chutes no Alvo: {estats['chutes_alvo_casa']} x {estats['chutes_alvo_fora']}\n"
                    f"• Chutes Para Fora: {estats['chutes_fora_casa']} x {estats['chutes_fora_fora']}\n"
                    f"• Dentro da Área: {estats['chutes_dentro_area_casa']} x {estats['chutes_dentro_area_fora']}\n"
                    f"• Chutes Bloqueados: {estats['chutes_bloqueados_casa']} x {estats['chutes_bloqueados_fora']}\n"
                    f"• Escanteios: {estats['cantos_casa']} x {estats['cantos_fora']}\n\n"
                    f"📈 **Gráfico de Momentum:**\n"
                    f"{grafico_visual}\n\n"
                    f"🎯 Mercado Sugerido: Mais de {total_gols_atual + 0.5} Gols ({periodo_etapa})\n"
                    f"💡 **Análise da Partida:**\n"
                    f"{analise_ia}\n\n"
                    f"⚠️ Gerencie sua banca com responsabilidade."
                )
                
                msg_id = enviar_alerta_telegram(mensagem)
                if msg_id:
                    print(f"    [ALERTA GOLS ENVIADO] 🚨 {time_casa} x {time_fora} aos {minuto}'")
                    CACHE_ALERTAS_ENVIADOS[chave_gols] = tempo_atual

    print(f"[{hora_atual}] Varredura finalizada.")

if __name__ == "__main__":
    print("🤖 Robô iniciado com Análise Inteligente Atualizada (Gemini 3.6 Flash)!")
    enviar_alerta_telegram("🚀 *Robô atualizado e conectado com sucesso ao modelo Gemini 3.6 Flash!*")
    
    while True:
        try:
            processar_partidas()
        except Exception as e:
            print(f"[ERRO NO LOOP] {e}")
        
        time.sleep(60)
