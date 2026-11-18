"""Discover a telemetry LAN without changing system networking."""
import argparse
import ipaddress
import json
from pathlib import Path
import subprocess
import sys

CHOICE_FILE = Path(__file__).with_name('.network-choice.json')


def command(args):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return ''


def discover():
    """Return active IPv4 broadcast networks and Linux AP/default-route roles."""
    if sys.platform == 'win32':
        raw = command(['powershell.exe', '-NoProfile', '-Command',
                       'Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.AddressState -eq "Preferred"} | Select-Object InterfaceAlias,IPAddress,PrefixLength | ConvertTo-Json -Compress'])
        entries = json.loads(raw or '[]')
        if isinstance(entries, dict):
            entries = [entries]
        rows = [dict(ifname=e['InterfaceAlias'], flags=['UP', 'BROADCAST'],
                     addr_info=[dict(local=e['IPAddress'], prefixlen=e['PrefixLength'])]) for e in entries]
    else:
        rows = json.loads(command(['ip', '-j', '-4', 'address', 'show']) or '[]')
    aps = set()
    interface = None
    for line in command(['iw', 'dev']).splitlines():
        parts = line.split()
        if parts[:1] == ['Interface']:
            interface = parts[1]
        if parts == ['type', 'AP']:
            aps.add(interface)
    routes = json.loads(command(['ip', '-j', '-4', 'route', 'show', 'default']) or '[]')
    uplinks = {r.get('dev') for r in routes}
    networks = []
    for row in rows:
        name = row['ifname']
        if 'UP' not in row.get('flags', []) or row.get('operstate') == 'DOWN':
            continue
        if name.startswith(('lo', 'docker', 'veth', 'br-', 'tailscale', 'tun', 'tap', 'virbr', 'vEthernet')):
            continue
        for address in row.get('addr_info', []):
            ip = ipaddress.ip_interface(f"{address['local']}/{address['prefixlen']}")
            if ip.version != 4 or ip.ip.is_loopback or ip.ip.is_link_local or ip.network.prefixlen >= 31:
                continue
            networks.append(dict(interface=name, ip=str(ip.ip), network=str(ip.network),
                                 broadcast=str(ip.network.broadcast_address),
                                 hotspot=name in aps, uplink=name in uplinks))
    return networks


def select(networks, interface=None, remembered=None):
    if interface:
        candidates = [n for n in networks if n['interface'] == interface]
        if len(candidates) != 1:
            raise ValueError(f'Interface {interface!r} needs exactly one active IPv4 network.')
        return candidates[0]
    hotspots = [n for n in networks if n['hotspot']]
    if len(hotspots) == 1:
        return hotspots[0]
    candidates = hotspots or networks
    if remembered:
        matching = [n for n in candidates if (n['interface'], n['network']) == tuple(remembered)]
        if len(matching) == 1:
            return matching[0]
    # Multiple addresses on the same subnet still identify one broadcast LAN.
    if len({n['network'] for n in candidates}) == 1:
        return candidates[0]
    raise ValueError('Select the telemetry network with --telemetry-interface NAME or --broadcast ADDRESS.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--telemetry-interface')
    parser.add_argument('--broadcast')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--subscription-port', type=int)
    parser.add_argument('--stream-port', type=int, default=8080)
    args, _ = parser.parse_known_args()
    networks = discover()
    remembered = None
    try:
        remembered = json.loads(CHOICE_FILE.read_text()).get('selection')
        if not isinstance(remembered, list) or len(remembered) != 2 or not all(isinstance(v, str) for v in remembered):
            remembered = None
    except (OSError, ValueError, AttributeError):
        pass
    chosen = None
    try:
        chosen = select(networks, args.telemetry_interface, remembered)
    except ValueError as error:
        if args.telemetry_interface:
            raise SystemExit(str(error))
        if not args.broadcast:
            if not networks or not sys.stdin.isatty():
                raise SystemExit(str(error))
            print('Choose the telemetry network:', file=sys.stderr)
            for i, n in enumerate(networks, 1):
                print(f"  {i}) {n['interface']} — {n['ip']} ({n['network']})", file=sys.stderr)
            while chosen is None:
                print('Network number: ', end='', file=sys.stderr, flush=True)
                answer = input()
                if answer.isdigit() and 1 <= int(answer) <= len(networks):
                    chosen = networks[int(answer) - 1]
            try:
                CHOICE_FILE.write_text(json.dumps({'selection': [chosen['interface'], chosen['network']]}))
            except OSError:
                print('Could not save network choice; it will be requested next time.', file=sys.stderr)
    destination = args.broadcast or chosen['broadcast']
    if args.broadcast:
        chosen = next((n for n in networks if n['broadcast'] == args.broadcast), chosen)
    if chosen:
        role = 'hotspot' if chosen['hotspot'] else 'LAN'
        print(f"Telemetry network: {chosen['interface']} ({role}) — {chosen['ip']}", file=sys.stderr)
    print(f'Broadcast: {destination}:{args.port}', file=sys.stderr)
    for n in networks:
        role = 'hotspot' if n['hotspot'] else ('default route' if n['uplink'] else 'LAN')
        print(f"  {n['interface']} ({role}): subscriptions {n['ip']}:{args.subscription_port or args.port + 1}; camera http://{n['ip']}:{args.stream_port}/", file=sys.stderr)
    print('Subscription requests go to the address above; replies return to the client socket.', file=sys.stderr)
    print(destination)


if __name__ == '__main__':
    main()
