# IDA Proxy Helm Chart

This chart deploys an nginx-based proxy that routes traffic from allocated proxy ports to user IDA workstations.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Kubernetes Cluster                         │
│                                                                    │
│  ┌─────────────┐    ┌─────────────────────────────────────────┐  │
│  │ MCP Client  │───▶│           IDA Proxy (nginx)              │  │
│  │ Controller  │    │                                          │  │
│  └─────────────┘    │  Port 9001 → userA.corp.local:9100      │  │
│        │            │  Port 9002 → userB.corp.local:9100      │  │
│        │            │  Port 9003 → userC.corp.local:9100      │  │
│        ▼            └────────────────────┬────────────────────┘  │
│  ┌─────────────┐                         │                        │
│  │ ConfigMaps  │                         │                        │
│  │ - port_map  │                         │                        │
│  │ - listen_   │                         │                        │
│  │   ports     │                         │                        │
│  └─────────────┘                         │                        │
└──────────────────────────────────────────┼────────────────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      ▼                      │
                    │    ┌─────────┐  ┌─────────┐  ┌─────────┐   │
                    │    │ UserA   │  │ UserB   │  │ UserC   │   │
                    │    │ IDA     │  │ IDA     │  │ IDA     │   │
                    │    │ :9100   │  │ :9100   │  │ :9100   │   │
                    │    └─────────┘  └─────────┘  └─────────┘   │
                    │              Corporate Network              │
                    └─────────────────────────────────────────────┘
```

## Installation

```bash
# Install with default values
helm install ida-proxy ./charts/ida-proxy

# Install with custom DNS servers
helm install ida-proxy ./charts/ida-proxy \
  --set dns.servers[0]=10.0.0.53 \
  --set dns.servers[1]=10.0.0.54

# Install with initial port mappings
helm install ida-proxy ./charts/ida-proxy \
  --set initialPortMappings[0].proxyPort=9001 \
  --set initialPortMappings[0].upstreamHost=userA.corp.local \
  --set initialPortMappings[0].upstreamPort=9100
```

## Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.repository` | Nginx image repository | `nginx` |
| `image.tag` | Nginx image tag | `alpine` |
| `replicaCount` | Number of proxy replicas | `1` |
| `portRange.start` | First port in proxy range | `9001` |
| `portRange.end` | Last port in proxy range | `9100` |
| `dns.servers` | DNS servers for hostname resolution | `[10.0.0.53, 10.0.0.54]` |
| `dns.resolverValid` | DNS cache TTL | `30s` |
| `proxy.connectTimeout` | Proxy connection timeout | `2s` |
| `proxy.readTimeout` | Proxy read timeout | `60s` |
| `proxy.sendTimeout` | Proxy send timeout | `60s` |

## ConfigMap Management

The MCP Client controller automatically manages two ConfigMaps:

### `ida-proxy-listen-ports`
Contains the nginx `listen` directives:
```
listen 9001;
listen 9002;
listen 9003;
```

### `ida-proxy-port-map`
Contains the port-to-upstream mappings:
```
9001          userA.corp.local:9100;
9002          userB.corp.local:9100;
9003          userC.corp.local:9100;
```

## Nginx Reload

When ConfigMaps are updated, the controller either:
1. Sends `nginx -s reload` to the pod (graceful reload)
2. Falls back to restarting the deployment if reload fails

## Health Checks

- **Liveness**: `GET /health` on port 8080
- **Readiness**: `GET /ready` on port 8080

## Security Considerations

1. DNS servers must be able to resolve user workstation hostnames
2. Network policies should restrict who can access proxy ports
3. Consider mTLS for connections to user workstations

## Troubleshooting

### Check nginx configuration
```bash
kubectl exec -it deploy/ida-proxy -- nginx -t
```

### View current port mappings
```bash
kubectl get configmap ida-proxy-port-map -o yaml
```

### Check nginx logs
```bash
kubectl logs -l app=ida-mcp,component=proxy -f
```

### Test connectivity
```bash
kubectl run test --rm -it --image=curlimages/curl -- curl http://ida-proxy:9001/health
```
