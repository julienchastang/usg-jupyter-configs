# Repurposing an Existing Jetstream2 JupyterHub Cluster

This runbook describes how to reuse an existing OpenStack Magnum/Kubernetes
JupyterHub for a new workshop without rebuilding the cluster. It covers
capacity planning, the user image, persistent NFS storage, JupyterHub profiles,
authentication, DNS, TLS certificates, deployment, testing, and rollback.

The examples use placeholders. Replace values such as `<cluster>`, `<volume-id>`,
and `<new-host>` with values from the target environment.

## 1. Define the target

Record the following before making changes:

- Existing Magnum cluster name and kubeconfig
- Existing and desired public hostnames
- Expected concurrent users
- Required CPU and RAM per user
- Per-user storage quota
- Shared-data requirement
- Container image and immutable tag
- Workshop repository and branch
- Authentication method, administrators, and allowed users
- Whether browser-based graphical applications are required

Do not assume that the desired public hostname is also the Magnum cluster name.
Renaming the public Hub does not rename existing OpenStack infrastructure.

## 2. Capture and back up the current deployment

Confirm that the correct OpenStack project and Kubernetes context are active:

```bash
openstack token issue
kubectl config current-context
kubectl get nodes
```

Save the current deployment state:

```bash
helm list -A
helm get values <release> -n <namespace> --all > values-before.yaml
kubectl get ingress -A -o yaml > ingress-before.yaml
kubectl get certificate -A -o yaml > certificates-before.yaml
kubectl get pvc,pv -A -o yaml > storage-before.yaml
```

Identify important Cinder volumes and take snapshots or backups while writes are
quiesced. A snapshot of an actively written filesystem may only be
crash-consistent.

## 3. Audit cluster and project capacity

Inspect current nodes, node groups, and OpenStack quota:

```bash
kubectl get nodes -o wide
openstack coe nodegroup list <cluster>
openstack coe nodegroup show <cluster> <nodegroup>
openstack quota show
```

Also account for project-wide usage by unrelated clusters and VMs. Relevant
limits include instances, vCPUs, RAM, ports, floating IPs, volumes, volume
storage, and security-group rules.

### Example capacity calculation

If an `m3.medium` supplies 8 vCPU and 30 GB RAM and each user requests 3.5
vCPU and 12 GB RAM, two users fit on each node:

```text
CPU:    2 x 3.5 = 7 of 8 vCPU
Memory: 2 x 12  = 24 of 30 GB
```

For 30 concurrent users:

```text
ceil(30 / 2) = 15 running user nodes
```

Set the node-group maximum above the steady requirement to allow for failures
and imperfect scheduling, for example 17-20 nodes. A maximum is only a ceiling;
autoscaling does not keep every node running.

Update a running node group's bounds with:

```bash
openstack coe nodegroup update \
  --min-nodes <minimum> \
  --max-nodes <maximum> \
  <cluster> <nodegroup>
```

Before a scheduled workshop, consider temporarily setting the minimum close to
the expected running-node count. Return it to its normal value afterward.

## 4. Audit persistent storage

Inspect both Kubernetes objects and their real OpenStack backing volumes:

```bash
kubectl get pvc,pv -A
openstack volume list
```

Do not assume that the capacity printed on a static NFS PV or PVC is the real
capacity. Some deployments use nominal `1M` or `1Mi` objects to expose an NFS
export while the actual storage is a much larger Cinder volume.

Inspect the backing PV and volume:

```bash
kubectl get pv <backing-pv> -o yaml
openstack volume show <volume-id>
```

For the `jupyterhub-home-nfs` pattern, one Cinder volume contains an XFS
filesystem exported over NFS:

```text
Cinder volume
  -> XFS filesystem
     -> NFS server
        -> per-user directories and shared-data directory
           -> mounts in JupyterHub user pods
```

The NFS pod commonly contains these containers:

- `nfs-server`: exports the filesystem
- `enforce-xfs-quota`: maintains XFS project quotas
- `auto-xfs-resizer`: periodically runs `xfs_growfs`
- `metrics-exporter`: reports filesystem metrics

Inspect actual capacity and quotas:

```bash
kubectl get pods -n jupyterhub-home-nfs

kubectl exec -n jupyterhub-home-nfs <nfs-pod> \
  -c nfs-server -- df -hT /export

kubectl exec -n jupyterhub-home-nfs <nfs-pod> \
  -c enforce-xfs-quota -- \
  xfs_quota -x -c 'report -h' /export
```

XFS project quotas are limits, not reservations. The filesystem must still be
large enough for the desired aggregate usage.

### Storage sizing

Use:

```text
user capacity = concurrent users x per-user quota
physical size = user capacity + shared-data quota + headroom
```

For 30 users at 10 GB, a 50 GB shared quota, and 100 GB headroom:

```text
30 x 10 GB + 50 GB + 100 GB = 450 GB
```

Measure a complete workshop exercise before finalizing the per-user quota and
shared-data size.

## 5. Expand an XFS-backed NFS volume when necessary

Perform this during a maintenance window and after taking a snapshot or backup.
Expansion is one-way; do not plan on shrinking XFS afterward.

Extend the real Cinder volume, not the nominal NFS PVC:

```bash
openstack --os-volume-api-version 3.42 volume set \
  --size <new-size-gib> \
  <volume-id>
```

Check all three layers:

```bash
openstack volume show <volume-id> -c size -c status -c attachments

kubectl exec -n jupyterhub-home-nfs <nfs-pod> \
  -c nfs-server -- \
  sh -c 'blockdev --getsize64 /dev/sdb; df -hT /export'
```

The required progression is:

```text
Cinder volume grows
-> guest block device grows
-> XFS filesystem grows
```

The `auto-xfs-resizer` sidecar may only run `xfs_growfs`; it may not make an
already attached guest device notice a Cinder resize. If OpenStack reports the
new size but `/dev/sdb` retains the old size, use a clean CSI detach/reattach:

```bash
kubectl scale deployment/home-nfs \
  -n jupyterhub-home-nfs \
  --replicas=0
```

Wait until the pod is gone and the volume reports `available` with no
attachments:

```bash
kubectl get pods -n jupyterhub-home-nfs
openstack volume show <volume-id> -c size -c status -c attachments
```

Then restore the NFS deployment:

```bash
kubectl scale deployment/home-nfs \
  -n jupyterhub-home-nfs \
  --replicas=1
```

After the new pod reaches its full ready count, verify device size, filesystem
size, existing files, and project quotas. If the block device has the new size
but XFS has not grown after the sidecar's polling interval, inspect its logs
before running `xfs_growfs /export` manually.

Do not delete the PV or PVC as part of this operation, and do not manually
detach a volume while Kubernetes still owns an active `VolumeAttachment`.

## 6. Build and publish the workshop image

Create or adapt a single-user image containing:

- Workshop applications and their runtime dependencies
- Required Python/Conda packages
- `nbgitpuller` if materials are populated from Git
- Browser desktop/VNC support if graphical applications require it
- Any startup files, kernels, or environment variables required by the workshop

Build and test the image before deployment. Push it using an immutable tag, not
`latest`, and confirm that Kubernetes has valid registry credentials.

Test at least:

- Application binaries and version
- Notebook kernel selection
- Representative workshop notebook
- Shared-data access
- GUI startup, if applicable
- Startup as the unprivileged notebook user

## 7. Configure the Hub

Update the cluster configuration with:

- Existing internal infrastructure identity
- User node-group maximum
- Actual persistent-storage sizes
- Per-user quota and shared-data quota
- Immutable image name and tag
- Workshop repository, branch, and destination
- Administrators and authentication policy
- Desired participant profiles

For predictable packing, expose only profiles that were included in the
capacity calculation. For example, two users per `m3.medium` requires the
effective Helm profile to request and limit approximately:

```text
CPU:    3.5
Memory: 12 GB
```

Inspect the generated Helm values rather than relying on a display name such as
`Standard`. Confirm `profileList`, CPU and memory requests/limits, node selector,
image tag, ingress hosts, and OAuth callback before applying the upgrade.

## 8. Change the public hostname, if required

Keep the internal Magnum cluster name unchanged. Treat DNS and the public Hub
hostname as separate configuration.

For a low-risk transition:

1. Obtain the ingress controller's public IP.
2. Create the new DNS record pointing to the same IP.
3. Verify public DNS resolution.
4. Add the new GitHub OAuth callback.
5. Add the new hostname to the ingress and TLS configuration.
6. Wait for cert-manager to issue a valid certificate.
7. Test login and spawning at the new hostname.
8. Retain the old hostname as an alias or HTTPS redirect if desired.

Create a Jetstream2 record with:

```bash
openstack recordset create \
  <project-zone>.projects.jetstream-cloud.org. \
  <new-host> \
  --type A \
  --record <ingress-ip> \
  --ttl 300
```

The OAuth callback is commonly:

```text
https://<new-fqdn>/hub/oauth_callback
```

Use the exact path already configured for the old hostname. During transition,
keep both callbacks registered if the OAuth provider supports it.

Configure both names on the ingress and certificate during migration. An HTTPS
redirect from the old hostname still requires a valid certificate for the old
hostname because TLS validation occurs before the redirect response.

Monitor certificate issuance with:

```bash
kubectl get certificate,certificaterequest,order,challenge -A
kubectl describe certificate -n <namespace> <certificate>
```

Verify the certificate's Subject Alternative Names:

```bash
openssl s_client \
  -connect <new-fqdn>:443 \
  -servername <new-fqdn> \
  </dev/null 2>/dev/null | \
openssl x509 -noout -subject -issuer -dates -ext subjectAltName
```

## 9. Deploy the JupyterHub update

Before upgrading:

- Announce the maintenance window
- Stop active user servers
- Save the current Helm values
- Confirm backups and snapshots
- Confirm the new image is pullable
- Review the rendered configuration

Use the deployment repository's normal generation and Helm-upgrade workflow.
Do not run cluster-creation or storage-provisioning steps against an existing
cluster unless that is explicitly intended.

## 10. Validate the repurposed Hub

Test with both an administrator and an ordinary participant:

- New hostname and valid TLS certificate
- OAuth login, logout, and callback
- User allow-list and administrator access
- Server spawn on the intended node group
- Correct CPU and memory profile
- Workshop image and application version
- Workshop-material population/update
- Persistent home directory across pod restarts
- Per-user quota enforcement
- Shared-data read/write permissions and quota
- Representative end-to-end workshop exercise
- GUI workflow, if required

Then perform a realistic concurrency test. Verify node autoscaling, pod packing,
startup latency, registry pulls, CPU and memory pressure, and filesystem usage.

## 11. Prepare for the event

- Pre-scale enough nodes for the opening session
- Pre-pull the large user image
- Load and validate shared datasets
- Freeze the image tag and workshop-material revision
- Record rollback commands and prior Helm values
- Monitor pending pods, node scaling, image pulls, and storage metrics

## 12. After the event

- Reduce the node-group minimum
- Preserve or archive participant data according to policy
- Decide whether to retain the old hostname as an alias or redirect
- Remove obsolete OAuth callbacks only after the transition period
- Document the final deployed image, configuration, storage size, and lessons
  learned

## Completion checklist

- [ ] Existing infrastructure identity preserved
- [ ] New image built, tested, pushed, and pinned
- [ ] Node capacity sized and quota confirmed
- [ ] Persistent storage sized and verified
- [ ] User and shared XFS quotas confirmed
- [ ] Workshop repository configured
- [ ] Participant profile verified from rendered Helm values
- [ ] Authentication and administrators configured
- [ ] DNS resolves to the ingress IP
- [ ] Certificate is ready and covers every active hostname
- [ ] OAuth callback succeeds
- [ ] Persistent storage survives a user-pod restart
- [ ] Representative workload succeeds for two users on one node
- [ ] Full concurrency or load rehearsal completed
- [ ] Rollback materials saved
