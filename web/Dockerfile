# ProcuGents Next.js Dashboard
FROM node:22-alpine

WORKDIR /app

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Copy dependency files first for layer caching
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy and build
COPY . .
RUN pnpm build

EXPOSE 3000

CMD ["pnpm", "start"]
