# OKD Cluster Operations - Overwatch

## Cluster Identity

| Property | Value |
|----------|-------|
| **Cluster Name** | overwatch |
| **Base Domain** | ${DOMAIN} |
| **API Endpoint** | `https://api.${OKD_CLUSTER}.${DOMAIN}:6443` |
| **Console** | `https://console-openshift-console.apps.${OKD_CLUSTER}.${DOMAIN}` |
| **Platform** | OKD 4.19 (Kubernetes v1.32.7) |
| **Distribution** | UPI on bare-metal Proxmox VMs |
| **CNI** | OVN-Kubernetes |
| **Workers** | 0 (control-plane nodes schedule all workloads) |

## Architecture Overview

The Overwatch cluster is a 3-node compact OKD deployment running on Proxmox
virtual machines across two physical hosts. All nodes carry both
`control-plane` and `worker` roles -- there are no dedicated worker nodes.

```
                         Internet
                            |
                    [pangolin-proxy]
                    ${PROXY_IP}
                            |
               +--- Management VLAN ---+
               |    ${LAN_NETWORK}/24    |
               |                       |
         [iac-control]          [config-server]
         ${IAC_CONTROL_IP}          VM 300 (HA backup)
         ${OKD_NETWORK_GW} (VIP)         ${OKD_GATEWAY}
         ${OKD_DNS_IP} (DHCP)
               |
               | vmbr1 (internal bridge)
               | ${OKD_NETWORK}/24
               |
     +---------+---------+
     |         |         |
 [master-1] [master-2] [master-3]
 ${OKD_MASTER1_IP} ${OKD_MASTER2_IP} ${OKD_MASTER3_IP}
 pve        proxmox-node-2    proxmox-node-2
```

### Node Inventory

| Node | VM ID | IP Address | Proxmox Host | CPU | Memory | Disk |
|------|-------|-----------|--------------|-----|--------|------|
| master-1 | 211 | ${OKD_MASTER1_IP} | pve | 12 cores | 32 GB | 120 GB |
| master-2 | 212 | ${OKD_MASTER2_IP} | proxmox-node-2 | 12 cores | 32 GB | 120 GB |
| master-3 | 213 | ${OKD_MASTER3_IP} | proxmox-node-2 | 12 cores | 32 GB | 120 GB |
| bootstrap | 210 | ${OKD_BOOTSTRAP_IP} | pve | 4 cores | 16 GB | 120 GB |

The bootstrap node (VM 210) is powered off post-install. It is only needed for
full cluster rebuilds.

### Supporting Infrastructure

| Component | Host | Role |
|-----------|------|------|
| **iac-control** (${IAC_CONTROL_IP} / ${OKD_NETWORK_GW}) | pve | HAProxy LB, dnsmasq DNS/DHCP/PXE, keepalived VIP, Squid egress proxy, nginx ignition server |
| **config-server** (${OKD_GATEWAY} / ${OKD_WORKER_IP}) | pve (VM 300) | HA failover: keepalived BACKUP, dnsmasq, HAProxy mirror |
| **pangolin-proxy** (${PROXY_IP}) | pve | Traefik reverse proxy, Cloudflare tunnel, CrowdSec |
| **vault-server** (${VAULT_IP}) | proxmox-node-2 | HashiCorp Vault (secrets, SSH CA, ESO backend), NFS storage |

### Network Topology

The cluster lives on an isolated internal network (`vmbr1`, ${OKD_NETWORK}/24)
with no direct internet access. iac-control bridges the management VLAN
(${LAN_NETWORK}/24) to the cluster network and provides:

- **NAT** for outbound traffic (with Squid domain-based allowlisting)
- **HAProxy** load balancing for API (6443), Machine Config (22623), and Ingress (80/443)
- **dnsmasq** DNS resolution (cluster + wildcard `*.apps.${OKD_CLUSTER}.${DOMAIN}`) and DHCP
- **keepalived** VIP (${OKD_NETWORK_GW}) for HA failover to config-server

**Critical constraint:** OKD pods CANNOT reach ${LAN_NETWORK}/24 (management
VLAN). Only the ${OKD_NETWORK}/24 internal network and NAT-routed internet
destinations are accessible.

### Air-Gapped Characteristics

While not fully air-gapped (Squid allows allowlisted domains), the cluster
has significant restrictions:

- No direct internet egress from pod network
- Grafana `gnetId` dashboard references silently fail -- always use inline JSON
- All container images are pulled from Harbor at `harbor.${INTERNAL_DOMAIN}` (on mgmt VLAN, accessible via iptables FORWARD rules to ${GITLAB_IP} and image registries)
- Squid allowlist controls which external registries are reachable

### Access Methods

```bash
# From WSL workstation to iac-control
ssh -i ~/.ssh/id_sentinel ubuntu@${IAC_CONTROL_IP}

# From iac-control: oc login
export KUBECONFIG=~/overwatch-repo/auth/kubeconfig
oc login https://api.${OKD_CLUSTER}.${DOMAIN}:6443 \
  -u kubeadmin -p $(cat ~/overwatch-repo/auth/kubeadmin-password) \
  --insecure-skip-tls-verify

# From iac-control: SSH to master nodes
ssh -i ~/.ssh/okd_key core@${OKD_MASTER1_IP}   # master-1
ssh -i ~/.ssh/okd_key core@${OKD_MASTER2_IP}   # master-2
ssh -i ~/.ssh/okd_key core@${OKD_MASTER3_IP}   # master-3
```

### Kubeconfig Maintenance

If `oc` returns "certificate signed by unknown authority" errors, refresh the
kubeconfig from a running master:

```bash
ssh -i ~/.ssh/okd_key core@${OKD_MASTER1_IP} \
  'sudo cat /etc/kubernetes/static-pod-resources/kube-apiserver-certs/secrets/node-kubeconfigs/lb-ext.kubeconfig' \
  > ~/overwatch-repo/auth/kubeconfig
```

### GitOps Repository

The cluster state is managed by ArgoCD from the `overwatch-gitops` repository
(GitLab project 3) at `http://${GITLAB_IP}/${GITLAB_NAMESPACE}/overwatch-gitops.git`.
Pushing to `main` triggers auto-sync. See [Workload Management](workload-management.md)
for the full app-of-apps structure.

### Terraform State

VM infrastructure state is stored in MinIO S3-compatible storage:

| Property | Value |
|----------|-------|
| Endpoint | `http://${MINIO_PRIMARY_IP}:9000` |
| Bucket | `terraform-state` |
| State Key | `overwatch/terraform.tfstate` |
| Provider | `bpg/proxmox` v0.70.0 |
| Terraform | OpenTofu >= 1.6.0 |
