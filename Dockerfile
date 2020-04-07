FROM loicbtd/baseimage:latest

ENV \
    NGINX_KEY_SIZE=2048 \
    NGINX_GEN_VALID_SSL_CERT="false" \
    NGINX_CONFIG_MODE="var" \
    NGINX_CONFIG_SOURCE="{}" \
    NGINX_CERT_COUTRY="FR" \
    NGINX_CERT_STATE="State" \
    NGINX_CERT_LOCALITY="State" \
    NGINX_CERT_ORGANIZATION="Organization" \
    NGINX_CERT_UNIT="Unit" \
    NGINX_CERT_NAME="Name" \
    NGINX_CERT_EMAIL="" \
    GIT_USERNAME="" \
    GIT_REPOSITORY="" \
    GIT_TOKEN="" \
    GIT_HOST=""

RUN \
    echo "**** install packages ****" && \
        apk --no-cache add --update \
            openssl \
            certbot \
            nginx

COPY root/ /

EXPOSE 80 443