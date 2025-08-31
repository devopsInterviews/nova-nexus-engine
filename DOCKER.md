# Docker Development Setup 🐳

This document provides comprehensive instructions for running MCP Client using Docker Compose for fast development deployment.

## 🚀 Quick Start

### Prerequisites
- Docker Desktop (Windows/Mac) or Docker Engine + Docker Compose (Linux)
- Git

### 1. Clone and Setup
```bash
git clone <repository-url>
cd mcp-client
cp .env.example .env
```

### 2. Start Development Environment
```bash
# Basic setup (recommended for development)
docker-compose up --build

# Or use the helper script (Linux/Mac)
./scripts/dev-start.sh basic

# Windows
.\scripts\dev-start.bat basic
```

### 3. Access the Application
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000  
- **API Documentation**: http://localhost:8000/docs
- **Database**: localhost:5432

## 📋 Available Profiles

The docker-compose setup uses profiles to provide different deployment configurations:

### Default Profile (Basic Development)
```bash
docker-compose up
```
**Includes**: PostgreSQL + Backend + Frontend
**Best for**: Day-to-day development

### Full Profile (With Caching)
```bash
docker-compose --profile full up
```
**Includes**: PostgreSQL + Backend + Frontend + Redis
**Best for**: Performance testing, caching features

### Nginx Profile (Production-like)
```bash
docker-compose --profile nginx up
```
**Includes**: Basic setup + Nginx reverse proxy
**Best for**: Testing production-like routing
**Access**: http://localhost:80

### MCP Profile (With Mock Server)
```bash
docker-compose --profile mcp up
```
**Includes**: Basic setup + Mock MCP server
**Best for**: Testing MCP integrations

### All Services
```bash
docker-compose --profile full --profile nginx --profile mcp up
```
**Includes**: Everything
**Best for**: Full system testing

## 🛠️ Helper Scripts

### Linux/Mac
```bash
# Start different configurations
./scripts/dev-start.sh basic    # Basic development setup
./scripts/dev-start.sh full     # With Redis
./scripts/dev-start.sh nginx    # With Nginx proxy
./scripts/dev-start.sh mcp      # With MCP server
./scripts/dev-start.sh all      # All services

# Management commands
./scripts/dev-start.sh stop     # Stop all services
./scripts/dev-start.sh clean    # Remove containers and volumes
./scripts/dev-start.sh logs     # View logs
./scripts/dev-start.sh status   # Check service status
```

### Windows
```cmd
REM Start different configurations
.\scripts\dev-start.bat basic   REM Basic development setup
.\scripts\dev-start.bat full    REM With Redis
.\scripts\dev-start.bat nginx   REM With Nginx proxy
.\scripts\dev-start.bat mcp     REM With MCP server
.\scripts\dev-start.bat all     REM All services

REM Management commands
.\scripts\dev-start.bat stop    REM Stop all services
.\scripts\dev-start.bat clean   REM Remove containers and volumes
.\scripts\dev-start.bat logs    REM View logs
.\scripts\dev-start.bat status  REM Check service status
```

## 🔧 Configuration

### Environment Variables
Copy `.env.example` to `.env` and customize:

```bash
# Database
DATABASE_NAME=mcp_client
DATABASE_USER=nova_user
DATABASE_PASSWORD=NovaNextDevPassword2025!

# Ports
BACKEND_PORT=8000
FRONTEND_PORT=5173
DATABASE_PORT=5432

# Authentication
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=120

# External Services
MCP_SERVER_URL=http://mcp-server:8050/mcp/
```

### Volume Mounts
- **Backend**: Source code is mounted for hot reload
- **Frontend**: Source code is mounted for Vite HMR
- **Database**: Data persisted in named volume `mcp-client-postgres-data`
- **Redis**: Data persisted in named volume `nova-nexus-redis-data`

## 🐛 Development Features

### Hot Reload
- **Backend**: Uses `uvicorn --reload` for automatic Python code reloading
- **Frontend**: Vite HMR for instant React component updates
- **Watch Mode**: Docker Compose watch mode for automatic rebuilds

### Live Logs
```bash
# View all service logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres
```

### Database Access
```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U nova_user mcp_client

# Run SQL files
docker-compose exec postgres psql -U nova_user mcp_client -f /path/to/file.sql

# Backup database
docker-compose exec postgres pg_dump -U nova_user mcp_client > backup.sql

# Restore database
docker-compose exec -T postgres psql -U nova_user mcp_client < backup.sql
```

### Redis Access (when using full profile)
```bash
# Connect to Redis CLI
docker-compose exec redis redis-cli

# Monitor Redis commands
docker-compose exec redis redis-cli monitor
```

## 🔍 Troubleshooting

### Common Issues

#### Port Conflicts
If you get port binding errors:
```bash
# Check what's using the port
netstat -tulpn | grep :8000  # Linux
netstat -ano | findstr :8000  # Windows

# Change ports in .env file
BACKEND_PORT=8001
FRONTEND_PORT=5174
```

#### Database Connection Issues
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Reset database
docker-compose down -v
docker-compose up postgres
```

#### Build Issues
```bash
# Clean rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up

# Remove all containers and images
docker-compose down --rmi all -v --remove-orphans
```

#### Permission Issues (Linux/Mac)
```bash
# Fix file permissions
sudo chown -R $USER:$USER .
chmod +x scripts/dev-start.sh
```

### Performance Issues

#### Slow Build Times
- Enable Docker BuildKit: `export DOCKER_BUILDKIT=1`
- Use `.dockerignore` to exclude unnecessary files
- Consider multi-stage builds for production

#### Memory Usage
```bash
# Check Docker resource usage
docker stats

# Clean up unused resources
docker system prune -f
docker volume prune -f
```

## 📊 Health Checks

All services include health checks:

```bash
# Check service health
docker-compose ps

# View health check details
docker inspect <container_name> | grep -A 10 Health
```

### Health Check Endpoints
- **Backend**: http://localhost:8000/api/health
- **Frontend**: http://localhost:5173 (Vite dev server)
- **Nginx**: http://localhost:80/health
- **PostgreSQL**: Internal `pg_isready` check
- **Redis**: Internal `redis-cli ping` check

## 🔒 Security Considerations

### Development Environment
- Default credentials are used for convenience
- HTTPS is not enabled (use nginx-ssl for SSL)
- Debug mode is enabled
- All ports are exposed to localhost

### Production Deployment
- Change all default passwords
- Use strong JWT secrets
- Enable HTTPS
- Configure proper firewall rules
- Use secrets management
- Regular security updates

## 🚀 Production Deployment

While this docker-compose setup is optimized for development, you can create a production variant:

1. Create `docker-compose.prod.yml`
2. Use production Dockerfile stages
3. Configure environment secrets
4. Set up proper networking
5. Add monitoring and logging
6. Configure backups

## 📝 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Docker Best Practices](https://docs.docker.com/develop/best-practices/)
- [FastAPI in Docker](https://fastapi.tiangolo.com/deployment/docker/)
- [React Development with Docker](https://create-react-app.dev/docs/deployment/)

## 🤝 Contributing

When working with the Docker setup:

1. Test changes with different profiles
2. Update documentation for new services
3. Ensure health checks work properly
4. Test on different platforms (Windows/Mac/Linux)
5. Update environment variable examples

## 📞 Support

If you encounter issues with the Docker setup:

1. Check the troubleshooting section above
2. Review Docker and Docker Compose logs
3. Ensure your Docker version is up to date
4. Check system resources (RAM, disk space)
5. Create an issue with detailed logs and system info
