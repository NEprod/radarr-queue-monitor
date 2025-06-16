#!/usr/bin/env python3
import os
import sqlite3
import time
import requests
import logging
from logging.handlers import RotatingFileHandler

def get_int_env(var_name, default):
    try:
        value = os.getenv(var_name, str(default)).strip()
        return int(value) if value else default
    except ValueError:
        print(f"[error] Invalid value for {var_name}. Falling back to default: {default}")
        return default

# --- Configuration ---
RADARR_URL = os.getenv("RADARR_URL")
RADARR_API_KEY = os.getenv("RADARR_API_KEY")
MAX_RETRIES = get_int_env("MAX_RETRIES", 5)
RETRY_WINDOW_SECONDS = get_int_env("RETRY_WINDOW_SECONDS", 3600)
PRUNE_INTERVAL_SECONDS = get_int_env("PRUNE_INTERVAL_SECONDS", 7200)
RETRY_DB_PATH = "/config/retry_tracker.db"
LOG_PATH = "/config/radarr_queue_monitor.log"
LOG_MAX_BYTES = 10 * 1024 * 1024
LOG_BACKUP_COUNT = 3

# --- Sanity Check ---
if not RADARR_URL or not RADARR_API_KEY:
    print("[fatal] RADARR_URL and RADARR_API_KEY must be set as environment variables.")
    exit(1)

# --- Logging ---
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logger = logging.getLogger("radarr_queue_monitor")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(LOG_PATH, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)
formatter = logging.Formatter('%(asctime)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
console = logging.StreamHandler()
console.setFormatter(formatter)
logger.addHandler(console)

# --- SQLite ---
def init_db():
    with sqlite3.connect(RETRY_DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS retries (movie_id INTEGER, timestamp INTEGER)")

def record_retry(movie_id):
    with sqlite3.connect(RETRY_DB_PATH) as conn:
        conn.execute("INSERT INTO retries (movie_id, timestamp) VALUES (?, ?)", (movie_id, int(time.time())))

def get_retry_count(movie_id):
    with sqlite3.connect(RETRY_DB_PATH) as conn:
        cur = conn.cursor()
        now = int(time.time())
        cur.execute("SELECT COUNT(*) FROM retries WHERE movie_id = ? AND timestamp > ?", (movie_id, now - RETRY_WINDOW_SECONDS))
        return cur.fetchone()[0]

def prune_old_retries():
    with sqlite3.connect(RETRY_DB_PATH) as conn:
        threshold = int(time.time()) - RETRY_WINDOW_SECONDS
        conn.execute("DELETE FROM retries WHERE timestamp < ?", (threshold,))
    logger.info("[prune] Old retry entries pruned.")

# --- Radarr API ---
def api_get(endpoint):
    return requests.get(f"{RADARR_URL}/api/v3/{endpoint}", headers={"X-Api-Key": RADARR_API_KEY})

def api_post(endpoint, json=None):
    return requests.post(f"{RADARR_URL}/api/v3/{endpoint}", headers={"X-Api-Key": RADARR_API_KEY}, json=json or {})

def api_delete(endpoint):
    return requests.delete(f"{RADARR_URL}/api/v3/queue/{endpoint}?removeFromClient=true", headers={"X-Api-Key": RADARR_API_KEY})

def has_english_audio(languages):
    return any(lang.get("name") == "English" for lang in languages)

def post_blocklist_entry(movie_id, history_entry):
    payload = {
        "movieId": movie_id,
        "sourceTitle": history_entry.get("sourceTitle"),
        "indexer": history_entry.get("indexer"),
        "protocol": history_entry.get("protocol"),
        "downloadClient": history_entry.get("downloadClient"),
        "downloadId": history_entry.get("downloadId"),
        "message": "Blocked due to non-English language.",
        "date": history_entry.get("date")
    }

    required = ["movieId", "sourceTitle", "downloadId"]
    if not all(payload.get(k) for k in required):
        for k, v in payload.items():
            if not v:
                logger.warning(f"[blocklist] Missing field: {k}")
        logger.warning("[blocklist] Skipping blocklist: missing required fields")
        return

    response = api_post("blocklist", json=payload)
    if response.status_code == 201:
        logger.info(f"[blocklist] Release added to blocklist: {payload['sourceTitle']}")
    else:
        logger.error(f"[blocklist] Failed to add release to blocklist. Status {response.status_code}: {response.text}")

# --- Main ---
def main():
    logger.info("[startup] Radarr non-English cleaner started")
    logger.info(f"[config] Retries: {MAX_RETRIES}, Retry window: {RETRY_WINDOW_SECONDS}s, Prune: {PRUNE_INTERVAL_SECONDS}s")
    init_db()
    last_prune = time.time()

    while True:
        try:
            response = api_get("queue?status=queued&status=downloading")
            items = response.json().get("records", [])
            logger.info(f"[scan] Queue has {len(items)} items")

            for item in items:
                movie_id = item.get("movieId")
                title = item.get("title", "???")
                download_id = item.get("downloadId")
                queue_id = item.get("id")
                languages = item.get("languages", [])

                if not movie_id or not download_id or not queue_id:
                    logger.warning(f"[skip] Missing critical fields for {title}")
                    continue

                if has_english_audio(languages):
                    logger.info(f"[ok] English audio present — keeping: {title}")
                    continue

                logger.info(f"[scan] Non-English detected: {title}")
                retry_count = get_retry_count(movie_id)

                if retry_count >= MAX_RETRIES:
                    logger.warning(f"[limit] {title} reached retry limit — removing only")
                else:
                    record_retry(movie_id)

                logger.info(f"[remove] Removing {title} from queue and blocklisting...")
                api_delete(queue_id)

                # Sleep to allow history metadata to be available
                time.sleep(5)

                # Fetch history again
                history = api_get(f"history?movieId={movie_id}").json().get("records", [])
                matched = next((r for r in history if r.get("downloadId") == download_id), None)

                if matched:
                    history_id = matched["id"]
                    logger.info(f"[history] Marking release as failed: ID {history_id}")
                    api_post(f"history/failed/{history_id}")


                    #logger.info(f"[history] Marking release as blocked: ID {history_id}")
                    #post_blocklist_entry(movie_id, matched)
                else:
                    logger.warning(f"[warn] No matching history found for blocklisting {title}")

                logger.info(f"[retry] {title} has {retry_count}/{MAX_RETRIES} attempts so far")
                if retry_count < MAX_RETRIES:
                    logger.info(f"[rescan] Triggering search for: {title}")
                    api_post("command", {
                        "name": "MoviesSearch",
                        "movieIds": [movie_id]
                    })

            if time.time() - last_prune > PRUNE_INTERVAL_SECONDS:
                prune_old_retries()
                last_prune = time.time()

        except Exception as e:
            logger.error(f"[error] Unexpected error: {e}")

        time.sleep(15)

if __name__ == "__main__":
    main()