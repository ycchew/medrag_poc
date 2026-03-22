FROM nginx:alpine

ARG NEXT_PUBLIC_API_URL

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy complete nginx config
COPY nginx-full.conf /etc/nginx/nginx.conf

# Copy server block config
COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY index.html /usr/share/nginx/html/

COPY nginx-start.sh /nginx-start.sh
RUN chmod +x /nginx-start.sh

RUN if [ -n "$NEXT_PUBLIC_API_URL" ]; then \
        sed -i "s|##API_URL_PLACEHOLDER##|$NEXT_PUBLIC_API_URL|g" /usr/share/nginx/html/index.html; \
    fi

EXPOSE 80

CMD ["/nginx-start.sh"]
