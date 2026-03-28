# agent-sandbox-router-chart

Helm chart that deploys the agent-sandbox router, its ClusterIP Service, an HTTPRoute, and a SandboxTemplate.

## Prerequisites

- Kubernetes 1.28+
- Helm 3.x
- Gateway API CRDs installed (`gateway.networking.k8s.io/v1`)
- agent-sandbox CRDs installed (`extensions.agents.x-k8s.io/v1alpha1`)
- A pre-existing Gateway resource in the cluster

## Install

```sh
helm install my-router oci://ghcr.io/OWNER/charts/agent-sandbox-router \
  --set httproute.hostname=<your-preferred-hostname> \
  --set httproute.parentRef.name=<your-gateway-name> \
  --set httproute.parentRef.namespace=<your-gateway-namespace> \
```

## Values

| Key | Default | Description |
|-----|---------|-------------|
| `namespace` | `agent-sandbox-system` | Namespace to deploy the router into |
| `router.replicaCount` | `2` | Number of router replicas |
| `router.image.repository` | `ghcr.io/linuxdweller/sandbox-router` | Router image repository |
| `router.image.tag` | `0.2.1` | Router image tag |
| `router.image.pullPolicy` | `IfNotPresent` | Image pull policy |
| `router.env` | `[PROXY_TIMEOUT_SECONDS=180]` | Environment variables for the router container |
| `router.resources` | requests 250m/512Mi, limits 1000m/1Gi | Resource requests and limits |
| `router.securityContext.runAsUser` | `1000` | Pod-level UID |
| `router.securityContext.runAsGroup` | `1000` | Pod-level GID |
| `httproute.enabled` | `true` | Create the HTTPRoute resource |
| `httproute.name` | `sandbox-router-route` | HTTPRoute name |
| `httproute.hostname` | `""` | Hostname to match; empty = all hostnames |
| `httproute.parentRef.name` | `external` | Gateway name |
| `httproute.parentRef.namespace` | `envoy` | Gateway namespace |
| `sandboxTemplate.enabled` | `true` | Create the SandboxTemplate resource |
| `sandboxTemplate.name` | `python-sandbox-template` | SandboxTemplate name |
| `sandboxTemplate.namespace` | `agent-sandboxes` | Namespace for SandboxTemplate and sandboxes (created by the chart) |
| `sandboxTemplate.containerName` | `python-runtime` | Container name in the sandbox pod |
| `sandboxTemplate.image.repository` | `us-central1-docker.pkg.dev/k8s-staging-images/agent-sandbox/python-runtime-sandbox` | Python runtime image |
| `sandboxTemplate.image.tag` | `latest-main` | Python runtime image tag |
| `sandboxTemplate.containerPort` | `8888` | Container port for the sandbox |
| `sandboxTemplate.readinessProbe.path` | `/` | Readiness probe path |
| `sandboxTemplate.readinessProbe.port` | `8888` | Readiness probe port |
| `sandboxTemplate.readinessProbe.periodSeconds` | `1` | Readiness probe period |
| `sandboxTemplate.livenessProbe.path` | `/` | Liveness probe path |
| `sandboxTemplate.livenessProbe.port` | `8888` | Liveness probe port |
| `sandboxTemplate.resources.requests` | cpu 250m, memory 512Mi, ephemeral-storage 512Mi | Sandbox pod resource requests |
| `sandboxTemplate.resources.limits` | cpu 500m, memory 1Gi, ephemeral-storage 1Gi | Sandbox pod resource limits |
| `sandboxTemplate.restartPolicy` | `OnFailure` | Sandbox pod restart policy |
