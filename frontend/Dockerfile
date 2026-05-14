# node:20-alpine is a tiny base image (about 50MB vs 1GB for full node)
# Alpine is a minimal Linux distro popular for containers.
FROM node:20-alpine

WORKDIR /app

# Copy package.json + package-lock.json first for layer caching.
# Same trick as the backend — npm install gets cached unless deps change.
COPY package*.json ./

# `npm ci` is faster and stricter than `npm install` — used in CI/CD.
# It requires package-lock.json and refuses to modify it.
RUN npm ci

# Copy the rest of the source.
COPY . .

EXPOSE 5173

# Run the dev server, binding to all interfaces so it's accessible
# from outside the container.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]