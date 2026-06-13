// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {EIP712Helper} from "./EIP712Helper.sol";

/// @title StateChannelLib
/// @notice Library for state channel operations with EIP-712 signature verification
/// @dev Provides channel state management, validation, and signature verification
library StateChannelLib {
    using EIP712Helper for bytes32;

    // =========================================================================
    // Constants
    // =========================================================================

    /// @notice EIP-712 typehash for channel state updates
    bytes32 public constant CHANNEL_STATE_TYPEHASH =
        keccak256("ChannelState(address participantA,address participantB,uint256 balanceA,uint256 balanceB,uint256 nonce,uint256 deadline)");

    // =========================================================================
    // Types
    // =========================================================================

    /// @notice Represents a state channel between two participants
    struct Channel {
        address participantA;
        address participantB;
        uint256 balanceA;
        uint256 balanceB;
        uint256 nonce;
        uint256 deadline;
        bool closed;
    }

    /// @notice Represents a state update signed by both participants
    struct StateUpdate {
        uint256 balanceA;
        uint256 balanceB;
        uint256 nonce;
        bytes signatureA;
        bytes signatureB;
    }

    // =========================================================================
    // Events
    // =========================================================================

    /// @notice Emitted when a channel is opened
    event ChannelOpened(address indexed channelId, address a, address b);

    /// @notice Emitted when a channel state is updated
    event StateUpdated(address indexed channelId, uint256 nonce);

    /// @notice Emitted when a channel is closed
    event ChannelClosed(address indexed channelId, uint256 finalBalanceA, uint256 finalBalanceB);

    // =========================================================================
    // Errors
    // =========================================================================

    /// @notice Thrown when a state update has an invalid nonce
    error InvalidNonce();

    /// @notice Thrown when the total balance in the update doesn't match the channel
    error BalanceMismatch();

    /// @notice Thrown when the channel is already closed
    error ChannelClosedError();

    /// @notice Thrown when a participant's signature is invalid
    error InvalidSignature();

    // =========================================================================
    // Functions
    // =========================================================================

    /// @notice Validates a state update against the current channel state
    /// @param _channel The current channel state
    /// @param _update The proposed state update
    /// @return True if the update is valid
    function validateStateUpdate(
        Channel memory _channel,
        StateUpdate memory _update
    ) internal pure returns (bool) {
        if (_channel.closed) revert ChannelClosedError();
        if (_update.nonce <= _channel.nonce) revert InvalidNonce();

        // Total balance must remain constant
        uint256 currentTotal = _channel.balanceA + _channel.balanceB;
        uint256 newTotal = _update.balanceA + _update.balanceB;
        if (currentTotal != newTotal) revert BalanceMismatch();

        return true;
    }

    /// @notice Verifies EIP-712 signatures from both participants on a state update
    /// @param _domainSeparator The EIP-712 domain separator
    /// @param _channel The current channel state
    /// @param _update The proposed state update with signatures
    /// @return True if both signatures are valid
    function verifyStateUpdateSignatures(
        bytes32 _domainSeparator,
        Channel memory _channel,
        StateUpdate memory _update
    ) internal view returns (bool) {
        // Build the struct hash for the state update
        bytes32 structHash = keccak256(
            abi.encode(
                CHANNEL_STATE_TYPEHASH,
                _channel.participantA,
                _channel.participantB,
                _update.balanceA,
                _update.balanceB,
                _update.nonce,
                _channel.deadline
            )
        );

        bytes32 digest = EIP712Helper.hashTypedData(_domainSeparator, structHash);

        // Verify both participants' signatures
        if (!EIP712Helper.verifySignature(digest, _update.signatureA, _channel.participantA)) {
            revert InvalidSignature();
        }

        if (!EIP712Helper.verifySignature(digest, _update.signatureB, _channel.participantB)) {
            revert InvalidSignature();
        }

        return true;
    }

    /// @notice Computes a unique channel ID from participant addresses and a salt
    /// @param _a Participant A address
    /// @param _b Participant B address
    /// @param _salt Additional entropy for uniqueness
    /// @return channelId The computed channel ID
    function computeChannelId(
        address _a,
        address _b,
        uint256 _salt
    ) internal pure returns (bytes32 channelId) {
        channelId = keccak256(abi.encodePacked(_a, _b, _salt));
    }

    /// @notice Creates a new channel struct
    /// @param _a Participant A address
    /// @param _b Participant B address
    /// @param _balanceA Initial balance for participant A
    /// @param _balanceB Initial balance for participant B
    /// @param _deadline Channel deadline timestamp
    /// @return channel The new channel struct
    function createChannel(
        address _a,
        address _b,
        uint256 _balanceA,
        uint256 _balanceB,
        uint256 _deadline
    ) internal pure returns (Channel memory channel) {
        channel = Channel({
            participantA: _a,
            participantB: _b,
            balanceA: _balanceA,
            balanceB: _balanceB,
            nonce: 0,
            deadline: _deadline,
            closed: false
        });
    }

    /// @notice Applies a validated state update to a channel
    /// @param _channel The channel to update (storage reference)
    /// @param _update The validated state update
    function applyStateUpdate(Channel storage _channel, StateUpdate memory _update) internal {
        _channel.balanceA = _update.balanceA;
        _channel.balanceB = _update.balanceB;
        _channel.nonce = _update.nonce;
    }

    /// @notice Closes a channel and returns the final balances
    /// @param _channel The channel to close (storage reference)
    /// @return finalBalanceA Final balance for participant A
    /// @return finalBalanceB Final balance for participant B
    function closeChannel(Channel storage _channel) internal returns (uint256 finalBalanceA, uint256 finalBalanceB) {
        _channel.closed = true;
        finalBalanceA = _channel.balanceA;
        finalBalanceB = _channel.balanceB;
    }
}
