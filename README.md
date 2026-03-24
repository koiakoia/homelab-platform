# homelab-platform

OKD 4.19 cluster bootstrap, AI agent framework, and platform architecture for a production homelab on Proxmox.

This is the platform layer of [Project Sentinel](https://github.com/koiakoia) — how the Kubernetes cluster gets built from bare metal, and how an AI agent operates the infrastructure day-to-day.

## What's In Here

### OKD Cluster Bootstrap (`infrastructure/`, `manifests/`)
Full UPI (User Provisioned Infrastructure) deployment for OKD 4.19 on Proxmox:

- **OpenTofu** — Provisions VMs on Proxmox (control plane, masters, workers)
- **iPXE/Ignition** — PXE boots Fedora CoreOS with generated ignition configs
- **HAProxy** — Load balances API server (6443), machine config (22623), and ingress
- **dnsmasq** — DNS and DHCP for the isolated cluster network
- **MachineConfigs** — SSH access and CoreOS customization

### AI Agent Framework (`CLAUDE.md`)
The `CLAUDE.md` file defines how an AI agent (Claude Code) operates the infrastructure:

- **Issue-driven workflow** — every change tracked in Plane with engineering notes
- **Read → Think → Write → Verify** cycle
- **Session handoff** — agents post state summaries so the next session can continue
- **Hard limits** — never disable security tooling, never merge your own MRs
- **Multi-agent coordination** — role-based agents (Planner, Worker, Judge, Compliance Scribe)
- **NIST 800-53 control mapping** — the agent framework maps to CM-3, AU-6, AU-12, AC-5, SA-10

This isn't a toy. The agent has run 100+ sessions managing this infrastructure — opening issues, writing Ansible roles, debugging networking, and submitting merge requests.

### Sentinel Agent (`sentinel-agent/`)
Python-based monitoring agent that runs as a systemd service:

- Collects infrastructure state from multiple sources
- Publishes health checks and alerts
- Integrates with the AI agent workflow

### Documentation (`docs/`)
Architecture docs, networking topology, installation guides, compliance mapping, and operational runbooks.

## Deployment

### Prerequisites
- Proxmox VE cluster
- OpenTofu / Terraform
- OKD 4.19 installer (`openshift-install`)
- Fedora CoreOS images

### Quick Start

1. Copy `.env.example` to `.env` and configure
2. Generate ignition configs: `openshift-install create ignition-configs`
3. Provision VMs: `cd infrastructure && tofu init && tofu apply`
4. PXE boot nodes — they pull ignition from the control plane
5. Wait for bootstrap to complete: `openshift-install wait-for bootstrap-complete`
6. Deploy workloads via [homelab-gitops](https://github.com/koiakoia/homelab-gitops)

## Related Repos

- [homelab-iac](https://github.com/koiakoia/homelab-iac) — Terraform, Ansible, Packer for all VMs
- [homelab-gitops](https://github.com/koiakoia/homelab-gitops) — ArgoCD manifests for everything running on the cluster
- [homelab-compliance](https://github.com/koiakoia/homelab-compliance) — NIST 800-53 compliance artifacts

## License

Apache 2.0 — see [LICENSE](LICENSE).
