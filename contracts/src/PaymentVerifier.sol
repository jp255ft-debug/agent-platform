// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {EIP712Helper} from "./libraries/EIP712Helper.sol";

/// @title PaymentVerifier
/// @notice Verifies x402 payments on-chain using EIP-712 typed signatures
/// @dev Implements replay protection via nonces and used payment hashes
contract PaymentVerifier {
    using EIP712Helper for bytes32;

    // =========================================================================
    // Constants
    // =========================================================================

    /// @notice EIP-712 typehash for payment
    bytes32 public constant PAYMENT_TYPEHASH =
        keccak256("Payment(address sender,address recipient,uint256 amount,uint256 nonce,uint256 deadline)");

    /// @notice Domain name for EIP-712
    string public constant DOMAIN_NAME = "AgentPlatform";

    /// @notice Domain version for EIP-712
    string public constant DOMAIN_VERSION = "1";

    // =========================================================================
    // Types
    // =========================================================================

    /// @notice Represents a payment to be verified
    struct Payment {
        address sender;
        address recipient;
        uint256 amount;
        uint256 nonce;
        uint256 deadline;
        bytes signature;
    }

    // =========================================================================
    // State
    // =========================================================================

    /// @notice Mapping from sender address to their current nonce
    mapping(address => uint256) public nonces;

    /// @notice Mapping from payment hash to whether it has been used (replay protection)
    mapping(bytes32 => bool) public usedPayments;

    /// @notice Cached domain separator
    bytes32 public immutable DOMAIN_SEPARATOR;

    // =========================================================================
    // Events
    // =========================================================================

    /// @notice Emitted when a payment is successfully verified
    event PaymentVerified(
        address indexed sender,
        address indexed recipient,
        uint256 amount,
        uint256 nonce
    );

    /// @notice Emitted when a payment is rejected due to replay
    event PaymentReused(bytes32 indexed paymentHash);

    // =========================================================================
    // Errors
    // =========================================================================

    /// @notice Thrown when the EIP-712 signature is invalid
    error InvalidSignature();

    /// @notice Thrown when the payment deadline has passed
    error PaymentExpired();

    /// @notice Thrown when the payment has already been used (replay)
    error PaymentAlreadyUsed();

    /// @notice Thrown when the payment amount is zero
    error InvalidAmount();

    /// @notice Thrown when the recipient is the zero address
    error InvalidRecipient();

    // =========================================================================
    // Constructor
    // =========================================================================

    /// @notice Initializes the contract and computes the domain separator
    constructor() {
        DOMAIN_SEPARATOR = EIP712Helper.buildDomainSeparator(
            DOMAIN_NAME,
            DOMAIN_VERSION,
            block.chainid,
            address(this)
        );
    }

    // =========================================================================
    // External Functions
    // =========================================================================

    /// @notice Verifies an x402 payment using EIP-712 typed signature
    /// @param _payment The payment struct containing sender, recipient, amount, nonce, deadline, and signature
    /// @return True if the payment is valid and verified
    function verifyPayment(Payment calldata _payment) external returns (bool) {
        // Validate inputs
        if (_payment.amount == 0) revert InvalidAmount();
        if (_payment.recipient == address(0)) revert InvalidRecipient();
        if (block.timestamp > _payment.deadline) revert PaymentExpired();

        // Compute payment hash for replay protection
        bytes32 paymentHash = keccak256(
            abi.encode(
                _payment.sender,
                _payment.recipient,
                _payment.amount,
                _payment.nonce,
                _payment.deadline
            )
        );

        if (usedPayments[paymentHash]) revert PaymentAlreadyUsed();

        // Verify EIP-712 signature
        bytes32 structHash = keccak256(
            abi.encode(
                PAYMENT_TYPEHASH,
                _payment.sender,
                _payment.recipient,
                _payment.amount,
                _payment.nonce,
                _payment.deadline
            )
        );
        bytes32 digest = EIP712Helper.hashTypedData(DOMAIN_SEPARATOR, structHash);

        if (!EIP712Helper.verifySignature(digest, _payment.signature, _payment.sender)) {
            revert InvalidSignature();
        }

        // Mark as used and increment nonce
        usedPayments[paymentHash] = true;
        nonces[_payment.sender]++;

        emit PaymentVerified(_payment.sender, _payment.recipient, _payment.amount, _payment.nonce);
        return true;
    }

    /// @notice Gets the current nonce for a sender
    /// @param _sender The sender address
    /// @return The current nonce
    function getNonce(address _sender) external view returns (uint256) {
        return nonces[_sender];
    }

    /// @notice Checks if a payment hash has already been used
    /// @param _paymentHash The payment hash to check
    /// @return True if the payment has been used
    function isPaymentUsed(bytes32 _paymentHash) external view returns (bool) {
        return usedPayments[_paymentHash];
    }
}
