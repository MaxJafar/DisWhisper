# Security

Please report vulnerabilities privately through GitHub's **Report a vulnerability** flow for this repository. Do not attach tokens, API keys, private conversations, or personal configuration to a public issue.

Include the affected version, platform, steps to reproduce, and the expected/actual behavior using fake credentials and synthetic transcripts. The latest release is the supported version.

The desktop service listens on loopback, rejects cross-origin requests and unexpected Host headers, and redacts configuration secrets. It is intended for a trusted single-user desktop. Other local processes running as your user can access the service and your transcript files.

Windows DPAPI protects newly saved credentials for the Windows account. Legacy CLI .env files and other plain-text configuration must be protected by the user. Delete or replace a token in the Discord Developer Portal if it has been disclosed.
