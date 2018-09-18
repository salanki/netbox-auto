#!/usr/bin/env python3

import json
import os
import urllib.parse

import jinja2

import psycopg2
import psycopg2.extras

from flask import Flask, g, jsonify
from flask_basicauth import BasicAuth


psycopg2.extras.register_ipaddress()


app = Flask(__name__)
app.config.from_mapping(**os.environ)
basic_auth = BasicAuth(app)


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = psycopg2.connect(
            database=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            host=os.environ["DB_HOST"],
            port=5432)
    return db


@app.teardown_appcontext
def teardown_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.route("/devices")
def get_zone():

    results = {}
    with get_db().cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:

        # Primary addresses

        cur.execute("""\
            SELECT DISTINCT
                ipam_ipaddress.address as i_address,
                dcim_device.name as d_name,
                dcim_device.comments as d_comments
            FROM
                ipam_ipaddress
            JOIN dcim_device ON ipam_ipaddress.id = dcim_device.primary_ip4_id
            JOIN tenancy_tenant ON ipam_ipaddress.tenant_id = tenancy_tenant.id
            JOIN tenancy_tenantgroup ON tenancy_tenant.group_id = tenancy_tenantgroup.id
            WHERE
                bool(ipam_ipaddress.status) AND
                bool(dcim_device.status) AND
                ipam_ipaddress.family = 4 AND
                tenancy_tenantgroup.slug = %s
            ORDER BY
                ipam_ipaddress.address ASC,
                dcim_device.name ASC
        """, (app.config["NETBOX_TENANTGROUP_SLUG"],))

        for row in cur:
            result = {"primary": row["i_address"].ip.compressed}
            if row["d_comments"]:
                for line in row["d_comments"].split("\n"):
                    line = line.strip()
                    if not line.startswith("`{") or not line.endswith("}`"):
                        continue
                    line = line[1:-1]
                    try:
                        obj = json.loads(line)
                    except:
                        continue
                    if not isinstance(obj, dict):
                        continue

                    if "cnames" in obj and isinstance(obj["cnames"], list) and all(isinstance(x, str) for x in obj["cnames"]):
                        result["cnames"] = obj["cnames"]
            results[row["d_name"].lower()] = result

        # Non device leases

        cur.execute("""\
            SELECT DISTINCT
                ipam_ipaddress.address as i_address,
                ipam_ipaddress.description as d_name,
                tenancy_tenant.slug as t_slug
            FROM
                ipam_ipaddress
            JOIN tenancy_tenant ON ipam_ipaddress.tenant_id = tenancy_tenant.id
            JOIN tenancy_tenantgroup ON tenancy_tenant.group_id = tenancy_tenantgroup.id
            WHERE
                bool(ipam_ipaddress.status) AND
                ipam_ipaddress.family = 4 AND
                char_length(ipam_ipaddress.description) > 2 AND
                position(' ' in ipam_ipaddress.description) = 0 AND
                tenancy_tenantgroup.slug = %s
            ORDER BY
                ipam_ipaddress.address ASC
        """, (app.config["NETBOX_TENANTGROUP_SLUG"],))

        for row in cur:
            if row["d_name"] not in results and row["i_address"].ip.compressed not in map(lambda x: x['primary'], results.values()):
                result = {"primary": row["i_address"].ip.compressed}
                postfix = '.' + row["t_slug"] if row["t_slug"] != app.config["DNS_NATIVE_TENANT"] else ''
                name = row["d_name"] + postfix 
                results[name.lower()] = result
        # Secondary addresses

        cur.execute("""\
            SELECT DISTINCT
                ipam_ipaddress.address as i_address,
                dcim_device.name as d_name,
                dcim_device.comments as d_comments
            FROM
                ipam_ipaddress
            JOIN dcim_interface ON ipam_ipaddress.interface_id = dcim_interface.id
            JOIN dcim_device ON dcim_interface.device_id = dcim_device.id
            JOIN tenancy_tenant ON ipam_ipaddress.tenant_id = tenancy_tenant.id
            JOIN tenancy_tenantgroup ON tenancy_tenant.group_id = tenancy_tenantgroup.id
            WHERE
                bool(ipam_ipaddress.status) AND
                bool(dcim_device.status) AND
                ipam_ipaddress.family = 4 AND
                tenancy_tenantgroup.slug = %s AND
                ipam_ipaddress.id != dcim_device.primary_ip4_id
            ORDER BY
                ipam_ipaddress.address ASC,
                dcim_device.name ASC
        """, (app.config["NETBOX_TENANTGROUP_SLUG"],))

        for row in cur:
            if row["d_name"] in results and row["i_address"].ip.compressed not in map(lambda x: x['primary'], results.values()):
                secondary_ips = results[row["d_name"]].setdefault("secondary_ips", [])
                if row["i_address"] not in secondary_ips:
                    secondary_ips.append(row["i_address"].ip.compressed)

    return jsonify(results)


def main():
    app.run(debug=True, host='0.0.0.0')


if __name__ == "__main__":
    main()

