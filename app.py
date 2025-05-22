from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import pyodbc
import hashlib
import os

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Add a secret key for session management

# Enable CORS for the Flask app
CORS(app, resources={
    r"/*": {
        "origins": ["http://example.com", "http://anotherdomain.com"],  # Thay bằng các domain được phép
        "methods": ["GET", "POST", "PUT", "DELETE"],  # Các method được phép
        "allow_headers": ["Content-Type", "Authorization"]  # Các header được phép
    }
})


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


# @app.route("/data")
# def data():
#     conn = get_db_connection()
#     cursor = conn.cursor()
#     cursor.execute("SELECT TOP 10 * FROM your_table_name")  
#     rows = cursor.fetchall()
#     conn.close()
#     return render_template("data.html", data=rows)


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

     # Kiểm tra quyền của người dùng hiện tại
    current_user = session.get("user")
    if not current_user:
        return jsonify({"error": "Bạn chưa đăng nhập"}), 401

    current_role = current_user.get("role")
    if current_role == "ContractCreator" and role != "Insured":
        return jsonify({"error": "Contract Creator chỉ được tạo tài khoản Insured"}), 403
    elif current_role != "Admin" and current_role != "ContractCreator":
        return jsonify({"error": "Bạn không có quyền tạo tài khoản"}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    # Kiểm tra username đã tồn tại
    cursor.execute("SELECT 1 FROM Users WHERE Username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"error": "Tên đăng nhập đã tồn tại"}), 400

    # Hash mật khẩu bằng SHA2_256
    password_hash = hashlib.sha256(password.encode('utf-8')).digest()

    # Thêm người dùng vào cơ sở dữ liệu
    cursor.execute(
        "INSERT INTO Users (Username, PasswordHash, FullName, Role, IsActive) VALUES (?, ?, ?, ?, 1)",
        (username, password_hash, full_name, role)
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
    cursor.execute("SELECT UserID, Username, FullName, Role, IsActive, PasswordHash FROM Users WHERE Username = ? AND IsActive = 1", (username,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return jsonify({"error": "Tên đăng nhập hoặc mật khẩu không đúng"}), 401

    user_id, username, full_name, role, is_active, stored_hash = user

    # Kiểm tra mật khẩu
    password_hash = hashlib.sha256(password.encode('utf-8')).digest()
    if password_hash != stored_hash:
        conn.close()
        return jsonify({"error": "Tên đăng nhập hoặc mật khẩu không đúng"}), 401

    # Gán SESSION_CONTEXT để RLS hoạt động
    cursor.execute("EXEC sp_set_session_context @key = N'UserID', @value = ?", user_id)

    # Lưu thông tin người dùng vào session
    session["user"] = {
        "user_id": user_id,
        "username": username,
        "full_name": full_name,
        "role": role,
        "is_active": is_active
    }

    conn.close()
    return jsonify({
        "message": "Đăng nhập thành công",
        "user": session["user"]
    }), 200


# API lấy thông tin người dùng hiện tại
@app.route("/current-user", methods=["GET"])
def current_user():
    if "user" in session:
        return jsonify(session["user"])
    return jsonify({"error": "Chưa đăng nhập"}), 401


# API đăng xuất
@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user", None)  # Remove the user from the session
    return jsonify({"message": "Đăng xuất thành công"}), 200


# API lấy danh sách hợp đồng chỉ cho ContractCreator
@app.route("/insurance-types", methods=["GET"])
def get_insurance_types():
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch all insurance types
        cursor.execute("SELECT InsuranceTypeID, TypeName FROM InsuranceTypes")
        insurance_types = [
            {"id": row[0], "name": row[1]} for row in cursor.fetchall()
        ]

        conn.close()
        return jsonify(insurance_types), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API lấy danh sách người được bảo hiểm chỉ cho ContractCreator
@app.route("/insured-persons/<int:person_id>", methods=["GET"])
def get_insured_person_by_id(person_id):
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        # Restrict access to ContractCreator role
        if current_user.get("role") != "ContractCreator":
            return jsonify({"error": "Bạn không có quyền truy cập"}), 403

        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch insured person by ID
        cursor.execute(
            "SELECT InsuredPersonID, FullName, Gender, DateOfBirth, Workplace, PermanentAddress, TemporaryAddress, ContactAddress FROM InsuredPersons WHERE InsuredPersonID = ?",
            (person_id,)
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return jsonify({"error": "Người được bảo hiểm không tồn tại"}), 404

        insured_person = {
            "id": row[0],
            "full_name": row[1],
            "gender": row[2],
            "date_of_birth": row[3],
            "workplace": row[4],
            "permanent_address": row[5],
            "temporary_address": row[6],
            "contact_address": row[7],
        }

        conn.close()
        return jsonify(insured_person), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API tạo hợp đồng bảo hiểm chỉ cho ContractCreator
@app.route("/insurance-contracts", methods=["POST"])
def create_insurance_contract():
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        # Restrict access to ContractCreator role
        if current_user.get("role") != "ContractCreator":
            return jsonify({"error": "Bạn không có quyền truy cập"}), 403

        data = request.json
        contract_number = data.get("contract_number")
        insurance_type_id = data.get("insurance_type_id")
        insured_person_id = data.get("insured_person_id")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        insurance_value = data.get("insurance_value")
        premium_amount = data.get("premium_amount")
        payment_frequency = data.get("payment_frequency")
        status = data.get("status", "Mới")

        if not all([contract_number, insurance_type_id, insured_person_id, start_date, end_date, insurance_value, premium_amount, payment_frequency]):
            return jsonify({"error": "Thiếu thông tin hợp đồng"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Open the symmetric key for encryption
        cursor.execute("OPEN SYMMETRIC KEY AppSymKey DECRYPTION BY CERTIFICATE AppCert")

        # Set session context for the current user ID
        cursor.execute("EXEC sp_set_session_context @key = N'UserID', @value = ?", current_user["user_id"])

        # Insert the insurance contract
        cursor.execute(
            """
            INSERT INTO InsuranceContracts (
                ContractNumber, InsuranceTypeID, InsuredPersonID, ContractCreatorUserID,
                StartDate, EndDate, InsuranceValue, PremiumAmount, PaymentFrequency, Status, CreatedAt
            )
            VALUES (?, ?, ?, ?, ?, ?, EncryptByKey(Key_GUID('AppSymKey'), CAST(? AS NVARCHAR(MAX))),
                    EncryptByKey(Key_GUID('AppSymKey'), CAST(? AS NVARCHAR(MAX))), ?, ?, SYSDATETIME())
            """,
            (
                contract_number, insurance_type_id, insured_person_id, current_user["user_id"],
                start_date, end_date, insurance_value, premium_amount, payment_frequency, status
            )
        )

        # Close the symmetric key after encryption
        cursor.execute("CLOSE SYMMETRIC KEY AppSymKey")

        conn.commit()
        conn.close()

        return jsonify({"message": "Hợp đồng bảo hiểm được tạo thành công"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API lấy hợp đồng theo người tạo hợp đồng (ContractCreator) chỉ cho ContractCreator
@app.route("/insurance-contracts/creator", methods=["GET"])
def get_insurance_contracts_by_creator():
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        # Restrict access to ContractCreator role
        if current_user.get("role") != "ContractCreator":
            return jsonify({"error": "Bạn không có quyền truy cập"}), 403

        conn = get_db_connection()
        cursor = conn.cursor()

        # Set session context for the current user ID
        cursor.execute("EXEC sp_set_session_context @key = N'UserID', @value = ?", current_user["user_id"])

        # Fetch insurance contracts by ContractCreatorUserID using session user ID
        cursor.execute(
            """
            SELECT ContractID, ContractNumber, InsuranceTypeID, InsuredPersonID, StartDate, EndDate, 
                   PaymentFrequency, Status, CreatedAt
            FROM InsuranceContracts
            WHERE ContractCreatorUserID = ?
            """,
            (current_user["user_id"],)  
        )

        contracts = [
            {
                "contract_id": row[0],
                "contract_number": row[1],
                "insurance_type_id": row[2],
                "insured_person_id": row[3],
                "start_date": row[4],
                "end_date": row[5],
                "payment_frequency": row[6],
                "status": row[7],
                "created_at": row[8],
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return jsonify(contracts), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API lấy hợp đồng theo loại bảo hiểm (InsuranceTypeID) chỉ cho Accountant và Supervisor
@app.route("/insurance-contracts/type", methods=["GET"])
def get_insurance_contracts_by_type(insurance_type_id):
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        # Restrict access to Accountant and Supervisor roles
        if current_user.get("role") not in ["Accountant", "Supervisor"]:
            return jsonify({"error": "Bạn không có quyền truy cập"}), 403

        
        conn = get_db_connection()
        cursor = conn.cursor()

        # Set session context for the current user ID
        cursor.execute("EXEC sp_set_session_context @key = N'UserID', @value = ?", current_user["user_id"])

        # Fetch insurance contracts by InsuranceTypeID
        cursor.execute(
            """
            SELECT ContractID, ContractNumber, InsuranceTypeID, InsuredPersonID, StartDate, EndDate, 
                   PaymentFrequency, Status, CreatedAt
            FROM InsuranceContracts
            WHERE InsuranceTypeID = ?
            """,
            (insurance_type_id,)
        )

        contracts = [
            {
                "contract_id": row[0],
                "contract_number": row[1],
                "insurance_type_id": row[2],
                "insured_person_id": row[3],
                "start_date": row[4],
                "end_date": row[5],
                "payment_frequency": row[6],
                "status": row[7],
                "created_at": row[8],
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return jsonify(contracts), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500





if __name__ == "__main__":
    app.run(debug=True)
