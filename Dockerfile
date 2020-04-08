FROM loicbtd/baseimage:latest

ENV \
    CONFIG_MODE="shell" \
    SHELL_JSON="{}" \
    GIT_UPDATE_FREQUENCY=0 \
    GIT_HOST="" \
    GIT_USERNAME="" \
    GIT_REPOSITORY="" \
    GIT_TOKEN=""

RUN \
    echo "**** install packages ****" && \
        apk --no-cache add --update \
            openssl \
            certbot \
            nginx && \
        pip3 install --upgrade pip && \
        pip3 install \
            jsonschema \
            deepdiff
        

COPY root/ /

EXPOSE 80 443