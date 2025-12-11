# Kubernetes Agent Platform

A production-grade AI agent platform for Kubernetes troubleshooting and management, built with MCP (Model Context Protocol) integration.

## Overview

This platform hosts AI agents that can interact with Kubernetes clusters through MCP servers and other tools. The initial use case is a Kubernetes troubleshooting agent that uses an existing FastMCP-based K8s MCP server.

## Architecture

### Technology Stack

**Backend:**
- **FastAPI** - Modern async Python web framework
- **Pydantic AI** - Type-safe AI agent framework with validation
- **FastMCP** - MCP client for connecting to MCP servers
- **PostgreSQL + pgvector** - Single database for both relational data and vector embeddings
- **asyncpg** - Fast PostgreSQL adapter for async operations

**Frontend:**
- **Streamlit** - Pure Python UI for rapid development (starting point)
- **React + TypeScript** - Future migration for production-grade UI

**AI Models:**
- Primary: Anthropic Claude (claude-3-5-sonnet)
- Embedding: OpenAI text-embedding-ada-002

### Key Design Decisions

1. **Single Database**: PostgreSQL with pgvector extension handles both relational data and vector search (no separate vector store needed)

2. **No Queue Initially**: FastAPI's async capabilities are sufficient; Celery/Redis queue added later only if needed for:
   - Long-running tasks (5+ minutes)
   - Scheduled background jobs
   - Complex multi-step workflows

3. **FastMCP Over MCP SDK**: Using FastMCP for simpler, more Pythonic API since existing K8s MCP server already uses it

4. **Streamlit First**: Starting with Streamlit for rapid MVP, migrating to React later for production features

5. **Raw SQL with asyncpg (No ORM)**: Using asyncpg directly instead of SQLAlchemy for:
   - Simpler stack with fewer dependencies
   - Better performance (no ORM overhead)
   - Full control over queries
   - Straightforward schema fits well with raw SQL
   - Add SQLAlchemy later only if complex relationships or automatic migrations become necessary

6. **Single Container for Backend + Frontend**: Running both FastAPI and Streamlit in same container for:
   - Simpler deployment and management
   - Single Dockerfile and deployment manifest
   - Easier local development
   - No inter-service networking complexity
   - Split into separate containers later only if needed for independent scaling or React migration

## Project Structure

```
agent-platform/
├── app/
│   ├── backend/
│   │   ├── main.py                 # FastAPI application
│   │   ├── config.py               # Configuration settings
│   │   ├── db/
│   │   │   ├── schema.sql          # Database schema (DDL)
│   │   │   └── database.py         # Database connection pool
│   │   ├── services/
│   │   │   ├── mcp_manager.py      # MCP server connection management
│   │   │   └── rag_service.py      # Vector search and RAG
│   │   └── agents/
│   │       └── k8s_agent.py        # Kubernetes troubleshooting agent
│   └── frontend/
│       └── streamlit_app.py        # Streamlit chat interface
├── k8s/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   └── secrets.yaml
├── requirements.txt
├── Dockerfile
├── start.sh                         # Startup script for both services
└── README.md
```

---

## Development Workflow

### Local Development (Recommended)

**Daily Development Loop:**
1. Make code changes
2. FastAPI auto-reloads (`--reload` flag)
3. Streamlit auto-reloads (watches file changes)
4. Test in browser immediately
5. Iterate quickly

**Advantages of Local Development:**
- ✅ Instant feedback (no container rebuild)
- ✅ Easy debugging with breakpoints
- ✅ Direct database access for inspection
- ✅ Fast iteration cycle
- ✅ No Docker/Kubernetes complexity during development

**When to Use Containers:**
- Testing production-like environment
- Validating Dockerfile changes
- Before deploying to cluster
- CI/CD pipeline

### Testing Strategy

**Unit Tests:**
```bash
pytest app/backend/tests/
```

**Integration Tests:**
```bash
# Test with real database
pytest app/backend/tests/integration/
```

**Manual Testing:**
- Use Streamlit UI for end-to-end testing
- Use FastAPI docs at http://localhost:8000/docs for API testing
- Test MCP server integration with real K8s cluster

**Container Testing (Before K8s Deployment):**
```bash
# Build and test locally
docker build -t agent-platform:test .
docker run -p 8000:8000 -p 8501:8501 \
  -e DATABASE_URL=postgresql://... \
  agent-platform:test
```

---

## Database Schema

### Core Tables

**users**
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**mcp_servers**
```sql
CREATE TABLE mcp_servers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(50), -- 'stdio', 'sse', 'websocket'
    command VARCHAR(255),
    args JSONB, -- List of command args
    env JSONB, -- Environment variables
    available_tools JSONB, -- Cached list of tools
    status VARCHAR(50) DEFAULT 'disconnected',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**agent_configs**
```sql
CREATE TABLE agent_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    model VARCHAR(255), -- 'anthropic:claude-3-5-sonnet'
    system_prompt TEXT,
    mcp_server_ids JSONB, -- List of MCP server IDs
    tools_enabled JSONB, -- List of tool names
    temperature FLOAT DEFAULT 0.7,
    max_tokens INTEGER,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**conversations**
```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    agent_config_id UUID REFERENCES agent_configs(id),
    title VARCHAR(255),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**messages**
```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id),
    role VARCHAR(50), -- 'user', 'assistant', 'system'
    content TEXT,
    tool_calls JSONB, -- Record of tools used
    metadata JSONB,
    embedding VECTOR(1536), -- OpenAI ada-002 dimension
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_embedding ON messages USING ivfflat (embedding vector_cosine_ops);
```

**documents**
```sql
-- For RAG: K8s docs, runbooks, etc.
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255),
    content TEXT,
    source VARCHAR(255), -- URL or file path
    doc_type VARCHAR(50), -- 'k8s_doc', 'runbook', 'alert'
    metadata JSONB,
    embedding VECTOR(1536),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_documents_type ON documents(doc_type);
```

**audit_logs**
```sql
-- Track all agent actions and tool calls
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    conversation_id UUID REFERENCES conversations(id),
    action_type VARCHAR(50), -- 'tool_call', 'agent_run', 'mcp_connect'
    tool_name VARCHAR(255),
    parameters JSONB,
    result JSONB,
    success BOOLEAN,
    error TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created ON audit_logs(created_at);
```

### Vector Search with pgvector

PostgreSQL with pgvector extension provides:
- Cosine similarity search on embeddings
- RAG for K8s documentation
- Semantic search across past conversations
- Single database for all data types

## Implementation Plan

### Development Approach

**Phase 1-3: Local Development & Testing (Weeks 1-3)**
- Build and test everything locally first
- Use local PostgreSQL instance
- Run services directly with Python (no containers initially)
- Iterate quickly without Docker/Kubernetes complexity

**Phase 4: Containerization & Deployment (Week 4+)**
- Create Dockerfile once application is stable
- Build and test container locally
- Deploy to Kubernetes cluster
- Production hardening

### Phase 1: Backend Foundation (Week 1-2)

**Goals:**
- Set up FastAPI application structure
- Configure PostgreSQL with pgvector locally
- Create database schema with SQL migrations
- Build MCP Manager for server connections
- Implement basic API endpoints

**Key Components:**
1. Database setup with pgvector extension on local PostgreSQL
2. Connection pool with asyncpg
3. SQL schema and migration scripts
4. MCPManager service for connecting to MCP servers
5. FastAPI endpoints: `/api/chat`, `/api/mcp-servers`, `/api/conversations`
6. Basic error handling and logging

**Testing:** All local Python, no containers needed yet

### Phase 2: MCP Integration & Agent (Week 2-3)

**Goals:**
- Connect to existing K8s MCP server
- Create Pydantic AI agent with MCP tools
- Implement streaming responses
- Add RAG for K8s documentation

**Key Components:**
1. MCPManager connecting to K8s MCP server via stdio
2. Dynamic tool registration from MCP server to Pydantic AI
3. Agent with system prompt and K8s expertise
4. RAG service for searching documentation
5. Streaming agent responses

**Testing:** Run locally, test agent with real K8s cluster via MCP

### Phase 3: Streamlit Frontend (Week 3)

**Goals:**
- Build chat interface
- MCP server management UI
- Conversation history
- Real-time streaming

**Key Components:**
1. Chat interface with message history
2. Sidebar for MCP server status
3. Streaming responses from backend
4. Session state management

**Testing:** Run both FastAPI and Streamlit locally, test end-to-end

### Phase 4: Containerization & Kubernetes (Week 4+)

**Goals:**
- Create Dockerfile for production deployment
- Build and test container locally
- Create Kubernetes manifests
- Deploy to cluster
- Production configuration

**Key Components:**
1. Dockerfile with multi-stage build
2. start.sh for running both services
3. Kubernetes deployment, service, ingress manifests
4. ConfigMaps and Secrets
5. Health checks and resource limits
6. CI/CD pipeline for automated builds

**Testing:** 
- Test container locally with `docker run`
- Deploy to dev/staging namespace first
- Validate in production

## API Endpoints

### Chat
- `POST /api/chat` - Send message, get response
- `POST /api/chat/stream` - Streaming agent response

### MCP Servers
- `GET /api/mcp-servers` - List all MCP servers
- `POST /api/mcp-servers` - Register new MCP server
- `GET /api/mcp-servers/{id}` - Get server details
- `DELETE /api/mcp-servers/{id}` - Remove MCP server
- `GET /api/mcp-servers/{id}/tools` - List available tools

### Conversations
- `GET /api/conversations` - List user's conversations
- `GET /api/conversations/{id}` - Get conversation with messages
- `DELETE /api/conversations/{id}` - Delete conversation

### Agents
- `GET /api/agents` - List available agent configs
- `POST /api/agents` - Create new agent config

## MCP Integration Architecture

### MCPManager Service

**Responsibilities:**
- Manage connections to multiple MCP servers
- List available tools from connected servers
- Route tool calls to appropriate MCP servers
- Handle connection lifecycle (connect, disconnect, reconnect)

**Connection Types:**
- stdio: Launch process and communicate via stdin/stdout
- SSE: Server-sent events over HTTP
- WebSocket: Bidirectional communication

### Agent-MCP Integration

**Flow:**
1. MCPManager connects to MCP server (e.g., K8s server)
2. Retrieve available tools from MCP server
3. Dynamically register tools with Pydantic AI agent
4. User sends prompt to agent
5. Agent decides which tools to use
6. MCPManager routes tool calls to appropriate MCP server
7. Agent synthesizes results and responds

## RAG Implementation

### Document Ingestion
1. Load K8s documentation, runbooks, alerts
2. Generate embeddings using OpenAI ada-002
3. Store in PostgreSQL with pgvector

### Search Flow
1. User query → generate embedding
2. Cosine similarity search in PostgreSQL
3. Return top-k relevant documents
4. Include in agent context

### Use Cases
- Search K8s documentation
- Find similar past issues
- Reference runbooks during troubleshooting
- Learn from historical solutions

## Development Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 16+ with pgvector
- Docker & Docker Compose (optional)
- OpenAI API key
- Anthropic API key

### Quick Start (Local Development)

**Initial Setup:**
```bash
# 1. Clone repository
git clone <repository>
cd agent-platform

# 2. Install PostgreSQL locally (if not already installed)
# macOS: brew install postgresql pgvector
# Ubuntu: apt-get install postgresql postgresql-contrib
# Then start PostgreSQL service

# 3. Create database and enable pgvector
createdb agent_platform
psql agent_platform -c "CREATE EXTENSION vector;"

# 4. Run database schema
psql agent_platform -f app/backend/db/schema.sql

# 5. Install Python dependencies
pip install -r requirements.txt

# 6. Set environment variables
export DATABASE_URL=postgresql://localhost:5432/agent_platform
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export K8S_MCP_SERVER_PATH=/path/to/your/k8s_mcp_server.py
```

**Run Application Locally:**
```bash
# Terminal 1: Run FastAPI backend
uvicorn app.backend.main:app --reload --port 8000

# Terminal 2: Run Streamlit frontend
streamlit run app/frontend/streamlit_app.py --server.port 8501

# Access the application:
# - Streamlit UI: http://localhost:8501
# - FastAPI docs: http://localhost:8000/docs
```

**Run with Single Script (Alternative):**
```bash
# Run both services together
chmod +x start.sh
./start.sh
```

---

### Kubernetes Deployment (After Local Testing)

**When ready to deploy to cluster:**

```bash
# 1. Build Docker image
docker build -t your-registry/agent-platform:latest .

# 2. Test container locally first
docker run -p 8000:8000 -p 8501:8501 \
  -e DATABASE_URL=postgresql://... \
  -e OPENAI_API_KEY=sk-... \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  your-registry/agent-platform:latest

# 3. Push to registry
docker push your-registry/agent-platform:latest

# 4. Create Kubernetes secrets
kubectl create secret generic agent-secrets \
  --from-literal=database-url=postgresql://... \
  --from-literal=openai-api-key=sk-... \
  --from-literal=anthropic-api-key=sk-ant-...

# 5. Deploy to Kubernetes
kubectl apply -f k8s/

# 6. Verify deployment
kubectl get pods
kubectl logs -f deployment/agent-platform

# 7. Access via port-forward (for testing)
kubectl port-forward svc/agent-platform 8501:8501
# Open http://localhost:8501

# 8. Or access via Ingress (production)
kubectl get ingress
# Use the ingress URL
```

### Deployment

**Containerization:**
- Single Docker image containing both FastAPI backend and Streamlit frontend
- Multi-stage build for optimized image size
- Startup script runs both services in same container
- Deploy to Kubernetes cluster

**Kubernetes Resources:**
- Single Deployment running both backend (port 8000) and frontend (port 8501)
- Service exposing both ports
- Ingress for external access with path-based routing
- ConfigMaps for configuration
- Secrets for API keys and database credentials
- PostgreSQL deployed separately or managed service (RDS, CloudSQL)

**Future Separation:**
Split into separate containers when you need:
- Independent scaling of API vs UI
- Different update frequencies
- Migration to React frontend
- Separate team ownership

## Kubernetes Deployment

### Container Image

**Single Dockerfile:**
- Multi-stage build for optimized image size
- Python 3.11 slim base image
- Install all dependencies (FastAPI, Streamlit, asyncpg, pgvector, pydantic-ai, fastmcp)
- Copy both backend and frontend application code
- Expose ports 8000 (FastAPI) and 8501 (Streamlit)
- Use start.sh script to run both services

**start.sh:**
```bash
#!/bin/bash
# Start FastAPI in background
uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 &
# Start Streamlit in foreground
streamlit run app/frontend/streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

### Kubernetes Resources

**deployment.yaml**
- Deployment with 2-3 replicas for high availability
- Resource requests/limits for CPU and memory
- Liveness probe on port 8501 (Streamlit)
- Readiness probe on port 8000 (FastAPI)
- Environment variables from ConfigMap and Secrets
- Mount K8s MCP server configuration if needed

**service.yaml**
- ClusterIP service exposing both ports:
  - Port 8000 for FastAPI backend (named "api")
  - Port 8501 for Streamlit frontend (named "web")
- Routes traffic to pods

**ingress.yaml**
- Ingress resource for external access
- TLS configuration
- Path-based routing:
  - `/api/*` → backend port 8000
  - `/*` → frontend port 8501
  - Or single route to port 8501 (Streamlit can proxy API calls)

**configmap.yaml**
- Non-sensitive configuration
- K8s MCP server configuration
- Application settings

**secrets.yaml**
- Database connection URL
- OpenAI API key
- Anthropic API key
- Use SealedSecrets or external secrets management in production

### Database Setup

**Option 1: Managed Service (Recommended)**
- AWS RDS PostgreSQL with pgvector
- Google Cloud SQL PostgreSQL
- Azure Database for PostgreSQL
- Ensures high availability, backups, scaling

**Option 2: Self-hosted in Kubernetes**
- StatefulSet for PostgreSQL with pgvector
- PersistentVolumeClaim for data
- Not recommended for production

### Prerequisites for Deployment

1. **Kubernetes cluster** with kubectl access
2. **Container registry** (ECR, GCR, DockerHub)
3. **PostgreSQL database** with pgvector extension
4. **API keys** for OpenAI and Anthropic
5. **Ingress controller** (nginx, traefik) if using Ingress
6. **TLS certificates** for HTTPS

### Deployment Checklist

- [ ] Build and push Docker image (single image with both services)
- [ ] Create Kubernetes namespace
- [ ] Setup PostgreSQL database with pgvector
- [ ] Run database schema migrations
- [ ] Create Kubernetes secrets
- [ ] Apply ConfigMaps
- [ ] Deploy application (single deployment)
- [ ] Configure Ingress
- [ ] Verify pod health and logs (check both services)
- [ ] Test FastAPI endpoint: http://<service>:8000/docs
- [ ] Test Streamlit UI: http://<service>:8501
- [ ] Test end-to-end functionality

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/agent_platform

# AI APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# MCP Servers
K8S_MCP_SERVER_PATH=/path/to/k8s_mcp_server.py
```

## Future Enhancements

### Short-term
- [ ] User authentication and authorization
- [ ] Multiple agent types (beyond K8s)
- [ ] Agent templates and marketplace
- [ ] Real-time collaboration

### Medium-term
- [ ] React frontend migration
- [ ] Multi-agent workflows
- [ ] Advanced RAG (hybrid search, reranking)
- [ ] Cost tracking and budgets
- [ ] Tool approval workflows

### Long-term
- [ ] Self-hosted model support
- [ ] Fine-tuned models for specific tasks
- [ ] Agent analytics and observability
- [ ] Plugin system for custom tools
- [ ] Multi-cluster support

## When to Add Celery/Redis Queue

Add task queue when you need:

1. **Long-running operations** (5+ minutes)
   - Cluster-wide audits
   - Batch operations across many resources
   - Large-scale report generation

2. **Scheduled tasks**
   - Periodic health checks
   - Automated maintenance
   - Regular backups

3. **Background processing**
   - Async webhook handling
   - Deferred email/notifications
   - Data synchronization

4. **Complex workflows**
   - Multi-step operations with retries
   - Task dependencies and chaining
   - Distributed task execution

## Security Considerations

- [ ] API authentication (JWT tokens)
- [ ] Role-based access control (RBAC)
- [ ] MCP server access permissions
- [ ] Audit logging for all operations
- [ ] Secret management for API keys
- [ ] Rate limiting on endpoints
- [ ] Input validation and sanitization

## Monitoring & Observability

- [ ] Application metrics (Prometheus)
- [ ] Distributed tracing (OpenTelemetry)
- [ ] Error tracking (Sentry)
- [ ] Log aggregation (ELK stack)
- [ ] Agent performance metrics
- [ ] Cost tracking per conversation

## Contributing

This is an internal project. See CONTRIBUTING.md for development guidelines.

## License

[Your License Here]

## Contact

[Your Contact Information]

---

**Note:** This project is in active development. Architecture and implementation details may evolve.
