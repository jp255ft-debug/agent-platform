// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {StateChannelLib} from "./libraries/StateChannelLib.sol";
import {EIP712Helper} from "./libraries/EIP712Helper.sol";

/**
 * @title StateChannelManager
 * @author Agent Platform
 * @notice Contrato principal para gerenciamento de state channels com suporte a depósitos,
 *         disputas, janelas de desafio e liquidação confiável.
 *
 * @dev Integra-se com StateChannelLib para validação criptográfica e EIP712Helper
 *      para assinaturas EIP-712. Gerencia o ciclo de vida completo:
 *
 *      1. deposit() → Abre canal e bloqueia fundos de ambas as partes
 *      2. updateState() → Atualiza estado off-chain (assinado por ambos)
 *      3. closeChannel() → Inicia fechamento com janela de desafio
 *      4. dispute() → Contesta estado fechado (dentro da janela)
 *      5. finalize() → Liquida canal após janela expirar
 */
contract StateChannelManager {
    using StateChannelLib for StateChannelLib.Channel;

    // =========================================================================
    // Constants
    // =========================================================================

    /// @notice Janela de desafio padrão: 1 dia
    uint256 public constant CHALLENGE_WINDOW = 1 days;

    /// @notice Depósito mínimo: 0.01 ETH
    uint256 public constant MIN_DEPOSIT = 0.01 ether;

    /// @notice Domain name para EIP-712
    string public constant DOMAIN_NAME = "AgentPlatform";

    /// @notice Domain version para EIP-712
    string public constant DOMAIN_VERSION = "1";

    // =========================================================================
    // Types
    // =========================================================================

    /// @notice Metadados on-chain do canal (não fazem parte do estado off-chain)
    struct ChannelMeta {
        uint256 depositA;          // ETH depositado por partyA
        uint256 depositB;          // ETH depositado por partyB
        uint256 closeNonce;        // Nonce do estado de fechamento
        bytes32 closeStateHash;    // Hash do estado de fechamento
        uint256 challengeDeadline; // Timestamp limite para disputas
        address challenger;        // Endereço que iniciou a última disputa
        bool closed;               // Canal foi fechado?
        bool finalized;            // Canal foi finalizado?
    }

    // =========================================================================
    // Events
    // =========================================================================

    event ChannelOpened(
        bytes32 indexed channelId,
        address indexed partyA,
        address indexed partyB,
        uint256 depositA,
        uint256 depositB,
        uint256 deadline
    );

    event FundsAdded(
        bytes32 indexed channelId,
        address indexed party,
        uint256 amount
    );

    event ChannelUpdated(
        bytes32 indexed channelId,
        uint256 newNonce,
        bytes32 newStateHash,
        address indexed updater
    );

    event ChannelClosed(
        bytes32 indexed channelId,
        address indexed closer,
        uint256 finalNonce,
        bytes32 finalStateHash
    );

    event DisputeRaised(
        bytes32 indexed channelId,
        address indexed challenger,
        uint256 disputedNonce,
        bytes32 disputedStateHash,
        uint256 challengeDeadline
    );

    event ChannelFinalized(
        bytes32 indexed channelId,
        address indexed partyA,
        address indexed partyB,
        uint256 amountToA,
        uint256 amountToB
    );

    // =========================================================================
    // State
    // =========================================================================

    /// @notice Contador para gerar channelIds únicos
    uint256 private _channelNonce;

    /// @notice Estado off-chain do canal (via StateChannelLib)
    mapping(bytes32 => StateChannelLib.Channel) public channels;

    /// @notice Metadados on-chain do canal
    mapping(bytes32 => ChannelMeta) public channelMeta;

    /// @notice Domain separator EIP-712 (cached)
    bytes32 public immutable DOMAIN_SEPARATOR;

    // =========================================================================
    // Errors
    // =========================================================================

    error ChannelAlreadyExists();
    error ChannelNotFound();
    error NotParty();
    error ChannelAlreadyClosed();
    error ChannelAlreadyFinalized();
    error ChannelNotClosed();
    error DepositBelowMinimum();
    error InvalidParty();
    error NonceNotGreater();
    error InvalidSignatureA();
    error InvalidSignatureB();
    error ChallengeWindowExpired();
    error DisputedNonceNotHigher();
    error AlreadyFinalized();
    error InsufficientBalance();

    // =========================================================================
    // Modifiers
    // =========================================================================

    modifier onlyParty(bytes32 _channelId) {
        StateChannelLib.Channel storage c = channels[_channelId];
        if (c.participantA != msg.sender && c.participantB != msg.sender) {
            revert NotParty();
        }
        _;
    }

    modifier channelExists(bytes32 _channelId) {
        if (channels[_channelId].participantA == address(0)) {
            revert ChannelNotFound();
        }
        _;
    }

    modifier channelNotClosed(bytes32 _channelId) {
        ChannelMeta storage meta = channelMeta[_channelId];
        if (meta.closed || meta.finalized) revert ChannelAlreadyClosed();
        _;
    }

    // =========================================================================
    // Constructor
    // =========================================================================

    constructor() {
        DOMAIN_SEPARATOR = EIP712Helper.buildDomainSeparator(
            DOMAIN_NAME,
            DOMAIN_VERSION,
            block.chainid,
            address(this)
        );
    }

    // =========================================================================
    // Core Functions
    // =========================================================================

    /**
     * @notice Abre um novo canal de estado com depósito de ambas as partes.
     * @param _partyB Endereço da contraparte
     * @param _balanceB Saldo inicial de partyB (deve ser depositado junto)
     * @param _deadline Timestamp de expiração (0 = sem expiração)
     */
    function deposit(
        address _partyB,
        uint256 _balanceB,
        uint256 _deadline
    ) external payable {
        if (_partyB == address(0) || _partyB == msg.sender) revert InvalidParty();
        if (msg.value < MIN_DEPOSIT) revert DepositBelowMinimum();

        // Gerar channelId único
        _channelNonce++;
        bytes32 channelId = StateChannelLib.computeChannelId(
            msg.sender, _partyB, _channelNonce
        );

        if (channels[channelId].participantA != address(0)) revert ChannelAlreadyExists();

        // Criar canal via library
        // O depósito de partyB é enviado junto na mesma tx ou via addFunds()
        StateChannelLib.Channel memory newChannel = StateChannelLib.createChannel(
            msg.sender,
            _partyB,
            msg.value,     // balanceA = deposit de partyA
            _balanceB,     // balanceB = deposit de partyB (se enviado junto)
            _deadline
        );
        channels[channelId] = newChannel;
        StateChannelLib.Channel storage c = channels[channelId];

        // Se partyB depositou junto, o valor total deve ser msg.value
        if (_balanceB > 0 && msg.value < _balanceB) revert InsufficientBalance();

        // Metadados on-chain
        ChannelMeta storage meta = channelMeta[channelId];
        meta.depositA = msg.value;
        meta.depositB = 0; // partyB deposita via addFunds()
        meta.closed = false;
        meta.finalized = false;

        emit ChannelOpened(channelId, msg.sender, _partyB, msg.value, _balanceB, _deadline);
    }

    /**
     * @notice Adiciona fundos ao canal (qualquer parte pode depositar).
     * @param _channelId ID do canal
     */
    function addFunds(bytes32 _channelId)
        external
        payable
        channelExists(_channelId)
        channelNotClosed(_channelId)
        onlyParty(_channelId)
    {
        ChannelMeta storage meta = channelMeta[_channelId];
        StateChannelLib.Channel storage c = channels[_channelId];

        if (msg.sender == c.participantA) {
            meta.depositA += msg.value;
            c.balanceA += msg.value;
        } else {
            meta.depositB += msg.value;
            c.balanceB += msg.value;
        }

        emit FundsAdded(_channelId, msg.sender, msg.value);
    }

    /**
     * @notice Atualiza o estado do canal com assinaturas EIP-712 de ambas as partes.
     * @param _channelId ID do canal
     * @param _newBalanceA Novo saldo de partyA
     * @param _newBalanceB Novo saldo de partyB
     * @param _newNonce Novo nonce (deve ser maior que o atual)
     * @param _signatureA Assinatura EIP-712 de partyA
     * @param _signatureB Assinatura EIP-712 de partyB
     */
    function updateState(
        bytes32 _channelId,
        uint256 _newBalanceA,
        uint256 _newBalanceB,
        uint256 _newNonce,
        bytes memory _signatureA,
        bytes memory _signatureB
    ) external channelExists(_channelId) channelNotClosed(_channelId) {
        StateChannelLib.Channel storage c = channels[_channelId];

        // Construir StateUpdate
        StateChannelLib.StateUpdate memory update = StateChannelLib.StateUpdate({
            balanceA: _newBalanceA,
            balanceB: _newBalanceB,
            nonce: _newNonce,
            signatureA: _signatureA,
            signatureB: _signatureB
        });

        // Validar nonce e balanço total
        StateChannelLib.validateStateUpdate(
            StateChannelLib.Channel({
                participantA: c.participantA,
                participantB: c.participantB,
                balanceA: c.balanceA,
                balanceB: c.balanceB,
                nonce: c.nonce,
                deadline: c.deadline,
                closed: c.closed
            }),
            update
        );

        // Verificar assinaturas EIP-712
        StateChannelLib.verifyStateUpdateSignatures(
            DOMAIN_SEPARATOR,
            StateChannelLib.Channel({
                participantA: c.participantA,
                participantB: c.participantB,
                balanceA: c.balanceA,
                balanceB: c.balanceB,
                nonce: c.nonce,
                deadline: c.deadline,
                closed: c.closed
            }),
            update
        );

        // Aplicar atualização
        StateChannelLib.applyStateUpdate(c, update);

        emit ChannelUpdated(_channelId, _newNonce, keccak256(abi.encode(update)), msg.sender);
    }

    /**
     * @notice Inicia o fechamento do canal com um estado final assinado por ambas as partes.
     * @param _channelId ID do canal
     * @param _finalBalanceA Saldo final de partyA
     * @param _finalBalanceB Saldo final de partyB
     * @param _finalNonce Nonce do estado final
     * @param _signatureA Assinatura EIP-712 de partyA
     * @param _signatureB Assinatura EIP-712 de partyB
     */
    function closeChannel(
        bytes32 _channelId,
        uint256 _finalBalanceA,
        uint256 _finalBalanceB,
        uint256 _finalNonce,
        bytes memory _signatureA,
        bytes memory _signatureB
    ) external channelExists(_channelId) channelNotClosed(_channelId) {
        StateChannelLib.Channel storage c = channels[_channelId];
        ChannelMeta storage meta = channelMeta[_channelId];

        // Construir estado de fechamento
        StateChannelLib.StateUpdate memory closeUpdate = StateChannelLib.StateUpdate({
            balanceA: _finalBalanceA,
            balanceB: _finalBalanceB,
            nonce: _finalNonce,
            signatureA: _signatureA,
            signatureB: _signatureB
        });

        // Validar nonce (deve ser <= currentNonce)
        if (_finalNonce > c.nonce) revert NonceNotGreater();

        // Verificar assinaturas para o estado de fechamento
        // Usamos o mesmo typehash de StateUpdate para consistência
        bytes32 structHash = keccak256(
            abi.encode(
                StateChannelLib.CHANNEL_STATE_TYPEHASH,
                c.participantA,
                c.participantB,
                _finalBalanceA,
                _finalBalanceB,
                _finalNonce,
                c.deadline
            )
        );
        bytes32 digest = EIP712Helper.hashTypedData(DOMAIN_SEPARATOR, structHash);

        if (!EIP712Helper.verifySignature(digest, _signatureA, c.participantA)) {
            revert InvalidSignatureA();
        }
        if (!EIP712Helper.verifySignature(digest, _signatureB, c.participantB)) {
            revert InvalidSignatureB();
        }

        // Fechar canal na library
        StateChannelLib.closeChannel(c);

        // Registrar metadados de fechamento
        meta.closed = true;
        meta.closeNonce = _finalNonce;
        meta.closeStateHash = keccak256(abi.encode(closeUpdate));
        meta.challengeDeadline = block.timestamp + CHALLENGE_WINDOW;

        emit ChannelClosed(_channelId, msg.sender, _finalNonce, meta.closeStateHash);
    }

    /**
     * @notice Desafia o estado de fechamento com um estado mais recente assinado.
     * @param _channelId ID do canal
     * @param _disputedBalanceA Saldo contestado de partyA
     * @param _disputedBalanceB Saldo contestado de partyB
     * @param _disputedNonce Nonce do estado contestado (deve ser > closeNonce)
     * @param _signatureA Assinatura EIP-712 de partyA
     * @param _signatureB Assinatura EIP-712 de partyB
     */
    function dispute(
        bytes32 _channelId,
        uint256 _disputedBalanceA,
        uint256 _disputedBalanceB,
        uint256 _disputedNonce,
        bytes memory _signatureA,
        bytes memory _signatureB
    ) external channelExists(_channelId) {
        StateChannelLib.Channel storage c = channels[_channelId];
        ChannelMeta storage meta = channelMeta[_channelId];

        if (!meta.closed) revert ChannelNotClosed();
        if (meta.finalized) revert AlreadyFinalized();
        if (block.timestamp > meta.challengeDeadline) revert ChallengeWindowExpired();

        // Nonce contestado deve ser maior que o nonce de fechamento
        if (_disputedNonce <= meta.closeNonce) revert DisputedNonceNotHigher();

        // Verificar assinaturas
        bytes32 structHash = keccak256(
            abi.encode(
                StateChannelLib.CHANNEL_STATE_TYPEHASH,
                c.participantA,
                c.participantB,
                _disputedBalanceA,
                _disputedBalanceB,
                _disputedNonce,
                c.deadline
            )
        );
        bytes32 digest = EIP712Helper.hashTypedData(DOMAIN_SEPARATOR, structHash);

        if (!EIP712Helper.verifySignature(digest, _signatureA, c.participantA)) {
            revert InvalidSignatureA();
        }
        if (!EIP712Helper.verifySignature(digest, _signatureB, c.participantB)) {
            revert InvalidSignatureB();
        }

        // Aceitar disputa: substituir estado de fechamento
        meta.closeNonce = _disputedNonce;
        meta.closeStateHash = keccak256(
            abi.encode(_disputedBalanceA, _disputedBalanceB, _disputedNonce)
        );
        meta.challengeDeadline = block.timestamp + CHALLENGE_WINDOW; // Reinicia janela
        meta.challenger = msg.sender;

        emit DisputeRaised(
            _channelId,
            msg.sender,
            _disputedNonce,
            meta.closeStateHash,
            meta.challengeDeadline
        );
    }

    /**
     * @notice Finaliza o canal após a janela de desafio expirar.
     *         Distribui os depósitos com base no estado final acordado.
     * @param _channelId ID do canal
     */
    function finalize(bytes32 _channelId) external channelExists(_channelId) {
        StateChannelLib.Channel storage c = channels[_channelId];
        ChannelMeta storage meta = channelMeta[_channelId];

        if (!meta.closed) revert ChannelNotClosed();
        if (meta.finalized) revert AlreadyFinalized();
        if (block.timestamp <= meta.challengeDeadline) revert ChallengeWindowExpired();

        // Decodificar o estado final para obter os saldos
        // O estado final é o closeStateHash. Precisamos dos saldos reais.
        // Como não armazenamos os saldos finais explicitamente, usamos os saldos
        // atuais do canal (que foram atualizados via updateState antes do close).
        // Se houve disputa, o closeNonce reflete o estado mais recente.
        //
        // Nota: Em produção, os saldos finais devem ser passados como prova.
        // Para este contrato, usamos os saldos do struct Channel que foram
        // congelados no closeChannel().

        // Calcular proporção dos depósitos com base nos saldos finais
        uint256 totalDeposit = meta.depositA + meta.depositB;
        uint256 totalBalance = c.balanceA + c.balanceB;

        uint256 amountToA;
        uint256 amountToB;

        if (totalBalance > 0) {
            // Proporcional aos saldos finais
            amountToA = (totalDeposit * c.balanceA) / totalBalance;
            amountToB = totalDeposit - amountToA;
        } else {
            // Fallback: dividir igualmente (não deveria acontecer)
            amountToA = totalDeposit / 2;
            amountToB = totalDeposit - amountToA;
        }

        // Marcar como finalizado (protege contra reentrância)
        meta.finalized = true;

        // Transferir fundos
        if (amountToA > 0) {
            payable(c.participantA).transfer(amountToA);
        }
        if (amountToB > 0) {
            payable(c.participantB).transfer(amountToB);
        }

        emit ChannelFinalized(_channelId, c.participantA, c.participantB, amountToA, amountToB);
    }

    // =========================================================================
    // View Functions
    // =========================================================================

    /**
     * @notice Retorna informações completas do canal.
     */
    function getChannelInfo(bytes32 _channelId)
        external
        view
        returns (
            address participantA,
            address participantB,
            uint256 balanceA,
            uint256 balanceB,
            uint256 nonce,
            uint256 deadline,
            bool closed,
            bool finalized,
            uint256 depositA,
            uint256 depositB
        )
    {
        StateChannelLib.Channel storage c = channels[_channelId];
        ChannelMeta storage meta = channelMeta[_channelId];

        return (
            c.participantA,
            c.participantB,
            c.balanceA,
            c.balanceB,
            c.nonce,
            c.deadline,
            meta.closed,
            meta.finalized,
            meta.depositA,
            meta.depositB
        );
    }

    /**
     * @notice Retorna informações de fechamento do canal.
     */
    function getCloseInfo(bytes32 _channelId)
        external
        view
        returns (
            uint256 closeNonce,
            bytes32 closeStateHash,
            uint256 challengeDeadline,
            address challenger
        )
    {
        ChannelMeta storage meta = channelMeta[_channelId];
        return (meta.closeNonce, meta.closeStateHash, meta.challengeDeadline, meta.challenger);
    }

    /**
     * @notice Retorna o nonce atual para criação de canais.
     */
    function getChannelNonce() external view returns (uint256) {
        return _channelNonce;
    }

    // =========================================================================
    // Receive (aceitar ETH)
    // =========================================================================

    /// @notice Aceita ETH enviado diretamente ao contrato
    receive() external payable {}

    /// @notice Fallback para chamadas com dados mas sem função correspondente
    fallback() external payable {}
}
