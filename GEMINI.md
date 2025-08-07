
## Project Overview

This project, named "Clwd," is a Python-based command-line interface (CLI) tool designed to streamline the deployment and management of Claude Code on remote cloud instances. It provides a "Netlify-like" experience for Claude, enabling developers to quickly set up a development environment in the cloud with a single command.

The core functionality of Clwd includes:
- **Automated Provisioning:** Creates a virtual private server (VPS) on Hetzner Cloud, with plans to support other providers like DigitalOcean and AWS.
- **Claude Code Installation:** Automatically installs and configures Claude Code on the provisioned server.
- **Credential Management:** Securely extracts Claude credentials from the user's local macOS Keychain and injects them into the remote environment.
- **Live Previews:** Sets up a web server (Nginx) with a diagnostic landing page, providing a live preview URL for the deployed application.
- **Remote Execution:** Allows users to execute Claude commands remotely on the cloud instance.
- **Security Hardening:** Offers optional security configurations, including setting up a UFW firewall, hardening SSH, and installing Fail2ban.

The project is structured as a Python package with a clear separation of concerns:
- `clwd/cli`: Contains the main CLI logic using the `click` library.
- `clwd/providers`: Implements the cloud provider interactions, with `hetzner.py` as the current provider.
- `clwd/utils`: Provides utility functions for configuration management, SSH communication, and Keychain access.

## Building and Running

### Dependencies

The project's dependencies are listed in `requirements.txt` and managed by `setup.py`. The main dependencies are:
- `click`: For creating the CLI.
- `requests`: For making API calls to the cloud provider.
- `paramiko`: For SSH communication with the remote instances.
- `rich`: For enhancing the CLI output with rich text and formatting.

### Installation

To install the project and its dependencies, run the following command in the project's root directory:

```bash
pip install -e .
```

This will install the package in editable mode, making the `clwd` command available in the shell.

### Running the Application

The main entry point for the application is the `clwd` command. Here are some common commands:

- **Initialize a new project:**
  ```bash
  clwd init --name my-app
  ```

- **Execute a command remotely:**
  ```bash
  clwd exec --name my-app "create a React app"
  ```

- **SSH into the instance:**
  ```bash
  clwd ssh --name my-app
  ```

- **Destroy a project:**
  ```bash
  clwd destroy --name my-app
  ```

### Configuration

The application requires a Hetzner API token to be set as an environment variable:

```bash
export HETZNER_API_TOKEN="your-token"
```

Project configurations are stored in `~/.clwd/projects.json`.

## Development Conventions

### Code Style

The code follows standard Python conventions (PEP 8). It uses type hints for better code clarity and maintainability. The `rich` library is used for user-facing output to provide a modern and user-friendly CLI experience.

### Architecture

The application is designed with a modular architecture, making it easy to extend. The `Provider` class in `clwd/providers/__init__.py` defines an interface for cloud providers, allowing for new providers to be added by implementing this interface.

The `SSHClient` class in `clwd/utils/ssh.py` abstracts the SSH communication, a simple way to execute commands on remote instances.

### Error Handling

The application includes error handling for common issues such as missing credentials, failed API requests, and SSH connection problems. The `rich` library is used to display user-friendly error messages.

### Testing

There are no explicit tests in the provided code. A good next step would be to add a test suite using a framework like `pytest` to ensure the reliability of the application.
