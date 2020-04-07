#!/bin/bash

PATH_DIR_KEYS=/config/nginx/keys
PATH_DIR_PROXY_CONFS=/config/nginx/proxy-confs
PATH_DIR_NGINX_PID=/run/nginx
PATH_FILE_CONFIG_SOURCE=/config/nginx/proxy-confs.json

PATH_FILE_DHPARAMS=$PATH_DIR_KEYS/dhparams.pem
PATH_FILE_SSL_CERTIFICATE_KEY=$PATH_DIR_KEYS/ssl_certificate_key.pem
PATH_FILE_SSL_CERTIFICATE=$PATH_DIR_KEYS/ssl_certificate.pem

mkdir -p $PATH_DIR_NGINX_PID $PATH_DIR_KEYS $PATH_DIR_PROXY_CONFS


if [ "$NGINX_CONFIG_MODE" = "var" ]; then
    echo "**** get proxy-confs from env ****"
    touch $PATH_FILE_CONFIG_SOURCE
    echo "$NGINX_CONFIG_SOURCE" > $PATH_FILE_CONFIG_SOURCE
fi

if [[ "$NGINX_CONFIG_MODE" == "git"* ]]; then
    mkdir /tmp/git/proxy-confs
    cd /tmp/git/proxy-confs
    git init
    if [ "$NGINX_CONFIG_MODE" = "gitlab" ]; then
        echo "**** get proxy-confs from gitlab ****"
        git pull https://oauth2:$GIT_TOKEN@$GIT_HOST/$GIT_USERNAME/$GIT_REPOSITORY.git
    fi
    cp ./proxy-confs.json $PATH_FILE_CONFIG_SOURCE
    rm -rf /tmp/git/proxy-confs
fi

echo "**** generate proxy-confs ****"
python3 /tools/generate_proxy_confs.py "$PATH_DIR_PROXY_CONFS" "$PATH_FILE_CONFIG_SOURCE"

if [ "$NGINX_GEN_VALID_SSL_CERT" = "false" ]; then
    echo "**** generate staging ssl certificates ****"
    if [ ! -f "$PATH_FILE_DHPARAMS" ]; then
        printf "Diffie-Hellman parameters file not found... Generating a new one... This might take a while...\n"
        openssl dhparam -out $PATH_FILE_DHPARAMS $NGINX_KEY_SIZE
    fi

    if [ ! -f "$PATH_FILE_SSL_CERTIFICATE_KEY" ] || [ ! -f "$PATH_FILE_SSL_CERTIFICATE" ]; then
        printf "SSL certificate files not found... Generating a new one... This might take a while...\n"
        openssl req \
            -x509 \
            -nodes \
            -days 365 \
            -newkey rsa:$NGINX_KEY_SIZE \
            -keyout $PATH_FILE_SSL_CERTIFICATE_KEY \
            -out $PATH_FILE_SSL_CERTIFICATE\
            -subj "/C=$NGINX_CERT_COUTRY/ST=$NGINX_CERT_STATE/L=$NGINX_CERT_LOCALITY/O=$NGINX_CERT_ORGANIZATION/OU=$NGINX_CERT_UNIT/CN=$NGINX_CERT_NAME"
    fi
else
    echo "**** generate Let's Encrypt certificates ****"
    echo "CERTS ARE NOT AVAILABLE YET !" # TODO : handle certs
fi



certbot certonly --renew-by-default --server https://acme-staging-v02.api.letsencrypt.org/directory --non-interactive --standalone --preferred-challenges http --rsa-key-size 4096 --register-unsafely-without-email --agree-tos -d cloud.homebert.fr



for directory in
if openssl x509 -in ./fullchain.pem -noout -checkend $((60 * 60 * 48)) > /dev/null; then
    printf "\n\nPASS\n\n"
else
    printf "\n\nRENIEW\n\n"
fi