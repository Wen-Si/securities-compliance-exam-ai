#!/usr/bin/env python3
"""
证券业风控合规智能考试平台 - 后端API服务
提供跨浏览器的用户注册/登录和数据持久化
启动方式: python3 server.py
默认端口: 8080
"""
import http.server
import json
import os
import hashlib
import time
import uuid
import urllib.parse
from datetime import datetime

PORT = int(os.environ.get('PORT', 8080))
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

os.makedirs(DATA_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, 'users.json')
USER_DATA_DIR = os.path.join(DATA_DIR, 'userdata')
os.makedirs(USER_DATA_DIR, exist_ok=True)

# hash_pwd removed - using front_hash_pwd instead

def hash_pwd_secure(pwd):
    """安全哈希（用于新注册）"""
    return hashlib.sha256(pwd.encode('utf-8')).hexdigest()[:16]

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_user_data(username):
    safe_name = hashlib.md5(username.encode()).hexdigest()
    path = os.path.join(USER_DATA_DIR, f'{safe_name}.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'wrongBook': [],
        'examHistory': [],
        'benefits': {'total': 100, 'used': 0},
        'benefitsHistory': [],
        'lastBenefitsRecover': ''
    }

def save_user_data(username, data):
    safe_name = hashlib.md5(username.encode()).hexdigest()
    path = os.path.join(USER_DATA_DIR, f'{safe_name}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def to_base36(n):
    chars = '0123456789abcdefghijklmnopqrstuvwxyz'
    if n == 0: return '0'
    result = ''
    while n > 0:
        result = chars[n % 36] + result
        n //= 36
    return result

def front_hash_pwd(pwd):
    """模拟前端 hashPwd 函数，保持兼容（与JS的Math.abs(h).toString(36)一致）"""
    h = 0
    for ch in pwd:
        h = ((h << 5) - h) + ord(ch)
        h &= 0xFFFFFFFF
        if h >= 0x80000000:
            h -= 0x100000000
    return 'h' + to_base36(abs(h))

def parse_body(body):
    if not body:
        return {}
    try:
        return json.loads(body)
    except:
        return {}

class APIHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        ts = datetime.now().strftime('%H:%M:%S')
        print(f"[{ts}] {args[0]}")

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(body)

    def send_cors(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_OPTIONS(self):
        self.send_cors()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else ''
        params = parse_body(body)

        if self.path == '/api/register':
            self.handle_register(params)
        elif self.path == '/api/login':
            self.handle_login(params)
        elif self.path == '/api/sync':
            self.handle_sync(params)
        elif self.path == '/api/check-user':
            self.handle_check_user(params)
        else:
            self.send_json({'error': 'Not found'}, 404)

    def do_GET(self):
        if self.path == '/api/user-count':
            users = load_users()
            self.send_json({'count': len(users)})
        elif self.path == '/api/health':
            self.send_json({'status': 'ok', 'time': datetime.now().isoformat()})
        else:
            self.send_json({'error': 'Not found'}, 404)

    def handle_register(self, params):
        username = params.get('username', '').strip()
        password = params.get('password', '').strip()
        client_hash = params.get('hash', '')  # 前端已哈希的密码

        if not username or len(username) < 2:
            self.send_json({'ok': False, 'error': '用户名至少2个字符'})
            return
        if not password or len(password) < 4:
            self.send_json({'ok': False, 'error': '密码至少4个字符'})
            return

        users = load_users()
        for u in users:
            if u['username'] == username:
                self.send_json({'ok': False, 'error': '该用户名已注册'})
                return

        # 如果前端传了hash，使用前端hash；否则用密码重新算
        if client_hash:
            pwd_hash = client_hash
        else:
            pwd_hash = front_hash_pwd(password)

        users.append({
            'username': username,
            'password_hash': pwd_hash,
            'created_at': datetime.now().isoformat()
        })
        save_users(users)

        # 初始化用户数据
        save_user_data(username, load_user_data(username))

        self.send_json({'ok': True, 'username': username})

    def handle_login(self, params):
        username = params.get('username', '').strip()
        password = params.get('password', '').strip()
        client_hash = params.get('hash', '')

        if not username or not password:
            self.send_json({'ok': False, 'error': '请输入用户名和密码'})
            return

        users = load_users()
        pwd_hash = client_hash if client_hash else front_hash_pwd(password)

        for u in users:
            if u['username'] == username:
                if u['password_hash'] == pwd_hash:
                    # 登录成功，返回用户数据
                    user_data = load_user_data(username)
                    self.send_json({
                        'ok': True,
                        'username': username,
                        'data': user_data
                    })
                    return
                else:
                    self.send_json({'ok': False, 'error': '用户名或密码错误'})
                    return

        self.send_json({'ok': False, 'error': '用户名或密码错误'})

    def handle_sync(self, params):
        username = params.get('username', '').strip()
        action = params.get('action', 'pull')  # pull or push
        data = params.get('data', {})

        if not username:
            self.send_json({'ok': False, 'error': '未登录'})
            return

        if action == 'push':
            # 保存客户端数据到服务端
            save_user_data(username, data)
            self.send_json({'ok': True})
        else:
            # 拉取服务端数据
            user_data = load_user_data(username)
            self.send_json({'ok': True, 'data': user_data})

    def handle_check_user(self, params):
        username = params.get('username', '').strip()
        users = load_users()
        exists = any(u['username'] == username for u in users)
        self.send_json({'ok': True, 'exists': exists})


def main():
    server = http.server.HTTPServer(('0.0.0.0', PORT), APIHandler)
    print(f'╔══════════════════════════════════════════════╗')
    print(f'║  证券业风控合规智能考试平台 - 后端服务       ║')
    print(f'║  端口: {PORT:<5}                              ║')
    print(f'║  数据目录: {DATA_DIR:<28}  ║')
    print(f'║  API: http://localhost:{PORT}/api/...          ║')
    print(f'╚══════════════════════════════════════════════╝')
    print(f'\n请用浏览器打开 index.html 访问平台\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务已停止')
        server.server_close()


if __name__ == '__main__':
    main()
