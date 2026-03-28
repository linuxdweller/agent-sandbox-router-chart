# Implementation Plan: `agent-sandbox-router` Helm Chart

## Overview

A new, dedicated Git repository that is itself a single Helm chart. The chart deploys the
sandbox router Deployment, its ClusterIP Service, an HTTPRoute, and a SandboxTemplate CRD
resource. Released to GHCR via OCI on `v*` tag push.

---

## Repo Structure

```
Chart.yaml
values.yaml
templates/
  _helpers.tpl
  deployment.yaml
  service.yaml
  httproute.yaml
  sandbox-template.yaml
tests/
  test_router.py
docs/
  README.md
.github/
  workflows/
    helm-release.yaml
.gitignore
```

---

## Source Values Reference

Extracted from existing manifests in the `agent-sandbox` repo:

**Router (from `sandbox_router.yaml`):**
- Deployment name: `sandbox-router-deployment`
- Replicas: `2`
- Container name: `router`
- Image: `IMAGE_PLACEHOLDER` (no default — operator must supply)
- Container port: `8080`
- Env: `PROXY_TIMEOUT_SECONDS: "180"`
- Pod-level securityContext: `runAsUser: 1000`, `runAsGroup: 1000`
- topologySpreadConstraint: `maxSkew: 1`, `topologyKey: topology.kubernetes.io/zone`, `whenUnsatisfiable: ScheduleAnyway`
- readinessProbe: `GET /healthz :8080`, `initialDelaySeconds: 5`, `periodSeconds: 5`
- livenessProbe: `GET /healthz :8080`, `initialDelaySeconds: 10`, `periodSeconds: 10`
- Resources requests: `cpu: 250m`, `memory: 512Mi`; limits: `cpu: 1000m`, `memory: 1Gi`
- Service name: `sandbox-router-svc`, type: `ClusterIP`, port: `8080`

**HTTPRoute (from `gateway.yaml`):**
- Name: `sandbox-router-route`
- apiVersion: `gateway.networking.k8s.io/v1`
- parentRef name: `external-http-gateway`
- Path match: `PathPrefix /`
- backendRef: `sandbox-router-svc:8080`

**SandboxTemplate (from `python-sandbox-template.yaml`):**
- apiVersion: `extensions.agents.x-k8s.io/v1alpha1`
- Name: `python-sandbox-template`, namespace: `default`
- Container name: `python-runtime`
- Image: `us-central1-docker.pkg.dev/k8s-staging-images/agent-sandbox/python-runtime-sandbox:latest-main`
- Port: `8888`
- runtimeClassName: `gvisor`
- readinessProbe: `GET / :8888`, `initialDelaySeconds: 0`, `periodSeconds: 1`
- livenessProbe: `GET / :8888`, `initialDelaySeconds: 2`, `periodSeconds: 10`
- Resources requests: `cpu: 250m`, `memory: 512Mi`, `ephemeral-storage: 512Mi` (no limits)
- restartPolicy: `OnFailure`

---

## Phase 1 — `Chart.yaml`

```yaml
apiVersion: v2
name: agent-sandbox-router
description: Deploys the agent-sandbox router, Service, HTTPRoute, and SandboxTemplate
type: application
version: 0.1.0
appVersion: "latest-main"
keywords: [agent-sandbox, sandbox, router, gateway]
home: https://github.com/kubernetes-sigs/agent-sandbox
sources:
  - https://github.com/kubernetes-sigs/agent-sandbox
maintainers:
  - name: agent-sandbox-maintainers
```

---

## Phase 2 — `values.yaml`

```yaml
namespace: default

router:
  replicaCount: 2
  image:
    repository: ""   # REQUIRED — no default, must be set at install time
    tag: "latest"
    pullPolicy: IfNotPresent
  containerPort: 8080
  env:
    - name: PROXY_TIMEOUT_SECONDS
      value: "180"
  resources:
    requests:
      cpu: "250m"
      memory: "512Mi"
    limits:
      cpu: "1000m"
      memory: "1Gi"
  securityContext:       # pod-level, not container-level
    runAsUser: 1000
    runAsGroup: 1000
  readinessProbe:
    path: /healthz
    port: 8080
    initialDelaySeconds: 5
    periodSeconds: 5
  livenessProbe:
    path: /healthz
    port: 8080
    initialDelaySeconds: 10
    periodSeconds: 10
  topologySpreadConstraints:
    - maxSkew: 1
      topologyKey: topology.kubernetes.io/zone
      whenUnsatisfiable: ScheduleAnyway

service:
  name: sandbox-router-svc
  type: ClusterIP
  port: 8080
  targetPort: 8080
  protocol: TCP
  portName: http

httproute:
  enabled: true
  name: sandbox-router-route
  hostname: ""           # empty = match all hostnames
  parentRef:
    name: external-http-gateway
    namespace: ""        # empty = same namespace as HTTPRoute

sandboxTemplate:
  enabled: true
  name: python-sandbox-template
  namespace: default     # can differ from router namespace
  containerName: python-runtime
  image:
    repository: us-central1-docker.pkg.dev/k8s-staging-images/agent-sandbox/python-runtime-sandbox
    tag: "latest-main"
  containerPort: 8888
  runtimeClassName: gvisor
  readinessProbe:
    path: /
    port: 8888
    initialDelaySeconds: 0
    periodSeconds: 1
  livenessProbe:
    path: /
    port: 8888
    initialDelaySeconds: 2
    periodSeconds: 10
  resources:
    requests:
      cpu: "250m"
      memory: "512Mi"
      ephemeral-storage: "512Mi"   # hyphenated — must use index function in templates
  restartPolicy: OnFailure
```

---

## Phase 3 — `templates/_helpers.tpl`

Standard helpers: `name`, `fullname`, `chart`, `labels`, `selectorLabels`.

`selectorLabels` uses `app.kubernetes.io/name` and `app.kubernetes.io/instance`. This helper
must be used identically in the Deployment `matchLabels`, pod template labels, Service selector,
and `topologySpreadConstraints` labelSelector to guarantee consistency.

```
{{- define "agent-sandbox-router.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "agent-sandbox-router.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "agent-sandbox-router.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "agent-sandbox-router.labels" -}}
helm.sh/chart: {{ include "agent-sandbox-router.chart" . }}
{{ include "agent-sandbox-router.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "agent-sandbox-router.selectorLabels" -}}
app.kubernetes.io/name: {{ include "agent-sandbox-router.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

---

## Phase 4 — `templates/deployment.yaml`

Fully templated. Two critical gotchas:

- **`securityContext` is pod-level** — goes under `spec.securityContext`, not `spec.containers[0].securityContext`
- **`range` loop and `$`** — inside `{{- range .Values.router.topologySpreadConstraints }}`, `.` is
  rebound to the current item. Call helpers with `$`: `include "agent-sandbox-router.selectorLabels" $`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sandbox-router-deployment
  namespace: {{ .Values.namespace }}
  labels:
    {{- include "agent-sandbox-router.labels" . | nindent 4 }}
spec:
  replicas: {{ .Values.router.replicaCount }}
  selector:
    matchLabels:
      {{- include "agent-sandbox-router.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "agent-sandbox-router.selectorLabels" . | nindent 8 }}
    spec:
      securityContext:
        runAsUser: {{ .Values.router.securityContext.runAsUser }}
        runAsGroup: {{ .Values.router.securityContext.runAsGroup }}
      topologySpreadConstraints:
        {{- range .Values.router.topologySpreadConstraints }}
        - maxSkew: {{ .maxSkew }}
          topologyKey: {{ .topologyKey }}
          whenUnsatisfiable: {{ .whenUnsatisfiable }}
          labelSelector:
            matchLabels:
              {{- include "agent-sandbox-router.selectorLabels" $ | nindent 14 }}
        {{- end }}
      containers:
        - name: router
          image: "{{ .Values.router.image.repository }}:{{ .Values.router.image.tag }}"
          imagePullPolicy: {{ .Values.router.image.pullPolicy }}
          env:
            {{- toYaml .Values.router.env | nindent 12 }}
          ports:
            - containerPort: {{ .Values.router.containerPort }}
              protocol: TCP
          readinessProbe:
            httpGet:
              path: {{ .Values.router.readinessProbe.path }}
              port: {{ .Values.router.readinessProbe.port }}
            initialDelaySeconds: {{ .Values.router.readinessProbe.initialDelaySeconds }}
            periodSeconds: {{ .Values.router.readinessProbe.periodSeconds }}
          livenessProbe:
            httpGet:
              path: {{ .Values.router.livenessProbe.path }}
              port: {{ .Values.router.livenessProbe.port }}
            initialDelaySeconds: {{ .Values.router.livenessProbe.initialDelaySeconds }}
            periodSeconds: {{ .Values.router.livenessProbe.periodSeconds }}
          resources:
            {{- toYaml .Values.router.resources | nindent 12 }}
```

---

## Phase 5 — `templates/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Values.service.name }}
  namespace: {{ .Values.namespace }}
  labels:
    {{- include "agent-sandbox-router.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  selector:
    {{- include "agent-sandbox-router.selectorLabels" . | nindent 4 }}
  ports:
    - name: {{ .Values.service.portName }}
      protocol: {{ .Values.service.protocol }}
      port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort }}
```

---

## Phase 6 — `templates/httproute.yaml`

- Gated by `{{- if .Values.httproute.enabled }}`
- `hostnames` block omitted entirely when `httproute.hostname` is empty
- `parentRef.namespace` omitted when empty (Gateway defaults to same namespace)

```yaml
{{- if .Values.httproute.enabled }}
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: {{ .Values.httproute.name }}
  namespace: {{ .Values.namespace }}
  labels:
    {{- include "agent-sandbox-router.labels" . | nindent 4 }}
spec:
  parentRefs:
    - name: {{ .Values.httproute.parentRef.name }}
      {{- if .Values.httproute.parentRef.namespace }}
      namespace: {{ .Values.httproute.parentRef.namespace }}
      {{- end }}
  {{- if .Values.httproute.hostname }}
  hostnames:
    - {{ .Values.httproute.hostname | quote }}
  {{- end }}
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: {{ .Values.service.name }}
          port: {{ .Values.service.port }}
{{- end }}
```

---

## Phase 7 — `templates/sandbox-template.yaml`

- Gated by `{{- if .Values.sandboxTemplate.enabled }}`
- `restartPolicy` is at `spec.podTemplate.spec.restartPolicy` — pod-spec level, not inside the container
- **`ephemeral-storage` gotcha**: Go templates cannot parse hyphenated keys via dot notation.
  Must use `index` function:
  ```
  {{ index .Values.sandboxTemplate.resources.requests "ephemeral-storage" | quote }}
  ```
  Using `.Values.sandboxTemplate.resources.requests.ephemeral-storage` will cause a parse
  error at `helm lint` time.

```yaml
{{- if .Values.sandboxTemplate.enabled }}
apiVersion: extensions.agents.x-k8s.io/v1alpha1
kind: SandboxTemplate
metadata:
  name: {{ .Values.sandboxTemplate.name }}
  namespace: {{ .Values.sandboxTemplate.namespace }}
  labels:
    {{- include "agent-sandbox-router.labels" . | nindent 4 }}
spec:
  podTemplate:
    spec:
      runtimeClassName: {{ .Values.sandboxTemplate.runtimeClassName }}
      containers:
        - name: {{ .Values.sandboxTemplate.containerName }}
          image: "{{ .Values.sandboxTemplate.image.repository }}:{{ .Values.sandboxTemplate.image.tag }}"
          ports:
            - containerPort: {{ .Values.sandboxTemplate.containerPort }}
          readinessProbe:
            httpGet:
              path: {{ .Values.sandboxTemplate.readinessProbe.path | quote }}
              port: {{ .Values.sandboxTemplate.readinessProbe.port }}
            initialDelaySeconds: {{ .Values.sandboxTemplate.readinessProbe.initialDelaySeconds }}
            periodSeconds: {{ .Values.sandboxTemplate.readinessProbe.periodSeconds }}
          livenessProbe:
            httpGet:
              path: {{ .Values.sandboxTemplate.livenessProbe.path | quote }}
              port: {{ .Values.sandboxTemplate.livenessProbe.port }}
            initialDelaySeconds: {{ .Values.sandboxTemplate.livenessProbe.initialDelaySeconds }}
            periodSeconds: {{ .Values.sandboxTemplate.livenessProbe.periodSeconds }}
          resources:
            requests:
              cpu: {{ index .Values.sandboxTemplate.resources.requests "cpu" | quote }}
              memory: {{ index .Values.sandboxTemplate.resources.requests "memory" | quote }}
              ephemeral-storage: {{ index .Values.sandboxTemplate.resources.requests "ephemeral-storage" | quote }}
      restartPolicy: {{ .Values.sandboxTemplate.restartPolicy }}
{{- end }}
```

---

## Phase 8 — `tests/test_router.py`

pytest-based. `scope="module"` fixture installs/uninstalls once for all tests.

**Environment variables:**
- `ROUTER_IMAGE` — required, full image repository path
- `NAMESPACE` — defaults to `default`
- `RELEASE_NAME` — defaults to `test-router`
- `ROUTER_GATEWAY_URL` — if set, `/healthz` check uses this URL; otherwise uses port-forward

**Tests:**
1. `test_deployment_ready` — `kubectl rollout status deployment/sandbox-router-deployment`
2. `test_httproute_accepted` — `kubectl get httproute sandbox-router-route -o json`, assert `status.parents[0].conditions[Accepted].status == "True"`
3. `test_sandbox_template_exists` — `kubectl get sandboxtemplate python-sandbox-template`
4. `test_healthz_returns_200` — `curl` to `/healthz` via port-forward (`localhost:18080`) or `ROUTER_GATEWAY_URL`

Chart path in test file: `os.path.join(os.path.dirname(__file__), "..")` (repo root).

---

## Phase 9 — `.github/workflows/helm-release.yaml`

Triggers on `v*` tags only.

```yaml
name: Helm Release

on:
  push:
    tags:
      - 'v*'

permissions:
  packages: write
  contents: read

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: azure/setup-helm@v4
        with:
          version: 'latest'

      - name: Login to GHCR
        run: |
          echo "${{ secrets.GITHUB_TOKEN }}" | helm registry login ghcr.io \
            --username "${{ github.actor }}" \
            --password-stdin

      - name: Lint
        run: helm lint .

      - name: Package
        run: helm package .

      - name: Push to GHCR
        run: helm push *.tgz oci://ghcr.io/${{ github.repository_owner }}/charts
```

> `helm push` takes the base collection path only — do not append `/agent-sandbox-router`.
> Helm derives the chart name from the `.tgz` filename automatically.

---

## Phase 10 — `docs/README.md`

Minimal docs covering prerequisites, install command, and a values reference table for all
top-level keys.

---

## Phase 11 — Validation

Run after all files are created:

```sh
# 1. Lint
helm lint .

# 2. Full template render
helm template test . --set router.image.repository=example.com/router --debug

# 3. Verify optional resources can be disabled
helm template test . \
  --set router.image.repository=example.com/router \
  --set httproute.enabled=false \
  --set sandboxTemplate.enabled=false

# 4. Package
helm package .
```

Expected: `helm lint` reports `1 chart(s) linted, 0 chart(s) failed`. All 4 resource kinds
appear in step 2. Only `Deployment` and `Service` in step 3.

---

## Key Gotchas

| # | Gotcha | Detail |
|---|--------|--------|
| 1 | `ephemeral-storage` hyphen | Use `index .Values... "ephemeral-storage"` — dot notation causes a parse error |
| 2 | `range` loop and `$` | Inside `range`, `.` is the loop item; use `$` to call named templates |
| 3 | `securityContext` is pod-level | Goes under `spec.securityContext`, not `spec.containers[0].securityContext` |
| 4 | `restartPolicy` placement | `spec.podTemplate.spec.restartPolicy`, not inside the container block |
| 5 | Service selector | Must use same `selectorLabels` helper as Deployment pod labels |
| 6 | `router.image.repository` has no default | Operators must supply it; `helm lint` will succeed but `helm install` without it will produce an invalid image ref |
| 7 | OCI push path | `oci://ghcr.io/OWNER/charts` only — Helm appends chart name from the `.tgz` automatically |
| 8 | Gateway is pre-existing infrastructure | The chart only creates the HTTPRoute; the Gateway must already exist in the cluster |
| 9 | SandboxTemplate namespace | Defaults to `default`, independent of `namespace` (router namespace) |
