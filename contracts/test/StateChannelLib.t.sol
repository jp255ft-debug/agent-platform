// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {StateChannelLib} from "../src/libraries/StateChannelLib.sol";
import {EIP712Helper} from "../src/libraries/EIP712Helper.sol";

/// @title StateChannelLibWrapper
/// @notice Wrapper contract to test StateChannelLib reverts
/// @dev Needed because Foundry has issues with expectRevert on library pure/view functions
contract StateChannelLibWrapper {
    function validateStateUpdate(
        StateChannelLib.Channel memory _channel,
        StateChannelLib.StateUpdate memory _update
    ) external pure returns (bool) {
        return StateChannelLib.validateStateUpdate(_channel, _update);
    }

    function verifyStateUpdateSignatures(
        bytes32 _domainSeparator,
        StateChannelLib.Channel memory _channel,
        StateChannelLib.StateUpdate memory _update
    ) external view returns (bool) {
        return StateChannelLib.verifyStateUpdateSignatures(_domainSeparator, _channel, _update);
    }
}

/// @title StateChannelLibTest
/// @notice Comprehensive tests for StateChannelLib
contract StateChannelLibTest is Test {
    using StateChannelLib for StateChannelLib.Channel;

    StateChannelLibWrapper public wrapper;
    StateChannelLib.Channel public channel;
    bytes32 public domainSeparator;

    address public participantA;
    address public participantB;
    uint256 public privateKeyA = 0xA1B2C3D4;
    uint256 public privateKeyB = 0xE5F6A7B8;

    uint256 public constant INITIAL_BALANCE_A = 100 ether;
    uint256 public constant INITIAL_BALANCE_B = 50 ether;
    uint256 public constant DEADLINE = 1_000_000;

    function setUp() public {
        wrapper = new StateChannelLibWrapper();

        participantA = vm.addr(privateKeyA);
        participantB = vm.addr(privateKeyB);

        domainSeparator = EIP712Helper.buildDomainSeparator(
            "AgentPlatform",
            "1",
            block.chainid,
            address(this)
        );

        channel = StateChannelLib.createChannel(
            participantA,
            participantB,
            INITIAL_BALANCE_A,
            INITIAL_BALANCE_B,
            DEADLINE
        );
    }

    // =========================================================================
    // createChannel
    // =========================================================================

    function test_CreateChannel() public view {
        assertEq(channel.participantA, participantA);
        assertEq(channel.participantB, participantB);
        assertEq(channel.balanceA, INITIAL_BALANCE_A);
        assertEq(channel.balanceB, INITIAL_BALANCE_B);
        assertEq(channel.nonce, 0);
        assertEq(channel.deadline, DEADLINE);
        assertFalse(channel.closed);
    }

    // =========================================================================
    // computeChannelId
    // =========================================================================

    function test_ComputeChannelId() public pure {
        bytes32 id1 = StateChannelLib.computeChannelId(
            address(0x1), address(0x2), 123
        );
        bytes32 id2 = StateChannelLib.computeChannelId(
            address(0x1), address(0x2), 456
        );
        assertFalse(id1 == id2, "Different salts should produce different IDs");
    }

    function test_ComputeChannelId_Deterministic() public pure {
        bytes32 id1 = StateChannelLib.computeChannelId(
            address(0x1), address(0x2), 123
        );
        bytes32 id2 = StateChannelLib.computeChannelId(
            address(0x1), address(0x2), 123
        );
        assertEq(id1, id2, "Same inputs should produce same ID");
    }

    // =========================================================================
    // validateStateUpdate
    // =========================================================================

    function _createValidUpdate() internal view returns (StateChannelLib.StateUpdate memory) {
        return StateChannelLib.StateUpdate({
            balanceA: 80 ether,
            balanceB: 70 ether,
            nonce: 1,
            signatureA: "",
            signatureB: ""
        });
    }

    function test_ValidateStateUpdate() public {
        StateChannelLib.StateUpdate memory update = _createValidUpdate();
        bool valid = StateChannelLib.validateStateUpdate(channel, update);
        assertTrue(valid);
    }

    function test_RevertWhen_UpdateNonceNotGreater() public {
        StateChannelLib.StateUpdate memory update = _createValidUpdate();
        update.nonce = 0; // Same as current nonce

        vm.expectRevert(StateChannelLib.InvalidNonce.selector);
        wrapper.validateStateUpdate(channel, update);
    }

    function test_RevertWhen_UpdateBalanceMismatch() public {
        StateChannelLib.StateUpdate memory update = _createValidUpdate();
        update.balanceA = 200 ether; // Total would be 270, not 150

        vm.expectRevert(StateChannelLib.BalanceMismatch.selector);
        wrapper.validateStateUpdate(channel, update);
    }

    function test_RevertWhen_ChannelClosed() public {
        channel.closed = true;

        StateChannelLib.StateUpdate memory update = _createValidUpdate();
        vm.expectRevert(StateChannelLib.ChannelClosedError.selector);
        wrapper.validateStateUpdate(channel, update);
    }

    // =========================================================================
    // verifyStateUpdateSignatures
    // =========================================================================

    function _signStateUpdate(
        uint256 _privateKey,
        StateChannelLib.StateUpdate memory _update
    ) internal view returns (bytes memory) {
        bytes32 structHash = keccak256(
            abi.encode(
                StateChannelLib.CHANNEL_STATE_TYPEHASH,
                participantA,
                participantB,
                _update.balanceA,
                _update.balanceB,
                _update.nonce,
                channel.deadline
            )
        );
        bytes32 digest = EIP712Helper.hashTypedData(domainSeparator, structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(_privateKey, digest);
        return abi.encodePacked(r, s, v);
    }

    function test_VerifyStateUpdateSignatures() public {
        StateChannelLib.StateUpdate memory update = _createValidUpdate();
        update.signatureA = _signStateUpdate(privateKeyA, update);
        update.signatureB = _signStateUpdate(privateKeyB, update);

        bool valid = StateChannelLib.verifyStateUpdateSignatures(
            domainSeparator, channel, update
        );
        assertTrue(valid);
    }

    function test_RevertWhen_SignatureAInvalid() public {
        StateChannelLib.StateUpdate memory update = _createValidUpdate();
        update.signatureA = _signStateUpdate(privateKeyB, update); // Wrong key (B instead of A)
        update.signatureB = _signStateUpdate(privateKeyB, update);

        vm.expectRevert(StateChannelLib.InvalidSignature.selector);
        wrapper.verifyStateUpdateSignatures(domainSeparator, channel, update);
    }

    function test_RevertWhen_SignatureBInvalid() public {
        StateChannelLib.StateUpdate memory update = _createValidUpdate();
        update.signatureA = _signStateUpdate(privateKeyA, update);
        update.signatureB = _signStateUpdate(privateKeyA, update); // Wrong key (A instead of B)

        vm.expectRevert(StateChannelLib.InvalidSignature.selector);
        wrapper.verifyStateUpdateSignatures(domainSeparator, channel, update);
    }

    // =========================================================================
    // applyStateUpdate
    // =========================================================================

    function test_ApplyStateUpdate() public {
        StateChannelLib.StateUpdate memory update = _createValidUpdate();

        StateChannelLib.applyStateUpdate(channel, update);

        assertEq(channel.balanceA, 80 ether);
        assertEq(channel.balanceB, 70 ether);
        assertEq(channel.nonce, 1);
    }

    // =========================================================================
    // closeChannel
    // =========================================================================

    function test_CloseChannel() public {
        (uint256 finalA, uint256 finalB) = StateChannelLib.closeChannel(channel);

        assertTrue(channel.closed);
        assertEq(finalA, INITIAL_BALANCE_A);
        assertEq(finalB, INITIAL_BALANCE_B);
    }

    function test_CloseChannel_ReturnsCurrentBalances() public {
        // First apply an update
        StateChannelLib.StateUpdate memory update = _createValidUpdate();
        StateChannelLib.applyStateUpdate(channel, update);

        (uint256 finalA, uint256 finalB) = StateChannelLib.closeChannel(channel);

        assertEq(finalA, 80 ether);
        assertEq(finalB, 70 ether);
    }

    // =========================================================================
    // Full flow integration test
    // =========================================================================

    function test_FullChannelFlow() public {
        // 1. Create channel (done in setUp)

        // 2. Create and validate state update
        StateChannelLib.StateUpdate memory update1 = StateChannelLib.StateUpdate({
            balanceA: 90 ether,
            balanceB: 60 ether,
            nonce: 1,
            signatureA: "",
            signatureB: ""
        });

        assertTrue(StateChannelLib.validateStateUpdate(channel, update1));

        // 3. Apply update
        StateChannelLib.applyStateUpdate(channel, update1);
        assertEq(channel.balanceA, 90 ether);
        assertEq(channel.balanceB, 60 ether);
        assertEq(channel.nonce, 1);

        // 4. Second update
        StateChannelLib.StateUpdate memory update2 = StateChannelLib.StateUpdate({
            balanceA: 70 ether,
            balanceB: 80 ether,
            nonce: 2,
            signatureA: "",
            signatureB: ""
        });

        assertTrue(StateChannelLib.validateStateUpdate(channel, update2));
        StateChannelLib.applyStateUpdate(channel, update2);
        assertEq(channel.balanceA, 70 ether);
        assertEq(channel.balanceB, 80 ether);
        assertEq(channel.nonce, 2);

        // 5. Close channel
        (uint256 finalA, uint256 finalB) = StateChannelLib.closeChannel(channel);
        assertEq(finalA, 70 ether);
        assertEq(finalB, 80 ether);
        assertTrue(channel.closed);

        // 6. Verify no more updates after close
        StateChannelLib.StateUpdate memory update3 = StateChannelLib.StateUpdate({
            balanceA: 50 ether,
            balanceB: 100 ether,
            nonce: 3,
            signatureA: "",
            signatureB: ""
        });

        vm.expectRevert(StateChannelLib.ChannelClosedError.selector);
        wrapper.validateStateUpdate(channel, update3);
    }
}
