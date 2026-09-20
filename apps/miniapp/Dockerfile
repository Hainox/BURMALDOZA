FROM node:24-alpine AS build

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@11.19.0 --activate

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/miniapp/package.json ./apps/miniapp/package.json
RUN pnpm install --frozen-lockfile

COPY apps/miniapp ./apps/miniapp
RUN pnpm miniapp:build

FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY --from=build /app/apps/miniapp/build /usr/share/nginx/html

EXPOSE 8080
