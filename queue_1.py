import warnings
from urllib3.exceptions import NotOpenSSLWarning
warnings.filterwarnings("ignore", category=NotOpenSSLWarning)

import os
import base64
import logging
from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key').encode()
CLIENT_ID = '4781e6fbedae431dbbc4c586fcce9d06'
CLIENT_SECRET = '09fcf15964624fc4a616abf76f2c4371'
REFRESH_TOKEN = 'AQAC0LbZpQo6A78s5D5PMTjvbMRqwsiVaIshd8VXkKEioa6emtoJfhukyFH1d1yK08hYyyAXypIkErZ_FX9tkIvL68gHoyHeE7TfLfzGTujhsyWvzkJ22WuQ600bo7CNIGU'

# CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
# CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
# REFRESH_TOKEN = os.getenv('SPOTIFY_REFRESH_TOKEN')

TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE_URL = 'https://api.spotify.com/v1'

session_retry = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)
session_retry.mount("https://", HTTPAdapter(max_retries=retry_strategy))


def get_access_token():
    try:
        auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
        headers = {
            'Authorization': f'Basic {base64.b64encode(auth_str.encode()).decode()}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': REFRESH_TOKEN
        }
        response = session_retry.post(TOKEN_URL, headers=headers, data=data)
        response.raise_for_status()
        token_data = response.json()
        return token_data['access_token']
    except Exception as e:
        logger.error(f"Access token retrieval failed: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('queue.html')

@app.route('/current')
def current_playing():
    access_token = get_access_token()
    if not access_token:
        return jsonify({"error": "Failed to authorize with Spotify"}), 500
    try:
        response = session_retry.get(
            f"{API_BASE_URL}/me/player/currently-playing",
            headers={'Authorization': f"Bearer {access_token}"}
        )
        if response.status_code == 204:
            return jsonify({"message": "No track currently playing"}), 204
        response.raise_for_status()
        data = response.json()
        if not data or "item" not in data:
            return jsonify({"message": "No track currently playing"}), 204
        track = data["item"]
        current_track = {
            "name": track["name"],
            "artist": track["artists"][0]["name"],
            "image": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
            "uri": track["uri"],
            "id": track["id"],
            "progress_ms": data.get("progress_ms", 0),
            "duration_ms": track.get("duration_ms", 0),
            "is_playing": data.get("is_playing", False),
        }
        return jsonify(current_track)
    except Exception as e:
        logger.error(f"Current track error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/queue-spotify')
def get_spotify_queue():
    access_token = get_access_token()
    if not access_token:
        return jsonify({"error": "Failed to authorize with Spotify"}), 500
    try:
        response = session_retry.get(
            f"{API_BASE_URL}/me/player/queue",
            headers={'Authorization': f"Bearer {access_token}"}
        )
        if response.status_code == 204:
            return jsonify({"message": "No active device or queue available"}), 204
        response.raise_for_status()
        queue_data = response.json()

        formatted_response = {
            "currently_playing": None,
            "queue": []
        }

        if queue_data.get('currently_playing'):
            track = queue_data['currently_playing']
            formatted_response["currently_playing"] = {
                "name": track['name'],
                "artist": track['artists'][0]['name'],
                "image": track['album']['images'][0]['url'] if track['album']['images'] else None,
                "uri": track['uri'],
                "duration_ms": track['duration_ms'],
                "id": track['id']
            }

        if queue_data.get('queue'):
            formatted_response["queue"] = [
                {
                    "name": item['name'],
                    "artist": item['artists'][0]['name'],
                    "image": item['album']['images'][0]['url'] if item['album']['images'] else None,
                    "uri": item['uri'],
                    "duration_ms": item['duration_ms'],
                    "id": item['id']
                } for item in queue_data['queue']
            ]

        return jsonify(formatted_response)

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error getting queue: {http_err}")
        return jsonify({"error": "Failed to get queue", "details": str(http_err)}), 500
    except Exception as e:
        logger.error(f"Queue retrieval error: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
