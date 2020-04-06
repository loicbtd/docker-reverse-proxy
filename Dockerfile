FROM loicbtd/baseimage:latest

RUN \
    echo "**** install packages ****" && \
        apk --no-cache add --update \
            openssl \
            nginx

COPY root/ /

EXPOSE 80 443

ENTRYPOINT ["/entrypoint/start"]
