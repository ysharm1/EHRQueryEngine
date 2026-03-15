"""
Security configuration for encryption and TLS.

This module provides configuration for:
- Database encryption (PostgreSQL, DuckDB)
- TLS/HTTPS configuration
- Key management integration
"""

import os
from pathlib import Path
from typing import Optional


class SecurityConfig:
    """Security configuration for the application."""
    
    # Database Encryption
    POSTGRES_ENCRYPTION_ENABLED = os.getenv("POSTGRES_ENCRYPTION_ENABLED", "false").lower() == "true"
    DUCKDB_ENCRYPTION_ENABLED = os.getenv("DUCKDB_ENCRYPTION_ENABLED", "false").lower() == "true"
    
    # TLS Configuration
    TLS_ENABLED = os.getenv("TLS_ENABLED", "false").lower() == "true"
    TLS_CERT_PATH = os.getenv("TLS_CERT_PATH", "./certs/cert.pem")
    TLS_KEY_PATH = os.getenv("TLS_KEY_PATH", "./certs/key.pem")
    
    # Key Management
    KEY_MANAGEMENT_PROVIDER = os.getenv("KEY_MANAGEMENT_PROVIDER", "local")  # local, aws_kms, azure_vault
    AWS_KMS_KEY_ID = os.getenv("AWS_KMS_KEY_ID")
    AZURE_VAULT_URL = os.getenv("AZURE_VAULT_URL")
    
    # File Storage Encryption
    FILE_ENCRYPTION_ENABLED = os.getenv("FILE_ENCRYPTION_ENABLED", "false").lower() == "true"
    FILE_ENCRYPTION_KEY = os.getenv("FILE_ENCRYPTION_KEY")
    
    @classmethod
    def get_postgres_ssl_config(cls) -> dict:
        """Get PostgreSQL SSL configuration."""
        if not cls.POSTGRES_ENCRYPTION_ENABLED:
            return {}
        
        return {
            "sslmode": "require",
            "sslrootcert": os.getenv("POSTGRES_SSL_ROOT_CERT", "./certs/postgres-ca.pem"),
            "sslcert": os.getenv("POSTGRES_SSL_CERT", "./certs/postgres-client.pem"),
            "sslkey": os.getenv("POSTGRES_SSL_KEY", "./certs/postgres-client-key.pem"),
        }
    
    @classmethod
    def get_duckdb_encryption_key(cls) -> Optional[str]:
        """Get DuckDB encryption key."""
        if not cls.DUCKDB_ENCRYPTION_ENABLED:
            return None
        
        # In production, this should come from KMS
        return os.getenv("DUCKDB_ENCRYPTION_KEY")
    
    @classmethod
    def get_tls_config(cls) -> Optional[dict]:
        """Get TLS configuration for FastAPI."""
        if not cls.TLS_ENABLED:
            return None
        
        return {
            "ssl_keyfile": cls.TLS_KEY_PATH,
            "ssl_certfile": cls.TLS_CERT_PATH,
            "ssl_version": 3,  # TLS 1.3
        }


# PostgreSQL encryption setup instructions
POSTGRES_ENCRYPTION_SETUP = """
# PostgreSQL Encryption Setup

## 1. Enable SSL/TLS in PostgreSQL

Edit postgresql.conf:
```
ssl = on
ssl_cert_file = '/path/to/server.crt'
ssl_key_file = '/path/to/server.key'
ssl_ca_file = '/path/to/ca.crt'
```

## 2. Enable data-at-rest encryption

PostgreSQL doesn't have built-in transparent data encryption.
Options:
- Use encrypted filesystem (LUKS, dm-crypt)
- Use pgcrypto extension for column-level encryption
- Use third-party solutions like Percona or EDB

## 3. Generate SSL certificates

```bash
# Generate CA key and certificate
openssl req -new -x509 -days 365 -nodes -text -out ca.crt -keyout ca.key

# Generate server key and certificate
openssl req -new -nodes -text -out server.csr -keyout server.key
openssl x509 -req -in server.csr -text -days 365 -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt

# Generate client key and certificate
openssl req -new -nodes -text -out client.csr -keyout client.key
openssl x509 -req -in client.csr -text -days 365 -CA ca.crt -CAkey ca.key -CAcreateserial -out client.crt
```

## 4. Update connection string

```python
postgresql://user:pass@host:5432/db?sslmode=require&sslrootcert=/path/to/ca.crt
```
"""

# DuckDB encryption setup instructions
DUCKDB_ENCRYPTION_SETUP = """
# DuckDB Encryption Setup

DuckDB supports encryption at rest using AES-256.

## 1. Install DuckDB with encryption support

```bash
pip install duckdb
```

## 2. Create encrypted database

```python
import duckdb

# Create encrypted database
conn = duckdb.connect('encrypted.duckdb', config={
    'encryption': 'aes256',
    'encryption_key': 'your-32-byte-key-here'
})
```

## 3. Use environment variable for key

```bash
export DUCKDB_ENCRYPTION_KEY="your-32-byte-key-here"
```

## 4. In production, use KMS

Retrieve encryption key from AWS KMS or Azure Key Vault:

```python
import boto3

kms = boto3.client('kms')
response = kms.decrypt(
    CiphertextBlob=encrypted_key,
    KeyId='your-kms-key-id'
)
encryption_key = response['Plaintext']
```
"""

# TLS setup instructions
TLS_SETUP = """
# TLS/HTTPS Setup

## 1. Generate SSL certificates

For development:
```bash
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
```

For production, use Let's Encrypt:
```bash
certbot certonly --standalone -d yourdomain.com
```

## 2. Configure FastAPI with TLS

```python
import uvicorn

uvicorn.run(
    app,
    host="0.0.0.0",
    port=443,
    ssl_keyfile="./certs/key.pem",
    ssl_certfile="./certs/cert.pem",
    ssl_version=3  # TLS 1.3
)
```

## 3. Update environment variables

```bash
TLS_ENABLED=true
TLS_CERT_PATH=./certs/cert.pem
TLS_KEY_PATH=./certs/key.pem
```

## 4. Configure secure cookies

```python
from fastapi import Response

response.set_cookie(
    key="session",
    value=token,
    httponly=True,
    secure=True,  # HTTPS only
    samesite="strict"
)
```
"""

# AWS KMS integration
AWS_KMS_SETUP = """
# AWS KMS Integration

## 1. Install boto3

```bash
pip install boto3
```

## 2. Create KMS key

```bash
aws kms create-key --description "Research Dataset Builder encryption key"
```

## 3. Use KMS for encryption

```python
import boto3
import base64

kms = boto3.client('kms')

# Encrypt data
response = kms.encrypt(
    KeyId='your-kms-key-id',
    Plaintext=b'sensitive-data'
)
encrypted_data = base64.b64encode(response['CiphertextBlob'])

# Decrypt data
response = kms.decrypt(
    CiphertextBlob=base64.b64decode(encrypted_data)
)
decrypted_data = response['Plaintext']
```

## 4. Set environment variables

```bash
KEY_MANAGEMENT_PROVIDER=aws_kms
AWS_KMS_KEY_ID=your-kms-key-id
AWS_REGION=us-east-1
```
"""

# Azure Key Vault integration
AZURE_VAULT_SETUP = """
# Azure Key Vault Integration

## 1. Install Azure SDK

```bash
pip install azure-keyvault-secrets azure-identity
```

## 2. Create Key Vault

```bash
az keyvault create --name mykeyvault --resource-group myresourcegroup --location eastus
```

## 3. Use Key Vault for secrets

```python
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://mykeyvault.vault.azure.net/", credential=credential)

# Store secret
client.set_secret("database-password", "my-secret-password")

# Retrieve secret
secret = client.get_secret("database-password")
password = secret.value
```

## 4. Set environment variables

```bash
KEY_MANAGEMENT_PROVIDER=azure_vault
AZURE_VAULT_URL=https://mykeyvault.vault.azure.net/
```
"""


def print_security_setup_instructions():
    """Print security setup instructions."""
    print("=" * 80)
    print("SECURITY SETUP INSTRUCTIONS")
    print("=" * 80)
    print("\n" + POSTGRES_ENCRYPTION_SETUP)
    print("\n" + DUCKDB_ENCRYPTION_SETUP)
    print("\n" + TLS_SETUP)
    print("\n" + AWS_KMS_SETUP)
    print("\n" + AZURE_VAULT_SETUP)
    print("=" * 80)


if __name__ == "__main__":
    print_security_setup_instructions()
