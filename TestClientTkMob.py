# client_tk.py
import asyncio
import socket
import json
import time
import random
import threading
from datetime import datetime
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
from queue import Queue


class UDPClientTk:
    def __init__(self, root):
        self.root = root
        self.server_host = "127.0.0.1"
        self.server_port = 3333
        self.running = True
        self.connected = False
        self.socket = None
        self.receive_thread = None
        self.ping_thread = None
        self.username = None
        self.client_port = None
        self.running_ping = False  # Флаг для управления автопингом

        # Очередь для сообщений от потока приема
        self.message_queue = Queue()

        self.setup_ui()
        self.after_id = self.root.after(100, self.process_queue)

        # Автопинг каждые 30 секунд при подключении
        self.ping_interval = 30

    def setup_ui(self):
        """Настройка интерфейса"""
        self.root.title("UDP Клиент")
        self.root.geometry("800x565")

        # Фрейм для верхней панели подключения
        connection_frame = tk.Frame(self.root, relief=tk.GROOVE, borderwidth=2)
        connection_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Настройки сервера
        tk.Label(connection_frame, text="Настройки сервера:", font=("Arial", 10, "bold")).grid(row=0, column=0,
                                                                                               columnspan=3,
                                                                                               sticky=tk.W, pady=5)

        tk.Label(connection_frame, text="Хост:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.host_entry = tk.Entry(connection_frame, width=15)
        self.host_entry.grid(row=1, column=1, padx=5)
        self.host_entry.insert(0, self.server_host)

        tk.Label(connection_frame, text="Порт:").grid(row=1, column=2, sticky=tk.W, padx=5)
        self.port_entry = tk.Entry(connection_frame, width=10)
        self.port_entry.grid(row=1, column=3, padx=5)
        self.port_entry.insert(0, str(self.server_port))

        self.update_server_btn = tk.Button(connection_frame, text="Обновить", command=self.update_server_settings)
        self.update_server_btn.grid(row=1, column=4, padx=5)

        # Статус и кнопки управления - разделены на три строки
        status_frame = tk.Frame(self.root)
        status_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Первая строка - статус
        self.status_label = tk.Label(status_frame, text="Статус: Не подключен", fg="red", font=("Arial", 10))
        self.status_label.pack(anchor=tk.W, padx=10, pady=2)

        # Вторая строка - кнопки подключения/отключения
        connect_row = tk.Frame(status_frame)
        connect_row.pack(fill=tk.X, pady=2)

        self.connect_btn = tk.Button(connect_row, text="Подключиться", command=self.connect_to_server, bg="lightgreen")
        self.connect_btn.pack(side=tk.LEFT, padx=2)

        self.disconnect_btn = tk.Button(connect_row, text="Отключиться", command=self.disconnect_from_server,
                                        state=tk.DISABLED, bg="lightcoral")
        self.disconnect_btn.pack(side=tk.LEFT, padx=2)

        # Третья строка - дополнительные кнопки
        actions_row = tk.Frame(status_frame)
        actions_row.pack(fill=tk.X, pady=2)

        self.users_btn = tk.Button(actions_row, text="Список пользователей", command=self.get_users_list)
        self.users_btn.pack(side=tk.LEFT, padx=2)

        self.ping_btn = tk.Button(actions_row, text="Проверить пинг", command=self.check_ping_manual)
        self.ping_btn.pack(side=tk.LEFT, padx=2)

        # Панель информации о клиенте
        client_info_frame = tk.Frame(self.root, relief=tk.GROOVE, borderwidth=1)
        client_info_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        tk.Label(client_info_frame, text="Информация о клиенте:", font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=5)

        self.client_info_label = tk.Label(client_info_frame, text="Имя: - | Порт: -")
        self.client_info_label.pack(anchor=tk.W, padx=5, pady=2)

        # История сообщений
        chat_frame = tk.LabelFrame(self.root, text="Чат", relief=tk.GROOVE, borderwidth=2)
        chat_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.chat_history = scrolledtext.ScrolledText(chat_frame, height=15, state='disabled', font=("Arial", 10))
        self.chat_history.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Панель ввода сообщений
        input_frame = tk.Frame(self.root)
        input_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        tk.Label(input_frame, text="Сообщение:").pack(side=tk.LEFT, padx=(0, 5))

        self.message_entry = tk.Entry(input_frame)
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.message_entry.bind("<Return>", self.send_message_event)
        self.message_entry.config(state=tk.DISABLED)

        self.send_btn = tk.Button(input_frame, text="Отправить", command=self.send_message, state=tk.DISABLED)
        self.send_btn.pack(side=tk.RIGHT)

        # Меню
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Настройки сервера...", command=self.show_server_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.on_closing)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Справка", menu=help_menu)
        help_menu.add_command(label="О программе", command=self.show_about)

    def update_server_settings(self):
        """Обновить настройки сервера"""
        host = self.host_entry.get().strip()
        port_str = self.port_entry.get().strip()

        if not host:
            messagebox.showerror("Ошибка", "Хост не может быть пустым")
            return

        if not port_str:
            messagebox.showerror("Ошибка", "Порт не может быть пустым")
            return

        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                messagebox.showerror("Ошибка", "Порт должен быть в диапазоне 1-65535")
                return

            self.server_host = host
            self.server_port = port

            self.queue_message('status', f"Настройки обновлены: {host}:{port}")

        except ValueError:
            messagebox.showerror("Ошибка", "Порт должен быть числом")

    def show_server_settings(self):
        """Открыть диалог настроек сервера"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Настройки сервера")
        settings_window.geometry("400x200")
        settings_window.transient(self.root)
        settings_window.grab_set()

        tk.Label(settings_window, text="Настройки подключения", font=("Arial", 12, "bold")).pack(pady=10)

        frame = tk.Frame(settings_window)
        frame.pack(pady=20, padx=20)

        tk.Label(frame, text="Хост сервера:", width=15, anchor=tk.W).grid(row=0, column=0, pady=5, sticky=tk.W)
        host_entry = tk.Entry(frame, width=20)
        host_entry.grid(row=0, column=1, pady=5, padx=5)
        host_entry.insert(0, self.server_host)

        tk.Label(frame, text="Порт сервера:", width=15, anchor=tk.W).grid(row=1, column=0, pady=5, sticky=tk.W)
        port_entry = tk.Entry(frame, width=20)
        port_entry.grid(row=1, column=1, pady=5, padx=5)
        port_entry.insert(0, str(self.server_port))

        def save_settings():
            host = host_entry.get().strip()
            port_str = port_entry.get().strip()

            if not host:
                messagebox.showerror("Ошибка", "Хост не может быть пустым")
                return

            if not port_str:
                messagebox.showerror("Ошибка", "Порт не может быть пустым")
                return

            try:
                port = int(port_str)
                if port < 1 or port > 65535:
                    messagebox.showerror("Ошибка", "Порт должен быть в диапазоне 1-65535")
                    return

                self.server_host = host
                self.server_port = port

                # Обновляем поля в основном окне
                self.host_entry.delete(0, tk.END)
                self.host_entry.insert(0, host)
                self.port_entry.delete(0, tk.END)
                self.port_entry.insert(0, str(port))

                self.queue_message('status', f"Настройки сервера изменены: {host}:{port}")
                settings_window.destroy()

            except ValueError:
                messagebox.showerror("Ошибка", "Порт должен быть числом")

        def cancel():
            settings_window.destroy()

        button_frame = tk.Frame(settings_window)
        button_frame.pack(pady=20)

        tk.Button(button_frame, text="Сохранить", command=save_settings, bg="lightgreen").pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="Отмена", command=cancel).pack(side=tk.LEFT, padx=10)

    def add_message(self, message, color="black"):
        """Добавить сообщение в историю"""
        self.chat_history.configure(state='normal')
        self.chat_history.insert(tk.END, message + "\n")
        self.chat_history.configure(state='disabled')
        self.chat_history.see(tk.END)

    def process_queue(self):
        """Обработка очереди сообщений из потока приема"""
        try:
            while not self.message_queue.empty():
                msg_type, data = self.message_queue.get_nowait()

                if msg_type == 'message':
                    from_user = data.get('from', 'Неизвестно')
                    text = data.get('text', '')
                    msg_time = data.get('time', '')

                    # Не показываем свои сообщения
                    if from_user != self.username:
                        self.add_message(f"[{msg_time}] {from_user}: {text}")

                elif msg_type == 'system':
                    self.add_message(f"Система: {data}")

                elif msg_type == 'error':
                    self.add_message(f"Ошибка: {data}")

                elif msg_type == 'status':
                    self.add_message(f"--- {data} ---")

                elif msg_type == 'ping_result':
                    self.add_message(f"Пинг: {data} мс")

                elif msg_type == 'client_info':
                    self.client_info_label.config(text=data)

        except:
            pass

        self.root.after(100, self.process_queue)

    def queue_message(self, msg_type, data):
        """Добавить сообщение в очередь"""
        self.message_queue.put((msg_type, data))

    def create_socket(self):
        """Создание сокета"""
        try:
            # Если сокет уже есть - закрываем его
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass

            # Генерируем случайный порт
            self.client_port = random.randint(10000, 60000)

            # Создаем сокет
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('0.0.0.0', self.client_port))
            self.socket.settimeout(2.0)

            # Обновляем информацию о клиенте
            self.queue_message('client_info',
                               f"Имя: {self.username if self.username else 'не установлено'} | Порт клиента: {self.client_port}")

            return True

        except Exception as e:
            self.queue_message('error', f"Ошибка создания сокета: {e}")
            self.socket = None
            return False

    def send_and_wait(self, message, timeout=3.0):
        """Отправка сообщения и ожидание ответа"""
        if not self.socket:
            self.queue_message('error', "Сокет не создан")
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
                    continue
                except Exception:
                    continue

            return None

        except Exception as e:
            self.queue_message('error', f"Ошибка при отправке: {e}")
            return None

    def send_ping(self):
        """Отправка ping и получение результата (для авто-пинга)"""
        if not self.connected or not self.socket:
            return None

        ping_msg = json.dumps({'type': 'ping', 'data': 'ping'})
        start_time = time.time()

        response = self.send_and_wait(ping_msg, timeout=2.0)

        if response and response.get('type') == 'pong':
            ping_time = int((time.time() - start_time) * 1000)
            return ping_time
        else:
            return None

    def check_ping_manual(self):
        """Ручная проверка пинга (по кнопке)"""
        if not self.connected:
            messagebox.showerror("Ошибка", "Нет подключения")
            return

        ping_time = self.send_ping()

        if ping_time is not None:
            self.queue_message('ping_result', ping_time)
        else:
            self.queue_message('error', "Не удалось проверить пинг")

    def connect_to_server(self):
        """Подключение к серверу"""
        # Проверяем настройки сервера
        host = self.host_entry.get().strip()
        port_str = self.port_entry.get().strip()

        if not host:
            messagebox.showerror("Ошибка", "Хост сервера не может быть пустым")
            return

        if not port_str:
            messagebox.showerror("Ошибка", "Порт сервера не может быть пустым")
            return

        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                messagebox.showerror("Ошибка", "Порт должен быть в диапазоне 1-65535")
                return

            self.server_host = host
            self.server_port = port

        except ValueError:
            messagebox.showerror("Ошибка", "Порт должен быть числом")
            return

        # Запрашиваем имя пользователя
        username = simpledialog.askstring("Подключение",
                                          f"Подключение к {host}:{port}\n\nВведите имя пользователя:")

        if not username:
            return

        # Валидация имени
        if len(username) < 2:
            messagebox.showerror("Ошибка", "Имя должно быть не менее 2 символов")
            return

        if len(username) > 20:
            messagebox.showerror("Ошибка", "Имя должно быть не более 20 символов")
            return

        # Проверка на разрешенные символы
        allowed_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
        if not all(c in allowed_chars for c in username):
            messagebox.showerror("Ошибка", "Только буквы латиницы, цифры и _")
            return

        # Первый символ должен быть буквой
        if not username[0].isalpha():
            messagebox.showerror("Ошибка", "Имя должно начинаться с буквы")
            return

        self.username = username

        # Создаем сокет
        if not self.create_socket():
            return False

        # Формируем команду подключения
        connect_cmd = f"/connect {self.username}:{self.client_port}"

        # Отправляем и ждем ответ
        response = self.send_and_wait(connect_cmd, timeout=5.0)

        if response:
            if response.get('type') == 'response' and response.get('data') == 'CONNECTED':
                self.connected = True
                self.update_ui_state()
                self.queue_message('status', f"Подключен как {self.username} к {host}:{port}")

                # Запускаем поток для приема сообщений
                if self.receive_thread is None or not self.receive_thread.is_alive():
                    self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
                    self.receive_thread.start()

                # Запускаем автопинг
                self.start_auto_ping()

                return True
            else:
                error_msg = response.get('data', 'Неизвестная ошибка')
                messagebox.showerror("Ошибка подключения", error_msg)
                return False
        else:
            messagebox.showerror("Ошибка", f"Сервер {host}:{port} не ответил")
            return False

    def disconnect_from_server(self):
        """Отключение от сервера"""
        if not self.connected:
            return True

        response = self.send_and_wait("/disconnect", timeout=3.0)

        if response and response.get('type') == 'response' and response.get('data') == 'DISCONNECTED':
            self.connected = False
            self.username = None
            self.update_ui_state()
            self.queue_message('status', f"Отключен от сервера {self.server_host}:{self.server_port}")

            # Останавливаем автопинг
            self.stop_auto_ping()
        else:
            self.connected = False
            self.username = None
            self.update_ui_state()
            self.queue_message('status', "Отключен (без подтверждения)")

            # Останавливаем автопинг
            self.stop_auto_ping()

        return True

    def send_message(self, event=None):
        """Отправка сообщения"""
        message = self.message_entry.get().strip()
        if not message:
            return

        if not self.connected:
            messagebox.showerror("Ошибка", "Нет подключения к серверу")
            return

        # Очищаем поле ввода
        self.message_entry.delete(0, tk.END)

        # Отображаем свое сообщение
        current_time = datetime.now().strftime("%H:%M:%S")
        self.add_message(f"[{current_time}] Вы: {message}")

        # Отправляем на сервер
        response = self.send_and_wait(message, timeout=5.0)

        if not response:
            self.queue_message('error', "Нет ответа от сервера")

    def send_message_event(self, event):
        """Обработчик события Enter"""
        self.send_message()
        return "break"  # Предотвращаем перенос строки

    def get_users_list(self):
        """Получить список пользователей"""
        if not self.connected:
            messagebox.showerror("Ошибка", "Нет подключения")
            return

        response = self.send_and_wait("/users", timeout=3.0)

        if response and response.get('type') == 'response':
            data = response.get('data', {})
            users = data.get('users', [])
            count = data.get('count', 0)

            users_window = tk.Toplevel(self.root)
            users_window.title(f"Список пользователей - {self.server_host}:{self.server_port}")
            users_window.geometry("300x400")

            tk.Label(users_window, text=f"Всего пользователей: {count}", font=("Arial", 10, "bold")).pack(pady=5)

            listbox = tk.Listbox(users_window, font=("Arial", 10))
            listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            for user in users:
                listbox.insert(tk.END, user)

            scrollbar = tk.Scrollbar(listbox)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            listbox.config(yscrollcommand=scrollbar.set)
            scrollbar.config(command=listbox.yview)

        else:
            self.queue_message('error', "Не удалось получить список пользователей")

    def receive_messages(self):
        """Прием асинхронных сообщений от сервера"""
        while self.running and self.connected and self.socket:
            try:
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
                            self.queue_message('message', msg_data)

                        elif msg_type == 'system':
                            self.queue_message('system', msg_data)

                        elif msg_type == 'ping':
                            # Автоответ на пинг от сервера
                            pong_msg = json.dumps({'type': 'pong', 'data': 'pong'})
                            self.socket.sendto(pong_msg.encode('utf-8'),
                                               (self.server_host, self.server_port))

                    except json.JSONDecodeError:
                        pass

                except socket.timeout:
                    continue
                except Exception:
                    continue

            except Exception:
                continue

    def start_auto_ping(self):
        """Запуск автоматического пинга"""
        if self.ping_thread and self.ping_thread.is_alive():
            return

        self.running_ping = True
        self.ping_thread = threading.Thread(target=self.auto_ping_loop, daemon=True)
        self.ping_thread.start()

    def stop_auto_ping(self):
        """Остановка автоматического пинга"""
        self.running_ping = False

    def auto_ping_loop(self):
        """Цикл автоматического пинга"""
        failed_pings = 0
        max_failed_pings = 3

        while self.running_ping and self.connected:
            time.sleep(self.ping_interval)

            if not self.connected or not self.running_ping:
                break

            # Отправляем пинг
            ping_time = self.send_ping()

            if ping_time is not None:
                failed_pings = 0
            else:
                failed_pings += 1
                self.queue_message('error', f"Автопинг не удался ({failed_pings}/{max_failed_pings})")

                if failed_pings >= max_failed_pings:
                    self.queue_message('error', "Слишком много неудачных пингов. Проверьте соединение.")
                    break

    def update_ui_state(self):
        """Обновление состояния UI"""
        if self.connected:
            self.status_label.config(text=f"Статус: Подключен как {self.username}", fg="green")
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
            self.users_btn.config(state=tk.NORMAL)
            self.ping_btn.config(state=tk.NORMAL)
            self.send_btn.config(state=tk.NORMAL)
            self.message_entry.config(state=tk.NORMAL)

            # Обновляем информацию о сервере
            self.host_entry.config(state=tk.DISABLED)
            self.port_entry.config(state=tk.DISABLED)
            self.update_server_btn.config(state=tk.DISABLED)
        else:
            self.status_label.config(text="Статус: Не подключен", fg="red")
            self.connect_btn.config(state=tk.NORMAL)
            self.disconnect_btn.config(state=tk.DISABLED)
            self.users_btn.config(state=tk.DISABLED)
            self.ping_btn.config(state=tk.DISABLED)
            self.send_btn.config(state=tk.DISABLED)
            self.message_entry.config(state=tk.DISABLED)

            # Разблокируем поля настроек
            self.host_entry.config(state=tk.NORMAL)
            self.port_entry.config(state=tk.NORMAL)
            self.update_server_btn.config(state=tk.NORMAL)

    def show_about(self):
        """Показать информацию о программе"""
        messagebox.showinfo("О программе",
                            "UDP Клиент с графическим интерфейсом\n\n"
                            "Функции:\n"
                            "- Настройка хоста и порта сервера\n"
                            "- Подключение/отключение к серверу\n"
                            "- Обмен сообщениями в реальном времени\n"
                            "- Список активных пользователей\n"
                            "- Проверка пинга\n"
                            "- Автоматическое поддержание соединения\n\n"
                            f"Текущий сервер: {self.server_host}:{self.server_port}")

    def on_closing(self):
        """Обработка закрытия окна"""
        if self.connected:
            if messagebox.askyesno("Подтверждение", "Вы подключены к серверу. Отключиться перед выходом?"):
                self.disconnect_from_server()

        self.running = False
        self.stop_auto_ping()

        if self.socket:
            try:
                self.socket.close()
            except:
                pass

        if self.after_id:
            self.root.after_cancel(self.after_id)

        self.root.destroy()

    def run(self):
        """Запуск клиента"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


def main():
    """Точка входа"""
    root = tk.Tk()
    client = UDPClientTk(root)
    client.run()


if __name__ == "__main__":
    main()