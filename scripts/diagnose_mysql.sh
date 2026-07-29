#!/usr/bin/env bash
# Orbis MySQL access diagnostic — prints the real errors setup is hiding.
echo "=== 1. is the mysql client installed? ==="
command -v mysql && mysql --version || echo "  mysql NOT on PATH"
echo
echo "=== 2. is the server running? ==="
(systemctl is-active mysql 2>/dev/null || systemctl is-active mysqld 2>/dev/null || echo "unknown") | sed 's/^/  /'
ss -lntp 2>/dev/null | grep -E ':3306' | sed 's/^/  /' || echo "  nothing listening on 3306"
ls -la /var/run/mysqld/mysqld.sock /tmp/mysql.sock 2>/dev/null | sed 's/^/  /' || echo "  no socket found at the usual paths"
echo
echo "=== 3. each connection attempt, with the REAL error ==="
try() { echo "--- $* ---"; "$@" -e "SELECT 1" 2>&1 | head -3 | sed 's/^/    /'; }
try mysql --no-defaults -u root -h localhost -P 3306
try mysql -u root
try sudo mysql --no-defaults -h localhost -P 3306
try sudo mysql --no-defaults
try sudo mysql
echo
echo "=== 4. can the working one do what setup needs? ==="
for c in "sudo mysql" "sudo mysql --no-defaults" "mysql -u root"; do
  if $c -e "SELECT 1" >/dev/null 2>&1; then
    echo "  '$c' connects — testing privileges:"
    $c -e "CREATE DATABASE IF NOT EXISTS orbis_probe; DROP DATABASE orbis_probe;
           CREATE USER IF NOT EXISTS 'orbis_probe'@'localhost'; DROP USER 'orbis_probe'@'localhost';" 2>&1 | head -3 | sed 's/^/      /'
    [ ${PIPESTATUS[0]} -eq 0 ] && echo "      OK — this command can run setup"
    break
  fi
done
