#!/bin/bash
# 从 /etc/resolv.conf 动态获取 WSL2 宿主机 IP
WSL_HOST=$(grep nameserver /etc/resolv.conf | awk '{print $2}')
export HTTP_PROXY="http://${WSL_HOST}:7897"
export HTTPS_PROXY="http://${WSL_HOST}:7897"
export ALL_PROXY="socks5://${WSL_HOST}:7898"
export USE_PROXY=true
exec /usr/bin/python3 /home/pascal/.openclaw/workspace/skills/investment/research/daily_stock_analysis/main.py
