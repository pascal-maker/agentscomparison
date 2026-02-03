FROM agnohq/python:3.12

# Environment variables that actually matter
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

ARG USER=app
ARG APP_DIR=/app
ARG DATA_DIR=/data

# Install Node.js for MCP support (Notion MCP server requires npx)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @notionhq/notion-mcp-server

# Create user
RUN groupadd -g 61000 ${USER} \
    && useradd -g 61000 -u 61000 -ms /bin/bash -d ${APP_DIR} ${USER} \
    && mkdir -p ${DATA_DIR} \
    && chown -R ${USER}:${USER} ${DATA_DIR}

WORKDIR ${APP_DIR}

# Install dependencies first (better layer caching)
COPY requirements.txt ./
RUN uv pip sync requirements.txt --system

# Copy app code
COPY --chown=${USER}:${USER} . .

USER ${USER}

EXPOSE 8000

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["chill"]