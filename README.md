# Clwd

**Fast cloud deployment CLI for Claude Code with live preview URLs**

Clwd is a deployment and management CLI tool that creates remote cloud instances running [Claude Code](https://claude.ai/code) with live preview URLs and optional security hardening. Think "Netlify for Claude Code" - it provisions VPS instances on cloud providers with Claude Code pre-installed, authenticated, and ready to use.

## Features

- 🚀 **Fast Deployment**: Deploy Claude Code instances in under 3 minutes
- 🔗 **Live Preview URLs**: Automatic port forwarding and preview URL generation
- 🛡️ **Security Hardening**: Multiple security levels from development to production
- 🔐 **Zero-Config Auth**: Seamless Claude Code authentication transfer
- 🌐 **Multi-Provider**: Extensible cloud provider architecture (Hetzner Cloud supported)
- 💻 **Interactive Sessions**: Full SSH access and remote development environment

## Quick Start

### Installation

```bash
# Install from PyPI (recommended)
pip install clwd

# Or install from source
git clone https://github.com/clwd-ai/clwd.git
cd clwd
pip install -e .
```

### Prerequisites

- **macOS or Linux**: Currently supports macOS and Linux systems
- **SSH Key**: Must have an SSH key in standard locations (`~/.ssh/id_ed25519`, `~/.ssh/id_rsa`, `~/.ssh/id_ecdsa`)
- **Claude Code**: Must be authenticated locally (`claude auth login`)
- **Cloud Provider**: API credentials for supported providers

### Basic Usage

```bash
# Initialize a new project
clwd init --name myproject --size medium

# Open interactive SSH session with Claude Code
clwd open --name myproject

# Execute commands remotely
clwd exec --name myproject "echo 'Hello from the cloud!'"

# Check project status
clwd status --name myproject

# Destroy instance when done
clwd destroy --name myproject
```

## Supported Providers

### Hetzner Cloud

**Setup:**
```bash
export HETZNER_API_TOKEN=your_token_here
```

**Instance Sizes:**
- `small`: CPX11 (2 vCPU, 4 GB RAM) - €4.51/month
- `medium`: CPX21 (3 vCPU, 8 GB RAM) - €9.07/month  
- `large`: CPX31 (4 vCPU, 16 GB RAM) - €17.86/month

## Security Hardening Levels

Clwd offers three security hardening levels to balance development convenience with production security:

### None (Development)
- SSH with password authentication enabled
- No firewall restrictions
- Minimal security setup
- **Use for**: Development and testing

### Minimal (Essential Security)
- SSH key-only authentication
- Basic UFW firewall (SSH, HTTP, HTTPS)
- fail2ban for SSH protection
- **Use for**: Staging and light production

### Full (Production Ready)
- Comprehensive SSH hardening
- Advanced firewall rules with rate limiting
- Process and resource limits
- Security monitoring
- **Use for**: Production deployments

```bash
# Specify hardening level during initialization
clwd init --name secure-project --hardening full
```

## Commands Reference

### Core Commands

```bash
# Project Management
clwd init --name PROJECT --size SIZE [--hardening LEVEL]
clwd status --name PROJECT
clwd destroy --name PROJECT

# Remote Access
clwd open --name PROJECT          # Interactive SSH session
clwd exec --name PROJECT "cmd"    # Execute single command
clwd logs --name PROJECT          # View setup logs

# Configuration
clwd config list                  # List all projects
clwd config show --name PROJECT  # Show project details
```

### Advanced Usage

```bash
# Custom instance configuration
clwd init --name myproject \
  --size large \
  --hardening minimal \
  --region nbg1 \
  --image ubuntu-24.04

# Premium service (when available)
clwd init --name myproject --premium

# Background execution with timeout
clwd exec --name myproject --timeout 300 "long-running-command"
```

## Architecture

Clwd follows a modular provider pattern:

- **Provider Interface**: Abstract base class for cloud providers
- **Hetzner Provider**: Implementation for Hetzner Cloud
- **Config Management**: JSON-based project state persistence
- **SSH Operations**: Direct subprocess calls for reliable remote access
- **Security Hardening**: Configurable cloud-init scripts

## Development

### Local Development Setup

```bash
# Clone repository
git clone https://github.com/clwd-ai/clwd.git
cd clwd

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Code formatting and linting
ruff format .
ruff check .
mypy src/
```

### Testing

```bash
# Run full test suite
pytest --cov=clwd

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/providers/
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## Premium Service

Clwd offers a premium service with **fast snapshot-based provisioning** (30-45 seconds vs 2-3 minutes) and additional features:

- ⚡ **Ultra-fast provisioning** from pre-built snapshots
- 🎯 **Priority support** and SLA guarantees
- 📊 **Advanced monitoring** and analytics
- 👥 **Team collaboration** features
- 🔧 **Managed infrastructure** - no API tokens needed

[Learn more about Premium →](https://clwd.ai/premium) *(Coming Soon)*

## Troubleshooting

### Common Issues

**"SSH connection failed"**
- Verify your SSH key is in a standard location
- Check cloud provider firewall settings
- Wait 30-60 seconds after instance creation

**"Claude authentication failed"**  
- Run `claude auth login` locally first
- Ensure keychain access on macOS
- Check that `~/.claude.json` exists

**"Provider API error"**
- Verify API token is set correctly
- Check API token permissions
- Confirm sufficient account quota

### Debug Mode

```bash
# Enable verbose logging
export CLWD_DEBUG=1
clwd init --name debug-project

# Check setup logs
clwd logs --name debug-project
```

## Security

- **Secrets**: Never logs or stores API tokens or authentication data
- **SSH Keys**: Uses your existing SSH keys, never generates or stores new ones  
- **Credentials**: Transfers Claude authentication securely during provisioning only
- **Hardening**: Multiple security levels with comprehensive protection options

Report security issues to: security@clwd.ai

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- 📚 **Documentation**: [GitHub Wiki](https://github.com/clwd-ai/clwd/wiki)
- 🐛 **Issues**: [GitHub Issues](https://github.com/clwd-ai/clwd/issues)  
- 💬 **Discussions**: [GitHub Discussions](https://github.com/clwd-ai/clwd/discussions)
- 📧 **Email**: team@clwd.ai

---

**Made with ❤️ for the Claude Code community**
