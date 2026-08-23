// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title  MediaProvenanceRegistry
 * @notice Immutable, tamper-proof registry of video forensic attestations.
 *
 * Each unique SHA-256 hash can be attested exactly once. The attesting address
 * must be the authorised verifier set at deploy time.
 *
 * Designed for deployment on:
 *   - Polygon Amoy testnet  (chainId 80002)
 *   - Ethereum Sepolia      (chainId 11155111)
 *
 * @dev No upgradability by design — records are permanent once written.
 */
contract MediaProvenanceRegistry {

    // ─────────────────────────────────────────────────────────────────────────
    // Types
    // ─────────────────────────────────────────────────────────────────────────

    /// @dev Machine-readable authenticity verdict categories.
    enum Verdict {
        Authentic,          // 0
        Deepfake,           // 1
        Cheapfake,          // 2
        AudioManipulated,   // 3
        Inconclusive        // 4
    }

    /// @dev Full provenance record sealed on-chain for a single media asset.
    struct ForensicRecord {
        bytes32 exactSha256;       // Byte-level SHA-256 of the raw video file
        string  perceptualHash;    // Visual pHash fingerprint (imagehash.phash)
        string  reportIpfsCid;     // IPFS CID of the full forensic report JSON
        uint8   authenticityScore; // 0 (definitely fake) — 100 (definitely real)
        Verdict verdict;
        string  attributedSource;  // e.g. "ElevenLabs", "Sora", "Organic"
        uint256 timestamp;         // block.timestamp at attestation
        address verifier;          // address that sealed this record
    }

    // ─────────────────────────────────────────────────────────────────────────
    // State
    // ─────────────────────────────────────────────────────────────────────────

    /// @notice The sole address authorised to call recordAttestation.
    address public immutable authorisedVerifier;

    /// @dev SHA-256 → ForensicRecord storage.
    mapping(bytes32 => ForensicRecord) private _records;

    /// @dev Track which hashes have been attested (prevents overwrites).
    mapping(bytes32 => bool) private _attested;

    // ─────────────────────────────────────────────────────────────────────────
    // Events
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * @notice Emitted whenever a new forensic attestation is sealed on-chain.
     * @param exactSha256      Byte-level SHA-256 of the video file.
     * @param ipfsCid          IPFS CID of the full JSON report.
     * @param authenticityScore 0–100 authenticity confidence.
     * @param verdict          Machine-readable verdict enum.
     * @param verifier         The address that performed the attestation.
     * @param timestamp        Block timestamp of attestation.
     */
    event MediaAttested(
        bytes32 indexed exactSha256,
        string          ipfsCid,
        uint8           authenticityScore,
        Verdict         verdict,
        address indexed verifier,
        uint256         timestamp
    );

    // ─────────────────────────────────────────────────────────────────────────
    // Errors
    // ─────────────────────────────────────────────────────────────────────────

    error Unauthorised(address caller);
    error AlreadyAttested(bytes32 exactSha256);
    error InvalidScore(uint8 score);

    // ─────────────────────────────────────────────────────────────────────────
    // Constructor
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * @param _verifier The wallet address authorised to seal attestations.
     *                  Should be the backend service hot-wallet.
     */
    constructor(address _verifier) {
        require(_verifier != address(0), "Verifier cannot be zero address");
        authorisedVerifier = _verifier;
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Write
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * @notice Seal a forensic attestation on-chain.
     *
     * Can only be called by `authorisedVerifier`.
     * Each SHA-256 hash can only be attested once — subsequent calls revert.
     *
     * @param _exactSha256       bytes32 SHA-256 of the raw video bytes.
     * @param _perceptualHash    Visual pHash string fingerprint.
     * @param _reportIpfsCid     IPFS CID pointing to the full JSON report.
     * @param _authenticityScore 0–100 confidence that the media is authentic.
     * @param _verdict           Verdict enum value.
     * @param _attributedSource  Human-readable source attribution string.
     */
    function recordAttestation(
        bytes32        _exactSha256,
        string calldata _perceptualHash,
        string calldata _reportIpfsCid,
        uint8           _authenticityScore,
        Verdict         _verdict,
        string calldata _attributedSource
    ) external {
        if (msg.sender != authorisedVerifier) revert Unauthorised(msg.sender);
        if (_attested[_exactSha256])           revert AlreadyAttested(_exactSha256);
        if (_authenticityScore > 100)          revert InvalidScore(_authenticityScore);

        _records[_exactSha256] = ForensicRecord({
            exactSha256:       _exactSha256,
            perceptualHash:    _perceptualHash,
            reportIpfsCid:     _reportIpfsCid,
            authenticityScore: _authenticityScore,
            verdict:           _verdict,
            attributedSource:  _attributedSource,
            timestamp:         block.timestamp,
            verifier:          msg.sender
        });

        _attested[_exactSha256] = true;

        emit MediaAttested(
            _exactSha256,
            _reportIpfsCid,
            _authenticityScore,
            _verdict,
            msg.sender,
            block.timestamp
        );
    }

    // ─────────────────────────────────────────────────────────────────────────
    // Read
    // ─────────────────────────────────────────────────────────────────────────

    /**
     * @notice Query the on-chain provenance record for a given SHA-256 hash.
     * @param _exactSha256 Byte-level SHA-256 of the video file.
     * @return record      The full ForensicRecord struct (zero-value if not attested).
     * @return exists      True if this hash has been attested.
     */
    function getRecord(bytes32 _exactSha256)
        external
        view
        returns (ForensicRecord memory record, bool exists)
    {
        return (_records[_exactSha256], _attested[_exactSha256]);
    }

    /**
     * @notice Convenience check — has this SHA-256 been attested?
     */
    function isAttested(bytes32 _exactSha256) external view returns (bool) {
        return _attested[_exactSha256];
    }
}
