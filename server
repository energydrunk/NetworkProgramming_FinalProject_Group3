# ============================================================
# server/server.py
# Jalankan: python -m server.server [--host HOST] [--port PORT]
# ============================================================
import socket, threading, select, sys, os, argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared.protocol import *
from shared.game_logic import is_valid_word
from server.room_manager import RoomManager

room_manager = RoomManager()

class ClientHandler(threading.Thread):
    def __init__(self, conn, addr):
        super().__init__(daemon=True)
        self.conn     = conn
        self.addr     = addr
        self.username = None
        self.room     = None
        self.buffer   = ""

    def run(self):
        print(f"[+] {self.addr}")
        try:
            while True:
                data = self.conn.recv(4096).decode("utf-8")
                if not data:
                    break
                self.buffer += data
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    if line.strip():
                        self._handle(decode(line))
        except Exception as e:
            print(f"[ERR] {self.addr}: {e}")
        finally:
            self._disconnect()

    def send(self, data):
        try:
            self.conn.sendall(encode(data))
        except: pass

    def _handle(self, msg):
        action = msg.get("action")
        if   action == "create_room": self._create_room(msg)
        elif action == "join_room":   self._join_room(msg)
        elif action == "start_game":  self._start_game()
        elif action == "next_round":  self._next_round()
        elif action == "play_again":  self._play_again()
        elif action == "guess":       self._guess(msg)
        elif action == "chat":        self._chat(msg)
        elif action == "leave":       self._disconnect()

    def _create_room(self, msg):
        self.username = msg["username"]
        diff = msg.get("difficulty", "normal")
        room = room_manager.create_room(diff, self)
        self.room = room
        self.send(msg_room_created(room.code, diff))
        print(f"[ROOM] {self.username} created {room.code} ({diff})")

    def _join_room(self, msg):
        self.username = msg["username"]
        code = msg["room_code"].upper()
        room = room_manager.get_room(code)
        if not room:
            self.send(msg_error("Room not found"))
            return
        if room.is_full():
            self.send(msg_error("Room is full"))
            return
        if room.game_started:
            self.send(msg_error("Game already in progress"))
            return
        room.add_player(self)
        self.room = room
        pl = room.get_player_list()
        self.send(msg_room_joined(room.code, pl, room.difficulty))
        room.broadcast(msg_player_joined(self.username, pl), exclude=self)
        print(f"[ROOM] {self.username} joined {room.code}")

    def _start_game(self):
        if not self.room:
            self.send(msg_error("Not in a room"))
            return
        if self.room.host != self:
            self.send(msg_error("Only host can start"))
            return
        if len(self.room.players) < 1:
            self.send(msg_error("Need at least 1 player"))
            return
        if self.room.game_started:
            self.send(msg_error("Game already started"))
            return
        diff = DIFFICULTY[self.room.difficulty]
        self.room.broadcast(msg_game_started(diff))
        threading.Thread(target=self.room.run_game, daemon=True).start()

    def _next_round(self):
        if self.room and self.room.waiting_next and self.room.host == self:
            self.room.waiting_next = False

    def _play_again(self):
        if not self.room or self.room.host != self:
            return
        # Reset room state
        room = self.room
        room.game_started = False
        room.current_round = 0
        room.total_scores  = {p.username: 0 for p in room.players}
        room.used_words    = set()
        pl = room.get_player_list()
        room.broadcast(msg_lobby_reset(pl))
        print(f"[ROOM] {room.code} reset for play again")

    def _guess(self, msg):
        if not self.room or not self.room.game_started:
            self.send(msg_error("Game not started"))
            return
        word  = msg["word"].upper()
        diff  = self.room.difficulty
        dconf = DIFFICULTY[diff]
        if len(word) != dconf["length"]:
            self.send(msg_invalid_word(f"Must be {dconf['length']} letters"))
            return
        if not is_valid_word(word, diff):
            self.send(msg_invalid_word("Not in word list"))
            return
        self.room.process_guess(self, word)

    def _chat(self, msg):
        if self.room:
            self.room.broadcast(msg_chat_broadcast(self.username, msg["message"]))

    def _disconnect(self):
        if self.room:
            self.room.remove_player(self)
            pl = self.room.get_player_list()
            self.room.broadcast(msg_player_left(self.username or "?", pl))
            # Transfer host jika host disconnect
            if self.room.host == self and self.room.players:
                self.room.host = self.room.players[0]
                print(f"[ROOM] Host transferred to {self.room.host.username}")
            if self.room.is_empty():
                room_manager.remove_room(self.room.code)
                print(f"[ROOM] {self.room.code} closed")
            # Jika sedang waiting_next dan host disconnect, lanjut otomatis
            if self.room and self.room.waiting_next:
                self.room.waiting_next = False
        try: self.conn.close()
        except: pass
        print(f"[-] {self.addr} ({self.username})")


def start_server(host="0.0.0.0", tcp_port=55000, udp_port=55002):
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp.bind((host, tcp_port))
    tcp.listen(20)
    print(f"[SERVER] TCP  {host}:{tcp_port}")

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        udp.bind((host, udp_port))
        print(f"[SERVER] UDP  {host}:{udp_port}")
    except Exception as e:
        print(f"[WARN] UDP bind failed ({e}), UDP status disabled")
        udp = None

    room_manager.udp_sock = udp
    inputs = [tcp] + ([udp] if udp else [])

    print("[SERVER] Ready! Press Ctrl+C to stop.\n")
    try:
        while True:
            readable, _, _ = select.select(inputs, [], [], 1.0)
            for s in readable:
                if s is tcp:
                    conn, addr = tcp.accept()
                    ClientHandler(conn, addr).start()
                elif udp and s is udp:
                    try:
                        data, addr = udp.recvfrom(1024)
                        m = decode(data.decode())
                        if m.get("action") == "register_udp":
                            room_manager.register_udp(m["username"], addr)
                    except: pass
    except KeyboardInterrupt:
        print("\n[SERVER] Stopped.")
    finally:
        tcp.close()
        if udp: udp.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wordle Multiplayer Server")
    parser.add_argument("--host",     default="0.0.0.0",  help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--tcp-port", default=55000, type=int, help="TCP port (default: 55000)")
    parser.add_argument("--udp-port", default=55002, type=int, help="UDP port (default: 55002)")
    args = parser.parse_args()
    start_server(args.host, args.tcp_port, args.udp_port)
