#!/usr/bin/env bash
# 出向網路白名單（spec §3.3）—— 這是**主機層**設定，docker compose 本身做不到。
#
# 目的：讓 CTF 容器只能連 openrouter.ai，連不到你的內網或任何其他目標。
# 這很重要：這個平臺刻意含漏洞，萬一被學員（或外人）拿到執行能力，
# 出向白名單是最後一道防線。
#
# 用法（在 docker host 上，root 執行）：
#     sudo bash scripts/egress_whitelist.sh apply
#     sudo bash scripts/egress_whitelist.sh remove
#
# 注意：
# - openrouter.ai 走 CDN，IP 會變。這裡每次執行時解析並寫入，建議放 cron 每小時重跑 apply。
# - 更穩的做法是改用「只允許 443 到指定 egress proxy」＋ proxy 端做網域白名單。
# - 請先確認你的 iptables 沒有被其他工具（firewalld/ufw）託管。

set -euo pipefail

CHAIN="CTF_EGRESS"
NET_NAME="${NET_NAME:-ais-ctf-net}"
ALLOW_HOSTS="${ALLOW_HOSTS:-openrouter.ai}"

subnet() {
  docker network inspect "$NET_NAME" \
    -f '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null || true
}

apply() {
  SUBNET="$(subnet)"
  if [[ -z "$SUBNET" ]]; then
    echo "找不到 docker network '$NET_NAME'，請先 docker compose up。" >&2
    exit 1
  fi
  echo "容器子網：$SUBNET"

  iptables -N "$CHAIN" 2>/dev/null || iptables -F "$CHAIN"

  # 允許 DNS（解析 openrouter.ai 需要）
  iptables -A "$CHAIN" -p udp --dport 53 -j ACCEPT
  iptables -A "$CHAIN" -p tcp --dport 53 -j ACCEPT
  # 允許已建立的回程
  iptables -A "$CHAIN" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

  for host in $ALLOW_HOSTS; do
    for ip in $(getent ahostsv4 "$host" | awk '{print $1}' | sort -u); do
      echo "  允許 $host -> $ip:443"
      iptables -A "$CHAIN" -d "$ip" -p tcp --dport 443 -j ACCEPT
    done
  done

  # 其餘一律拒絕（含所有 RFC1918 內網）
  iptables -A "$CHAIN" -j REJECT --reject-with icmp-admin-prohibited

  iptables -D DOCKER-USER -s "$SUBNET" -j "$CHAIN" 2>/dev/null || true
  iptables -I DOCKER-USER 1 -s "$SUBNET" -j "$CHAIN"
  echo "已套用。驗證： docker compose exec app python -c \"import socket;socket.create_connection(('1.1.1.1',443),3)\"（應該要失敗）"
}

remove() {
  SUBNET="$(subnet)"
  [[ -n "$SUBNET" ]] && iptables -D DOCKER-USER -s "$SUBNET" -j "$CHAIN" 2>/dev/null || true
  iptables -F "$CHAIN" 2>/dev/null || true
  iptables -X "$CHAIN" 2>/dev/null || true
  echo "已移除。"
}

case "${1:-}" in
  apply) apply ;;
  remove) remove ;;
  *) echo "用法：$0 {apply|remove}" >&2; exit 2 ;;
esac
