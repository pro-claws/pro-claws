#!/bin/bash
# Run in the operator's terminal. Sudo authenticates locally on Linode.
# Installs reviewed controls and performs preparation; never fences or routes.
set -euo pipefail
ssh -t vendistri-prod 'sudo install -o root -g root -m 0755 /home/akatary/pro_claws/.migration/aws-20261024/install_source_control.py /usr/local/sbin/vendistri-install-cutover && echo "edd993965818090971654d99d48bf5893a68fa4a305107601df5c8fc01f26005  /usr/local/sbin/vendistri-install-cutover" | sudo sha256sum -c - && sudo /usr/local/sbin/vendistri-install-cutover'
