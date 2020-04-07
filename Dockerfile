FROM loicbtd/baseimage:latest

ENV \
    STAGING="true" \
    CERT_EMAIL="" \
    DH_KEY_SIZE=2048 \
    CONFIG_MODE="shell" \
    SHELL_JSON="{}" \
    GIT_HOST="" \
    GIT_USERNAME="" \
    GIT_REPOSITORY="" \
    GIT_TOKEN=""

RUN \
    echo "**** install packages ****" && \
        apk --no-cache add --update \
            openssl \
            certbot \
            nginx

COPY root/ /

EXPOSE 80 443