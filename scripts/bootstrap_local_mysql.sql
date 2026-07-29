-- Bootstrap the LOCAL MySQL for Orbis_HR.
-- Run from the project root as the local MySQL root:
--
--     sudo mysql < scripts/bootstrap_local_mysql.sql
--
-- Creates the orbis_hr database, the employees table, and a read-only
-- orbis_user (matching .env). Employee rows are loaded separately by
--
--     python -m app.provision load-employees
--
-- rather than with LOAD DATA LOCAL INFILE, which would need the SUPER
-- privilege, a client-side flag, and a path relative to the working directory.
--
-- BEFORE RUNNING: replace __SET_A_STRONG_PASSWORD__ below with the password you
-- put in MYSQL_PASSWORD in .env. Never commit a real password to this file.
-- (`setup.py` does this substitution for you.)
-- NOTE: re-running drops the employees table, so only run it on a fresh setup.

-- Guard: refuse to run while the password placeholder is still in place.
-- Running this file raw would set the application user's password to the
-- literal placeholder and silently lock the app out of its own database.
-- When substituted, the two sides differ and this is a no-op.
-- The sentinel is assembled from fragments so the substitution, which rewrites
-- every literal occurrence of the placeholder, cannot rewrite this side too.
SET @guard := IF(
  '__SET_A_STRONG_PASSWORD__' = CONCAT('__SET', '_A_STRONG', '_PASSWORD__'),
  'SELECT `ABORT: password placeholder not substituted — run ./setup.sh (or setup.bat) instead`',
  'DO 0');
PREPARE guard_check FROM @guard;
EXECUTE guard_check;
DEALLOCATE PREPARE guard_check;

CREATE DATABASE IF NOT EXISTS orbis_hr
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE orbis_hr;

DROP TABLE IF EXISTS employees;
CREATE TABLE employees (
  -- Business identifier, e.g. 'EMP1001'. Never reused: a recycled id would
  -- hand a departed colleague's account access to whoever inherits the number.
  EmployeeID            VARCHAR(20) PRIMARY KEY,
  FullName              VARCHAR(255) NOT NULL,
  -- Company address: the login identity. Unique across the organisation.
  Email                 VARCHAR(255) UNIQUE,
  -- Where onboarding invitations are sent. Private: never exposed to the
  -- NL->SQL engine (see rag_engine/nl_to_sql.py).
  PersonalEmail         VARCHAR(255),
  Role                  VARCHAR(100),
  Department            VARCHAR(100),
  Location              VARCHAR(100),
  DateOfJoining         DATE,
  ManagerID             VARCHAR(20),
  ManagerName           VARCHAR(255),
  CasualLeaveBalance    INT,
  CasualLeaveUsed       INT,
  SickLeaveBalance      INT,
  SickLeaveUsed         INT,
  EarnedLeaveBalance    INT,
  EarnedLeaveUsed       INT,
  LastAppraisalDate     DATE,
  NextAppraisalDate     DATE,
  POSHTrainingCompleted VARCHAR(10),
  POSHTrainingDate      DATE,
  PerformanceRating     VARCHAR(40),
  AnnualCTC_INR         INT,
  EmploymentType        VARCHAR(20),
  IsAdmin               VARCHAR(10),
  -- Lifecycle: 'active' or 'exited'. Employees are marked exited, never deleted.
  Status                VARCHAR(20) NOT NULL DEFAULT 'active',
  INDEX idx_department (Department),
  INDEX idx_location (Location),
  INDEX idx_role (Role),
  INDEX idx_manager (ManagerID),
  INDEX idx_status (Status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Read-only application user (credentials match .env).
CREATE USER IF NOT EXISTS 'orbis_user'@'localhost'
  IDENTIFIED WITH caching_sha2_password BY '__SET_A_STRONG_PASSWORD__';
CREATE USER IF NOT EXISTS 'orbis_user'@'127.0.0.1'
  IDENTIFIED WITH caching_sha2_password BY '__SET_A_STRONG_PASSWORD__';
CREATE USER IF NOT EXISTS 'orbis_user'@'%'
  IDENTIFIED WITH caching_sha2_password BY '__SET_A_STRONG_PASSWORD__';
ALTER USER 'orbis_user'@'localhost' IDENTIFIED WITH caching_sha2_password BY '__SET_A_STRONG_PASSWORD__';
ALTER USER 'orbis_user'@'127.0.0.1' IDENTIFIED WITH caching_sha2_password BY '__SET_A_STRONG_PASSWORD__';
ALTER USER 'orbis_user'@'%'         IDENTIFIED WITH caching_sha2_password BY '__SET_A_STRONG_PASSWORD__';

GRANT SELECT ON orbis_hr.* TO 'orbis_user'@'localhost';
GRANT SELECT ON orbis_hr.* TO 'orbis_user'@'127.0.0.1';
GRANT SELECT ON orbis_hr.* TO 'orbis_user'@'%';
FLUSH PRIVILEGES;

SELECT 'orbis_hr ready — now run: python -m app.provision load-employees' AS next_step;
