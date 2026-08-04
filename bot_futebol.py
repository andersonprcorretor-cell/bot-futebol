import requests
from datetime import datetime, timedelta

API_KEY = "996420a90647414f900fdc57ac9ab3a7"
BASE_URL = "https://api.football-data.org/v4/matches"

def buscar_proximos_jogos():
    headers = {"X-Auth-Token": API_KEY}
    
    # Pega de hoje até os próximos 7 dias para garantir que encontre jogos no plano gratuito
    hoje = datetime.now().strftime("%Y-%m-%d")
    futuro = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    params = {
        "dateFrom": hoje,
        "dateTo": futuro
    }
    
    print(f"Buscando partidas de {hoje} até {futuro}...")
    response = requests.get(BASE_URL, headers=headers, params=params)
    
    if response.status_code != 200:
        print(f"Erro na requisição: {response.status_code}")
        print("Confira se a sua chave da API está correta.")
        return
    
    data = response.json()
    matches = data.get("matches", [])
    
    if not matches:
        print("Nenhuma partida encontrada no período.")
        return

    print(f"\n=== {len(matches)} PARTIDAS ENCONTRADAS ===\n")
    
    for match in matches[:10]: # Mostra os 10 primeiros para não poluir o terminal
        home_team = match["homeTeam"]["name"]
        away_team = match["awayTeam"]["name"]
        competition = match["competition"]["name"]
        match_date = match["utcDate"].split("T")[0]
        
        # Simulação de probabilidade básica para orientar apostas
        prob_home = 48.0
        prob_draw = 26.0
        prob_away = 26.0
        
        print(f"🏆 [{competition}] - Data: {match_date}")
        print(f"⚽ {home_team} vs {away_team}")
        print(f"📊 Probabilidades: Casa {prob_home}% | Empate {prob_draw}% | Fora {prob_away}%")
        print("-" * 50)

if __name__ == "__main__":
    buscar_proximos_jogos()