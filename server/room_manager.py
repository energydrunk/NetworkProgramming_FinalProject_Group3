# ============================================================
# server/room_manager.py
# ============================================================
import random, string, threading, time
from shared.protocol import *
from shared.game_logic import get_random_word, get_feedback, calculate_score, calculate_rank

MAX_PLAYERS  = 5

def gen_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=4))

class Room:
    def __init__(self, code, difficulty, host):
        self.code         = code
        self.difficulty   = difficulty
        self.host         = host
        self.players      = [host]
        self.game_started = False
        self.current_round= 0
        self.secret_word  = ""
        self.round_scores = {}
        self.total_scores = {}
        self.player_states= {}
        self.timer_left   = {}
        self.round_lock   = threading.Lock()
        self.round_done   = threading.Event()
        self.waiting_next = False   # host harus pencet next
        self.udp_addresses= {}
        self._mgr         = None
        self.used_words   = set()

    def add_player(self, c):
        self.players.append(c)
        self.total_scores[c.username] = 0

    def remove_player(self, c):
        if c in self.players:
            self.players.remove(c)

    def is_full(self):   return len(self.players) >= MAX_PLAYERS
    def is_empty(self):  return len(self.players) == 0

    def get_player_list(self):
        return [p.username for p in self.players]

    def broadcast(self, data, exclude=None):
        for p in self.players[:]:
            if p != exclude:
                p.send(data)

    def broadcast_to(self, data, targets):
        for p in targets:
            p.send(data)

    def broadcast_udp(self, data):
        if not self._mgr or not self._mgr.udp_sock:
            return
        payload = encode(data)
        for addr in self.udp_addresses.values():
            try: self._mgr.udp_sock.sendto(payload, addr)
            except: pass

    # ── Game Loop ─────────────────────────────────────────────
    def run_game(self):
        self.game_started = True
        diff = DIFFICULTY[self.difficulty]
        for p in self.players:
            self.total_scores[p.username] = 0

        for rnd in range(1, TOTAL_ROUNDS + 1):
            self.current_round = rnd
            # Pilih kata yang belum pernah dipakai
            word = get_random_word(self.difficulty)
            attempts = 0
            while word in self.used_words and attempts < 50:
                word = get_random_word(self.difficulty)
                attempts += 1
            self.used_words.add(word)
            self.secret_word = word

            self.round_scores = {}
            self.round_done.clear()
            self.waiting_next = False

            self.player_states = {
                p.username: {"attempts": 0, "status": STATUS_GUESSING, "timer_left": diff["timer"]}
                for p in self.players
            }

            print(f"[ROUND {rnd}] Room {self.code} word={self.secret_word}")
            self.broadcast(msg_round_start(rnd, TOTAL_ROUNDS, diff["timer"], diff["length"]))

            # Timer thread
            t = threading.Thread(target=self._timer, args=(diff["timer"],), daemon=True)
            t.start()

            self.round_done.wait()

            # Hitung scores
            scores_list = []
            for p in self.players:
                u = p.username
                sc = self.round_scores.get(u, 0)
                self.total_scores[u] = self.total_scores.get(u, 0) + sc
                scores_list.append({"username": u, "round_score": sc, "total_score": self.total_scores[u]})

            # Kirim round_end, kasih tau siapa host
            for p in self.players:
                p.send(msg_round_end(self.secret_word, scores_list, p == self.host))

            # Tunggu host pencet next (kecuali ronde terakhir)
            if rnd < TOTAL_ROUNDS:
                self.waiting_next = True
                # Tunggu sampai host kirim next_round
                while self.waiting_next and self.game_started:
                    time.sleep(0.2)

        # Game selesai
        lb = calculate_rank([{"username": u, "score": s} for u, s in self.total_scores.items()])
        for p in self.players:
            p.send(msg_game_end(lb, p == self.host))
        self.game_started = False

    def _timer(self, duration):
        for t in range(duration, 0, -1):
            if self.round_done.is_set():
                return
            # Update timer_left tiap player
            for st in self.player_states.values():
                if st["status"] == STATUS_GUESSING:
                    st["timer_left"] = t
            self.broadcast(msg_timer_update(t))
            time.sleep(1)
        if not self.round_done.is_set():
            self._end_round()

    def _end_round(self):
        with self.round_lock:
            if self.round_done.is_set():
                return
            for p in self.players:
                if p.username not in self.round_scores:
                    self.round_scores[p.username] = 0
                    if p.username in self.player_states:
                        self.player_states[p.username]["status"] = STATUS_OUT
            self.round_done.set()

    def process_guess(self, client, word):
        u     = client.username
        state = self.player_states.get(u)
        dconf = DIFFICULTY[self.difficulty]
        if not state or state["status"] != STATUS_GUESSING:
            client.send(msg_error("You already finished this round"))
            return

        state["attempts"] += 1
        feedback = get_feedback(word, self.secret_word)
        attempt  = state["attempts"]

        client.send(msg_guess_result(feedback, attempt, dconf["attempts"], word))
        self._broadcast_status()

        if word == self.secret_word:
            sc = calculate_score(attempt, state["timer_left"])
            self.round_scores[u] = sc
            state["status"] = STATUS_CORRECT
            print(f"[GUESS] {u} correct in {attempt} attempts, score={sc}")
        elif attempt >= dconf["attempts"]:
            state["status"] = STATUS_OUT
            self.round_scores[u] = 0

        all_done = all(s["status"] != STATUS_GUESSING for s in self.player_states.values())
        if all_done:
            self._end_round()

    def _broadcast_status(self):
        data = [{"username": p.username,
                 "attempts": self.player_states[p.username]["attempts"],
                 "status":   self.player_states[p.username]["status"]}
                for p in self.players if p.username in self.player_states]
        self.broadcast_udp(msg_player_status(data))


class RoomManager:
    def __init__(self):
        self.rooms    = {}
        self.udp_sock = None
        self._lock    = threading.Lock()

    def create_room(self, difficulty, host):
        with self._lock:
            while True:
                code = gen_code()
                if code not in self.rooms:
                    break
            room = Room(code, difficulty, host)
            room._mgr = self
            room.total_scores[host.username] = 0
            self.rooms[code] = room
            return room

    def get_room(self, code):
        return self.rooms.get(code.upper())

    def remove_room(self, code):
        with self._lock:
            self.rooms.pop(code, None)

    def register_udp(self, username, addr):
        for room in self.rooms.values():
            for p in room.players:
                if p.username == username:
                    room.udp_addresses[username] = addr
                    return
