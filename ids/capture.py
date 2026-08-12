"""
ids/capture.py — Live packet capture using Scapy.
Runs as a daemon thread started from main.py on startup.
Requires root or CAP_NET_RAW privilege.
"""

import time
import logging
import socket

logger = logging.getLogger("ids.capture")


def _get_local_ips() -> set:
    """Return the set of IP addresses assigned to this machine."""
    ips = {"127.0.0.1"}
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ips.add(info[4][0])
    except Exception:
        pass
    # Also try the common way
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return ips


def start(interface: str, aggregator):
    """
    Start live packet capture on *interface*.
    Calls aggregator.add_packet(pkt_info) for every IP packet.
    This function blocks — run it in a daemon thread.
    """
    try:
        from scapy.all import sniff, IP, TCP
    except ImportError:
        logger.error("scapy is not installed — packet capture disabled.")
        return

    local_ips = _get_local_ips()

    def _process_packet(pkt):
        try:
            if not pkt.haslayer(IP):
                return

            ip_layer = pkt[IP]
            src_ip = ip_layer.src
            dst_ip = ip_layer.dst
            proto = ip_layer.proto  # 6=TCP, 17=UDP, 1=ICMP

            src_port = 0
            dst_port = 0
            syn = fin = rst = psh = ack = urg = 0
            win = 0

            if pkt.haslayer(TCP):
                tcp = pkt[TCP]
                src_port = tcp.sport
                dst_port = tcp.dport
                flags = tcp.flags
                syn = 1 if flags & 0x02 else 0
                fin = 1 if flags & 0x01 else 0
                rst = 1 if flags & 0x04 else 0
                psh = 1 if flags & 0x08 else 0
                ack = 1 if flags & 0x10 else 0
                urg = 1 if flags & 0x20 else 0
                win = tcp.window
            else:
                # UDP / ICMP — try sport/dport if present
                if hasattr(pkt, "sport"):
                    src_port = pkt.sport
                if hasattr(pkt, "dport"):
                    dst_port = pkt.dport

            direction = "fwd" if src_ip in local_ips else "bwd"

            pkt_info = {
                "source": "packet",
                "timestamp": time.time(),
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "src_port": src_port,
                "dst_port": dst_port,
                "proto": proto,
                "size": len(pkt),
                "hdr_len": ip_layer.ihl * 4,
                "direction": direction,
                "syn": syn,
                "fin": fin,
                "rst": rst,
                "psh": psh,
                "ack": ack,
                "urg": urg,
                "win": win,
            }

            aggregator.add_packet(pkt_info)

        except Exception as exc:
            logger.debug(f"Packet processing error: {exc}")

    logger.info(f"Starting packet capture on interface '{interface}' …")
    try:
        sniff(iface=interface, prn=_process_packet, store=False)
    except PermissionError:
        logger.error(
            "Packet capture requires root privileges. "
            "Run with sudo or grant CAP_NET_RAW."
        )
    except Exception as exc:
        logger.error(f"Packet capture failed: {exc}")
