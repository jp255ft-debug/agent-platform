// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {PaymentVerifier} from "../src/PaymentVerifier.sol";
import {EIP712Helper} from "../src/libraries/EIP712Helper.sol";

/// @title PaymentVerifierTest
/// @notice Comprehensive tests for PaymentVerifier contract
contract PaymentVerifierTest is Test {
    PaymentVerifier public verifier;

    address public sender;
    address public recipient = address(0x2);
    uint256 public senderPrivateKey = 0xA1B2C3D4;

    uint256 public constant AMOUNT = 1 ether;
    uint256 public constant DEADLINE_DURATION = 1 hours;

    function setUp() public {
        sender = vm.addr(senderPrivateKey);
        verifier = new PaymentVerifier();
    }

    // =========================================================================
    // verifyPayment()
    // =========================================================================

    function _createPayment(
        address _sender,
        address _recipient,
        uint256 _amount,
        uint256 _nonce,
        uint256 _deadline
    ) internal view returns (PaymentVerifier.Payment memory) {
        bytes32 structHash = keccak256(
            abi.encode(
                verifier.PAYMENT_TYPEHASH(),
                _sender,
                _recipient,
                _amount,
                _nonce,
                _deadline
            )
        );
        bytes32 digest = EIP712Helper.hashTypedData(verifier.DOMAIN_SEPARATOR(), structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(senderPrivateKey, digest);
        bytes memory signature = abi.encodePacked(r, s, v);

        return PaymentVerifier.Payment({
            sender: _sender,
            recipient: _recipient,
            amount: _amount,
            nonce: _nonce,
            deadline: _deadline,
            signature: signature
        });
    }

    function test_VerifyPayment() public {
        uint256 nonce = verifier.getNonce(sender);
        uint256 deadline = block.timestamp + DEADLINE_DURATION;

        PaymentVerifier.Payment memory payment = _createPayment(
            sender, recipient, AMOUNT, nonce, deadline
        );

        bool result = verifier.verifyPayment(payment);
        assertTrue(result);
    }

    function test_VerifyPayment_EmitsEvent() public {
        uint256 nonce = verifier.getNonce(sender);
        uint256 deadline = block.timestamp + DEADLINE_DURATION;

        PaymentVerifier.Payment memory payment = _createPayment(
            sender, recipient, AMOUNT, nonce, deadline
        );

        vm.expectEmit(true, true, false, true);
        emit PaymentVerifier.PaymentVerified(sender, recipient, AMOUNT, nonce);
        verifier.verifyPayment(payment);
    }

    function test_VerifyPayment_IncrementsNonce() public {
        uint256 nonce = verifier.getNonce(sender);
        uint256 deadline = block.timestamp + DEADLINE_DURATION;

        PaymentVerifier.Payment memory payment = _createPayment(
            sender, recipient, AMOUNT, nonce, deadline
        );

        verifier.verifyPayment(payment);
        assertEq(verifier.getNonce(sender), nonce + 1);
    }

    function test_VerifyPayment_MarksPaymentAsUsed() public {
        uint256 nonce = verifier.getNonce(sender);
        uint256 deadline = block.timestamp + DEADLINE_DURATION;

        PaymentVerifier.Payment memory payment = _createPayment(
            sender, recipient, AMOUNT, nonce, deadline
        );

        bytes32 paymentHash = keccak256(
            abi.encode(sender, recipient, AMOUNT, nonce, deadline)
        );

        assertFalse(verifier.isPaymentUsed(paymentHash));
        verifier.verifyPayment(payment);
        assertTrue(verifier.isPaymentUsed(paymentHash));
    }

    // =========================================================================
    // Revert cases
    // =========================================================================

    function test_RevertWhen_AmountIsZero() public {
        uint256 nonce = verifier.getNonce(sender);
        uint256 deadline = block.timestamp + DEADLINE_DURATION;

        PaymentVerifier.Payment memory payment = _createPayment(
            sender, recipient, 0, nonce, deadline
        );

        vm.expectRevert(PaymentVerifier.InvalidAmount.selector);
        verifier.verifyPayment(payment);
    }

    function test_RevertWhen_RecipientIsZero() public {
        uint256 nonce = verifier.getNonce(sender);
        uint256 deadline = block.timestamp + DEADLINE_DURATION;

        PaymentVerifier.Payment memory payment = _createPayment(
            sender, address(0), AMOUNT, nonce, deadline
        );

        vm.expectRevert(PaymentVerifier.InvalidRecipient.selector);
        verifier.verifyPayment(payment);
    }

    function test_RevertWhen_DeadlinePassed() public {
        uint256 nonce = verifier.getNonce(sender);
        uint256 deadline = block.timestamp - 1; // Already expired

        PaymentVerifier.Payment memory payment = _createPayment(
            sender, recipient, AMOUNT, nonce, deadline
        );

        vm.expectRevert(PaymentVerifier.PaymentExpired.selector);
        verifier.verifyPayment(payment);
    }

    function test_RevertWhen_InvalidSignature() public {
        uint256 nonce = verifier.getNonce(sender);
        uint256 deadline = block.timestamp + DEADLINE_DURATION;

        // Create payment with wrong signer
        uint256 wrongKey = 0xDEADBEEF;
        address wrongSender = vm.addr(wrongKey);

        bytes32 structHash = keccak256(
            abi.encode(
                verifier.PAYMENT_TYPEHASH(),
                wrongSender,
                recipient,
                AMOUNT,
                nonce,
                deadline
            )
        );
        bytes32 digest = EIP712Helper.hashTypedData(verifier.DOMAIN_SEPARATOR(), structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(wrongKey, digest);
        bytes memory signature = abi.encodePacked(r, s, v);

        PaymentVerifier.Payment memory payment = PaymentVerifier.Payment({
            sender: sender, // Claiming to be sender but signed by wrongSender
            recipient: recipient,
            amount: AMOUNT,
            nonce: nonce,
            deadline: deadline,
            signature: signature
        });

        vm.expectRevert(PaymentVerifier.InvalidSignature.selector);
        verifier.verifyPayment(payment);
    }

    function test_RevertWhen_ReplayAttack() public {
        uint256 nonce = verifier.getNonce(sender);
        uint256 deadline = block.timestamp + DEADLINE_DURATION;

        PaymentVerifier.Payment memory payment = _createPayment(
            sender, recipient, AMOUNT, nonce, deadline
        );

        // First use succeeds
        verifier.verifyPayment(payment);

        // Second use should fail (payment hash already used)
        vm.expectRevert(PaymentVerifier.PaymentAlreadyUsed.selector);
        verifier.verifyPayment(payment);
    }

    function test_RevertWhen_SamePaymentDifferentNonce() public {
        uint256 nonce = verifier.getNonce(sender);
        uint256 deadline = block.timestamp + DEADLINE_DURATION;

        PaymentVerifier.Payment memory payment1 = _createPayment(
            sender, recipient, AMOUNT, nonce, deadline
        );

        verifier.verifyPayment(payment1);

        // Same payment with incremented nonce should work
        PaymentVerifier.Payment memory payment2 = _createPayment(
            sender, recipient, AMOUNT, nonce + 1, deadline
        );

        bool result = verifier.verifyPayment(payment2);
        assertTrue(result);
    }

    // =========================================================================
    // Domain Separator
    // =========================================================================

    function test_DomainSeparator() public view {
        bytes32 expected = EIP712Helper.buildDomainSeparator(
            verifier.DOMAIN_NAME(),
            verifier.DOMAIN_VERSION(),
            block.chainid,
            address(verifier)
        );
        assertEq(verifier.DOMAIN_SEPARATOR(), expected);
    }

    // =========================================================================
    // Fuzz testing
    // =========================================================================

    function testFuzz_VerifyPayment_Consistency(
        uint256 _privateKey,
        uint256 _amount,
        uint256 _deadlineOffset
    ) public {
        vm.assume(_privateKey > 0 && _privateKey < 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141);
        vm.assume(_amount > 0 && _amount < 1000 ether);
        vm.assume(_deadlineOffset > 0 && _deadlineOffset < 30 days);

        address fuzzSender = vm.addr(_privateKey);
        address fuzzRecipient = address(uint160(uint256(keccak256(abi.encode(_privateKey, "recipient")))));

        uint256 nonce = verifier.getNonce(fuzzSender);
        uint256 deadline = block.timestamp + _deadlineOffset;

        bytes32 structHash = keccak256(
            abi.encode(
                verifier.PAYMENT_TYPEHASH(),
                fuzzSender,
                fuzzRecipient,
                _amount,
                nonce,
                deadline
            )
        );
        bytes32 digest = EIP712Helper.hashTypedData(verifier.DOMAIN_SEPARATOR(), structHash);

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(_privateKey, digest);
        bytes memory signature = abi.encodePacked(r, s, v);

        PaymentVerifier.Payment memory payment = PaymentVerifier.Payment({
            sender: fuzzSender,
            recipient: fuzzRecipient,
            amount: _amount,
            nonce: nonce,
            deadline: deadline,
            signature: signature
        });

        bool result = verifier.verifyPayment(payment);
        assertTrue(result);
        assertEq(verifier.getNonce(fuzzSender), nonce + 1);
    }
}
