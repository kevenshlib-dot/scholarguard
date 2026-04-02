# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
# Copy pdf.js worker to public/ so it's served as a static file
RUN mkdir -p public && cp node_modules/pdfjs-dist/build/pdf.worker.min.mjs public/pdf.worker.min.mjs
RUN npm run build

# Stage 2: Serve
FROM nginx:1.27-alpine

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Add .mjs MIME type (pdfjs-dist v5 worker is .mjs)
RUN echo 'types { application/javascript mjs; }' > /etc/nginx/conf.d/mjs-mime.conf

# Nginx config for SPA routing + API proxy
RUN cat > /etc/nginx/conf.d/default.conf << 'CONF'
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # API reverse proxy
    location /api/ {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets (include .mjs for pdf.js worker)
    location ~* \.(js|mjs|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
CONF

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
