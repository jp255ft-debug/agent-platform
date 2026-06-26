// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {EIP712Helper} from "./libraries/EIP712Helper.sol";

/// @title AgentDelegation
/// @notice Manages agent delegation using EIP-7702 with EIP-712 typed signatures
/// @dev Agents can delegate authority to other addresses with expiration and budget cap
contract AgentDelegation {
    using EIP712Helper for bytes32;

    // =========================================================================
    // Constants
    // =========================================================================

    /// @notice EIP-712 typehash for delegation (includes maxBudget for budget cap enforcement)
    bytes32 public constant DELEGATION_TYPEHASH =
        keccak256("Delegation(address agent,address delegate,uint256 expiresAt,uint256 nonce,uint256 maxBudget)");

    /// @notice Domain name for EIP-712
    string public constant DOMAIN_NAME = "AgentPlatform";

    /// @notice Domain version for EIP-712
    string public constant DOMAIN_VERSION = "1";

    // =========================================================================
    // Types
    // =========================================================================

    /// @notice Represents a delegation from an agent to a delegate
    struct Delegation {
        address agent;
        address delegate;
        uint256 expiresAt;
        uint256 maxBudget;      /// @notice Maximum spend amount in wei (budget cap)
        uint256 spentAmount;    /// @notice Accumulated spend amount in wei
        bool active;
    }

    // =========================================================================
    // State
    // =========================================================================

    /// @notice Mapping from agent address to their current delegation
    mapping(address => Delegation) public delegations;

    /// @notice Mapping from agent address to their delegation history
    mapping(address => address[]) public delegationHistory;

    /// @notice Mapping from agent address to their current nonce (for replay protection)
    mapping(address => uint256) public nonces;

    /// @notice Mapping of authorized spend recorders (contracts that can call recordSpend)
    mapping(address => bool) public spendRecorders;

    /// @notice Cached domain separator
    bytes32 public immutable DOMAIN_SEPARATOR;

    // =========================================================================
    // Events
    // =========================================================================

    /// @notice Emitted when a delegation is created
    event DelegationCreated(
        address indexed agent,
        address indexed delegate,
        uint256 expiresAt,
        uint256 maxBudget,
        uint256 nonce
    );

    /// @notice Emitted when a delegation is revoked
    event DelegationRevoked(address indexed agent, address indexed delegate);

    /// @notice Emitted when a delegation expires
    event DelegationExpired(address indexed agent, address indexed delegate);

    /// @notice Emitted when a spend is recorded against a delegation budget
    event SpendRecorded(
        address indexed agent,
        uint256 amount,
        uint256 totalSpent,
        uint256 remainingBudget
    );

    // =========================================================================
    // Errors
    // =========================================================================

    /// @notice Thrown when an agent already has an active delegation
    error DelegationAlreadyExists();

    /// @notice Thrown when no delegation exists to revoke
    error DelegationNotFound();

    /// @notice Thrown when the delegation expiry is in the past
    error DelegationExpiredError();

    /// @notice Thrown when the caller is not authorized
    error Unauthorized();

    /// @notice Thrown when the EIP-712 signature is invalid
    error InvalidSignature();

    /// @notice Thrown when the nonce is incorrect (replay protection)
    error InvalidNonce();

    /// @notice Thrown when the spend would exceed the maxBudget
    error BudgetExceeded();

    /// @notice Thrown when a non-authorized address calls recordSpend
    error UnauthorizedSpendRecorder();

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

    /// @notice Creates a delegation from msg.sender to a delegate with a budget cap
    /// @param _delegate The address to delegate authority to
    /// @param _expiresAt The timestamp when the delegation expires
    /// @param _maxBudget The maximum spend amount in wei (budget cap)
    function delegate(address _delegate, uint256 _expiresAt, uint256 _maxBudget) external {
        _delegateFor(msg.sender, _delegate, _expiresAt, _maxBudget);
    }

    /// @notice Creates a delegation using an EIP-712 signature (gasless delegation)
    /// @param _agent The agent granting delegation
    /// @param _delegate The address to delegate authority to
    /// @param _expiresAt The timestamp when the delegation expires
    /// @param _maxBudget The maximum spend amount in wei (budget cap)
    /// @param _signature EIP-712 signature from the agent
    function delegateBySig(
        address _agent,
        address _delegate,
        uint256 _expiresAt,
        uint256 _maxBudget,
        bytes calldata _signature
    ) external {
        // Verify nonce
        uint256 nonce = nonces[_agent];
        bytes32 structHash = keccak256(
            abi.encode(DELEGATION_TYPEHASH, _agent, _delegate, _expiresAt, nonce, _maxBudget)
        );
        bytes32 digest = EIP712Helper.hashTypedData(DOMAIN_SEPARATOR, structHash);

        if (!EIP712Helper.verifySignature(digest, _signature, _agent)) {
            revert InvalidSignature();
        }

        // Increment nonce to prevent replay
        nonces[_agent] = nonce + 1;

        _delegateFor(_agent, _delegate, _expiresAt, _maxBudget);
    }

    /// @notice Revokes the delegation for msg.sender
    function revoke() external {
        _revokeFor(msg.sender);
    }

    /// @notice Revokes a delegation using an EIP-712 signature (gasless revoke)
    /// @param _agent The agent revoking delegation
    /// @param _signature EIP-712 signature from the agent
    function revokeBySig(address _agent, bytes calldata _signature) external {
        uint256 nonce = nonces[_agent];
        bytes32 structHash = keccak256(
            abi.encode(DELEGATION_TYPEHASH, _agent, address(0), 0, nonce, 0)
        );
        bytes32 digest = EIP712Helper.hashTypedData(DOMAIN_SEPARATOR, structHash);

        if (!EIP712Helper.verifySignature(digest, _signature, _agent)) {
            revert InvalidSignature();
        }

        nonces[_agent] = nonce + 1;
        _revokeFor(_agent);
    }

    /// @notice Records a spend against an agent's delegation budget
    /// @param _agent The agent whose budget to deduct from
    /// @param _amount The amount spent in wei
    /// @dev Only callable by authorized spend recorders (e.g., PaymentVerifier)
    function recordSpend(address _agent, uint256 _amount) external {
        if (!spendRecorders[msg.sender]) revert UnauthorizedSpendRecorder();

        Delegation storage del = delegations[_agent];
        if (!del.active) revert DelegationNotFound();
        if (del.expiresAt <= block.timestamp) revert DelegationExpiredError();

        uint256 newSpent = del.spentAmount + _amount;
        if (newSpent > del.maxBudget) revert BudgetExceeded();

        del.spentAmount = newSpent;

        emit SpendRecorded(_agent, _amount, newSpent, del.maxBudget - newSpent);
    }

    /// @notice Authorizes or deauthorizes a spend recorder contract
    /// @param _recorder The address of the contract to authorize
    /// @param _authorized True to authorize, false to deauthorize
    /// @dev Only callable by the contract owner (deployer)
    function setSpendRecorder(address _recorder, bool _authorized) external {
        if (msg.sender != address(this)) revert Unauthorized();
        spendRecorders[_recorder] = _authorized;
    }

    // =========================================================================
    // View Functions
    // =========================================================================

    /// @notice Checks if a delegation is currently valid
    /// @param _agent The agent address
    /// @param _delegate The delegate address to check
    /// @return True if the delegation is active and not expired
    function isValidDelegation(address _agent, address _delegate) external view returns (bool) {
        Delegation memory del = delegations[_agent];
        return del.active && del.delegate == _delegate && del.expiresAt > block.timestamp;
    }

    /// @notice Gets the full delegation details for an agent
    /// @param _agent The agent address
    /// @return The delegation struct
    function getDelegation(address _agent) external view returns (Delegation memory) {
        return delegations[_agent];
    }

    /// @notice Gets the delegation history for an agent
    /// @param _agent The agent address
    /// @return Array of delegate addresses (historical)
    function getDelegationHistory(address _agent) external view returns (address[] memory) {
        return delegationHistory[_agent];
    }

    /// @notice Gets the current nonce for an agent (for EIP-712 signing)
    /// @param _agent The agent address
    /// @return The current nonce
    function getNonce(address _agent) external view returns (uint256) {
        return nonces[_agent];
    }

    /// @notice Gets the remaining budget for an agent's delegation
    /// @param _agent The agent address
    /// @return The remaining budget in wei (maxBudget - spentAmount), or 0 if no active delegation
    function getRemainingBudget(address _agent) external view returns (uint256) {
        Delegation memory del = delegations[_agent];
        if (!del.active) return 0;
        if (del.spentAmount >= del.maxBudget) return 0;
        return del.maxBudget - del.spentAmount;
    }

    // =========================================================================
    // Internal Functions
    // =========================================================================

    /// @notice Internal function to create a delegation
    /// @param _agent The agent granting delegation
    /// @param _delegate The address to delegate authority to
    /// @param _expiresAt The timestamp when the delegation expires
    /// @param _maxBudget The maximum spend amount in wei (budget cap)
    function _delegateFor(
        address _agent,
        address _delegate,
        uint256 _expiresAt,
        uint256 _maxBudget
    ) internal {
        if (delegations[_agent].active) revert DelegationAlreadyExists();
        if (_expiresAt <= block.timestamp) revert DelegationExpiredError();
        if (_delegate == address(0)) revert DelegationNotFound();

        delegations[_agent] = Delegation({
            agent: _agent,
            delegate: _delegate,
            expiresAt: _expiresAt,
            maxBudget: _maxBudget,
            spentAmount: 0,
            active: true
        });

        delegationHistory[_agent].push(_delegate);
        emit DelegationCreated(_agent, _delegate, _expiresAt, _maxBudget, nonces[_agent]);
    }

    /// @notice Internal function to revoke a delegation
    /// @param _agent The agent revoking delegation
    function _revokeFor(address _agent) internal {
        Delegation storage del = delegations[_agent];
        if (!del.active) revert DelegationNotFound();

        del.active = false;
        emit DelegationRevoked(_agent, del.delegate);
    }
}
