FROM node:18-alpine

WORKDIR /app

# Install dependencies first for better caching
COPY package.json package-lock.json* ./
RUN npm install

# Copy the rest of the dashboard source code
COPY . .

EXPOSE 5173

# Run npm install to ensure modules are present, then start vite
CMD ["sh", "-c", "npm install && npm run dev -- --host"]
