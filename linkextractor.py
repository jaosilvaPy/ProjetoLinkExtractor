#!/usr/bin/env python
"""
Link Extractor API — Python / Flask
Endpoint: GET /api/<url>
Cache opcional via variável de ambiente REDIS_URL
"""

import json
import os

import redis
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify

app = Flask(__name__)

# Conecta ao Redis apenas se REDIS_URL estiver definida
redis_client = None
redis_url = os.environ.get("REDIS_URL")
if redis_url:
    redis_client = redis.from_url(redis_url)


@app.route("/api/<path:url>")
def extract_links(url):
    # Tenta retornar do cache
    if redis_client:
        cached = redis_client.get(url)
        if cached:
            return app.response_class(
                response=cached, status=200, mimetype="application/json"
            )

    # Busca a página e extrai links
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        links = [
            {"text": a.get_text(strip=True), "href": a.get("href")}
            for a in soup.find_all("a", href=True)
        ]
        result = json.dumps(links)

        # Salva no cache
        if redis_client:
            redis_client.set(url, result)

        return app.response_class(
            response=result, status=200, mimetype="application/json"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)