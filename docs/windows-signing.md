# Windows release signing

The release workflow can sign the one-file executable, the standalone FileTree executable and the
MSI through Azure Artifact Signing (formerly Trusted Signing). Signing is optional and disabled
until configured. Development Desktop builds remain unsigned. No signing account or private key is
created by this repository. Native successful signing remains blocked on the owner's account.

Create an Azure signing account, complete the required identity validation and create a **Public
Trust** certificate profile. Give a dedicated Entra application only the **Artifact Signing
Certificate Profile Signer** role on that profile. Configure a GitHub OIDC federated credential with
audience `api://AzureADTokenExchange` and subject
`repo:JeffreyChen-s-Utils/FileTree:environment:windows-signing`. Protect the `windows-signing` GitHub
environment for the intended release branch and maintainers before enabling signing. The Windows
release job uses that environment and alone receives `id-token: write`; it has read-only repository
contents permission. Azure login and signing actions are pinned to commits. Authentication uses
Azure CLI after OIDC login; environment passwords, managed identities and interactive fallback are
excluded. Dependency caching and trace logging are disabled.

Set these identifiers as repository or `windows-signing` environment **secrets**:

- `FILETREE_AZURE_CLIENT_ID`
- `FILETREE_AZURE_TENANT_ID`
- `FILETREE_AZURE_SUBSCRIPTION_ID`

Set these repository or environment **variables**:

- `FILETREE_WINDOWS_SIGNING=azure-artifact`
- `FILETREE_SIGNING_ENDPOINT`: the account's HTTPS regional endpoint, such as
  `https://wus.codesigning.azure.net/`.
- `FILETREE_SIGNING_ACCOUNT`: the signing account name.
- `FILETREE_SIGNING_PROFILE`: its Public Trust certificate profile name.
- `FILETREE_SIGNING_PUBLISHER`: the exact expected certificate subject, including its attribute
  ordering, from that reviewed profile/certificate. This is compared case-sensitively with the
  native certificate's `Subject`; it is not a display-name substring.

Leave `FILETREE_WINDOWS_SIGNING` unset for unsigned releases. Any other mode, missing enabled field
or malformed configuration stops before compilation; enabled signing never silently falls back to
unsigned output. `tools/check_signing.py` writes only the enabled boolean to the workflow output and
does not echo identifiers or contact the service.

The local signing action checks exact nonlinked release paths, then signs only
`build/onefile/FileTree.exe` and `build/standalone/start_file_tree.dist/FileTree.exe`. It uses SHA-256
file digests and RFC 3161 SHA-256 timestamps. Native `Get-AuthenticodeSignature` must report a valid
trusted signature, a timestamp certificate and the exact expected publisher. Verification failure
stops packaging. The standalone ZIP and MSI therefore contain the verified standalone executable.
The completed MSI is separately signed and verified **before** uploading it or calculating store
manifest hashes. Third-party runtime binaries are not selected for resigning. The release job does
not launch any binary as a signing check.

Signing does not guarantee SmartScreen reputation or antivirus acceptance. A successful native
signing run, downloaded-artifact signature/hash verification and the actual signing account remain
unverified until the owner supplies the environment. No secrets, account settings or release gates
have been enabled by implementing this workflow.

References: [Azure OIDC integration](https://github.com/Azure/artifact-signing-action/blob/main/docs/OIDC.md),
[Artifact Signing setup](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart), and
[SignTool policies and timestamping](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool).
