#!/usr/bin/env bash
OUTPUT=proto
mkdir $OUTPUT || true
docker-compose run --rm django python3 -m grpc.tools.protoc -Iservis --python_out=$OUTPUT --grpc_python_out=$OUTPUT servis/vseth/sip/payment/payment.proto servis/vseth/sip/products/products.proto