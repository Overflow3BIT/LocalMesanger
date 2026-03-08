# client_tk_mobile.py
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
        self.running_ping = False

        # Очередь для сообщений от потока приема
        self.message_queue = Queue()

        self.setup_ui()
        self.after_id = self.root.after(100, self.process_queue)

        # Автопинг каждые 30 секунд при подключении
        self.ping_interval = 30

    def setup_ui(self):
        """Настройка интерфейса для мобильных устройств"""
        self.root.title("UDP Клиент")

        # Устанавливаем размер под мобильные экраны
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Для телефонов делаем почти полный экран
        if screen_width <= 480:  # Типичная ширина телефона
            width = screen_width - 10
            height = screen_height - 50
        else:
            width = 400
            height = 650

        self.root.geometry(f"{width}x{height}")

        # Основной контейнер с прокруткой для всего интерфейса
        main_canvas = tk.Canvas(self.root, highlightthickness=0)
        scrollbar = tk.Scrollbar(self.root, orient="vertical", command=main_canvas.yview)
        scrollable_frame = tk.Frame(main_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Привязка колесика мыши для прокрутки
        def _on_mousewheel(event):
            main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        main_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Фрейм для верхней панели подключения (компактный)
        connection_frame = tk.Frame(scrollable_frame, relief=tk.GROOVE, borderwidth=1, bg='#f0f0f0')
        connection_frame.pack(side=tk.TOP, fill=tk.X, padx=3, pady=3)

        # Заголовок настроек
        tk.Label(connection_frame, text="Сервер:", font=("Arial", 9, "bold"),
                 bg='#f0f0f0').pack(anchor=tk.W, padx=5, pady=(2, 0))

        # Первая строка - хост и порт
        server_row1 = tk.Frame(connection_frame, bg='#f0f0f0')
        server_row1.pack(fill=tk.X, padx=5, pady=2)

        tk.Label(server_row1, text="Хост:", font=("Arial", 8), bg='#f0f0f0').pack(side=tk.LEFT)
        self.host_entry = tk.Entry(server_row1, width=12, font=("Arial", 8))
        self.host_entry.pack(side=tk.LEFT, padx=(2, 5))
        self.host_entry.insert(0, self.server_host)

        tk.Label(server_row1, text="Порт:", font=("Arial", 8), bg='#f0f0f0').pack(side=tk.LEFT)
        self.port_entry = tk.Entry(server_row1, width=6, font=("Arial", 8))
        self.port_entry.pack(side=tk.LEFT, padx=2)
        self.port_entry.insert(0, str(self.server_port))

        self.update_server_btn = tk.Button(server_row1, text="Обн", font=("Arial", 7),
                                           command=self.update_server_settings, height=1, width=4)
        self.update_server_btn.pack(side=tk.RIGHT)

        # Статус и кнопки управления в одной строке
        control_frame = tk.Frame(scrollable_frame, bg='white')
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=3, pady=2)

        self.status_label = tk.Label(control_frame, text="● Не подключен",
                                     fg="red", font=("Arial", 8), bg='white')
        self.status_label.pack(side=tk.LEFT)

        # Кнопки в строку
        btn_frame = tk.Frame(control_frame, bg='white')
        btn_frame.pack(side=tk.RIGHT)

        self.connect_btn = tk.Button(btn_frame, text="Подкл", command=self.connect_to_server,
                                     bg="#90EE90", font=("Arial", 7), height=1, width=6)
        self.connect_btn.pack(side=tk.LEFT, padx=1)

        self.disconnect_btn = tk.Button(btn_frame, text="Откл", command=self.disconnect_from_server,
                                        state=tk.DISABLED, bg="#FFB6C1", font=("Arial", 7), height=1, width=6)
        self.disconnect_btn.pack(side=tk.LEFT, padx=1)

        # Вторая строка кнопок
        btn_frame2 = tk.Frame(scrollable_frame, bg='white')
        btn_frame2.pack(side=tk.TOP, fill=tk.X, padx=3, pady=2)

        self.users_btn = tk.Button(btn_frame2, text="Пользователи", command=self.get_users_list,
                                   font=("Arial", 8), height=1)
        self.users_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        self.ping_btn = tk.Button(btn_frame2, text="Пинг", command=self.check_ping_manual,
                                  font=("Arial", 8), height=1)
        self.ping_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        # Информация о клиенте (компактная)
        info_frame = tk.Frame(scrollable_frame, relief=tk.GROOVE, borderwidth=1, bg='#e6f3ff')
        info_frame.pack(side=tk.TOP, fill=tk.X, padx=3, pady=2)

        tk.Label(info_frame, text="Информация:", font=("Arial", 7, "bold"),
                 bg='#e6f3ff').pack(anchor=tk.W, padx=2)

        self.client_info_label = tk.Label(info_frame,
                                          text="Имя: - | Порт: -",
                                          font=("Arial", 7), bg='#e6f3ff', wraplength=350)
        self.client_info_label.pack(anchor=tk.W, padx=5, pady=1)

        # Чат
        chat_frame = tk.LabelFrame(scrollable_frame, text="Чат", font=("Arial", 8, "bold"))
        chat_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=3, pady=2)

        self.chat_history = scrolledtext.ScrolledText(chat_frame, height=15,
                                                      state='disabled', font=("Arial", 9),
                                                      wrap=tk.WORD)
        self.chat_history.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Панель ввода сообщений (компактная)
        input_frame = tk.Frame(scrollable_frame, bg='#f5f5f5')
        input_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=3, pady=3)

        # Поле ввода и кнопка в одной строке
        input_row = tk.Frame(input_frame, bg='#f5f5f5')
        input_row.pack(fill=tk.X)

        self.message_entry = tk.Entry(input_row, font=("Arial", 9))
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        self.message_entry.bind("<Return>", self.send_message_event)
        self.message_entry.config(state=tk.DISABLED)

        self.send_btn = tk.Button(input_row, text="Отправить", command=self.send_message,
                                  state=tk.DISABLED, bg="#4CAF50", fg="white",
                                  font=("Arial", 8), width=8, height=1)
        self.send_btn.pack(side=tk.RIGHT)

        # Компактное меню через кнопки
        menu_frame = tk.Frame(scrollable_frame, bg='white')
        menu_frame.pack(side=tk.TOP, fill=tk.X, padx=3, pady=2)

        tk.Button(menu_frame, text="Настройки", command=self.show_server_settings,
                  font=("Arial", 8), height=1).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        tk.Button(menu_frame, text="О программе", command=self.show_about,
                  font=("Arial", 8), height=1).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        tk.Button(menu_frame, text="Выход", command=self.on_closing,
                  font=("Arial", 8), height=1, bg="#FF4444", fg="white").pack(side=tk.LEFT, expand=True, fill=tk.X,
                                                                              padx=1)

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
        """Открыть диалог настроек сервера (компактный)"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Настройки")
        settings_window.geometry("300x200")
        settings_window.transient(self.root)
        settings_window.grab_set()

        tk.Label(settings_window, text="Настройки сервера",
                 font=("Arial", 12, "bold")).pack(pady=10)

        frame = tk.Frame(settings_window)
        frame.pack(pady=20, padx=20, fill=tk.X)

        tk.Label(frame, text="Хост:", width=10, anchor=tk.W).grid(row=0, column=0, pady=5, sticky=tk.W)
        host_entry = tk.Entry(frame, width=20)
        host_entry.grid(row=0, column=1, pady=5, padx=5)
        host_entry.insert(0, self.server_host)

        tk.Label(frame, text="Порт:", width=10, anchor=tk.W).grid(row=1, column=0, pady=5, sticky=tk.W)
        port_entry = tk.Entry(frame, width=20)
        port_entry.grid(row=1, column=1, pady=5, padx=5)
        port_entry.insert(0, str(self.server_port))

        def save_settings():
            host = host_entry.get().strip()
            port_str = port_entry.get().strip()

            if not host or not port_str:
                messagebox.showerror("Ошибка", "Заполните все поля")
                return

            try:
                port = int(port_str)
                if port < 1 or port > 65535:
                    messagebox.showerror("Ошибка", "Порт 1-65535")
                    return

                self.server_host = host
                self.server_port = port

                self.host_entry.delete(0, tk.END)
                self.host_entry.insert(0, host)
                self.port_entry.delete(0, tk.END)
                self.port_entry.insert(0, str(port))

                self.queue_message('status', f"Сервер: {host}:{port}")
                settings_window.destroy()

            except ValueError:
                messagebox.showerror("Ошибка", "Порт должен быть числом")

        button_frame = tk.Frame(settings_window)
        button_frame.pack(pady=20)

        tk.Button(button_frame, text="Сохранить", command=save_settings,
                  bg="lightgreen", width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Отмена", command=settings_window.destroy,
                  width=10).pack(side=tk.LEFT, padx=5)

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
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass

            self.client_port = random.randint(10000, 60000)

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('0.0.0.0', self.client_port))
            self.socket.settimeout(2.0)

            self.queue_message('client_info',
                               f"Имя: {self.username if self.username else '-'} | Порт: {self.client_port}")

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
            server_address = (self.server_host, self.server_port)
            self.socket.sendto(message.encode('utf-8'), server_address)

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
        """Отправка ping и получение результата"""
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
        """Ручная проверка пинга"""
        if not self.connected:
            messagebox.showerror("Ошибка", "Нет подключения")
            return

        self.queue_message('status', "Проверка пинга...")
        ping_time = self.send_ping()

        if ping_time is not None:
            self.queue_message('ping_result', ping_time)
        else:
            self.queue_message('error', "Не удалось проверить пинг")

    def connect_to_server(self):
        """Подключение к серверу"""
        host = self.host_entry.get().strip()
        port_str = self.port_entry.get().strip()

        if not host or not port_str:
            messagebox.showerror("Ошибка", "Заполните хост и порт сервера")
            return

        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                messagebox.showerror("Ошибка", "Порт должен быть 1-65535")
                return

            self.server_host = host
            self.server_port = port

        except ValueError:
            messagebox.showerror("Ошибка", "Порт должен быть числом")
            return

        # Запрашиваем имя пользователя
        username = simpledialog.askstring("Подключение",
                                          f"Подключение к {host}:{port}\n\nВведите имя (лат., 2-20 симв.):")

        if not username:
            return

        # Валидация имени
        if len(username) < 2 or len(username) > 20:
            messagebox.showerror("Ошибка", "Имя должно быть от 2 до 20 символов")
            return

        allowed_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
        if not all(c in allowed_chars for c in username):
            messagebox.showerror("Ошибка", "Только латиница, цифры и _")
            return

        if not username[0].isalpha():
            messagebox.showerror("Ошибка", "Имя должно начинаться с буквы")
            return

        self.username = username

        if not self.create_socket():
            return False

        connect_cmd = f"/connect {self.username}:{self.client_port}"

        response = self.send_and_wait(connect_cmd, timeout=5.0)

        if response:
            if response.get('type') == 'response' and response.get('data') == 'CONNECTED':
                self.connected = True
                self.update_ui_state()
                self.queue_message('status', f"Подключен как {self.username} к {host}:{port}")

                if self.receive_thread is None or not self.receive_thread.is_alive():
                    self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
                    self.receive_thread.start()

                self.start_auto_ping()

                return True
            else:
                error_msg = response.get('data', 'Неизвестная ошибка')
                messagebox.showerror("Ошибка подключения", error_msg)
                return False
        else:
            messagebox.showerror("Ошибка", f"Сервер {host}:{port} не отвечает")
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
            self.queue_message('status', f"Отключен от сервера")

            self.stop_auto_ping()
        else:
            self.connected = False
            self.username = None
            self.update_ui_state()
            self.queue_message('status', "Отключен (без подтверждения)")

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

        self.message_entry.delete(0, tk.END)

        current_time = datetime.now().strftime("%H:%M:%S")
        self.add_message(f"[{current_time}] Вы: {message}")

        response = self.send_and_wait(message, timeout=5.0)

        if not response:
            self.queue_message('error', "Нет ответа от сервера")

    def send_message_event(self, event):
        """Обработчик события Enter"""
        self.send_message()
        return "break"

    def get_users_list(self):
        """Получить список пользователей (компактный)"""
        if not self.connected:
            messagebox.showerror("Ошибка", "Нет подключения")
            return

        response = self.send_and_wait("/users", timeout=3.0)

        if response and response.get('type') == 'response':
            data = response.get('data', {})
            users = data.get('users', [])
            count = data.get('count', 0)

            users_window = tk.Toplevel(self.root)
            users_window.title("Пользователи")

            # Компактный размер для телефона
            screen_width = self.root.winfo_screenwidth()
            width = min(300, screen_width - 40)
            users_window.geometry(f"{width}x400")

            tk.Label(users_window, text=f"Всего пользователей: {count}",
                     font=("Arial", 10, "bold")).pack(pady=5)

            listbox = tk.Listbox(users_window, font=("Arial", 10))
            listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            for user in users:
                listbox.insert(tk.END, user)

            scrollbar = tk.Scrollbar(listbox)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            listbox.config(yscrollcommand=scrollbar.set)
            scrollbar.config(command=listbox.yview)

            tk.Button(users_window, text="Закрыть",
                      command=users_window.destroy).pack(pady=5)

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

            ping_time = self.send_ping()

            if ping_time is not None:
                failed_pings = 0
            else:
                failed_pings += 1

                if failed_pings >= max_failed_pings:
                    self.queue_message('error', "Потеря связи с сервером")
                    break

    def update_ui_state(self):
        """Обновление состояния UI"""
        if self.connected:
            self.status_label.config(text="● Подключен", fg="green")
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
            self.users_btn.config(state=tk.NORMAL)
            self.ping_btn.config(state=tk.NORMAL)
            self.send_btn.config(state=tk.NORMAL)
            self.message_entry.config(state=tk.NORMAL)

            self.host_entry.config(state=tk.DISABLED)
            self.port_entry.config(state=tk.DISABLED)
            self.update_server_btn.config(state=tk.DISABLED)
        else:
            self.status_label.config(text="● Не подключен", fg="red")
            self.connect_btn.config(state=tk.NORMAL)
            self.disconnect_btn.config(state=tk.DISABLED)
            self.users_btn.config(state=tk.DISABLED)
            self.ping_btn.config(state=tk.DISABLED)
            self.send_btn.config(state=tk.DISABLED)
            self.message_entry.config(state=tk.DISABLED)

            self.host_entry.config(state=tk.NORMAL)
            self.port_entry.config(state=tk.NORMAL)
            self.update_server_btn.config(state=tk.NORMAL)

    def show_about(self):
        """Показать информацию о программе"""
        messagebox.showinfo("О программе",
                            "UDP Клиент для мобильных устройств\n\n"
                            "Функции:\n"
                            "• Чат через UDP\n"
                            "• Список пользователей\n"
                            "• Проверка пинга\n"
                            "• Автоподдержка соединения\n\n"
                            f"Сервер: {self.server_host}:{self.server_port}")

    def on_closing(self):
        """Обработка закрытия окна"""
        if self.connected:
            if messagebox.askyesno("Подтверждение", "Отключиться и выйти?"):
                self.disconnect_from_server()
            else:
                return

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