import json
import os
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect

app = Flask(__name__)
app.secret_key = "sim_racing_ultra_secret_2026"

# Шляхи до файлів
SESSIONS_FILE = 'sessions.json'
CONFIG_FILE = 'admin_config.json'

# --- РОБОТА З ДАНИМИ ---

def load_config():
    if not os.path.exists(CONFIG_FILE):
        # Дефолтний конфіг, якщо файлу немає
        default_cfg = {
            "roles": {"admin": {"password": "123", "role": "Admin"}, "owner": {"password": "root", "role": "Owner"}},
            "pc_types": {"Standard": 200, "VIP": 350},
            "promo_codes": {"RACE10": 10}
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_cfg, f, indent=4)
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_pcs():
    if not os.path.exists(SESSIONS_FILE):
        with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f) # Порожній словник - починаємо з нуля
    with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_pcs(pcs):
    with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(pcs, f, indent=4, ensure_ascii=False)

def log_transaction(pc_id, driver, duration, cost, role):
    today = datetime.now().strftime('%Y-%m-%d')
    log_file = f"logs_{today}.txt"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {pc_id} | {driver} | {duration}m | {cost} UAH | By: {role}\n")

# --- ФОНОВИЙ ТАЙМЕР ---

def countdown_worker():
    while True:
        time.sleep(60)
        try:
            pcs = load_pcs()
            changed = False
            for pc in pcs.values():
                if pc['time_left'] > 0 and not pc.get('paused', False):
                    pc['time_left'] -= 1
                    if pc['time_left'] == 0:
                        pc['status'] = "Time Over"
                    changed = True
            if changed:
                save_pcs(pcs)
        except Exception as e:
            print(f"Timer error: {e}")

threading.Thread(target=countdown_worker, daemon=True).start()

# --- МАРШРУТИ (ROUTES) ---

@app.route('/')
def index():
    if 'user' not in session:
        return redirect('/login')
    return render_template('index.html', 
                           pcs=load_pcs(), 
                           club_config=load_config(), 
                           role=session['role'], 
                           user=session['user'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('username'), request.form.get('password')
        cfg = load_config()
        if u in cfg['roles'] and cfg['roles'][u]['password'] == p:
            session.update({'user': u, 'role': cfg['roles'][u]['role']})
            return redirect('/')
        return "Помилка входу!"
    
    # Виправлено: передаємо pcs та club_config, щоб не було помилки UndefinedError
    return render_template('index.html', 
                           login_mode=True, 
                           pcs={}, 
                           club_config=load_config())

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# --- API КЕРУВАННЯ ПК ---

@app.route('/api/add_pc', methods=['POST'])
def add_pc():
    if session.get('role') not in ['Admin', 'Owner']: return jsonify({"status": "error"}), 403
    data, pcs = request.json, load_pcs()
    name = data.get('pc_name')
    if name in pcs: return jsonify({"status": "error", "message": "Вже існує"}), 400
    
    pcs[name] = {
        "id": f"SIM-{int(time.time())}",
        "status": "Free",
        "game": "None",
        "time_left": 0,
        "paused": False,
        "driver": "",
        "type": data.get('type', 'Standard'),
        "conn_mode": data.get('conn_mode', 'Local')
    }
    save_pcs(pcs)
    return jsonify({"status": "success"})

@app.route('/api/delete_pc', methods=['POST'])
def delete_pc():
    if session.get('role') != 'Owner': return jsonify({"status": "error"}), 403
    pc_id, pcs = request.json.get('pc_id'), load_pcs()
    if pc_id in pcs:
        del pcs[pc_id]
        save_pcs(pcs)
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404

@app.route('/api/update_pc', methods=['POST'])
def update_pc():
    if session.get('role') == 'Viewer': return jsonify({"status": "error"}), 403
    data, pcs, cfg = request.json, load_pcs(), load_config()
    pc_id = data.get('pc_id')
    if pc_id in pcs:
        pc = pcs[pc_id]
        if 'add_time' in data:
            mins = int(data['add_time'])
            pc.update({"time_left": pc['time_left'] + mins, "status": "Racing", "paused": False})
            if data.get('driver'): pc['driver'] = data['driver']
            if data.get('game'): pc['game'] = data['game']
            
            rate = cfg['pc_types'].get(pc['type'], 200)
            cost = round((mins / 60) * rate * (1 - cfg['promo_codes'].get(data.get('promo', '').upper(), 0)/100), 2)
            log_transaction(pc_id, pc['driver'], mins, cost, session['user'])
            
        if 'action' in data:
            if data['action'] == 'pause': pc['paused'] = not pc.get('paused', False)
            elif data['action'] == 'stop': pc.update({"time_left": 0, "status": "Free", "driver": "", "paused": False, "game": "None"})
        
        save_pcs(pcs)
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404

@app.route('/api/get_final_stats', methods=['POST'])
def get_final_stats():
    pc_id, pcs = request.json.get('pc_id'), load_pcs()
    if pc_id in pcs:
        pc = pcs[pc_id]
        cfg = load_config()
        return jsonify({"driver": pc['driver'], "rate": cfg['pc_types'].get(pc['type'], 200)})
    return jsonify({"status": "error"}), 404

# Додайте цей маршрут до app.py
@app.route('/api/get_session_summary', methods=['POST'])
def get_session_summary():
    pc_id = request.json.get('pc_id')
    pcs = load_pcs()
    if pc_id in pcs:
        pc = pcs[pc_id]
        cfg = load_config()
        # Розраховуємо ціну (на основі того, що залишилось або було додано)
        rate = cfg['pc_types'].get(pc['type'], 200)
        # Це спрощена логіка, в ідеалі треба зберігати час старту
        return jsonify({
            "pc_id": pc_id,
            "driver": pc['driver'],
            "game": pc['game'],
            "rate": rate
        })
    return jsonify({"status": "error"}), 404

@app.route('/api/save_config', methods=['POST'])
def save_config():
    if session.get('role') != 'Owner': return jsonify({"status": "error"}), 403
    cfg = load_config()
    cfg['pc_types'].update(request.json.get('pc_types', {}))
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)