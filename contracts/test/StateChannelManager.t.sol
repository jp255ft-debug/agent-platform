// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {StateChannelManager} from "../src/StateChannelManager.sol";
import {StateChannelLib} from "../src/libraries/StateChannelLib.sol";
import {EIP712Helper} from "../src/libraries/EIP712Helper.sol";

/// @title StateChannelManagerTest
/// @notice Testes completos para o StateChannelManager
contract StateChannelManagerTest is Test {
    StateChannelManager public manager;

    address public alice;
    address public bob;
    uint256 public aliceKey = 0xA1B2C3D4;
    uint256 public bobKey = 0xE5F6A7B8;

    uint256 public constant DEPOSIT = 1 ether;
    uint256 public constant DEADLINE = 1_000_000;
    bytes32 public channelId;

    // Event signatures for testing
    event ChannelOpened(
        bytes32 indexed channelId,
        address indexed partyA,
        address indexed partyB,
        uint256 depositA,
        uint256 depositB,
        uint256 deadline
    );
    event FundsAdded(bytes32 indexed channelId, address indexed party, uint256 amount);
    event ChannelClosed(bytes32 indexed channelId, address indexed closer, uint256 finalNonce, bytes32 finalStateHash);
    event DisputeRaised(bytes32 indexed channelId, address indexed challenger, uint256 disputedNonce, bytes32 disputedStateHash, uint256 challengeDeadline);
    event ChannelFinalized(bytes32 indexed channelId, address indexed partyA, address indexed partyB, uint256 amountToA, uint256 amountToB);

    function setUp() public {
        manager = new StateChannelManager();
        alice = vm.addr(aliceKey);
        bob = vm.addr(bobKey);

        vm.deal(alice, 100 ether);
        vm.deal(bob, 100 ether);
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    function _openChannel() internal returns (bytes32) {
        vm.prank(alice);
        manager.deposit{value: DEPOSIT}(bob, 0, DEADLINE);

        bytes32 id = keccak256(abi.encodePacked(alice, bob, uint256(1)));
        return id;
    }

    function _signStateUpdate(
        uint256 _privateKey,
        address _partyA,
        address _partyB,
        uint256 _balanceA,
        uint256 _balanceB,
        uint256 _nonce,
        uint256 _deadline
    ) internal view returns (bytes memory) {
        bytes32 structHash = keccak256(
            abi.encode(
                StateChannelLib.CHANNEL_STATE_TYPEHASH,
                _partyA,
                _partyB,
                _balanceA,
                _balanceB,
                _nonce,
                _deadline
            )
        );
        bytes32 digest = EIP712Helper.hashTypedData(manager.DOMAIN_SEPARATOR(), structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(_privateKey, digest);
        return abi.encodePacked(r, s, v);
    }

    function _setupChannelWithUpdates() internal returns (bytes32) {
        bytes32 id = _openChannel();

        // Bob adds funds
        vm.prank(bob);
        manager.addFunds{value: DEPOSIT}(id);

        // Update state: Alice pays Bob 0.5 ETH
        bytes memory sigA = _signStateUpdate(aliceKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);
        bytes memory sigB = _signStateUpdate(bobKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);

        vm.prank(alice);
        manager.updateState(id, 1.5 ether, 0.5 ether, 1, sigA, sigB);

        return id;
    }

    // =========================================================================
    // deposit()
    // =========================================================================

    function test_Deposit_OpensChannel() public {
        bytes32 id = _openChannel();

        (
            address participantA,
            address participantB,
            uint256 balanceA,
            uint256 balanceB,
            uint256 nonce,
            uint256 deadline,
            bool closed,
            bool finalized,
            uint256 depositA,
            uint256 depositB
        ) = manager.getChannelInfo(id);

        assertEq(participantA, alice);
        assertEq(participantB, bob);
        assertEq(balanceA, DEPOSIT);
        assertEq(balanceB, 0);
        assertEq(nonce, 0);
        assertEq(deadline, DEADLINE);
        assertFalse(closed);
        assertFalse(finalized);
        assertEq(depositA, DEPOSIT);
        assertEq(depositB, 0);
    }

    function test_Deposit_RevertWhen_InvalidParty() public {
        vm.prank(alice);
        vm.expectRevert(StateChannelManager.InvalidParty.selector);
        manager.deposit{value: DEPOSIT}(address(0), 0, DEADLINE);

        vm.prank(alice);
        vm.expectRevert(StateChannelManager.InvalidParty.selector);
        manager.deposit{value: DEPOSIT}(alice, 0, DEADLINE);
    }

    function test_Deposit_RevertWhen_BelowMinimum() public {
        vm.prank(alice);
        vm.expectRevert(StateChannelManager.DepositBelowMinimum.selector);
        manager.deposit{value: 0.001 ether}(bob, 0, DEADLINE);
    }

    function test_Deposit_EmitsEvent() public {
        vm.prank(alice);
        vm.expectEmit(true, true, true, true);
        emit ChannelOpened(
            keccak256(abi.encodePacked(alice, bob, uint256(1))),
            alice, bob, DEPOSIT, 0, DEADLINE
        );
        manager.deposit{value: DEPOSIT}(bob, 0, DEADLINE);
    }

    // =========================================================================
    // addFunds()
    // =========================================================================

    function test_AddFunds_ByAlice() public {
        bytes32 id = _openChannel();

        vm.prank(alice);
        vm.expectEmit(true, true, false, true);
        emit FundsAdded(id, alice, 0.5 ether);
        manager.addFunds{value: 0.5 ether}(id);

        (,,,,,,,, uint256 depositA,) = manager.getChannelInfo(id);
        assertEq(depositA, DEPOSIT + 0.5 ether);
    }

    function test_AddFunds_ByBob() public {
        bytes32 id = _openChannel();

        vm.prank(bob);
        manager.addFunds{value: 0.5 ether}(id);

        (,,,,,,,,, uint256 depositB) = manager.getChannelInfo(id);
        assertEq(depositB, 0.5 ether);
    }

    function test_AddFunds_RevertWhen_NotParty() public {
        bytes32 id = _openChannel();
        address charlie = address(0x3);
        vm.deal(charlie, 10 ether);

        vm.prank(charlie);
        vm.expectRevert(StateChannelManager.NotParty.selector);
        manager.addFunds{value: 1 ether}(id);
    }

    function test_AddFunds_RevertWhen_ChannelNotFound() public {
        vm.prank(alice);
        vm.expectRevert(StateChannelManager.ChannelNotFound.selector);
        manager.addFunds{value: 1 ether}(keccak256("fake"));
    }

    // =========================================================================
    // updateState()
    // =========================================================================

    function test_UpdateState_Success() public {
        bytes32 id = _setupChannelWithUpdates();

        (,, uint256 balanceA, uint256 balanceB, uint256 nonce,,,,,) = manager.getChannelInfo(id);
        assertEq(balanceA, 1.5 ether);
        assertEq(balanceB, 0.5 ether);
        assertEq(nonce, 1);
    }

    function test_UpdateState_RevertWhen_InvalidNonce() public {
        bytes32 id = _openChannel();

        bytes memory sigA = _signStateUpdate(aliceKey, alice, bob, 0.5 ether, 0.5 ether, 0, DEADLINE);
        bytes memory sigB = _signStateUpdate(bobKey, alice, bob, 0.5 ether, 0.5 ether, 0, DEADLINE);

        vm.prank(alice);
        vm.expectRevert(StateChannelLib.InvalidNonce.selector);
        manager.updateState(id, 0.5 ether, 0.5 ether, 0, sigA, sigB);
    }

    function test_UpdateState_RevertWhen_BalanceMismatch() public {
        bytes32 id = _openChannel();

        bytes memory sigA = _signStateUpdate(aliceKey, alice, bob, 2 ether, 0.5 ether, 1, DEADLINE);
        bytes memory sigB = _signStateUpdate(bobKey, alice, bob, 2 ether, 0.5 ether, 1, DEADLINE);

        vm.prank(alice);
        vm.expectRevert(StateChannelLib.BalanceMismatch.selector);
        manager.updateState(id, 2 ether, 0.5 ether, 1, sigA, sigB);
    }

    function test_UpdateState_RevertWhen_InvalidSignatureA() public {
        bytes32 id = _openChannel();

        bytes memory sigA = _signStateUpdate(bobKey, alice, bob, 0.5 ether, 0.5 ether, 1, DEADLINE); // Wrong key
        bytes memory sigB = _signStateUpdate(bobKey, alice, bob, 0.5 ether, 0.5 ether, 1, DEADLINE);

        vm.prank(alice);
        vm.expectRevert(StateChannelLib.InvalidSignature.selector);
        manager.updateState(id, 0.5 ether, 0.5 ether, 1, sigA, sigB);
    }

    function test_UpdateState_RevertWhen_InvalidSignatureB() public {
        bytes32 id = _openChannel();

        bytes memory sigA = _signStateUpdate(aliceKey, alice, bob, 0.5 ether, 0.5 ether, 1, DEADLINE);
        bytes memory sigB = _signStateUpdate(aliceKey, alice, bob, 0.5 ether, 0.5 ether, 1, DEADLINE); // Wrong key

        vm.prank(alice);
        vm.expectRevert(StateChannelLib.InvalidSignature.selector);
        manager.updateState(id, 0.5 ether, 0.5 ether, 1, sigA, sigB);
    }

    // =========================================================================
    // closeChannel()
    // =========================================================================

    function test_CloseChannel_Success() public {
        bytes32 id = _setupChannelWithUpdates();

        bytes memory sigA = _signStateUpdate(aliceKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);
        bytes memory sigB = _signStateUpdate(bobKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);

        vm.prank(alice);
        manager.closeChannel(id, 1.5 ether, 0.5 ether, 1, sigA, sigB);

        (,,,,,, bool closed,,,) = manager.getChannelInfo(id);
        assertTrue(closed);

        (uint256 closeNonce,, uint256 challengeDeadline,) = manager.getCloseInfo(id);
        assertEq(closeNonce, 1);
        assertEq(challengeDeadline, block.timestamp + 1 days);
    }

    function test_CloseChannel_RevertWhen_NonceTooHigh() public {
        bytes32 id = _setupChannelWithUpdates();

        bytes memory sigA = _signStateUpdate(aliceKey, alice, bob, 1.5 ether, 0.5 ether, 2, DEADLINE);
        bytes memory sigB = _signStateUpdate(bobKey, alice, bob, 1.5 ether, 0.5 ether, 2, DEADLINE);

        vm.prank(alice);
        vm.expectRevert(StateChannelManager.NonceNotGreater.selector);
        manager.closeChannel(id, 1.5 ether, 0.5 ether, 2, sigA, sigB);
    }

    function test_CloseChannel_RevertWhen_InvalidSignature() public {
        bytes32 id = _setupChannelWithUpdates();

        bytes memory sigA = _signStateUpdate(bobKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE); // Wrong key

        vm.prank(alice);
        vm.expectRevert(StateChannelManager.InvalidSignatureA.selector);
        manager.closeChannel(id, 1.5 ether, 0.5 ether, 1, sigA, "");
    }

    // =========================================================================
    // dispute()
    // =========================================================================

    function test_Dispute_Success() public {
        bytes32 id = _openChannel();

        // Bob adds funds
        vm.prank(bob);
        manager.addFunds{value: DEPOSIT}(id);

        // Update to nonce 1: Alice pays Bob 0.5 ETH
        bytes memory sigA1 = _signStateUpdate(aliceKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);
        bytes memory sigB1 = _signStateUpdate(bobKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);
        vm.prank(alice);
        manager.updateState(id, 1.5 ether, 0.5 ether, 1, sigA1, sigB1);

        // Update to nonce 2: Alice pays Bob another 0.5 ETH
        bytes memory sigA2 = _signStateUpdate(aliceKey, alice, bob, 1 ether, 1 ether, 2, DEADLINE);
        bytes memory sigB2 = _signStateUpdate(bobKey, alice, bob, 1 ether, 1 ether, 2, DEADLINE);
        vm.prank(alice);
        manager.updateState(id, 1 ether, 1 ether, 2, sigA2, sigB2);

        // Close with nonce 1 (stale state - Bob tries to cheat)
        bytes memory sigA_close = _signStateUpdate(aliceKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);
        bytes memory sigB_close = _signStateUpdate(bobKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);
        vm.prank(bob);
        manager.closeChannel(id, 1.5 ether, 0.5 ether, 1, sigA_close, sigB_close);

        // Dispute with nonce 2 (correct state)
        vm.prank(alice);
        manager.dispute(id, 1 ether, 1 ether, 2, sigA2, sigB2);

        (uint256 closeNonce,,,) = manager.getCloseInfo(id);
        assertEq(closeNonce, 2);
    }

    function test_Dispute_RevertWhen_ChannelNotClosed() public {
        bytes32 id = _openChannel();

        bytes memory sigA = _signStateUpdate(aliceKey, alice, bob, 0.5 ether, 0.5 ether, 1, DEADLINE);
        bytes memory sigB = _signStateUpdate(bobKey, alice, bob, 0.5 ether, 0.5 ether, 1, DEADLINE);

        vm.prank(bob);
        vm.expectRevert(StateChannelManager.ChannelNotClosed.selector);
        manager.dispute(id, 0.5 ether, 0.5 ether, 1, sigA, sigB);
    }

    function test_Dispute_RevertWhen_NonceNotHigher() public {
        bytes32 id = _setupChannelWithUpdates();

        bytes memory sigA = _signStateUpdate(aliceKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);
        bytes memory sigB = _signStateUpdate(bobKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);

        vm.prank(alice);
        manager.closeChannel(id, 1.5 ether, 0.5 ether, 1, sigA, sigB);

        // Try to dispute with same nonce
        vm.prank(bob);
        vm.expectRevert(StateChannelManager.DisputedNonceNotHigher.selector);
        manager.dispute(id, 1.5 ether, 0.5 ether, 1, sigA, sigB);
    }

    function test_Dispute_RevertWhen_ChallengeExpired() public {
        bytes32 id = _setupChannelWithUpdates();

        bytes memory sigA = _signStateUpdate(aliceKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);
        bytes memory sigB = _signStateUpdate(bobKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);

        vm.prank(alice);
        manager.closeChannel(id, 1.5 ether, 0.5 ether, 1, sigA, sigB);

        // Warp past challenge window
        vm.warp(block.timestamp + 2 days);

        bytes memory sigA2 = _signStateUpdate(aliceKey, alice, bob, 1 ether, 1 ether, 2, DEADLINE);
        bytes memory sigB2 = _signStateUpdate(bobKey, alice, bob, 1 ether, 1 ether, 2, DEADLINE);

        vm.prank(bob);
        vm.expectRevert(StateChannelManager.ChallengeWindowExpired.selector);
        manager.dispute(id, 1 ether, 1 ether, 2, sigA2, sigB2);
    }

    // =========================================================================
    // finalize()
    // =========================================================================

    function test_Finalize_Success() public {
        bytes32 id = _setupChannelWithUpdates();

        bytes memory sigA = _signStateUpdate(aliceKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);
        bytes memory sigB = _signStateUpdate(bobKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);

        vm.prank(alice);
        manager.closeChannel(id, 1.5 ether, 0.5 ether, 1, sigA, sigB);

        // Warp past challenge window
        vm.warp(block.timestamp + 2 days);

        uint256 aliceBalanceBefore = alice.balance;
        uint256 bobBalanceBefore = bob.balance;

        vm.prank(alice);
        manager.finalize(id);

        // Alice gets 75% (1.5 / 2.0), Bob gets 25% (0.5 / 2.0)
        uint256 totalDeposit = 2 ether; // 1 from Alice + 1 from Bob
        uint256 expectedAlice = (totalDeposit * 1.5 ether) / 2 ether; // 1.5 ETH
        uint256 expectedBob = totalDeposit - expectedAlice; // 0.5 ETH

        assertEq(alice.balance, aliceBalanceBefore + expectedAlice);
        assertEq(bob.balance, bobBalanceBefore + expectedBob);

        (,,,,,,, bool finalized,,) = manager.getChannelInfo(id);
        assertTrue(finalized);
    }

    function test_Finalize_RevertWhen_NotClosed() public {
        bytes32 id = _openChannel();

        vm.prank(alice);
        vm.expectRevert(StateChannelManager.ChannelNotClosed.selector);
        manager.finalize(id);
    }

    function test_Finalize_RevertWhen_ChallengeActive() public {
        bytes32 id = _setupChannelWithUpdates();

        bytes memory sigA = _signStateUpdate(aliceKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);
        bytes memory sigB = _signStateUpdate(bobKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);

        vm.prank(alice);
        manager.closeChannel(id, 1.5 ether, 0.5 ether, 1, sigA, sigB);

        vm.prank(alice);
        vm.expectRevert(StateChannelManager.ChallengeWindowExpired.selector);
        manager.finalize(id);
    }

    function test_Finalize_RevertWhen_AlreadyFinalized() public {
        bytes32 id = _setupChannelWithUpdates();

        bytes memory sigA = _signStateUpdate(aliceKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);
        bytes memory sigB = _signStateUpdate(bobKey, alice, bob, 1.5 ether, 0.5 ether, 1, DEADLINE);

        vm.prank(alice);
        manager.closeChannel(id, 1.5 ether, 0.5 ether, 1, sigA, sigB);

        vm.warp(block.timestamp + 2 days);

        vm.prank(alice);
        manager.finalize(id);

        vm.prank(alice);
        vm.expectRevert(StateChannelManager.AlreadyFinalized.selector);
        manager.finalize(id);
    }

    // =========================================================================
    // Full flow integration
    // =========================================================================

    function test_FullChannelFlow_WithDispute() public {
        bytes32 id = _openChannel();

        // Bob adds funds
        vm.prank(bob);
        manager.addFunds{value: DEPOSIT}(id);

        // Update 1: Alice pays Bob 0.3 ETH
        bytes memory sigA1 = _signStateUpdate(aliceKey, alice, bob, 1.7 ether, 0.3 ether, 1, DEADLINE);
        bytes memory sigB1 = _signStateUpdate(bobKey, alice, bob, 1.7 ether, 0.3 ether, 1, DEADLINE);
        vm.prank(alice);
        manager.updateState(id, 1.7 ether, 0.3 ether, 1, sigA1, sigB1);

        // Update 2: Alice pays Bob another 0.2 ETH
        bytes memory sigA2 = _signStateUpdate(aliceKey, alice, bob, 1.5 ether, 0.5 ether, 2, DEADLINE);
        bytes memory sigB2 = _signStateUpdate(bobKey, alice, bob, 1.5 ether, 0.5 ether, 2, DEADLINE);
        vm.prank(alice);
        manager.updateState(id, 1.5 ether, 0.5 ether, 2, sigA2, sigB2);

        // Close with nonce 1 (stale state - Bob tries to cheat)
        bytes memory sigA_close = _signStateUpdate(aliceKey, alice, bob, 1.7 ether, 0.3 ether, 1, DEADLINE);
        bytes memory sigB_close = _signStateUpdate(bobKey, alice, bob, 1.7 ether, 0.3 ether, 1, DEADLINE);
        vm.prank(bob);
        manager.closeChannel(id, 1.7 ether, 0.3 ether, 1, sigA_close, sigB_close);

        // Alice disputes with nonce 2 (correct state)
        bytes memory sigA_dispute = _signStateUpdate(aliceKey, alice, bob, 1.5 ether, 0.5 ether, 2, DEADLINE);
        bytes memory sigB_dispute = _signStateUpdate(bobKey, alice, bob, 1.5 ether, 0.5 ether, 2, DEADLINE);
        vm.prank(alice);
        manager.dispute(id, 1.5 ether, 0.5 ether, 2, sigA_dispute, sigB_dispute);

        // Verify closeNonce was updated
        (uint256 closeNonce,,,) = manager.getCloseInfo(id);
        assertEq(closeNonce, 2);

        // Finalize
        vm.warp(block.timestamp + 2 days);

        uint256 aliceBefore = alice.balance;
        uint256 bobBefore = bob.balance;

        vm.prank(alice);
        manager.finalize(id);

        // Alice should get 75% (1.5/2.0), Bob 25% (0.5/2.0)
        uint256 total = 2 ether;
        uint256 expectedAlice = (total * 1.5 ether) / 2 ether;
        uint256 expectedBob = total - expectedAlice;

        assertEq(alice.balance, aliceBefore + expectedAlice);
        assertEq(bob.balance, bobBefore + expectedBob);
    }

    // =========================================================================
    // View functions
    // =========================================================================

    function test_GetChannelInfo_Empty() public view {
        (address a,,,,,,,,,) = manager.getChannelInfo(keccak256("nonexistent"));
        assertEq(a, address(0));
    }

    function test_GetCloseInfo_Empty() public view {
        (uint256 nonce,,,) = manager.getCloseInfo(keccak256("nonexistent"));
        assertEq(nonce, 0);
    }

    function test_GetChannelNonce() public {
        assertEq(manager.getChannelNonce(), 0);
        _openChannel();
        assertEq(manager.getChannelNonce(), 1);
        _openChannel();
        assertEq(manager.getChannelNonce(), 2);
    }

    // =========================================================================
    // Constants
    // =========================================================================

    function test_Constants() public view {
        assertEq(manager.CHALLENGE_WINDOW(), 1 days);
        assertEq(manager.MIN_DEPOSIT(), 0.01 ether);
        assertEq(manager.DOMAIN_NAME(), "AgentPlatform");
        assertEq(manager.DOMAIN_VERSION(), "1");
    }
}
