# Security policy

bussola runs a local web server that reads your repositories, runs `git` and `gh`, and can act on GitHub with your `gh` login. Issues that let another site, another user on the same machine or crafted repository content reach that server or those commands are taken seriously.

## Reporting a vulnerability

Please do not open a public issue. Use **Report a vulnerability** on the repository's **Security** tab, which opens a private advisory, and include the steps to reproduce and the version you tested. Do not include private code or real tokens: reproduce with a small public or made-up repository.

You should get a reply within a week. Once a fix is released, the advisory is published with credit to you, unless you prefer otherwise.

## What matters most here

- A web page in the same browser, or another user on the same machine, calling the bussola API without the session token, or getting around the `Host` check.
- Repository content (file names, branch names, commit messages, code) that makes bussola run a command, read a file outside the git object database, or pass an option to `git` or `gh`.
- Markdown or HTML from a comment or pull request description that runs script in the bussola page.
- The `gh` token reaching any host other than `github.com`, or being stored by bussola.
- A GitHub action (sending comments, resolving threads) that happens without the user asking for it.

## Supported versions

Only the latest release receives security fixes.

## Scope

The protections bussola relies on are described in the Security section of the [README](README.md#security): the loopback-only default, the session token cookie, the `Host` check, ref validation, HTML sanitizing and the limits on GitHub image downloads. Running bussola with `--host` set to a non-loopback address exposes it to your network and is outside what it is designed for.
