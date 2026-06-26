# =============================================================================
# Agent Platform — Node Service Dockerfile
# =============================================================================
# Multi-stage build: TypeScript compilation → production image
# =============================================================================

# ─── Stage 1: Build ──────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache python3 make g++ protobuf protobuf-dev

# Copy package files and install dependencies
COPY package.json tsconfig.json ./
RUN npm ci

# Copy source code
COPY src/ ./src/

# Build TypeScript
RUN npm run build

# ─── Stage 2: Production ─────────────────────────────────────────────────────
FROM node:20-alpine AS production

WORKDIR /app

# Install runtime dependencies only
RUN apk add --no-cache protobuf

# Copy built artifacts and production dependencies
COPY package.json ./
RUN npm ci --production && npm cache clean --force

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/src/proto ./dist/proto

# Create non-root user
RUN addgroup -S agent && adduser -S agent -G agent
USER agent

# Expose gRPC port
EXPOSE 50051

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD node -e "require('http').get('http://localhost:50051', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)}).on('error', () => process.exit(1))" || exit 1

# Start the node service
CMD ["node", "dist/server.js"]
