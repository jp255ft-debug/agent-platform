# Solidity Patterns — Knowledge Base

## EIP-712: Typed Structured Data Hashing and Signing

### Conceito
EIP-712 permite que usuários assinem dados estruturados (não apenas mensagens planas) off-chain, e esses dados sejam verificados on-chain.

### Implementação

#### Contrato
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract EIP712Verifier {
    bytes32 public constant DOMAIN_SEPARATOR = keccak256(abi.encode(
        keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"),
        keccak256(bytes("AgentPlatform")),
        keccak256(bytes("1")),
        block.chainid,
        address(this)
    ));

    bytes32 public constant DELEGATION_TYPEHASH = keccak256(
        "Delegation(address agent,address delegate,uint256 expiresAt)"
    );

    function verifyDelegation(
        address agent,
        address delegate,
        uint256 expiresAt,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) public view returns (address) {
        bytes32 structHash = keccak256(abi.encode(
            DELEGATION_TYPEHASH,
            agent,
            delegate,
            expiresAt
        ));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", DOMAIN_SEPARATOR, structHash));
        return ecrecover(digest, v, r, s);
    }
}
```

#### Off-chain (Python/Web3)
```python
from web3 import Web3
from eth_account.messages import encode_typed_data

domain_data = {
    "name": "AgentPlatform",
    "version": "1",
    "chainId": 84532,  # Base Sepolia
    "verifyingContract": contract_address,
}

message_types = {
    "Delegation": [
        {"name": "agent", "type": "address"},
        {"name": "delegate", "type": "address"},
        {"name": "expiresAt", "type": "uint256"},
    ]
}

message = {
    "agent": agent_address,
    "delegate": delegate_address,
    "expiresAt": expires_at,
}

signed = w3.eth.account.sign_typed_data(
    private_key, domain_data, message_types, message
)
```

---

## EIP-7702: Set EOA Account Code

### Conceito
EIP-7702 permite que Externally Owned Accounts (EOAs) definam código de contrato para si mesmas, permitindo que EOAs executem lógica de contrato durante transações.

### Implementação

#### Contrato de Delegação
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract AgentDelegation {
    mapping(address => address) public delegations;
    mapping(address => uint256) public delegationExpiry;

    event DelegationSet(address indexed agent, address indexed delegate, uint256 expiresAt);
    event DelegationRevoked(address indexed agent);

    function setDelegation(address agent, address delegate, uint256 expiresAt) external {
        require(msg.sender == agent || isAuthorized(agent), "Not authorized");
        delegations[agent] = delegate;
        delegationExpiry[agent] = expiresAt;
        emit DelegationSet(agent, delegate, expiresAt);
    }

    function revokeDelegation(address agent) external {
        require(msg.sender == agent || isAuthorized(agent), "Not authorized");
        delete delegations[agent];
        delete delegationExpiry[agent];
        emit DelegationRevoked(agent);
    }

    function getDelegation(address agent) external view returns (address) {
        if (block.timestamp > delegationExpiry[agent]) return address(0);
        return delegations[agent];
    }

    function isDelegationActive(address agent) external view returns (bool) {
        return delegations[agent] != address(0) && block.timestamp <= delegationExpiry[agent];
    }
}
```

---

## Security Patterns

### Checks-Effects-Interactions
```solidity
function withdraw(uint256 amount) external nonReentrant {
    // CHECKS
    require(balances[msg.sender] >= amount, "Insufficient balance");

    // EFFECTS
    balances[msg.sender] -= amount;

    // INTERACTIONS
    (bool success, ) = msg.sender.call{value: amount}("");
    require(success, "Transfer failed");
}
```

### ReentrancyGuard
```solidity
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract SecureContract is ReentrancyGuard {
    function vulnerable(bytes calldata data) external nonReentrant {
        // ...
    }
}
```

### Access Control
```solidity
import "@openzeppelin/contracts/access/Ownable.sol";

contract MyContract is Ownable {
    function onlyOwner() external onlyOwner {
        // ...
    }
}
```

---

## State Channels

### Conceito
State channels permitem que múltiplas transações ocorram off-chain, com apenas o estado final sendo submetido on-chain.

### Implementação

#### Estado do Canal
```solidity
struct ChannelState {
    address agent;
    address platform;
    uint256 balanceAgent;
    uint256 balancePlatform;
    uint256 nonce;
    uint256 deadline;
}
```

#### Verificação de Assinatura
```solidity
function verifyState(ChannelState memory state, bytes memory signature) internal view returns (bool) {
    bytes32 hash = keccak256(abi.encode(
        CHANNEL_TYPEHASH,
        state.agent,
        state.platform,
        state.balanceAgent,
        state.balancePlatform,
        state.nonce,
        state.deadline
    ));
    bytes32 digest = keccak256(abi.encodePacked("\x19\x01", domainSeparator, hash));
    address signer = ecrecover(digest, signature);
    return signer == state.agent || signer == state.platform;
}
```

---

## Gas Optimization Patterns

1. **Usar `uint256`**: EVM opera em palavras de 256 bits; tipos menores custam mais gas
2. **Packed structs**: Usar `uint128` + `uint128` em vez de `uint256` + `uint256` quando possível
3. **Short-circuiting**: Colocar condições mais baratas primeiro em `require`
4. **Events em vez de storage**: Para dados históricos, usar eventos (mais baratos)
5. **Immutable variables**: Para constantes que não mudam após deploy
6. **Custom errors**: Em vez de `require(false, "string")`, usar `error MeuErro()`
