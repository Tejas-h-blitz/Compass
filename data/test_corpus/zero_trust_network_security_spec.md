# Zero-Trust Architecture (ZTA) Technical Specification

## 1. Architectural Philosophy
Under NIST Special Publication 800-207 guidelines, network locality no longer implies trust. Every request inside our virtual private cloud (VPC) must be explicitly authenticated, authorized, and encrypted.

## 2. Mutual TLS (mTLS) with SPIFFE/SPIRE Identity Attestation
All inter-service microservice calls require mutual TLS 1.3 with automated X.509 certificate issuance. SPIRE agents validate cryptographic node attestation before minting short-lived SVID tokens.

## 3. Microsegmentation & Role-Based Access Control (RBAC)
Workloads are partitioned across Kubernetes network policies. Database instances reject any connection that lacks an approved security group identity tag.
