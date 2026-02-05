"""
Cryptographic operation test vectors for Reticulum protocol conformance.

Test IDs:
  CRYPTO-001: SHA-256 known outputs
  CRYPTO-002: X25519 key exchange
  CRYPTO-003: Ed25519 sign/verify
  CRYPTO-004: AES-256-CBC encrypt/decrypt
  CRYPTO-005: HKDF key derivation
  CRYPTO-006: Token encrypt/decrypt
  CRYPTO-007: Identity hash computation
"""

import unittest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import RNS
from RNS.Cryptography import X25519PrivateKey, X25519PublicKey
from RNS.Cryptography import Ed25519PrivateKey, Ed25519PublicKey
from RNS.Cryptography import AES, PKCS7, hkdf, sha256
from RNS.Cryptography.Token import Token

from tests.e2e.utils.vector_loader import VectorLoader


class TestCryptoVectors(unittest.TestCase):
    """Test cryptographic operations against known test vectors."""

    @classmethod
    def setUpClass(cls):
        cls.loader = VectorLoader()

    def test_CRYPTO_001_sha256(self):
        """CRYPTO-001: SHA-256 known outputs"""
        for vector in self.loader.iter_vectors("crypto", "sha256"):
            with self.subTest(vector_id=vector["id"]):
                data = bytes.fromhex(vector["input"]["data_hex"])
                expected = bytes.fromhex(vector["expected"]["hash_hex"])

                result = sha256(data)

                self.assertEqual(result, expected,
                    f"SHA-256 mismatch for {vector['id']}: "
                    f"expected {expected.hex()}, got {result.hex()}")

    def test_CRYPTO_002_x25519_key_exchange(self):
        """CRYPTO-002: X25519 key exchange"""
        for vector in self.loader.iter_vectors("crypto", "x25519"):
            with self.subTest(vector_id=vector["id"]):
                if "private_key_a_hex" in vector["input"]:
                    # Key exchange test
                    prv_a = X25519PrivateKey.from_private_bytes(
                        bytes.fromhex(vector["input"]["private_key_a_hex"])
                    )
                    prv_b = X25519PrivateKey.from_private_bytes(
                        bytes.fromhex(vector["input"]["private_key_b_hex"])
                    )

                    pub_a = prv_a.public_key()
                    pub_b = prv_b.public_key()

                    # Verify public key derivation
                    self.assertEqual(
                        pub_a.public_bytes(),
                        bytes.fromhex(vector["expected"]["public_key_a_hex"]),
                        f"Public key A mismatch for {vector['id']}"
                    )
                    self.assertEqual(
                        pub_b.public_bytes(),
                        bytes.fromhex(vector["expected"]["public_key_b_hex"]),
                        f"Public key B mismatch for {vector['id']}"
                    )

                    # Verify shared secret
                    shared_a = prv_a.exchange(pub_b)
                    shared_b = prv_b.exchange(pub_a)

                    self.assertEqual(shared_a, shared_b,
                        f"Shared secrets don't match for {vector['id']}")
                    self.assertEqual(
                        shared_a,
                        bytes.fromhex(vector["expected"]["shared_secret_hex"]),
                        f"Shared secret mismatch for {vector['id']}"
                    )

                elif "private_key_hex" in vector["input"]:
                    # Public key derivation test
                    prv = X25519PrivateKey.from_private_bytes(
                        bytes.fromhex(vector["input"]["private_key_hex"])
                    )
                    pub = prv.public_key()

                    self.assertEqual(
                        pub.public_bytes(),
                        bytes.fromhex(vector["expected"]["public_key_hex"]),
                        f"Public key mismatch for {vector['id']}"
                    )

    def test_CRYPTO_003_ed25519_signing(self):
        """CRYPTO-003: Ed25519 sign/verify"""
        for vector in self.loader.iter_vectors("crypto", "ed25519"):
            with self.subTest(vector_id=vector["id"]):
                prv = Ed25519PrivateKey.from_private_bytes(
                    bytes.fromhex(vector["input"]["private_key_hex"])
                )
                pub = prv.public_key()

                # Verify public key derivation
                self.assertEqual(
                    pub.public_bytes(),
                    bytes.fromhex(vector["expected"]["public_key_hex"]),
                    f"Public key mismatch for {vector['id']}"
                )

                if "message_hex" in vector["input"] and "signature_hex" in vector["expected"]:
                    message = bytes.fromhex(vector["input"]["message_hex"])
                    expected_sig = bytes.fromhex(vector["expected"]["signature_hex"])

                    # Sign and verify signature matches
                    signature = prv.sign(message)
                    self.assertEqual(signature, expected_sig,
                        f"Signature mismatch for {vector['id']}")

                    # Verify the signature is valid
                    try:
                        pub.verify(signature, message)
                    except Exception as e:
                        self.fail(f"Signature verification failed for {vector['id']}: {e}")

    def test_CRYPTO_004_aes256_cbc(self):
        """CRYPTO-004: AES-256-CBC encrypt/decrypt"""
        for vector in self.loader.iter_vectors("crypto", "aes256_cbc"):
            with self.subTest(vector_id=vector["id"]):
                key = bytes.fromhex(vector["input"]["key_hex"])
                iv = bytes.fromhex(vector["input"]["iv_hex"])
                plaintext = bytes.fromhex(vector["input"]["plaintext_hex"])

                expected_padded = bytes.fromhex(vector["expected"]["padded_hex"])
                expected_ciphertext = bytes.fromhex(vector["expected"]["ciphertext_hex"])

                # Test padding
                padded = PKCS7.pad(plaintext)
                self.assertEqual(padded, expected_padded,
                    f"PKCS7 padding mismatch for {vector['id']}")

                # Test encryption
                ciphertext = AES.AES_256_CBC.encrypt(padded, key, iv)
                self.assertEqual(ciphertext, expected_ciphertext,
                    f"Ciphertext mismatch for {vector['id']}")

                # Test decryption
                decrypted = AES.AES_256_CBC.decrypt(ciphertext, key, iv)
                self.assertEqual(decrypted, padded,
                    f"Decryption mismatch for {vector['id']}")

                # Test unpadding
                unpadded = PKCS7.unpad(decrypted)
                self.assertEqual(unpadded, plaintext,
                    f"Unpadding mismatch for {vector['id']}")

    def test_CRYPTO_005_hkdf(self):
        """CRYPTO-005: HKDF key derivation"""
        for vector in self.loader.iter_vectors("crypto", "hkdf"):
            with self.subTest(vector_id=vector["id"]):
                ikm = bytes.fromhex(vector["input"]["ikm_hex"])
                salt = bytes.fromhex(vector["input"]["salt_hex"])
                info_hex = vector["input"].get("info_hex", "")
                info = bytes.fromhex(info_hex) if info_hex else None
                length = vector["input"]["length"]

                expected_okm = bytes.fromhex(vector["expected"]["okm_hex"])

                # Derive key
                okm = hkdf(length=length, derive_from=ikm, salt=salt, context=info)

                self.assertEqual(okm, expected_okm,
                    f"HKDF output mismatch for {vector['id']}: "
                    f"expected {expected_okm.hex()}, got {okm.hex()}")

    def test_CRYPTO_006_token(self):
        """CRYPTO-006: Token encrypt/decrypt"""
        for vector in self.loader.iter_vectors("crypto", "token"):
            with self.subTest(vector_id=vector["id"]):
                if "token_hex" in vector["input"]:
                    # Decryption test
                    key = bytes.fromhex(vector["input"]["key_hex"])
                    token_bytes = bytes.fromhex(vector["input"]["token_hex"])
                    expected_plaintext = bytes.fromhex(vector["expected"]["plaintext_hex"])

                    token = Token(key)
                    decrypted = token.decrypt(token_bytes)

                    self.assertEqual(decrypted, expected_plaintext,
                        f"Token decryption mismatch for {vector['id']}")

                    # Verify token structure
                    expected_iv = bytes.fromhex(vector["expected"]["iv_hex"])
                    expected_ct = bytes.fromhex(vector["expected"]["ciphertext_hex"])
                    expected_hmac = bytes.fromhex(vector["expected"]["hmac_hex"])

                    self.assertEqual(token_bytes[:16], expected_iv,
                        f"Token IV mismatch for {vector['id']}")
                    self.assertEqual(token_bytes[16:-32], expected_ct,
                        f"Token ciphertext mismatch for {vector['id']}")
                    self.assertEqual(token_bytes[-32:], expected_hmac,
                        f"Token HMAC mismatch for {vector['id']}")

                elif "full_key_hex" in vector["input"]:
                    # Key layout test
                    full_key = bytes.fromhex(vector["input"]["full_key_hex"])
                    expected_signing = bytes.fromhex(vector["expected"]["signing_key_hex"])
                    expected_encryption = bytes.fromhex(vector["expected"]["encryption_key_hex"])

                    self.assertEqual(full_key[:32], expected_signing,
                        f"Signing key mismatch for {vector['id']}")
                    self.assertEqual(full_key[32:], expected_encryption,
                        f"Encryption key mismatch for {vector['id']}")

    def test_CRYPTO_007_identity_hash(self):
        """CRYPTO-007: Identity hash computation"""
        for vector in self.loader.iter_vectors("identity", "keys"):
            with self.subTest(vector_id=vector["id"]):
                private_key = bytes.fromhex(vector["input"]["private_key_hex"])
                expected_hash = bytes.fromhex(vector["expected"]["identity_hash_hex"])
                expected_pub = bytes.fromhex(vector["expected"]["public_key_hex"])

                # Create identity from private key
                identity = RNS.Identity.from_bytes(private_key)

                # Verify public key
                self.assertEqual(identity.get_public_key(), expected_pub,
                    f"Public key mismatch for {vector['id']}")

                # Verify identity hash
                self.assertEqual(identity.hash, expected_hash,
                    f"Identity hash mismatch for {vector['id']}: "
                    f"expected {expected_hash.hex()}, got {identity.hash.hex()}")

                # Verify hash is truncated_hash(public_key)
                computed_hash = RNS.Identity.truncated_hash(expected_pub)
                self.assertEqual(computed_hash, expected_hash,
                    f"Truncated hash mismatch for {vector['id']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
