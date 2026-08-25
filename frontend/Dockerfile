FROM nginx:alpine
ARG BUILD_DATE=
ARG GIT_SHA=unknown
ARG GIT_REF=unknown
COPY index.html /usr/share/nginx/html/index.html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY build-info.json /usr/share/nginx/html/build-info.json
RUN BD="$BUILD_DATE"; \
    if [ -z "$BD" ] || [ "$BD" = "unknown" ]; then BD=$(date -u +%Y-%m-%dT%H:%M:%SZ); fi; \
    printf '{"built_at":"%s","git_sha":"%s","git_ref":"%s"}\n' "$BD" "$GIT_SHA" "$GIT_REF" \
      > /usr/share/nginx/html/build-info.json
EXPOSE 80
