from flask import Flask, render_template, request, jsonify
import pyodbc
import hashlib
import os

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/about")
def about():
    return render_template("about.html")


# Cấu hình kết nối MSSQL
def get_db_connection():
    connection = pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;"  # Thay bằng tên hoặc IP của server
        "DATABASE=QLBaoHiem;"
        "UID=sa;"  # Thay bằng username
        "PWD=Matkhau04@;"  # Thay bằng password
    )
    return connection


@app.route("/data")
def data():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT TOP 10 * FROM your_table_name")  # Thay bằng tên bảng của bạn
    rows = cursor.fetchall()
    conn.close()
    return render_template("data.html", data=rows)


@app.route("/check-db")
def check_db():
    try:
        conn = get_db_connection()
        conn.close()
        return "Kết nối cơ sở dữ liệu thành công!"
    except Exception as e:
        return f"Lỗi kết nối cơ sở dữ liệu: {str(e)}"


# API đăng ký
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    full_name = data.get("full_name")
    role = data.get("role")

    if not username or not password or not full_name or not role:
        return jsonify({"error": "Thiếu thông tin đăng ký"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Kiểm tra username đã tồn tại
    cursor.execute("SELECT 1 FROM Users WHERE Username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"error": "Tên đăng nhập đã tồn tại"}), 400

    # Tạo salt và hash mật khẩu
    salt = os.urandom(32)
    password_hash = hashlib.sha256(password.encode('utf-8') + salt).digest()

    # Thêm người dùng vào cơ sở dữ liệu
    cursor.execute(
        "INSERT INTO Users (Username, PasswordHash, PasswordSalt, FullName, Role, IsActive) VALUES (?, ?, ?, ?, ?, 1)",
        (username, password_hash, salt, full_name, role)
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "Đăng ký thành công"}), 201


# API đăng nhập
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Thiếu thông tin đăng nhập"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Lấy thông tin người dùng
    cursor.execute("SELECT UserID, PasswordHash, PasswordSalt FROM Users WHERE Username = ?", (username,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"error": "Tên đăng nhập hoặc mật khẩu không đúng"}), 401

    user_id, stored_hash, salt = user

    # Kiểm tra mật khẩu
    password_hash = hashlib.sha256(password.encode('utf-8') + salt).digest()
    if password_hash != stored_hash:
        conn.close()
        return jsonify({"error": "Tên đăng nhập hoặc mật khẩu không đúng"}), 401

    conn.close()
    return jsonify({"message": "Đăng nhập thành công", "user_id": user_id}), 200


if __name__ == "__main__":
    app.run(debug=True)
