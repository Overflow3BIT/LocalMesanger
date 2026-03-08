# TestServer.py
import random
import socket
import threading
import json
import time
from datetime import datetime

# ========== НАСТРОЙКИ ==========
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 3333
MAX_CLIENTS = 10
PING_INTERVAL = 60
PING_TIMEOUT = 10


def is_valid_port(port_string):
    port_string = port_string.strip()
    if not port_string:
        return False

    if len(port_string) not in [4, 5]:
        return False

    if not port_string.isdigit():
        return False

    port = int(port_string)

    if port < 1 or port > 65535:
        return False

    return True

def is_valid_ip(ip_string):
    parts = ip_string.split('.')

    if len(parts) != 4:
        return False

    for part in parts:
        if not part:
            return False

        if not part.isdigit():
            return False

        if len(part) > 1 and part[0] == '0':
            return False

        num = int(part)
        if num < 0 or num > 255:
            return False

    return True

SHS = True
while SHS == True:
    InpSH = str(input("SERVER_HOST: "))
    if InpSH == "exit":
        exit(1)
    elif InpSH != "":
        if is_valid_ip(InpSH):
            SERVER_HOST = InpSH
            SHS = False
    else:
        SHS = False

SPS = True
while SPS == True:
    InpSP = str(input("SERVER_PORT: "))
    if InpSP == "exit":
        exit(1)
    elif InpSP != "":
        if is_valid_port(InpSP):
            SERVER_PORT = int(InpSP)
            SPS = False
    else:
        SERVER_PORT = random.randint(1000, 65535)
        SPS = False

# Запрещенные имена
FORBIDDEN_NAMES = {'admin', 'administrator', 'server', 'root', 'system'}


# ===============================

def validate_username(username):
    """Валидация имени пользователя"""
    if not username:
        return False, "Имя не может быть пустым"

    if len(username) < 2:
        return False, "Имя должно быть не менее 2 символов"

    if len(username) > 20:
        return False, "Имя должно быть не более 20 символов"

    # Разрешенные символы: буквы, цифры, подчеркивание
    allowed_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
    if not all(c in allowed_chars for c in username):
        return False, "Только буквы латиницы, цифры и _"

    # Первый символ должен быть буквой
    if not username[0].isalpha():
        return False, "Имя должно начинаться с буквы"

    # Проверка на запрещенные имена
    if username.lower() in FORBIDDEN_NAMES:
        return False, "Это имя запрещено"

    return True, "OK"


class UDPServer:
    def __init__(self, host=SERVER_HOST, port=SERVER_PORT, max_clients=MAX_CLIENTS):
        self.host = host
        self.port = port
        self.max_clients = max_clients
        self.running = True
        self.socket = None
        self.clients = {}  # {client_addr: {username, client_port, ...}}
        self.usernames = {}  # {username: client_addr}
        self.lock = threading.Lock()

        self.ping_thread = threading.Thread(target=self.ping_checker, daemon=True)

    def get_current_time(self):
        return datetime.now().strftime("%H:%M:%S")

    def can_accept_client(self):
        """Проверка возможности принять нового клиента"""
        with self.lock:
            return len(self.clients) < self.max_clients

    def is_username_taken(self, username):
        """Проверка занятости имени"""
        with self.lock:
            return username in self.usernames

    def is_port_available(self, port, client_addr):
        """Проверка доступности порта"""
        if port == self.port:
            return False

        with self.lock:
            for addr, client_info in self.clients.items():
                if addr != client_addr and client_info.get('client_port') == port:
                    return False

        return True

    def add_client(self, client_addr, username, client_port):
        """Добавление нового клиента"""
        with self.lock:
            if client_addr in self.clients:
                return False

            if username in self.usernames:
                return False

            current_time = time.time()
            self.clients[client_addr] = {
                'username': username,
                'client_port': client_port,
                'ip': client_addr[0],
                'server_port': client_addr[1],
                'last_seen': current_time,
                'last_ping': current_time,
                'message_count': 0,
                'connected_at': current_time,
                'ping_response': True
            }

            self.usernames[username] = client_addr

            print(f"[{self.get_current_time()}] Подключился: {username}")
            print(f"    IP: {client_addr[0]}, Клиентский порт: {client_port}")
            print(f"    Всего: {len(self.clients)}/{self.max_clients}")

            return True

    def remove_client(self, client_addr, reason="отключился"):
        """Удаление клиента"""
        with self.lock:
            if client_addr in self.clients:
                client_info = self.clients[client_addr]
                username = client_info['username']

                # Удаляем из словарей
                del self.clients[client_addr]
                if username in self.usernames:
                    del self.usernames[username]

                print(f"[{self.get_current_time()}] Отключился: {username}")
                print(f"    Причина: {reason}")

                return True
        return False

    def get_client_info(self, client_addr):
        """Получение информации о клиенте"""
        with self.lock:
            if client_addr in self.clients:
                return self.clients[client_addr].copy()
        return None

    def ping_checker(self):
        """Проверка активности клиентов"""
        while self.running:
            time.sleep(PING_INTERVAL)

            with self.lock:
                current_time = time.time()
                clients_to_remove = []

                for client_addr, client_info in self.clients.items():
                    time_since_last_ping = current_time - client_info['last_ping']

                    if time_since_last_ping > PING_TIMEOUT and not client_info['ping_response']:
                        clients_to_remove.append(client_addr)
                    else:
                        self.clients[client_addr]['ping_response'] = False

                        ping_message = {'type': 'ping', 'data': 'ping'}
                        try:
                            self.socket.sendto(json.dumps(ping_message).encode('utf-8'), client_addr)
                        except:
                            pass

                for client_addr in clients_to_remove:
                    self.remove_client(client_addr, "отключен по таймауту")

    def process_connect(self, data, client_addr):
        """Обработка подключения"""
        try:
            # Извлекаем данные из строки
            parts = data.split(':', 1)
            if len(parts) != 2:
                return {'type': 'error', 'data': 'INVALID_FORMAT'}

            username = parts[0].strip()
            try:
                client_port = int(parts[1].strip())
            except ValueError:
                return {'type': 'error', 'data': 'INVALID_PORT'}

            # Проверяем возможность подключения
            if not self.can_accept_client():
                return {'type': 'error', 'data': 'SERVER_FULL'}

            # Валидация имени
            is_valid, message = validate_username(username)
            if not is_valid:
                return {'type': 'error', 'data': f'INVALID_NAME: {message}'}

            # Проверка занятости имени
            if self.is_username_taken(username):
                return {'type': 'error', 'data': 'NAME_TAKEN'}

            # Проверка порта
            if not self.is_port_available(client_port, client_addr):
                return {'type': 'error', 'data': 'PORT_BUSY'}

            # Добавляем клиента
            if self.add_client(client_addr, username, client_port):
                # Оповещаем всех о новом пользователе
                self.broadcast({
                    'type': 'system',
                    'data': f'{username} подключился'
                }, exclude=client_addr)

                return {'type': 'response', 'data': 'CONNECTED'}

            return {'type': 'error', 'data': 'CONNECTION_FAILED'}

        except Exception as e:
            return {'type': 'error', 'data': f'ERROR: {str(e)}'}

    def handle_message(self, raw_data, client_addr):
        """Обработка сообщения"""
        try:
            # Пытаемся разобрать JSON
            try:
                message = json.loads(raw_data)
                msg_type = message.get('type', '')
                msg_data = message.get('data', '')
            except:
                # Если не JSON, обрабатываем как текстовую команду
                msg_type = 'text'
                msg_data = raw_data.decode('utf-8', errors='ignore')

            # Получаем информацию о клиенте
            client_info = self.get_client_info(client_addr)

            if msg_type == 'text':
                # Текстовые команды
                if msg_data.startswith('/connect '):
                    # Подключение: /connect username:port
                    connect_data = msg_data[9:]  # Убираем "/connect "
                    return self.process_connect(connect_data, client_addr)

                elif msg_data == '/disconnect':
                    # Отключение
                    if client_info:
                        username = client_info['username']
                        self.remove_client(client_addr, "отключился")
                        self.broadcast({
                            'type': 'system',
                            'data': f'{username} отключился'
                        })
                        return {'type': 'response', 'data': 'DISCONNECTED'}
                    else:
                        return {'type': 'error', 'data': 'NOT_CONNECTED'}

                elif msg_data == '/ping':
                    # Пинг
                    if client_info:
                        with self.lock:
                            if client_addr in self.clients:
                                self.clients[client_addr]['last_ping'] = time.time()
                                self.clients[client_addr]['ping_response'] = True
                        return {'type': 'pong', 'data': 'pong'}
                    else:
                        return {'type': 'error', 'data': 'NOT_CONNECTED'}

                elif msg_data == '/users':
                    # Список пользователей
                    with self.lock:
                        users = [info['username'] for info in self.clients.values()]
                        return {'type': 'response', 'data': {'users': users, 'count': len(users)}}

                elif msg_data == '/whoami':
                    # Информация о себе
                    if client_info:
                        return {'type': 'response', 'data': {
                            'username': client_info['username'],
                            'port': client_info['client_port']
                        }}
                    else:
                        return {'type': 'error', 'data': 'NOT_CONNECTED'}

                elif msg_data.startswith('/'):
                    # Неизвестная команда
                    return {'type': 'error', 'data': 'UNKNOWN_COMMAND'}

                else:
                    # Обычное сообщение
                    if not client_info:
                        return {'type': 'error', 'data': 'NOT_CONNECTED'}

                    # Обновляем активность
                    with self.lock:
                        if client_addr in self.clients:
                            self.clients[client_addr]['last_seen'] = time.time()
                            self.clients[client_addr]['message_count'] += 1

                    # Логируем
                    username = client_info['username']
                    print(f"[{self.get_current_time()}] {username}: {msg_data}")

                    # ОТПРАВЛЯЕМ ПОДТВЕРЖДЕНИЕ ОТПРАВИТЕЛЮ
                    sender_response = {'type': 'response', 'data': 'MESSAGE_SENT'}

                    # Рассылаем сообщение всем КРОМЕ отправителя
                    self.broadcast({
                        'type': 'message',
                        'data': {
                            'from': username,
                            'text': msg_data,
                            'time': self.get_current_time()
                        }
                    }, exclude=client_addr)

                    return sender_response

            elif msg_type == 'ping':
                # Пинг от клиента
                if client_info:
                    with self.lock:
                        if client_addr in self.clients:
                            self.clients[client_addr]['last_ping'] = time.time()
                            self.clients[client_addr]['ping_response'] = True
                return {'type': 'pong', 'data': 'pong'}

            elif msg_type == 'pong':
                # Ответ на пинг
                if client_info:
                    with self.lock:
                        if client_addr in self.clients:
                            self.clients[client_addr]['last_ping'] = time.time()
                            self.clients[client_addr]['ping_response'] = True
                return None

            else:
                return {'type': 'error', 'data': 'UNKNOWN_TYPE'}

        except Exception as e:
            print(f"[{self.get_current_time()}] Ошибка обработки: {e}")
            return {'type': 'error', 'data': 'PROCESSING_ERROR'}

    def broadcast(self, message, exclude=None):
        """Рассылка сообщения всем клиентам КРОМЕ указанного"""
        with self.lock:
            for addr in self.clients.keys():
                if exclude and addr == exclude:
                    continue

                try:
                    self.socket.sendto(json.dumps(message).encode('utf-8'), addr)
                except:
                    pass

    def start(self):
        """Запуск сервера"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((self.host, self.port))

        print(f"{'═' * 60}")
        print(f"UDP Сервер запущен")
        print(f"{'═' * 60}")
        print(f"Адрес: {self.host}:{self.port}")
        print(f"Максимум пользователей: {self.max_clients}")
        print(f"{'═' * 60}")
        print("Ожидание подключений...")
        print(f"{'═' * 60}")

        self.ping_thread.start()

        while self.running:
            try:
                data, client_addr = self.socket.recvfrom(1024)

                if not data:
                    continue

                # Обрабатываем в отдельном потоке
                threading.Thread(
                    target=self.process_client,
                    args=(data, client_addr),
                    daemon=True
                ).start()

            except KeyboardInterrupt:
                print(f"\n[{self.get_current_time()}] Остановка сервера...")
                self.stop()
                break
            except Exception as e:
                if self.running:
                    print(f"[{self.get_current_time()}] Ошибка: {e}")

    def process_client(self, data, client_addr):
        """Обработка клиента"""
        try:
            response = self.handle_message(data, client_addr)

            if response:
                self.socket.sendto(json.dumps(response).encode('utf-8'), client_addr)

        except Exception as e:
            print(f"[{self.get_current_time()}] Ошибка клиента {client_addr}: {e}")

    def stop(self):
        """Остановка сервера"""
        if self.running:
            self.running = False

            # Оповещаем всех
            for client_addr in list(self.clients.keys()):
                try:
                    self.socket.sendto(json.dumps({
                        'type': 'system',
                        'data': 'Сервер останавливается'
                    }).encode('utf-8'), client_addr)
                except:
                    pass

            if self.socket:
                self.socket.close()

            # Статистика
            with self.lock:
                print(f"\n{'═' * 60}")
                print(f"СТАТИСТИКА")
                print(f"{'═' * 60}")
                print(f"Пользователей: {len(self.clients)}")

                if self.clients:
                    print(f"\nСписок пользователей:")
                    print(f"{'-' * 40}")
                    for client_info in self.clients.values():
                        username = client_info['username']
                        address = f"{client_info['ip']}:{client_info['client_port']}"
                        print(f"{username:20} {address:20}")

            print(f"{'═' * 60}")
            print("Сервер остановлен")


def main():
    server = UDPServer()

    try:
        server.start()
    except Exception as e:
        print(f"Фатальная ошибка: {e}")
    finally:
        server.stop()



if __name__ == "__main__":
    main()