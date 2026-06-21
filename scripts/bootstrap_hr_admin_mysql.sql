-- Bootstrap a read-write HR-data user for admin employee management.
-- Run once as the local MySQL root (auth_socket):
--
--     sudo mysql < scripts/bootstrap_hr_admin_mysql.sql
--
-- This user can manage rows in orbis_hr.employees (add/update/delete employees
-- from the admin UI). The NL->SQL engine continues to use the read-only
-- `orbis_user`, so LLM-generated queries can never write.

CREATE USER IF NOT EXISTS 'orbis_hr_admin'@'localhost' IDENTIFIED WITH caching_sha2_password BY 'Ovi@2021';
CREATE USER IF NOT EXISTS 'orbis_hr_admin'@'127.0.0.1' IDENTIFIED WITH caching_sha2_password BY 'Ovi@2021';
CREATE USER IF NOT EXISTS 'orbis_hr_admin'@'%'         IDENTIFIED WITH caching_sha2_password BY 'Ovi@2021';

GRANT SELECT, INSERT, UPDATE, DELETE ON orbis_hr.employees TO 'orbis_hr_admin'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON orbis_hr.employees TO 'orbis_hr_admin'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE, DELETE ON orbis_hr.employees TO 'orbis_hr_admin'@'%';
FLUSH PRIVILEGES;
