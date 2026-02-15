"""NIP-44 encryption/decryption using nostr-sdk."""

import json
import logging

from nostr_sdk import Keys, Nip44Version, PublicKey, nip44_decrypt, nip44_encrypt

logger = logging.getLogger(__name__)


class Nip44Crypto:
    """Handles NIP-44 encryption and decryption for the bridge."""

    def __init__(self, private_key_hex_or_nsec: str, publisher_pubkey_hex_or_npub: str):
        self._keys = Keys.parse(private_key_hex_or_nsec)
        self._publisher_pubkey = PublicKey.parse(publisher_pubkey_hex_or_npub)

        logger.info(
            "NIP-44 crypto initialized. Bridge pubkey: %s",
            self._keys.public_key().to_bech32(),
        )

    @property
    def bridge_public_key(self) -> PublicKey:
        return self._keys.public_key()

    @property
    def publisher_public_key(self) -> PublicKey:
        return self._publisher_pubkey

    def decrypt(self, encrypted_content: str) -> str:
        """Decrypt NIP-44 encrypted content from the publisher.

        Handles both single payloads and MyMealPlanner's chunked format
        where large records are split into {"_chunks": ["...", "..."]}.

        Args:
            encrypted_content: The NIP-44 encrypted payload string.

        Returns:
            Decrypted plaintext string.

        Raises:
            Exception: If decryption fails (wrong key, tampered data, etc.)
        """
        # Handle chunked format from MyMealPlanner
        if encrypted_content.startswith('{"_chunks":'):
            try:
                wrapper = json.loads(encrypted_content)
                chunks = wrapper["_chunks"]
                parts = [
                    nip44_decrypt(self._keys.secret_key(), self._publisher_pubkey, chunk)
                    for chunk in chunks
                ]
                return "".join(parts)
            except (json.JSONDecodeError, KeyError):
                pass  # Fall through to single decrypt

        return nip44_decrypt(self._keys.secret_key(), self._publisher_pubkey, encrypted_content)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext message for the publisher (useful for testing).

        Args:
            plaintext: The message to encrypt.

        Returns:
            NIP-44 encrypted string.
        """
        return nip44_encrypt(self._keys.secret_key(), self._publisher_pubkey, plaintext, Nip44Version.V2)
