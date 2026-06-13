// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title EIP712Helper
/// @notice Helper library for EIP-712 typed structured data hashing and verification
/// @dev Provides domain separator building, typed data hashing, and signature recovery
library EIP712Helper {
    /// @notice EIP-712 domain typehash constant
    bytes32 public constant EIP712_DOMAIN_TYPEHASH =
        keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");

    // =========================================================================
    // Errors
    // =========================================================================

    /// @notice Thrown when the signature length is invalid
    error InvalidSignatureLength();

    /// @notice Thrown when the recovered signer is address(0)
    error InvalidSignature();

    /// @notice Thrown when the signature is empty
    error EmptySignature();

    // =========================================================================
    // Functions
    // =========================================================================

    /// @notice Builds an EIP-712 domain separator
    /// @param _name Domain name (e.g., "AgentPlatform")
    /// @param _version Domain version (e.g., "1")
    /// @param _chainId Blockchain chain ID
    /// @param _verifyingContract Address of the verifying contract
    /// @return domainSeparator The computed domain separator
    function buildDomainSeparator(
        string memory _name,
        string memory _version,
        uint256 _chainId,
        address _verifyingContract
    ) internal pure returns (bytes32 domainSeparator) {
        domainSeparator = keccak256(
            abi.encode(
                EIP712_DOMAIN_TYPEHASH,
                keccak256(bytes(_name)),
                keccak256(bytes(_version)),
                _chainId,
                _verifyingContract
            )
        );
    }

    /// @notice Hashes typed data according to EIP-712: `keccak256("\x19\x01" ‖ domainSeparator ‖ structHash)`
    /// @param _domainSeparator The domain separator
    /// @param _structHash The hash of the typed struct
    /// @return digest The final EIP-712 digest
    function hashTypedData(
        bytes32 _domainSeparator,
        bytes32 _structHash
    ) internal pure returns (bytes32 digest) {
        digest = keccak256(abi.encodePacked("\x19\x01", _domainSeparator, _structHash));
    }

    /// @notice Recovers the signer address from an EIP-712 digest and signature
    /// @param _digest The EIP-712 digest (already hashed with domain separator)
    /// @param _v ECDSA recovery id (27 or 28)
    /// @param _r ECDSA signature r component
    /// @param _s ECDSA signature s component
    /// @return signer The address that signed the digest
    function recoverSigner(
        bytes32 _digest,
        uint8 _v,
        bytes32 _r,
        bytes32 _s
    ) internal pure returns (address signer) {
        signer = ecrecover(_digest, _v, _r, _s);
        if (signer == address(0)) revert InvalidSignature();
    }

    /// @notice Recovers the signer address from an EIP-712 digest and packed signature bytes
    /// @param _digest The EIP-712 digest
    /// @param _signature Packed ECDSA signature (65 bytes: r, s, v)
    /// @return signer The address that signed the digest
    function recoverSigner(
        bytes32 _digest,
        bytes memory _signature
    ) internal pure returns (address signer) {
        if (_signature.length == 0) revert EmptySignature();
        if (_signature.length != 65) revert InvalidSignatureLength();
        (uint8 v, bytes32 r, bytes32 s) = splitSignature(_signature);
        signer = recoverSigner(_digest, v, r, s);
    }

    /// @notice Verifies that a signature was signed by the expected signer
    /// @param _digest The EIP-712 digest
    /// @param _signature Packed ECDSA signature (65 bytes)
    /// @param _expectedSigner The expected signer address
    /// @return valid True if the signature is valid
    function verifySignature(
        bytes32 _digest,
        bytes memory _signature,
        address _expectedSigner
    ) internal pure returns (bool valid) {
        return recoverSigner(_digest, _signature) == _expectedSigner;
    }

    /// @notice Splits a packed signature into v, r, s components
    /// @param _sig Packed signature (65 bytes)
    /// @return v Recovery id
    /// @return r R component
    /// @return s S component
    function splitSignature(bytes memory _sig) internal pure returns (uint8 v, bytes32 r, bytes32 s) {
        if (_sig.length != 65) revert InvalidSignatureLength();
        assembly {
            r := mload(add(_sig, 32))
            s := mload(add(_sig, 64))
            v := byte(0, mload(add(_sig, 96)))
        }
    }

    /// @notice Builds a complete EIP-712 struct hash for a given type and encoded data
    /// @param _typehash The typehash of the struct (e.g., keccak256("Delegation(address agent,...)"))
    /// @param _encodedData ABI-encoded struct data
    /// @return structHash The computed struct hash
    function hashStruct(bytes32 _typehash, bytes memory _encodedData) internal pure returns (bytes32 structHash) {
        structHash = keccak256(abi.encodePacked(_typehash, _encodedData));
    }
}
