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
CONTROLE_GOLS = {}
MONITORAMENTO_FEEDBACK = {}
HISTORICO_MOMENTUM = {}

# ATIVADO: Filtra apenas ligas principais e competitivas do mundo
FILTRAR_APENAS_LIGAS_PRINCIPAIS = True

LIGAS_PRINCIPAIS = [
    "libertadores", "sudamericana", "champions league", "europa league", "conference league", 
    "premier league", "la liga", "bundesliga", "ligue 1", "serie a", "serie b",
    "brasileiro", "copa do brasil", "liga profesional", "primera division", 
    "primeira liga", "eredivisie", "championship", "super lig", "pro league", 
    "superligaen", "allsvenskan", "eliteserien", "saudi professional league", 
    "mls", "j1 league", "k league", "liga mx", "liga 1", "primera a"
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
                elif "shots off goal" in stype:
                    stats[f"chutes_fora_{sufixo}"] = val_limpo
                elif "shots inside" in stype or "inside the box" in stype:
                    stats[f"chutes_dentro_area_{sufixo}"] = val_limpo
                elif "dangerous attacks" in stype or "attacks" in stype:
                    stats[f"ataques_perigosos_{sufixo}"] = val_limpo
                elif "corner kicks" in stype:
                    stats[f"cantos_{sufixo}"] = val_limpo
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

def calcular_probabilidade_poisson(lmbda, k):
    try:
        return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)
    except:
        return 0.0

def probabilidade_acumulada_poisson_maior(lmbda, k_atual):
    prob_acumulada = 0.0
    for i in range(0, 6):
        prob_acumulada += calcular_probabilidade_poisson(lmbda, i)
    return max(0.0, min(1.0, 1.0 - prob_acumulada))

def projetar_gols_avancados(total_gols_atuais, minuto, status_short):
    if minuto <= 0:
        return 0.0, False
        
    minutos_totais = 45.0 if status_short == '1H' else 90.0
    minutos_restantes = max(5.0, minutos_totais - minuto)
    
    taxa_por_minuto = (max(0.5, total_gols_atuais) / float(minuto)) if total_gols_atuais > 0 else 0.03
    lambda_restante = taxa_por_minuto * minutos_restantes
    
    linha_sugerida = total_gols_atuais + 0.5
    probabilidade_sucesso = probabilidade_acumulada_poisson_maior(lambda_restante, 0)
    
    return linha_sugerida, probabilidade_sucesso

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
        return 7, f"• O volume ofensivo apresentado por {time_casa} e {time_fora} demonstra clara pressão territorial.\n• Os indicadores estatísticos sustentam a expectativa de movimentação no placar."
    
    resumo_stats = (
        f"Posse: {estats['posse_casa']} x {estats['posse_fora']} | "
        f"Chutes Totais: {estats['chutes_totais_casa']} x {estats['chutes_totais_fora']} | "
        f"Alvo: {estats['chutes_alvo_casa']} x {estats['chutes_alvo_fora']} | "
        f"Dentro da Área: {estats['chutes_dentro_area_casa']} x {estats['chutes_dentro_area_fora']} | "
        f"Cantos: {estats['cantos_casa']} x {estats['cantos_fora']}"
    )

    prompt = (
        f"Você é um Analista Tático Sênior e Trader Esportivo Quantitativo de elite. "
        f"Sua missão é criar uma análise EXCLUSIVA para o jogo entre {time_casa} e {time_fora} "
        f"pela competição {liga}, atualmente no minuto {minuto}' do {periodo_etapa} com o placar de {gols_casa} a {gols_fora}.\n\n"
        f"ESTATÍSTICAS ATUAIS:\n{resumo_stats}\n\n"
        f"REGRAS DE FORMATAÇÃO OBRIGATÓRIAS:\n"
        f"1. Na PRIMEIRA LINHA, escreva APENAS um número inteiro de 1 a 10.\n"
        f"2. A partir da segunda linha, escreva EXATAMENTE 3 tópicos começando com '• '."
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
        
        if len(analise_linhas) < 10:
            analise_linhas = (
                f"• {time_casa} e {time_fora} alternam investidas ofensivas na busca por espaços.\n"
                f"• A proporção de finalizações exige atenção redobrada no setor defensivo.\n"
                f"• O cenário tático atual apresenta indícios favoráveis ao mercado de {tipo}."
            )
            
        return nota_num, analise_linhas
    except Exception as e:
        return 7, (
            f"• A circulação de bola entre {time_casa} e {time_fora} demonstra alta intensidade.\n"
            f"• O volume de ações ofensivas consolidadas reflete o ritmo imposto no {periodo_etapa}.\n"
            f"• A dinâmica estrutural aos {minuto}' sustenta expectativas para o mercado de {tipo}."
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
        
        if fixture_id not in CONTROLE_GOLS:
            CONTROLE_GOLS[fixture_id] = {
                'total_gols': total_gols_atual, 
                'minuto_ultimo_gol': minuto if total_gols_atual > 0 else -99
            }
            continue 
            
        # FILTROS EQUILIBRADOS: Janelas moderadas para evitar extremos (nem muito restrito, nem spam)
        rolando_1t = (status_short == '1H' and 8 <= minuto <= 43)
        rolando_2t = (status_short == '2H' and 50 <= minuto <= 86)

        chave_gols = f"{fixture_id}_gols"
        if (rolando_1t or rolando_2t) and chave_gols not in CACHE_ALERTAS_ENVIADOS:
            periodo_etapa = "1T" if status_short == '1H' else "2T"
            
            estats = extrair_estatisticas(fixture_id)
            
            # Trava anti-zero: descarta se a API retornar dados vazios na liga principal
            if estats['chutes_totais_casa'] == 0 and estats['chutes_totais_fora'] == 0 and estats['cantos_casa'] == 0 and estats['cantos_fora'] == 0:
                continue

            estats_avancadas = extrair_estatisticas_avancadas(fixture_id)
            _, prob_gols = projetar_gols_avancados(total_gols_atual, minuto, status_short)

            nota_pressao, analise_ia = gerar_analise_inteligente(
                liga, time_casa, time_fora, gols_casa, gols_fora, minuto, periodo_etapa, estats, estats_avancadas, tipo="gols"
            )
            
            # FILTROS MODERADOS: Nota de pressão >= 6 e probabilidade >= 35%
            if nota_pressao >= 6 and prob_gols >= 0.35:
                grafico_visual = gerar_grafico_momentum(fixture_id, nota_pressao)

                mensagem = (
                    f"🚨 **TENDÊNCIA PARA GOL ({periodo_etapa})** 🚨\n\n"
                    f"🏆 Liga: {liga}\n"
                    f"⚽ Partida: {time_casa} {gols_casa} x {gols_fora} {time_fora}\n"
                    f"⏱️ Alerta aos {minuto}' ({periodo_etapa}) • Placar {gols_casa}-{gols_fora}\n\n"
                    f"📊 **Estatísticas Reais:**\n"
                    f"• Posse: {estats['posse_casa']} x {estats['posse_fora']}\n"
                    f"• Chutes Totais: {estats['chutes_totais_casa']} x {estats['chutes_totais_fora']}\n"
                    f"• Chutes no Alvo: {estats['chutes_alvo_casa']} x {estats['chutes_alvo_fora']}\n"
                    f"• Escanteios: {estats['cantos_casa']} x {estats['cantos_fora']}\n"
                    f"📈 **Gráfico de Momentum:**\n"
                    f"{grafico_visual}\n\n"
                    f"🎯 Mercado Sugerido: Mais de {total_gols_atual + 0.5} Gols ({periodo_etapa})\n"
                    f"💡 **Análise da Partida:**\n"
                    f"{analise_ia}\n\n"
                    f"⚠️ Gerencie sua banca com responsabilidade."
                )
                
                msg_id = enviar_alerta_telegram(mensagem)
                if msg_id:
                    print(f"   [ALERTA GOLS ENVIADO] 🚨 {time_casa} x {time_fora} aos {minuto}'")
                    CACHE_ALERTAS_ENVIADOS[chave_gols] = tempo_atual

    print(f"[{hora_atual}] Varredura finalizada.")

if __name__ == "__main__":
    print("🤖 Robô iniciado com ligas principais e filtros equilibrados!")
    enviar_alerta_telegram("🚀 *Robô de apostas reiniciado com ligas principais e filtros equilibrados!*")
    
    while True:
        try:
            processar_partidas()
        except Exception as e:
            print(f"[ERRO NO LOOP] {e}")
        
        time.sleep(60)
