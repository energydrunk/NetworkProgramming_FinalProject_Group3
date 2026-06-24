# ============================================================
# shared/game_logic.py
# ============================================================
import random, os
from shared.protocol import GREEN, YELLOW, GRAY, DIFFICULTY

WORD_FILES = {
    "easy":   "words/easy.txt",
    "normal": "words/normal.txt",
    "hard":   "words/hard.txt",
}
_cache = {}

def load_words(difficulty):
    if difficulty in _cache:
        return _cache[difficulty]
    path = WORD_FILES.get(difficulty, WORD_FILES["normal"])
    fallback = {
        "easy":   ["CATS","DOGS","FISH","BIRD","FROG","DUCK","LION","BEAR","WOLF","DEER"],
        "normal": ["CRANE","SLATE","AUDIO","RAISE","STARE","ARISE","LATER","SMART","PLANT","WORLD"],
        "hard":   ["PLANET","BRIDGE","CASTLE","FLOWER","GARDEN","MIRROR","FROZEN","WINTER"],
    }
    if not os.path.exists(path):
        _cache[difficulty] = fallback.get(difficulty, fallback["normal"])
        return _cache[difficulty]
    with open(path) as f:
        words = [w.strip().upper() for w in f if w.strip()]
    tlen = DIFFICULTY[difficulty]["length"]
    words = [w for w in words if len(w) == tlen]
    _cache[difficulty] = words
    return words

def get_random_word(difficulty):
    return random.choice(load_words(difficulty))

def is_valid_word(word, difficulty):
    return word.upper() in load_words(difficulty)

def get_feedback(guess, secret):
    guess, secret = guess.upper(), secret.upper()
    n = len(secret)
    result = [GRAY] * n
    counts = {}
    for i in range(n):
        if guess[i] == secret[i]:
            result[i] = GREEN
        else:
            counts[secret[i]] = counts.get(secret[i], 0) + 1
    for i in range(n):
        if result[i] == GREEN:
            continue
        if guess[i] in counts and counts[guess[i]] > 0:
            result[i] = YELLOW
            counts[guess[i]] -= 1
    return result

BASE_SCORES = {1:100,2:85,3:70,4:55,5:40,6:25,7:10}

def calculate_score(attempt, seconds_left):
    base  = BASE_SCORES.get(attempt, 0)
    bonus = seconds_left // 10
    return base + bonus

def calculate_rank(scores):
    s = sorted(scores, key=lambda x: x["score"], reverse=True)
    for i, e in enumerate(s):
        e["rank"] = i + 1
    return s
