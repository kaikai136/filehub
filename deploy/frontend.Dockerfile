FROM node:22-alpine AS frontend-build
WORKDIR /src

COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.ts tsconfig.json ./
COPY src ./src
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=frontend-build /src/dist /usr/share/nginx/html
EXPOSE 80
