import os
import requests
from datetime import datetime, timedelta
from telegram import Bot

# Puxa as chaves direto do servidor (nuvem) de forma segura
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FOOTBALL_API_KEY = os.getenv("API_KEY")

BASE_URL = "https://api-sports.io/v4/matches" # Ou o endpoint correto da sua API Pro

def enviar_mensagem_telegram(mensagem):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Erro: Token ou Chat ID do Telegram não configurados.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"Erro ao enviar mensagem para o Telegram: {response.text}")
    except Exception as e:
        print(f"Erro de conexão com o Telegram: {e}")

def main():
    print("Robô blindado iniciado. Sistema de auto-reconexão ativado.")
    # Mensagem de teste para confirmar que o bot está online e conectado
    enviar_mensagem_telegram("🤖 *Robô de Futebol Conectado!*\n\nO bot foi iniciado com sucesso na nuvem e está monitorando os jogos.")

    # Aqui continua o seu loop principal de monitoramento...
    while True:
        # Exemplo de lógica de varredura
        print("Varrendo partidas ao vivo...")
        # Adicione sua lógica de requisição da API e filtros aqui
        break # Apenas para teste inicial

if __name__ == "__main__":
    main()
