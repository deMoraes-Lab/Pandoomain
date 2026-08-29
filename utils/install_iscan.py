#!/usr/bin/env python3

import shutil
import subprocess as sp
import sys
import os
from argparse import ArgumentParser
from pathlib import Path
from shlex import split


def run(cmd: str, dry: bool = False, **kwargs):
    """Wrapper for subprocess.run with logging."""
    try:
        print(f"cd {kwargs['cwd']}")
    except KeyError:
        pass

    print(f"{cmd}")

    if not dry:
        return sp.run(split(cmd), check=True, **kwargs)


def can_reach(url):
    """Check if a URL is reachable before attempting download."""
    import httplib2
    try:
        h = httplib2.Http()
        resp = h.request(url, "HEAD")
        return int(resp[0]["status"]) < 400
    except Exception:
        return False


def fix_system_dependencies():
    """
    Checks for and attempts to install system libraries required by InterProScan binaries.
    Requires sudo privileges.
    """
    missing = []
    libs = {
        "libgomp.so.1": "libgomp1",
        "libpcre.so.3": "libpcre3"
    }
    
    print("# Checking system libraries...")
    try:
        # Check ldconfig for existing libraries
        ld_out = sp.check_output(["/sbin/ldconfig", "-p"], stderr=sp.DEVNULL).decode()
        for lib, package in libs.items():
            if lib not in ld_out:
                missing.append(package)
    except Exception:
        # Fallback to assuming they might be missing if ldconfig fails
        pass

    if missing:
        print(f"MISSING LIBS: {', '.join(missing)}. Attempting to install...")
        try:
            print("Requesting sudo to install missing system dependencies...")
            sp.run(split("sudo apt-get update"), check=True)
            sp.run(split(f"sudo apt-get install -y {' '.join(missing)}"), check=True)
            print("SUCCESS: System libraries installed.")
        except sp.CalledProcessError:
            print("\n" + "!"*60)
            print("MANUAL ACTION REQUIRED: Could not install system libraries automatically.")
            print(f"Please run manually: sudo apt-get install -y {' '.join(missing)}")
            print("!"*60 + "\n")


def check_bundled_binaries(iscan_dir):
    """
    Checks if the bundled binaries can actually run by checking their shared library dependencies.
    """
    iscan_dir = Path(iscan_dir)
    rpsblast = iscan_dir / "bin" / "cdd" / "rpsblast"
    
    if not rpsblast.exists():
        return True

    print("# Verifying bundled binaries (rpsblast)...")
    try:
        ldd_out = sp.check_output(["ldd", str(rpsblast)], stderr=sp.STDOUT).decode()
        missing = [line.strip() for line in ldd_out.split('\n') if "not found" in line]
        
        if missing:
            print("\n" + "!"*60)
            print("CRITICAL: Missing shared libraries for InterProScan binaries:")
            for m in missing:
                print(f"  - {m}")
            print("!"*60 + "\n")
            return False
    except Exception as e:
        print(f"Warning: Could not run ldd check: {e}")
    
    return True


def setup_path_access(bin_path, dry=False):
    """
    Helper to make the binary accessible via PATH or symlink.
    """
    bin_path = Path(bin_path).resolve()
    local_bin = Path.home() / ".local" / "bin"
    
    print("\n# Finalizing Path Access")
    
    if not dry:
        local_bin.mkdir(parents=True, exist_ok=True)
        link_path = local_bin / "interproscan.sh"
        try:
            if link_path.exists() or link_path.is_symlink():
                link_path.unlink()
            link_path.symlink_to(bin_path)
            print(f"SUCCESS: Created symlink at {link_path}")
        except Exception as e:
            print(f"NOTICE: Could not create symlink: {e}")
    else:
        print(f"mkdir -p {local_bin}")
        print(f"ln -s {bin_path} {local_bin}/interproscan.sh")

    current_path = os.environ.get("PATH", "")
    if str(bin_path.parent) not in current_path and str(local_bin) not in current_path:
        print("\n" + "!"*60)
        print("ACTION REQUIRED: To run InterProScan from anywhere, add it to your PATH.")
        print(f"Add this line to your ~/.bashrc (or ~/.zshrc):")
        print(f'\nexport PATH="$PATH:{bin_path.parent}"\n')
        print("Then run: source ~/.bashrc")
        print("!"*60 + "\n")


# iscan defaults
ISCAN_VERSION = "5.76-107.0"
ISCAN_INSTALLATION_DIR = Path(".")


# define args
parser = ArgumentParser(description="Download and Install interproscan.sh")

parser.add_argument(
    "--target", help=f"Version interproscan.sh to install. Default: {ISCAN_VERSION}"
)
parser.add_argument(
    "--data",
    type=Path,
    help=f"Where to put the profile data. About 60GB. Default: {ISCAN_INSTALLATION_DIR}",
)
parser.add_argument(
    "-n",
    "--dry-run",
    action="store_true",
    help="Do nothing. Only print steps that would be executed.",
)
args = parser.parse_args()


# parse args
ISCAN_VERSION = args.target if args.target is not None else ISCAN_VERSION
ISCAN_INSTALLATION_DIR = (
    args.data if args.data is not None else ISCAN_INSTALLATION_DIR
).resolve()
DRY = args.dry_run

# remotes
ISCAN_FTP = f"https://ftp.ebi.ac.uk/pub/databases/interpro/iprscan/5/{ISCAN_VERSION}"
ISCAN_FTP_GZ = f"{ISCAN_FTP}/interproscan-{ISCAN_VERSION}-64-bit.tar.gz"
ISCAN_FTP_MD5 = f"{ISCAN_FTP_GZ}.md5"

# local
MD5 = (ISCAN_INSTALLATION_DIR / Path(ISCAN_FTP_MD5).name).resolve()
GZ = (ISCAN_INSTALLATION_DIR / Path(ISCAN_FTP_GZ).name).resolve()
ISCAN_DIR = (ISCAN_INSTALLATION_DIR / f"interproscan-{ISCAN_VERSION}").resolve()
ISCAN_BIN = (ISCAN_DIR / "interproscan.sh").resolve()


# dependencies
ARIA2C = shutil.which("aria2c")
JAVA = shutil.which("java")


if __name__ == "__main__":
    # Fix system libraries before starting
    if not DRY:
        fix_system_dependencies()

    # check network
    for url in (ISCAN_FTP_GZ, ISCAN_FTP_MD5):
        if not can_reach(url):
            raise ConnectionError(f"Unreachable {url}")

    # check dependencies
    if ARIA2C is None or JAVA is None:
        print("Missing aria2c or java binaries")
        print("Execution halted")
        sys.exit(1)

    # create download directory
    if not DRY:
        ISCAN_INSTALLATION_DIR.mkdir(parents=True, exist_ok=True)
    else:
        print(f"mkdir -p {ISCAN_INSTALLATION_DIR}")

    # download GZ
    for ftp_target in (ISCAN_FTP_MD5, ISCAN_FTP_GZ):
        cmd = (
            "aria2c "
            f"--dir {ISCAN_INSTALLATION_DIR} "
            "--continue=true "
            "--split 12 "
            "--max-connection-per-server=16 "
            "--min-split-size=1M "
            f"{ftp_target}"
        )
        run(cmd, dry=DRY)

    # check md5sum
    run(f"md5sum -c {MD5}", dry=DRY, cwd=ISCAN_INSTALLATION_DIR)

    # untar
    run(f"tar -xf {GZ}", dry=DRY, cwd=ISCAN_INSTALLATION_DIR)

    # Verify binaries after untar
    if not check_bundled_binaries(ISCAN_DIR):
        print("Dependency check failed. Attempting to fix...")
        if not DRY:
            fix_system_dependencies()

    # setup
    run(f"python3 setup.py -f interproscan.properties", dry=DRY, cwd=ISCAN_DIR)

    # set permissions
    if not DRY:
        ISCAN_BIN.chmod(0o755)
    else:
        print(f"chmod 755 {ISCAN_BIN}")

    # Finalize Path
    setup_path_access(ISCAN_BIN, dry=DRY)

    # test
    print("\n# Test installation.")
    try:
        run(f"{ISCAN_BIN} -i test_all_appl.fasta -f tsv", dry=DRY, cwd=ISCAN_DIR)
    except sp.CalledProcessError:
        print("\n" + "!"*60)
        print("TEST FAILED: InterProScan could not complete the test run.")
        print("Check if missing libraries are mentioned above.")
        print("!"*60 + "\n")
        sys.exit(1)