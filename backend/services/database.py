# backend/services/database.py
import pymysql
import os
import datetime

# 数据库配置（从环境变量读取，适配 Docker 和本地开发）
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '127.0.0.1'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'root123'),
    'database': os.getenv('DB_NAME', 'ai_assistant'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}


def get_connection():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG)


def init_database():
    """初始化数据库表（如果不存在）"""
    conn = get_connection()
    cursor = conn.cursor()

    # 用户表
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS users
                   (
                       id
                       INT
                       AUTO_INCREMENT
                       PRIMARY
                       KEY,
                       username
                       VARCHAR
                   (
                       255
                   ) UNIQUE NOT NULL,
                       password_hash VARCHAR(255) NOT NULL DEFAULT '',
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                   ''')

    # 会话表
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS sessions
                   (
                       id
                       INT
                       AUTO_INCREMENT
                       PRIMARY
                       KEY,
                       user_id
                       INT
                       NOT
                       NULL,
                       name
                       VARCHAR
                   (
                       255
                   ) NOT NULL,
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                       FOREIGN KEY
                   (
                       user_id
                   ) REFERENCES users
                   (
                       id
                   ) ON DELETE CASCADE
                       ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                   ''')

    # 消息表
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS messages
                   (
                       id
                       INT
                       AUTO_INCREMENT
                       PRIMARY
                       KEY,
                       user_id
                       INT,
                       session_id
                       INT,
                       role
                       VARCHAR
                   (
                       50
                   ) NOT NULL,
                       content TEXT NOT NULL,
                       feedback VARCHAR
                   (
                       50
                   ) DEFAULT NULL,
                       timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                       FOREIGN KEY
                   (
                       user_id
                   ) REFERENCES users
                   (
                       id
                   ) ON DELETE SET NULL,
                       FOREIGN KEY
                   (
                       session_id
                   ) REFERENCES sessions
                   (
                       id
                   )
                     ON DELETE CASCADE
                       ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                   ''')

    # 兼容旧表：添加 password_hash 列（如果不存在）
    try:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NOT NULL DEFAULT ''"
        )
    except Exception:
        pass

    conn.commit()
    conn.close()


# --- 用户操作 ---
import hashlib
import os

def _hash_password(password: str) -> str:
    """PBKDF2 密码哈希"""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ':' + dk.hex()

def _verify_password(password: str, stored: str) -> bool:
    """验证密码"""
    try:
        salt_hex, hash_hex = stored.split(':')
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return dk.hex() == hash_hex
    except (ValueError, AttributeError):
        return False

def register_user(username: str, password: str):
    """注册用户，返回 user_id；用户名已存在则返回 None"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        conn.close()
        return None  # 用户名已存在
    pw_hash = _hash_password(password)
    cursor.execute(
        "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
        (username, pw_hash)
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id

def login_user(username: str, password: str):
    """登录验证，成功返回 user_id，失败返回 None"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, password_hash FROM users WHERE username = %s",
        (username,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    if _verify_password(password, row['password_hash']):
        return row['id']
    return None

def get_or_create_user(username):
    """兼容旧接口：无密码登录（用于测试/迁移）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
    row = cursor.fetchone()
    if row:
        user_id = row['id']
    else:
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, '')",
            (username,)
        )
        user_id = cursor.lastrowid
        conn.commit()
    conn.close()
    return user_id


# --- 会话操作 ---
def create_session(user_id, name="新对话"):
    """创建新会话并返回 session_id"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (user_id, name) VALUES (%s, %s)",
        (user_id, name)
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def get_user_sessions(user_id):
    """返回该用户的所有会话列表 [(session_id, name, created_at), ...]"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, created_at FROM sessions WHERE user_id = %s ORDER BY created_at DESC",
        (user_id,)
    )
    sessions = cursor.fetchall()  # 字典列表
    conn.close()
    # 转换为与原有接口兼容的元组列表
    return [(s['id'], s['name'], s['created_at']) for s in sessions]


def delete_session(session_id):
    """删除会话及其所有消息（通过外键级联）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
    conn.commit()
    conn.close()


def rename_session(session_id, new_name):
    """重命名会话"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET name = %s WHERE id = %s", (new_name, session_id))
    conn.commit()
    conn.close()


# --- 消息操作 ---
def save_message(user_id, session_id, role, content):
    """保存一条消息，返回消息ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (user_id, session_id, role, content) VALUES (%s, %s, %s, %s)",
        (user_id, session_id, role, content)
    )
    msg_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return msg_id


def get_session_messages(session_id, limit=50):
    """获取某个会话的最近消息（从旧到新），返回格式 [(id, role, content, feedback, timestamp), ...]"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT id, role, content, feedback, timestamp
           FROM messages
           WHERE session_id = %s
           ORDER BY id DESC
               LIMIT %s""",
        (session_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    # 转换为兼容的元组列表
    result = [(r['id'], r['role'], r['content'], r['feedback'], r['timestamp']) for r in rows]
    return list(reversed(result))


def clear_session_messages(session_id):
    """清空一个会话的所有消息"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE session_id = %s", (session_id,))
    conn.commit()
    conn.close()


def set_message_feedback(msg_id, feedback):
    """为某条消息设置反馈（👍/👎）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE messages SET feedback = %s WHERE id = %s", (feedback, msg_id))
    conn.commit()
    conn.close()