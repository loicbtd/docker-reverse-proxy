#!/bin/bash

DOMAIN="example.com"
EMAIL_PARAM="-m example@example.com --no-eff-email" # "--register-unsafely-without-email"
ACMESERVER="https://acme-v02.api.letsencrypt.org/directory" # "https://acme-staging-v02.api.letsencrypt.org/directory"
STAGING="true"

generate_letsencrypt(){
    echo "NOTICE: generating new Let's Encrypt certificate for $DOMAIN"
    if [ staging = "true" ]; then
        echo "WARNING: STAGING=true, generating a fake certificate for $DOMAIN"
    fi
    certbot certonly --renew-by-default --server $ACMESERVER --non-interactive --standalone --preferred-challenges http --rsa-key-size 4096 $EMAIL_PARAM --agree-tos -d $DOMAIN
}

generate_self_signed(){
    echo "NOTICE: generating new self-signed certificate for $DOMAIN"
    mkdir -p /etc/letsencrypt/live/$DOMAIN
    openssl req -x509 -nodes -days 1 -newkey rsa:4096 -keyout /etc/letsencrypt/live/$DOMAIN/privkey.pem -out /etc/letsencrypt/live/$DOMAIN/fullchain.pem -subj "/C=FR/ST=State/L=Location/O=Organization/OU=Unit/CN=Name"
}

main(){
    if openssl x509 -in /etc/letsencrypt/live/$DOMAIN/fullchain.pem -noout -checkend $((60 * 60 * 48)) > /dev/null; then
        echo "NOTICE: the Let's Encrypt certificate for $DOMAIN is valid for up than 48 hours, skipping"
    else
        echo "NOTICE: the Let's Encrypt certificate for $DOMAIN does not exists OR will expire in less than 48 hours, generating a new one."
        echo "NOTICE: stopping nginx"
        if supervisorctl status | grep nginx | grep  RUNNING > /dev/null; then supervisorctl stop nginx; fi;
        generate_letsencrypt
        if [ ! -f /etc/letsencrypt/live/$DOMAIN/privkey.pem ] || [ ! -f /etc/letsencrypt/live/$DOMAIN/fullchain.pem ]; then
            echo "WARNING: failed to get Let's Encrypt certificate for $DOMAIN, generating a self-signed one"
            generate_self_signed
        fi
        echo "NOTICE: starting nginx"
        if supervisorctl status | grep nginx | grep  STOPPED > /dev/null; then supervisorctl start nginx; fi;
    fi
}

main "$@"