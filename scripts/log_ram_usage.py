#!/usr/bin/env python3
"""
Script para registrar uso de RAM en SQLite, reemplazando las alertas de cron job.
Captura todo: RAM, swap, top procesos, load avg, uptime.
"""
import sqlite3
import subprocess
import datetime
import os
import sys
import re

DB_PATH = '/var/www/predicta.com.co/ram_monitor.db'

def capture_memory_info():
    """Captura info de free, top, swap, load average, uptime."""
    data = {}
    # free -m
    free_output = subprocess.check_output(['free', '-m'], text=True).strip()
    lines = free_output.split('\n')
    data['free_output'] = free_output
    
    # Parse RAM
    if len(lines) >= 2:
        parts = lines[1].split()
        if len(parts) >= 3:
            data['total_mb'] = int(parts[1])
            data['used_mb'] = int(parts[2])
            data['free_mb'] = int(parts[3])
            data['usage_percent'] = round((data['used_mb'] / data['total_mb']) * 100, 2) if data['total_mb'] > 0 else 0.0
        else:
            data['total_mb'] = data['used_mb'] = data['free_mb'] = data['usage_percent'] = 0
    else:
        data['total_mb'] = data['used_mb'] = data['free_mb'] = data['usage_percent'] = 0
    
    # Parse swap (línea 3)
    if len(lines) >= 3:
        parts = lines[2].split()
        if len(parts) >= 3:
            data['swap_total_mb'] = int(parts[1])
            data['swap_used_mb'] = int(parts[2])
            data['swap_free_mb'] = int(parts[3])
            data['swap_percent'] = round((data['swap_used_mb'] / data['swap_total_mb']) * 100, 2) if data['swap_total_mb'] > 0 else 0.0
        else:
            data['swap_total_mb'] = data['swap_used_mb'] = data['swap_free_mb'] = data['swap_percent'] = 0
    else:
        data['swap_total_mb'] = data['swap_used_mb'] = data['swap_free_mb'] = data['swap_percent'] = 0

    # top -b -n1 (completo)
    try:
        top_output = subprocess.check_output(['top', '-b', '-n1'], text=True, timeout=3).strip()
        data['top_output'] = top_output[:2000]  # límite razonable
    except Exception as e:
        data['top_output'] = f"Error top: {e}"
    
    # top ordenado por memoria (top 20 líneas después del header)
    try:
        top_mem = subprocess.check_output(['ps', 'aux', '--sort=-%mem'], text=True, timeout=2)
        lines_mem = top_mem.split('\n')[:22]  # header + 20 procesos
        data['top_mem_output'] = '\n'.join(lines_mem)[:1500]
    except Exception as e:
        data['top_mem_output'] = f"Error top mem: {e}"
    
    # load average (de /proc/loadavg)
    try:
        with open('/proc/loadavg', 'r') as f:
            load = f.read().strip().split()[:3]
            data['load_1'], data['load_5'], data['load_15'] = map(float, load)
    except Exception as e:
        data['load_1'] = data['load_5'] = data['load_15'] = 0.0
    
    # uptime
    try:
        uptime_out = subprocess.check_output(['uptime'], text=True).strip()
        data['uptime_output'] = uptime_out
    except Exception as e:
        data['uptime_output'] = f"Error uptime: {e}"
    
    return data

def insert_record(data):
    """Inserta registro en SQLite."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO ram_usage (
            total_mb, used_mb, free_mb, usage_percent,
            swap_total_mb, swap_used_mb, swap_free_mb, swap_percent,
            top_output, free_output, top_mem_output
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data['total_mb'], data['used_mb'], data['free_mb'], data['usage_percent'],
        data['swap_total_mb'], data['swap_used_mb'], data['swap_free_mb'], data['swap_percent'],
        data['top_output'], data['free_output'], data['top_mem_output']
    ))
    conn.commit()
    conn.close()

def main():
    try:
        data = capture_memory_info()
        insert_record(data)
        print(f"Registro completo: RAM {data['used_mb']}MB/{data['total_mb']}MB ({data['usage_percent']}%) | Swap {data['swap_used_mb']}MB/{data['swap_total_mb']}MB ({data['swap_percent']}%) | Load {data['load_1']:.2f} {data['load_5']:.2f} {data['load_15']:.2f}")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()