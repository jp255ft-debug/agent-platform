// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console} from "forge-std/Script.sol";
import {AgentReputationSBT} from "../src/AgentReputationSBT.sol";

/// @title DeployReputationSBT
/// @notice Deploy script for AgentReputationSBT contract
/// @dev Usage: forge script script/DeployReputationSBT.s.sol --rpc-url <rpc> --broadcast
contract DeployReputationSBT is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address reputationOracle = vm.envAddress("REPUTATION_ORACLE");
        vm.startBroadcast(deployerPrivateKey);

        AgentReputationSBT reputation = new AgentReputationSBT(reputationOracle);

        vm.stopBroadcast();

        console.log("AgentReputationSBT deployed at:", address(reputation));
        console.log("Reputation Oracle:", reputationOracle);
    }
}
