// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {ERC721} from "openzeppelin-contracts/contracts/token/ERC721/ERC721.sol";
import {Ownable} from "openzeppelin-contracts/contracts/access/Ownable.sol";

/// @title AgentReputationSBT
/// @notice Soulbound token for agent reputation (non-transferable)
/// @dev Implements ERC-721 with transfer restrictions and reputation tracking
contract AgentReputationSBT is ERC721, Ownable {
    // =========================================================================
    // Types
    // =========================================================================

    /// @notice Represents an agent's reputation data
    struct Reputation {
        uint256 score;
        uint256 totalConsumptions;
        uint256 successfulPayments;
        uint256 lastUpdated;
    }

    // =========================================================================
    // State
    // =========================================================================

    /// @notice Mapping from token ID to reputation data
    mapping(uint256 => Reputation) public reputations;

    /// @notice Mapping from agent address to their token ID
    mapping(address => uint256) public agentTokens;

    /// @notice Next available token ID (starts at 1 to avoid 0 == unset)
    uint256 private _nextTokenId = 1;

    /// @notice Address authorized to update reputation (e.g., backend operator)
    address public reputationOracle;

    // =========================================================================
    // Events
    // =========================================================================

    /// @notice Emitted when reputation is updated
    event ReputationUpdated(uint256 indexed tokenId, uint256 newScore);

    /// @notice Emitted when a new SBT is minted
    event SBTMinted(address indexed agent, uint256 tokenId);

    /// @notice Emitted when the reputation oracle is updated
    event ReputationOracleUpdated(address indexed oldOracle, address indexed newOracle);

    // =========================================================================
    // Errors
    // =========================================================================

    /// @notice Thrown when attempting to transfer a soulbound token
    error TransferNotAllowed();

    /// @notice Thrown when an agent already has a token
    error AlreadyMinted();

    /// @notice Thrown when the caller is not the reputation oracle
    error NotReputationOracle();

    /// @notice Thrown when the token ID does not exist
    error TokenDoesNotExist();

    // =========================================================================
    // Constructor
    // =========================================================================

    /// @notice Initializes the SBT contract
    /// @param _reputationOracle Address authorized to update reputation
    constructor(address _reputationOracle) ERC721("AgentReputationSBT", "AR-SBT") Ownable(msg.sender) {
        reputationOracle = _reputationOracle;
    }

    // =========================================================================
    // External Functions
    // =========================================================================

    /// @notice Mints a new reputation SBT for an agent
    /// @param _agent The agent address to mint the token for
    /// @return tokenId The ID of the newly minted token
    function mint(address _agent) external onlyOwner returns (uint256) {
        if (agentTokens[_agent] != 0) revert AlreadyMinted();

        uint256 tokenId = _nextTokenId++;
        _safeMint(_agent, tokenId);

        agentTokens[_agent] = tokenId;

        reputations[tokenId] = Reputation({
            score: 100, // Starting score
            totalConsumptions: 0,
            successfulPayments: 0,
            lastUpdated: block.timestamp
        });

        emit SBTMinted(_agent, tokenId);
        return tokenId;
    }

    /// @notice Updates the reputation score for a token
    /// @param _tokenId The token ID to update
    /// @param _score The new reputation score
    function updateReputation(uint256 _tokenId, uint256 _score) external {
        if (msg.sender != reputationOracle && msg.sender != owner()) {
            revert NotReputationOracle();
        }
        if (_ownerOf(_tokenId) == address(0)) revert TokenDoesNotExist();

        reputations[_tokenId].score = _score;
        reputations[_tokenId].lastUpdated = block.timestamp;

        emit ReputationUpdated(_tokenId, _score);
    }

    /// @notice Records a consumption event for an agent
    /// @param _agent The agent address
    function recordConsumption(address _agent) external {
        if (msg.sender != reputationOracle && msg.sender != owner()) {
            revert NotReputationOracle();
        }

        uint256 tokenId = agentTokens[_agent];
        if (tokenId == 0) revert TokenDoesNotExist();

        reputations[tokenId].totalConsumptions++;
        reputations[tokenId].successfulPayments++;
        reputations[tokenId].lastUpdated = block.timestamp;
    }

    /// @notice Updates the reputation oracle address
    /// @param _newOracle The new oracle address
    function setReputationOracle(address _newOracle) external onlyOwner {
        address oldOracle = reputationOracle;
        reputationOracle = _newOracle;
        emit ReputationOracleUpdated(oldOracle, _newOracle);
    }

    // =========================================================================
    // View Functions
    // =========================================================================

    /// @notice Gets the reputation data for an agent
    /// @param _agent The agent address
    /// @return The reputation data
    function getAgentReputation(address _agent) external view returns (Reputation memory) {
        uint256 tokenId = agentTokens[_agent];
        if (tokenId == 0) revert TokenDoesNotExist();
        return reputations[tokenId];
    }

    /// @notice Gets the token ID for an agent
    /// @param _agent The agent address
    /// @return The token ID (0 if not minted)
    function getAgentTokenId(address _agent) external view returns (uint256) {
        return agentTokens[_agent];
    }

    // =========================================================================
    // Internal Functions
    // =========================================================================

    /// @notice Overrides ERC-721 transfer to make tokens soulbound (non-transferable)
    /// @dev Only allows minting (to != address(0)) and burning (auth != address(0))
    function _update(
        address to,
        uint256 tokenId,
        address auth
    ) internal override returns (address) {
        // Allow minting (from address(0)) and burning (to address(0))
        // but prevent transfers between non-zero addresses
        if (to != address(0) && _ownerOf(tokenId) != address(0)) {
            revert TransferNotAllowed();
        }
        return super._update(to, tokenId, auth);
    }
}
