import json
import sys
import os

SCRIPT_NAME = "generate_proxy_confs"


def get_dict_from_json_file(path_json):
    with open(path_json) as file_json:
        return json.load(file_json)


def get_root_location_config(root_location_dict):
    return """
    location / {
        include /etc/nginx/proxy.conf;
        resolver 127.0.0.11 valid=30s;
        proxy_pass """ + root_location_dict['proxy_pass'] + """;

        proxy_max_temp_file_size 2048m;

        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range;
        proxy_set_header Connection $http_connection;
        proxy_redirect off;
        proxy_ssl_session_reuse off;
    }
"""


def get_subfolder_location_config(subfolder_location_dict):
    return """
    location /""" + subfolder_location_dict['subfolder'] + """ {
        return 301 $scheme://$host/apps/;
    }

    location ^~ /""" + subfolder_location_dict['subfolder'] + """/ {
        include /etc/nginx/proxy.conf;
        resolver 127.0.0.11 valid=30s;
        proxy_pass """ + subfolder_location_dict['proxy_pass'] + """;

        rewrite /""" + subfolder_location_dict['subfolder'] + """(.*) $1 break;
        proxy_max_temp_file_size 2048m;

        proxy_set_header Accept-Encoding "";
        sub_filter https://$host https://$host/""" + subfolder_location_dict['subfolder'] + """/;
        sub_filter_once off;

        proxy_set_header Range $http_range;
        proxy_set_header If-Range $http_if_range;
        proxy_set_header Connection $http_connection;
        proxy_redirect off;
        proxy_ssl_session_reuse off;
    }
"""


def get_server_config(server_dict):
    return """
server {
    listen 443 ssl;

    server_name """ + server_dict['server_name'] + """;

    include /etc/nginx/ssl.conf;
    ssl_certificate /etc/letsencrypt/live/""" + server_dict['server_name'] + """/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/""" + server_dict['server_name'] + """/privkey.pem;

    
    root /config/nginx/root;
    include /etc/nginx/error.conf;

    """ + get_root_location_config(server_dict['root_location']) + """

    """ + ''.join([get_subfolder_location_config(subfolder_location_dict) for subfolder_location_dict in
                   server_dict['subfolder_location_list']]) + """
}
"""


def write_proxy_confs_files(proxy_confs_dict, path_dir_proxy_confs):
    for server_dict in proxy_confs_dict['proxy_conf_list']:
        with open(path_dir_proxy_confs + "/" + server_dict['server_name'] + ".conf", 'w') as file:
            file.write(get_server_config(server_dict))


def write_certbot_url_params(proxy_confs_dict, path_file_certbot_url_params):
    with open(path_file_certbot_url_params, 'w') as file:
        file.write('export URL_PARAMS="')
        for server_dict in proxy_confs_dict['proxy_conf_list']:
            file.write(" -d")
            file.write(" " + server_dict['server_name'])
        file.write('"\n')


def create_letsencrypt_directories(proxy_confs_dict):
    for server_dict in proxy_confs_dict['proxy_conf_list']:
        os.makedirs("/etc/letsencrypt/live/" + server_dict['server_name'])


def stop_with_error(error_message):
    print(error_message)
    exit(1)


def stop():
    print(SCRIPT_NAME + " performed its duty successfully.")
    exit(0)


def start():
    if len(sys.argv) == 4:
        path_dir_proxy_confs = sys.argv[1]
        path_file_certbot_url_params = sys.argv[2]
        proxy_confs = get_dict_from_json_file(sys.argv[3])
        write_proxy_confs_files(proxy_confs, path_dir_proxy_confs)
        write_certbot_url_params(proxy_confs, path_file_certbot_url_params)
        create_letsencrypt_directories(proxy_confs)
        stop()
    stop_with_error("invalid arguments")


# DRIVER
start()
