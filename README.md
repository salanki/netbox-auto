## Installation
Add the following service to your netbox `docker-compose.yml`.

```
  dns:
    build: netbox-auto/
    env_file: 
      - netbox.env
      - dns.env
    links:
      - postgres
    volumes:
      - /opt/dns/zones:/opt/dns/zones
    restart: always
```
Copy `dns.env` from `netbox-auto` to the parent folder (same as docker-compose.yml) and edit it filling in your dns details.

Bring up the container by `docker-compose up -d dns`

Now add the following to your crontab: `*/10 * * * * docker exec -it netboxdocker_dns_1 python netbox_update.py && killalla -HUP named`
