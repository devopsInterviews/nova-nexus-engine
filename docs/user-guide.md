# AI Portal — User Guide

---

## What is this?

The AI Portal is your team's internal hub for working with AI — without needing to set anything up yourself.

Think of it as a layer that connects AI models to the tools your team already uses: disassemblers, databases, IDEs, chat interfaces, CI/CD pipelines. Instead of every engineer reinventing how to wire up an LLM to their workflow, the portal makes it repeatable, governed, and shareable.

It's built for technical teams. You don't need to be an AI expert to use it, but you do need to know your way around your own tools.

There are three main areas covered in this guide:

- **Home** — your starting point
- **Research** — AI-assisted binary analysis
- **Marketplace** — deploy and share AI Agents and MCP Servers

---

## Home

**Who it's for:** Everyone.

When you log in, the Home page gives you a quick map of what you can do and where to go. It's personalised to your name and shows only the features you have access to.

### Feature cards

Three cards show you the main capabilities of the portal. Each one tells you what it does and links you directly to it:

**AI Marketplace** — Build and deploy custom AI Agents and MCP Servers. Connect them to OpenWebUI, your IDE, or any tool, and automate complex workflows.

**Binary File Research** — Connect your IDA Pro workstation to the portal and ask the LLM anything about the binaries you're analysing. Reverse engineering meets generative AI.

**Business Intelligence** — Ask questions in plain language and get AI-generated SQL, results, and insights directly from your databases.

If you see a lock icon on a card, you don't have access to that feature yet. Reach out to DevOps to request it.

### Getting started links

At the bottom of the page you'll find two helpful shortcuts:

- **Don't know where to start?** — Links to the Confluence documentation and the Developer Portal, where you can generate API keys for LLM access.
- **Chat & Code with AI** — Links to OpenWebUI (the internal chat interface) and download links for IDE tools like Cline and OpenCode so you can work with AI directly from your editor.

---

## Research

**Who it's for:** Reverse engineers who use IDA Pro (JADX and Ghidra support is on the way).

**What it does:** It connects your local IDA Pro session to OpenWebUI, so you can ask an LLM questions about the binary you currently have open — all through a secure, managed proxy. The portal doesn't host IDA centrally. It just makes the connection between your machine and the AI repeatable and supportable.

### How it works

**Step 1 — Install the IDA plugin on your workstation**

You'll need Python 3.11 or higher and IDA Pro 8.3 or higher (IDA Free is not supported).

The Research page shows you the exact install command with the current recommended version, and you can copy it directly. Once installed, run the setup command and restart IDA fully, then start the plugin from inside IDA: *Edit → Plugins → MCP*.

**Step 2 — Register your workstation in the portal**

Fill in:
- Your workstation hostname (FQDN) — for example `mypc.corp.example.com`, or `localhost` if you're running locally
- The IDA plugin port (default is `13337`)
- The MCP Server version you want to use (the recommended one is pre-selected)

Hit **Connect**. The portal will set up a secure tunnel between your IDA session and OpenWebUI.

**Step 3 — Use it in OpenWebUI**

Once connected, go to OpenWebUI, open the Tools panel, and toggle on the IDA MCP server for your hostname. From there, ask the LLM anything about your binary — functions, strings, structures, references, whatever you're investigating.

**Prefer your IDE over OpenWebUI?** The page also gives you a local URL you can paste directly into Cline or any MCP-compatible client.

### Switching between office and home

If you're working from a different network, your hostname or IP may change. The page gives you a tip on how to handle this — just reconnect with the new details.

### Status and cleanup

Once you've connected, your MCP server card will show you its live status (Running, Deploying, or Error), the connection details, and when it was last active. When you're done, you can delete the connection from the same card.

---

## Marketplace

**Who it's for:** Anyone who wants to deploy AI capabilities to their workflow, and teams who build and share them.

**What it does:** The Marketplace is the internal app store for AI assets. Teams publish AI Agents and MCP Servers here, manage their lifecycle, and share them with the organisation. If someone on another team has already built something useful, you can find it, deploy it, and start using it in minutes.

### What's in it

**Agents** are autonomous task executors — they do things. A code review agent, a Jenkins assistant, a SQL analyst. Each one is listed with a description, its current status, usage stats, and instructions for how to connect to it.

**MCP Servers** are tool and context providers — they give the AI model access to a specific system or data source, like a database, a repo, or a service. The AI then calls them when it needs information or to take an action.

**Skills** (coming soon) — will let you chain Agents and MCP Servers into multi-step pipelines without writing glue code.

### Lifecycle states

Every item in the Marketplace has a status that tells you where it is in its lifecycle:

| Status | What it means |
|---|---|
| **Built** | Published and ready, but not deployed yet |
| **Dev Deployed** | Running in the dev environment, expires after a set number of days |
| **Expiring** | Dev deployment with 7 days or less left — act soon if you're relying on it |
| **Release** | Deployed to production, persistent with no expiry |

### Finding what you need

Use the search bar at the top to search by name, description, owner, or chart name. Use the filter bar to narrow by status — useful when you only want to see what's actively running in production.

### Deploying something

Click on any item card to open its detail view. You'll see the full description, how to use it, what tools it exposes, its connection URL, and usage stats.

If you have permission (or you're the owner), you'll also see action buttons:

- **Deploy Dev** — spins it up in the dev environment with an expiry date
- **Deploy Release** — deploys to production, no expiry
- **Upgrade** — redeploy with a newer chart version
- **Extend Life** — push back the expiry on a dev deployment
- **Fork** — clone it as your own and customise from there

When you deploy, the portal will ask you to pick the environment, the Helm chart version from Artifactory, and any optional config overrides. During deployment, a loading screen will keep you company (and maybe make you smile). Once it's done, you'll get the connection URL to use in OpenWebUI or your IDE.

### Publishing something

Have something useful to share? Click **+ Publish Agent / MCP Server**, give it a name, a description, choose the type, and optionally add a Bitbucket repo link, an icon, and usage instructions. Once published, it shows up in the Marketplace as *Built* and you can deploy it from there.

---

## A note on access

Not all features are available to all users. Your access is managed by your admin. If you're missing a tab or a feature, contact DevOps to request access. Admins have additional controls visible only to them — such as removing items from the database directly or managing other users' deployments.

---

*For further help, see the Confluence documentation linked on the Home page, or reach out to the DevOps team.*
