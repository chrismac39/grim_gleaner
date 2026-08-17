# Windows Release Trust

This document describes how Grim Gleaner should be distributed on Windows once public releases begin.

## Current state

The repository's release script builds `grim_gleaner.exe` with `pyside6-deploy`, assembles the release resources, and places the executable and resources in a ZIP archive. It does not currently sign the executable.

The `grim-gleaner-ui` command is a Python development entry point. It is not the public release artifact. Users should receive `grim_gleaner.exe` from a release archive.

An unsigned executable can trigger Microsoft Defender SmartScreen or another Windows application-control policy. Signing reduces those warnings and lets Windows show a verified publisher, but it does not guarantee that every machine will allow a new program to run. Enterprise WDAC or AppLocker policies can still require their own administrator approval.

## Recommended release path

1. Build the release in a controlled environment.
2. Sign the final `grim_gleaner.exe` after the executable is built and before the ZIP is created.
3. Use an Authenticode certificate issued to the person or organization publishing Grim Gleaner. Keep the private key out of the repository and out of ordinary developer machines.
4. Add a trusted timestamp when signing. A timestamp keeps the signature valid after the signing certificate expires, provided the certificate was valid when the file was signed.
5. Verify the signature and publisher identity in CI before publishing.
6. Publish the same signed binary through the project's GitHub Releases page. Do not rebuild the executable after signing.
7. Keep the signed binary stable while it accumulates SmartScreen reputation. Every changed binary has a new file identity and may produce a warning again.

## Certificate options

For a small open-source project, use one of these approaches rather than putting a raw private key in the repository:

- A code-signing certificate stored on a hardware token or protected signing service.
- A cloud signing service such as Azure Trusted Signing or another vendor that supports CI signing without exporting the private key.
- A CI secret containing an encrypted PFX, only if the certificate provider and the CI platform's secret-storage controls are acceptable. Restrict signing to protected release tags and limit who can approve those jobs.

An OV code-signing certificate is the normal starting point. EV certificates can improve publisher validation, but neither certificate type is a guaranteed SmartScreen bypass. Microsoft reputation is also based on download and execution reputation, the publisher, the file hash, and security telemetry.

## Local signing example

The Windows SDK provides `signtool.exe`. The exact path depends on the installed SDK version. After building, sign the final executable with a certificate from the Windows certificate store:

```powershell
signtool sign `
  /fd SHA256 `
  /td SHA256 `
  /tr https://timestamp.digicert.com `
  /sha1 YOUR_CERTIFICATE_THUMBPRINT `
  .\dist\Grim Gleaner\grim_gleaner.exe

signtool verify /pa /v .\dist\Grim Gleaner\grim_gleaner.exe
Get-AuthenticodeSignature .\dist\Grim Gleaner\grim_gleaner.exe
```

If the certificate is supplied as a PFX, do not put the password in a script or command committed to the repository. Supply it interactively or through the signing provider's protected secret mechanism. Use a certificate thumbprint or a protected certificate alias in automation where possible.

The expected verification result is `Status: Valid`, with the intended publisher shown in the signature details. A timestamp should also be present.

## Packaging integration

Signing must happen after this script produces and copies `grim_gleaner.exe`, but before `Compress-Archive` runs:

```text
build executable -> assemble resources -> sign executable -> verify signature -> create ZIP
```

The release script should eventually expose signing configuration, for example a certificate thumbprint or protected signing-service parameters. It should fail the release when signing is requested but verification does not return a valid signature. Unsigned builds may remain useful for local development, but they should be clearly labeled as such and should not be presented as the normal public download.

## What signing does not solve

- SmartScreen may still show an initial warning for a new publisher or new binary.
- A ZIP downloaded from the internet can retain a Mark-of-the-Web tag. Users may need to use the ZIP file's Properties dialog and select **Unblock** before extracting it when Windows presents a download warning.
- WDAC, AppLocker, or other organization-managed application-control policies can reject an executable even when it is correctly signed. Those policies must trust the publisher certificate or explicitly allow the application.
- Signing does not replace malware scanning, dependency review, release checksums, or a reproducible and access-controlled build process.

## Release checklist

- [ ] Build from a protected release commit or tag.
- [ ] Run the test suite before packaging.
- [ ] Confirm the executable contains the intended version and resources.
- [ ] Sign the final executable with SHA-256 and a trusted timestamp.
- [ ] Verify the Authenticode signature and publisher.
- [ ] Scan the signed artifact and archive it without modifying it afterward.
- [ ] Publish a SHA-256 checksum alongside the ZIP.
- [ ] Test the downloaded archive on a clean Windows machine.
- [ ] Record the certificate identity and release artifact hash for the release record, without publishing private-key material.
