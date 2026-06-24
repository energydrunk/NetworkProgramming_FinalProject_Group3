# NetworkProgramming_FinalProject_Group3
# 🟩 Wordle Multiplayer
**Network Programming Final Project — Group 4**

---

## Team Members

| Name | NRP | Role |
|---|---|---|
| Nuha Usama Okbah | 5025241005 | Server Core Developer |
| Almira Nayla Felisitha | 5025241014 | Sync & UDP Developer |
| Embun Nabila R.A.Z. | 5025241009 | GUI & Features Developer |
| Adelia Tanalina Yumna | 5025241078 | Game Logic Developer |
| Kirana Alivia Enrico | 5025211190 | Chat & Leaderboard Developer |

---

## How to Run

### Install dependencies
```bash
pip install pygame
```

### Single Laptop
```bash
# Terminal 1 — start server
python -m server.server

# Terminal 2, 3, etc. — one per player
python -m client.gui
```

### Different Laptops (same WiFi/hotspot)
```bash
# Server laptop
python -m server.server --host 0.0.0.0

# Client laptops (replace with server's IP address)
python -m client.gui --host 192.168.x.x
```

> To find the server's IP on Windows: run `ipconfig` and look for **IPv4 Address**

---

## File Structure

```
wordle_v2/
├── server/
│   ├── server.py          → Main TCP server
│   └── room_manager.py    → Room & game loop
├── client/
│   ├── gui.py             → Pygame GUI
│   └── network.py         → Network handler
├── shared/
│   ├── protocol.py        → JSON message format
│   └── game_logic.py      → Game logic
└── words/
    ├── easy.txt            → 4-letter words
    ├── normal.txt          → 5-letter words
    └── hard.txt            → 6-letter words
```

---

## Code Explanation

### 1. `shared/protocol.py`
**PIC: Adelia**

This file acts as the "shared language" between the server and all clients. Every message sent over the network uses the JSON format defined here.

**Core functions:**

```python
def encode(data: dict) -> bytes:
    return (json.dumps(data) + "\n").encode("utf-8")
```
Converts a Python dict into JSON bytes with a newline delimiter. The newline is critical because TCP is a stream protocol — without a delimiter, the receiver cannot tell where one message ends and the next begins.

```python
def decode(raw: str) -> dict:
    return json.loads(raw.strip())
```
The reverse — converts a JSON string back into a Python dict.

**Client → Server message formats:**
```python
msg_create_room("Embun", "normal")
# → {"action": "create_room", "username": "Embun", "difficulty": "normal"}

msg_guess("CRANE")
# → {"action": "guess", "word": "CRANE"}

msg_chat("gg!")
# → {"action": "chat", "message": "gg!"}
```

**Server → Client message formats:**
```python
msg_round_start(round_num=1, total_rounds=5, timer=60, word_length=5)
# → {"event": "round_start", "round": 1, "total_rounds": 5, "timer": 60, "word_length": 5}

msg_guess_result(["green","gray","yellow","gray","green"], attempt=2, max_attempts=6, word="CRANE")
# → {"event": "guess_result", "feedback": [...], "attempt": 2, ...}

msg_round_end(secret_word="ARISE", scores=[...], is_host=True)
# → {"event": "round_end", "secret_word": "ARISE", "scores": [...], "is_host": True}
```

**Difficulty config constants:**
```python
DIFFICULTY = {
    "easy":   {"length": 4, "attempts": 7, "timer": 90},
    "normal": {"length": 5, "attempts": 6, "timer": 60},
    "hard":   {"length": 6, "attempts": 5, "timer": 45},
}
```

---

### 2. `shared/game_logic.py`
**PIC: Adelia**

Contains all game logic used by the server: loading words, validating guesses, generating tile feedback, and calculating scores.

**Word loader:**
```python
def load_words(difficulty: str) -> list:
```
Reads the appropriate `.txt` file based on difficulty, filters words by the required length, and caches the result so the file is not re-read every round.

**Tile feedback algorithm:**
```python
def get_feedback(guess: str, secret: str) -> list:
```
Uses a two-pass algorithm:
- **Pass 1** — compare each position. If the letter and position match → `"green"`. Otherwise, record the remaining letters in the secret word.
- **Pass 2** — for non-green letters, check if the letter exists in the remaining secret letters → `"yellow"`. Anything else → `"gray"`.

Example:
```python
get_feedback("CRANE", "ARISE")
# C → gray   (not in ARISE)
# R → green  (position 2 matches)
# A → yellow (exists in ARISE but wrong position)
# N → gray   (not in ARISE)
# E → green  (position 5 matches)
# → ["gray", "green", "yellow", "gray", "green"]
```

Why two passes? Because a letter can appear more than once. Pass 1 prioritizes green first, then pass 2 looks for yellow — this prevents double-counting the same letter.

**Scoring:**
```python
BASE_SCORES = {1:100, 2:85, 3:70, 4:55, 5:40, 6:25, 7:10}

def calculate_score(attempt: int, seconds_left: int) -> int:
    base  = BASE_SCORES.get(attempt, 0)
    bonus = seconds_left // 10
    return base + bonus
```
Fewer attempts = higher base score. Bonus points = remaining seconds divided by 10.

**Ranking:**
```python
def calculate_rank(scores: list) -> list:
```
Sorts scores in descending order and adds a `rank` field to each entry.

---

### 3. `server/server.py`
**PIC: Nuha**

The server entry point. Manages incoming connections and coordinates TCP + UDP communication using `select()`.

**Socket initialization:**
```python
tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
tcp.bind((host, tcp_port))
tcp.listen(20)

udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp.bind((host, udp_port))
```
TCP handles reliable, ordered communication. UDP handles live player status broadcasts (fast, no ACK needed).

**Select loop (Lecture 03):**
```python
inputs = [tcp, udp]
while True:
    readable, _, _ = select.select(inputs, [], [], 1.0)
    for s in readable:
        if s is tcp:
            conn, addr = tcp.accept()
            ClientHandler(conn, addr).start()
        elif s is udp:
            data, addr = udp.recvfrom(1024)
            # handle register_udp
```
`select()` allows the server to monitor both TCP and UDP sockets simultaneously without blocking on either one. The 1.0 second timeout prevents the loop from hanging indefinitely.

**ClientHandler (Lecture 04 — Thread):**
```python
class ClientHandler(threading.Thread):
    def run(self):
        while True:
            data = self.conn.recv(4096).decode("utf-8")
            self.buffer += data
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                self._handle(decode(line))
```
Each connected client runs in its own thread. The buffer handles TCP fragmentation — data may arrive incomplete, so it accumulates until a newline signals a complete message.

**Message routing:**
```python
def _handle(self, msg):
    action = msg.get("action")
    if   action == "create_room": self._create_room(msg)
    elif action == "join_room":   self._join_room(msg)
    elif action == "start_game":  self._start_game()
    elif action == "next_round":  self._next_round()
    elif action == "guess":       self._guess(msg)
    elif action == "chat":        self._chat(msg)
```

**Host transfer on disconnect:**
```python
def _disconnect(self):
    was_host = (self.room.host == self)
    self.room.remove_player(self)
    if was_host and self.room.players:
        self.room.host = self.room.players[0]
```
If the host disconnects, the next player in the list automatically becomes the new host.

---

### 4. `server/room_manager.py`
**PIC: Nuha**

Manages all active rooms and runs the game loop for each room.

**RoomManager:**
```python
class RoomManager:
    def __init__(self):
        self.rooms    = {}   # {room_code: Room}
        self.udp_sock = None
```
A dictionary of all active rooms. `udp_sock` is set from `server.py` so rooms can broadcast via UDP.

**Room code generator:**
```python
def gen_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
```
Generates a random 4-character code (uppercase letters + digits). Uniqueness is verified before use.

**Game loop (runs in a separate thread):**
```python
def run_game(self):
    self.game_started = True
    for rnd in range(1, TOTAL_ROUNDS + 1):
        self.secret_word = get_random_word(self.difficulty)
        self.broadcast(msg_round_start(...))

        # Run timer in a separate thread
        t = threading.Thread(target=self._timer, args=(duration,))
        t.start()

        # Wait for round to finish
        self.round_done.wait()

        # Broadcast round results
        self.broadcast(msg_round_end(...))

        # Wait for host to press next round
        while self.waiting_next:
            time.sleep(0.2)
```
Each round waits on a `round_done` Event. The event is set when all players finish (correct/out of attempts) or when the timer runs out.

**Timer thread:**
```python
def _timer(self, duration):
    for t in range(duration, 0, -1):
        if self.round_done.is_set():
            return   # round already finished early
        self.broadcast(msg_timer_update(t))
        time.sleep(1)
    self._end_round()   # time's up, force end round
```

**Process guess:**
```python
def process_guess(self, client, word):
    state["attempts"] += 1
    feedback = get_feedback(word, self.secret_word)
    client.send(msg_guess_result(feedback, attempt, ...))
    self._broadcast_status()   # UDP to all clients

    if word == self.secret_word:
        score = calculate_score(attempt, state["timer_left"])
        state["status"] = STATUS_CORRECT
    elif attempt >= max_attempts:
        state["status"] = STATUS_OUT

    if all(s["status"] != STATUS_GUESSING for s in self.player_states.values()):
        self._end_round()
```

**UDP status broadcast:**
```python
def _broadcast_status(self):
    data = [{"username": p, "attempts": ..., "status": ...} for p in players]
    self.broadcast_udp(msg_player_status(data))
```
Sent via UDP every time a player submits a guess, so all clients can update their sidebar in real time.

---

### 5. `client/network.py`
**PIC: Almira**

Handles all network communication on the client side. Two listener threads (TCP + UDP) run in parallel in the background.

**Connect:**
```python
def connect(self, host, tcp_port, udp_port):
    self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.tcp_sock.settimeout(5)
    self.tcp_sock.connect((host, tcp_port))

    self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.udp_sock.bind(("", 0))   # bind to a random port

    threading.Thread(target=self._tcp_listen, daemon=True).start()
    threading.Thread(target=self._udp_listen, daemon=True).start()
```
TCP connects to the server. UDP binds to a random port (0 = OS chooses). Both listener threads run as daemons (automatically terminate when the main thread exits).

**Register UDP:**
```python
def register_udp(self):
    payload = encode(msg_register_udp(self.username))
    self.udp_sock.sendto(payload, (self.host, self.udp_port))
```
After joining a room, the client sends its UDP address to the server. The server stores this address to know where to send UDP broadcasts.

**TCP listener:**
```python
def _tcp_listen(self):
    while self.running:
        data = self.tcp_sock.recv(4096).decode("utf-8")
        self.buffer += data
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            self.callback(decode(line))
```
Same buffering approach as the server to handle TCP fragmentation. Each complete message is passed to the `callback` function (which is `on_event` in the GUI).

**UDP listener:**
```python
def _udp_listen(self):
    while self.running:
        self.udp_sock.settimeout(1.0)
        data, _ = self.udp_sock.recvfrom(4096)
        self.callback(decode(data.decode()))
```
Receives UDP broadcasts from the server (player status updates). The 1-second timeout prevents indefinite blocking.

---

### 6. `client/gui.py`
**PIC: Embun**

The full Pygame GUI. Uses a state machine to manage which screen is currently displayed.

**State machine:**
```
login → lobby → game → round_end → game_end
                 ↑__________________________|  (play again)
```

**on_event (callback from network thread):**
```python
def on_event(self, ev):
    e = ev.get("event")
    if   e == "room_created":  self.state = "lobby"
    elif e == "round_start":   self.state = "game"
    elif e == "round_end":     self.state = "round_end"
    elif e == "game_end":      self.state = "game_end"
    elif e == "player_left":
        self.players = ev["players"]
        # Check if this client becomes the new host
        if self.players and self.players[0] == self.net.username:
            self.is_host = True
```
Called from the network thread. Updates GUI state based on events received from the server.

**Tile flip animation:**
```python
class FlipTile:
    def update(self):
        self.phase += self.speed   # 0 → 2
        if self.phase >= 1.0:
            self.show_color = True  # reveal color at the midpoint

    def draw(self, surf, font):
        if self.phase < 1.0:
            scale = 1.0 - self.phase    # shrinking
        else:
            scale = self.phase - 1.0    # growing
        h = max(2, int(self.size * scale))
        # draw tile with variable height
```
The flip animation has two phases: shrink (0→1) and grow (1→2). The tile color is revealed at the transition point (middle of the flip), creating the effect of the tile rotating to show its color.

Tiles are staggered per column:
```python
ft.phase = -col * 0.35   # right columns start slightly later
```

**Grid rendering:**
```python
for row in range(self.max_attempts):
    for col in range(self.word_length):
        cell = self.grid[row][col]
        letter = cell["letter"]
        # Show currently typed letters on the active row
        if row == self.cur_row and col < len(self.cur_input):
            letter = self.cur_input[col]
```

**Shake animation (invalid word):**
```python
if row == self.shake_row and self.shake_timer > 0:
    shake_dx = int(6 * (1 if (self.shake_timer//3)%2==0 else -1))
```
The active row shakes left and right at a fixed frequency for a few frames when an invalid word is submitted.

**In-game chat (Lecture 06 — Chat):**
```python
# Send chat
if ev.key == pygame.K_RETURN and self.chat_input.strip():
    self.net.chat(self.chat_input.strip())
    self.chat_input = ""

# Receive chat
elif e == "chat":
    self.chat_msgs.append((ev["from"], ev["message"]))
```
Chat is implemented over TCP — the client sends a message to the server, and the server broadcasts it to all clients in the same room.

---

## Course Materials Implemented

| Material | Lecture | File | Implementation |
|---|---|---|---|
| **TCP Socket** | Lecture 02 | server.py, network.py | Main communication channel for all game events |
| **Select()** | Lecture 03 | server.py | Monitor TCP + UDP sockets simultaneously without blocking |
| **Thread** | Lecture 04 | server.py, room_manager.py, network.py | Client handler thread, timer thread, TCP+UDP listener threads |
| **Chat** | Lecture 06 | server.py, gui.py | In-game chat broadcast to all clients in the room |
| **UDP** | Lecture 07 | server.py, network.py | Real-time live player status broadcast to all clients |
| **Object Serialization** | — | protocol.py | All messages encoded/decoded as JSON |
