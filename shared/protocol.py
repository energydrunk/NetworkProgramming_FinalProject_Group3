# ============================================================
# shared/protocol.py
# ============================================================
import json

TOTAL_ROUNDS = 5

DIFFICULTY = {
    "easy":   {"length": 4, "attempts": 7, "timer": 90},
    "normal": {"length": 5, "attempts": 6, "timer": 60},
    "hard":   {"length": 6, "attempts": 5, "timer": 45},
}

GREEN  = "green"
YELLOW = "yellow"
GRAY   = "gray"

STATUS_GUESSING = "guessing"
STATUS_CORRECT  = "correct"
STATUS_OUT      = "out"

def encode(data: dict) -> bytes:
    return (json.dumps(data) + "\n").encode("utf-8")

def decode(raw: str) -> dict:
    return json.loads(raw.strip())

def msg_create_room(username, difficulty):
    return {"action": "create_room", "username": username, "difficulty": difficulty}
def msg_join_room(username, room_code):
    return {"action": "join_room", "username": username, "room_code": room_code}
def msg_start_game():
    return {"action": "start_game"}
def msg_next_round():
    return {"action": "next_round"}
def msg_play_again():
    return {"action": "play_again"}
def msg_guess(word):
    return {"action": "guess", "word": word.upper()}
def msg_chat(message):
    return {"action": "chat", "message": message}
def msg_leave():
    return {"action": "leave"}
def msg_register_udp(username):
    return {"action": "register_udp", "username": username}

def msg_room_created(room_code, difficulty):
    return {"event": "room_created", "room_code": room_code, "difficulty": difficulty}
def msg_room_joined(room_code, players, difficulty):
    return {"event": "room_joined", "room_code": room_code, "players": players, "difficulty": difficulty}
def msg_player_joined(username, players):
    return {"event": "player_joined", "username": username, "players": players}
def msg_player_left(username, players):
    return {"event": "player_left", "username": username, "players": players}
def msg_game_started(difficulty):
    return {"event": "game_started", "difficulty": difficulty}
def msg_round_start(round_num, total_rounds, timer, word_length):
    return {"event": "round_start", "round": round_num, "total_rounds": total_rounds,
            "timer": timer, "word_length": word_length}
def msg_guess_result(feedback, attempt, max_attempts, word):
    return {"event": "guess_result", "feedback": feedback,
            "attempt": attempt, "max_attempts": max_attempts, "word": word}
def msg_invalid_word(reason):
    return {"event": "invalid_word", "reason": reason}
def msg_player_status(players):
    return {"event": "player_status", "players": players}
def msg_round_end(secret_word, scores, is_host):
    return {"event": "round_end", "secret_word": secret_word, "scores": scores, "is_host": is_host}
def msg_game_end(leaderboard, is_host):
    return {"event": "game_end", "leaderboard": leaderboard, "is_host": is_host}
def msg_chat_broadcast(username, message):
    return {"event": "chat", "from": username, "message": message}
def msg_timer_update(seconds_left):
    return {"event": "timer_update", "seconds_left": seconds_left}
def msg_error(reason):
    return {"event": "error", "reason": reason}
def msg_waiting_host():
    return {"event": "waiting_host"}
def msg_lobby_reset(players):
    return {"event": "lobby_reset", "players": players}
