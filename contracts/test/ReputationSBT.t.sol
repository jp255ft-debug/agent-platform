// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test} from "forge-std/Test.sol";
import {AgentReputationSBT} from "../src/AgentReputationSBT.sol";

/// @title ReputationSBTTest
/// @notice Comprehensive tests for AgentReputationSBT contract
contract ReputationSBTTest is Test {
    AgentReputationSBT public reputation;

    address public owner;
    address public oracle;
    address public agent = address(0x1);
    address public unauthorized = address(0x2);

    function setUp() public {
        owner = address(this);
        oracle = address(0xCAFE);
        reputation = new AgentReputationSBT(oracle);
    }

    // =========================================================================
    // Constructor
    // =========================================================================

    function test_Constructor() public view {
        assertEq(reputation.name(), "AgentReputationSBT");
        assertEq(reputation.symbol(), "AR-SBT");
        assertEq(reputation.reputationOracle(), oracle);
        assertEq(reputation.owner(), owner);
    }

    // =========================================================================
    // mint()
    // =========================================================================

    function test_Mint() public {
        uint256 tokenId = reputation.mint(agent);

        assertEq(reputation.ownerOf(tokenId), agent);
        assertEq(reputation.balanceOf(agent), 1);
        assertEq(reputation.getAgentTokenId(agent), tokenId);
        assertTrue(tokenId > 0);
    }

    function test_Mint_EmitsEvent() public {
        vm.expectEmit(true, true, false, true);
        emit AgentReputationSBT.SBTMinted(agent, 1);
        reputation.mint(agent);
    }

    function test_Mint_InitialReputation() public {
        uint256 tokenId = reputation.mint(agent);

        (
            uint256 score,
            uint256 totalConsumptions,
            uint256 successfulPayments,
            uint256 lastUpdated
        ) = reputation.reputations(tokenId);

        assertEq(score, 100);
        assertEq(totalConsumptions, 0);
        assertEq(successfulPayments, 0);
        assertEq(lastUpdated, block.timestamp);
    }

    function test_RevertWhen_MintByNonOwner() public {
        vm.prank(unauthorized);
        vm.expectRevert();
        reputation.mint(agent);
    }

    function test_RevertWhen_MintTwice() public {
        reputation.mint(agent);
        vm.expectRevert(AgentReputationSBT.AlreadyMinted.selector);
        reputation.mint(agent);
    }

    // =========================================================================
    // updateReputation()
    // =========================================================================

    function test_UpdateReputation_ByOracle() public {
        uint256 tokenId = reputation.mint(agent);

        vm.prank(oracle);
        reputation.updateReputation(tokenId, 200);

        (uint256 score,,,) = reputation.reputations(tokenId);
        assertEq(score, 200);
    }

    function test_UpdateReputation_ByOwner() public {
        uint256 tokenId = reputation.mint(agent);

        reputation.updateReputation(tokenId, 200);

        (uint256 score,,,) = reputation.reputations(tokenId);
        assertEq(score, 200);
    }

    function test_UpdateReputation_EmitsEvent() public {
        uint256 tokenId = reputation.mint(agent);

        vm.prank(oracle);
        vm.expectEmit(true, true, false, true);
        emit AgentReputationSBT.ReputationUpdated(tokenId, 200);
        reputation.updateReputation(tokenId, 200);
    }

    function test_RevertWhen_UpdateReputationByUnauthorized() public {
        uint256 tokenId = reputation.mint(agent);

        vm.prank(unauthorized);
        vm.expectRevert(AgentReputationSBT.NotReputationOracle.selector);
        reputation.updateReputation(tokenId, 200);
    }

    function test_RevertWhen_UpdateReputationNonExistentToken() public {
        vm.expectRevert(AgentReputationSBT.TokenDoesNotExist.selector);
        reputation.updateReputation(999, 200);
    }

    // =========================================================================
    // recordConsumption()
    // =========================================================================

    function test_RecordConsumption() public {
        uint256 tokenId = reputation.mint(agent);

        vm.prank(oracle);
        reputation.recordConsumption(agent);

        (uint256 score, uint256 totalConsumptions, uint256 successfulPayments,) =
            reputation.reputations(tokenId);

        assertEq(totalConsumptions, 1);
        assertEq(successfulPayments, 1);
    }

    function test_RecordConsumption_Multiple() public {
        uint256 tokenId = reputation.mint(agent);

        vm.prank(oracle);
        reputation.recordConsumption(agent);

        vm.prank(oracle);
        reputation.recordConsumption(agent);

        (, uint256 totalConsumptions, uint256 successfulPayments,) =
            reputation.reputations(tokenId);

        assertEq(totalConsumptions, 2);
        assertEq(successfulPayments, 2);
    }

    function test_RevertWhen_RecordConsumptionByUnauthorized() public {
        reputation.mint(agent);

        vm.prank(unauthorized);
        vm.expectRevert(AgentReputationSBT.NotReputationOracle.selector);
        reputation.recordConsumption(agent);
    }

    function test_RevertWhen_RecordConsumptionNonExistentAgent() public {
        vm.prank(oracle);
        vm.expectRevert(AgentReputationSBT.TokenDoesNotExist.selector);
        reputation.recordConsumption(address(0xDEAD));
    }

    // =========================================================================
    // setReputationOracle()
    // =========================================================================

    function test_SetReputationOracle() public {
        address newOracle = address(0xBEEF);
        reputation.setReputationOracle(newOracle);
        assertEq(reputation.reputationOracle(), newOracle);
    }

    function test_SetReputationOracle_EmitsEvent() public {
        address newOracle = address(0xBEEF);
        vm.expectEmit(true, true, false, true);
        emit AgentReputationSBT.ReputationOracleUpdated(oracle, newOracle);
        reputation.setReputationOracle(newOracle);
    }

    function test_RevertWhen_SetReputationOracleByNonOwner() public {
        vm.prank(unauthorized);
        vm.expectRevert();
        reputation.setReputationOracle(address(0xBEEF));
    }

    // =========================================================================
    // getAgentReputation()
    // =========================================================================

    function test_GetAgentReputation() public {
        reputation.mint(agent);

        AgentReputationSBT.Reputation memory rep = reputation.getAgentReputation(agent);

        assertEq(rep.score, 100);
        assertEq(rep.totalConsumptions, 0);
        assertEq(rep.successfulPayments, 0);
        assertEq(rep.lastUpdated, block.timestamp);
    }

    function test_RevertWhen_GetAgentReputationNonExistent() public {
        vm.expectRevert(AgentReputationSBT.TokenDoesNotExist.selector);
        reputation.getAgentReputation(address(0xDEAD));
    }

    // =========================================================================
    // Soulbound (non-transferable)
    // =========================================================================

    function test_RevertWhen_Transfer() public {
        uint256 tokenId = reputation.mint(agent);

        vm.prank(agent);
        vm.expectRevert(AgentReputationSBT.TransferNotAllowed.selector);
        reputation.transferFrom(agent, unauthorized, tokenId);
    }

    // =========================================================================
    // Fuzz testing
    // =========================================================================

    function testFuzz_MintAndUpdateReputation(uint256 _score) public {
        vm.assume(_score > 0 && _score <= 1000);

        uint256 tokenId = reputation.mint(agent);

        vm.prank(oracle);
        reputation.updateReputation(tokenId, _score);

        (uint256 score,,,) = reputation.reputations(tokenId);
        assertEq(score, _score);
    }
}
