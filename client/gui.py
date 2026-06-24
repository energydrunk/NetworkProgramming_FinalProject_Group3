import pygame, sys, threading, os, argparse, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared.protocol import *
from client.network import NetworkClient

WIDTH, HEIGHT = 960, 640
FPS = 60

BG          = (18,  18,  19)
DARK        = (30,  30,  32)
PANEL       = (40,  40,  42)
TILE_EMPTY  = (18,  18,  19)
TILE_BORDER = (58,  58,  60)
TILE_FILLED = (18,  18,  19)
C_GREEN     = (83,  141, 78)
C_YELLOW    = (181, 159, 59)
C_GRAY      = (58,  58,  60)
KEY_DEF     = (129, 131, 132)
WHITE       = (255, 255, 255)
OFF_WHITE   = (200, 200, 200)
TEAL        = (0,   180, 216)
MINT        = (2,   195, 154)
RED         = (220, 60,  60)
GOLD        = (255, 200, 50)
MID_GRAY    = (100, 100, 100)
LIGHT_PANEL = (50,  50,  52)

TILE_COLORS = {"green": C_GREEN, "yellow": C_YELLOW, "gray": C_GRAY}

KB_ROWS = [
    list("QWERTYUIOP"),
    list("ASDFGHJKL"),
    ["ENTER"] + list("ZXCVBNM") + ["<<"],
]

class FlipTile:
    def __init__(self, letter, color, x, y, size):
        self.letter  = letter
        self.color   = color
        self.x, self.y, self.size = x, y, size
        self.phase   = 0.0  
        self.speed   = 0.08
        self.done    = False
        self.show_color = False

    def update(self):
        if self.done: return
        self.phase += self.speed
        if self.phase >= 1.0 and not self.show_color:
            self.show_color = True
        if self.phase >= 2.0:
            self.phase = 2.0
            self.done  = True

    def draw(self, surf, font):
        if self.done:
            scale = 1.0
        elif self.phase < 1.0:
            scale = 1.0 - self.phase
        else:
            scale = self.phase - 1.0

        h = max(2, int(self.size * scale))
        rect_y = self.y + (self.size - h) // 2
        color = self.color if self.show_color else TILE_FILLED
        border = self.color if self.show_color else WHITE
        pygame.draw.rect(surf, color, (self.x, rect_y, self.size, h))
        pygame.draw.rect(surf, border, (self.x, rect_y, self.size, h), 2)
        if scale > 0.3 and self.letter:
            t = font.render(self.letter, True, WHITE)
            surf.blit(t, (self.x + self.size//2 - t.get_width()//2,
                          rect_y + h//2 - t.get_height()//2))


# MAIN APP
class WordleApp:
    def __init__(self, server_host="127.0.0.1", tcp_port=55000, udp_port=55002):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Wordle Multiplayer")
        self.clock  = pygame.time.Clock()

        self.server_host = server_host
        self.tcp_port    = tcp_port
        self.udp_port    = udp_port

        self.font_xl   = pygame.font.SysFont("Arial", 42, bold=True)
        self.font_lg   = pygame.font.SysFont("Arial", 30, bold=True)
        self.font_md   = pygame.font.SysFont("Arial", 20)
        self.font_sm   = pygame.font.SysFont("Arial", 15)
        self.font_xs   = pygame.font.SysFont("Arial", 12)
        self.font_tile = pygame.font.SysFont("Arial", 26, bold=True)
        self.font_key  = pygame.font.SysFont("Arial", 13, bold=True)

        self.net   = NetworkClient(self.on_event)
        self.state = "login"   

        # Login
        self.inp_user   = ""
        self.inp_room   = ""
        self.inp_ip     = server_host
        self.inp_tcp    = str(tcp_port)
        self.inp_udp    = str(udp_port)
        self.active_inp = "user"
        self.sel_diff   = "normal"
        self.login_mode = "create"
        self.error_msg  = ""
        self.show_adv   = False   

        # Lobby
        self.room_code  = ""
        self.players    = []
        self.is_host    = False
        self.difficulty = "normal"
        self.lobby_msg  = ""

        # Game
        self.word_length  = 5
        self.max_attempts = 6
        self.grid         = []
        self.flip_tiles   = []   
        self.cur_row      = 0
        self.cur_input    = ""
        self.key_colors   = {}
        self.timer_left   = 60
        self.round_num    = 1
        self.total_rounds = TOTAL_ROUNDS
        self.opp_status   = []
        self.chat_msgs    = []
        self.chat_input   = ""
        self.chat_focused = False
        self.my_status    = STATUS_GUESSING
        self.invalid_msg  = ""
        self.invalid_timer= 0
        self.shake_row    = -1
        self.shake_timer  = 0

        # Round end
        self.round_secret = ""
        self.round_scores = []
        self.can_next     = False  

        # Game end
        self.leaderboard  = []
        self.can_again    = False

        self._lock = threading.Lock()

    # EVENT HANDLER
    def on_event(self, ev):
        e = ev.get("event")

        if e == "room_created":
            self.room_code  = ev["room_code"]
            self.difficulty = ev["difficulty"]
            self.is_host    = True
            self.players    = [self.inp_user]
            self.lobby_msg  = f"Room created! Share code: {self.room_code}"
            self.state      = "lobby"
            self.net.register_udp()

        elif e == "room_joined":
            self.room_code  = ev["room_code"]
            self.players    = ev["players"]
            self.difficulty = ev["difficulty"]
            self.is_host    = False
            self.lobby_msg  = "Joined! Waiting for host to start..."
            self.state      = "lobby"
            self.net.register_udp()

        elif e == "player_joined":
            self.players   = ev["players"]
            self.lobby_msg = f"{ev['username']} joined the room!"

        elif e == "player_left":
            self.players   = ev["players"]
            self.lobby_msg = f"{ev['username']} left."
            if self.players and self.players[0] == self.net.username:
                if not self.is_host:
                    self.is_host   = True
                    self.lobby_msg = f"{ev['username']} left. You are now the host!"

        elif e == "lobby_reset":
            self.players   = ev["players"]
            self.lobby_msg = "Host reset! Waiting to start again..."
            self.state     = "lobby"
            self._reset_game_state()

        elif e == "game_started":
            d = ev["difficulty"]
            self.word_length  = d["length"]
            self.max_attempts = d["attempts"]
            self._init_grid()

        elif e == "round_start":
            self.round_num    = ev["round"]
            self.total_rounds = ev["total_rounds"]
            self.timer_left   = ev["timer"]
            self.word_length  = ev["word_length"]
            self.cur_row      = 0
            self.cur_input    = ""
            self.key_colors   = {}
            self.my_status    = STATUS_GUESSING
            self.invalid_msg  = ""
            self.opp_status   = []
            self.flip_tiles   = []
            self._init_grid()
            self.state        = "game"

        elif e == "guess_result":
            self._apply_feedback(ev["feedback"], ev["attempt"], ev["word"])

        elif e == "invalid_word":
            self.invalid_msg   = ev["reason"]
            self.invalid_timer = 120
            self.shake_row     = self.cur_row
            self.shake_timer   = 20

        elif e == "player_status":
            self.opp_status = [p for p in ev["players"] if p["username"] != self.net.username]

        elif e == "timer_update":
            self.timer_left = ev["seconds_left"]

        elif e == "round_end":
            self.round_secret = ev["secret_word"]
            self.round_scores = ev["scores"]
            self.can_next     = ev["is_host"]
            self.state        = "round_end"

        elif e == "game_end":
            self.leaderboard = ev["leaderboard"]
            self.can_again   = ev["is_host"]
            self.state       = "game_end"

        elif e == "chat":
            self.chat_msgs.append((ev["from"], ev["message"]))
            if len(self.chat_msgs) > 30:
                self.chat_msgs.pop(0)

        elif e == "error":
            self.error_msg = ev["reason"]

        elif e == "disconnected":
            self.error_msg = "Disconnected from server."
            self.state     = "login"

    # HELPERS
    def _init_grid(self):
        self.grid = [[{"letter":"","color":None} for _ in range(self.word_length)]
                     for _ in range(self.max_attempts)]
        self.flip_tiles = []

    def _reset_game_state(self):
        self.cur_row      = 0
        self.cur_input    = ""
        self.key_colors   = {}
        self.my_status    = STATUS_GUESSING
        self.flip_tiles   = []
        self.opp_status   = []
        self.chat_msgs    = []
        self.chat_input   = ""

    def _apply_feedback(self, feedback, attempt, word):
        row = attempt - 1
        tiles_to_flip = []
        for col, (letter, color) in enumerate(zip(word, feedback)):
            self.grid[row][col] = {"letter": letter, "color": color}
            prev = self.key_colors.get(letter)
            if color == "green":
                self.key_colors[letter] = "green"
            elif color == "yellow" and prev != "green":
                self.key_colors[letter] = "yellow"
            elif color == "gray" and prev is None:
                self.key_colors[letter] = "gray"

            x, y, sz = self._tile_pos(row, col)
            ft = FlipTile(letter, TILE_COLORS[color], x, y, sz)
            ft.phase = -col * 0.35 
            tiles_to_flip.append(ft)

        self.flip_tiles.extend(tiles_to_flip)
        self.cur_row   = attempt
        self.cur_input = ""

        if all(c == "green" for c in feedback):
            self.my_status = STATUS_CORRECT
        elif attempt >= self.max_attempts:
            self.my_status = STATUS_OUT

    def _tile_pos(self, row, col):
        sz     = min(55, 300 // self.word_length)
        gap    = 5
        grid_w = self.word_length * (sz + gap) - gap
        gx     = 50 + (420 - grid_w) // 2
        gy     = 80
        return gx + col*(sz+gap), gy + row*(sz+gap), sz

    # MAIN LOOP
    def run(self):
        while True:
            dt = self.clock.tick(FPS)
            self._events()
            self._update()
            self._draw()
            pygame.display.flip()

    def _update(self):
        self.flip_tiles = [ft for ft in self.flip_tiles if not ft.done or ft.phase < 2.0]
        for ft in self.flip_tiles:
            ft.update()
        if self.invalid_timer > 0:
            self.invalid_timer -= 1
            if self.invalid_timer == 0:
                self.invalid_msg = ""
        if self.shake_timer > 0:
            self.shake_timer -= 1

    def _events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.net.disconnect()
                pygame.quit()
                sys.exit()
            if ev.type == pygame.KEYDOWN:
                if   self.state == "login":     self._key_login(ev)
                elif self.state == "game":      self._key_game(ev)
                elif self.state == "round_end": self._key_roundend(ev)
            if ev.type == pygame.MOUSEBUTTONDOWN:
                if   self.state == "login":    self._click_login(ev.pos)
                elif self.state == "lobby":    self._click_lobby(ev.pos)
                elif self.state == "game":     self._click_game(ev.pos)
                elif self.state == "round_end":self._click_roundend(ev.pos)
                elif self.state == "game_end": self._click_gameend(ev.pos)

    # DRAW
    def _draw(self):
        self.screen.fill(BG)
        if   self.state == "login":     self._draw_login()
        elif self.state == "lobby":     self._draw_lobby()
        elif self.state == "game":      self._draw_game()
        elif self.state == "round_end": self._draw_round_end()
        elif self.state == "game_end":  self._draw_game_end()

    # LOGIN
    def _draw_login(self):
        LX = 30
        FW = 440

        self._text("WORDLE MULTIPLAYER", self.font_lg, WHITE, LX + FW//2, 18, center=True)

        for i, (mode, label) in enumerate([("create","CREATE ROOM"),("join","JOIN ROOM")]):
            bx = LX + i * 225
            color = TEAL if self.login_mode == mode else PANEL
            self._btn(label, bx, 55, 200, 34, color, self.font_sm)

        self._text("Username:", self.font_sm, OFF_WHITE, LX, 105)
        self._input_box(self.inp_user, LX, 122, FW, 34, self.active_inp == "user")

        if self.login_mode == "join":
            self._text("Room Code:", self.font_sm, OFF_WHITE, LX, 172)
            self._input_box(self.inp_room.upper(), LX, 189, FW, 34, self.active_inp == "room")

        if self.login_mode == "create":
            self._text("Difficulty:", self.font_sm, OFF_WHITE, LX, 172)
            bw = 138
            for i, (d, label, desc1, desc2) in enumerate([
                ("easy",  "EASY",  "4 letters", "7 tries · 90s"),
                ("normal","NORMAL","5 letters", "6 tries · 60s"),
                ("hard",  "HARD",  "6 letters", "5 tries · 45s"),
            ]):
                bx = LX + i * 150
                bc = C_GREEN if self.sel_diff == d else PANEL
                self._btn(label, bx, 189, bw, 34, bc, self.font_sm)
                self._text(desc1, self.font_xs, MID_GRAY, bx + bw//2, 229, center=True)
                self._text(desc2, self.font_xs, MID_GRAY, bx + bw//2, 243, center=True)

        # Advanced toggle
        adv_y = 265 if self.login_mode == "create" else 238
        adv_label = "▼ Advanced" if not self.show_adv else "▲ Advanced"
        self._text(adv_label, self.font_xs, TEAL, LX, adv_y)

        if self.show_adv:
            self._text("Server IP:", self.font_xs, OFF_WHITE, LX, adv_y+20)
            self._input_box(self.inp_ip, LX, adv_y+35, 260, 30, self.active_inp == "ip", font=self.font_xs)
            self._text("TCP Port:", self.font_xs, OFF_WHITE, LX+275, adv_y+20)
            self._input_box(self.inp_tcp, LX+275, adv_y+35, 155, 30, self.active_inp == "tcp", font=self.font_xs)

        # Connect button
        btn_y = adv_y + (78 if self.show_adv else 28)
        self._btn("CONNECT & PLAY", LX + FW//2 - 130, btn_y, 260, 44, C_GREEN, self.font_md)

        if self.error_msg:
            self._text(self.error_msg, self.font_sm, RED, LX + FW//2, btn_y + 54, center=True)

        RX = 490
        RW = WIDTH - RX - 10
        self._panel(RX, 10, RW, HEIGHT - 20)
        self._text("How to Play", self.font_md, TEAL, RX + RW//2, 25, center=True)
        pygame.draw.line(self.screen, PANEL, (RX+15, 55), (RX+RW-15, 55), 1)

        tips = [
            ("hdr", "Steps:"),
            ("txt", "1. Enter your username"),
            ("txt", "2. Create a room or join with code"),
            ("txt", "3. Share room code with friends"),
            ("txt", "4. Host presses START to begin"),
            ("txt", "5. Guess the hidden word!"),
            ("gap", ""),
            ("hdr", "Tiles:"),
            ("grn", "GREEN  = right letter, right spot"),
            ("yel", "YELLOW = right letter, wrong spot"),
            ("gry", "GRAY   = letter not in word"),
            ("gap", ""),
            ("hdr", "Scoring:"),
            ("txt", "Fewer attempts = higher base score"),
            ("txt", "More time left = bonus points"),
            ("gap", ""),
            ("hdr", "Difficulty:"),
            ("txt", "Easy   — 4 letters, 7 tries, 90s"),
            ("txt", "Normal — 5 letters, 6 tries, 60s"),
            ("txt", "Hard   — 6 letters, 5 tries, 45s"),
        ]
        color_map = {"hdr": WHITE, "txt": OFF_WHITE, "grn": C_GREEN, "yel": C_YELLOW, "gry": MID_GRAY}
        ty = 64
        for kind, text in tips:
            if kind == "gap":
                ty += 7
                continue
            font = self.font_sm if kind == "hdr" else self.font_xs
            self._text(text, font, color_map[kind], RX+15, ty)
            ty += 22
    # LOBBY
    def _draw_lobby(self):
        self._text("WORDLE MULTIPLAYER", self.font_lg, WHITE, WIDTH//2, 30, center=True)
        self._panel(WIDTH//2-220, 70, 440, 480)

        self._text(f"Room Code:", self.font_sm, OFF_WHITE, WIDTH//2, 90, center=True)
        self._text(self.room_code, self.font_xl, TEAL, WIDTH//2, 115, center=True)
        self._text(f"Difficulty: {self.difficulty.upper()}", self.font_sm, MINT, WIDTH//2, 165, center=True)

        pygame.draw.line(self.screen, PANEL, (WIDTH//2-180, 185), (WIDTH//2+180, 185), 1)

        self._text("Players:", self.font_sm, OFF_WHITE, WIDTH//2, 200, center=True)
        for i, p in enumerate(self.players):
            crown = "👑 " if i == 0 else "   "
            color = GOLD if i == 0 else WHITE
            self._text(f"{crown}{p}", self.font_md, color, WIDTH//2, 225+i*35, center=True)

        pygame.draw.line(self.screen, PANEL, (WIDTH//2-180, 395), (WIDTH//2+180, 395), 1)
        self._text(self.lobby_msg, self.font_xs, MINT, WIDTH//2, 408, center=True)

        if self.is_host:
            self._btn("START GAME", WIDTH//2-120, 430, 220, 46, C_GREEN, self.font_md)
            self._btn("LEAVE", WIDTH//2+115, 430, 90, 46, MID_GRAY, self.font_sm)
        else:
            self._btn("LEAVE ROOM", WIDTH//2-80, 430, 160, 46, MID_GRAY, self.font_md)

    # GAME
    def _draw_game(self):
        pygame.draw.rect(self.screen, DARK, (0, 0, WIDTH, 55))
        self._text(f"Round {self.round_num}/{self.total_rounds}", self.font_sm, OFF_WHITE, 15, 18)
        self._text("WORDLE MULTIPLAYER", self.font_sm, WHITE, WIDTH//2, 18, center=True)
        tc = RED if self.timer_left <= 10 else WHITE
        self._text(f"⏱ {self.timer_left}s", self.font_md, tc, WIDTH-80, 18, center=True)

        sz  = min(55, 300 // self.word_length)
        gap = 5
        gw  = self.word_length * (sz+gap) - gap
        gx  = 50 + (420-gw)//2
        gy  = 80

        flip_cells = {}
        for ft in self.flip_tiles:
            for row in range(self.max_attempts):
                for col in range(self.word_length):
                    x2,y2,sz2 = self._tile_pos(row,col)
                    if ft.x == x2 and ft.y == y2:
                        flip_cells[(row,col)] = ft

        for row in range(self.max_attempts):
            shake_dx = 0
            if row == self.shake_row and self.shake_timer > 0:
                shake_dx = int(6 * (1 if (self.shake_timer//3)%2==0 else -1))

            for col in range(self.word_length):
                x = gx + col*(sz+gap) + shake_dx
                y = gy + row*(sz+gap)
                cell = self.grid[row][col]

                if (row,col) in flip_cells:
                    flip_cells[(row,col)].x = x
                    flip_cells[(row,col)].y = y
                    flip_cells[(row,col)].draw(self.screen, self.font_tile)
                    continue

                letter = cell["letter"]
                if row == self.cur_row and col < len(self.cur_input):
                    letter = self.cur_input[col]

                color_key = cell.get("color")
                if color_key:
                    bg = TILE_COLORS[color_key]; border = bg
                elif letter:
                    bg = TILE_FILLED; border = WHITE
                else:
                    bg = TILE_EMPTY; border = TILE_BORDER

                pygame.draw.rect(self.screen, bg, (x,y,sz,sz))
                pygame.draw.rect(self.screen, border, (x,y,sz,sz), 2)
                if letter:
                    t = self.font_tile.render(letter, True, WHITE)
                    self.screen.blit(t, (x+sz//2-t.get_width()//2, y+sz//2-t.get_height()//2))

        for ft in self.flip_tiles:
            if not any(ft.x == self._tile_pos(r,c)[0] and ft.y == self._tile_pos(r,c)[1]
                       for r in range(self.max_attempts) for c in range(self.word_length)):
                ft.draw(self.screen, self.font_tile)

        kw, kh = 34, 38
        ky0 = gy + self.max_attempts*(sz+gap) + 18
        for ri, row in enumerate(KB_ROWS):
            rw  = sum((kw*2+4 if k in ("ENTER","<<") else kw+4) for k in row)
            kx  = 50 + (420-rw)//2
            for key in row:
                w2 = kw*2 if key in ("ENTER","<<") else kw
                ky = ky0 + ri*(kh+5)
                c  = TILE_COLORS.get(self.key_colors.get(key), KEY_DEF)
                pygame.draw.rect(self.screen, c, (kx, ky, w2, kh), border_radius=4)
                t = self.font_key.render(key, True, WHITE)
                self.screen.blit(t, (kx+w2//2-t.get_width()//2, ky+kh//2-t.get_height()//2))
                kx += w2+4

        if self.invalid_msg and self.invalid_timer > 0:
            tw = self.font_sm.render(self.invalid_msg, True, WHITE)
            px, py, pw, ph = WIDTH//2-tw.get_width()//2-10, 60, tw.get_width()+20, 28
            pygame.draw.rect(self.screen, DARK, (px,py,pw,ph), border_radius=4)
            self.screen.blit(tw, (px+10, py+6))

        if self.my_status == STATUS_CORRECT:
            self._text("Correct!", self.font_sm, C_GREEN, 240, 65, center=True)
        elif self.my_status == STATUS_OUT:
            self._text("Out of attempts!", self.font_sm, RED, 240, 65, center=True)

        px, py = 490, 60
        pw, ph = 455, HEIGHT-70

        # Player status
        self._panel(px, py, pw, 230)
        self._text("PLAYERS", self.font_xs, TEAL, px+10, py+8)
        # Show self
        my_color = C_GREEN if self.my_status==STATUS_CORRECT else RED if self.my_status==STATUS_OUT else WHITE
        self._text(f"You ({self.net.username})", self.font_xs, my_color, px+10, py+28)
        for i, p in enumerate(self.opp_status):
            sc = C_GREEN if p["status"]=="correct" else RED if p["status"]=="out" else OFF_WHITE
            bar_w = min(190, p["attempts"]*18)
            pygame.draw.rect(self.screen, PANEL, (px+10, py+50+i*42, 200, 14), border_radius=3)
            pygame.draw.rect(self.screen, sc, (px+10, py+50+i*42, bar_w, 14), border_radius=3)
            self._text(f"{p['username']}", self.font_xs, sc, px+10, py+36+i*42)
            self._text(f"{p['attempts']} tries", self.font_xs, MID_GRAY, px+215, py+50+i*42)

        # Chat
        chat_y = py + 240
        self._panel(px, chat_y, pw, HEIGHT-chat_y-10)
        self._text("CHAT", self.font_xs, TEAL, px+10, chat_y+8)
        max_msgs = (HEIGHT-chat_y-70)//20
        for i, (u, m) in enumerate(self.chat_msgs[-max_msgs:]):
            txt = f"{u}: {m}"[:55]
            self._text(txt, self.font_xs, OFF_WHITE, px+10, chat_y+28+i*20)

        # Chat input
        inp_y = HEIGHT-45
        pygame.draw.rect(self.screen, PANEL, (px, inp_y, pw, 34), border_radius=4)
        border_c = TEAL if self.chat_focused else TILE_BORDER
        pygame.draw.rect(self.screen, border_c, (px, inp_y, pw, 34), 1, border_radius=4)
        placeholder = "Click here to chat..." if not self.chat_focused and not self.chat_input else ""
        txt = self.chat_input[-50:] or placeholder
        tc2 = OFF_WHITE if self.chat_input else MID_GRAY
        self._text(txt, self.font_xs, tc2, px+8, inp_y+10)

    # ROUND END 
    def _draw_round_end(self):
        self._panel(WIDTH//2-280, 40, 560, 520)
        self._text(f"Round {self.round_num} Complete!", self.font_lg, TEAL, WIDTH//2, 65, center=True)
        self._text(f"The word was:", self.font_sm, OFF_WHITE, WIDTH//2, 105, center=True)

        # Show secret word as tiles
        tw = len(self.round_secret)
        tsx= WIDTH//2 - tw*32
        for i, ch in enumerate(self.round_secret):
            rx = tsx + i*60
            pygame.draw.rect(self.screen, C_GREEN, (rx, 120, 54, 54))
            t = self.font_tile.render(ch, True, WHITE)
            self.screen.blit(t, (rx+27-t.get_width()//2, 133))

        # Scores table
        self._text("Round Scores:", self.font_sm, OFF_WHITE, WIDTH//2, 195, center=True)
        for i, sc in enumerate(self.round_scores):
            y2 = 218+i*38
            is_me = sc["username"] == self.net.username
            bg = DARK if is_me else BG
            pygame.draw.rect(self.screen, bg, (WIDTH//2-240, y2, 480, 32), border_radius=4)
            color = GOLD if is_me else WHITE
            self._text(sc["username"], self.font_sm, color, WIDTH//2-220, y2+8)
            self._text(f"+{sc['round_score']} pts", self.font_sm, MINT, WIDTH//2+20, y2+8)
            self._text(f"Total: {sc['total_score']}", self.font_sm, OFF_WHITE, WIDTH//2+140, y2+8)

        # Host controls
        btn_y = 430
        if self.can_next:
            if self.round_num < self.total_rounds:
                self._btn("NEXT ROUND →", WIDTH//2-110, btn_y, 220, 46, C_GREEN, self.font_md)
                self._text("(Only you can advance as host)", self.font_xs, MID_GRAY, WIDTH//2, btn_y+55, center=True)
        else:
            self._text("Waiting for host to start next round...", self.font_sm, MID_GRAY, WIDTH//2, btn_y+15, center=True)

    # GAME END
    def _draw_game_end(self):
        self._panel(WIDTH//2-300, 30, 600, 560)
        self._text("GAME OVER", self.font_xl, TEAL, WIDTH//2, 60, center=True)
        self._text("Final Leaderboard", self.font_md, OFF_WHITE, WIDTH//2, 105, center=True)
        pygame.draw.line(self.screen, PANEL, (WIDTH//2-260,125),(WIDTH//2+260,125),1)

        medals = {1:"#1", 2:"#2", 3:"#3"}
        medal_c = {1:GOLD, 2:OFF_WHITE, 3:(205,127,50)}
        for e in self.leaderboard:
            y2  = 140 + (e["rank"]-1)*60
            is_me = e["username"] == self.net.username
            if is_me:
                pygame.draw.rect(self.screen, DARK, (WIDTH//2-260, y2-4, 520, 52), border_radius=6)

            rank_str = medals.get(e["rank"], f"#{e['rank']}")
            rc = medal_c.get(e["rank"], MID_GRAY)
            self._text(rank_str, self.font_lg, rc, WIDTH//2-230, y2+10)
            color = GOLD if is_me else WHITE
            self._text(e["username"], self.font_md, color, WIDTH//2-160, y2+10)
            self._text(f"{e['score']} pts", self.font_md, MINT, WIDTH//2+120, y2+10)
            if e["rank"] == 1:
                self._text("WINNER!", self.font_xs, GOLD, WIDTH//2+230, y2+15)

        # Buttons
        btn_y = 490
        if self.can_again:
            self._btn("PLAY AGAIN", WIDTH//2-230, btn_y, 200, 44, C_GREEN,  self.font_md)
            self._btn("LEAVE ROOM",   WIDTH//2+30,  btn_y, 200, 44, MID_GRAY, self.font_md)
            self._text("(Host only)", self.font_xs, MID_GRAY, WIDTH//2, btn_y+52, center=True)
        else:
            self._text("Waiting for host...", self.font_sm, MID_GRAY, WIDTH//2, btn_y+15, center=True)

    # INPUT HANDLERS
    def _key_login(self, ev):
        mapping = {"user":("inp_user",12), "room":("inp_room",6), "ip":("inp_ip",40), "tcp":("inp_tcp",5)}
        if ev.key == pygame.K_RETURN:
            self._do_connect()
            return
        if ev.key == pygame.K_TAB:
            tabs = ["user","room","ip","tcp"] if self.show_adv else ["user","room"]
            idx  = tabs.index(self.active_inp) if self.active_inp in tabs else 0
            self.active_inp = tabs[(idx+1)%len(tabs)]
            return
        if ev.key == pygame.K_BACKSPACE:
            attr, _ = mapping.get(self.active_inp, ("inp_user",12))
            setattr(self, attr, getattr(self, attr)[:-1])
        elif ev.unicode:
            attr, maxlen = mapping.get(self.active_inp, ("inp_user",12))
            val = getattr(self, attr)
            if len(val) < maxlen:
                ch = ev.unicode.upper() if self.active_inp == "room" else ev.unicode
                setattr(self, attr, val + ch)

    def _key_game(self, ev):
        if self.chat_focused:
            if ev.key == pygame.K_RETURN:
                if self.chat_input.strip():
                    self.net.chat(self.chat_input.strip())
                    self.chat_input = ""
            elif ev.key == pygame.K_BACKSPACE:
                self.chat_input = self.chat_input[:-1]
            elif ev.key == pygame.K_ESCAPE:
                self.chat_focused = False
            elif ev.unicode:
                self.chat_input += ev.unicode
            return

        if self.my_status != STATUS_GUESSING:
            return

        self.invalid_msg = ""
        if ev.key == pygame.K_RETURN:
            if len(self.cur_input) == self.word_length:
                self.net.guess(self.cur_input)
        elif ev.key == pygame.K_BACKSPACE:
            self.cur_input = self.cur_input[:-1]
        elif ev.unicode and ev.unicode.isalpha() and len(self.cur_input) < self.word_length:
            self.cur_input += ev.unicode.upper()

    def _key_roundend(self, ev):
        if ev.key == pygame.K_RETURN and self.can_next and self.round_num < self.total_rounds:
            self.net.next_round()

    # Click handlers
    def _click_login(self, pos):
        x, y = pos
        LX = 30
        # Mode tabs
        if 55 <= y <= 89:
            if LX <= x <= LX+200: self.login_mode = "create"
            elif LX+225 <= x <= LX+425: self.login_mode = "join"
        # Username box
        if 122 <= y <= 156: self.active_inp = "user"
        # Difficulty / room code
        if 189 <= y <= 223:
            if self.login_mode == "create":
                for i, d in enumerate(["easy","normal","hard"]):
                    if LX+i*150 <= x <= LX+i*150+138:
                        self.sel_diff = d
            else:
                self.active_inp = "room"
        # Advanced toggle
        adv_y = 265 if self.login_mode == "create" else 238
        if adv_y <= y <= adv_y+16:
            self.show_adv = not self.show_adv
        # Advanced inputs
        if self.show_adv:
            if adv_y+35 <= y <= adv_y+65:
                if LX <= x <= LX+260: self.active_inp = "ip"
                elif LX+275 <= x <= LX+430: self.active_inp = "tcp"
        # Connect button
        btn_y = adv_y + (78 if self.show_adv else 28)
        if btn_y <= y <= btn_y+44 and LX+90 <= x <= LX+350:
            self._do_connect()

    def _click_lobby(self, pos):
        x, y = pos
        if self.is_host:
            if 430 <= y <= 476 and WIDTH//2-120 <= x <= WIDTH//2+100:
                self.net.start_game()
            if 430 <= y <= 476 and WIDTH//2+115 <= x <= WIDTH//2+205:
                self._do_leave()
        else:
            if 430 <= y <= 476 and WIDTH//2-80 <= x <= WIDTH//2+80:
                self._do_leave()

    def _click_game(self, pos):
        x, y = pos
        # Chat focus
        if HEIGHT-45 <= y <= HEIGHT-11 and 490 <= x <= 945:
            self.chat_focused = True
        else:
            self.chat_focused = False

        if self.my_status != STATUS_GUESSING or self.chat_focused:
            return

        # On-screen keyboard clicks
        sz  = min(55, 300 // self.word_length)
        gap = 5
        gy  = 80
        kw, kh = 34, 38
        ky0 = gy + self.max_attempts*(sz+gap) + 18
        for ri, row in enumerate(KB_ROWS):
            gw2 = self.word_length*(sz+gap)-gap
            rw  = sum((kw*2+4 if k in ("ENTER","<<") else kw+4) for k in row)
            kx  = 50 + (420-rw)//2
            for key in row:
                w2 = kw*2 if key in ("ENTER","<<") else kw
                ky2 = ky0 + ri*(kh+5)
                if kx <= x <= kx+w2 and ky2 <= y <= ky2+kh:
                    self._kb_press(key)
                kx += w2+4

    def _click_roundend(self, pos):
        x, y = pos
        if self.can_next and self.round_num < self.total_rounds:
            if 430 <= y <= 476 and WIDTH//2-110 <= x <= WIDTH//2+110:
                self.net.next_round()

    def _click_gameend(self, pos):
        x, y = pos
        if self.can_again and 490 <= y <= 534:
            if WIDTH//2-230 <= x <= WIDTH//2-30:
                self.net.play_again()
            elif WIDTH//2+30 <= x <= WIDTH//2+230:
                self.net.disconnect()
                self._full_reset()

    def _kb_press(self, key):
        self.invalid_msg = ""
        if key == "ENTER":
            if len(self.cur_input) == self.word_length:
                self.net.guess(self.cur_input)
        elif key == "<<":
            self.cur_input = self.cur_input[:-1]
        elif len(self.cur_input) < self.word_length:
            self.cur_input += key

    def _full_reset(self):
        self.state      = "login"
        self.error_msg  = ""
        self.inp_user   = ""
        self.inp_room   = ""
        self.room_code  = ""
        self.players    = []
        self.is_host    = False
        self.net        = NetworkClient(self.on_event)
        self._reset_game_state()

    def _do_leave(self):
        """Keluar dari room dan balik ke login screen"""
        self.net.disconnect()
        self._full_reset()

    def _do_connect(self):
        self.error_msg = ""
        if not self.inp_user.strip():
            self.error_msg = "Enter a username"
            return
        host    = self.inp_ip.strip() or self.server_host
        try:
            tcp_p = int(self.inp_tcp) if self.inp_tcp else self.tcp_port
        except:
            tcp_p = self.tcp_port
        if not self.net.connect(host, tcp_p, self.udp_port):
            self.error_msg = f"Cannot connect to {host}:{tcp_p}"
            return
        if self.login_mode == "create":
            self.net.create_room(self.inp_user.strip(), self.sel_diff)
        else:
            if not self.inp_room.strip():
                self.error_msg = "Enter a room code"
                return
            self.net.join_room(self.inp_user.strip(), self.inp_room.strip())

    # Draw helpers
    def _text(self, txt, font, color, x, y, center=False):
        s = font.render(str(txt), True, color)
        if center: self.screen.blit(s, (x - s.get_width()//2, y))
        else:      self.screen.blit(s, (x, y))

    def _btn(self, txt, x, y, w, h, color, font):
        pygame.draw.rect(self.screen, color, (x,y,w,h), border_radius=6)
        s = font.render(txt, True, WHITE)
        self.screen.blit(s, (x+w//2-s.get_width()//2, y+h//2-s.get_height()//2))

    def _input_box(self, val, x, y, w, h, active, font=None):
        font = font or self.font_sm
        pygame.draw.rect(self.screen, DARK, (x,y,w,h), border_radius=4)
        bc = TEAL if active else TILE_BORDER
        pygame.draw.rect(self.screen, bc, (x,y,w,h), 1, border_radius=4)
        s = font.render(val, True, WHITE)
        self.screen.blit(s, (x+8, y+h//2-s.get_height()//2))

    def _panel(self, x, y, w, h):
        pygame.draw.rect(self.screen, DARK, (x,y,w,h), border_radius=8)


# ENTRY POINT
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wordle Multiplayer Client")
    parser.add_argument("--host",     default="127.0.0.1", help="Server IP (default: 127.0.0.1)")
    parser.add_argument("--tcp-port", default=55000, type=int, help="TCP port (default: 55000)")
    parser.add_argument("--udp-port", default=55002, type=int, help="UDP port (default: 55002)")
    args = parser.parse_args()

    app = WordleApp(args.host, args.tcp_port, args.udp_port)
    app.run()
