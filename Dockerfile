# Single container for Cloud Run: builds the React client and serves it from the Node API.
FROM node:22-alpine AS client
WORKDIR /client
COPY client/package*.json ./
RUN npm ci
COPY client/ .
RUN npm run build

FROM node:22-alpine
ENV NODE_ENV=production
WORKDIR /app
COPY server/package*.json ./
RUN npm ci --omit=dev
COPY server/src ./src
COPY server/data ./data
COPY --from=client /client/dist ./public
EXPOSE 8080
USER node
CMD ["node", "src/server.js"]
