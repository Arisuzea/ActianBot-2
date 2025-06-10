import os
import time
import requests
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "I'm alive"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def ping_replit():
    while True:
        try:
            requests.get("https://6e4f5529-9a5d-469e-a825-abc89a4c4566-00-2chl2pt6folb9.sisko.replit.dev/")
            print("Pinged Replit")
        except Exception as e:
            print("Failed to ping Replit:", e)
        time.sleep(300)

def keep_alive():
    Thread(target=run).start()
    Thread(target=ping_replit).start()
