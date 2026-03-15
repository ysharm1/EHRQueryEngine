#!/bin/bash

# Security Setup Script for Research Dataset Builder
# This script helps set up encryption and TLS for production deployment

set -e

echo "=========================================="
echo "Research Dataset Builder - Security Setup"
echo "=========================================="
echo ""

# Create certs directory
mkdir -p certs

# Function to generate self-signed certificates (for development)
generate_dev_certs() {
    echo "Generating development SSL certificates..."
    
    # Generate CA
    openssl req -new -x509 -days 365 -nodes -text \
        -out certs/ca.crt \
        -keyout certs/ca.key \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=CA"
    
    # Generate server certificate
    openssl req -new -nodes -text \
        -out certs/server.csr \
        -keyout certs/server.key \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
    
    openssl x509 -req -in certs/server.csr -text -days 365 \
        -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial \
        -out certs/server.crt
    
    # Generate client certificate
    openssl req -new -nodes -text \
        -out certs/client.csr \
        -keyout certs/client.key \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=client"
    
    openssl x509 -req -in certs/client.csr -text -days 365 \
        -CA certs/ca.crt -CAkey certs/ca.key -CAcreateserial \
        -out certs/client.crt
    
    # Generate API TLS certificate
    openssl req -x509 -newkey rsa:4096 -nodes \
        -out certs/cert.pem \
        -keyout certs/key.pem \
        -days 365 \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
    
    echo "✓ Development certificates generated in ./certs/"
}

# Function to generate encryption keys
generate_encryption_keys() {
    echo "Generating encryption keys..."
    
    # Generate DuckDB encryption key (32 bytes for AES-256)
    DUCKDB_KEY=$(openssl rand -base64 32)
    
    # Generate file encryption key
    FILE_KEY=$(openssl rand -base64 32)
    
    # Generate JWT secret
    JWT_SECRET=$(openssl rand -base64 64)
    
    echo ""
    echo "Generated encryption keys (add these to your .env file):"
    echo "DUCKDB_ENCRYPTION_KEY=$DUCKDB_KEY"
    echo "FILE_ENCRYPTION_KEY=$FILE_KEY"
    echo "JWT_SECRET_KEY=$JWT_SECRET"
    echo ""
    echo "⚠️  IMPORTANT: Store these keys securely!"
    echo "⚠️  In production, use AWS KMS or Azure Key Vault"
}

# Function to update .env file
update_env_file() {
    echo "Updating .env file with security settings..."
    
    if [ ! -f .env ]; then
        cp .env.example .env
    fi
    
    # Add security settings
    cat >> .env << EOF

# Security Configuration (added by setup_security.sh)
POSTGRES_ENCRYPTION_ENABLED=true
DUCKDB_ENCRYPTION_ENABLED=true
TLS_ENABLED=true
TLS_CERT_PATH=./certs/cert.pem
TLS_KEY_PATH=./certs/key.pem
FILE_ENCRYPTION_ENABLED=true

# PostgreSQL SSL
POSTGRES_SSL_ROOT_CERT=./certs/ca.crt
POSTGRES_SSL_CERT=./certs/client.crt
POSTGRES_SSL_KEY=./certs/client.key

# Key Management (change to aws_kms or azure_vault in production)
KEY_MANAGEMENT_PROVIDER=local
EOF
    
    echo "✓ .env file updated"
}

# Main menu
echo "Select setup option:"
echo "1) Generate development certificates"
echo "2) Generate encryption keys"
echo "3) Update .env file with security settings"
echo "4) All of the above"
echo "5) Show production setup instructions"
echo ""
read -p "Enter choice [1-5]: " choice

case $choice in
    1)
        generate_dev_certs
        ;;
    2)
        generate_encryption_keys
        ;;
    3)
        update_env_file
        ;;
    4)
        generate_dev_certs
        generate_encryption_keys
        update_env_file
        echo ""
        echo "=========================================="
        echo "✓ Security setup complete!"
        echo "=========================================="
        echo ""
        echo "Next steps:"
        echo "1. Review and update the .env file with generated keys"
        echo "2. For production, use Let's Encrypt for TLS certificates"
        echo "3. For production, use AWS KMS or Azure Key Vault for key management"
        echo "4. Configure PostgreSQL to use SSL (see app/security.py for instructions)"
        echo ""
        ;;
    5)
        python -m app.security
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "For detailed production setup instructions, run:"
echo "python -m app.security"
