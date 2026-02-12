#!/usr/bin/env python
"""
Setup C++ Acceleration Dependencies
Downloads and installs required Visual C++ runtime for Windows.
"""

import os
import sys
import platform
import subprocess
import urllib.request
import tempfile
from pathlib import Path

def check_cpp_acceleration():
    """Check if C++ acceleration modules are available."""
    try:
        from edgecore import cointegration_cpp
        print("✓ C++ cointegration module available")
        return True
    except ImportError as e:
        print(f"✗ C++ module not available: {e}")
        return False

def install_visual_cpp_runtime():
    """Install Visual C++ 14.0+ runtime on Windows."""
    
    if platform.system() != "Windows":
        print("⚠ Visual C++ runtime installation only needed on Windows")
        return False
    
    print("\nAttempting to install Visual C++ Runtime...")
    print("This may require administrator privileges.\n")
    
    # URLs for Visual C++ redistributables
    vcruntime_urls = {
        'x64': 'https://aka.ms/vs/17/release/vc_redist.x64.exe',
        'x86': 'https://aka.ms/vs/17/release/vc_redist.x86.exe',
    }
    
    # Determine architecture
    arch = 'x64' if sys.maxsize > 2**32 else 'x86'
    url = vcruntime_urls[arch]
    
    try:
        print(f"Downloading Visual C++ Runtime for {arch}...")
        
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as tmp:
            tmp_path = tmp.name
            
        # Download
        urllib.request.urlretrieve(url, tmp_path)
        print(f"✓ Downloaded to {tmp_path}")
        
        # Run installer
        print("Running installer (this may prompt for admin rights)...")
        result = subprocess.run([tmp_path, '/quiet', '/norestart'], 
                              capture_output=False)
        
        # Cleanup
        os.unlink(tmp_path)
        
        if result.returncode == 0:
            print("✓ Visual C++ Runtime installed successfully")
            return True
        else:
            print(f"⚠ Installer exited with code {result.returncode}")
            return False
            
    except Exception as e:
        print(f"✗ Installation failed: {e}")
        print("\nManual Installation:")
        print(f"  Download: {url}")
        print(f"  Run: vc_redist.{arch}.exe /quiet /install")
        return False

def install_build_tools():
    """Install build tools if missing."""
    
    tools_needed = []
    
    # Check for cmake
    try:
        subprocess.run(['cmake', '--version'], 
                      capture_output=True, check=True)
        print("✓ CMake found")
    except (FileNotFoundError, subprocess.CalledProcessError):
        tools_needed.append('cmake')
        print("⚠ CMake not found")
    
    # Check for pybind11
    try:
        import pybind11
        print("✓ pybind11 found")
    except ImportError:
        tools_needed.append('pybind11')
        print("⚠ pybind11 not found")
    
    if tools_needed:
        print(f"\nInstalling missing build tools: {', '.join(tools_needed)}")
        for tool in tools_needed:
            subprocess.run([sys.executable, '-m', 'pip', 'install', tool],
                         check=False)
        return len(tools_needed) > 0
    
    return False

def compile_cpp_modules():
    """Compile C++ extensions."""
    
    edgecore_root = Path(__file__).parent.parent
    build_dir = edgecore_root / 'build'
    
    print("\nCompiling C++ modules...")
    print(f"  Working directory: {edgecore_root}")
    
    try:
        # Create build directory
        build_dir.mkdir(exist_ok=True)
        os.chdir(build_dir)
        
        # Configure with CMake
        print("  Running: cmake ..")
        result = subprocess.run(['cmake', '..'], 
                              cwd=build_dir,
                              capture_output=True, 
                              text=True)
        
        if result.returncode != 0:
            print(f"✗ CMake configuration failed:")
            print(result.stderr)
            return False
        
        print("  ✓ CMake configuration succeeded")
        
        # Build
        print("  Running: cmake --build . --config Release")
        result = subprocess.run(['cmake', '--build', '.', '--config', 'Release'],
                              cwd=build_dir,
                              capture_output=True,
                              text=True)
        
        if result.returncode != 0:
            print(f"✗ Build failed:")
            print(result.stderr)
            return False
        
        print("  ✓ Compilation succeeded")
        return True
        
    except Exception as e:
        print(f"✗ Compilation error: {e}")
        return False
    finally:
        os.chdir(edgecore_root)

def main():
    """Main setup routine."""
    
    print("=" * 80)
    print("  EDGECORE C++ ACCELERATION SETUP")
    print("=" * 80)
    print()
    
    # Check current status
    has_cpp = check_cpp_acceleration()
    print()
    
    if has_cpp:
        print("✓ C++ acceleration is already available!")
        print("  10x+ speedup enabled for cointegration testing")
        return 0
    
    # Install dependencies
    print("\n" + "=" * 80)
    print("  INSTALLING DEPENDENCIES")
    print("=" * 80)
    
    if platform.system() == "Windows":
        install_visual_cpp_runtime()
    
    install_build_tools()
    
    # Try to compile
    print("\n" + "=" * 80)
    print("  COMPILING C++ MODULES")
    print("=" * 80)
    print()
    
    if compile_cpp_modules():
        print("\n✓ C++ modules compiled successfully!")
    else:
        print("\n⚠ Compilation failed")
        print("  You can still use EDGECORE with Python-only mode")
        print("  (Performance will be slower but fully functional)")
    
    # Final check
    print("\n" + "=" * 80)
    print("  VERIFICATION")
    print("=" * 80)
    print()
    
    if check_cpp_acceleration():
        print("\n✓ SUCCESS! C++ acceleration is now active")
        print("  Cointegration tests will be 10x faster")
        return 0
    else:
        print("\n⚠ C++ acceleration not yet available")
        print("  Using Python fallback (fully functional)")
        return 1

if __name__ == '__main__':
    sys.exit(main())
