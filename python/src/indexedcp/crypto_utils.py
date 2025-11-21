"""
Cryptographic utilities for asymmetric envelope encryption

Design:
- RSA-OAEP (SHA-256) for key wrapping
- AES-256-GCM for data encryption
- Per-stream ephemeral session keys
- IV + AAD for authenticity and uniqueness
"""

import os
import json
import hashlib
import base64
from typing import Dict, Any, Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


class CryptoUtils:
    """Cryptographic utilities for asymmetric envelope encryption."""
    
    def __init__(self):
        self.AES_KEY_LENGTH = 32  # 256 bits
        self.IV_LENGTH = 12  # 96 bits for GCM
        self.AUTH_TAG_LENGTH = 16  # 128 bits
    
    def generate_server_key_pair(self, modulus_length: int = 4096) -> Dict[str, str]:
        """
        Generate RSA key pair for server.
        
        Args:
            modulus_length: Key size in bits (default: 4096)
        
        Returns:
            Dict containing publicKey, privateKey (PEM format), and kid (key ID)
        """
        # Generate RSA key pair
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=modulus_length,
            backend=default_backend()
        )
        
        # Serialize public key to PEM format
        public_key_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        # Serialize private key to PEM format
        private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        # Generate key ID from public key hash
        kid = hashlib.sha256(public_key_pem.encode()).hexdigest()[:16]
        
        return {
            'publicKey': public_key_pem,
            'privateKey': private_key_pem,
            'kid': kid
        }
    
    def generate_session_key(self) -> bytes:
        """
        Generate ephemeral AES session key.
        
        Returns:
            256-bit AES key as bytes
        """
        return os.urandom(self.AES_KEY_LENGTH)
    
    def wrap_session_key(self, session_key: bytes, public_key_pem: str) -> bytes:
        """
        Wrap (encrypt) an AES session key with RSA public key.
        
        Args:
            session_key: AES key to wrap
            public_key_pem: RSA public key in PEM format
        
        Returns:
            Wrapped (encrypted) session key as bytes
        """
        # Load public key
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode(),
            backend=default_backend()
        )
        
        # Encrypt session key with RSA-OAEP
        wrapped_key = public_key.encrypt(
            session_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return wrapped_key
    
    def unwrap_session_key(self, wrapped_key: bytes, private_key_pem: str) -> bytes:
        """
        Unwrap (decrypt) an AES session key with RSA private key.
        
        Args:
            wrapped_key: Encrypted session key
            private_key_pem: RSA private key in PEM format
        
        Returns:
            Unwrapped AES session key as bytes
        """
        # Load private key
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None,
            backend=default_backend()
        )
        
        # Decrypt session key with RSA-OAEP
        session_key = private_key.decrypt(
            wrapped_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        return session_key
    
    def encrypt_packet(
        self, 
        data: bytes, 
        session_key: bytes, 
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Encrypt data with AES-GCM.
        
        Args:
            data: Plaintext to encrypt
            session_key: AES session key
            metadata: Additional authenticated data (sessionId, seq, etc.)
        
        Returns:
            Dict containing ciphertext, iv, authTag, and aad
        """
        # Generate unique IV for this packet
        iv = os.urandom(self.IV_LENGTH)
        
        # Prepare AAD (Additional Authenticated Data)
        aad_dict = {
            'sessionId': metadata.get('sessionId'),
            'seq': metadata.get('seq'),
            'codec': metadata.get('codec', 'raw'),
            'timestamp': metadata.get('timestamp', int(time.time() * 1000))
        }
        aad = json.dumps(aad_dict, separators=(',', ':')).encode()
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(session_key),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        
        # Set AAD
        encryptor.authenticate_additional_data(aad)
        
        # Encrypt
        ciphertext = encryptor.update(data) + encryptor.finalize()
        
        # Get authentication tag
        auth_tag = encryptor.tag
        
        return {
            'ciphertext': ciphertext,
            'iv': iv,
            'authTag': auth_tag,
            'aad': aad
        }
    
    def decrypt_packet(
        self,
        ciphertext: bytes,
        session_key: bytes,
        iv: bytes,
        auth_tag: bytes,
        aad: bytes
    ) -> bytes:
        """
        Decrypt data with AES-GCM.
        
        Args:
            ciphertext: Encrypted data
            session_key: AES session key
            iv: Initialization vector
            auth_tag: Authentication tag
            aad: Additional authenticated data
        
        Returns:
            Decrypted plaintext as bytes
        """
        # Create cipher
        cipher = Cipher(
            algorithms.AES(session_key),
            modes.GCM(iv, auth_tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        
        # Set AAD
        decryptor.authenticate_additional_data(aad)
        
        # Decrypt
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        
        return plaintext
    
    def serialize_packet(self, packet: Dict[str, bytes]) -> Dict[str, str]:
        """
        Serialize encrypted packet for storage.
        
        Args:
            packet: Encrypted packet data with bytes values
        
        Returns:
            Serialized packet with base64-encoded strings
        """
        return {
            'ciphertext': base64.b64encode(packet['ciphertext']).decode('utf-8'),
            'iv': base64.b64encode(packet['iv']).decode('utf-8'),
            'authTag': base64.b64encode(packet['authTag']).decode('utf-8'),
            'aad': base64.b64encode(packet['aad']).decode('utf-8')
        }
    
    def deserialize_packet(self, serialized: Dict[str, str]) -> Dict[str, bytes]:
        """
        Deserialize encrypted packet from storage.
        
        Args:
            serialized: Serialized packet with base64-encoded strings
        
        Returns:
            Packet with bytes values
        """
        return {
            'ciphertext': base64.b64decode(serialized['ciphertext']),
            'iv': base64.b64decode(serialized['iv']),
            'authTag': base64.b64decode(serialized['authTag']),
            'aad': base64.b64decode(serialized['aad'])
        }
    
    def parse_aad(self, aad: bytes) -> Dict[str, Any]:
        """
        Parse AAD to extract metadata.
        
        Args:
            aad: Additional authenticated data
        
        Returns:
            Metadata dictionary
        """
        return json.loads(aad.decode())
    
    def is_valid_key_id(self, kid: str) -> bool:
        """
        Validate key ID format.
        
        Args:
            kid: Key ID to validate
        
        Returns:
            True if valid, False otherwise
        """
        import re
        return bool(re.match(r'^[a-f0-9]{16}$', kid))
    
    def generate_session_id(self) -> str:
        """
        Generate session ID.
        
        Returns:
            Unique session identifier
        """
        return os.urandom(16).hex()


# Import time module for timestamp
import time
