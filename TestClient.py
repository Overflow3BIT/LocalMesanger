# client.py
import socket
import json
import time
import random
import threading
from datetime import datetime

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 3333


class UDPClient:
    def __init__(self):
        self.server_host = SERVER_HOST
        self.server_port = SERVER_PORT
        self.running = True
        self.connected = False
        self.socket = None
        self.receive_thread = None
        self.username = None
        self.client_port = None
        self.waiting_for_response = False
        self.response_lock = threading.Lock()

    def get_current_time(self):
        return datetime.now().strftime("%H:%M:%S")

    def create_socket(self):
        """Создание сокета ОДИН раз"""
        try:
            # Если сокет уже есть - закрываем его
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass

            # Генерируем случайный порт
            self.client_port = random.randint(10000, 60000)

            # СОЗДАЕМ СОКЕТ ОДИН РАЗ
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # ВАЖНО: перед bind нужно установить опцию SO_REUSEADDR
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Привязываем сокет к порту
            self.socket.bind(('0.0.0.0', self.client_port))

            # Устанавливаем НЕБЛОКИРУЮЩИЙ режим с таймаутом
            self.socket.settimeout(2.0)

            return True

        except Exception as e:
            print(f"Ошибка создания сокета: {e}")
            self.socket = None
            return False

    def send_and_wait(self, message, timeout=3.0):
        """Отправка сообщения и ожидание ответа"""
        if not self.socket:
            print("Сокет не создан")
            return None

        try:
            # Отправляем сообщение
            server_address = (self.server_host, self.server_port)
            self.socket.sendto(message.encode('utf-8'), server_address)

            # Ждем ответ с таймаутом
            start_time = time.time()

            while time.time() - start_time < timeout:
                try:
                    data, addr = self.socket.recvfrom(1024)

                    if data:
                        try:
                            return json.loads(data.decode('utf-8'))
                        except json.JSONDecodeError:
                            continue

                except socket.timeout:
                    # Продолжаем ждать до истечения общего таймаута
                    continue
                except Exception:
                    continue

            return None

        except Exception as e:
            print(f"Ошибка при отправке: {e}")
            return None

    def connect_to_server(self):
        """Подключение к серверу"""
        print("\n" + "=" * 40)
        print("ПОДКЛЮЧЕНИЕ К СЕРВЕРУ")
        print("=" * 40)

        # Запрашиваем имя пользователя
        while True:
            username = input("Введите имя пользователя: ").strip()

            if not username:
                print("Имя не может быть пустым")
                continue

            if len(username) < 2:
                print("Имя должно быть не менее 2 символов")
                continue

            if len(username) > 20:
                print("Имя должно быть не более 20 символов")
                continue

            # Проверка на разрешенные символы
            allowed_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
            if not all(c in allowed_chars for c in username):
                print("Только буквы латиницы, цифры и _")
                continue

            # Первый символ должен быть буквой
            if not username[0].isalpha():
                print("Имя должно начинаться с буквы")
                continue

            self.username = username
            break

        # Создаем сокет ОДИН раз
        if not self.create_socket():
            print("Не удалось создать сокет")
            return False

        # Формируем команду подключения
        # ВАЖНО: формат "username:port"
        connect_cmd = f"/connect {self.username}:{self.client_port}"

        # Отправляем и ждем ответ
        response = self.send_and_wait(connect_cmd, timeout=5.0)

        if response:
            if response.get('type') == 'response' and response.get('data') == 'CONNECTED':
                self.connected = True
                print(f"Подключен как {self.username}")

                # Запускаем поток для приема сообщений
                if self.receive_thread is None or not self.receive_thread.is_alive():
                    self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
                    self.receive_thread.start()

                return True
            else:
                error_msg = response.get('data', 'Неизвестная ошибка')
                print(f"Ошибка подключения: {error_msg}")
                return False
        else:
            print("Сервер не ответил")
            return False

    def disconnect_from_server(self):
        """Отключение от сервера"""
        if not self.connected:
            print("Не подключен")
            return True

        print("Отключение от сервера...")

        response = self.send_and_wait("/disconnect", timeout=3.0)

        if response and response.get('type') == 'response' and response.get('data') == 'DISCONNECTED':
            self.connected = False
            self.username = None
            print("Отключен")
        else:
            self.connected = False
            self.username = None
            print("Отключен (без подтверждения)")

        return True

    def send_message(self, text):
        """Отправка текстового сообщения"""
        if not self.connected:
            print("Нет подключения к серверу")
            return False

        response = self.send_and_wait(text, timeout=5.0)

        if response:
            if response.get('type') == 'response' and response.get('data') == 'MESSAGE_SENT':
                return True
            else:
                error_msg = response.get('data', 'Неизвестная ошибка')
                print(f"Ошибка: {error_msg}")
                return False
        else:
            print("Нет ответа от сервера")
            return False

    def check_ping(self):
        """Проверка пинга"""
        if not self.connected:
            print("Нет подключения")
            return None

        print("Проверка пинга...")

        ping_msg = json.dumps({'type': 'ping', 'data': 'ping'})
        start_time = time.time()

        response = self.send_and_wait(ping_msg, timeout=3.0)

        if response and response.get('type') == 'pong':
            ping_time = int((time.time() - start_time) * 1000)
            print(f"Пинг: {ping_time} мс")
            return ping_time
        else:
            print("Не удалось проверить пинг")
            return None

    def receive_messages(self):
        """Прием асинхронных сообщений от сервера"""
        while self.running and self.connected and self.socket:
            try:
                # Устанавливаем короткий таймаут
                self.socket.settimeout(0.5)

                try:
                    data, addr = self.socket.recvfrom(1024)

                    if not data:
                        continue

                    try:
                        message = json.loads(data.decode('utf-8'))
                        msg_type = message.get('type')
                        msg_data = message.get('data')

                        if msg_type == 'message':
                            from_user = msg_data.get('from', 'Неизвестно')
                            text = msg_data.get('text', '')
                            msg_time = msg_data.get('time', '')

                            # Не показываем свои сообщения
                            if from_user != self.username:
                                print(f"\n[{msg_time}] {from_user}: {text}")

                        elif msg_type == 'system':
                            print(f"\n{msg_data}")

                        elif msg_type == 'ping':
                            # Автоответ на пинг
                            pong_msg = json.dumps({'type': 'pong', 'data': 'pong'})
                            self.socket.sendto(pong_msg.encode('utf-8'),
                                               (self.server_host, self.server_port))

                    except json.JSONDecodeError:
                        pass

                except socket.timeout:
                    continue  # Это нормально
                except Exception:
                    continue

            except Exception:
                continue

    def show_status(self):
        """Показать статус"""
        status = "Подключен" if self.connected else "Не подключен"
        user_info = f" как {self.username}" if self.username else ""
        port_info = f", Порт: {self.client_port}" if self.client_port else ""

        print(f"Статус: {status}{user_info}{port_info}")

    def process_command(self, command):
        """Обработка команд"""
        cmd = command.strip()

        if not cmd:
            return True

        cmd_lower = cmd.lower()

        if cmd_lower == '/ping':
            self.check_ping()
            return True

        elif cmd_lower == '/status':
            self.show_status()
            return True

        elif cmd_lower == '/connect':
            if self.connected:
                print("Уже подключен")
            else:
                self.connect_to_server()
            return True

        elif cmd_lower == '/disconnect':
            if self.connected:
                self.disconnect_from_server()
            else:
                print("Не подключен")
            return True

        elif cmd_lower == '/exit' or cmd_lower == '/quit':
            print("\nВыход...")
            self.running = False
            return False

        elif cmd_lower == '/help':
            print("\nДоступные команды:")
            print("  /ping       - Проверить пинг")
            print("  /status     - Показать статус")
            print("  /connect    - Подключиться к серверу")
            print("  /disconnect - Отключиться от сервера")
            print("  /help       - Показать эту справку")
            print("  /exit       - Выйти из программы")
            print("  [текст]     - Отправить сообщение на сервер")
            return True

        elif cmd.startswith('/'):
            print(f"Неизвестная команда: {cmd}")
            print("Используйте /help для списка команд")
            return True

        else:
            # Отправка обычного текстового сообщения
            self.send_message(cmd)
            return True

    def input_loop(self):
        """Основной цикл ввода"""
        print("=" * 40)
        print("Используйте /connect для подключения")
        print("=" * 40 + "\n")

        while self.running:
            try:
                # Показываем приглашение в зависимости от статуса
                if self.connected:
                    prompt = f"<{self.username}> "
                else:
                    prompt = ">>> "

                # Безопасный ввод
                try:
                    user_input = input(prompt).strip()
                except KeyboardInterrupt:
                    print("\n\nДля выхода используйте команду /exit")
                    continue
                except EOFError:
                    print("\n\nИспользуйте /exit для выхода")
                    continue

                # Обрабатываем команду
                should_continue = self.process_command(user_input)
                if not should_continue:
                    break

            except Exception as e:
                print(f"Ошибка ввода: {e}")

    def cleanup(self):
        """Очистка ресурсов"""
        self.running = False

        # Отключаемся от сервера если подключены
        if self.connected:
            try:
                self.disconnect_from_server()
            except:
                pass

        # Закрываем сокет
        if self.socket:
            try:
                self.socket.close()
            except:
                pass

    def run(self):
        """Запуск клиента"""
        print("=" * 40)
        print("UDP Клиент")
        print("=" * 40)
        print(f"Сервер: {self.server_host}:{self.server_port}")

        try:
            self.input_loop()
        except Exception as e:
            print(f"\nОшибка: {e}")
        finally:
            self.cleanup()
            print("\nРабота завершена")


def main():
    """Точка входа"""
    client = UDPClient()
    client.run()


if __name__ == "__main__":
    main()