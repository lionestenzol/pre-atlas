#!/bin/bash
set -e
export PATH=/usr/local/go/bin:/usr/bin:/bin:/usr/sbin:/sbin
cd /root/fest-install
sed -i 's/go 1.25.6/go 1.24.2/' go.mod
go mod tidy 2>&1 || true
go build -o /usr/local/bin/fest ./cmd/fest
chmod +x /usr/local/bin/fest
echo "fest installed:"
/usr/local/bin/fest --version 2>&1 || /usr/local/bin/fest version 2>&1 || echo "binary built at /usr/local/bin/fest"
