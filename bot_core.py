import time
import logging
import requests
from datetime import datetime

# Configuração de logs
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot_execution.log"),
        logging.StreamHandler()
    ]
)

class LiveMatchScanner:
    def __init__(self, telegram_token, chat_id, api_key):
        self.telegram_token = telegram_token
        self.chat_id = chat_id
        self.api_key = api_key
        self.alerted_matches = set()
        self.headers = {"x-apisports-key": self.api_key}

    def fetch_live_fixtures_from_api(self):
        """Busca a lista de partidas ao vivo com tratamento de falhas de rede"""
        url = "https://v3.football.api-sports.io/fixtures"
        querystring = {"live": "all"}

        try:
            response = requests.get(url, headers=self.headers, params=querystring, timeout=15)
            if response.status_code == 200:
                return response.json().get("response", [])
            else:
                logging.error(f"Erro ao buscar partidas ao vivo: {response.status_code}")
                return []
        except requests.exceptions.RequestException as e:
            logging.warning(f"Falha temporária de rede/conexão: {e}. Tentando novamente em breve...")
            return []

    def fetch_match_statistics(self, fixture_id):
        """Busca estatísticas detalhadas de uma partida específica pelo ID"""
        url = "https://v3.football.api-sports.io/fixtures/statistics"
        querystring = {"fixture": fixture_id}

        try:
            response = requests.get(url, headers=self.headers, params=querystring, timeout=10)
            if response.status_code == 200:
                return response.json().get("response", [])
        except requests.exceptions.RequestException:
            pass # Ignora falhas pontuais de estatísticas individuais para não travar o loop
        return []

    def evaluate_strategy(self, match_data):
        """Avalia as faixas de minutos e analisa individualmente o desempenho dos times"""
        try:
            fixture_id = match_data["fixture"]["id"]
            status_short = match_data["fixture"]["status"]["short"]
            elapsed = match_data["fixture"]["status"].get("elapsed", 0)
            
            home_team = match_data["teams"]["home"]["name"]
            away_team = match_data["teams"]["away"]["name"]
            
            home_goals = match_data["goals"]["home"]
            away_goals = match_data["goals"]["away"]
            total_goals = home_goals + away_goals

            # Janelas estratégicas
            is_early = (status_short == "1H" and 22 <= elapsed <= 38 and total_goals == 0)
            is_ht = (status_short == "HT" and home_goals <= away_goals)
            is_second_half = (status_short == "2H" and 55 <= elapsed <= 78 and total_goals < 3)

            if not (is_early or is_ht or is_second_half):
                return None

            # Busca estatísticas detalhadas
            statistics = self.fetch_match_statistics(fixture_id)
            if not statistics or len(statistics) < 2:
                return None

            home_stats = {stat["type"]: stat["value"] for stat in statistics[0]["statistics"]}
            away_stats = {stat["type"]: stat["value"] for stat in statistics[1]["statistics"]}
            
            # Coleta métricas individuais com segurança
            home_shots_target = int(home_stats.get("Shots on Goal", 0) or 0)
            away_shots_target = int(away_stats.get("Shots on Goal", 0) or 0)
            total_shots_target = home_shots_target + away_shots_target

            home_attacks = int(home_stats.get("Total Attacks", 0) or 0)
            away_attacks = int(away_stats.get("Total Attacks", 0) or 0)
            total_attacks = home_attacks + away_attacks

            home_possession = int(str(home_stats.get("Ball Possession", "50%")).replace("%", ""))
            away_possession = int(str(away_stats.get("Ball Possession", "50%")).replace("%", ""))

            # Estratégia 1: Pressão Inicial (1º Tempo)
            if is_early and total_shots_target >= 3 and total_attacks >= 35:
                signal_key = f"{fixture_id}_early_v4"
                if signal_key not in self.alerted_matches:
                    self.alerted_matches.add(signal_key)
                    return {
                        "home": home_team, "away": away_team, "score_home": home_goals, "score_away": away_goals,
                        "market": "Mais de 0.5 Gols (1º Tempo)", "confidence": "Alta ⭐⭐⭐",
                        "intensity": "🔥 Pressão Inicial Forte",
                        "reason": f"Jogo aberto aos {elapsed} min (0x0). Ataques Totais: {home_attacks}x{away_attacks} | Chutes no Alvo: {home_shots_target}x{away_shots_target}."
                    }

            # Estratégia 2: Alta Intensidade (2º Tempo)
            if is_second_half and total_shots_target >= 5:
                signal_key = f"{fixture_id}_second_v4"
                if signal_key not in self.alerted_matches:
                    self.alerted_matches.add(signal_key)
                    return {
                        "home": home_team, "away": away_team, "score_home": home_goals, "score_away": away_goals,
                        "market": "Mais de 1.5 / 2.5 Gols (Live)", "confidence": "Muito Alta ⭐⭐⭐⭐",
                        "intensity": "🔥🔥 Ritmo Acelerado (Pressão Máxima)",
                        "reason": f"Sufoco aos {elapsed} min ({home_goals}x{away_goals}). Chutes no Alvo: {home_team} ({home_shots_target}) x {away_team} ({away_shots_target}). Posse: {home_possession}% x {away_possession}%."
                    }

            # Estratégia 3: Pressão de Mandante/Favorito no Intervalo (HT)
            if is_ht and home_possession >= 55 and home_shots_target >= 3:
                signal_key = f"{fixture_id}_ht_v4"
                if signal_key not in self.alerted_matches:
                    self.alerted_matches.add(signal_key)
                    return {
                        "home": home_team, "away": away_team, "score_home": home_goals, "score_away": away_goals,
                        "market": "Mais de 1.5 Gols (Geral / Seq.)", "confidence": "Alta ⭐⭐⭐",
                        "intensity": "⚡ Reversão Esperada no 2º Tempo",
                        "reason": f"{home_team} mandou no 1º tempo mas perdendo de {home_goals}x{away_goals}. Posse: {home_possession}% | Chutes no Alvo: {home_shots_target}x{away_shots_target}."
                    }

        except Exception as e:
            logging.error(f"Erro interno ao avaliar partida: {e}")

        return None

    def send_telegram_alert(self, signal_info):
        message = (
            f"🚨 *SINAL VIP - OPORTUNIDADE LIVE* 🚨\n\n"
            f"⚽ *Partida:* `{signal_info['home']} vs {signal_info['away']}`\n"
            f"📊 *Placar Atual:* `{signal_info['score_home']} x {signal_info['score_away']}`\n"
            f"🎯 *Mercado Sugerido:* *{signal_info['market']}*\n"
            f"📈 *Status:* _{signal_info['intensity']}_\n"
            f"⭐ *Confiança:* {signal_info['confidence']}\n\n"
            f"💡 *Raio-X Estatístico:*\n{signal_info['reason']}\n\n"
            f"🤖 _Gerado automaticamente pelo Robô em {datetime.now().strftime('%H:%M:%S')}_"
        )
        
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"}

        try:
            requests.post(url, json=payload, timeout=10)
            logging.info(f"Sinal profissional enviado para o Telegram: {signal_info['home']} vs {signal_info['away']}")
        except Exception as e:
            logging.error(f"Erro ao enviar alerta ao Telegram: {e}")

    def run_scanner_loop(self):
        logging.info("Robô blindado iniciado. Sistema de auto-reconexão ativado.")
        while True:
            try:
                fixtures = self.fetch_live_fixtures_from_api()
                if fixtures:
                    logging.info(f"Varrendo {len(fixtures)} partidas ao vivo...")
                    for match in fixtures:
                        signal = self.evaluate_strategy(match)
                        if signal:
                            self.send_telegram_alert(signal)
                else:
                    logging.info("Aguardando novas partidas ou reconectando...")
            except Exception as e:
                logging.error(f"Erro crítico capturado no loop principal: {e}. Retomando em 10 segundos...")
            
            time.sleep(60)

if __name__ == "__main__":
    TELEGRAM_TOKEN = "8509837129:AAEjLc0QKWQpJUaL-ilfe9UaPkSXuM6zX-A"
    CHAT_ID = "-1003764651701"
    API_KEY = "6fda158f8d68552276eab254c2b0ba77"

    scanner = LiveMatchScanner(telegram_token=TELEGRAM_TOKEN, chat_id=CHAT_ID, api_key=API_KEY)
    scanner.run_scanner_loop()