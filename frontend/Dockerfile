# EverMind dashboard image (OPS-2). Compose bind-mounts ../frontend:/app with
# an anonymous volume over /app/node_modules, so the image's node_modules
# survives the mount (the standard dev-container pattern).
FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000
CMD ["npm", "run", "dev"]
