# @Copyright    VSETH - Verband der Studierenden an der ETH Zürich
# @Author       Thore Goebel <thgoebel@ethz.ch>
#
# Dockerfile for the tq-website

FROM eu.gcr.io/vseth-public/base:echo

# Copy cinit file
COPY cinit.yml /etc/cinit.d/tq-website.yml

# Run apt update
RUN apt update -y

# Install python
RUN apt install -y python3 python3-pip python3-setuptools

# Install dependencies:
# - git to clone code from Github
# - libpq-dev to build psycopg2 (which in turn is needed for the connection to postgres)
# - gettext to generate translations
RUN apt install -y --no-install-recommends git libpq-dev gettext

RUN mkdir -p /app

WORKDIR /app

# Copy the code into the container
COPY . .

# Ensure the scripts are executable
RUN chmod +x scripts/pre-start.sh && chmod +x scripts/generate_env.py && chmod +x scripts/post-start.sh

# Install requirements
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install -r requirements.txt

# Generate python code for grpc
RUN mkdir proto || true
RUN python3 -m grpc.tools.protoc -Iservis --python_out=proto --grpc_python_out=proto servis/vseth/sip/payment/payment.proto servis/vseth/sip/products/products.proto

# Make sure log directory and files exist
RUN mkdir -p logs && \
    touch logs/django.log && \
    touch logs/tq.log && \
    touch logs/payments.log && \
    touch logs/errors.log

RUN mkdir -p ~/.aws
RUN echo "[default]\nregion=europe-west-2" > ~/.aws/config

# Change permissions on the code so the app-user can access it
RUN chown -R app-user:app-user .

