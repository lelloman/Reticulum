# Reticulum - Claude Code Knowledge Base

## Overview

**Reticulum** is a self-configuring, encrypted, and resilient mesh networking stack for building local and wide-area networks with readily available hardware. It's designed to work over diverse physical media and extremely low bandwidths (down to 5 bits/second).

### Key Features
- **Uncentralized**: No central authority; identity based on cryptographic keys, not location
- **Encryption by default**: All communication encrypted with X25519/Ed25519/AES-256
- **Multi-medium**: Works over LoRa, TCP, UDP, Serial, I2P, and more
- **Resilient**: Store-and-forward design for intermittent/high-latency networks
- **Nomadic**: Nodes can roam between different connection types seamlessly

### License
Reticulum License with two restrictions:
1. Cannot be used in systems designed to harm humans
2. Cannot be used to create AI/ML training datasets

---

## Repository Structure

```
/home/lelloman/Reticulum/
├── RNS/                      # Core Python library
│   ├── Reticulum.py          # Master instance & config (1716 lines)
│   ├── Transport.py          # Mesh routing engine (3312 lines)
│   ├── Link.py               # Encrypted links (1549 lines)
│   ├── Identity.py           # Cryptographic identities (821 lines)
│   ├── Destination.py        # Communication endpoints (691 lines)
│   ├── Packet.py             # Packet handling (602 lines)
│   ├── Resource.py           # Large data transfers (1361 lines)
│   ├── Channel.py            # Structured messaging (705 lines)
│   ├── Buffer.py             # Stream I/O (369 lines)
│   ├── Discovery.py          # Interface discovery (733 lines)
│   ├── Resolver.py           # Identity resolution (stub)
│   ├── Cryptography/         # Crypto implementations
│   ├── Interfaces/           # Network interface implementations
│   ├── Utilities/            # CLI tools (rnsd, rnstatus, etc.)
│   └── vendor/               # Vendored dependencies
├── Examples/                 # 14 example applications
├── tests/                    # Unit test suite
├── docs/                     # Sphinx documentation
│   ├── manual/               # Compiled HTML manual
│   ├── source/               # RST source files
│   ├── Reticulum Manual.pdf  # PDF manual
│   └── Reticulum Manual.epub # EPUB e-book
├── setup.py                  # Package configuration
├── Makefile                  # Build automation
├── README.md                 # Project overview
├── Changelog.md              # Release history
├── Roadmap.md                # Development priorities
└── Zen of Reticulum.md       # Philosophy document
```

---

## Core Architecture

### Module Hierarchy
```
Reticulum (singleton master)
├── manages Interfaces[]
├── manages Transport (static routing engine)
│   ├── Destinations[]
│   ├── Links (pending & active)
│   ├── path_table (routing)
│   ├── link_table
│   └── announce_table
└── manages Identity

Identity
├── X25519 keys (encryption)
├── Ed25519 keys (signing)
└── known_destinations cache

Destination → Packet → Transport → Interface → Network
Link (over Destination) → Channel → Buffer
Resource (over Link) → segmented transfer
```

### Key Classes

| Class | File | Purpose |
|-------|------|---------|
| `Reticulum` | RNS/Reticulum.py | Master instance, config loading, lifecycle |
| `Transport` | RNS/Transport.py | Static routing engine, path discovery |
| `Identity` | RNS/Identity.py | Cryptographic identity (keys, signing) |
| `Destination` | RNS/Destination.py | Network endpoint (SINGLE/GROUP/PLAIN/LINK) |
| `Link` | RNS/Link.py | Encrypted bidirectional channel |
| `Packet` | RNS/Packet.py | Atomic transmission unit |
| `Resource` | RNS/Resource.py | Large file/data transfer |
| `Channel` | RNS/Channel.py | Structured message protocol |
| `Interface` | RNS/Interfaces/Interface.py | Abstract hardware interface |

### Constants
- **MTU**: 500 bytes
- **Encrypted MDU**: 383 bytes
- **Minimum bitrate**: 5 bits/second
- **Truncated hash length**: 128 bits (16 bytes)
- **Identity key size**: 512 bits (256 encryption + 256 signing)
- **Max hops**: 128
- **Link keepalive**: 360 seconds
- **Path expiry**: 7 days (normal), 1 day (AP), 6 hours (roaming)

---

## Network Interfaces

Located in `RNS/Interfaces/`:

| Interface | File | Description |
|-----------|------|-------------|
| RNode | RNodeInterface.py | LoRa radio modem (70KB, most complex) |
| RNode Multi | RNodeMultiInterface.py | Multiple RNode devices |
| TCP | TCPInterface.py | TCP/IP connections |
| UDP | UDPInterface.py | UDP broadcast/multicast |
| Serial | SerialInterface.py | Serial port (UART) |
| KISS | KISSInterface.py | KISS modem protocol |
| AX.25 | AX25KISSInterface.py | Amateur radio AX.25 |
| Local | LocalInterface.py | Inter-process communication |
| Auto | AutoInterface.py | Auto-discovery (Ethernet/WiFi) |
| Backbone | BackboneInterface.py | Mesh backbone (Unix socket) |
| Weave | WeaveInterface.py | Weave mesh protocol |
| I2P | I2PInterface.py | I2P anonymity network |
| Pipe | PipeInterface.py | Named pipes |

### Interface Modes
- `FULL`: Full routing participation
- `POINT_TO_POINT`: Direct connection only
- `ACCESS_POINT`: Limited routing
- `ROAMING`: Mobile/nomadic node
- `BOUNDARY`: Network boundary
- `GATEWAY`: Gateway to other networks

---

## Cryptography

Located in `RNS/Cryptography/`:

| Algorithm | File | Purpose |
|-----------|------|---------|
| X25519 | X25519.py | Key exchange (ECDH) |
| Ed25519 | Ed25519.py | Digital signatures |
| AES-256-CBC | AES.py | Symmetric encryption |
| SHA-256/512 | Hashes.py | Hashing |
| HMAC | HMAC.py | Message authentication |
| HKDF | HKDF.py | Key derivation |
| PKCS7 | PKCS7.py | Padding |
| Token | Token.py | Encrypted tokens |

### Crypto Provider System
- **PYCA**: Uses PyCA/cryptography library (faster)
- **INTERNAL**: Pure Python fallback (no dependencies)

Auto-detected in `Cryptography/Provider.py`.

---

## Configuration

### Default Location
`~/.reticulum/config`

### Configuration Sections
```ini
[reticulum]
enable_transport = true
share_instance = true
instance_name = default
shared_instance_port = 37428
instance_control_port = 37429
panic_on_interface_error = false

[logging]
loglevel = 4

[interfaces]
# Interface definitions here
```

### Programmatic Configuration
```python
import RNS
reticulum = RNS.Reticulum(configpath="/path/to/config")
```

---

## CLI Tools

Installed via pip, defined in setup.py entry_points:

| Command | File | Purpose |
|---------|------|---------|
| `rnsd` | RNS/Utilities/rnsd.py | Run as daemon/service |
| `rnstatus` | RNS/Utilities/rnstatus.py | Display network status |
| `rnpath` | RNS/Utilities/rnpath.py | Path table management |
| `rnprobe` | RNS/Utilities/rnprobe.py | Connectivity diagnostics |
| `rncp` | RNS/Utilities/rncp.py | File transfer utility |
| `rnid` | RNS/Utilities/rnid.py | Identity management |
| `rnx` | RNS/Utilities/rnx.py | Remote command execution |
| `rnir` | RNS/Utilities/rnir.py | Interface reporting |
| `rnpkg` | RNS/Utilities/rnpkg.py | Package management |
| `rnodeconf` | RNS/Utilities/rnodeconf.py | RNode device configuration |

---

## Examples

Located in `Examples/`:

| Example | Purpose |
|---------|---------|
| Minimal.py | Basic RNS initialization |
| Announce.py | Destination announcements |
| Echo.py | Echo server/client |
| Link.py | Link establishment |
| Identify.py | Identity verification |
| Request.py | Request/response pattern |
| Channel.py | Channel messaging |
| Resource.py | Resource transfers |
| Filetransfer.py | File transfer demo |
| Buffer.py | Buffer/streaming |
| Broadcast.py | Broadcast messaging |
| Ratchets.py | Forward secrecy/ratcheting |
| Speedtest.py | Performance testing |
| ExampleInterface.py | Custom interface example |

### Basic Usage Pattern
```python
import RNS

# Initialize
reticulum = RNS.Reticulum(configpath=None)

# Create identity
identity = RNS.Identity()

# Create destination
destination = RNS.Destination(
    identity,
    RNS.Destination.IN,
    RNS.Destination.SINGLE,
    "app_name",
    "aspect"
)

# Announce presence
destination.announce()

# Create link to remote destination
link = RNS.Link(remote_destination)

# Send data
packet = RNS.Packet(destination, data)
packet.send()

# Transfer large files
resource = RNS.Resource(data, link)
```

---

## Testing

### Test Location
`tests/`

### Test Files
- `tests/all.py` - Main test runner
- `tests/identity.py` - Identity/crypto tests
- `tests/hashes.py` - Hash function tests
- `tests/link.py` - Link communication tests
- `tests/channel.py` - Channel messaging tests

### Running Tests
```bash
make test
# or
python3 -m tests.all
```

### CI/CD
GitHub Actions workflow in `.github/workflows/build.yml`:
- Runs on Ubuntu with Python 3.11
- Tests on every push/PR
- Builds wheels on tags

---

## Build System

### Makefile Targets
```bash
make test              # Run unit tests
make clean             # Clean build artifacts
make documentation     # Build HTML docs
make manual            # Build PDF/EPUB manual
make release           # Full release (test + docs + wheels)
make debug             # Debug build (wheels only)
make upload            # Upload to PyPI
```

### Package Variants
1. **rns** - Standard with dependencies (cryptography, pyserial)
2. **rnspure** - Pure Python, zero dependencies

### Installation
```bash
pip install rns        # Standard
pip install rnspure    # Pure Python
pipx install rns       # Isolated environment
```

---

## Protocol Details

### Packet Types
- `DATA`: Application data
- `ANNOUNCE`: Destination announcements
- `LINKREQUEST`: Link establishment request
- `PROOF`: Delivery proof

### Packet Contexts
- `NONE`, `RESOURCE`, `REQUEST`, `RESPONSE`, `CHANNEL`, `KEEPALIVE`, `COMMAND`

### Destination Types
- `SINGLE`: Point-to-point (encrypted to recipient's key)
- `GROUP`: Multicast (pre-shared key)
- `PLAIN`: Unencrypted
- `LINK`: Via established Link

### Link States
`PENDING` → `HANDSHAKE` → `ACTIVE` → `STALE` → `CLOSED`

### Link Establishment (4-way handshake)
1. Initiator sends LINKREQUEST with ephemeral public key
2. Responder generates session keys, sends LINKIDENTIFY proof
3. Initiator verifies, derives same keys, sends proof back
4. Link becomes ACTIVE

### Resource Transfer
- Window-based flow control (2-75 bytes)
- Automatic compression (bz2) for large payloads
- Up to 16 retries per segment
- Supports up to 16MB efficiently (theoretical 16GB)

### PATHFINDER Algorithm
- Controlled flooding of announcements
- Path selection by hop count
- Bandwidth cap: 2% of interface bandwidth
- Queued announces expire after 24 hours

---

## Documentation

### Online Manual
https://markqvist.github.io/Reticulum/manual/

### Local Documentation
- HTML: `docs/manual/`
- PDF: `docs/Reticulum Manual.pdf`
- EPUB: `docs/Reticulum Manual.epub`
- RST sources: `docs/source/`

### Key Documentation Files
- `README.md` - Project overview (22KB)
- `Zen of Reticulum.md` - Philosophy (36KB)
- `Contributing.md` - Contribution guidelines
- `Changelog.md` - Release history (77KB)
- `Roadmap.md` - Development priorities

---

## Important File Paths

### Core Implementation
- `RNS/Reticulum.py` - Main class
- `RNS/Transport.py` - Routing (largest file)
- `RNS/Link.py` - Links
- `RNS/Identity.py` - Identities
- `RNS/Destination.py` - Destinations
- `RNS/Packet.py` - Packets
- `RNS/Resource.py` - Resources
- `RNS/Channel.py` - Channels

### Cryptography
- `RNS/Cryptography/__init__.py` - Provider selection
- `RNS/Cryptography/Provider.py` - Backend detection
- `RNS/Cryptography/X25519.py` - Key exchange
- `RNS/Cryptography/Ed25519.py` - Signatures
- `RNS/Cryptography/AES.py` - Encryption
- `RNS/Cryptography/pure25519/` - Pure Python Curve25519

### Interfaces
- `RNS/Interfaces/Interface.py` - Base class
- `RNS/Interfaces/RNodeInterface.py` - LoRa (largest interface)
- `RNS/Interfaces/TCPInterface.py` - TCP
- `RNS/Interfaces/UDPInterface.py` - UDP

### Version
- `RNS/_version.py` - Current version: 1.1.3

---

## Development Notes

### Design Patterns Used
- **Callback Pattern**: Event-driven communication
- **Factory Pattern**: Hash/identity creation
- **Observer Pattern**: PacketReceipt, progress tracking
- **Registry Pattern**: Transport maintains static lookups
- **State Machine**: Link/Resource states
- **Pluggable Provider**: Crypto backend selection

### Philosophy (Zen of Reticulum)
1. **Illusion of Center**: No privileged nodes
2. **Physics of Trust**: Cryptographic proof, not institutional
3. **Merits of Scarcity**: Optimized for constrained networks
4. **Sovereignty**: User-controlled identity
5. **Identity/Nomadism**: Location-independent identity
6. **Ethics**: Built for human flourishing
7. **Design Patterns**: Simplicity, resilience
8. **Independence**: Works without infrastructure

### Current Version
RNS 1.1.3 (2026-01-17)

### Python Requirements
Python >= 3.7

---

## Rust Port (`rns-rs/`)

A Rust implementation of RNS, organized as a Cargo workspace. `rns-crypto` and `rns-core` are `no_std`-compatible with zero external dependencies. `rns-net` is `std`-only and drives the core via real sockets and threads.

### Workspace Structure
```
rns-rs/
├── Cargo.toml                  # Workspace: members = ["rns-crypto", "rns-core", "rns-net", "rns-cli"]
├── rns-crypto/                 # Phase 1: Crypto primitives
│   ├── Cargo.toml
│   ├── src/
│   │   ├── lib.rs              # Rng trait, FixedRng, OsRng
│   │   ├── bigint.rs           # Big integer arithmetic
│   │   ├── pkcs7.rs            # PKCS#7 padding
│   │   ├── sha256.rs           # SHA-256
│   │   ├── sha512.rs           # SHA-512
│   │   ├── hmac.rs             # HMAC-SHA256
│   │   ├── hkdf.rs             # HKDF key derivation
│   │   ├── aes.rs              # AES core (S-box, MixColumns, etc.)
│   │   ├── aes128.rs           # AES-128-CBC
│   │   ├── aes256.rs           # AES-256-CBC
│   │   ├── token.rs            # Encrypted token (IV + AES-CBC + HMAC)
│   │   ├── x25519.rs           # X25519 ECDH key exchange
│   │   ├── ed25519.rs          # Ed25519 signatures
│   │   └── identity.rs         # High-level Identity (encrypt/decrypt/sign/verify)
│   └── tests/
│       └── interop.rs          # 11 interop tests vs Python vectors
├── rns-core/                   # Phase 2+3+4a+4b: Wire protocol + Transport + Link + Resource
│   ├── Cargo.toml              # depends on rns-crypto
│   ├── src/
│   │   ├── lib.rs
│   │   ├── constants.rs        # All protocol + transport constants
│   │   ├── hash.rs             # full_hash, truncated_hash, name_hash
│   │   ├── packet.rs           # PacketFlags + RawPacket pack/unpack/hash
│   │   ├── destination.rs      # expand_name, destination_hash
│   │   ├── announce.rs         # AnnounceData pack/unpack/validate
│   │   ├── receipt.rs          # Proof validation (explicit/implicit)
│   │   ├── transport/          # Phase 3: Routing engine
│   │   │   ├── mod.rs, types.rs, tables.rs, dedup.rs
│   │   │   ├── pathfinder.rs, announce_proc.rs
│   │   │   ├── inbound.rs, outbound.rs, rate_limit.rs, jobs.rs
│   │   ├── link/               # Phase 4a: Link engine
│   │   │   ├── mod.rs, types.rs, handshake.rs
│   │   │   ├── crypto.rs, keepalive.rs, identify.rs
│   │   ├── channel/            # Phase 4a: Channel messaging
│   │   │   ├── mod.rs, types.rs, envelope.rs
│   │   ├── buffer/             # Phase 4a: Buffer streaming
│   │   │   ├── mod.rs, types.rs
│   │   ├── msgpack.rs          # Phase 4b: Minimal msgpack codec
│   │   └── resource/           # Phase 4b: Resource transfer
│   │       ├── mod.rs, types.rs, advertisement.rs
│   │       ├── parts.rs, window.rs, sender.rs, receiver.rs, proof.rs
│   └── tests/
│       ├── interop.rs              # 12 interop tests vs Python vectors
│       ├── transport_integration.rs # 15 integration tests
│       ├── link_integration.rs     # 9 link/channel/buffer integration tests
│       └── resource_integration.rs # 8 resource transfer integration tests
├── rns-net/                    # Phase 5a-5d+6a: Network node (std-only)
│   ├── Cargo.toml              # depends on rns-core, rns-crypto, log, libc
│   ├── src/
│   │   ├── lib.rs              # Public API, re-exports
│   │   ├── hdlc.rs             # HDLC escape/unescape/frame + streaming Decoder
│   │   ├── kiss.rs             # KISS framing (FEND/FESC) + streaming Decoder
│   │   ├── rnode_kiss.rs       # RNode KISS commands + streaming RNodeDecoder
│   │   ├── event.rs            # Event enum + QueryRequest/QueryResponse
│   │   ├── time.rs             # now() → f64 Unix epoch
│   │   ├── config.rs           # ConfigObj parser for Python RNS config files
│   │   ├── storage.rs          # Identity + known destinations persistence
│   │   ├── ifac.rs             # IFAC derive/mask/unmask (Interface Access Codes)
│   │   ├── serial.rs           # Raw serial I/O via libc termios
│   │   ├── pickle.rs           # Minimal pickle codec (proto 2 encode, 2–5 decode)
│   │   ├── md5.rs              # MD5 + HMAC-MD5 for Python multiprocessing auth
│   │   ├── rpc.rs              # Python multiprocessing.connection wire protocol
│   │   ├── driver.rs           # Callbacks, Driver loop, InterfaceStats, query dispatch
│   │   ├── node.rs             # RnsNode lifecycle + share_instance/RPC config
│   │   └── interface/
│   │       ├── mod.rs          # Writer trait, InterfaceEntry
│   │       ├── tcp.rs          # TCP client: connect, reconnect, reader thread
│   │       ├── tcp_server.rs   # TCP server: accept, per-client reader threads
│   │       ├── udp.rs          # UDP broadcast interface (no HDLC framing)
│   │       ├── local.rs        # Unix abstract socket + TCP fallback
│   │       ├── serial_iface.rs # Serial + HDLC framing, reconnect
│   │       ├── kiss_iface.rs   # KISS + flow control, TNC config
│   │       ├── pipe.rs         # Subprocess stdin/stdout + HDLC, auto-respawn
│   │       ├── rnode.rs        # RNode LoRa radio, multi-sub, flow control
│   │       └── backbone.rs     # TCP mesh backbone, Linux epoll
│   ├── examples/
│   │   ├── tcp_connect.rs      # Connect to Python RNS, log announces
│   │   └── rnsd.rs             # Rust rnsd daemon (config-driven)
│   └── tests/
│       ├── python_interop.rs   # Rust↔Python announce reception
│       └── ifac_interop.rs     # IFAC mask/unmask vs Python vectors
├── rns-cli/                    # Phase 6a: CLI binaries (std-only)
│   ├── Cargo.toml              # depends on rns-net, rns-core, rns-crypto, log, env_logger, libc
│   └── src/
│       ├── lib.rs              # Re-exports
│       ├── args.rs             # Simple argument parser (no external deps)
│       ├── format.rs           # size_str, speed_str, prettytime, prettyhexrep
│       └── bin/
│           ├── rnsd.rs         # Daemon: start node from config, signal handling
│           ├── rnstatus.rs     # Interface stats via RPC connection
│           ├── rnpath.rs       # Path/rate table management via RPC
│           └── rnid.rs         # Identity management (standalone, no RPC)
└── tests/
    ├── generate_vectors.py     # Generates JSON test fixtures from Python RNS
    └── fixtures/
        ├── crypto/             # 11 JSON fixture files (Phase 1)
        ├── protocol/           # 6 JSON fixture files (Phase 2)
        ├── transport/          # 4 JSON fixture files (Phase 3)
        ├── link/               # 5 JSON fixture files (Phase 4a)
        ├── resource/           # 6 JSON fixture files (Phase 4b)
        └── ifac/               # 1 JSON fixture file (Phase 5c)
```

### Key APIs

**rns-crypto::Identity**
- `new(rng)`, `from_private_key(&[u8; 64])`, `from_public_key(&[u8; 64])`
- `encrypt(plaintext, rng)`, `decrypt(ciphertext)`
- `sign(message)` → `[u8; 64]`, `verify(signature, message)` → `bool`
- `hash()` → `&[u8; 16]` (truncated SHA-256 of public key)

**rns-core::packet::RawPacket**
- `pack(flags, hops, dest_hash, transport_id, context, data)` → wire bytes
- `unpack(raw)` → parsed fields + packet hash
- `get_hashable_part()`, `get_hash()`, `get_truncated_hash()`

**rns-core::announce::AnnounceData**
- `pack(identity, dest_hash, name_hash, random_hash, ratchet, app_data)` → announce bytes
- `unpack(data, has_ratchet)` → parsed fields
- `validate(dest_hash)` → `ValidatedAnnounce` (signature + hash verification)

**rns-core::transport::TransportEngine**
- `new(config)` → create engine with `TransportConfig`
- `register_interface(info)`, `deregister_interface(id)` — manage interfaces
- `register_destination(hash, type)`, `deregister_destination(hash)` — manage local destinations
- `handle_inbound(raw, iface, now, rng)` → `Vec<TransportAction>` — process incoming packet
- `handle_outbound(packet, dest_type, attached_iface, now)` → `Vec<TransportAction>` — route outgoing packet
- `tick(now, rng)` → `Vec<TransportAction>` — periodic maintenance (retransmit, cull)
- `has_path(hash)`, `hops_to(hash)`, `next_hop(hash)`, `next_hop_interface(hash)` — path queries
- Action queue model: no callbacks, no I/O; caller inspects `TransportAction` variants and performs I/O

**rns-net::RnsNode**
- `from_config(config_path, callbacks)` → read config file, load/create identity, start interfaces
- `start(config, callbacks)` → connect interfaces, start driver + timer threads
- `shutdown(self)` → stop driver, wait for thread exit
- Thread model: single Driver thread (owns TransportEngine), per-interface Reader threads, Timer thread
- All communication via single `mpsc::channel()` of `Event` variants

**rns-net::Callbacks** (trait)
- `on_announce(dest_hash, identity_hash, public_key, app_data, hops)` — announce received
- `on_path_updated(dest_hash, hops)` — path table updated
- `on_local_delivery(dest_hash, raw, packet_hash)` — packet for local destination
- `on_interface_up(id)` / `on_interface_down(id)` — interface state changes (default no-op)

### Running Tests
```bash
cd rns-rs

# Generate test vectors from Python (requires RNS importable)
python3 tests/generate_vectors.py

# Run all Rust tests
cargo test

# Run only one crate
cargo test -p rns-crypto
cargo test -p rns-core
cargo test -p rns-net
cargo test -p rns-cli
```

### Test Counts
- **rns-crypto**: 65 unit tests + 11 interop tests = 76
- **rns-core**: 331 unit tests + 12 interop tests + 32 integration tests = 375
- **rns-net**: 215 unit tests + 2 interop tests = 217
- **rns-cli**: 9 unit tests = 9
- **Total**: 677 tests
