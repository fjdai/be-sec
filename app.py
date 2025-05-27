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
CORS(app, supports_credentials=True)

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/about")
def about():
    return render_template("about.html")


# Cấu hình kết nối MSSQL
def get_db_connection():
    connection = pyodbc.connect(
        # "DRIVER={ODBC Driver 17 for SQL Server};"
        # "SERVER=localhost;"  # Thay bằng tên hoặc IP của server
        # "DATABASE=QLBaoHiem;"
        # "UID=sa;"  # Thay bằng username
        # "PWD=Matkhau04@;"  # Thay bằng password

        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;"
        "DATABASE=QLBaoHiem;"
        "Trusted_Connection=yes;"
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


# API đăng ký - xong
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


# API đăng nhập - xong
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


# API đăng xuất - xong
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

        # Mở khóa symmetric key để giải mã
        cursor.execute("OPEN SYMMETRIC KEY AppSymKey DECRYPTION BY CERTIFICATE AppCert")

        # Fetch insurance contracts by ContractCreatorUserID using session user ID and decrypt columns
        cursor.execute(
            """
            SELECT ContractID, ContractNumber, InsuranceTypeID, InsuredPersonID, StartDate, EndDate, 
                   CAST(DecryptByKey(InsuranceValue) AS NVARCHAR(MAX)) AS InsuranceValue,
                   CAST(DecryptByKey(PremiumAmount) AS NVARCHAR(MAX)) AS PremiumAmount,
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
                "insurance_value": row[6],
                "premium_amount": row[7],
                "payment_frequency": row[8],
                "status": row[9],
                "created_at": row[10],
            }
            for row in cursor.fetchall()
        ]

        # Đóng symmetric key sau khi giải mã
        cursor.execute("CLOSE SYMMETRIC KEY AppSymKey")

        conn.close()
        return jsonify(contracts), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API lấy hợp đồng theo loại bảo hiểm (InsuranceTypeID) và giải mã các cột đã mã hóa
@app.route("/insurance-contracts/type", methods=["GET"])
def get_insurance_contracts_with_decryption():
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        conn = get_db_connection()
        cursor = conn.cursor()

        # Lấy danh sách InsuranceTypeID của user từ bảng RoleAssignments
        cursor.execute(
            """
            SELECT DISTINCT InsuranceTypeID
            FROM RoleAssignments
            WHERE UserID = ?
            """,
            (current_user["user_id"],)
        )
        insurance_type_ids = [row[0] for row in cursor.fetchall()]

        if not insurance_type_ids:
            conn.close()
            return jsonify({"error": "Người dùng không có quyền trên bất kỳ loại bảo hiểm nào"}), 403

        # Mở khóa symmetric key để giải mã
        cursor.execute("OPEN SYMMETRIC KEY AppSymKey DECRYPTION BY CERTIFICATE AppCert")

        # Lấy danh sách hợp đồng bảo hiểm tương ứng với các InsuranceTypeID và giải mã các cột
        cursor.execute(
            """
            SELECT ContractID, ContractNumber, InsuranceTypeID, InsuredPersonID, StartDate, EndDate, 
                   CAST(DecryptByKey(InsuranceValue) AS NVARCHAR(MAX)) AS InsuranceValue,
                   CAST(DecryptByKey(PremiumAmount) AS NVARCHAR(MAX)) AS PremiumAmount,
                   PaymentFrequency, Status, CreatedAt
            FROM InsuranceContracts
            WHERE InsuranceTypeID IN ({})
            """.format(",".join("?" for _ in insurance_type_ids)),
            insurance_type_ids
        )

        contracts = [
            {
                "contract_id": row[0],
                "contract_number": row[1],
                "insurance_type_id": row[2],
                "insured_person_id": row[3],
                "start_date": row[4],
                "end_date": row[5],
                "insurance_value": row[6],
                "premium_amount": row[7],
                "payment_frequency": row[8],
                "status": row[9],
                "created_at": row[10],
            }
            for row in cursor.fetchall()
        ]

        # Đóng symmetric key sau khi giải mã
        cursor.execute("CLOSE SYMMETRIC KEY AppSymKey")

        conn.close()
        return jsonify(contracts), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API lấy toàn bộ audit logs chỉ cho Admin
@app.route("/audit", methods=["GET"])
def get_audit():
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        # Restrict access to Admin role
        if current_user.get("role") != "Admin":
            return jsonify({"error": "Bạn không có quyền truy cập"}), 403

        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch all audit logs
        cursor.execute("SELECT LogID, TableName, ActionType, RecordPK, ChangedByUserID, ChangeDate, Details FROM AuditLogs")
        audit_logs = [
            {
                "log_id": row[0],
                "table_name": row[1],
                "action_type": row[2],
                "record_pk": row[3],
                "changed_by_user_id": row[4],
                "change_date": row[5],
                "details": row[6]
            } 
            for row in cursor.fetchall()
        ]

        conn.close()
        return jsonify(audit_logs), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API lấy audit logs theo trang chỉ cho Admin
@app.route("/audit/paginated", methods=["GET"])
def get_audit_paginated():
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        # Restrict access to Admin role
        if current_user.get("role") != "Admin":
            return jsonify({"error": "Bạn không có quyền truy cập"}), 403

        # Get pagination parameters
        page = request.args.get("page", default=1, type=int)
        per_page = request.args.get("per_page", default=10, type=int)

        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch paginated audit logs
        offset = (page - 1) * per_page
        cursor.execute(
            """
            SELECT LogID, TableName, ActionType, RecordPK, ChangedByUserID, ChangeDate, Details 
            FROM AuditLogs 
            ORDER BY ChangeDate DESC 
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """,
            (offset, per_page)
        )
        audit_logs = [
            {
                "log_id": row[0],
                "table_name": row[1],
                "action_type": row[2],
                "record_pk": row[3],
                "changed_by_user_id": row[4],
                "change_date": row[5],
                "details": row[6]
            } 
            for row in cursor.fetchall()
        ]

        conn.close()
        return jsonify(audit_logs), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API gán vai trò cho người dùng chỉ cho Admin
@app.route("/assign-role", methods=["POST"])
def assign_role():
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        # Restrict access to Admin role
        if current_user.get("role") != "Admin":
            return jsonify({"error": "Bạn không có quyền truy cập"}), 403

        data = request.json
        user_id = data.get("user_id")
        insurance_type_id = data.get("insurance_type_id")
        assigned_role = data.get("assigned_role")

        if not all([user_id, insurance_type_id, assigned_role]):
            return jsonify({"error": "Thiếu thông tin cần thiết"}), 400

        if assigned_role not in ["Accountant", "Supervisor"]:
            return jsonify({"error": "Vai trò không hợp lệ"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert the role assignment
        cursor.execute(
            """
            INSERT INTO RoleAssignments (UserID, InsuranceTypeID, AssignedRole)
            VALUES (?, ?, ?)
            """,
            (user_id, insurance_type_id, assigned_role)
        )

        conn.commit()
        conn.close()

        return jsonify({"message": "Gán vai trò thành công"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API sửa gán vai trò chỉ cho Admin
@app.route("/assign-role/<int:role_id>", methods=["PUT"])
def update_role_assignment(role_id):
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        # Restrict access to Admin role
        if current_user.get("role") != "Admin":
            return jsonify({"error": "Bạn không có quyền truy cập"}), 403

        data = request.json
        insurance_type_id = data.get("insurance_type_id")
        assigned_role = data.get("assigned_role")

        if not all([insurance_type_id, assigned_role]):
            return jsonify({"error": "Thiếu thông tin cần thiết"}), 400

        if assigned_role not in ["Accountant", "Supervisor"]:
            return jsonify({"error": "Vai trò không hợp lệ"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Update the role assignment
        cursor.execute(
            """
            UPDATE RoleAssignments
            SET InsuranceTypeID = ?, AssignedRole = ?
            WHERE RoleID = ?
            """,
            (insurance_type_id, assigned_role, role_id)
        )

        conn.commit()
        conn.close()

        return jsonify({"message": "Cập nhật vai trò thành công"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API xóa gán vai trò chỉ cho Admin
@app.route("/assign-role/<int:role_id>", methods=["DELETE"])
def delete_role_assignment(role_id):
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        # Restrict access to Admin role
        if current_user.get("role") != "Admin":
            return jsonify({"error": "Bạn không có quyền truy cập"}), 403

        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete the role assignment
        cursor.execute("DELETE FROM RoleAssignments WHERE RoleID = ?", (role_id,))

        conn.commit()
        conn.close()

        return jsonify({"message": "Xóa vai trò thành công"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API xóa hợp đồng bảo hiểm chỉ cho ContractCreator
@app.route("/insurance-contracts/<int:contract_id>", methods=["DELETE"])
def delete_insurance_contract(contract_id):
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

        # Check if the contract exists and belongs to the current user
        cursor.execute(
            "SELECT ContractID FROM InsuranceContracts WHERE ContractID = ? AND ContractCreatorUserID = ?",
            (contract_id, current_user["user_id"])
        )
        contract = cursor.fetchone()

        if not contract:
            conn.close()
            return jsonify({"error": "Hợp đồng không tồn tại hoặc bạn không có quyền xóa"}), 404

        # Delete the contract
        cursor.execute("DELETE FROM InsuranceContracts WHERE ContractID = ?", (contract_id,))
        conn.commit()
        conn.close()

        return jsonify({"message": "Xóa hợp đồng thành công"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API sửa hợp đồng bảo hiểm chỉ cho ContractCreator
@app.route("/insurance-contracts/<int:contract_id>", methods=["PUT"])
def update_insurance_contract(contract_id):
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        # Restrict access to ContractCreator role
        if current_user.get("role") != "ContractCreator":
            return jsonify({"error": "Bạn không có quyền truy cập"}), 403

        data = request.json
        insurance_value = data.get("insurance_value")
        premium_amount = data.get("premium_amount")
        status = data.get("status")

        if not all([insurance_value, premium_amount, status]):
            return jsonify({"error": "Thiếu thông tin cần thiết"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the contract exists and belongs to the current user
        cursor.execute(
            "SELECT ContractID FROM InsuranceContracts WHERE ContractID = ? AND ContractCreatorUserID = ?",
            (contract_id, current_user["user_id"])
        )
        contract = cursor.fetchone()

        if not contract:
            conn.close()
            return jsonify({"error": "Hợp đồng không tồn tại hoặc bạn không có quyền sửa"}), 404

        # Open the symmetric key for encryption
        cursor.execute("OPEN SYMMETRIC KEY AppSymKey DECRYPTION BY CERTIFICATE AppCert")

        # Update the contract
        cursor.execute(
            """
            UPDATE InsuranceContracts
            SET InsuranceValue = EncryptByKey(Key_GUID('AppSymKey'), CAST(? AS NVARCHAR(MAX))),
                PremiumAmount = EncryptByKey(Key_GUID('AppSymKey'), CAST(? AS NVARCHAR(MAX))),
                Status = ?
            WHERE ContractID = ?
            """,
            (insurance_value, premium_amount, status, contract_id)
        )

        # Close the symmetric key after encryption
        cursor.execute("CLOSE SYMMETRIC KEY AppSymKey")

        conn.commit()
        conn.close()

        return jsonify({"message": "Cập nhật hợp đồng thành công"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API sửa thông tin người được bảo hiểm chỉ cho ContractCreator
@app.route("/insured-persons/<int:person_id>", methods=["PUT"])
def update_insured_person(person_id):
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        # Restrict access to ContractCreator role
        if current_user.get("role") != "ContractCreator":
            return jsonify({"error": "Bạn không có quyền truy cập"}), 403

        data = request.json
        full_name = data.get("full_name")
        gender = data.get("gender")
        date_of_birth = data.get("date_of_birth")
        workplace = data.get("workplace")
        permanent_address = data.get("permanent_address")
        temporary_address = data.get("temporary_address")
        contact_address = data.get("contact_address")

        if not all([full_name, gender, date_of_birth, workplace, permanent_address, temporary_address, contact_address]):
            return jsonify({"error": "Thiếu thông tin cần thiết"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the insured person exists
        cursor.execute(
            "SELECT InsuredPersonID FROM InsuredPersons WHERE InsuredPersonID = ?",
            (person_id,)
        )
        insured_person = cursor.fetchone()

        if not insured_person:
            conn.close()
            return jsonify({"error": "Người được bảo hiểm không tồn tại"}), 404

        # Update the insured person's information
        cursor.execute(
            """
            UPDATE InsuredPersons
            SET FullName = ?, Gender = ?, DateOfBirth = ?, Workplace = ?,
                PermanentAddress = ?, TemporaryAddress = ?, ContactAddress = ?
            WHERE InsuredPersonID = ?
            """,
            (full_name, gender, date_of_birth, workplace, permanent_address, temporary_address, contact_address, person_id)
        )

        conn.commit()
        conn.close()

        return jsonify({"message": "Cập nhật thông tin người được bảo hiểm thành công"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API lấy danh sách tất cả người dùng chỉ cho Admin
@app.route("/users", methods=["GET"])
def get_all_users():
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        # Restrict access to Admin role
        if current_user.get("role") != "Admin":
            return jsonify({"error": "Bạn không có quyền truy cập"}), 403

        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch all users
        cursor.execute("SELECT UserID, Username, FullName, Role, IsActive FROM Users")
        users = [
            {
                "user_id": row[0],
                "username": row[1],
                "full_name": row[2],
                "role": row[3],
                "is_active": row[4]
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return jsonify(users), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API sửa thông tin người dùng chỉ cho Admin
@app.route("/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        # Restrict access to Admin role
        if current_user.get("role") != "Admin":
            return jsonify({"error": "Bạn không có quyền truy cập"}), 403

        data = request.json
        full_name = data.get("full_name")
        role = data.get("role")
        is_active = data.get("is_active")

        if not all([full_name, role, is_active is not None]):
            return jsonify({"error": "Thiếu thông tin cần thiết"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Update the user's information
        cursor.execute(
            """
            UPDATE Users
            SET FullName = ?, Role = ?, IsActive = ?
            WHERE UserID = ?
            """,
            (full_name, role, is_active, user_id)
        )

        conn.commit()
        conn.close()

        return jsonify({"message": "Cập nhật thông tin người dùng thành công"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API xóa người dùng chỉ cho Admin - xong
@app.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        # Restrict access to Admin role
        if current_user.get("role") != "Admin":
            return jsonify({"error": "Bạn không có quyền truy cập"}), 403

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the user exists
        cursor.execute("SELECT UserID FROM Users WHERE UserID = ?", (user_id,))
        user = cursor.fetchone()

        if not user:
            conn.close()
            return jsonify({"error": "Người dùng không tồn tại"}), 404

        # Delete the user
        cursor.execute("DELETE FROM Users WHERE UserID = ?", (user_id,))
        conn.commit()
        conn.close()

        return jsonify({"message": "Xóa người dùng thành công"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API lấy người dùng theo vai trò chỉ cho Admin
@app.route("/users/role/<string:role>", methods=["GET"])
def get_users_by_role(role):
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        # Restrict access to Admin role
        if current_user.get("role") != "Admin":
            return jsonify({"error": "Bạn không có quyền truy cập"}), 403

        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch users by role
        cursor.execute("SELECT UserID, Username, FullName, Role, IsActive FROM Users WHERE Role = ?", (role,))
        users = [
            {
                "user_id": row[0],
                "username": row[1],
                "full_name": row[2],
                "role": row[3],
                "is_active": row[4]
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return jsonify(users), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API hủy kích hoạt tài khoản người dùng chỉ cho Admin
@app.route("/users/<int:user_id>/deactivate", methods=["POST"])
def deactivate_user(user_id):
    try:
        # Check if the user is logged in
        current_user = session.get("user")
        if not current_user:
            return jsonify({"error": "Bạn chưa đăng nhập"}), 401

        # Restrict access to Admin role
        if current_user.get("role") != "Admin":
            return jsonify({"error": "Bạn không có quyền truy cập"}), 403

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the user exists
        cursor.execute("SELECT UserID FROM Users WHERE UserID = ?", (user_id,))
        user = cursor.fetchone()

        if not user:
            conn.close()
            return jsonify({"error": "Người dùng không tồn tại"}), 404

        # Deactivate the user account
        cursor.execute("UPDATE Users SET IsActive = 0 WHERE UserID = ?", (user_id,))
        conn.commit()
        conn.close()

        return jsonify({"message": "Tài khoản người dùng đã được hủy kích hoạt"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API hủy kích hoạt tài khoản Insured chỉ cho ContractCreator
@app.route("/insured/<int:insured_id>/deactivate", methods=["POST"])
def deactivate_insured_account(insured_id):
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

        # Check if the insured person exists
        cursor.execute("SELECT InsuredPersonID FROM InsuredPersons WHERE InsuredPersonID = ?", (insured_id,))
        insured_person = cursor.fetchone()

        if not insured_person:
            conn.close()
            return jsonify({"error": "Người được bảo hiểm không tồn tại"}), 404

        # Deactivate the insured account
        cursor.execute("UPDATE InsuredPersons SET IsActive = 0 WHERE InsuredPersonID = ?", (insured_id,))
        conn.commit()
        conn.close()

        return jsonify({"message": "Tài khoản người được bảo hiểm đã được hủy kích hoạt"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Tạo tài khoản admin nếu chưa tồn tại
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Kiểm tra xem tài khoản admin đã tồn tại chưa
        cursor.execute("SELECT 1 FROM Users WHERE Username = ?", ("admin",))
        if not cursor.fetchone():
            # Hash mật khẩu admin
            admin_password_hash = hashlib.sha256("admin".encode('utf-8')).digest()

            # Tạo tài khoản admin
            cursor.execute(
                "INSERT INTO Users (Username, PasswordHash, FullName, Role, IsActive) VALUES (?, ?, ?, ?, 1)",
                ("admin", admin_password_hash, "Administrator", "Admin")
            )
            conn.commit()
            print("Tài khoản admin đã được tạo thành công.")
        else:
            print("Tài khoản admin đã tồn tại.")

        conn.close()
    except Exception as e:
        print(f"Lỗi khi tạo tài khoản admin: {str(e)}")

    app.run(debug=True)
