-- Bootstrap a read-write HR-data user for admin employee management.
-- Run once as the local MySQL root (auth_socket):
--
--     sudo mysql < scripts/bootstrap_hr_admin_mysql.sql
--
-- This user can manage rows in orbis_hr.employees (add/update/delete employees
-- from the admin UI). The NL->SQL engine continues to use the read-only
-- `orbis_user`, so LLM-generated queries can never write.
--
-- BEFORE RUNNING: replace __SET_A_STRONG_PASSWORD__ below with the password you
-- put in MYSQL_HR_ADMIN_PASSWORD in .env. Never commit a real password to this file.

-- Guard: refuse to run while the password placeholder is still in place.
-- The sentinel is assembled from fragments so the substitution, which rewrites
-- every literal occurrence of the placeholder, cannot rewrite this side too.
SET @guard := IF(
  '__SET_A_STRONG_PASSWORD__' = CONCAT('__SET', '_A_STRONG', '_PASSWORD__'),
  'SELECT `ABORT: password placeholder not substituted — run ./setup.sh (or setup.bat) instead`',
  'DO 0');
PREPARE guard_check FROM @guard;
EXECUTE guard_check;
DEALLOCATE PREPARE guard_check;

CREATE USER IF NOT EXISTS 'orbis_hr_admin'@'localhost' IDENTIFIED WITH caching_sha2_password BY '__SET_A_STRONG_PASSWORD__';
CREATE USER IF NOT EXISTS 'orbis_hr_admin'@'127.0.0.1' IDENTIFIED WITH caching_sha2_password BY '__SET_A_STRONG_PASSWORD__';
CREATE USER IF NOT EXISTS 'orbis_hr_admin'@'%'         IDENTIFIED WITH caching_sha2_password BY '__SET_A_STRONG_PASSWORD__';

GRANT SELECT, INSERT, UPDATE, DELETE ON orbis_hr.employees TO 'orbis_hr_admin'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON orbis_hr.employees TO 'orbis_hr_admin'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE, DELETE ON orbis_hr.employees TO 'orbis_hr_admin'@'%';
FLUSH PRIVILEGES;
