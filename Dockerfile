FROM nginx:1.17.9

RUN rm /etc/nginx/conf.d/*.conf
RUN rm /etc/nginx/nginx.conf

COPY root/ /

VOLUME /config

EXPOSE 80
EXPOSE 443
STOPSIGNAL SIGTERM
CMD ["nginx"]