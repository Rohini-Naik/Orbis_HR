-- Bootstrap the read-write application-state database for Orbis_HR.
-- Run once as the local MySQL root (auth_socket):
--
--     sudo mysql < scripts/bootstrap_app_mysql.sql
--
-- Creates the `orbis_app` database and a dedicated read-write `orbis_app` user.
-- This database is isolated from `orbis_hr` (HR data), so the application user
-- has no access to employee records. The app creates its own tables on startup.
--
-- BEFORE RUNNING: replace __SET_A_STRONG_PASSWORD__ below with the password you
-- put in MYSQL_APP_PASSWORD in .env. Never commit a real password to this file.

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

CREATE DATABASE IF NOT EXISTS orbis_app
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'orbis_app'@'localhost' IDENTIFIED WITH caching_sha2_password BY '__SET_A_STRONG_PASSWORD__';
CREATE USER IF NOT EXISTS 'orbis_app'@'127.0.0.1' IDENTIFIED WITH caching_sha2_password BY '__SET_A_STRONG_PASSWORD__';
CREATE USER IF NOT EXISTS 'orbis_app'@'%'         IDENTIFIED WITH caching_sha2_password BY '__SET_A_STRONG_PASSWORD__';

GRANT ALL PRIVILEGES ON orbis_app.* TO 'orbis_app'@'localhost';
GRANT ALL PRIVILEGES ON orbis_app.* TO 'orbis_app'@'127.0.0.1';
GRANT ALL PRIVILEGES ON orbis_app.* TO 'orbis_app'@'%';
FLUSH PRIVILEGES;
