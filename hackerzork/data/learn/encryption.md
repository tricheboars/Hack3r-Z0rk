# ENCRYPTION — symmetric, asymmetric, hashing

Three different cryptographic primitives that solve different problems.

## Symmetric encryption

ONE key, used for both encrypt and decrypt. Fast, suitable for bulk data.

  AES-256-GCM       gold standard. Authenticated (detects tampering).
  ChaCha20-Poly1305 modern alternative, fast on hardware without AES-NI.

The hard part: getting the key to the recipient WITHOUT anyone in the
middle seeing it. Solved by asymmetric crypto.

## Asymmetric (public-key) encryption

A KEYPAIR. Anything encrypted with the public key can only be decrypted
with the matching private key. The public half is shareable; the private
half is the secret.

  RSA-2048+         classic, well-understood
  ECC (curve25519)  modern, smaller keys, faster

In practice nobody encrypts large data asymmetrically. The pattern is:

  1. Sender generates a fresh symmetric key (the "session key").
  2. Encrypts the bulk data with the symmetric key.
  3. Encrypts the session key with the recipient's public key.
  4. Sends both blobs.

This is what TLS, GPG, age, and most secure-messaging apps do under the
hood. "Hybrid" encryption.

## Hashing

A one-way function: arbitrary input → fixed-size digest. Useful for:

  - integrity checks (did this file change?)
  - password storage (store hash, never plaintext)
  - signatures (sign the hash, not the data)

  SHA-256 / SHA-512   general purpose
  Blake3              modern, very fast
  bcrypt / argon2     PASSWORD-specific. Slow on purpose, salted, tunable
                      cost. Use these for passwords, NEVER plain SHA.

MD5 and SHA-1 are BROKEN for collision resistance. Don't use them where
collisions matter (signatures, certs). Still fine for non-adversarial
checksums (downloaded an ISO, want to compare).

## Authenticated encryption

Plain encryption hides data but doesn't prove the ciphertext wasn't
tampered with. AUTHENTICATED encryption (AEAD) does both. AES-GCM and
ChaCha20-Poly1305 are AEAD; AES-CBC alone is not — pair it with HMAC or
just use GCM.

## In this game

`evidence/core.enc` is an AES-256-GCM container. `cat` shows it as a hex
dump because it's marked encrypted. Decrypting it requires the right key,
which is split across the relay nodes. The container format is real-ish;
the splitting is dramatic license.

## See also

  man gpg           learn ssh-keys    learn permissions
