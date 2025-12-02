#!/bin/bash
#
# Generate self-signed SSL certificate for MS Macro PWA
# This enables HTTPS which is required for iOS push notifications
#
# Usage:
#   ./generate_ssl_cert.sh [hostname]
#
# Example:
#   ./generate_ssl_cert.sh raspberrypi.local
#
# The certificate will be valid for 365 days and stored in:
#   ~/.local/share/msmacro/ssl/
#
# After generating, set environment variables:
#   export MSMACRO_SSL_CERT=~/.local/share/msmacro/ssl/server.crt
#   export MSMACRO_SSL_KEY=~/.local/share/msmacro/ssl/server.key

set -e

HOSTNAME="${1:-raspberrypi.local}"
SSL_DIR="${HOME}/.local/share/msmacro/ssl"
DAYS_VALID=365

echo "=== MS Macro SSL Certificate Generator ==="
echo ""
echo "Hostname: ${HOSTNAME}"
echo "Output dir: ${SSL_DIR}"
echo "Valid for: ${DAYS_VALID} days"
echo ""

# Create SSL directory
mkdir -p "${SSL_DIR}"
chmod 700 "${SSL_DIR}"

# Generate private key
echo "Generating private key..."
openssl genrsa -out "${SSL_DIR}/server.key" 2048
chmod 600 "${SSL_DIR}/server.key"

# Generate certificate signing request config
cat > "${SSL_DIR}/openssl.cnf" << EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
C = US
ST = California
L = San Francisco
O = MSMacro
OU = Development
CN = ${HOSTNAME}

[v3_req]
subjectAltName = @alt_names
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth

[alt_names]
DNS.1 = ${HOSTNAME}
DNS.2 = localhost
IP.1 = 127.0.0.1
EOF

# Generate self-signed certificate
echo "Generating self-signed certificate..."
openssl req -new -x509 \
    -key "${SSL_DIR}/server.key" \
    -out "${SSL_DIR}/server.crt" \
    -days ${DAYS_VALID} \
    -config "${SSL_DIR}/openssl.cnf"

# Cleanup config
rm "${SSL_DIR}/openssl.cnf"

echo ""
echo "=== Certificate Generated Successfully ==="
echo ""
echo "Certificate: ${SSL_DIR}/server.crt"
echo "Private Key: ${SSL_DIR}/server.key"
echo ""
echo "To enable HTTPS, add to your environment:"
echo ""
echo "  export MSMACRO_SSL_CERT=${SSL_DIR}/server.crt"
echo "  export MSMACRO_SSL_KEY=${SSL_DIR}/server.key"
echo ""
echo "Or add to ~/.bashrc or /etc/environment"
echo ""
echo "=== iOS Setup Instructions ==="
echo ""
echo "1. Open Safari on iPhone and go to:"
echo "   https://${HOSTNAME}:8787"
echo ""
echo "2. Accept the self-signed certificate warning:"
echo "   - Tap 'Show Details' → 'visit this website' → 'Visit Website'"
echo ""
echo "3. Install as PWA:"
echo "   - Tap Share button → 'Add to Home Screen'"
echo ""
echo "4. Open app from home screen and enable notifications"
echo ""
