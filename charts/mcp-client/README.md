# MCP Client Kubernetes Deployment

This Helm chart deploys the MCP Client application with PostgreSQL database support, user authentication, and comprehensive user management features.

## Features

- **FastAPI Backend** with comprehensive REST API
- **PostgreSQL Database** with flexible storage options
- **JWT Authentication** with user management
- **React Frontend** with beautiful login animations
- **Admin Dashboard** for user management
- **Test Configuration Storage** with database backend
- **Activity Logging** and session management

## Quick Start

### Development Installation
```bash
helm install mcp-client ./charts/mcp-client -f values-dev.yaml
```

### Production Installation
```bash
helm install mcp-client ./charts/mcp-client -f values-prod.yaml
```

### Custom Installation
```bash
helm install mcp-client ./charts/mcp-client \
  --set postgres.password="your-secure-password" \
  --set auth.jwtSecret="your-jwt-secret"
```

## Configuration Values

### Application Settings
| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.repository` | Docker image repository | `mcp-client` |
| `image.tag` | Docker image tag | `latest` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `replicaCount` | Number of replicas | `1` |
| `client.host` | Application host | `0.0.0.0` |
| `client.port` | Application port | `8000` |

### Environment Variables
| Parameter | Description | Default |
|-----------|-------------|---------|
| `env.MCP_SERVER_URL` | MCP Server URL | `http://localhost:8050/mcp/` |
| `env.LLM_API_URL` | LLM API URL | `https://api.openai.com/v1` |
| `env.LLM_MODEL` | LLM Model | `gpt-4` |
| `env.LLM_API_KEY` | LLM API Key | `""` (set via secret) |
| `env.LOG_LEVEL` | Logging level | `INFO` |

### Resources
| Parameter | Description | Default |
|-----------|-------------|---------|
| `resources.limits.cpu` | CPU limit | `1000m` |
| `resources.limits.memory` | Memory limit | `1Gi` |
| `resources.requests.cpu` | CPU request | `500m` |
| `resources.requests.memory` | Memory request | `512Mi` |

### Service Configuration
| Parameter | Description | Default |
|-----------|-------------|---------|
| `service.type` | Service type | `ClusterIP` |
| `service.port` | Service port | `8000` |
| `service.targetPort` | Target port | `8000` |

### PostgreSQL Configuration
| Parameter | Description | Default |
|-----------|-------------|---------|
| `postgres.database` | Database name | `mcp_client` |
| `postgres.username` | Database username | `mcp_user` |
| `postgres.password` | Database password | `McpClient2025!SecurePassword` |
| `postgres.persistence.enabled` | Enable persistence | `true` |
| `postgres.persistence.size` | Storage size | `10Gi` |
| `postgres.persistence.storageClass` | Storage class | `""` (host path) |
| `postgres.persistence.hostPath` | Host path for storage | `/data/mcp-client-postgres` |

### Authentication Settings
| Parameter | Description | Default |
|-----------|-------------|---------|
| `auth.jwtSecret` | JWT secret key | `your-super-secret-jwt-key-change-in-production` |
| `auth.accessTokenExpire` | Access token expiry (seconds) | `3600` |
| `auth.refreshTokenExpire` | Refresh token expiry (seconds) | `604800` |
| `auth.admin.username` | Default admin username | `admin` |
| `auth.admin.password` | Default admin password | `admin123` |
| `auth.admin.email` | Default admin email | `admin@mcp-client.local` |

### Feature Flags
| Parameter | Description | Default |
|-----------|-------------|---------|
| `features.enableUserRegistration` | Allow user registration | `true` |
| `features.enableGuestAccess` | Allow guest access | `false` |
| `features.enableMetrics` | Enable metrics | `true` |
| `features.enableTracing` | Enable tracing | `false` |

### Ingress Configuration
| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingress.enabled` | Enable ingress | `false` |
| `ingress.className` | Ingress class | `""` |
| `ingress.hosts[0].host` | Hostname | `mcp-client.local` |

### Autoscaling
| Parameter | Description | Default |
|-----------|-------------|---------|
| `autoscaling.enabled` | Enable autoscaling | `false` |
| `autoscaling.minReplicas` | Minimum replicas | `1` |
| `autoscaling.maxReplicas` | Maximum replicas | `10` |
| `autoscaling.targetCPUUtilizationPercentage` | CPU target | `80` |

## PostgreSQL Storage Configuration

The chart supports flexible storage options for PostgreSQL data persistence:

### Option 1: Using Storage Classes (Recommended for Production)

If you have a storage class available in your cluster:

```yaml
postgres:
  persistence:
    enabled: true
    size: 10Gi
    storageClass: "fast-ssd"  # Your storage class name
```

### Option 2: Host Path Storage (Development/Local)

If you don't have a storage class, the chart will automatically create a PersistentVolume using host path:

```yaml
postgres:
  persistence:
    enabled: true
    size: 10Gi
    storageClass: ""  # Empty or comment out
    hostPath: "/data/mcp-client-postgres"  # Host directory for data
    nodeSelector: ""  # Optional: specific node to run on
```

## Deployment Examples

### 1. Development Environment
```bash
# Quick development setup
helm install mcp-client ./charts/mcp-client -f values-dev.yaml

# With custom settings
helm install mcp-client ./charts/mcp-client \
  --set env.LOG_LEVEL="DEBUG" \
  --set postgres.persistence.size="2Gi" \
  --set features.enableGuestAccess=true
```

### 2. Production Environment
```bash
# Production deployment
helm install mcp-client ./charts/mcp-client -f values-prod.yaml

# With secrets
helm install mcp-client ./charts/mcp-client \
  --set postgres.password="$(kubectl get secret db-secret -o jsonpath='{.data.password}' | base64 -d)" \
  --set auth.jwtSecret="$(openssl rand -base64 32)" \
  --set postgres.persistence.storageClass="fast-ssd"
```

### 3. Custom Configuration
```bash
helm install mcp-client ./charts/mcp-client \
  --set replicaCount=3 \
  --set resources.limits.memory="2Gi" \
  --set postgres.persistence.size="50Gi" \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host="mcp.your-domain.com"
```

## Default Credentials

**⚠️ SECURITY WARNING**: Change these immediately in production!

- **Admin User**: `admin` / `admin123`
- **Database**: `mcp_user` / `McpClient2025!SecurePassword`
- **JWT Secret**: `your-super-secret-jwt-key-change-in-production`

## File Structure

The PostgreSQL deployment is split into separate files for better organization:

- `postgres-deployment.yaml` - PostgreSQL Deployment
- `postgres-service.yaml` - PostgreSQL Service
- `postgres-pvc.yaml` - PersistentVolume and PersistentVolumeClaim
- `postgres-secret.yaml` - PostgreSQL credentials

## Post-Installation

1. **Get the application URL**:
```bash
kubectl get ingress mcp-client
# OR for LoadBalancer/NodePort:
kubectl get service mcp-client
```

2. **Access the admin panel**:
   - Login with `admin` / `admin123`
   - Navigate to the "Users" tab for user management

3. **Change default passwords**:
   - Update admin password in the UI
   - Update database password via Helm upgrade

4. **Monitor the deployment**:
```bash
kubectl get pods -l app.kubernetes.io/name=mcp-client
kubectl logs -l app.kubernetes.io/name=mcp-client -f
```

## Troubleshooting

### Common Issues

1. **Pod not starting**: Check resource limits and node capacity
2. **Database connection failed**: Verify postgres pod is running
3. **Storage issues**: Check PV/PVC status and storage class availability
4. **Authentication errors**: Verify JWT secret configuration

### Useful Commands
```bash
# Check all resources
kubectl get all -l app.kubernetes.io/name=mcp-client

# View logs
kubectl logs deployment/mcp-client -f

# Check database
kubectl exec -it deployment/mcp-client-postgres -- psql -U mcp_user -d mcp_client

# Port forward for local access
kubectl port-forward service/mcp-client 8000:8000
```
