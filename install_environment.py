#!/usr/bin/env python3
"""
ArPI Installation and Management Tool
A comprehensive Python-based replacement for bash installation scripts

Based on the original ArPI bash modules:
- System packages (zsh, oh-my-zsh, development tools)
- Hardware setup (RTC, GSM, WiringPi)  
- Database (PostgreSQL installation and configuration)
- NGINX (compilation from source with SSL)
- MQTT (Mosquitto broker with authentication)
- Certbot (SSL certificate management)
- Service setup (systemd services, secrets management)
"""

from time import sleep
import click
import subprocess
import logging
import os
import platform
import tempfile
import secrets
import string
from datetime import datetime
from abc import ABC, abstractmethod

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s: %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# General Helper Functions
# =============================================================================

class AptLockError(Exception):
    """Custom exception for apt lock errors"""
    pass

class SystemHelper:
    """Helper class for general system operations"""
    
    @staticmethod
    def run_command(
        command: str,
        input: str = "",
        check: bool = True,
        capture: bool = False,
        cwd: str = None,
        suppress_output: bool = True
    ) -> subprocess.CompletedProcess:
        """Run shell command with proper error handling"""

        if capture and input:
            raise ValueError("Cannot use 'input' with 'capture=True'")

        result: subprocess.CompletedProcess = None
        try:
            if not suppress_output:
                click.echo(f"   ⚡Starting command at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                click.echo(f"    > Running: {command}")

            collected_output = []
            def print_lines(output):
                for line in output or []:
                    line = "    |\t" + line.rstrip()
                    click.echo(line)
                    collected_output.append(line)

            if capture:
                result = subprocess.run(
                    command, 
                    shell=True, 
                    check=check,
                    capture_output=True,
                    text=True,
                    cwd=cwd
                )
                if result.stdout and not suppress_output:
                    print_lines(result.stdout.splitlines())
            else:
                # Stream output line by line, indenting each line
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE if input else None,
                    text=True,
                    cwd=cwd
                )

                if input:
                    process.stdin.write(input)
                    process.stdin.flush()
                    process.stdin.close()

                print_lines(process.stdout)

                process.wait()
                result = subprocess.CompletedProcess(
                    args=command,
                    returncode=process.returncode,
                    stdout=collected_output
                )

                if check and process.returncode != 0:
                    raise subprocess.CalledProcessError(
                        process.returncode,
                        command,
                        output=process.stdout.readlines()
                )
            
            if not suppress_output:
                click.echo(f"   ⚡Finished command at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            return result
        except subprocess.CalledProcessError as e:
            if "apt-get" in command and e.returncode == 100:
                click.echo("    ⚠️ APT lock error encountered. Another process may be using apt.")
                raise AptLockError("APT lock error encountered. Another process may be using apt.") from e

            click.echo(f"    Command failed! Error: {e}")
            if suppress_output:
                click.echo("    ⚠️ Command failed!")
                if result and e.stdout:
                    for line in e.stdout:
                        click.echo(line)

            raise

    @staticmethod
    def is_service_running(service: str) -> bool:
        """Check if systemd service is running"""
        try:
            result = SystemHelper.run_command(f"systemctl is-active --quiet {service}", check=False)
            return result.returncode == 0
        except Exception:
            return False
    
    @staticmethod
    def is_service_enabled(service: str) -> bool:
        """Check if systemd service is enabled"""
        try:
            result = SystemHelper.run_command(f"systemctl is-enabled --quiet {service}", check=False)
            return result.returncode == 0
        except Exception:
            return False
    
    @staticmethod
    def get_architecture() -> str:
        """Get system architecture"""
        return platform.machine()
    
    @staticmethod
    def file_contains_text(file_path: str, text: str) -> bool:
        """Check if file contains specific text"""
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                return text in content
        except Exception:
            return False
    
    @staticmethod
    def append_to_file(file_path: str, text: str):
        """Append text to file"""
        with open(file_path, 'a') as f:
            f.write(text)
    
    @staticmethod
    def write_file(file_path: str, content: str):
        """Write content to file"""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            f.write(content)

class SecurityHelper:
    """Helper class for security-related operations"""
    
    @staticmethod
    def generate_password(length: int = 24) -> str:
        """Generate a secure random password"""
        alphabet = string.ascii_letters + string.digits + "!#*+"
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    def set_file_permissions(file_path: str, owner: str, mode: str, recursive: bool = False):
        """Set file ownership and permissions"""
        recursive_flag = "-R" if recursive else ""
        SystemHelper.run_command(f"chown {recursive_flag} {owner} {file_path}")
        SystemHelper.run_command(f"chmod {recursive_flag} {mode} {file_path}")

class PackageHelper:
    """Helper class for package management operations"""
    MAX_RETRIES = 5
    RETRY_DELAY = 10
    
    @staticmethod
    def update_package_cache():
        """Update package cache"""
        attempts = 0
        error = None
        while attempts < PackageHelper.MAX_RETRIES:
            try:
                SystemHelper.run_command("apt-get update", suppress_output=False)
                return
            except AptLockError as e:
                attempts += 1
                error = e
                sleep(PackageHelper.RETRY_DELAY)

        raise error

    @staticmethod
    def upgrade_system():
        """Upgrade system packages"""
        attempts = 0
        error = None
        while attempts < PackageHelper.MAX_RETRIES:
            try:
                SystemHelper.run_command("apt-get -y upgrade", suppress_output=False)
                SystemHelper.run_command("apt-get -y autoremove", suppress_output=False)
                return
            except AptLockError as e:
                attempts += 1
                error = e

        raise error
    
    @staticmethod
    def is_package_installed(package: str) -> bool:
        """Check if package is installed"""
        try:
            result = SystemHelper.run_command(f"dpkg -l | grep '^ii  {package} '", 
                                    check=False, capture=True)
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def install_packages(packages: list, description: str = None):
        """Install multiple packages if not already installed"""
        missing_packages = []
        for package in packages:
            if not PackageHelper.is_package_installed(package):
                missing_packages.append(package)
        
        if missing_packages:
            packages_str = " ".join(missing_packages)
            click.echo(f"   ⚡Starting installation at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            if description:
                click.echo(f"    > Installing {description}...")
            else:
                click.echo(f"    > Installing packages: {packages_str}...")
            
            attempts = 0
            error = None
            while attempts < PackageHelper.MAX_RETRIES:
                try:
                    SystemHelper.run_command(f"apt-get -y install {packages_str}", suppress_output=False)
                    return True
                except AptLockError as e:
                    attempts += 1
                    error = e

            raise error
        else:
            if description:
                click.echo(f"   ✓ {description} already installed")
            return False

class ServiceHelper:
    """Helper class for systemd service operations"""
    
    @staticmethod
    def start_service(service: str):
        """Start systemd service"""
        SystemHelper.run_command(f"systemctl start {service}")
    
    @staticmethod
    def enable_service(service: str):
        """Enable systemd service"""
        SystemHelper.run_command(f"systemctl enable {service}")
    
    @staticmethod
    def restart_service(service: str):
        """Restart systemd service"""
        SystemHelper.run_command(f"systemctl restart {service}")
    
    @staticmethod
    def stop_service(service: str, ignore_errors: bool = True):
        """Stop systemd service"""
        try:
            SystemHelper.run_command(f"systemctl stop {service}", check=not ignore_errors)
        except Exception:
            if not ignore_errors:
                raise
    
    @staticmethod
    def disable_service(service: str, ignore_errors: bool = True):
        """Disable systemd service"""
        try:
            SystemHelper.run_command(f"systemctl disable {service}", check=not ignore_errors)
        except Exception:
            if not ignore_errors:
                raise

# =============================================================================
# Base Installer Class
# =============================================================================

class BaseInstaller(ABC):
    """Base class for all component installers"""

    def __init__(self, config: dict):
        self.config = config
        self.warnings = []
    
    @abstractmethod
    def install(self):
        """Install the component"""
        pass
    
    @abstractmethod
    def is_installed(self) -> bool:
        """Check if component is installed"""
        pass
    
    @abstractmethod
    def get_status(self) -> dict:
        """Get component status information"""
        pass

# =============================================================================
# Component Installer Classes
# =============================================================================

class SystemInstaller(BaseInstaller):
    """Installer for system packages and shell configuration"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.user = config.get("user", "argus")
    
    def is_zsh_configured(self) -> bool:
        """Check if zsh is configured with oh-my-zsh and ArPI environment"""
        home = f"/home/{self.user}"
        oh_my_zsh_dir = os.path.join(home, ".oh-my-zsh")
        zshrc_file = os.path.join(home, ".zshrc")
        
        return (
            os.path.exists(oh_my_zsh_dir) and
            SystemHelper.run_command(f"getent passwd {self.user}", capture=True).stdout.strip().endswith("/bin/zsh") and
            SystemHelper.file_contains_text(zshrc_file, "source ~/.venvs/server/bin/activate")
        )

    def install_system_packages(self):
        """Install and configure system packages"""
        click.echo("   🔧 Installing system packages...")
        
        PackageHelper.update_package_cache()
        PackageHelper.upgrade_system()
        
        essential_packages = [
            "zsh", "curl", "git", "vim", "minicom", "net-tools", "telnet", "dnsutils",
        ]
        
        PackageHelper.install_packages(essential_packages, "essential packages")
    
    def install_oh_my_zsh(self):
        """Install oh-my-zsh"""
        click.echo("   🐚 Installing oh-my-zsh...")
        
        home = f"/home/{self.user}"
        oh_my_zsh_dir = os.path.join(home, ".oh-my-zsh")
        
        if not os.path.exists(oh_my_zsh_dir):
            # Install oh-my-zsh
            try:
                install_script = f"su - {self.user} -c \"$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh) --unattended\""
                SystemHelper.run_command(install_script)
            except subprocess.CalledProcessError as error:
                if error.returncode == 1:
                    # suppress error code 1
                    # the install fails with code 1 but oh-my-zsh is installed correctly
                    click.echo("   ✓ oh-my-zsh installed")
                else:
                    click.echo("   ✗ oh-my-zsh installation failed")
                    raise
        else:
            click.echo("   ✓ oh-my-zsh already cloned")

        # is zsh shell selected for argus user
        if not SystemHelper.run_command(f"getent passwd {self.user}", capture=True).stdout.strip().endswith("/bin/zsh"):
            # Change shell for argus user
            SystemHelper.run_command(f"chsh -s /bin/zsh {self.user}")
            click.echo("   ✓ Shell changed to zsh for argus user")
        else:
            click.echo("   ✓ zsh is already the default shell for argus user")
    
    def configure_zsh_environment(self):
        """Configure zsh environment for ArPI"""
        click.echo("   ⚙️ Configuring zsh environment...")
        
        if not self.is_zsh_configured():
            home = f"/home/{self.user}"
            zshrc_file = os.path.join(home, ".zshrc")
            
            config_addition = """

# active python virtual environment and load env variables
source ~/.venvs/server/bin/activate
set -a
. ~/server/.env
. ~/server/secrets.env
set +a
"""
            
            SystemHelper.append_to_file(zshrc_file, config_addition)
            click.echo("   ✓ Zsh environment configured")
        else:
            click.echo("   ✓ Zsh environment already configured")
    
    def install_common_tools(self):
        """Install common development tools"""
        click.echo("   🛠️ Installing common development tools...")
        
        tools_packages = [
            "python3", "python3-cryptography", "python3-dev",
            "python3-gpiozero", "python3-gi", "python3-setuptools", "cmake",
            "gcc", "libgirepository1.0-dev", "libcairo2-dev", "pkg-config",
            "gir1.2-gtk-3.0", "fail2ban", "python3-pip", "pipenv"
        ]
        
        if PackageHelper.install_packages(tools_packages, "common development tools"):
            # Remove pip configuration to avoid hash mismatch
            if os.path.exists("/etc/pip.conf"):
                os.remove("/etc/pip.conf")
    
    def install(self):
        """Install system components"""
        self.install_system_packages()
        self.install_oh_my_zsh()
        self.configure_zsh_environment()
        self.install_common_tools()
    
    def is_installed(self) -> bool:
        """Check if system components are installed"""
        return (PackageHelper.is_package_installed("zsh") and 
                self.is_zsh_configured())
    
    def get_status(self) -> dict:
        """Get system component status"""
        return {
            "zsh_installed": PackageHelper.is_package_installed("zsh"),
            "zsh_configured": self.is_zsh_configured(),
            "python3_installed": PackageHelper.is_package_installed("python3")
        }

class HardwareInstaller(BaseInstaller):
    """Installer for hardware components (RTC, GSM, WiringPi)"""
    
    def install_rtc_hardware(self):
        """Install and configure RTC (DS1307) hardware"""
        click.echo("   🕐 Setting up RTC hardware...")
        
        # Install i2c-tools
        PackageHelper.install_packages(["i2c-tools"])
        
        # Configure RTC device
        try:
            SystemHelper.run_command("echo ds1307 0x68 > /sys/class/i2c-adapter/i2c-1/new_device")
            click.echo("   ✓ RTC device configured")
        except Exception as e:
            click.echo(f"    ⚠️ WARNING: Could not configure RTC device: {e}")
            self.warnings.append(f"Could not configure RTC device: {e}")
        
        # Configure device tree overlay
        config_txt = "/boot/firmware/config.txt"
        if os.path.exists(config_txt) and not SystemHelper.file_contains_text(config_txt, "dtoverlay=i2c-rtc,ds1307"):
            SystemHelper.append_to_file(config_txt, "\ndtoverlay=i2c-rtc,ds1307\n")
            click.echo("   ✓ RTC overlay configured")
        
        # Configure kernel module
        modules_file = "/etc/modules"
        if os.path.exists(modules_file) and not SystemHelper.file_contains_text(modules_file, "rtc-ds1307"):
            SystemHelper.append_to_file(modules_file, "rtc-ds1307\n")
            click.echo("   ✓ RTC module configured")
        
        # Copy RTC cron job (matching bash script)
        if os.path.exists("/tmp/server/etc/cron/hwclock"):
            SystemHelper.run_command("cp /tmp/server/etc/cron/hwclock /etc/cron.d/")
            SystemHelper.run_command("chmod 644 /etc/cron.d/hwclock")
            click.echo("   ✓ RTC cron job configured")
        else:
            click.echo("   ⚠️ RTC cron job file not found at /tmp/server/etc/cron/hwclock")

    def install_gsm_hardware(self):
        """Install and configure GSM module"""
        click.echo("   📱 Setting up GSM hardware...")
        
        # Disable serial getty services
        services = ["serial-getty@ttyAMA0.service", "serial-getty@ttyS0.service"]
        for service in services:
            ServiceHelper.stop_service(service)
            ServiceHelper.disable_service(service)
        
        # Configure boot command line
        cmdline_file = "/boot/cmdline.txt"
        if os.path.exists(cmdline_file) and SystemHelper.file_contains_text(cmdline_file, "console=serial0,115200"):
            with open(cmdline_file, "r") as f:
                content = f.read()
            content = content.replace("console=serial0,115200 ", "")
            SystemHelper.write_file(cmdline_file, content)
            click.echo("   ✓ Console removed from boot command line")
        
        # Configure UART and Bluetooth settings
        config_txt = "/boot/firmware/config.txt"
        if os.path.exists(config_txt):
            additions = []
            if not SystemHelper.file_contains_text(config_txt, "enable_uart=1"):
                additions.extend(["\n# Enable UART", "enable_uart=1", "dtoverlay=uart0"])
            
            if not SystemHelper.file_contains_text(config_txt, "dtoverlay=disable-bt"):
                additions.extend(["dtoverlay=disable-bt", "dtoverlay=miniuart-bt"])
            
            if additions:
                SystemHelper.append_to_file(config_txt, "\n".join(additions) + "\n")
                click.echo("   ✓ UART and Bluetooth configured")
        
        # Disable hciuart service
        ServiceHelper.stop_service("hciuart")
        ServiceHelper.disable_service("hciuart")
    
    def install_wiringpi(self):
        """Install WiringPi library"""
        click.echo("   🔌 Installing WiringPi...")
        
        # Check if WiringPi is already installed
        try:
            result = SystemHelper.run_command("gpio -v", check=False, capture=True)
            if result.returncode != 0:
                click.echo("   ✓ WiringPi already installed")
                return
        except Exception:
            pass
        
        # Clone and build WiringPi
        with tempfile.TemporaryDirectory() as temp_dir:
            wiringpi_dir = os.path.join(temp_dir, "wiringpi")
            
            try:
                SystemHelper.run_command(f"git clone https://github.com/WiringPi/WiringPi.git {wiringpi_dir}")
                SystemHelper.run_command("./build", cwd=wiringpi_dir)
                SystemHelper.run_command("ldconfig")
                click.echo("   ✓ WiringPi installed successfully")
            except Exception as e:
                click.echo(f"    ⚠️ WARNING: WiringPi installation failed: {e}")
                self.warnings.append(f"WiringPi installation failed: {e}")
    
    def install(self):
        """Install hardware components"""
        self.install_rtc_hardware()
        self.install_gsm_hardware()
        self.install_wiringpi()
    
    def is_installed(self) -> bool:
        """Check if hardware components are installed"""
        return PackageHelper.is_package_installed("i2c-tools")
    
    def get_status(self) -> dict:
        """Get hardware component status"""
        return {
            "i2c_tools_installed": PackageHelper.is_package_installed("i2c-tools"),
            "rtc_configured": os.path.exists("/sys/class/i2c-adapter/i2c-1/1-0068"),
            "wiringpi_available": os.system("gpio -v > /dev/null 2>&1") == 0
        }

class DatabaseInstaller(BaseInstaller):
    """Installer for PostgreSQL database"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.postgresql_version = config.get("postgresql_version", "15")
        self.db_username = config.get("db_username", "argus")
        self.db_name = config.get("db_name", "argus")
        self.db_password = config.get("db_password", "")

        # try to read existing password from secrets.env
        secrets_file = os.path.join(config.get("server_dir", "/home/argus/server"), "secrets.env")
        if os.path.exists(secrets_file):
            with open(secrets_file, "r") as f:
                for line in f:
                    if line.startswith("DB_PASSWORD="):
                        self.db_password = line.strip().split("=", 1)[1].strip("\"")
                        break
    
    def install_postgresql(self):
        """Install PostgreSQL database"""
        click.echo("   🗄️ Installing PostgreSQL...")
        
        pg_packages = [
            f"postgresql-{self.postgresql_version}",
            f"postgresql-client-{self.postgresql_version}", 
            f"postgresql-contrib-{self.postgresql_version}",
            "libpq-dev"
        ]
        
        if PackageHelper.install_packages(pg_packages, f"PostgreSQL {self.postgresql_version}"):
            ServiceHelper.start_service("postgresql")
            ServiceHelper.enable_service("postgresql")
        
        # Ensure service is running
        if not SystemHelper.is_service_running("postgresql"):
            ServiceHelper.start_service("postgresql")
    
    def configure_database(self):
        """Configure PostgreSQL database for ArPI"""
        click.echo("   ⚙️ Configuring database...")
        
        # Generate database password if not set
        if not self.db_password:
            self.db_password = SecurityHelper.generate_password()
            click.echo("   ✓ Generated database password")
        
        # Create database user
        try:
            # Check if user exists
            result = SystemHelper.run_command(
                f"su - postgres -c \"psql -tAc \\\"SELECT 1 FROM pg_roles WHERE rolname='{self.db_username}'\\\"\"",
                capture=True,
                check=False,
                suppress_output=False
            )
            
            if "1" not in result.stdout:
                # Create user
                SystemHelper.run_command(
                    f"su - postgres -c \"createuser --createdb --login --no-password {self.db_username}\"",
                    suppress_output=False
                )
                click.echo(f"   ✓ Created database user: {self.db_username}")
            else:
                click.echo(f"   ✓ Database user {self.db_username} already exists")

            SystemHelper.run_command(
                f"su - postgres -c \"psql -c \\\"ALTER USER {self.db_username} WITH PASSWORD '{self.db_password}';\\\"\"",
                suppress_output=False
            )
            click.echo(f"   ✓ Updated password for user: {self.db_username}")
        except Exception as e:
            click.echo(f"    ⚠️ WARNING: User creation may have failed: {e}")
            self.warnings.append(f"User creation may have failed: {e}")
        
        # Create database
        try:
            result = SystemHelper.run_command(
                f"sudo -u argus psql -lqt | cut -d \\| -f 1 | grep -qw {self.db_name}",
                check=False
            )
            
            if result.returncode != 0:
                SystemHelper.run_command(f"sudo -u postgres createdb -O {self.db_username} {self.db_name}")
                click.echo(f"   ✓ Created database: {self.db_name}")
            else:
                click.echo(f"   ✓ Database {self.db_name} already exists")
        except Exception as e:
            click.echo(f"    ⚠️ WARNING: Database creation may have failed: {e}")
            self.warnings.append(f"Database creation may have failed: {e}")

    def install(self):
        """Install database components"""
        self.install_postgresql()
        self.configure_database()
    
    def is_installed(self) -> bool:
        """Check if database is installed"""
        return (PackageHelper.is_package_installed(f"postgresql-{self.postgresql_version}") and
                SystemHelper.is_service_running("postgresql"))
    
    def get_status(self) -> dict:
        """Get database status"""
        return {
            "postgresql_installed": PackageHelper.is_package_installed(f"postgresql-{self.postgresql_version}"),
            "postgresql_running": SystemHelper.is_service_running("postgresql"),
            "postgresql_enabled": SystemHelper.is_service_enabled("postgresql")
        }

class NginxInstaller(BaseInstaller):
    """Installer for NGINX web server"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.nginx_version = config.get("nginx_version", "1.24.0")
        self.dhparam_file = config.get("dhparam_file", "")
    
    def install_nginx_dependencies(self):
        """Install NGINX build dependencies"""
        click.echo("   📦 Installing NGINX build dependencies...")
        build_deps = ["build-essential", "libpcre3-dev", "libssl-dev", "zlib1g-dev"]
        PackageHelper.install_packages(build_deps, "NGINX build dependencies")
    
    def compile_nginx_from_source(self):
        """Compile and install NGINX from source"""
        click.echo(f"   🔨 Compiling NGINX {self.nginx_version} from source...")
        
        # Check if already installed
        if os.path.exists("/usr/local/nginx/sbin/nginx"):
            click.echo("   ✓ NGINX already installed")
            return
        
        with tempfile.TemporaryDirectory() as temp_dir:
            nginx_archive = f"nginx-{self.nginx_version}.tar.gz"
            nginx_dir = f"nginx-{self.nginx_version}"
            
            # Download NGINX source
            SystemHelper.run_command(
                f"curl -s -O -J http://nginx.org/download/{nginx_archive}",
                cwd=temp_dir
            )
            
            # Extract and compile
            SystemHelper.run_command(f"tar xzf {nginx_archive}", cwd=temp_dir)
            
            nginx_source_dir = os.path.join(temp_dir, nginx_dir)
            
            # Configure build
            SystemHelper.run_command(
                "./configure --with-http_stub_status_module --with-http_ssl_module",
                cwd=nginx_source_dir
            )
            
            # Compile
            SystemHelper.run_command("make", cwd=nginx_source_dir)
            
            # Install
            SystemHelper.run_command("make install", cwd=nginx_source_dir, suppress_output=False)
            
            click.echo("   ✓ NGINX compiled and installed successfully")
    
    def configure_nginx_setup(self):
        """Configure NGINX setup matching bash script"""
        click.echo("   ⚙️ Configuring NGINX setup...")
        
        # Add user www-data to argus group
        try:
            result = SystemHelper.run_command("groups www-data", capture=True, check=False)
            if "argus" not in result.stdout:
                SystemHelper.run_command("adduser www-data argus")
                click.echo("   ✓ Added www-data to argus group")
        except Exception as e:
            click.echo(f"    ⚠️ WARNING: User configuration may have failed: {e}")
            self.warnings.append(f"User configuration may have failed: {e}")
        
        # Remove existing config and copy new one
        SystemHelper.run_command("rm -r /usr/local/nginx/conf/* | true")
        SystemHelper.run_command("cp -r /tmp/server/etc/nginx/* /usr/local/nginx/conf/")
        
        # Create modules-enabled directory and symlinks
        SystemHelper.run_command("mkdir -p /usr/local/nginx/conf/modules-enabled/")
        SystemHelper.run_command("ln -s /usr/local/nginx/conf/modules-available/* /usr/local/nginx/conf/modules-enabled/")

        # Create certificate symlink
        SystemHelper.run_command("ln -s /usr/local/nginx/conf/snippets/self-signed.conf /usr/local/nginx/conf/snippets/certificates.conf")

        # Create sites-enabled directory and symlinks
        SystemHelper.run_command("mkdir -p /usr/local/nginx/conf/sites-enabled/")
        SystemHelper.run_command("ln -s /usr/local/nginx/conf/sites-available/http.conf /usr/local/nginx/conf/sites-enabled/http.conf")
        SystemHelper.run_command("ln -s /usr/local/nginx/conf/sites-available/local.conf /usr/local/nginx/conf/sites-enabled/local.conf")

        # Copy dhparam file
        SystemHelper.run_command(f"cp {self.dhparam_file} /usr/local/nginx/conf/ssl/")
        click.echo("   ✓ Copied dhparam file")
        
        # Set proper ownership for SSL directory
        SecurityHelper.set_file_permissions("/usr/local/nginx/conf", "www-data:www-data", "755", recursive=True)
        
        click.echo("   ✓ NGINX configuration setup complete")
    
    def install(self):
        """Install NGINX components"""
        self.install_nginx_dependencies()
        self.compile_nginx_from_source()
        self.configure_nginx_setup()
    
    def is_installed(self) -> bool:
        """Check if NGINX is installed"""
        return os.path.exists("/usr/local/nginx/sbin/nginx")
    
    def get_status(self) -> dict:
        """Get NGINX status"""
        return {
            "nginx_installed": os.path.exists("/usr/local/nginx/sbin/nginx"),
            "nginx_configured": os.path.exists("/usr/local/nginx/conf/sites-enabled/http.conf"),
            "nginx_config_valid": SystemHelper.run_command("/usr/local/nginx/sbin/nginx -t", check=False).returncode == 0,
            "nginx_running": SystemHelper.is_service_running("nginx")
        }

class MqttInstaller(BaseInstaller):
    """Installer for MQTT broker"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.mqtt_password = config.get("mqtt_password", "")
        self.dhparam_file = config.get("dhparam_file", "")
    
    def setup_mosquitto_repository(self):
        """Setup Mosquitto repository for installation"""
        click.echo("   📡 Setting up Mosquitto repository...")
        
        # Check if repository is already configured
        sources_file = "/etc/apt/sources.list.d/mosquitto.list"
        if os.path.exists(sources_file):
            with open(sources_file, "r") as f:
                if "repo.mosquitto.org" in f.read():
                    click.echo("   ✓ Mosquitto repository already configured")
                    return
        
        # Download and add repository key
        with tempfile.TemporaryDirectory() as temp_dir:
            key_file = os.path.join(temp_dir, "mosquitto-repo.gpg")
            
            try:
                SystemHelper.run_command(f"wget -O {key_file} http://repo.mosquitto.org/debian/mosquitto-repo.gpg", cwd="/tmp")
                SystemHelper.run_command(f"apt-key add {key_file}")
            except Exception as e:
                click.echo(f"    ⚠️ WARNING: Could not add repository key: {e}")
                self.warnings.append(f"Could not add repository key: {e}")
        
        # Add repository to sources list
        SystemHelper.write_file(sources_file, "deb https://repo.mosquitto.org/debian bookworm main\n")
        
        click.echo("   ✓ Mosquitto repository configured")
    
    def install_mosquitto(self):
        """Install Mosquitto MQTT broker"""
        click.echo("   🦟 Installing Mosquitto MQTT broker...")
        
        # Setup repository first
        self.setup_mosquitto_repository()
        
        # Update package list
        PackageHelper.update_package_cache()
        
        # Install Mosquitto
        if PackageHelper.install_packages(["mosquitto"], "Mosquitto MQTT broker"):
            ServiceHelper.enable_service("mosquitto")
        
        # Ensure service is running
        if not SystemHelper.is_service_running("mosquitto"):
            ServiceHelper.start_service("mosquitto")
    
    def configure_mqtt_ssl_certificates(self):
        """Configure SSL certificates for MQTT"""
        click.echo("   🔐 Configuring MQTT SSL certificates...")
        
        # Create certs directory and copy certificates
        SystemHelper.run_command("mkdir -p /etc/mosquitto/certs")
        
        # Copy dhparam file
        SystemHelper.run_command(f"cp {self.dhparam_file} /etc/mosquitto/certs/")
        click.echo("   ✓ Copied dhparam file")
        
        # Copy SSL certificates from nginx config
        ssl_files = [
            "/tmp/server/etc/nginx/ssl/arpi_app.crt",
            "/tmp/server/etc/nginx/ssl/arpi_app.key", 
            "/tmp/server/etc/nginx/ssl/arpi_ca.crt"
        ]
        
        for ssl_file in ssl_files:
            SystemHelper.run_command(f"cp {ssl_file} /etc/mosquitto/certs/")
        
        # Set proper ownership for certs directory
        SecurityHelper.set_file_permissions("/etc/mosquitto/certs", "mosquitto:mosquitto", "755", recursive=True)
        
        click.echo("   ✓ MQTT SSL certificates configured")
    
    def configure_mqtt_configs(self):
        """Configure MQTT configuration files"""
        click.echo("   ⚙️ Configuring MQTT configuration files...")
        
        # Copy auth and logging configurations
        SystemHelper.run_command("cp /tmp/server/etc/mosquitto/auth.conf /etc/mosquitto/conf.d/")
        SystemHelper.run_command("cp /tmp/server/etc/mosquitto/logging.conf /etc/mosquitto/conf.d/")

        # Create configs-available directory and copy SSL configs
        SystemHelper.run_command("mkdir -p /etc/mosquitto/configs-available/")
        SystemHelper.run_command("cp /tmp/server/etc/mosquitto/ssl*.conf /etc/mosquitto/configs-available/")
        
        # Create symlink for SSL configuration
        SystemHelper.run_command("ln -sf /etc/mosquitto/configs-available/ssl-self-signed.conf /etc/mosquitto/conf.d/ssl.conf")
        
        click.echo("   ✓ MQTT configuration files setup complete")
    
    def configure_mqtt_authentication(self):
        """Configure MQTT authentication"""
        click.echo("   🔐 Configuring MQTT authentication...")
        
        # Generate MQTT password if not set
        if not self.mqtt_password:
            self.mqtt_password = SecurityHelper.generate_password()
            click.echo("   ✓ Generated MQTT password")
        
        # Create password file
        try:
            SystemHelper.run_command(f"mosquitto_passwd -b -c /etc/mosquitto/.passwd argus {self.mqtt_password}")
            SecurityHelper.set_file_permissions("/etc/mosquitto/.passwd", "mosquitto:mosquitto", "644")
            click.echo("   ✓ MQTT authentication configured")
        except Exception as e:
            click.echo(f"    ⚠️ WARNING: MQTT authentication setup failed: {e}")
            self.warnings.append(f"MQTT authentication setup failed: {e}")
    
    def install(self):
        """Install MQTT components"""
        self.install_mosquitto()
        self.configure_mqtt_ssl_certificates() 
        self.configure_mqtt_configs()
        self.configure_mqtt_authentication()
    
    def is_installed(self) -> bool:
        """Check if MQTT is installed"""
        return (PackageHelper.is_package_installed("mosquitto") and
                SystemHelper.is_service_running("mosquitto"))
    
    def get_status(self) -> dict:
        """Get MQTT status"""
        return {
            "mosquitto_installed": PackageHelper.is_package_installed("mosquitto"),
            "mosquitto_running": SystemHelper.is_service_running("mosquitto"),
            "mosquitto_enabled": SystemHelper.is_service_enabled("mosquitto")
        }

class CertbotInstaller(BaseInstaller):
    """Installer for SSL certificate management"""
    
    def should_use_snap_certbot(self) -> bool:
        """Determine if snap should be used for certbot installation"""
        return SystemHelper.get_architecture() == "x86_64"
    
    def install_certbot(self):
        """Install Certbot for SSL certificate management"""
        
        if self.should_use_snap_certbot():
            click.echo("   🔒 Installing Certbot from Snap...")
            # Install via snap for x86_64
            if PackageHelper.install_packages(["snapd"]):
                try:
                    SystemHelper.run_command("snap install core")
                    SystemHelper.run_command("snap refresh core")
                    SystemHelper.run_command("snap install certbot --classic")
                    SystemHelper.run_command("ln -sf /snap/bin/certbot /usr/bin/certbot")
                    click.echo("   ✓ Certbot installed via snap")
                except Exception as e:
                    click.echo(f"    ⚠️ WARNING: Snap installation failed, trying apt: {e}")
                    self.warnings.append(f"Snap installation failed: {e}")
        else:
            click.echo("   🔒 Installing Certbot via apt...")
            # Install via apt for ARM architectures
            PackageHelper.install_packages(["certbot"])
            click.echo("   ✓ Certbot installed via apt")
    
    def install(self):
        """Install Certbot components"""
        self.install_certbot()
    
    def is_installed(self) -> bool:
        """Check if Certbot is installed"""
        try:
            SystemHelper.run_command("certbot --version", capture=True)
            return True
        except Exception:
            return False
    
    def get_status(self) -> dict:
        """Get Certbot status"""
        return {
            "certbot_installed": self.is_installed()
        }

class ServiceInstaller(BaseInstaller):
    """Installer for ArPI services and configurations"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.user = config.get("user", "argus")
        self.db_password = config.get("db_password", "")
        self.salt = config.get("salt", "")
        self.secret = config.get("secret", "")
        self.mqtt_password = config.get("mqtt_password", "")
    
    def generate_service_secrets(self):
        """Generate secrets for ArPI services"""
        click.echo("   🔑 Generating service secrets...")
        
        secrets_generated = False
        
        if not self.db_password:
            self.db_password = SecurityHelper.generate_password()
            secrets_generated = True
        
        if not self.salt:
            self.salt = SecurityHelper.generate_password()
            secrets_generated = True
        
        if not self.secret:
            self.secret = SecurityHelper.generate_password()
            secrets_generated = True
        
        if not self.mqtt_password:
            self.mqtt_password = SecurityHelper.generate_password()
            secrets_generated = True
        
        if secrets_generated:
            click.echo("   ✓ Service secrets generated")
        else:
            click.echo("   ✓ Service secrets already exist")
    
    def create_service_directories(self):
        """Create ArPI service directories"""
        click.echo("   📁 Creating service directories...")
        
        # Create argus user if it doesn't exist
        try:
            SystemHelper.run_command(f"id {self.user}", capture=True)
            click.echo(f"   ✓ User '{self.user}' already exists")
        except subprocess.CalledProcessError:
            SystemHelper.run_command(f"useradd -m -s /bin/bash {self.user}")
            click.echo(f"   ✓ Created user '{self.user}'")
        
        # Create service directories
        directories = [
            f"/home/{self.user}/server",
            f"/home/{self.user}/webapplication", f"/run/{self.user}",
            f"/run/{self.user}",
        ]
        for directory in directories:
            SystemHelper.run_command(f"mkdir -p {directory}")

        SecurityHelper.set_file_permissions(f"/home/{self.user}", f"{self.user}:{self.user}", "755", recursive=True)
        SecurityHelper.set_file_permissions(f"/run/{self.user}", f"{self.user}:{self.user}", "755", recursive=True)

        # Create tmpfiles configuration
        tmpfiles_config = f"""# Type Path                     Mode    UID     GID     Age     Argument
d /run/{self.user} 0755 {self.user} {self.user}
"""
        SystemHelper.run_command("mkdir -p /usr/lib/tmpfiles.d")
        SystemHelper.write_file(f"/usr/lib/tmpfiles.d/{self.user}.conf", tmpfiles_config)
        
        click.echo("   ✓ Service directories created")
    
    def save_secrets_to_file(self):
        """Save generated secrets to file"""

        if os.path.exists(f"/home/{self.user}/server/secrets.env"):
            click.echo("   ✓ Secrets file already exists, skipping save")
            return

        click.echo("   💾 Saving secrets to file...")

        secrets_file = f"/home/{self.user}/server/secrets.env"
        SystemHelper.run_command(f"mkdir -p {os.path.dirname(secrets_file)}")

        secrets_content = f"""# Argus Service Secrets
# Generated on {datetime.now()}

SALT="{self.salt}"
SECRET="{self.secret}"
DB_PASSWORD="{self.db_password}"
ARGUS_MQTT_PASSWORD="{self.mqtt_password}"
"""

        SystemHelper.write_file(secrets_file, secrets_content)

        # Set proper ownership and permissions
        SystemHelper.run_command(f"chown {self.user}:{self.user} {secrets_file}")
        SecurityHelper.set_file_permissions(secrets_file, f"{self.user}:{self.user}", "600")

        click.echo("   ✓ Secrets saved to file")

    def setup_systemd_services(self):
        """Setup systemd services"""
        click.echo("   ⚙️ Setting up systemd services...")
        
        # Copy systemd service files
        SystemHelper.run_command("cp -r /tmp/server/etc/systemd/* /etc/systemd/system/")
        
        # Reload systemd daemon
        SystemHelper.run_command("systemctl daemon-reload")
        
        # Enable services
        services_to_enable = ["argus_server", "argus_monitor", "nginx"]
        for service in services_to_enable:
            ServiceHelper.enable_service(service)
            click.echo(f"   ✓ Enabled {service} service")
        
        click.echo("   ✓ Systemd services configured")
    
    def create_python_virtual_environment(self):
        """Create Python virtual environment"""
        click.echo("   🐍 Creating Python virtual environment...")
        
        venv_path = f"/home/{self.user}/.venvs"
        
        if not os.path.exists(venv_path):
            SystemHelper.run_command(f"mkdir -p {venv_path}")
            SecurityHelper.set_file_permissions(venv_path, f"{self.user}:{self.user}", "755")
            click.echo("   ✓ Python virtual environment created")
        else:
            click.echo("   ✓ Python virtual environment already exists")
    
    def install(self):
        """Install service components"""
        self.generate_service_secrets()
        self.create_service_directories()
        self.create_python_virtual_environment()
        self.save_secrets_to_file()
        self.setup_systemd_services()
    
    def is_installed(self) -> bool:
        """Check if services are installed"""
        return os.path.exists(f"/home/{self.user}/server/secrets.env")
    
    def get_status(self) -> dict:
        """Get service status"""
        return {
            "user_exists": os.path.exists(f"/home/{self.user}"),
            "secrets_file_exists": os.path.exists(f"/home/{self.user}/server/secrets.env"),
            "env_file_exists": os.path.exists(f"/home/{self.user}/server/.env"),
            "venv_exists": os.path.exists(f"/home/{self.user}/.venvs/server"),
            "service_directories_exist": os.path.exists(f"/run/{self.user}"),
            "argus_server_enabled": SystemHelper.is_service_enabled("argus_server"),
            "argus_monitor_enabled": SystemHelper.is_service_enabled("argus_monitor"),
            "nginx_enabled": SystemHelper.is_service_enabled("nginx")
        }

# =============================================================================
# Main Orchestrator Class
# =============================================================================

class ArpiOrchestrator:
    """Main orchestrator for ArPI installation components"""
    
    def __init__(self):
        self.config = {
            "postgresql_version": os.getenv("POSTGRESQL_VERSION", "15"),
            "nginx_version": os.getenv("NGINX_VERSION", "1.24.0"),
            "db_username": os.getenv("ARGUS_DB_USERNAME", "argus"),
            "db_name": os.getenv("ARGUS_DB_NAME", "argus"),
            "dhparam_file": os.getenv("DHPARAM_FILE", ""),
            "db_password": os.getenv("ARGUS_DB_PASSWORD", ""),
            "salt": os.getenv("SALT", ""),
            "secret": os.getenv("SECRET", ""),
            "mqtt_password": os.getenv("ARGUS_MQTT_PASSWORD", ""),
            "user": os.getenv("ARGUS_USER", "argus")
        }

        click.echo("Installation Configuration:")
        for key, value in self.config.items():
            display_value = value if "password" not in key.lower() and "secret" not in key.lower() else "****"
            click.echo(f"   {key}: {display_value}") 
        
        # Initialize component installers
        self.system_installer = SystemInstaller(self.config)
        self.hardware_installer = HardwareInstaller(self.config)
        self.database_installer = DatabaseInstaller(self.config)
        self.nginx_installer = NginxInstaller(self.config)
        self.mqtt_installer = MqttInstaller(self.config)
        self.certbot_installer = CertbotInstaller(self.config)
        self.service_installer = ServiceInstaller(self.config)
    
    def get_installer(self, component: str) -> BaseInstaller:
        """Get installer for specific component"""
        installers = {
            "system": self.system_installer,
            "hardware": self.hardware_installer,
            "database": self.database_installer,
            "nginx": self.nginx_installer,
            "mqtt": self.mqtt_installer,
            "certbot": self.certbot_installer,
            "services": self.service_installer
        }
        return installers.get(component)
    
    def get_all_status(self) -> dict:
        """Get status of all components"""
        return {
            "system": self.system_installer.get_status(),
            "hardware": self.hardware_installer.get_status(),
            "database": self.database_installer.get_status(),
            "nginx": self.nginx_installer.get_status(),
            "mqtt": self.mqtt_installer.get_status(),
            "certbot": self.certbot_installer.get_status(),
            "services": self.service_installer.get_status()
        }
    
    def get_warnings(self) -> list:
        """Get all warnings from installers"""
        warnings = []
        for installer in [self.system_installer, self.hardware_installer, self.database_installer,
                          self.nginx_installer, self.mqtt_installer, self.certbot_installer,
                          self.service_installer]:
            warnings.extend(installer.warnings)
        return warnings

@click.group()
@click.pass_context
def cli(ctx):
    """ArPI Installation and Management Tool"""
    ctx.ensure_object(dict)
    ctx.obj['orchestrator'] = ArpiOrchestrator()

@cli.command()
@click.pass_context
def install_system(ctx):
    """Install and configure system packages"""
    orchestrator: ArpiOrchestrator = ctx.obj['orchestrator']
    
    click.echo("🔧 Installing system...")
    orchestrator.system_installer.install()
    click.echo("✅ System installation complete")

@cli.command()
@click.pass_context
def install_hardware(ctx):
    """Install and configure hardware components (RTC, GSM, WiringPi)"""
    orchestrator: ArpiOrchestrator = ctx.obj['orchestrator']
    
    click.echo("🔧 Installing hardware components...")
    orchestrator.hardware_installer.install()
    click.echo("✅ Hardware installation complete")

@cli.command()
@click.pass_context
def install_database(ctx):
    """Install and configure PostgreSQL database"""
    orchestrator: ArpiOrchestrator = ctx.obj['orchestrator']
    
    click.echo("🗄️ Installing database...")
    orchestrator.database_installer.install()
    click.echo("✅ Database installation complete")

@cli.command()
@click.pass_context
def install_nginx(ctx):
    """Install and configure NGINX web server"""
    orchestrator: ArpiOrchestrator = ctx.obj['orchestrator']
    
    click.echo("🌐 Installing NGINX...")
    orchestrator.nginx_installer.install()
    click.echo("✅ NGINX installation complete")

@cli.command()
@click.pass_context
def install_mqtt(ctx):
    """Install and configure MQTT broker"""
    orchestrator: ArpiOrchestrator = ctx.obj['orchestrator']
    
    click.echo("📡 Installing MQTT broker...")
    orchestrator.mqtt_installer.install()
    click.echo("✅ MQTT installation complete")

@cli.command()
@click.pass_context
def install_certbot(ctx):
    """Install Certbot for SSL certificate management"""
    orchestrator: ArpiOrchestrator = ctx.obj['orchestrator']
    
    click.echo("🔒 Installing Certbot...")
    orchestrator.certbot_installer.install()
    click.echo("✅ Certbot installation complete")

@cli.command()
@click.pass_context
def setup_services(ctx):
    """Setup ArPI services and configurations"""
    orchestrator: ArpiOrchestrator = ctx.obj['orchestrator']
    
    click.echo("⚙️ Setting up ArPI services...")
    orchestrator.service_installer.install()
    click.echo("✅ ArPI services setup complete")

@cli.command()
@click.pass_context
def full_install(ctx):
    """Run complete ArPI installation"""
    click.echo("🚀 Starting full ArPI installation...")

    current_user_process = SystemHelper.run_command("whoami", capture=True)
    click.echo(f"👤 Executing with user: {current_user_process.stdout}")
    ctx.invoke(install_system)
    ctx.invoke(install_hardware)
    ctx.invoke(install_database)
    ctx.invoke(install_nginx)
    ctx.invoke(install_mqtt)
    ctx.invoke(install_certbot)
    ctx.invoke(setup_services)

    warnings = ctx.obj['orchestrator'].get_warnings()
    if warnings:
        click.echo("\n⚠️ Installation completed with warnings:")
        for warning in warnings:
            click.echo(f"   - {warning}")
    
    click.echo("🎉 Full ArPI installation complete!")

@cli.command()
@click.pass_context
def status(ctx):
    """Check status of ArPI components"""
    orchestrator: ArpiOrchestrator = ctx.obj['orchestrator']
    
    click.echo("📊 ArPI System Status:")
    
    all_status = orchestrator.get_all_status()
    
    for component, status in all_status.items():
        click.echo(f"\n{component.upper()}:")
        for key, value in status.items():
            status_icon = "✅" if value else "❌"
            click.echo(f"   {status_icon} {key}")

if __name__== "__main__":
    cli()
