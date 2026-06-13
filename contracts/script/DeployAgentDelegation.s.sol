// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script} from "forge-std/Script.sol";
import {AgentDelegation} from "../src/AgentDelegation.sol";

contract DeployAgentDelegation is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(deployerPrivateKey);
        AgentDelegation delegation = new AgentDelegation();
        vm.stopBroadcast();
    }
}
