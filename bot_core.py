import os
import time
import requests
from google import genai
from google.genai import types

# Configurações de API (Variáveis de Ambiente do Railway)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Inicializa cliente Gemini de forma segura
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

def enviar_telegram(mensagem):
    """Envia mensagem para o Telegram com tratamento de timeout seguro."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Credenciais do Telegram não configuradas.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code != 200:
            print(f"⚠️ Erro ao enviar Telegram: {response.text}")
    except requests.exceptions.Timeout:
        print("⚠️ [EXCEÇÃO TELEGRAM] Timeout de 15 segundos atingido. O ciclo continuará normalmente.")
    except Exception as e:
        print(f"⚠️ [EXCEÇÃO TELEGRAM] {e}")

def extrair_estatisticas(stats_api):
    """Extrai e padroniza de forma segura todas as estatísticas da API de futebol."""
    casa = {}
    fora = {}
    
    try:
        # Mapeamento robusto dos dados da API
        for team_stats in stats_api:
            team_side = team_stats.get('team', {}).get('id') # ou 'home'/'away' dependendo da API
            # Identificando o lado (ajuste conforme a estrutura da sua API de futebol)
            is_home = team_stats.get('side') == 'home' or team_stats.get('type') == 'home'
            
            stats_dict = {}
            for stat in team_stats.get('statistics', []):
                tipo = stat.get('type', '').lower()
                valor = stat.get('value', 0)
                if valor is None:
                    valor = 0
                
                if 'ball possession' in tipo:
                    stats_dict['posse'] = str(valor) if '%' in str(valor) else f"{valor}%"
                elif 'total shots' in tipo:
                    stats_dict['chutes_totais'] = valor
                elif 'shots on goal' in tipo:
                    stats_dict['chutes_no_alvo'] = valor
                elif 'shots off goal' in tipo or 'shots off target' in tipo:
                    stats_dict['chutes_fora'] = valor
                elif 'shots inside the box' in tipo:
                    stats_dict['chutes_dentro_area'] = valor
                elif 'blocked shots' in tipo:
                    stats_dict['chutes_bloqueados'] = valor
                elif 'corner kicks' in tipo:
                    stats_dict['escanteios'] = valor
                elif 'red cards' in tipo:
                    stats_dict['vermelhos'] = valor

            if is_home or team_stats.get('home_team', False):
                casa = stats_dict
            else:
                fora = stats_dict
    except Exception as e:
        print(f"⚠️ Erro ao processar estatísticas: {e}")

    # Fallback seguro para evitar chaves vazias
    defaults = {
        'posse': '50%', 'chutes_totais': 0, 'chutes_no_alvo': 0,
        'chutes_fora': 0, 'chutes_dentro_area': 0, 'chutes_bloqueados': 0,
        'escanteios': 0, 'vermelhos': 0
    }
    for k, v in defaults.items():
        if k not in casa: casa[k] = v
        if k not in fora: fora[k] = v

    return casa, fora

def formatar_mensagem_alerta(partida, casa, fora, analise_ia=""):
    """Formata o alerta completo para o Telegram incluindo todas as estatísticas detalhadas."""
    texto = (
        f"🚨 **OPORTUNIDADE DETECTADA** 🚨\n\n"
        f"🏆 **{partida.get('liga', 'Partida')}**\n"
        f"⚔️ {partida.get('time_casa', 'Casa')} {partida.get('placar_casa', 0)} x {partida.get('placar_fora', 0)} {partida.get('time_fora', 'Fora')}\n"
        f"⏱️ **Minuto:** {partida.get('minuto', 0)}'\n\n"
        f"📊 **Estatísticas Completas:**\n"
        f"• **Posse:** {casa.get('posse')} x {fora.get('posse')}\n"
        f"• **Chutes Totais:** {casa.get('chutes_totais')} x {fora.get('chutes_totais')}\n"
        f"• **No Alvo:** {casa.get('chutes_no_alvo')} x {fora.get('chutes_no_alvo')}\n"
        f"• **Para Fora:** {casa.get('chutes_fora')} x {fora.get('chutes_fora')}\n"
        f"• **Dentro da Área:** {casa.get('chutes_dentro_area')} x {fora.get('chutes_dentro_area')}\n"
        f"• **Bloqueados:** {casa.get('chutes_bloqueados')} x {fora.get('chutes_bloqueados')}\n"
        f"• **Escanteios:** {casa.get('escanteios')} x {fora.get('escanteios')}\n"
        f"• **Vermelhos:** {casa.get('vermelhos')} x {fora.get('vermelhos')}\n"
    )
    
    if analise_ia:
        texto += f"\n🤖 **Análise IA:**\n{analise_ia}"
        
    return texto

def analisar_partida_com_ia(dados_partida):
    """Executa a análise de IA de forma segura sem quebrar o fluxo."""
    if not client:
        return "Análise de IA desativada (Sem chave configurada)."
    
    try:
        prompt = f"Analise esta partida de futebol com base nestes dados: {dados_partida}. Dê uma nota de 0 a 10 e um breve parecer."
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"⚠️ Erro na chamada da IA: {e}")
        return "Análise indisponível no momento."

def ciclo_principal():
    """Loop principal de varredura das partidas."""
    print("🤖 Robô iniciado e rodando varreduras...")
    
    # Exemplo simulado do loop contínuo que já está no seu Railway
    while True:
        try:
            # Aqui entra a sua chamada à API de Futebol para buscar jogos ao vivo
            # Exemplo de lógica de filtro de partidas sem ação já implementada:
            partidas_ao_vivo = [] # Substituir pela chamada real da API
            
            for partida in partidas_ao_vivo:
                casa, fora = extrair_estatisticas(partida.get('statistics', []))
                
                # Filtro de partidas sem ação (ignora se tudo estiver zerado)
                total_movimento = (
                    casa.get('chutes_totais', 0) + fora.get('chutes_totais', 0) +
                    casa.get('escanteios', 0) + fora.get('escanteios', 0)
                )
                
                if total_movimento == 0:
                    print(f"[{partida.get('id', 'JOGO')}] [IGNORADO] Partida sem ações relevantes.")
                    continue
                
                # Se passou pelo filtro, processa alerta e IA
                analise = analisar_partida_com_ia(partida)
                mensagem = formatar_mensagem_alerta(partida, casa, fora, analise)
                enviar_telegram(mensagem)
                
            print("🔄 Varredura finalizada. Aguardando próximo ciclo...")
        except Exception as e:
            print(f"⚠️ Erro crítico no ciclo principal: {e}")
            
        time.sleep(60) # Intervalo entre as varreduras

if __name__ == "__main__":
    ciclo_principal()
