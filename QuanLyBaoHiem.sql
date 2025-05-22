-- Xóa các đối tượng cũ nếu tồn tại để tránh lỗi khi chạy lại
-- (Thêm các lệnh DROP khác nếu cần: DROP PROCEDURE, DROP FUNCTION, DROP TRIGGER, ...)
/*IF OBJECT_ID('dbo.Policy_Filter_InsuranceContracts', 'SP') IS NOT NULL DROP SECURITY POLICY dbo.Policy_Filter_InsuranceContracts;
IF OBJECT_ID('dbo.fn_rls_BlockInsuranceContractsChanges', 'FN') IS NOTIONAL DROP FUNCTION dbo.fn_rls_BlockInsuranceContractsChanges;
IF OBJECT_ID('dbo.fn_rls_FilterInsuranceContracts', 'FN') IS NOT NULL DROP FUNCTION dbo.fn_rls_FilterInsuranceContracts;
-- ... (Thêm lệnh DROP cho các SP, Trigger, Bảng khác nếu cần chạy lại script nhiều lần) ...
IF OBJECT_ID('dbo.AuditLogs', 'U') IS NOT NULL DROP TABLE dbo.AuditLogs;
IF OBJECT_ID('dbo.RoleAssignments', 'U') IS NOT NULL DROP TABLE dbo.RoleAssignments;
IF OBJECT_ID('dbo.InsuranceContracts', 'U') IS NOT NULL DROP TABLE dbo.InsuranceContracts;
IF OBJECT_ID('dbo.InsuredPersons', 'U') IS NOT NULL DROP TABLE dbo.InsuredPersons;
IF OBJECT_ID('dbo.InsuranceTypes', 'U') IS NOT NULL DROP TABLE dbo.InsuranceTypes;
IF OBJECT_ID('dbo.Users', 'U') IS NOT NULL DROP TABLE dbo.Users;

-- (Nếu Key/Cert cũ tồn tại, cần DROP chúng trước)
IF EXISTS (SELECT * FROM sys.symmetric_keys WHERE name = 'AppSymKey') DROP SYMMETRIC KEY AppSymKey;
IF EXISTS (SELECT * FROM sys.certificates WHERE name = 'AppCert') DROP CERTIFICATE AppCert;
IF EXISTS (SELECT * FROM sys.asymmetric_keys WHERE name = 'MedicalAsymKey') DROP ASYMMETRIC KEY MedicalAsymKey;
IF EXISTS (SELECT * FROM sys.certificates WHERE name = 'MedicalCert') DROP CERTIFICATE MedicalCert;
IF EXISTS (SELECT * FROM sys.database_master_keys) DROP MASTER KEY; -- Cẩn thận khi chạy lệnh này!
GO*/

-- Tạo Database nếu chưa có
CREATE DATABASE QLBaoHiem;
GO

USE QLBaoHiem;
GO

-- ****** BẢNG DỮ LIỆU ******

CREATE TABLE Users (
    UserID INT IDENTITY(1,1) NOT NULL,
    Username NVARCHAR(100) NOT NULL,
    PasswordHash VARBINARY(64) NOT NULL, -- SHA2_256 output size
    FullName NVARCHAR(150) NOT NULL,
    Role NVARCHAR(50) NOT NULL, -- Vai trò ('ContractCreator', 'Insured', 'Accountant', 'Supervisor')
    IsActive BIT NOT NULL DEFAULT 1,

    CONSTRAINT PK_Users PRIMARY KEY (UserID),
    CONSTRAINT UQ_Users_Username UNIQUE (Username),
    CONSTRAINT CK_Users_Role CHECK (Role IN ('Admin','ContractCreator', 'Insured', 'Accountant', 'Supervisor'))
);
GO

CREATE TABLE InsuranceTypes (
    InsuranceTypeID INT IDENTITY(1,1) NOT NULL,
    TypeName NVARCHAR(150) NOT NULL,

    CONSTRAINT PK_InsuranceTypes PRIMARY KEY (InsuranceTypeID),
    CONSTRAINT UQ_InsuranceTypes_TypeName UNIQUE (TypeName)
);
GO

CREATE TABLE InsuredPersons (
    InsuredPersonID INT IDENTITY(1,1) NOT NULL,
    FullName NVARCHAR(150) NOT NULL,
    Gender NVARCHAR(10) NULL,
    DateOfBirth DATE NOT NULL,
    Workplace NVARCHAR(255) NULL,
    PermanentAddress NVARCHAR(500) NOT NULL,
    TemporaryAddress NVARCHAR(500),
    ContactAddress NVARCHAR(500) NOT NULL,
    MedicalHistory VARBINARY(MAX), -- Dữ liệu mã hóa bất đối xứng
    UserID INT NULL, -- Liên kết tới tài khoản người dùng (nếu người được BH có tài khoản)
    CreatedAt DATETIME2(3) NOT NULL DEFAULT SYSDATETIME(),

    CONSTRAINT PK_InsuredPersons PRIMARY KEY (InsuredPersonID),
    CONSTRAINT FK_InsuredPersons_Users FOREIGN KEY (UserID) REFERENCES Users(UserID)
        ON DELETE SET NULL ON UPDATE CASCADE, -- Nếu User bị xóa, chỉ set NULL ở đây
    CONSTRAINT CK_InsuredPersons_Gender CHECK (Gender IS NULL OR Gender IN (N'Nam', N'Nữ', N'Khác'))
);
GO

CREATE TABLE InsuranceContracts (
    ContractID INT IDENTITY(1,1) NOT NULL,
    ContractNumber NVARCHAR(50) NOT NULL,
    InsuranceTypeID INT NOT NULL,
    InsuredPersonID INT NOT NULL,
    ContractCreatorUserID INT NOT NULL, -- UserID của người lập hợp đồng
    StartDate DATE NOT NULL,
    EndDate DATE NOT NULL,
    InsuranceValue VARBINARY(MAX) NOT NULL, -- Dữ liệu mã hóa đối xứng
    PremiumAmount VARBINARY(MAX) NOT NULL, -- Dữ liệu mã hóa đối xứng
    PaymentFrequency NVARCHAR(50) NOT NULL,
    Status NVARCHAR(50) NOT NULL,
    CreatedAt DATETIME2(3) NOT NULL DEFAULT SYSDATETIME(),
    -- CreatedByUserID INT NOT NULL, -- Cột này có thể không cần thiết nếu dùng Trigger Log với SESSION_CONTEXT

    CONSTRAINT PK_InsuranceContracts PRIMARY KEY (ContractID),
    CONSTRAINT UQ_InsuranceContracts_ContractNumber UNIQUE (ContractNumber),
    CONSTRAINT FK_InsuranceContracts_InsuranceTypes FOREIGN KEY (InsuranceTypeID) REFERENCES InsuranceTypes(InsuranceTypeID)
        ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT FK_InsuranceContracts_InsuredPersons FOREIGN KEY (InsuredPersonID) REFERENCES InsuredPersons(InsuredPersonID)
        ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT FK_InsuranceContracts_PolicyCreator FOREIGN KEY (ContractCreatorUserID) REFERENCES Users(UserID)
        ON DELETE NO ACTION ON UPDATE NO ACTION,
    -- CONSTRAINT FK_InsuranceContracts_CreatedByUser FOREIGN KEY (CreatedByUserID) REFERENCES Users(UserID)
    --     ON DELETE NO ACTION ON UPDATE NO ACTION,
    CONSTRAINT CK_InsuranceContracts_Dates CHECK (EndDate >= StartDate),
    CONSTRAINT CK_InsuranceContracts_Status CHECK (Status IN (N'Mới', N'Hiệu lực', N'Hết hạn', N'Hủy bỏ'))
);
GO

CREATE TABLE RoleAssignments (
    AssignmentID INT IDENTITY(1,1) NOT NULL,
    UserID INT NOT NULL, -- UserID của Accountant hoặc Supervisor
    InsuranceTypeID INT NOT NULL,
    AssignedRole NVARCHAR(50) NOT NULL, -- Chỉ 'Accountant' hoặc 'Supervisor'

    CONSTRAINT PK_RoleAssignments PRIMARY KEY (AssignmentID),
    CONSTRAINT FK_RoleAssignments_Users FOREIGN KEY (UserID) REFERENCES Users(UserID)
        ON DELETE CASCADE ON UPDATE CASCADE, -- Nếu User bị xóa/đổi ID, phân công cũng thay đổi/xóa
    CONSTRAINT FK_RoleAssignments_InsuranceTypes FOREIGN KEY (InsuranceTypeID) REFERENCES InsuranceTypes(InsuranceTypeID)
        ON DELETE CASCADE ON UPDATE CASCADE, -- Nếu Loại BH bị xóa/đổi ID, phân công cũng thay đổi/xóa
    CONSTRAINT UQ_RoleAssignments_UserTypeRole UNIQUE (UserID, InsuranceTypeID, AssignedRole),
    CONSTRAINT CK_RoleAssignments_AssignedRole CHECK (AssignedRole IN ('Accountant', 'Supervisor'))
);
GO

CREATE TABLE AuditLogs (
    LogID BIGINT IDENTITY(1,1) PRIMARY KEY, -- Dùng BIGINT cho bảng log lớn
    TableName NVARCHAR(128) NOT NULL, -- sysname = NVARCHAR(128)
    ActionType NVARCHAR(10) NOT NULL, -- 'INSERT', 'UPDATE', 'DELETE'
    RecordPK NVARCHAR(255) NOT NULL, -- Lưu khóa chính của bản ghi bị ảnh hưởng (có thể là nhiều cột)
    ChangedByUserID INT NULL, -- UserID từ SESSION_CONTEXT (NULL nếu không set)
    ChangeDate DATETIME2(3) NOT NULL DEFAULT SYSDATETIME(),
    Details NVARCHAR(MAX) NULL -- Mô tả chi tiết thay đổi (JSON hoặc văn bản)
);
GO

-- ****** MÃ HÓA ******

-- 1. Master Key (nếu chưa có)
IF NOT EXISTS (SELECT name FROM sys.symmetric_keys WHERE name = '##MS_DatabaseMasterKey##')
BEGIN
    CREATE MASTER KEY ENCRYPTION BY PASSWORD = 'QuanLyBaoHiem88!'; -- Thay bằng mật khẩu cực mạnh
END
GO

-- 2. Certificate và Symmetric Key cho dữ liệu hợp đồng (AES)
IF NOT EXISTS (SELECT * FROM sys.certificates WHERE name = 'AppCert')
BEGIN
    CREATE CERTIFICATE AppCert WITH SUBJECT = 'Application Data Encryption';
END
GO


IF NOT EXISTS (SELECT * FROM sys.symmetric_keys WHERE name = 'AppSymKey')
BEGIN
    CREATE SYMMETRIC KEY AppSymKey
    WITH ALGORITHM = AES_256
    ENCRYPTION BY CERTIFICATE AppCert;
END
GO

-- 3. Certificate và Asymmetric Key cho lịch sử bệnh (RSA)
-- Lưu ý: Certificate này cần chứa khóa riêng tư để có thể giải mã bằng Asymmetric Key tương ứng
IF NOT EXISTS (SELECT * FROM sys.certificates WHERE name = 'MedicalCert')
BEGIN
    -- Tạo Certificate (ví dụ tự ký - self-signed)
    -- Trong thực tế, bạn có thể import Certificate từ file PFX đã có khóa riêng
    CREATE CERTIFICATE MedicalCert WITH SUBJECT = 'Medical History Encryption';
END
GO


IF NOT EXISTS (SELECT * FROM sys.asymmetric_keys WHERE name = 'MedicalAsymKey')
BEGIN
    CREATE ASYMMETRIC KEY MedicalAsymKey
    WITH ALGORITHM = RSA_2048; -- Bạn có thể chọn độ dài khóa khác (ví dụ: RSA_1024, RSA_4096)
END
GO


-- ****** STORED PROCEDURES ******

CREATE PROCEDURE CreateUser
    @Username NVARCHAR(100),
    @Password NVARCHAR(100),
    @FullName NVARCHAR(150),
    @Role NVARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (SELECT 1 FROM Users WHERE Username = @Username)
    BEGIN
        RAISERROR('Tên đăng nhập đã tồn tại.', 16, 1);
        RETURN;
    END;

    IF @Role NOT IN ('ContractCreator', 'Insured', 'Accountant', 'Supervisor', 'Admin')
    BEGIN
        RAISERROR('Vai trò không hợp lệ.', 16, 1);
        RETURN;
    END;

	DECLARE @PasswordHash VARBINARY(64) = HASHBYTES('SHA2_256', CAST(@Password AS VARBINARY(MAX)));

	INSERT INTO Users (Username, PasswordHash, FullName, Role, IsActive)
	VALUES (@Username, @PasswordHash, @FullName, @Role, 1);

END;
GO

-- SP Xác thực mật khẩu
CREATE PROCEDURE VerifyUserPassword
    @Username NVARCHAR(100),
    @Password NVARCHAR(100),
    @UserID INT OUTPUT,
    @IsValid BIT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @StoredHash VARBINARY(64);
    DECLARE @UserRole NVARCHAR(50);
    DECLARE @UserIsActive BIT;

    SELECT
        @UserID = UserID,
        @StoredHash = PasswordHash,
        @UserRole = Role,
        @UserIsActive = IsActive
    FROM Users
    WHERE Username = @Username;

    IF @UserID IS NULL OR @UserIsActive = 0
    BEGIN
        SET @IsValid = 0;
        SET @UserID = NULL;
        RETURN;
    END;

    DECLARE @InputHash VARBINARY(64) = HASHBYTES('SHA2_256', CAST(@Password AS VARBINARY(MAX)));

    IF @InputHash = @StoredHash
    BEGIN
        SET @IsValid = 1;
        -- Có thể thực hiện set session context ngay tại đây nếu muốn
        -- EXEC sp_set_session_context N'UserID', @UserID;
        -- EXEC sp_set_session_context N'UserRole', @UserRole;
    END
    ELSE
    BEGIN
        SET @IsValid = 0;
        SET @UserID = NULL;
    END;
END;
GO

-- SP Tạo người được bảo hiểm (Mã hóa lịch sử bệnh)
CREATE PROCEDURE CreateInsuredPerson
    @FullName NVARCHAR(150),
    @Gender NVARCHAR(10) = NULL,
    @DateOfBirth DATE,
    @Workplace NVARCHAR(255) = NULL,
    @PermanentAddress NVARCHAR(500),
    @TemporaryAddress NVARCHAR(500) = NULL,
    @ContactAddress NVARCHAR(500),
    @MedicalHistory NVARCHAR(MAX) = NULL, -- Dữ liệu gốc (text)
    @UserID INT = NULL -- Liên kết với tài khoản User (nếu có)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @EncryptedMedicalHistory VARBINARY(MAX) = NULL;

    -- Chỉ mã hóa nếu có lịch sử bệnh
    IF @MedicalHistory IS NOT NULL AND LEN(@MedicalHistory) > 0
    BEGIN
        -- Không cần mở key bất đối xứng
        SET @EncryptedMedicalHistory = EncryptByAsymKey(AsymKey_ID('MedicalAsymKey'), CONVERT(VARBINARY(MAX), @MedicalHistory));
    END

    INSERT INTO InsuredPersons (
        FullName, Gender, DateOfBirth, Workplace,
        PermanentAddress, TemporaryAddress, ContactAddress,
        MedicalHistory, UserID, CreatedAt
    )
    VALUES (
        @FullName, @Gender, @DateOfBirth, @Workplace,
        @PermanentAddress, @TemporaryAddress, @ContactAddress,
        @EncryptedMedicalHistory, @UserID, SYSDATETIME()
    );
END;
GO

-- SP Tạo hợp đồng bảo hiểm (Mã hóa giá trị, phí)
CREATE PROCEDURE CreateInsuranceContract
    @ContractNumber NVARCHAR(50),
    @InsuranceTypeID INT,
    @InsuredPersonID INT,
    @ContractCreatorUserID INT, -- UserID người tạo từ ứng dụng
    @StartDate DATE,
    @EndDate DATE,
    @InsuranceValue DECIMAL(18, 2), -- Dữ liệu gốc
    @PremiumAmount DECIMAL(18, 2), -- Dữ liệu gốc
    @PaymentFrequency NVARCHAR(50),
    @Status NVARCHAR(50) = N'Mới'
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @EncryptedValue VARBINARY(MAX);
    DECLARE @EncryptedPremium VARBINARY(MAX);

    -- Kiểm tra quyền và dữ liệu đầu vào
    DECLARE @CreatorRole NVARCHAR(50);
    SELECT @CreatorRole = Role FROM Users WHERE UserID = @ContractCreatorUserID AND IsActive = 1;

    IF @CreatorRole <> 'ContractCreator'
    BEGIN
        RAISERROR(N'Người dùng không có quyền tạo hợp đồng.', 16, 1);
        RETURN;
    END;

    IF NOT EXISTS (SELECT 1 FROM InsuranceTypes WHERE InsuranceTypeID = @InsuranceTypeID)
    BEGIN
        RAISERROR(N'Loại bảo hiểm không tồn tại.', 16, 1);
        RETURN;
    END;

    IF NOT EXISTS (SELECT 1 FROM InsuredPersons WHERE InsuredPersonID = @InsuredPersonID)
    BEGIN
        RAISERROR(N'Người được bảo hiểm không tồn tại.', 16, 1);
        RETURN;
    END;

    IF @EndDate < @StartDate
    BEGIN
        RAISERROR(N'Ngày kết thúc phải sau hoặc bằng ngày bắt đầu.', 16, 1);
        RETURN;
    END;

    BEGIN TRY
        -- Mở khóa đối xứng
        OPEN SYMMETRIC KEY AppSymKey DECRYPTION BY CERTIFICATE AppCert;

        SET @EncryptedValue = EncryptByKey(KEY_GUID('AppSymKey'), CAST(@InsuranceValue AS VARCHAR(50)));
        SET @EncryptedPremium = EncryptByKey(KEY_GUID('AppSymKey'), CAST(@PremiumAmount AS VARCHAR(50)));

        INSERT INTO InsuranceContracts (
            ContractNumber, InsuranceTypeID, InsuredPersonID,
            ContractCreatorUserID, StartDate, EndDate,
            InsuranceValue, PremiumAmount,
            PaymentFrequency, Status, CreatedAt
        )
        VALUES (
            @ContractNumber, @InsuranceTypeID, @InsuredPersonID,
            @ContractCreatorUserID, @StartDate, @EndDate,
            @EncryptedValue, @EncryptedPremium,
            @PaymentFrequency, @Status, SYSDATETIME()
        );

        -- Đóng khóa đối xứng
        CLOSE SYMMETRIC KEY AppSymKey;
    END TRY
    BEGIN CATCH
        -- Đóng key trong catch block nếu có lỗi
        BEGIN TRY
            CLOSE SYMMETRIC KEY AppSymKey;
        END TRY
        BEGIN CATCH
            -- Không làm gì nếu đóng thất bại
        END CATCH;

        -- Ném lại lỗi
        THROW;
    END CATCH
END;
GO


-- SP Lấy thông tin giải mã (cho Kế toán/Giám sát - yêu cầu quyền trên AsymKey)
CREATE PROCEDURE usp_GetDecryptedInsuranceInfo
    @TargetInsuredPersonID INT,
    @TargetContractID INT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @CurrentUserID INT = CAST(SESSION_CONTEXT(N'UserID') AS INT);
    DECLARE @CurrentUserRole NVARCHAR(50);
    DECLARE @IsAssigned BIT = 0;
    DECLARE @InsuranceTypeOfContract INT;

    IF @CurrentUserID IS NULL
    BEGIN
        RAISERROR(N'Không xác định được người dùng hiện tại. Cần set SESSION_CONTEXT.', 16, 1);
        RETURN;
    END

    -- 1. Kiểm tra quyền người dùng: phải là Accountant hoặc Supervisor
    SELECT @CurrentUserRole = Role FROM Users WHERE UserID = @CurrentUserID AND IsActive = 1;

    IF @CurrentUserRole NOT IN ('Accountant', 'Supervisor')
    BEGIN
        RAISERROR(N'Bạn không có quyền truy cập thông tin này.', 16, 1);
        RETURN;
    END

    -- 2. Kiểm tra xem người dùng có được phân công cho loại BH của hợp đồng này không
    SELECT @InsuranceTypeOfContract = InsuranceTypeID
    FROM InsuranceContracts
    WHERE ContractID = @TargetContractID;

    IF @InsuranceTypeOfContract IS NULL
    BEGIN
        RAISERROR(N'Không tìm thấy hợp đồng.', 16, 1);
        RETURN;
    END

    IF EXISTS (
        SELECT 1
        FROM RoleAssignments
        WHERE UserID = @CurrentUserID
          AND InsuranceTypeID = @InsuranceTypeOfContract
          AND AssignedRole = @CurrentUserRole
    )
    BEGIN
        SET @IsAssigned = 1;
    END

    IF @IsAssigned = 0
    BEGIN
        RAISERROR(N'Bạn không được phân công quản lý/giám sát loại bảo hiểm của hợp đồng này.', 16, 1);
        RETURN;
    END

    -- 3. Lấy dữ liệu mã hóa
    DECLARE @EncryptedHistory VARBINARY(MAX);
    DECLARE @EncryptedPremium VARBINARY(MAX);
    DECLARE @EncryptedValue VARBINARY(MAX);
    DECLARE @ContractNumber NVARCHAR(50);
    DECLARE @InsuredName NVARCHAR(150);

    SELECT
        @EncryptedHistory = ip.MedicalHistory,
        @EncryptedPremium = ic.PremiumAmount,
        @EncryptedValue = ic.InsuranceValue,
        @ContractNumber = ic.ContractNumber,
        @InsuredName = ip.FullName
    FROM InsuredPersons ip
    JOIN InsuranceContracts ic ON ip.InsuredPersonID = ic.InsuredPersonID
    WHERE ip.InsuredPersonID = @TargetInsuredPersonID
      AND ic.ContractID = @TargetContractID;

    IF @ContractNumber IS NULL
    BEGIN
        RAISERROR(N'Dữ liệu không khớp hoặc không tồn tại.', 16, 1);
        RETURN;
    END

    -- 4. Giải mã
    DECLARE @DecryptedHistory NVARCHAR(MAX) = NULL;
    DECLARE @DecryptedPremium DECIMAL(18, 2) = NULL;
    DECLARE @DecryptedValue DECIMAL(18, 2) = NULL;

    BEGIN TRY
        -- Giải mã lịch sử bệnh (RSA - yêu cầu quyền trên AsymKey)
        IF @EncryptedHistory IS NOT NULL
        BEGIN
            SET @DecryptedHistory = CONVERT(NVARCHAR(MAX), DecryptByAsymKey(AsymKey_ID('MedicalAsymKey'), @EncryptedHistory));
        END

        -- Giải mã phí và giá trị BH (AES)
		OPEN SYMMETRIC KEY AppSymKey DECRYPTION BY CERTIFICATE AppCert;

		IF @EncryptedPremium IS NOT NULL
		BEGIN
			SET @DecryptedPremium = CAST(CONVERT(VARCHAR(MAX), DecryptByKey(@EncryptedPremium)) AS DECIMAL(18, 2));
		END
		IF @EncryptedValue IS NOT NULL
		BEGIN
			SET @DecryptedValue = CAST(CONVERT(VARCHAR(MAX), DecryptByKey(@EncryptedValue)) AS DECIMAL(18, 2));
		END

		CLOSE SYMMETRIC KEY AppSymKey;
    END TRY
    BEGIN CATCH
        -- Đóng symmetric key nếu mở và bỏ qua lỗi nếu chưa mở
        BEGIN TRY
            CLOSE SYMMETRIC KEY AppSymKey;
        END TRY
        BEGIN CATCH
            -- Không làm gì nếu lỗi trong việc đóng
        END CATCH;

        RAISERROR(N'Lỗi trong quá trình giải mã dữ liệu. Kiểm tra quyền hoặc tính toàn vẹn dữ liệu.', 16, 1);
        THROW;
    END CATCH

    -- 5. Trả kết quả
    SELECT
        @InsuredName AS InsuredName,
        @ContractNumber AS ContractNumber,
        @DecryptedValue AS InsuranceValue,
        @DecryptedPremium AS PremiumAmount,
        @DecryptedHistory AS MedicalHistory;
END;
GO


-- SP Kết xuất báo cáo theo vai trò (Accountant/Supervisor)
CREATE PROCEDURE sp_ExportInsuranceReportByRole
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @CurrentUserID INT = CAST(SESSION_CONTEXT(N'UserID') AS INT);
    DECLARE @CurrentUserRole NVARCHAR(50);

    IF @CurrentUserID IS NULL
    BEGIN
        RAISERROR(N'Không xác định được người dùng hiện tại. Cần set SESSION_CONTEXT.', 16, 1);
        RETURN;
    END

    SELECT @CurrentUserRole = Role FROM Users WHERE UserID = @CurrentUserID AND IsActive = 1;

    IF @CurrentUserRole NOT IN ('Accountant', 'Supervisor')
    BEGIN
        RAISERROR(N'Chức năng này chỉ dành cho Kế toán hoặc Giám sát.', 16, 1);
        RETURN;
    END

    BEGIN TRY
        OPEN SYMMETRIC KEY AppSymKey DECRYPTION BY CERTIFICATE AppCert;

        SELECT
            ra.AssignedRole,
            it.TypeName AS InsuranceType,
            ic.ContractNumber,
            ip.FullName AS InsuredName,
            ic.StartDate,
            ic.EndDate,
            CAST(CONVERT(VARCHAR(MAX), DecryptByKey(ic.InsuranceValue)) AS DECIMAL(18, 2)) AS InsuranceValue,
            CAST(CONVERT(VARCHAR(MAX), DecryptByKey(ic.PremiumAmount)) AS DECIMAL(18, 2)) AS PremiumAmount,
            ic.Status
        FROM RoleAssignments ra
        JOIN InsuranceTypes it ON ra.InsuranceTypeID = it.InsuranceTypeID
        JOIN InsuranceContracts ic ON ic.InsuranceTypeID = ra.InsuranceTypeID
        JOIN InsuredPersons ip ON ic.InsuredPersonID = ip.InsuredPersonID
        WHERE ra.UserID = @CurrentUserID AND ra.AssignedRole = @CurrentUserRole;

        CLOSE SYMMETRIC KEY AppSymKey;
    END TRY
    BEGIN CATCH
        BEGIN TRY
            CLOSE SYMMETRIC KEY AppSymKey;
        END TRY
        BEGIN CATCH
        END CATCH;

        THROW;
    END CATCH
END;
GO



-- SP quản lý người dùng khác (ví dụ)
CREATE PROCEDURE UpdateUserRoleOrStatus
    @UserID INT,
    @NewRole NVARCHAR(50) = NULL,
    @NewIsActive BIT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    -- *** Thêm kiểm tra quyền của người thực thi SP này (ví dụ: chỉ Admin mới được gọi) ***

    IF NOT EXISTS (SELECT 1 FROM Users WHERE UserID = @UserID)
    BEGIN
        RAISERROR('Người dùng không tồn tại.', 16, 1);
        RETURN;
    END

    IF @NewRole IS NOT NULL AND @NewRole NOT IN ('ContractCreator', 'Insured', 'Accountant', 'Supervisor')
    BEGIN
        RAISERROR('Vai trò mới không hợp lệ.', 16, 1);
        RETURN;
    END

    UPDATE Users
    SET
        Role = ISNULL(@NewRole, Role),
        IsActive = ISNULL(@NewIsActive, IsActive)
    WHERE UserID = @UserID;

    -- Nếu đổi vai trò thành không phải Accountant/Supervisor, xóa các phân công cũ
    IF @NewRole IS NOT NULL AND @NewRole NOT IN ('Accountant', 'Supervisor')
    BEGIN
        DELETE FROM RoleAssignments WHERE UserID = @UserID;
    END
END
GO

CREATE PROCEDURE AssignAccountantOrSupervisorToType
    @AssigningUserID INT, -- Người thực hiện gán (cần kiểm tra quyền)
    @TargetUserID INT,
    @InsuranceTypeID INT,
    @RoleToAssign NVARCHAR(50) -- 'Accountant' or 'Supervisor'
AS
BEGIN
    SET NOCOUNT ON;
    -- *** Thêm kiểm tra quyền của @AssigningUserID ***

    IF @RoleToAssign NOT IN ('Accountant', 'Supervisor')
    BEGIN
         RAISERROR('Chỉ có thể gán vai trò Accountant hoặc Supervisor.', 16, 1);
         RETURN;
    END

    DECLARE @TargetUserRole NVARCHAR(50);
    SELECT @TargetUserRole = Role FROM Users WHERE UserID = @TargetUserID AND IsActive = 1;

    IF @TargetUserRole <> @RoleToAssign
    BEGIN
         RAISERROR('Vai trò cần gán không khớp với vai trò của người dùng trong bảng Users.', 16, 1);
         RETURN;
    END

    IF NOT EXISTS (SELECT 1 FROM InsuranceTypes WHERE InsuranceTypeID = @InsuranceTypeID)
    BEGIN
         RAISERROR('Loại bảo hiểm không tồn tại.', 16, 1);
         RETURN;
    END

    -- Kiểm tra trùng lặp trước khi insert
    IF NOT EXISTS (SELECT 1 FROM RoleAssignments WHERE UserID = @TargetUserID AND InsuranceTypeID = @InsuranceTypeID AND AssignedRole = @RoleToAssign)
    BEGIN
        INSERT INTO RoleAssignments(UserID, InsuranceTypeID, AssignedRole)
        VALUES (@TargetUserID, @InsuranceTypeID, @RoleToAssign);
    END
END
GO

CREATE PROCEDURE RevokeAccountantOrSupervisorFromType
    @RevokingUserID INT, -- Người thực hiện thu hồi (cần kiểm tra quyền)
    @TargetUserID INT,
    @InsuranceTypeID INT,
    @RoleToRevoke NVARCHAR(50) -- 'Accountant' or 'Supervisor'
AS
BEGIN
     SET NOCOUNT ON;
     -- *** Thêm kiểm tra quyền của @RevokingUserID ***

     IF @RoleToRevoke NOT IN ('Accountant', 'Supervisor')
     BEGIN
         RAISERROR('Chỉ có thể thu hồi vai trò Accountant hoặc Supervisor.', 16, 1);
         RETURN;
     END

     DELETE FROM RoleAssignments
     WHERE UserID = @TargetUserID
       AND InsuranceTypeID = @InsuranceTypeID
       AND AssignedRole = @RoleToRevoke;
END
GO


-- ****** TRIGGER GHI NHẬT KÝ (Sửa ChangedByUserID) ******

-- Helper Function để lấy chi tiết thay đổi (ví dụ đơn giản)
CREATE FUNCTION dbo.fn_GetAuditDetails (@ActionType NVARCHAR(10), @Inserted XML, @Deleted XML)
RETURNS NVARCHAR(MAX)
AS
BEGIN
    -- Đây là ví dụ rất cơ bản, bạn có thể làm phức tạp hơn nhiều, ví dụ dùng JSON
    DECLARE @Details NVARCHAR(MAX) = '';
    IF @ActionType = 'INSERT' SET @Details = ISNULL(CONVERT(NVARCHAR(MAX), @Inserted, 1), '');
    IF @ActionType = 'DELETE' SET @Details = ISNULL(CONVERT(NVARCHAR(MAX), @Deleted, 1), '');
    IF @ActionType = 'UPDATE' SET @Details = 'OLD: ' + ISNULL(CONVERT(NVARCHAR(MAX), @Deleted, 1), '') + ' | NEW: ' + ISNULL(CONVERT(NVARCHAR(MAX), @Inserted, 1), '');
    RETURN @Details;
END;
GO

-- Trigger cho Users
CREATE TRIGGER trg_Audit_Users ON Users AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @ActionType NVARCHAR(10);
    DECLARE @CurrentUserID INT = ISNULL(CAST(SESSION_CONTEXT(N'UserID') AS INT), -1); -- -1: User không xác định/hệ thống

    IF EXISTS (SELECT * FROM inserted) AND EXISTS (SELECT * FROM deleted)
        SET @ActionType = 'UPDATE';
    ELSE IF EXISTS (SELECT * FROM inserted)
        SET @ActionType = 'INSERT';
    ELSE
        SET @ActionType = 'DELETE';

    INSERT INTO AuditLogs (TableName, ActionType, RecordPK, ChangedByUserID, ChangeDate, Details)
    SELECT
        'Users',
        @ActionType,
        COALESCE(i.UserID, d.UserID), -- Lấy PK
        @CurrentUserID,
        SYSDATETIME(),
        dbo.fn_GetAuditDetails(@ActionType, (SELECT i.* FOR XML PATH('row'), TYPE), (SELECT d.* FOR XML PATH('row'), TYPE))
    FROM inserted i FULL OUTER JOIN deleted d ON i.UserID = d.UserID
    -- Chỉ log UPDATE nếu các cột quan trọng thay đổi (ví dụ)
    WHERE @ActionType IN ('INSERT', 'DELETE') OR
          (@ActionType = 'UPDATE' AND (
            ISNULL(i.Username,'') <> ISNULL(d.Username,'') OR
            ISNULL(i.FullName,'') <> ISNULL(d.FullName,'') OR
            ISNULL(i.Role,'') <> ISNULL(d.Role,'') OR
            ISNULL(i.IsActive,0) <> ISNULL(d.IsActive,0)
          ));
END;
GO

-- Trigger cho InsuranceTypes (Tương tự Users)
CREATE TRIGGER trg_Audit_InsuranceTypes ON InsuranceTypes AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @ActionType NVARCHAR(10);
    DECLARE @CurrentUserID INT = ISNULL(CAST(SESSION_CONTEXT(N'UserID') AS INT), -1);

    IF EXISTS (SELECT * FROM inserted) AND EXISTS (SELECT * FROM deleted) SET @ActionType = 'UPDATE';
    ELSE IF EXISTS (SELECT * FROM inserted) SET @ActionType = 'INSERT';
    ELSE SET @ActionType = 'DELETE';

    INSERT INTO AuditLogs (TableName, ActionType, RecordPK, ChangedByUserID, ChangeDate, Details)
    SELECT 'InsuranceTypes', @ActionType, COALESCE(i.InsuranceTypeID, d.InsuranceTypeID), @CurrentUserID, SYSDATETIME(), dbo.fn_GetAuditDetails(@ActionType, (SELECT i.* FOR XML PATH('row'), TYPE), (SELECT d.* FOR XML PATH('row'), TYPE))
    FROM inserted i FULL OUTER JOIN deleted d ON i.InsuranceTypeID = d.InsuranceTypeID
    WHERE @ActionType IN ('INSERT', 'DELETE') OR (@ActionType = 'UPDATE' AND ISNULL(i.TypeName,'') <> ISNULL(d.TypeName,''));
END;
GO

-- Trigger cho InsuredPersons (Tương tự)
CREATE TRIGGER trg_Audit_InsuredPersons ON InsuredPersons AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @ActionType NVARCHAR(10);
     DECLARE @CurrentUserID INT = ISNULL(CAST(SESSION_CONTEXT(N'UserID') AS INT), -1);

    IF EXISTS (SELECT * FROM inserted) AND EXISTS (SELECT * FROM deleted) SET @ActionType = 'UPDATE';
    ELSE IF EXISTS (SELECT * FROM inserted) SET @ActionType = 'INSERT';
    ELSE SET @ActionType = 'DELETE';

    INSERT INTO AuditLogs (TableName, ActionType, RecordPK, ChangedByUserID, ChangeDate, Details)
    SELECT 'InsuredPersons', @ActionType, COALESCE(i.InsuredPersonID, d.InsuredPersonID), @CurrentUserID, SYSDATETIME(),
           -- Không log chi tiết MedicalHistory mã hóa ra đây vì lý do bảo mật và kích thước
           CASE
               WHEN @ActionType = 'INSERT' THEN 'Inserted InsuredPersonID: ' + CAST(COALESCE(i.InsuredPersonID, d.InsuredPersonID) AS VARCHAR)
               WHEN @ActionType = 'DELETE' THEN 'Deleted InsuredPersonID: ' + CAST(COALESCE(i.InsuredPersonID, d.InsuredPersonID) AS VARCHAR)
               WHEN @ActionType = 'UPDATE' THEN 'Updated InsuredPersonID: ' + CAST(i.InsuredPersonID AS VARCHAR) + ' (Details omitted for brevity/security)'
               ELSE ''
           END
    FROM inserted i FULL OUTER JOIN deleted d ON i.InsuredPersonID = d.InsuredPersonID
    WHERE @ActionType IN ('INSERT', 'DELETE') OR
          (@ActionType = 'UPDATE' AND (
            ISNULL(i.FullName,'') <> ISNULL(d.FullName,'') OR
            ISNULL(i.Gender,'') <> ISNULL(d.Gender,'') OR
            ISNULL(i.DateOfBirth,'') <> ISNULL(d.DateOfBirth,'') OR
            ISNULL(i.Workplace,'') <> ISNULL(d.Workplace,'') OR
            ISNULL(i.PermanentAddress,'') <> ISNULL(d.PermanentAddress,'') OR
            ISNULL(i.TemporaryAddress,'') <> ISNULL(d.TemporaryAddress,'') OR
            ISNULL(i.ContactAddress,'') <> ISNULL(d.ContactAddress,'') OR
            ISNULL(i.UserID,0) <> ISNULL(d.UserID,0) OR
            -- So sánh hash của medical history nếu muốn biết nó có thay đổi không, không log nội dung
            HASHBYTES('SHA2_256', ISNULL(i.MedicalHistory,0x)) <> HASHBYTES('SHA2_256', ISNULL(d.MedicalHistory,0x))
          ));
END;
GO

-- Trigger cho InsuranceContracts (Tương tự, không log giá trị mã hóa)
CREATE TRIGGER trg_Audit_InsuranceContracts ON InsuranceContracts AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @ActionType NVARCHAR(10);
    DECLARE @CurrentUserID INT = ISNULL(CAST(SESSION_CONTEXT(N'UserID') AS INT), -1);

    IF EXISTS (SELECT * FROM inserted) AND EXISTS (SELECT * FROM deleted) SET @ActionType = 'UPDATE';
    ELSE IF EXISTS (SELECT * FROM inserted) SET @ActionType = 'INSERT';
    ELSE SET @ActionType = 'DELETE';

    INSERT INTO AuditLogs (TableName, ActionType, RecordPK, ChangedByUserID, ChangeDate, Details)
    SELECT 'InsuranceContracts', @ActionType, COALESCE(i.ContractID, d.ContractID), @CurrentUserID, SYSDATETIME(),
           CASE
               WHEN @ActionType = 'INSERT' THEN 'Inserted ContractID: ' + CAST(COALESCE(i.ContractID, d.ContractID) AS VARCHAR) + ' Number: ' + i.ContractNumber
               WHEN @ActionType = 'DELETE' THEN 'Deleted ContractID: ' + CAST(COALESCE(i.ContractID, d.ContractID) AS VARCHAR) + ' Number: ' + d.ContractNumber
               WHEN @ActionType = 'UPDATE' THEN 'Updated ContractID: ' + CAST(i.ContractID AS VARCHAR) + ' Number: ' + i.ContractNumber + ' (Encrypted details omitted)'
               ELSE ''
           END
    FROM inserted i FULL OUTER JOIN deleted d ON i.ContractID = d.ContractID
    WHERE @ActionType IN ('INSERT', 'DELETE') OR
          (@ActionType = 'UPDATE' AND (
            ISNULL(i.ContractNumber,'') <> ISNULL(d.ContractNumber,'') OR
            ISNULL(i.InsuranceTypeID,0) <> ISNULL(d.InsuranceTypeID,0) OR
            ISNULL(i.InsuredPersonID,0) <> ISNULL(d.InsuredPersonID,0) OR
            ISNULL(i.ContractCreatorUserID,0) <> ISNULL(d.ContractCreatorUserID,0) OR
            ISNULL(i.StartDate,'') <> ISNULL(d.StartDate,'') OR
            ISNULL(i.EndDate,'') <> ISNULL(d.EndDate,'') OR
            ISNULL(i.PaymentFrequency,'') <> ISNULL(d.PaymentFrequency,'') OR
            ISNULL(i.Status,'') <> ISNULL(d.Status,'') OR
            HASHBYTES('SHA2_256', ISNULL(i.InsuranceValue,0x)) <> HASHBYTES('SHA2_256', ISNULL(d.InsuranceValue,0x)) OR
            HASHBYTES('SHA2_256', ISNULL(i.PremiumAmount,0x)) <> HASHBYTES('SHA2_256', ISNULL(d.PremiumAmount,0x))
          ));
END;
GO

-- Trigger cho RoleAssignments (Tương tự)
CREATE TRIGGER trg_Audit_RoleAssignments ON RoleAssignments AFTER INSERT, UPDATE, DELETE AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @ActionType NVARCHAR(10);
    DECLARE @CurrentUserID INT = ISNULL(CAST(SESSION_CONTEXT(N'UserID') AS INT), -1);

    IF EXISTS (SELECT * FROM inserted) AND EXISTS (SELECT * FROM deleted) SET @ActionType = 'UPDATE';
    ELSE IF EXISTS (SELECT * FROM inserted) SET @ActionType = 'INSERT';
    ELSE SET @ActionType = 'DELETE';

    INSERT INTO AuditLogs (TableName, ActionType, RecordPK, ChangedByUserID, ChangeDate, Details)
    SELECT 'RoleAssignments', @ActionType, COALESCE(i.AssignmentID, d.AssignmentID), @CurrentUserID, SYSDATETIME(), dbo.fn_GetAuditDetails(@ActionType, (SELECT i.* FOR XML PATH('row'), TYPE), (SELECT d.* FOR XML PATH('row'), TYPE))
    FROM inserted i FULL OUTER JOIN deleted d ON i.AssignmentID = d.AssignmentID
    WHERE @ActionType IN ('INSERT', 'DELETE') OR
          (@ActionType = 'UPDATE' AND (
            ISNULL(i.UserID,0) <> ISNULL(d.UserID,0) OR
            ISNULL(i.InsuranceTypeID,0) <> ISNULL(d.InsuranceTypeID,0) OR
            ISNULL(i.AssignedRole,'') <> ISNULL(d.AssignedRole,'')
          ));
END;
GO


-- ****** ROW-LEVEL SECURITY (RLS) ******

-- Hàm lọc (FILTER): Xác định dòng nào người dùng được *xem*
CREATE FUNCTION dbo.fn_rls_FilterInsuranceContracts(@CurrentUserID INT)
RETURNS TABLE
WITH SCHEMABINDING -- Cần thiết cho RLS
AS
RETURN
(
    SELECT 1 AS Result -- Trả về 1 nếu được phép xem
    FROM dbo.InsuranceContracts ic -- Tham chiếu đến bảng gốc mà Policy áp dụng
    LEFT JOIN dbo.InsuredPersons ip ON ic.InsuredPersonID = ip.InsuredPersonID -- Join để kiểm tra người được BH
    WHERE
        -- 1. Người dùng là người tạo hợp đồng này
        ic.ContractCreatorUserID = @CurrentUserID

        -- 2. Hoặc, người dùng là người được bảo hiểm trong hợp đồng này (liên kết qua InsuredPersons.UserID)
        OR (ip.UserID IS NOT NULL AND ip.UserID = @CurrentUserID)

        -- 3. Hoặc, người dùng là Kế toán hoặc Giám sát được phân công cho loại bảo hiểm của hợp đồng này
        OR EXISTS (
            SELECT 1
            FROM dbo.RoleAssignments ra
            WHERE ra.UserID = @CurrentUserID
              AND ra.InsuranceTypeID = ic.InsuranceTypeID
              AND ra.AssignedRole IN ('Accountant', 'Supervisor')
        )
);
GO

-- Hàm chặn (BLOCK): Xác định người dùng có được *thay đổi* (UPDATE, DELETE) dòng dữ liệu hay không
CREATE FUNCTION dbo.fn_rls_BlockInsuranceContractsChanges(@CurrentUserID INT)
RETURNS TABLE
WITH SCHEMABINDING
AS
RETURN
(
    SELECT 1 AS Result -- Trả về 1 nếu được phép thay đổi
    FROM dbo.InsuranceContracts ic
    WHERE
        -- Chỉ người tạo hợp đồng mới được phép thay đổi hợp đồng của họ
        ic.ContractCreatorUserID = @CurrentUserID
);
GO

-- Tạo Security Policy áp dụng các hàm trên
-- Lưu ý: Policy này cần được tạo SAU khi các hàm đã được tạo
CREATE SECURITY POLICY Policy_Filter_InsuranceContracts
ADD FILTER PREDICATE dbo.fn_rls_FilterInsuranceContracts(CAST(SESSION_CONTEXT(N'UserID') AS INT)) 
    ON dbo.InsuranceContracts,
ADD BLOCK PREDICATE dbo.fn_rls_BlockInsuranceContractsChanges(CAST(SESSION_CONTEXT(N'UserID') AS INT)) 
    ON dbo.InsuranceContracts BEFORE UPDATE,
ADD BLOCK PREDICATE dbo.fn_rls_BlockInsuranceContractsChanges(CAST(SESSION_CONTEXT(N'UserID') AS INT)) 
    ON dbo.InsuranceContracts BEFORE DELETE
WITH (STATE = ON);


-- ****** Dữ liệu mẫu ******
-- User
INSERT INTO Users (Username, PasswordHash, FullName, Role, IsActive)
VALUES 
(N'admin01', HASHBYTES('SHA2_256', CAST(N'admin@123' AS VARBINARY(MAX))), N'Admin Chính', N'Admin', 1),
(N'creator01', HASHBYTES('SHA2_256', CAST(N'creator@123' AS VARBINARY(MAX))), N'Nguyễn Văn A', N'ContractCreator', 1),
(N'creator02', HASHBYTES('SHA2_256', CAST(N'creator@456' AS VARBINARY(MAX))), N'Trần Thị B', N'ContractCreator', 1),
(N'insured01', HASHBYTES('SHA2_256', CAST(N'insured@123' AS VARBINARY(MAX))), N'Phạm Minh C', N'Insured', 1),
(N'accountant01', HASHBYTES('SHA2_256', CAST(N'acc@123' AS VARBINARY(MAX))), N'Lê Văn D', N'Accountant', 1),
(N'supervisor01', HASHBYTES('SHA2_256', CAST(N'sup@123' AS VARBINARY(MAX))), N'Vũ Thị E', N'Supervisor', 1);
GO

--InsuranceTypes
INSERT INTO InsuranceTypes (TypeName)
VALUES 
(N'Bảo hiểm Y tế'),
(N'Bảo hiểm Tai nạn'),
(N'Bảo hiểm Nhân thọ');
GO

--InsuredPersons
EXEC CreateInsuredPerson 
    @FullName = N'Phạm Minh C',
    @Gender = N'Nam',
    @DateOfBirth = '1990-05-21',
    @Workplace = N'Công ty ABC',
    @PermanentAddress = N'123 Nguyễn Trãi',
    @TemporaryAddress = N'456 Lê Văn Sỹ',
    @ContactAddress = N'456 Lê Văn Sỹ',
    @MedicalHistory = N'Không có tiền sử bệnh lý',
    @UserID = 4; -- ID của insured01

EXEC CreateInsuredPerson 
    @FullName = N'Đặng Thị F',
    @Gender = N'Nữ',
    @DateOfBirth = '1985-08-10',
    @Workplace = N'Trường THPT XYZ',
    @PermanentAddress = N'22 Nguyễn Huệ',
    @TemporaryAddress = NULL,
    @ContactAddress = N'22 Nguyễn Huệ',
    @MedicalHistory = N'Cao huyết áp',
    @UserID = NULL;

EXEC CreateInsuredPerson 
    @FullName = N'Hồ Văn G',
    @Gender = N'Nam',
    @DateOfBirth = '1978-12-01',
    @Workplace = N'Bệnh viện 115',
    @PermanentAddress = N'78 Hoàng Văn Thụ',
    @TemporaryAddress = NULL,
    @ContactAddress = N'78 Hoàng Văn Thụ',
    @MedicalHistory = N'Đái tháo đường',
    @UserID = NULL;
GO



--RoleAssignments
EXEC AssignAccountantOrSupervisorToType
    @AssigningUserID = 1, -- admin01
    @TargetUserID = 5, -- accountant01
    @InsuranceTypeID = 1,
    @RoleToAssign = 'Accountant';

EXEC AssignAccountantOrSupervisorToType
    @AssigningUserID = 1, -- admin01
    @TargetUserID = 6, -- supervisor01
    @InsuranceTypeID = 2,
    @RoleToAssign = 'Supervisor';
GO
