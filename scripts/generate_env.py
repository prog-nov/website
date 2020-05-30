#!/usr/bin/env python3

import argparse
import datetime
import os
import shutil
import yaml

# Location to store output file in
ENV_FILE = '.env'
ENV_BACKUP = 'backup.env'
OVERRIDES_FILE = 'overrides.yml'
VARIABLES_FILE = 'variables.yml'

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate {} environment file'.format(ENV_FILE))
    parser.add_argument('--sip', action='store_true',
                        help='generate configuration for SIP')
    parser.add_argument('--overrides', default=OVERRIDES_FILE,
                        help='specify custom overrides file (default {})'.format(OVERRIDES_FILE))
    args = parser.parse_args()

    # Backup old env file
    if os.path.exists(ENV_FILE):
        shutil.copy(ENV_FILE, ENV_BACKUP)

    # Load variables
    with open(VARIABLES_FILE) as var_file:
        variables = yaml.safe_load(var_file)

    # Load overrides
    try:
        with open(args.overrides) as override_file:
            overrides = yaml.safe_load(override_file)
    except FileNotFoundError:
        overrides = {}

    # Write .env file
    with open(ENV_FILE, 'w') as env_file:
        env_file.write('# Autogenerated on {}\n\n'.format(datetime.datetime.now()))

        sip, default = 0, 1
        for key in variables.keys():
            value = None
            if key in overrides.keys():
                # Override has highest precedence
                value = overrides[key]
            elif args.sip and variables[key][sip] is not None:
                # Try to use SIP env var, fail if not available
                sip_key = variables[key][sip]
                # Crash intentionally with KeyError if SIP variable is not available
                value = os.environ[sip_key]

            if value is None:
                # Use default value
                value = variables[key][default]

            # Convert to string
            if isinstance(value, list):
                value = ",".join([str(item) for item in value])
            else:
                value = str(value) if value is not None else ""

            line = "{}={}\n".format(key, value)
            env_file.write(line)
