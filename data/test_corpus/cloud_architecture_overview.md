# High-Availability Cloud Architecture & Microservices Infrastructure

## 1. Kubernetes Cluster (EKS)
Our primary backend workloads run on an Amazon Elastic Kubernetes Service (EKS) multi-AZ cluster. Ingress traffic is managed by Traefik with automatic TLS termination and rate-limiting.

## 2. Distributed Caching with Redis
To achieve sub-millisecond query responses, we deploy an in-memory Redis cluster. Session tokens, frequent search results, and API rate-limiting buckets are stored in Redis with an LRU eviction policy.

## 3. Asynchronous Messaging with Apache Kafka
Inter-service communication utilizes Apache Kafka event streams. The user activity tracking and notification services consume event topics with partitioned consumer groups for horizontal scale.
