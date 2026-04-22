#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Get desktop window information using UFO's own MCP tools."""

import asyncio
import json
import subprocess


def get_windows_powershell():
    """Get window info via PowerShell."""
    cmd = r"""
$windows = @()
Get-Process | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -ne '' } | ForEach-Object {
    $windows += [PSCustomObject]@{
        PID = $_.Id
        Process = $_.ProcessName
        Exe = if($_.Path){Split-Path $_.Path -Leaf}else{''}
        Title = $_.MainWindowTitle
    }
}
$windows | Sort-Object Process | ConvertTo-Json -Depth 3
"""
    result = subprocess.run(
        ["powershell", "-Command", cmd],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout


def get_detailed_windows():
    """Get detailed window info with position and state."""
    cmd = r"""
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public class WinAPI {
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll", CharSet=CharSet.Auto)] public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    public struct RECT { public int Left, Top, Right, Bottom; }
}
'@ -Language CSharp

$fgHwnd = [WinAPI]::GetForegroundWindow()
$windows = @()
Get-Process | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -ne '' } | ForEach-Object {
    $hwnd = $_.MainWindowHandle
    $minimized = [WinAPI]::IsIconic($hwnd)
    $maximized = [WinAPI]::IsZoomed($hwnd)
    $rect = New-Object WinAPI+RECT
    [void][WinAPI]::GetWindowRect($hwnd, [ref]$rect)
    $sb = New-Object System.Text.StringBuilder 256
    [void][WinAPI]::GetClassName($hwnd, $sb, 256)
    $isActive = ($hwnd -eq $fgHwnd)
    
    $state = "Normal"
    if ($minimized) { $state = "Minimized" }
    elseif ($maximized) { $state = "Maximized" }
    
    $windows += [PSCustomObject]@{
        PID = $_.Id
        Process = $_.ProcessName
        Exe = if($_.Path){Split-Path $_.Path -Leaf}else{''}
        Title = $_.MainWindowTitle
        ClassName = $sb.ToString()
        State = $state
        Active = $isActive
        Position = "$($rect.Left),$($rect.Top)"
        Size = "$($rect.Right - $rect.Left)x$($rect.Bottom - $rect.Top)"
    }
}
$windows | Sort-Object Process | ConvertTo-Json -Depth 3
"""
    result = subprocess.run(
        ["powershell", "-Command", cmd],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout


def get_ufo_control_info():
    """Get control tree info for active windows using UFO's COM automation."""
    cmd = r"""
$shell = New-Object -ComObject Shell.Application
$windows = $shell.Windows()
Write-Output "Shell windows count: $($windows.Count)"
"""
    result = subprocess.run(
        ["powershell", "-Command", cmd],
        capture_output=True, text=True, timeout=15
    )
    return result.stdout


if __name__ == "__main__":
    print("=" * 70)
    print("  Desktop Window Information Report")
    print("=" * 70)
    
    # Simple window list
    print("\n📋 Running Processes with Windows:")
    print("-" * 70)
    raw = get_windows_powershell()
    try:
        wins = json.loads(raw)
        if not isinstance(wins, list):
            wins = [wins]
        for w in wins:
            print(f"  PID={w.get('PID','?'):>6}  {w.get('Exe','?'):<25}  Title: {w.get('Title','')[:60]}")
        print(f"\n  Total: {len(wins)} windows")
    except:
        print(raw[:2000])
    
    # Detailed info
    print("\n\n📊 Detailed Window States:")
    print("-" * 70)
    raw2 = get_detailed_windows()
    try:
        wins2 = json.loads(raw2)
        if not isinstance(wins2, list):
            wins2 = [wins2]
        for w in wins2:
            active_mark = " ⭐ACTIVE" if w.get("Active") else ""
            print(f"  [{w.get('State','?'):>10}] {w.get('Exe','?'):<25} @ ({w.get('Position','?')}) {w.get('Size','?')}{active_mark}")
            print(f"             Title: {w.get('Title','')[:70]}")
            print(f"             Class: {w.get('ClassName','')[:50]}")
            print()
    except:
        print(raw2[:2000])
