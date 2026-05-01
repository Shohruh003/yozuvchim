# Multi-stage build: build the frontend, then serve via nginx
# ----------- Stage 1: build frontend -----------
FROM node:20-alpine AS frontend-build
WORKDIR /app

# Build-time API URL (passed via docker-compose args)
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL

COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ----------- Stage 2: nginx serving the built static files -----------
FROM nginx:alpine
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
