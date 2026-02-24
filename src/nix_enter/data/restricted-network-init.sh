#!/bin/bash
# Set up restricted networking, then drop NET_ADMIN and exec shell

# Allow loopback
iptables -A OUTPUT -o lo -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow DNS
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

# Allow each domain
IFS=',' read -ra DOMAINS <<< "$NIX_ENTER_ALLOWED_DOMAINS"
for domain in "${DOMAINS[@]}"; do
    for ip in $(dig +short A "$domain" 2>/dev/null); do
        iptables -A OUTPUT -d "$ip" -j ACCEPT
    done
done

# Drop everything else
iptables -A OUTPUT -j DROP

# Drop NET_ADMIN capability and exec the real entrypoint
exec capsh --drop=cap_net_admin -- -c "exec $*"
