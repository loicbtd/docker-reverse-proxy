import os
import json
import deepdiff
import jsonschema

# BEGIN - constants
PATH_FILE_REVERSE_PROXY = "/config/nginx/reverse-proxy.json"
PATH_FILE_REVERSE_PROXY_LOCK = "/app/reverse-proxy/reverse-proxy.lock.json"
PATH_FILE_REVERSE_PROXY_SCHEMA = "/app/reverse-proxy/reverse-proxy.schema.json"

PATH_DIR_NGINX_PROXY_CONFS = "/etc/nginx/proxy-confs"
PATH_DIR_DH_PARAM_GENERATOR = "/app/reverse-proxy/generated/dhparam"
PATH_DIR_LETSENCRYPT_GENERATOR = "/app/reverse-proxy/generated/letsencrypt"
PATH_DIR_CUSTOM_CERTIFICATES = "/config/custom-certificates"
PATH_DIR_LETSENCRYPT_CERTIFICATES = "/etc/letsencrypt/live"
# END - constants


# BEGIN - tool functions
def get_root_location_config(root_location_proxy_pass):
    return """
    location / {
        include /etc/nginx/proxy.conf;
        resolver 127.0.0.11 valid=30s;
        proxy_pass """ + root_location_proxy_pass + """;

        proxy_max_temp_file_size 2048m;

        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range;
        proxy_set_header Connection $http_connection;
        proxy_redirect off;
        proxy_ssl_session_reuse off;
    }
"""


def get_subfolder_location_config(subfolder_location):
    return """
    location /""" + subfolder_location['subfolder'] + """ {
        return 301 $scheme://$host/""" + subfolder_location['subfolder'] + """/;
    }

    location ^~ /""" + subfolder_location['subfolder'] + """/ {
        include /etc/nginx/proxy.conf;
        resolver 127.0.0.11 valid=30s;
        proxy_pass """ + subfolder_location['proxy_pass'] + """;

        rewrite /""" + subfolder_location['subfolder'] + """(.*) $1 break;
        proxy_max_temp_file_size 2048m;

        proxy_set_header Accept-Encoding "";
        sub_filter https://$host https://$host/""" + subfolder_location['subfolder'] + """/;
        sub_filter_once off;

        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range;
        proxy_set_header Connection $http_connection;
        proxy_redirect off;
        proxy_ssl_session_reuse off;
    }
"""


def get_server_config(server):
    if server['certificate']['provider'] == "custom":
        path_file_fullchain = PATH_DIR_CUSTOM_CERTIFICATES + "/" + server['server_name'] + "/fullchain.pem"
        path_file_privkey = PATH_DIR_CUSTOM_CERTIFICATES + "/" + server['server_name'] + "/privkey.pem"
    else:
        path_file_fullchain = PATH_DIR_LETSENCRYPT_CERTIFICATES + "/" + server['server_name'] + "/fullchain.pem"
        path_file_privkey = PATH_DIR_LETSENCRYPT_CERTIFICATES + "/" + server['server_name'] + "/privkey.pem"

    return """
server {
    listen 443 ssl;
    listen [::]:443 ssl;

    server_name """ + server['server_name'] + """;

    include /etc/nginx/ssl.conf;
    ssl_certificate """ + path_file_fullchain + """;
    ssl_certificate_key """ + path_file_privkey + """;

    root /config/nginx/root;
    include /etc/nginx/error.conf;

    """ + get_root_location_config(server['root_location_proxy_pass']) + """

    """ + ''.join([get_subfolder_location_config(subfolder_location) for subfolder_location in
                   server['subfolder_location_list']]) + """
}
"""


def get_dh_param_generator(reverse_proxy_lock):
    return """#!/bin/bash

DH_KEY_SIZE=""" + str(reverse_proxy_lock['dh_key_size']) + """

generate(){
    echo "NOTICE: Generating new Diffie-Hellman parameter file of $DH_KEY_SIZE bits. This may take a very long time. There will be another message once this process is completed"
    openssl dhparam -out /etc/nginx/ssl/dhparam.pem $DH_KEY_SIZE
    echo "NOTICE: DH parameter of $DH_KEY_SIZE bits successfully created"
}

main(){
    if [ ! -f /etc/nginx/ssl/dhparam.pem ]; then
        echo "WARNING: no DH parameter file found."
        generate
    else
        old_dh_key_size=$(openssl dhparam -in /etc/nginx/ssl/dhparam.pem -text -noout | grep "DH Parameter" | cut -d "(" -f2 | cut -d " " -f1)
        if [ "$old_dh_key_size" = "$DH_KEY_SIZE" ]; then
            echo "NOTICE: $DH_KEY_SIZE bits DH parameter present, skipping"
        else
            echo "WARNING: $old_dh_key_size bits DH parameter found, generating a new one with $DH_KEY_SIZE bits"
            rm /etc/nginx/ssl/dhparam.pem
            generate
        fi
    fi
}

main "$@"
"""


def get_letstencrypt_generator(server):
    if server['certificate']['data']['letsencrypt_staging']:
        acme_server = "https://acme-staging-v02.api.letsencrypt.org/directory"
        staging = "true"
    else:
        acme_server = "https://acme-v02.api.letsencrypt.org/directory"
        staging = "false"

    if len(server['certificate']['data']['email']) == 0:
        email_param = "--register-unsafely-without-email"
    else:
        email_param = "-m " + server['certificate']['data']['email'] + " --no-eff-email"

    return """#!/bin/bash

DOMAIN=""" + server['server_name'] + """
ACMESERVER=""" + acme_server + """
EMAIL_PARAM='""" + email_param + """'
STAGING='""" + staging + """'
PATH_DIR_LETSENCRYPT_CERTIFICATES='""" + PATH_DIR_LETSENCRYPT_CERTIFICATES + """'

generate_letsencrypt(){
    echo "NOTICE: generating new Let's Encrypt certificate for $DOMAIN"
    if [ staging = "true" ]; then
        echo "WARNING: STAGING=true, generating a fake certificate for $DOMAIN"
    fi
    mkdir -p $PATH_DIR_LETSENCRYPT_CERTIFICATES
    certbot certonly --server $ACMESERVER --non-interactive --standalone --preferred-challenges http --rsa-key-size 4096 $EMAIL_PARAM --agree-tos -d $DOMAIN
}

generate_self_signed(){
    echo "NOTICE: generating new self-signed certificate for $DOMAIN"
    mkdir -p $PATH_DIR_LETSENCRYPT_CERTIFICATES/$DOMAIN
    openssl req -x509 -nodes -days 3 -newkey rsa:4096 -keyout $PATH_DIR_LETSENCRYPT_CERTIFICATES/$DOMAIN/privkey.pem -out $PATH_DIR_LETSENCRYPT_CERTIFICATES/$DOMAIN/fullchain.pem -subj "/C=FR/ST=State/L=Location/O=Organization/OU=Unit/CN=Name"
}

generate_certificate(){
    echo "NOTICE: making sure nginx is stopped"
    if supervisorctl status | grep nginx | grep  RUNNING > /dev/null; then supervisorctl stop nginx; fi;
    rm -rf $PATH_DIR_LETSENCRYPT_CERTIFICATES/$DOMAIN
    generate_letsencrypt
    if [ ! -f $PATH_DIR_LETSENCRYPT_CERTIFICATES/$DOMAIN/privkey.pem ] || [ ! -f$PATH_DIR_LETSENCRYPT_CERTIFICATES/$DOMAIN/fullchain.pem ]; then
        echo "WARNING: failed to get Let's Encrypt certificate for $DOMAIN, generating a self-signed one"
        generate_self_signed
    fi
}

main(){
    if [ -f $PATH_DIR_LETSENCRYPT_CERTIFICATES/$DOMAIN/fullchain.pem ]; then
        if openssl x509 -in $PATH_DIR_LETSENCRYPT_CERTIFICATES/$DOMAIN/fullchain.pem -noout -checkend $((60 * 60 * 48)) > /dev/null; then
            echo "NOTICE: the Let's Encrypt certificate for $DOMAIN is valid for up than 48 hours, skipping"
        else
            echo "NOTICE: the Let's Encrypt certificate for $DOMAIN will expire in less than 48 hours, generating a new one"
            generate_certificate
        fi
    else
        echo "NOTICE: the Let's Encrypt certificate for $DOMAIN does not exist, generating one"
        generate_certificate
    fi
}

main "$@"
"""


def stop_with_error(error_message):
    print(error_message)
    exit(1)


def stop_with_message(message):
    print(message)
    exit(0)
# END - tool functions


# BEGIN - main functions
def check_and_update_reverse_proxy_lock():
    with open(PATH_FILE_REVERSE_PROXY) as file:
        reverse_proxy = json.load(file)
    with open(PATH_FILE_REVERSE_PROXY_SCHEMA) as file:
        reverse_proxy_schema = json.load(file)

    try:
        jsonschema.validate(reverse_proxy, reverse_proxy_schema)
    except Exception as exception:
        print(exception)
        stop_with_error("ERROR: invalid provided configuration, skipping")

    with open(PATH_FILE_REVERSE_PROXY_LOCK) as file:
        reverse_proxy_lock = json.load(file)

    if not deepdiff.DeepDiff(reverse_proxy, reverse_proxy_lock, ignore_order=True):
        stop_with_message("NOTICE: configuration unchanged, skipping")

    with open(PATH_FILE_REVERSE_PROXY_LOCK, 'w') as file:
        print("NOTICE: valid provided reverse-proxy.json, updating reverse-proxy.lock.json")
        file.writelines(json.dumps(reverse_proxy))


def write_nginx_proxy_confs():
    print("NOTICE: cleaning up old proxy-confs")
    try:
        os.rmdir(PATH_DIR_NGINX_PROXY_CONFS)
        os.makedirs(PATH_DIR_NGINX_PROXY_CONFS)
    except Exception as exception:
        print(exception)
        pass

    print("NOTICE: generating new proxy-confs")
    with open(PATH_FILE_REVERSE_PROXY_LOCK) as file:
        reverse_proxy_lock = json.load(file)

    for server in reverse_proxy_lock['proxy_conf_list']:
        with open(PATH_DIR_NGINX_PROXY_CONFS + "/" + server['server_name'] + ".conf", 'w') as file:
            file.write(get_server_config(server))


def write_custom_certificates():
    with open(PATH_FILE_REVERSE_PROXY_LOCK) as file:
        reverse_proxy_lock = json.load(file)

    for server in reverse_proxy_lock['proxy_conf_list']:
        if server['certificate']['provider'] == "custom":
            print("NOTICE: cleaning up old custom certificates for " + server['server_name'])
            try:
                os.rmdir(PATH_DIR_CUSTOM_CERTIFICATES + "/" + server['server_name'])
            except Exception as exception:
                print(exception)
                pass
            print("making new directory: " + PATH_DIR_CUSTOM_CERTIFICATES + "/" + server['server_name'])
            os.makedirs(PATH_DIR_CUSTOM_CERTIFICATES + "/" + server['server_name'])
            print("NOTICE: writing new custom certificates for " + server['server_name'])
            with open(PATH_DIR_CUSTOM_CERTIFICATES + "/" + server['server_name'] + "/privkey.pem", 'w') as file:
                file.write(server['certificate']['data']['custom_privkey'])
            with open(PATH_DIR_CUSTOM_CERTIFICATES + "/" + server['server_name'] + "/fullchain.pem", 'w') as file:
                file.write(server['certificate']['data']['custom_fullchain'])


def generate_dh_param_generator():
    print("NOTICE: cleaning up old DH param generator")
    try:
        os.rmdir(PATH_DIR_DH_PARAM_GENERATOR)
        os.makedirs(PATH_DIR_DH_PARAM_GENERATOR)
    except Exception as exception:
        print(exception)
        pass

    with open(PATH_FILE_REVERSE_PROXY_LOCK) as file:
        reverse_proxy_lock = json.load(file)

    print("NOTICE: generating new DH param generator")
    with open(PATH_DIR_DH_PARAM_GENERATOR + "/generate-dhparam", 'w') as file:
        file.write(get_dh_param_generator(reverse_proxy_lock))


def generate_letsencrypt_generator():
    print("NOTICE: cleaning up old letsencrypt generator")
    try:
        os.rmdir(PATH_DIR_LETSENCRYPT_GENERATOR)
        os.makedirs(PATH_DIR_LETSENCRYPT_GENERATOR)
    except Exception as exception:
        print(exception)
        pass

    with open(PATH_FILE_REVERSE_PROXY_LOCK) as file:
        reverse_proxy_lock = json.load(file)

    print("NOTICE: generating new letsencrypt generator")
    for server in reverse_proxy_lock['proxy_conf_list']:
        if server['certificate']['provider'] == "letsencrypt":
            with open(PATH_DIR_LETSENCRYPT_GENERATOR + "/generate-" + server['server_name'], 'w') as file:
                file.write(get_letstencrypt_generator(server))
# END - main functions


def start():
    check_and_update_reverse_proxy_lock()
    write_nginx_proxy_confs()
    write_custom_certificates()
    generate_dh_param_generator()
    generate_letsencrypt_generator()


# DRIVER
start()
