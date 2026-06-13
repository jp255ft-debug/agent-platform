// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console} from "forge-std/Script.sol";
import {PaymentVerifier} from "../src/PaymentVerifier.sol";

/// @title DeployPaymentVerifier
/// @notice Deploy script for PaymentVerifier contract
/// @dev Usage: forge script script/DeployPaymentVerifier.s.sol --rpc-url <rpc> --broadcast
contract DeployPaymentVerifier is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(deployerPrivateKey);

        PaymentVerifier verifier = new PaymentVerifier();

        vm.stopBroadcast();

        console.log("PaymentVerifier deployed at:", address(verifier));
        console.log("Domain Separator:", vm.toString(verifier.DOMAIN_SEPARATOR()));
    }
}
