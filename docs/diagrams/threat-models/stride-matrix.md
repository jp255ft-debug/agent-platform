# STRIDE Threat Matrix

| Threat | Component | Mitigation |
|--------|-----------|------------|
| Spoofing | API Gateway | Signature verification |
| Tampering | Event Store | Append-only, checksums |
| Repudiation | All | Full audit trail |
| Information Disclosure | API | Encryption at rest |
| Denial of Service | Rate Limiter | Token bucket + Redis |
| Elevation of Privilege | Auth | EIP-7702 delegation |
