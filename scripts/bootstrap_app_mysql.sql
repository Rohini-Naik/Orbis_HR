-- Bootstrap the read-write application-state database for Orbis_HR.
-- Run once as the local MySQL root (auth_socket):
--
--     sudo mysql < scripts/bootstrap_app_mysql.sql
--
-- Creates the `orbis_app` database and a dedicated read-write `orbis_app` user.
-- This database is isolated from `orbis_hr` (HR data), so the application user
-- has no access to employee records. The app creates its own tables on startup.

CREATE DATABASE IF NOT EXISTS orbis_app
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'orbis_app'@'localhost' IDENTIFIED WITH caching_sha2_password BY 'Ovi@2021';
CREATE USER IF NOT EXISTS 'orbis_app'@'127.0.0.1' IDENTIFIED WITH caching_sha2_password BY 'Ovi@2021';
CREATE USER IF NOT EXISTS 'orbis_app'@'%'         IDENTIFIED WITH caching_sha2_password BY 'Ovi@2021';

GRANT ALL PRIVILEGES ON orbis_app.* TO 'orbis_app'@'localhost';
GRANT ALL PRIVILEGES ON orbis_app.* TO 'orbis_app'@'127.0.0.1';
GRANT ALL PRIVILEGES ON orbis_app.* TO 'orbis_app'@'%';
FLUSH PRIVILEGES;
