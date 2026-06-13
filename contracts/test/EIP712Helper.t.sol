// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {EIP712Helper} from "../src/libraries/EIP712Helper.sol";

/// @title EIP712HelperWrapper
/// @notice Wrapper contract to test EIP712Helper library reverts
/// @dev Needed because Foundry has issues with expectRevert on library pure/view functions
contract EIP712HelperWrapper {
    function recoverSigner(bytes32 _digest, uint8 _v, bytes32 _r, bytes32 _s) external pure returns (address) {
        return EIP712Helper.recoverSigner(_digest, _v, _r, _s);
    }

    function recoverSigner(bytes32 _digest, bytes memory _signature) external pure returns (address) {
        return EIP712Helper.recoverSigner(_digest, _signature);
    }

    function splitSignature(bytes memory _sig) external pure returns (uint8 v, bytes32 r, bytes32 s) {
        return EIP712Helper.splitSignature(_sig);
    }
}

/// @title EIP712HelperTest
/// @notice Comprehensive tests for the EIP712Helper library
contract EIP712HelperTest is Test {
    using EIP712Helper for bytes32;

    EIP712HelperWrapper public wrapper;

    // --- Test vectors ---
    bytes32 constant TEST_TYPEHASH = keccak256("TestStruct(address user,uint256 value)");

    string constant DOMAIN_NAME = "AgentPlatform";
    string constant DOMAIN_VERSION = "1";
    uint256 constant CHAIN_ID = 84532; // Base Sepolia
    address constant VERIFYING_CONTRACT = address(0x1234);

    bytes32 public domainSeparator;
    address public signer;
    uint256 public signerPrivateKey;

    function setUp() public {
        wrapper = new EIP712HelperWrapper();

        domainSeparator = EIP712Helper.buildDomainSeparator(
            DOMAIN_NAME,
            DOMAIN_VERSION,
            CHAIN_ID,
            VERIFYING_CONTRACT
        );

        // Generate a deterministic key pair for testing
        signerPrivateKey = 0xA1B2C3D4;
        signer = vm.addr(signerPrivateKey);
    }

    // =========================================================================
    // buildDomainSeparator
    // =========================================================================

    function test_BuildDomainSeparator() public view {
        bytes32 expected = keccak256(
            abi.encode(
                EIP712Helper.EIP712_DOMAIN_TYPEHASH,
                keccak256(bytes(DOMAIN_NAME)),
                keccak256(bytes(DOMAIN_VERSION)),
                CHAIN_ID,
                VERIFYING_CONTRACT
            )
        );

        assertEq(domainSeparator, expected, "Domain separator mismatch");
    }

    function test_BuildDomainSeparator_DifferentNames() public pure {
        bytes32 sep1 = EIP712Helper.buildDomainSeparator("Name1", "1", CHAIN_ID, VERIFYING_CONTRACT);
        bytes32 sep2 = EIP712Helper.buildDomainSeparator("Name2", "1", CHAIN_ID, VERIFYING_CONTRACT);
        assertFalse(sep1 == sep2, "Different names should produce different separators");
    }

    function test_BuildDomainSeparator_DifferentVersions() public pure {
        bytes32 sep1 = EIP712Helper.buildDomainSeparator(DOMAIN_NAME, "1", CHAIN_ID, VERIFYING_CONTRACT);
        bytes32 sep2 = EIP712Helper.buildDomainSeparator(DOMAIN_NAME, "2", CHAIN_ID, VERIFYING_CONTRACT);
        assertFalse(sep1 == sep2, "Different versions should produce different separators");
    }

    function test_BuildDomainSeparator_DifferentChainIds() public pure {
        bytes32 sep1 = EIP712Helper.buildDomainSeparator(DOMAIN_NAME, DOMAIN_VERSION, 1, VERIFYING_CONTRACT);
        bytes32 sep2 = EIP712Helper.buildDomainSeparator(DOMAIN_NAME, DOMAIN_VERSION, 2, VERIFYING_CONTRACT);
        assertFalse(sep1 == sep2, "Different chain IDs should produce different separators");
    }

    // =========================================================================
    // hashTypedData
    // =========================================================================

    function test_HashTypedData() public view {
        bytes32 structHash = keccak256(abi.encode(TEST_TYPEHASH, address(0x1), uint256(100)));
        bytes32 digest = EIP712Helper.hashTypedData(domainSeparator, structHash);

        bytes32 expected = keccak256(abi.encodePacked("\x19\x01", domainSeparator, structHash));
        assertEq(digest, expected, "Typed data hash mismatch");
    }

    function test_HashTypedData_DifferentStructHashes() public view {
        bytes32 structHash1 = keccak256(abi.encode(TEST_TYPEHASH, address(0x1), uint256(100)));
        bytes32 structHash2 = keccak256(abi.encode(TEST_TYPEHASH, address(0x2), uint256(200)));

        bytes32 digest1 = EIP712Helper.hashTypedData(domainSeparator, structHash1);
        bytes32 digest2 = EIP712Helper.hashTypedData(domainSeparator, structHash2);

        assertFalse(digest1 == digest2, "Different structs should produce different digests");
    }

    // =========================================================================
    // recoverSigner (v, r, s)
    // =========================================================================

    function test_RecoverSigner_WithVRs() public view {
        bytes32 structHash = keccak256(abi.encode(TEST_TYPEHASH, signer, uint256(42)));
        bytes32 digest = EIP712Helper.hashTypedData(domainSeparator, structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerPrivateKey, digest);
        address recovered = EIP712Helper.recoverSigner(digest, v, r, s);

        assertEq(recovered, signer, "Recovered signer should match original");
    }

    function test_RevertWhen_RecoverSigner_InvalidSignature() public {
        bytes32 digest = keccak256("some random digest");
        // Use v=0 which is invalid and will cause ecrecover to return address(0)
        vm.expectRevert(EIP712Helper.InvalidSignature.selector);
        wrapper.recoverSigner(digest, 0, bytes32(uint256(1)), bytes32(uint256(1)));
    }

    // =========================================================================
    // recoverSigner (bytes)
    // =========================================================================

    function test_RecoverSigner_WithBytes() public view {
        bytes32 structHash = keccak256(abi.encode(TEST_TYPEHASH, signer, uint256(42)));
        bytes32 digest = EIP712Helper.hashTypedData(domainSeparator, structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerPrivateKey, digest);
        bytes memory signature = abi.encodePacked(r, s, v);

        address recovered = EIP712Helper.recoverSigner(digest, signature);
        assertEq(recovered, signer, "Recovered signer should match original");
    }

    function test_RevertWhen_RecoverSigner_InvalidSignatureLength() public {
        bytes32 digest = keccak256("test");
        bytes memory invalidSig = abi.encodePacked(bytes32(uint256(1)), bytes32(uint256(2))); // 64 bytes

        vm.expectRevert(EIP712Helper.InvalidSignatureLength.selector);
        wrapper.recoverSigner(digest, invalidSig);
    }

    function test_RevertWhen_RecoverSigner_EmptySignature() public {
        bytes32 digest = keccak256("test");
        bytes memory emptySig = "";

        vm.expectRevert(EIP712Helper.EmptySignature.selector);
        wrapper.recoverSigner(digest, emptySig);
    }

    // =========================================================================
    // verifySignature
    // =========================================================================

    function test_VerifySignature_Valid() public view {
        bytes32 structHash = keccak256(abi.encode(TEST_TYPEHASH, signer, uint256(42)));
        bytes32 digest = EIP712Helper.hashTypedData(domainSeparator, structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerPrivateKey, digest);
        bytes memory signature = abi.encodePacked(r, s, v);

        bool valid = EIP712Helper.verifySignature(digest, signature, signer);
        assertTrue(valid, "Signature should be valid");
    }

    function test_VerifySignature_InvalidSigner() public view {
        bytes32 structHash = keccak256(abi.encode(TEST_TYPEHASH, signer, uint256(42)));
        bytes32 digest = EIP712Helper.hashTypedData(domainSeparator, structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerPrivateKey, digest);
        bytes memory signature = abi.encodePacked(r, s, v);

        address wrongSigner = address(0xDEAD);
        bool valid = EIP712Helper.verifySignature(digest, signature, wrongSigner);
        assertFalse(valid, "Signature should be invalid for wrong signer");
    }

    function test_VerifySignature_TamperedDigest() public view {
        bytes32 structHash = keccak256(abi.encode(TEST_TYPEHASH, signer, uint256(42)));
        bytes32 digest = EIP712Helper.hashTypedData(domainSeparator, structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerPrivateKey, digest);
        bytes memory signature = abi.encodePacked(r, s, v);

        bytes32 tamperedDigest = keccak256("tampered");
        bool valid = EIP712Helper.verifySignature(tamperedDigest, signature, signer);
        assertFalse(valid, "Signature should be invalid for tampered digest");
    }

    // =========================================================================
    // splitSignature
    // =========================================================================

    function test_SplitSignature() public pure {
        bytes32 r = bytes32(uint256(0xABCD));
        bytes32 s = bytes32(uint256(0xEF01));
        uint8 v = 27;

        bytes memory sig = abi.encodePacked(r, s, v);
        (uint8 recoveredV, bytes32 recoveredR, bytes32 recoveredS) = EIP712Helper.splitSignature(sig);

        assertEq(recoveredV, v, "v mismatch");
        assertEq(recoveredR, r, "r mismatch");
        assertEq(recoveredS, s, "s mismatch");
    }

    function test_RevertWhen_SplitSignature_InvalidLength() public {
        bytes memory invalidSig = new bytes(64);
        vm.expectRevert(EIP712Helper.InvalidSignatureLength.selector);
        wrapper.splitSignature(invalidSig);
    }

    // =========================================================================
    // hashStruct
    // =========================================================================

    function test_HashStruct() public pure {
        bytes memory encodedData = abi.encode(address(0x1), uint256(100));
        bytes32 expected = keccak256(abi.encodePacked(TEST_TYPEHASH, encodedData));

        bytes32 result = EIP712Helper.hashStruct(TEST_TYPEHASH, encodedData);
        assertEq(result, expected, "Struct hash mismatch");
    }

    function test_HashStruct_DifferentData() public pure {
        bytes memory data1 = abi.encode(address(0x1), uint256(100));
        bytes memory data2 = abi.encode(address(0x2), uint256(200));

        bytes32 hash1 = EIP712Helper.hashStruct(TEST_TYPEHASH, data1);
        bytes32 hash2 = EIP712Helper.hashStruct(TEST_TYPEHASH, data2);

        assertFalse(hash1 == hash2, "Different data should produce different hashes");
    }

    // =========================================================================
    // Full EIP-712 flow integration test
    // =========================================================================

    function test_FullEIP712Flow() public view {
        // Simulate a complete EIP-712 signing and verification flow
        address user = address(0xCAFE);
        uint256 value = 12345;

        // 1. Build struct hash
        bytes32 structHash = keccak256(abi.encode(TEST_TYPEHASH, user, value));

        // 2. Build typed data digest
        bytes32 digest = EIP712Helper.hashTypedData(domainSeparator, structHash);

        // 3. Sign (simulated)
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(signerPrivateKey, digest);
        bytes memory signature = abi.encodePacked(r, s, v);

        // 4. Verify
        bool valid = EIP712Helper.verifySignature(digest, signature, signer);
        assertTrue(valid, "Full EIP-712 flow should verify successfully");

        // 5. Verify with individual components
        address recovered = EIP712Helper.recoverSigner(digest, v, r, s);
        assertEq(recovered, signer, "Full flow: recovered signer mismatch");
    }

    // =========================================================================
    // Fuzz testing
    // =========================================================================

    function testFuzz_RecoverSigner_Consistency(uint256 _privateKey, uint256 _value) public {
        // Ensure private key is valid (non-zero and less than secp256k1 order)
        vm.assume(_privateKey > 0 && _privateKey < 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141);

        address expectedSigner = vm.addr(_privateKey);
        bytes32 structHash = keccak256(abi.encode(TEST_TYPEHASH, expectedSigner, _value));
        bytes32 digest = EIP712Helper.hashTypedData(domainSeparator, structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(_privateKey, digest);
        address recovered = EIP712Helper.recoverSigner(digest, v, r, s);

        assertEq(recovered, expectedSigner, "Fuzz: recovered signer should match");
    }
}
