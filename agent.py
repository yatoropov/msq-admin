import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import os
import sys
import psutil
import webbrowser
import subprocess
import tkinter as tk
from tkinter import messagebox
from PIL import ImageGrab
import threading
import configparser

# --- ПІДТРИМКА РЕСУРСІВ (NIRCMD) ---
def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

NIRCMD = get_resource_path("nircmd.exe")

# --- ЗАВАНТАЖЕННЯ КОНФІГУРАЦІЇ ---
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__), 'agent.conf')

if os.path.exists(config_path):
    config.read(config_path, encoding='utf-8')
    BROKER = config.get('SETTINGS', 'broker_ip', fallback='127.0.0.1')
    PORT = config.getint('SETTINGS', 'port', fallback=1883)
else:
    # Значення за замовчуванням, якщо файлу немає
    BROKER = "127.0.0.1"
    PORT = 1883

PC_NAME = os.environ.get('COMPUTERNAME', 'UnknownPC')
TOPIC_ALL = "commands/all"
TOPIC_INDIVIDUAL = f"commands/{PC_NAME}"

def show_popup(text):
    def run_msg():
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showinfo(f"Повідомлення для {PC_NAME}", text)
        root.destroy()
    threading.Thread(target=run_msg).start()

def on_message(client, userdata, msg):
    try:
        command = msg.payload.decode('utf-8')
        
        if command == "lock":
            os.system("rundll32.exe user32.dll,LockWorkStation")
        
        elif command == "mute":
            subprocess.run([NIRCMD, "mutesysvolume", "1"], shell=True)
        
        elif command == "unmute":
            subprocess.run([NIRCMD, "mutesysvolume", "0"], shell=True)

        elif command == "shutdown":
            os.system("shutdown /s /t 15")
            client.publish(f"reports/{PC_NAME}", "Статус: Вимикається (15 сек)")

        elif command == "screenshot":
            scr_path = os.path.join(os.path.expanduser("~"), "last_screen.png")
            ImageGrab.grab().save(scr_path)
            client.publish(f"reports/{PC_NAME}", f"Скріншот збережено: {scr_path}")

        elif command.startswith("msg "):
            show_popup(command.replace("msg ", ""))

        elif command.startswith("open_url "):
            webbrowser.open(command.replace("open_url ", ""))

        elif command == "get_procs":
            interesting = ['chrome.exe', 'msedge.exe', 'steam.exe', 'valorant.exe', 'cs2.exe']
            found = [p.info['name'] for p in psutil.process_iter(['name']) 
                     if any(t in p.info['name'].lower() for t in interesting)]
            report = f"Процеси: {', '.join(set(found)) if found else 'Чисто'}"
            client.publish(f"reports/{PC_NAME}", report)
            
    except Exception as e:
        client.publish(f"reports/{PC_NAME}", f"Помилка: {str(e)}")

# Ініціалізація MQTT
client = mqtt.Client(CallbackAPIVersion.VERSION2)
client.on_message = on_message

try:
    client.connect(BROKER, PORT, 60)
    client.subscribe([(TOPIC_ALL, 0), (TOPIC_INDIVIDUAL, 0)])
    client.loop_forever()
except:
    pass