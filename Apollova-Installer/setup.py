"""
Apollova Setup Wizard
Installs required dependencies for Apollova
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
import os
import threading
import urllib.request
import tempfile
from pathlib import Path
import shutil


class SetupWizard:
    # Python installer URL (Windows 64-bit)
    PYTHON_URL = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    PYTHON_INSTALLER_SIZE = "~25MB"
    
    def __init__(self, root):
        self.root = root
        self.root.title("Apollova Setup")
        self.root.geometry("550x520")
        self.root.resizable(False, False)
        
        # Center window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 550) // 2
        y = (self.root.winfo_screenheight() - 520) // 2
        self.root.geometry(f"550x520+{x}+{y}")
        
        # Get install directory (where setup.exe is located)
        if getattr(sys, 'frozen', False):
            self.install_dir = Path(sys.executable).parent
        else:
            self.install_dir = Path(__file__).parent
        
        self.assets_dir = self.install_dir / "assets"
        self.requirements_dir = self.assets_dir / "requirements"
        
        # State
        self.installing = False
        self.cancelled = False
        self.python_path = None
        
        self._create_ui()
        self._check_python()
    
    def _create_ui(self):
        """Create the setup wizard UI"""
        
        # Main container
        main = ttk.Frame(self.root, padding="20")
        main.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title = ttk.Label(main, text="Apollova Setup", font=('Segoe UI', 18, 'bold'))
        title.pack(pady=(0, 5))
        
        subtitle = ttk.Label(main, text="Install dependencies to run Apollova", 
                            font=('Segoe UI', 10), foreground='#666666')
        subtitle.pack(pady=(0, 20))
        
        # Python status frame
        python_frame = ttk.LabelFrame(main, text="Python Status", padding="10")
        python_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.python_status = ttk.Label(python_frame, text="Checking...", font=('Segoe UI', 9))
        self.python_status.pack(anchor=tk.W)
        
        self.install_python_var = tk.BooleanVar(value=False)
        self.install_python_check = ttk.Checkbutton(
            python_frame, 
            text=f"Download and install Python for me ({self.PYTHON_INSTALLER_SIZE})",
            variable=self.install_python_var,
            state='disabled'
        )
        self.install_python_check.pack(anchor=tk.W, pady=(5, 0))
        
        # Options frame
        options_frame = ttk.LabelFrame(main, text="Installation Options", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Base packages (required)
        self.base_var = tk.BooleanVar(value=True)
        base_check = ttk.Checkbutton(
            options_frame,
            text="Install required packages (required)",
            variable=self.base_var,
            state='disabled'  # Always required
        )
        base_check.pack(anchor=tk.W)
        
        # GPU acceleration
        self.gpu_var = tk.BooleanVar(value=False)
        gpu_check = ttk.Checkbutton(
            options_frame,
            text="Enable GPU Acceleration (optional)",
            variable=self.gpu_var
        )
        gpu_check.pack(anchor=tk.W, pady=(10, 0))
        
        gpu_info = ttk.Label(
            options_frame,
            text="    • Requires NVIDIA GPU with CUDA support\n"
                 "    • Additional storage: ~1.5GB\n"
                 "    • Significantly speeds up transcription",
            font=('Segoe UI', 8),
            foreground='#666666'
        )
        gpu_info.pack(anchor=tk.W)
        
        # Desktop shortcut
        self.shortcut_var = tk.BooleanVar(value=True)
        shortcut_check = ttk.Checkbutton(
            options_frame,
            text="Create desktop shortcut",
            variable=self.shortcut_var
        )
        shortcut_check.pack(anchor=tk.W, pady=(10, 0))
        
        # Progress frame
        progress_frame = ttk.LabelFrame(main, text="Progress", padding="10")
        progress_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.status_var = tk.StringVar(value="Ready to install")
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var, font=('Segoe UI', 9))
        self.status_label.pack(anchor=tk.W)
        
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(10, 5))
        
        self.detail_var = tk.StringVar(value="")
        self.detail_label = ttk.Label(progress_frame, textvariable=self.detail_var, 
                                       font=('Segoe UI', 8), foreground='#888888')
        self.detail_label.pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.cancel_btn = ttk.Button(button_frame, text="Cancel", command=self._cancel)
        self.cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        self.install_btn = ttk.Button(button_frame, text="Install", command=self._start_install)
        self.install_btn.pack(side=tk.RIGHT)
    
    def _check_python(self):
        """Check if Python is installed"""
        self.python_path = self._find_python()
        
        if self.python_path:
            version = self._get_python_version(self.python_path)
            self.python_status.config(
                text=f"✓ Python {version} found at: {self.python_path}",
                foreground='green'
            )
            self.install_python_check.config(state='disabled')
            self.install_python_var.set(False)
        else:
            self.python_status.config(
                text="✗ Python 3.10+ not found",
                foreground='red'
            )
            self.install_python_check.config(state='normal')
            self.install_python_var.set(True)
    
    def _find_python(self):
        """Find Python executable"""
        # Check common locations
        possible_paths = [
            "python",
            "python3",
            sys.executable,
            r"C:\Python311\python.exe",
            r"C:\Python310\python.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Python\Python311\python.exe"),
            os.path.expanduser(r"~\AppData\Local\Programs\Python\Python310\python.exe"),
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run(
                    [path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    version_str = result.stdout.strip() or result.stderr.strip()
                    # Check version >= 3.10
                    if "Python 3.1" in version_str or "Python 3.2" in version_str:
                        return path
            except:
                continue
        
        return None
    
    def _get_python_version(self, python_path):
        """Get Python version string"""
        try:
            result = subprocess.run(
                [python_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip().replace("Python ", "") or "Unknown"
        except:
            return "Unknown"
    
    def _cancel(self):
        """Cancel installation"""
        if self.installing:
            self.cancelled = True
            self.status_var.set("Cancelling...")
        else:
            self.root.quit()
    
    def _start_install(self):
        """Start the installation process"""
        if self.installing:
            return
        
        # Validate
        if not self.python_path and not self.install_python_var.get():
            messagebox.showerror("Error", "Python is required. Please check 'Download and install Python'.")
            return
        
        self.installing = True
        self.cancelled = False
        self.install_btn.config(state='disabled')
        
        # Run in thread
        thread = threading.Thread(target=self._install_thread, daemon=True)
        thread.start()
    
    def _install_thread(self):
        """Installation thread"""
        try:
            steps = []
            
            # Determine steps
            if not self.python_path and self.install_python_var.get():
                steps.append(("download_python", "Downloading Python..."))
                steps.append(("install_python", "Installing Python..."))
            
            steps.append(("install_base", "Installing required packages..."))
            
            if self.gpu_var.get():
                steps.append(("install_gpu", "Installing GPU packages (this may take a while)..."))
            
            steps.append(("create_launcher", "Creating Apollova launcher..."))
            steps.append(("create_uninstaller", "Creating uninstaller..."))
            
            if self.shortcut_var.get():
                steps.append(("create_shortcut", "Creating desktop shortcut..."))
            
            total_steps = len(steps)
            
            for i, (step_id, step_name) in enumerate(steps):
                if self.cancelled:
                    self._update_status("Installation cancelled", 0, "")
                    break
                
                progress = (i / total_steps) * 100
                self._update_status(step_name, progress, "")
                
                success = self._run_step(step_id)
                
                if not success and not self.cancelled:
                    self._update_status(f"Failed: {step_name}", progress, "See error message")
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to complete: {step_name}"))
                    break
            else:
                # All steps completed
                self._update_status("Installation complete!", 100, "")
                self.root.after(0, self._show_complete_dialog)
        
        except Exception as e:
            self._update_status(f"Error: {str(e)}", 0, "")
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        
        finally:
            self.installing = False
            self.root.after(0, lambda: self.install_btn.config(state='normal'))
    
    def _run_step(self, step_id):
        """Run a single installation step"""
        
        if step_id == "download_python":
            return self._download_python()
        
        elif step_id == "install_python":
            return self._install_python()
        
        elif step_id == "install_base":
            return self._install_packages("requirements-base.txt")
        
        elif step_id == "install_gpu":
            return self._install_packages("requirements-gpu.txt")
        
        elif step_id == "create_launcher":
            return self._create_launcher()
        
        elif step_id == "create_uninstaller":
            return self._create_uninstaller()
        
        elif step_id == "create_shortcut":
            return self._create_shortcut()
        
        return False
    
    def _download_python(self):
        """Download Python installer"""
        try:
            self._update_detail("Connecting to python.org...")
            
            temp_dir = tempfile.gettempdir()
            installer_path = os.path.join(temp_dir, "python_installer.exe")
            
            def progress_hook(block_num, block_size, total_size):
                if total_size > 0:
                    percent = min(100, (block_num * block_size * 100) // total_size)
                    self._update_detail(f"Downloading: {percent}%")
            
            urllib.request.urlretrieve(self.PYTHON_URL, installer_path, progress_hook)
            
            self.python_installer_path = installer_path
            return True
        
        except Exception as e:
            self._update_detail(f"Download failed: {e}")
            return False
    
    def _install_python(self):
        """Install Python silently"""
        try:
            self._update_detail("Running Python installer (this may take a minute)...")
            
            # Silent install with pip and add to PATH
            result = subprocess.run([
                self.python_installer_path,
                "/quiet",
                "InstallAllUsers=0",
                "PrependPath=1",
                "Include_pip=1",
                "Include_test=0"
            ], timeout=300)
            
            if result.returncode == 0:
                # Re-check for Python
                self.python_path = self._find_python()
                return self.python_path is not None
            
            return False
        
        except Exception as e:
            self._update_detail(f"Install failed: {e}")
            return False
    
    def _install_packages(self, requirements_file):
        """Install packages from requirements file"""
        try:
            req_path = self.requirements_dir / requirements_file
            
            if not req_path.exists():
                self._update_detail(f"Requirements file not found: {req_path}")
                return False
            
            python = self.python_path or "python"
            
            # Read requirements to show progress
            with open(req_path, 'r') as f:
                packages = [line.strip() for line in f if line.strip() and not line.startswith('#') and not line.startswith('--')]
            
            self._update_detail(f"Installing {len(packages)} packages...")
            
            # Install using pip
            cmd = [python, "-m", "pip", "install", "-r", str(req_path), "--quiet"]
            
            # For GPU packages, add the extra index URL
            if "gpu" in requirements_file:
                cmd.extend(["--extra-index-url", "https://download.pytorch.org/whl/cu118"])
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(timeout=1800)  # 30 min timeout for GPU packages
            
            if process.returncode != 0:
                self._update_detail(f"pip error: {stderr[:200]}")
                return False
            
            return True
        
        except subprocess.TimeoutExpired:
            self._update_detail("Installation timed out")
            return False
        except Exception as e:
            self._update_detail(f"Error: {e}")
            return False
    
    def _create_launcher(self):
        """Create the Apollova.exe launcher"""
        try:
            python = self.python_path or "python"
            gui_path = self.assets_dir / "apollova_gui.py"
            
            # Create a batch file first, then we'll explain how to convert to exe
            # Or create a simple Python launcher that gets compiled
            
            launcher_py = self.install_dir / "launcher_temp.py"
            launcher_code = f'''#!/usr/bin/env python
"""Apollova Launcher"""
import subprocess
import sys
import os
from pathlib import Path

def main():
    # Get the directory where this exe is located
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent
    
    gui_path = base_dir / "assets" / "apollova_gui.py"
    
    if not gui_path.exists():
        import tkinter.messagebox as mb
        mb.showerror("Error", f"Could not find apollova_gui.py at:\\n{{gui_path}}")
        sys.exit(1)
    
    # Run the GUI
    os.chdir(base_dir)
    subprocess.run([sys.executable, str(gui_path)])

if __name__ == "__main__":
    main()
'''
            
            with open(launcher_py, 'w') as f:
                f.write(launcher_code)
            
            # Build the launcher exe using PyInstaller
            self._update_detail("Building launcher executable...")
            
            result = subprocess.run([
                python, "-m", "PyInstaller",
                "--onefile",
                "--windowed",
                "--name", "Apollova",
                "--icon", str(self.assets_dir / "icon.ico") if (self.assets_dir / "icon.ico").exists() else "",
                "--distpath", str(self.install_dir),
                "--workpath", str(self.install_dir / "build_temp"),
                "--specpath", str(self.install_dir / "build_temp"),
                str(launcher_py)
            ], capture_output=True, text=True, timeout=300)
            
            # Cleanup
            launcher_py.unlink(missing_ok=True)
            shutil.rmtree(self.install_dir / "build_temp", ignore_errors=True)
            
            if result.returncode != 0:
                # Fallback: create a .bat file
                self._update_detail("Creating batch launcher as fallback...")
                bat_path = self.install_dir / "Apollova.bat"
                with open(bat_path, 'w') as f:
                    f.write(f'@echo off\ncd /d "%~dp0"\n"{python}" "assets\\apollova_gui.py"\n')
                return True
            
            return True
        
        except Exception as e:
            self._update_detail(f"Error creating launcher: {e}")
            # Fallback to batch file
            try:
                bat_path = self.install_dir / "Apollova.bat"
                python = self.python_path or "python"
                with open(bat_path, 'w') as f:
                    f.write(f'@echo off\ncd /d "%~dp0"\n"{python}" "assets\\apollova_gui.py"\n')
                return True
            except:
                return False
    
    def _create_uninstaller(self):
        """Create uninstaller"""
        try:
            python = self.python_path or "python"
            
            uninstaller_py = self.install_dir / "uninstaller_temp.py"
            
            # Read packages to uninstall from requirements
            packages_to_remove = []
            for req_file in ["requirements-base.txt", "requirements-gpu.txt"]:
                req_path = self.requirements_dir / req_file
                if req_path.exists():
                    with open(req_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#') and not line.startswith('--'):
                                # Get package name (before any version specifier)
                                pkg = line.split('==')[0].split('>=')[0].split('<=')[0].split('[')[0]
                                if pkg not in packages_to_remove:
                                    packages_to_remove.append(pkg)
            
            packages_str = str(packages_to_remove)
            
            uninstaller_code = f'''#!/usr/bin/env python
"""Apollova Uninstaller"""
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading

PACKAGES = {packages_str}

class Uninstaller:
    def __init__(self, root):
        self.root = root
        self.root.title("Uninstall Apollova")
        self.root.geometry("400x200")
        self.root.resizable(False, False)
        
        # Center
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - 400) // 2
        y = (self.root.winfo_screenheight() - 200) // 2
        self.root.geometry(f"400x200+{{x}}+{{y}}")
        
        main = ttk.Frame(self.root, padding="20")
        main.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main, text="Uninstall Apollova", font=('Segoe UI', 14, 'bold')).pack(pady=(0, 10))
        ttk.Label(main, text="This will remove installed Python packages.\\nYour projects and templates will NOT be deleted.", 
                  justify=tk.CENTER).pack(pady=(0, 15))
        
        self.status = ttk.Label(main, text="")
        self.status.pack()
        
        self.progress = ttk.Progressbar(main, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=10)
        
        btn_frame = ttk.Frame(main)
        btn_frame.pack()
        
        self.uninstall_btn = ttk.Button(btn_frame, text="Uninstall", command=self.uninstall)
        self.uninstall_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="Cancel", command=self.root.quit).pack(side=tk.LEFT, padx=5)
    
    def uninstall(self):
        self.uninstall_btn.config(state='disabled')
        self.progress.start()
        threading.Thread(target=self._uninstall_thread, daemon=True).start()
    
    def _uninstall_thread(self):
        try:
            for i, pkg in enumerate(PACKAGES):
                self.root.after(0, lambda p=pkg: self.status.config(text=f"Removing {{p}}..."))
                subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", pkg],
                             capture_output=True, timeout=60)
            
            self.root.after(0, self._complete)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.root.after(0, lambda: self.uninstall_btn.config(state='normal'))
            self.root.after(0, self.progress.stop)
    
    def _complete(self):
        self.progress.stop()
        self.status.config(text="Uninstall complete!")
        messagebox.showinfo("Complete", "Apollova packages have been removed.\\n\\nYou can now delete the Apollova folder.")
        self.root.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = Uninstaller(root)
    root.mainloop()
'''
            
            with open(uninstaller_py, 'w') as f:
                f.write(uninstaller_code)
            
            # Build uninstaller exe
            self._update_detail("Building uninstaller executable...")
            
            result = subprocess.run([
                python, "-m", "PyInstaller",
                "--onefile",
                "--windowed",
                "--name", "Uninstall",
                "--distpath", str(self.install_dir),
                "--workpath", str(self.install_dir / "build_temp"),
                "--specpath", str(self.install_dir / "build_temp"),
                str(uninstaller_py)
            ], capture_output=True, text=True, timeout=300)
            
            # Cleanup
            uninstaller_py.unlink(missing_ok=True)
            shutil.rmtree(self.install_dir / "build_temp", ignore_errors=True)
            
            return True
        
        except Exception as e:
            self._update_detail(f"Error creating uninstaller: {e}")
            return False
    
    def _create_shortcut(self):
        """Create desktop shortcut"""
        try:
            import winreg
            
            # Get desktop path
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
            desktop = winreg.QueryValueEx(key, "Desktop")[0]
            winreg.CloseKey(key)
            
            # Create shortcut using PowerShell
            exe_path = self.install_dir / "Apollova.exe"
            if not exe_path.exists():
                exe_path = self.install_dir / "Apollova.bat"
            
            shortcut_path = os.path.join(desktop, "Apollova.lnk")
            icon_path = self.assets_dir / "icon.ico"
            
            ps_script = f'''
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{exe_path}"
$Shortcut.WorkingDirectory = "{self.install_dir}"
$Shortcut.IconLocation = "{icon_path}"
$Shortcut.Save()
'''
            
            subprocess.run(["powershell", "-Command", ps_script], 
                          capture_output=True, timeout=30)
            
            return True
        
        except Exception as e:
            self._update_detail(f"Shortcut creation failed: {e}")
            return False
    
    def _update_status(self, status, progress, detail):
        """Update status from thread"""
        self.root.after(0, lambda: self.status_var.set(status))
        self.root.after(0, lambda: self.progress_var.set(progress))
        self.root.after(0, lambda: self.detail_var.set(detail))
    
    def _update_detail(self, detail):
        """Update detail text from thread"""
        self.root.after(0, lambda: self.detail_var.set(detail))
    
    def _show_complete_dialog(self):
        """Show installation complete dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Setup Complete")
        dialog.geometry("450x350")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 450) // 2
        y = (dialog.winfo_screenheight() - 350) // 2
        dialog.geometry(f"450x350+{x}+{y}")
        
        main = ttk.Frame(dialog, padding="20")
        main.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main, text="Setup Complete!", font=('Segoe UI', 16, 'bold'), 
                 foreground='green').pack(pady=(0, 15))
        
        ttk.Label(main, text="✓ All dependencies installed successfully", 
                 font=('Segoe UI', 10)).pack(anchor=tk.W)
        
        # Whisper note
        note_frame = ttk.LabelFrame(main, text="Important Note", padding="10")
        note_frame.pack(fill=tk.X, pady=15)
        
        note_text = (
            "The first time you generate jobs, the Whisper transcription\n"
            "model will be downloaded automatically.\n\n"
            "Model sizes:\n"
            "  • tiny   - ~75MB   (fastest, less accurate)\n"
            "  • base   - ~140MB  (balanced)\n"
            "  • small  - ~460MB  (recommended)\n"
            "  • medium - ~1.5GB  (slower, more accurate)\n"
            "  • large  - ~3GB    (slowest, most accurate)"
        )
        ttk.Label(note_frame, text=note_text, font=('Segoe UI', 9)).pack(anchor=tk.W)
        
        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        
        def launch_app():
            dialog.destroy()
            self.root.quit()
            # Launch Apollova
            exe_path = self.install_dir / "Apollova.exe"
            if exe_path.exists():
                subprocess.Popen([str(exe_path)])
            else:
                bat_path = self.install_dir / "Apollova.bat"
                if bat_path.exists():
                    subprocess.Popen([str(bat_path)], shell=True)
        
        def close_setup():
            dialog.destroy()
            self.root.quit()
        
        ttk.Button(btn_frame, text="Launch Apollova", command=launch_app).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Close", command=close_setup).pack(side=tk.RIGHT)


def main():
    root = tk.Tk()
    app = SetupWizard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
