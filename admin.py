import tkinter as tk
from tkinter import ttk, messagebox
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import configparser
import os

# --- ЗАВАНТАЖЕННЯ КОНФІГУРАЦІЇ ---
config = configparser.ConfigParser()
config.read('admin.conf', encoding='utf-8')

BROKER = config.get('SERVER', 'broker_ip', fallback='127.0.0.1')
PORT = config.getint('SERVER', 'port', fallback=1883)
PC_LIST = config.get('CLIENTS', 'list', fallback='all').split(', ')

class AdminPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("AlteraAdmin - Контроль Класу")
        self.root.geometry("550x750")

        self.client = mqtt.Client(CallbackAPIVersion.VERSION2)
        self.client.on_message = self.on_report
        
        try:
            self.client.connect(BROKER, PORT, 60)
            self.client.subscribe("reports/#")
            self.client.loop_start()
        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося підключитися до Mac-брокера: {e}")

        tk.Label(root, text="ALTERA SCHOOL - ПАНЕЛЬ КЕРУВАННЯ", font=('Arial', 14, 'bold')).pack(pady=15)

        # Вибір комп'ютера (Combobox)
        t_frame = tk.Frame(root)
        t_frame.pack(pady=5)
        tk.Label(t_frame, text="Оберіть ПК: ", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        self.target_pc = ttk.Combobox(t_frame, values=PC_LIST, width=25, state="readonly")
        self.target_pc.set(PC_LIST[0]) 
        self.target_pc.pack(side=tk.LEFT)

        # Кнопки швидких команд
        btn_grid = tk.Frame(root)
        btn_grid.pack(pady=10)

        actions = [
            ("Блокувати Екрани", "lock"),
            ("Вимкнути Звук", "mute"),
            ("Увімкнути Звук", "unmute"),
            ("Перевірити Процеси", "get_procs"),
            ("Зняти Скріншот", "screenshot"),
            ("ЗАВЕРШИТИ РОБОТУ ПК (15с)", "shutdown")
        ]

        for text, cmd in actions:
            btn = ttk.Button(btn_grid, text=text, width=40, command=lambda c=cmd: self.send(c))
            btn.pack(pady=3)

        # Текстові повідомлення
        tk.Label(root, text="Надіслати повідомлення учням:").pack(pady=(15,0))
        self.msg_entry = ttk.Entry(root, width=55)
        self.msg_entry.pack(pady=5)
        ttk.Button(root, text="Надіслати Текст", command=self.send_msg).pack()

        # Посилання
        tk.Label(root, text="Відкрити посилання (URL):").pack(pady=(15,0))
        self.url_entry = ttk.Entry(root, width=55)
        self.url_entry.insert(0, "https://")
        self.url_entry.pack(pady=5)
        ttk.Button(root, text="Відкрити сайт", command=self.send_url).pack()

        # Лог звітів
        tk.Label(root, text="Звіти від учнівських ПК:").pack(pady=(20,0))
        self.log_area = tk.Text(root, height=12, width=65, font=('Consolas', 9), bg="#f0f0f0")
        self.log_area.pack(padx=10, pady=5)
        ttk.Button(root, text="Очистити список звітів", command=lambda: self.log_area.delete('1.0', tk.END)).pack()

    def on_report(self, client, userdata, msg):
        pc = msg.topic.replace("reports/", "")
        self.log_area.insert(tk.END, f"[{pc}]: {msg.payload.decode()}\n")
        self.log_area.see(tk.END)

    def send(self, cmd):
        if cmd == "shutdown":
            if not messagebox.askyesno("Увага", f"Ви дійсно хочете ВИМКНУТИ {self.target_pc.get()}?"):
                return
        self.client.publish(f"commands/{self.target_pc.get()}", cmd)

    def send_msg(self):
        txt = self.msg_entry.get()
        if txt: self.send(f"msg {txt}")

    def send_url(self):
        url = self.url_entry.get()
        if url: self.send(f"open_url {url}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AdminPanel(root)
    root.mainloop()