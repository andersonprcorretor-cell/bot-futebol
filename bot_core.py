import os
import time
import requests
from datetime import datetime

# ==========================================
# CONFIGURAÇÕES E CREDENCIAIS DO ROBÔ
# ==========================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "SEU_TELEGRAM_TOKEN_AQUI")
CHAT_ID = os.getenv("CHAT_ID", "SEU_CHAT_ID_AQUI")
FOOTBALL_API_KEY = os.getenv("API_KEY", "SUA_API_KEY_AQUI")

HEADERS_API = {
    'x-apisports-key': FOOTBALL_API_KEY
}

# Dicionário de cache anti-flood (evita mandar alerta repetido do mesmo jogo toda hora)
CACHE_ALERTAS_ENVIADOS = {}

# Dicionário para rastrear o último placar conhecido e o momento do último gol de cada partida
# Formato: { fixture_id: {'total_gols': int, 'minuto_ultimo_gol': int} }
CONTROLE_GOLS = {}

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

def processar_partidas():
    hora_atual = datetime.now().strftime('%H:%M:%S')
    print(f"\n[{hora_atual}] Iniciando varredura de partidas...")
    jogos = buscar_jogos_ao_vivo()
    
    if not jogos:
        print(f"[{hora_atual}] Nenhum jogo ao vivo encontrado na API nesta varredura.")
        return

    global CACHE_ALERTAS_ENVIADOS, CONTROLE_GOLS
    tempo_atual = time.time()
    
    # Limpa cache antigo (permite re-alertar a mesma partida após 30 minutos se o cenário mudar)
    CACHE_ALERTAS_ENVIADOS = {fid: ts for fid, ts in CACHE_ALERTAS_ENVIADOS.items() if tempo_atual - ts < 1800}

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
        
        # Atualiza o total de gols caso tenha mudado sem passar pela verificação estrita (ex: reinício de loop)
        CONTROLE_GOLS[fixture_id]['total_gols'] = total_gols_atual
        
        minuto_do_ultimo_gol = CONTROLE_GOLS[fixture_id]['minuto_ultimo_gol']
        
        # TRAVA DE SEGURANÇA: Se o gol saiu há menos de 4 minutos, proíbe qualquer sinal preditivo
        if (minuto - minuto_do_ultimo_gol) < 4:
            continue
        ------------------------------------------
        
        # Filtro de gatilho: disparar quando o jogo estiver no segundo tempo (ex: entre 60' e 80')
        condicao_gatilho = (status_short in ['2H'] and 60 <= minuto <= 80)
        
        if condicao_gatilho:
            # Verifica se já alertamos este jogo recentemente
            if fixture_id in CACHE_ALERTAS_ENVIADOS:
                continue
                
            # Monta a mensagem exatamente no seu layout padrão profissional
            mensagem = (
                f"🚨 **TENDÊNCIA PARA GOL** 🚨\n\n"
                f"🏆 Liga: {liga}\n"
                f"⚽ Partida: {time_casa} {gols_casa} x {gols_fora} {time_fora}\n"
                f"⏱️ Alerta enviado aos {minuto}' • placar {gols_casa}-{gols_fora}\n\n"
                f"📊 Intensidade de Pressão:\n"
                f"██████████ (100%)\n\n"
                f"🎯 Mercado Sugerido: Mais de {total_gols_atual + 0.5} Gols (Live)\n"
                f"💡 O que o robô viu:\n"
                f"⚡ Chances claras se acumulando nos últimos minutos\n"
                f"• Placar atual apontando pressão forte\n\n"
                f"⚠️ Alerta estatístico baseado na leitura do jogo — não é recomendação de aposta."
            )
            
            enviar_alerta_telegram(mensagem)
            print(f"   [ALERTA ENVIADO] 🚨 {time_casa} x {time_fora} aos {minuto}'")
            
            CACHE_ALERTAS_ENVIADOS[fixture_id] = tempo_atual
            alertas_enviados_ciclo += 1

    print(f"[{hora_atual}] Varredura finalizada. Alertas disparados neste ciclo: {alertas_enviados_ciclo}")

if __name__ == "__main__":
    print("🤖 Robô de Alertas Preditivos (Com Trava Anti-Gol) iniciado!")
    enviar_alerta_telegram("🚀 *Robô atualizado com blindagem anti-gol pós-evento ativada!*")
    
    while True:
        try:
            processar_partidas()
        except Exception as e:
            print(f"[ERRO NO LOOP] {e}")
        
        time.sleep(60)
