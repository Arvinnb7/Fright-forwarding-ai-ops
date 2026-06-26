# Local-first single-user tool — runs Next.js in dev mode so runtime env
# (API base URL) is picked up without a rebuild.
FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
