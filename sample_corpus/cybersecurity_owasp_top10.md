# OWASP Top 10 Application Security Vulnerabilities

Understanding common application vulnerabilities is essential for secure software engineering.

1. **Broken Access Control:** Failures where users act outside their intended permissions (e.g., IDOR - Insecure Direct Object References).
2. **Cryptographic Failures:** Exposure of sensitive data due to weak algorithms (MD5, SHA-1), hardcoded secrets, or lack of TLS.
3. **Injection:** SQL, command, and LDAP injection where hostile data is parsed as commands. Remedy: Parameterized prepared statements.
4. **Insecure Design:** Flaws inherent in architecture rather than code implementation, requiring threat modeling before coding.
5. **Security Misconfiguration:** Default credentials, verbose error stack traces, unpatched dependencies, and missing security headers.