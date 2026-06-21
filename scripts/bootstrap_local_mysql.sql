-- Bootstrap the LOCAL MySQL for Orbis_HR.
-- Run from the project root as the local MySQL root (auth_socket):
--
--     sudo mysql --local-infile=1 < scripts/bootstrap_local_mysql.sql
--
-- Creates the orbis_hr database, the employees table, loads the CSV, and
-- creates a read-only orbis_user (matching .env). Safe to re-run.

SET GLOBAL local_infile = 1;

CREATE DATABASE IF NOT EXISTS orbis_hr
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE orbis_hr;

DROP TABLE IF EXISTS employees;
CREATE TABLE employees (
  EmployeeID INT PRIMARY KEY,
  EmployeeName VARCHAR(255),
  Age INT,
  Gender VARCHAR(20),
  Location VARCHAR(100),
  Department VARCHAR(100),
  Role VARCHAR(100),
  YearsAtCompany INT,
  DateOfJoining DATE,
  YearsInCurrentRole INT,
  EducationLevel VARCHAR(50),
  MonthlySalaryINR INT,
  WorkHoursPerWeek INT,
  ProjectsHandled INT,
  TrainingHoursLastYear INT,
  SickLeavesLastYear INT,
  OvertimeHoursLastMonth INT,
  ManagerRating INT,
  DisciplinaryNotices INT,
  PolicyViolationsLastYear INT,
  PerformanceRating INT,
  PromotionLast2Years VARCHAR(10),
  ComplianceRiskLevel VARCHAR(20),
  AttritionRisk VARCHAR(20),
  INDEX idx_department (Department),
  INDEX idx_location (Location),
  INDEX idx_role (Role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Load the CSV (path is relative to the project root where you run this).
LOAD DATA LOCAL INFILE 'database_data/employees (1).csv'
INTO TABLE employees
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(EmployeeID, EmployeeName, Age, Gender, Location, Department, Role, YearsAtCompany,
 @DateOfJoining, YearsInCurrentRole, EducationLevel, MonthlySalaryINR, WorkHoursPerWeek,
 ProjectsHandled, TrainingHoursLastYear, SickLeavesLastYear, OvertimeHoursLastMonth,
 ManagerRating, DisciplinaryNotices, PolicyViolationsLastYear, PerformanceRating,
 PromotionLast2Years, ComplianceRiskLevel, AttritionRisk)
SET DateOfJoining = STR_TO_DATE(@DateOfJoining, '%m/%d/%Y');

-- Read-only application user (credentials match .env).
CREATE USER IF NOT EXISTS 'orbis_user'@'localhost'
  IDENTIFIED WITH caching_sha2_password BY 'Ovi@2021';
CREATE USER IF NOT EXISTS 'orbis_user'@'127.0.0.1'
  IDENTIFIED WITH caching_sha2_password BY 'Ovi@2021';
CREATE USER IF NOT EXISTS 'orbis_user'@'%'
  IDENTIFIED WITH caching_sha2_password BY 'Ovi@2021';
ALTER USER 'orbis_user'@'localhost' IDENTIFIED WITH caching_sha2_password BY 'Ovi@2021';
ALTER USER 'orbis_user'@'127.0.0.1' IDENTIFIED WITH caching_sha2_password BY 'Ovi@2021';
ALTER USER 'orbis_user'@'%'         IDENTIFIED WITH caching_sha2_password BY 'Ovi@2021';

GRANT SELECT ON orbis_hr.* TO 'orbis_user'@'localhost';
GRANT SELECT ON orbis_hr.* TO 'orbis_user'@'127.0.0.1';
GRANT SELECT ON orbis_hr.* TO 'orbis_user'@'%';
FLUSH PRIVILEGES;

SELECT COUNT(*) AS employees_loaded FROM employees;
