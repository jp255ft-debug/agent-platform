// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {AgentDelegation} from "../src/AgentDelegation.sol";
import {EIP712Helper} from "../src/libraries/EIP712Helper.sol";

/// @title AgentDelegationTest
/// @notice Comprehensive tests for AgentDelegation contract with budget cap
contract AgentDelegationTest is Test {
    AgentDelegation public delegation;

    address public agent;
    address public delegate = address(0x2);
    address public thirdParty = address(0x3);
    address public spendRecorder = address(0x4);

    uint256 public agentPrivateKey = 0xA1B2C3D4;
    uint256 public constant EXPIRY_DURATION = 1 days;
    uint256 public constant DEFAULT_BUDGET = 100 ether;

    function setUp() public {
        agent = vm.addr(agentPrivateKey);
        delegation = new AgentDelegation();

        // Authorize spendRecorder for budget tests
        vm.prank(address(delegation));
        delegation.setSpendRecorder(spendRecorder, true);
    }

    // =========================================================================
    // delegate()
    // =========================================================================

    function test_Delegate() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        AgentDelegation.Delegation memory del = delegation.getDelegation(agent);

        assertEq(del.agent, agent);
        assertEq(del.delegate, delegate);
        assertTrue(del.active);
        assertEq(del.expiresAt, block.timestamp + EXPIRY_DURATION);
        assertEq(del.maxBudget, DEFAULT_BUDGET);
        assertEq(del.spentAmount, 0);
    }

    function test_Delegate_EmitsEvent() public {
        vm.prank(agent);
        vm.expectEmit(true, true, false, true);
        emit AgentDelegation.DelegationCreated(agent, delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET, 0);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);
    }

    function test_RevertWhen_AlreadyDelegated() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        vm.prank(agent);
        vm.expectRevert(AgentDelegation.DelegationAlreadyExists.selector);
        delegation.delegate(delegate, block.timestamp + 2 days, DEFAULT_BUDGET);
    }

    function test_RevertWhen_ExpiryInPast() public {
        vm.prank(agent);
        vm.expectRevert(AgentDelegation.DelegationExpiredError.selector);
        delegation.delegate(delegate, block.timestamp - 1, DEFAULT_BUDGET);
    }

    function test_RevertWhen_DelegateIsZero() public {
        vm.prank(agent);
        vm.expectRevert(AgentDelegation.DelegationNotFound.selector);
        delegation.delegate(address(0), block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);
    }

    // =========================================================================
    // revoke()
    // =========================================================================

    function test_Revoke() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        vm.prank(agent);
        delegation.revoke();

        AgentDelegation.Delegation memory del = delegation.getDelegation(agent);
        assertFalse(del.active);
    }

    function test_Revoke_EmitsEvent() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        vm.prank(agent);
        vm.expectEmit(true, true, false, true);
        emit AgentDelegation.DelegationRevoked(agent, delegate);
        delegation.revoke();
    }

    function test_RevertWhen_RevokeWithoutDelegation() public {
        vm.prank(agent);
        vm.expectRevert(AgentDelegation.DelegationNotFound.selector);
        delegation.revoke();
    }

    function test_RevertWhen_RevokeTwice() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        vm.prank(agent);
        delegation.revoke();

        vm.prank(agent);
        vm.expectRevert(AgentDelegation.DelegationNotFound.selector);
        delegation.revoke();
    }

    // =========================================================================
    // isValidDelegation()
    // =========================================================================

    function test_IsValidDelegation() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        assertTrue(delegation.isValidDelegation(agent, delegate));
    }

    function test_IsValidDelegation_AfterRevoke() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        vm.prank(agent);
        delegation.revoke();

        assertFalse(delegation.isValidDelegation(agent, delegate));
    }

    function test_IsValidDelegation_WrongDelegate() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        assertFalse(delegation.isValidDelegation(agent, thirdParty));
    }

    function test_IsValidDelegation_AfterExpiry() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + 1, DEFAULT_BUDGET);

        vm.warp(block.timestamp + 2);

        assertFalse(delegation.isValidDelegation(agent, delegate));
    }

    // =========================================================================
    // delegateBySig() (EIP-712)
    // =========================================================================

    function test_DelegateBySig() public {
        uint256 nonce = delegation.getNonce(agent);
        uint256 expiresAt = block.timestamp + EXPIRY_DURATION;

        bytes32 structHash = keccak256(
            abi.encode(delegation.DELEGATION_TYPEHASH(), agent, delegate, expiresAt, nonce, DEFAULT_BUDGET)
        );
        bytes32 digest = EIP712Helper.hashTypedData(delegation.DOMAIN_SEPARATOR(), structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(agentPrivateKey, digest);
        bytes memory signature = abi.encodePacked(r, s, v);

        delegation.delegateBySig(agent, delegate, expiresAt, DEFAULT_BUDGET, signature);

        AgentDelegation.Delegation memory del = delegation.getDelegation(agent);
        assertEq(del.agent, agent);
        assertEq(del.delegate, delegate);
        assertTrue(del.active);
        assertEq(del.maxBudget, DEFAULT_BUDGET);
    }

    function test_DelegateBySig_IncrementsNonce() public {
        uint256 nonce = delegation.getNonce(agent);
        uint256 expiresAt = block.timestamp + EXPIRY_DURATION;

        bytes32 structHash = keccak256(
            abi.encode(delegation.DELEGATION_TYPEHASH(), agent, delegate, expiresAt, nonce, DEFAULT_BUDGET)
        );
        bytes32 digest = EIP712Helper.hashTypedData(delegation.DOMAIN_SEPARATOR(), structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(agentPrivateKey, digest);
        bytes memory signature = abi.encodePacked(r, s, v);

        delegation.delegateBySig(agent, delegate, expiresAt, DEFAULT_BUDGET, signature);

        assertEq(delegation.getNonce(agent), nonce + 1);
    }

    function test_RevertWhen_DelegateBySig_InvalidSignature() public {
        uint256 expiresAt = block.timestamp + EXPIRY_DURATION;
        bytes memory invalidSig = abi.encodePacked(
            bytes32(uint256(0xBAD)),
            bytes32(uint256(0xBAD)),
            uint8(27)
        );

        vm.expectRevert(AgentDelegation.InvalidSignature.selector);
        delegation.delegateBySig(agent, delegate, expiresAt, DEFAULT_BUDGET, invalidSig);
    }

    function test_RevertWhen_DelegateBySig_ReplayAttack() public {
        uint256 nonce = delegation.getNonce(agent);
        uint256 expiresAt = block.timestamp + EXPIRY_DURATION;

        bytes32 structHash = keccak256(
            abi.encode(delegation.DELEGATION_TYPEHASH(), agent, delegate, expiresAt, nonce, DEFAULT_BUDGET)
        );
        bytes32 digest = EIP712Helper.hashTypedData(delegation.DOMAIN_SEPARATOR(), structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(agentPrivateKey, digest);
        bytes memory signature = abi.encodePacked(r, s, v);

        // First use succeeds
        delegation.delegateBySig(agent, delegate, expiresAt, DEFAULT_BUDGET, signature);

        // Second use should fail (nonce changed)
        vm.expectRevert(AgentDelegation.InvalidSignature.selector);
        delegation.delegateBySig(agent, delegate, expiresAt, DEFAULT_BUDGET, signature);
    }

    // =========================================================================
    // revokeBySig() (EIP-712)
    // =========================================================================

    function test_RevokeBySig() public {
        // First create delegation
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        // Now revoke via signature
        uint256 nonce = delegation.getNonce(agent);
        bytes32 structHash = keccak256(
            abi.encode(delegation.DELEGATION_TYPEHASH(), agent, address(0), uint256(0), nonce, uint256(0))
        );
        bytes32 digest = EIP712Helper.hashTypedData(delegation.DOMAIN_SEPARATOR(), structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(agentPrivateKey, digest);
        bytes memory signature = abi.encodePacked(r, s, v);

        delegation.revokeBySig(agent, signature);

        AgentDelegation.Delegation memory del = delegation.getDelegation(agent);
        assertFalse(del.active);
    }

    function test_RevokeBySig_IncrementsNonce() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        uint256 nonce = delegation.getNonce(agent);
        bytes32 structHash = keccak256(
            abi.encode(delegation.DELEGATION_TYPEHASH(), agent, address(0), uint256(0), nonce, uint256(0))
        );
        bytes32 digest = EIP712Helper.hashTypedData(delegation.DOMAIN_SEPARATOR(), structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(agentPrivateKey, digest);
        bytes memory signature = abi.encodePacked(r, s, v);

        delegation.revokeBySig(agent, signature);
        assertEq(delegation.getNonce(agent), nonce + 1);
    }

    // =========================================================================
    // getDelegationHistory()
    // =========================================================================

    function test_GetDelegationHistory() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        address[] memory history = delegation.getDelegationHistory(agent);
        assertEq(history.length, 1);
        assertEq(history[0], delegate);
    }

    function test_GetDelegationHistory_MultipleDelegations() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        vm.prank(agent);
        delegation.revoke();

        address delegate2 = address(0x5);
        vm.prank(agent);
        delegation.delegate(delegate2, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        address[] memory history = delegation.getDelegationHistory(agent);
        assertEq(history.length, 2);
        assertEq(history[0], delegate);
        assertEq(history[1], delegate2);
    }

    // =========================================================================
    // Domain Separator
    // =========================================================================

    function test_DomainSeparator() public view {
        bytes32 expected = EIP712Helper.buildDomainSeparator(
            delegation.DOMAIN_NAME(),
            delegation.DOMAIN_VERSION(),
            block.chainid,
            address(delegation)
        );
        assertEq(delegation.DOMAIN_SEPARATOR(), expected);
    }

    // =========================================================================
    // Budget Cap Tests
    // =========================================================================

    function test_RecordSpend() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        vm.prank(spendRecorder);
        delegation.recordSpend(agent, 10 ether);

        AgentDelegation.Delegation memory del = delegation.getDelegation(agent);
        assertEq(del.spentAmount, 10 ether);
    }

    function test_RecordSpend_EmitsEvent() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        vm.prank(spendRecorder);
        vm.expectEmit(true, true, true, true);
        emit AgentDelegation.SpendRecorded(agent, 10 ether, 10 ether, 90 ether);
        delegation.recordSpend(agent, 10 ether);
    }

    function test_RecordSpend_Multiple() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        vm.prank(spendRecorder);
        delegation.recordSpend(agent, 30 ether);

        vm.prank(spendRecorder);
        delegation.recordSpend(agent, 20 ether);

        AgentDelegation.Delegation memory del = delegation.getDelegation(agent);
        assertEq(del.spentAmount, 50 ether);
    }

    function test_RevertWhen_RecordSpend_ExceedsBudget() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        vm.prank(spendRecorder);
        vm.expectRevert(AgentDelegation.BudgetExceeded.selector);
        delegation.recordSpend(agent, 101 ether);
    }

    function test_RevertWhen_RecordSpend_UnauthorizedCaller() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        vm.prank(thirdParty);
        vm.expectRevert(AgentDelegation.UnauthorizedSpendRecorder.selector);
        delegation.recordSpend(agent, 1 ether);
    }

    function test_RevertWhen_RecordSpend_NoDelegation() public {
        vm.prank(spendRecorder);
        vm.expectRevert(AgentDelegation.DelegationNotFound.selector);
        delegation.recordSpend(agent, 1 ether);
    }

    function test_RevertWhen_RecordSpend_AfterRevoke() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        vm.prank(agent);
        delegation.revoke();

        vm.prank(spendRecorder);
        vm.expectRevert(AgentDelegation.DelegationNotFound.selector);
        delegation.recordSpend(agent, 1 ether);
    }

    function test_RevertWhen_RecordSpend_AfterExpiry() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + 1, DEFAULT_BUDGET);

        vm.warp(block.timestamp + 2);

        vm.prank(spendRecorder);
        vm.expectRevert(AgentDelegation.DelegationExpiredError.selector);
        delegation.recordSpend(agent, 1 ether);
    }

    function test_GetRemainingBudget() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        assertEq(delegation.getRemainingBudget(agent), DEFAULT_BUDGET);

        vm.prank(spendRecorder);
        delegation.recordSpend(agent, 30 ether);

        assertEq(delegation.getRemainingBudget(agent), 70 ether);
    }

    function test_GetRemainingBudget_NoDelegation() public {
        assertEq(delegation.getRemainingBudget(agent), 0);
    }

    function test_GetRemainingBudget_Exhausted() public {
        vm.prank(agent);
        delegation.delegate(delegate, block.timestamp + EXPIRY_DURATION, DEFAULT_BUDGET);

        vm.prank(spendRecorder);
        delegation.recordSpend(agent, DEFAULT_BUDGET);

        assertEq(delegation.getRemainingBudget(agent), 0);
    }

    function test_SetSpendRecorder() public {
        address newRecorder = address(0x6);

        vm.prank(address(delegation));
        delegation.setSpendRecorder(newRecorder, true);

        assertTrue(delegation.spendRecorders(newRecorder));

        vm.prank(address(delegation));
        delegation.setSpendRecorder(newRecorder, false);

        assertFalse(delegation.spendRecorders(newRecorder));
    }

    function test_RevertWhen_SetSpendRecorder_Unauthorized() public {
        vm.prank(thirdParty);
        vm.expectRevert(AgentDelegation.Unauthorized.selector);
        delegation.setSpendRecorder(address(0x6), true);
    }

    // =========================================================================
    // Fuzz testing
    // =========================================================================

    function testFuzz_DelegateBySig_Consistency(
        uint256 _privateKey,
        uint256 _expiryOffset,
        uint256 _budget
    ) public {
        vm.assume(_privateKey > 0 && _privateKey < 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141);
        vm.assume(_expiryOffset > 0 && _expiryOffset < 365 days);
        vm.assume(_budget > 0 && _budget < 1_000_000 ether);

        address fuzzAgent = vm.addr(_privateKey);
        address fuzzDelegate = address(uint160(uint256(keccak256(abi.encode(_privateKey, "delegate")))));

        uint256 expiresAt = block.timestamp + _expiryOffset;
        uint256 nonce = delegation.getNonce(fuzzAgent);

        bytes32 structHash = keccak256(
            abi.encode(delegation.DELEGATION_TYPEHASH(), fuzzAgent, fuzzDelegate, expiresAt, nonce, _budget)
        );
        bytes32 digest = EIP712Helper.hashTypedData(delegation.DOMAIN_SEPARATOR(), structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(_privateKey, digest);
        bytes memory signature = abi.encodePacked(r, s, v);

        delegation.delegateBySig(fuzzAgent, fuzzDelegate, expiresAt, _budget, signature);

        assertTrue(delegation.isValidDelegation(fuzzAgent, fuzzDelegate));
        assertEq(delegation.getRemainingBudget(fuzzAgent), _budget);
    }
}
