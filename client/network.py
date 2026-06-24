import socket, threading, sys, os, argparse
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared.protocol import *

DEFAULT_HOST = "127.0.0.1"
TCP_PORT     = 55000
UDP_PORT     = 55002

class NetworkClient:
    def __init__(self, callback):
        self.callback  = callback
        self.tcp_sock  = None
        self.udp_sock  = None
        self.username  = None
        self.running   = False
        self.buffer    = ""
        self.host      = DEFAULT_HOST
        self.tcp_port  = TCP_PORT
        self.udp_port  = UDP_PORT

    def connect(self, host=None, tcp_port=None, udp_port=None):
        self.host     = host     or DEFAULT_HOST
        self.tcp_port = tcp_port or TCP_PORT
        self.udp_port = udp_port or UDP_PORT
        try:
            self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_sock.settimeout(5)
            self.tcp_sock.connect((self.host, self.tcp_port))
            self.tcp_sock.settimeout(None)
            self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_sock.bind(("", 0))
            self.running = True
            threading.Thread(target=self._tcp_listen, daemon=True).start()
            threading.Thread(target=self._udp_listen, daemon=True).start()
            print(f"[NET] Connected to {self.host}:{self.tcp_port}")
            return True
        except Exception as e:
            print(f"[NET] Failed: {e}")
            return False

    def send(self, data):
        try: self.tcp_sock.sendall(encode(data))
        except Exception as e: print(f"[NET] Send error: {e}")

    def register_udp(self):
        try:
            payload = encode(msg_register_udp(self.username))
            self.udp_sock.sendto(payload, (self.host, self.udp_port))
        except: pass

    def _tcp_listen(self):
        while self.running:
            try:
                data = self.tcp_sock.recv(4096).decode("utf-8")
                if not data: break
                self.buffer += data
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    if line.strip():
                        self.callback(decode(line))
            except Exception as e:
                if self.running: print(f"[NET] TCP err: {e}")
                break
        self.running = False
        self.callback({"event": "disconnected"})

    def _udp_listen(self):
        while self.running:
            try:
                self.udp_sock.settimeout(1.0)
                data, _ = self.udp_sock.recvfrom(4096)
                self.callback(decode(data.decode()))
            except socket.timeout: continue
            except Exception as e:
                if self.running: print(f"[NET] UDP err: {e}")
                break

    def create_room(self, username, difficulty):
        self.username = username
        self.send(msg_create_room(username, difficulty))

    def join_room(self, username, room_code):
        self.username = username
        self.send(msg_join_room(username, room_code))

    def start_game(self):  self.send(msg_start_game())
    def next_round(self):  self.send(msg_next_round())
    def play_again(self):  self.send(msg_play_again())
    def guess(self, word): self.send(msg_guess(word))
    def chat(self, msg_):  self.send(msg_chat(msg_))

    def disconnect(self):
        self.running = False
        try: self.send(msg_leave())
        except: pass
        try: self.tcp_sock.close()
        except: pass
        try: self.udp_sock.close()
        except: pass
