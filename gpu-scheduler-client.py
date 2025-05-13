#!/usr/bin/env python3
"""
Simple client for the GPU scheduler with robust error handling
"""

import argparse
import requests
import sys
import os
from datetime import datetime

def make_api_request(method, url, json_data=None):
    """Make an API request with error handling"""
    try:
        if method.lower() == 'get':
            response = requests.get(url)
        elif method.lower() == 'post':
            response = requests.post(url, json=json_data)
        else:
            print(f"Unsupported method: {method}")
            return None
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: API returned {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error connecting to server: {e}")
        return None

def submit_job(args):
    """Submit a job to the scheduler"""
    # Parse environment variables
    env = {}
    if args.env:
        for env_var in args.env:
            key, value = env_var.split('=', 1)
            env[key] = value
    
    # Prepare job config
    job_config = {
        "command": args.command,
        "num_gpus": args.gpus,
        "memory_limit": args.memory,
        "priority": args.priority
    }
    
    if args.gpu_ids:
        job_config["gpu_ids"] = args.gpu_ids
    if env:
        job_config["env"] = env
    if args.working_dir:
        job_config["working_dir"] = args.working_dir
    if args.name:
        job_config["name"] = args.name
    
    print(f"Submitting job with command: {args.command}")
    print(f"Options: {args.gpus} GPUs, Memory: {args.memory}GB, Priority: {args.priority}")
    
    # Send request
    result = make_api_request('post', f"{args.server}/jobs", job_config)
    if result:
        print(f"Job submitted with ID: {result['job_id']}")
        return True
    return False

def list_jobs(args):
    """List all jobs"""
    result = make_api_request('get', f"{args.server}/jobs")
    if not result:
        return False
    
    jobs = result.get("jobs", {})
    if not jobs:
        print("No jobs found.")
        return True
    
    # Print header
    print(f"{'JOB ID':<10} {'NAME':<20} {'STATUS':<10} {'GPUs':<10} {'SUBMITTED':<20}")
    print("-" * 70)
    
    # Print jobs
    for job_id, job in jobs.items():
        gpus_str = ','.join(map(str, job['assigned_gpus'] or [])) if job['assigned_gpus'] else '-'
        submit_time = job['submit_time']
        submit_time_str = datetime.fromtimestamp(submit_time).strftime('%Y-%m-%d %H:%M:%S') if submit_time else '-'
        
        print(f"{job_id:<10} {job['name'][:20]:<20} {job['status']:<10} {gpus_str:<10} {submit_time_str:<20}")
    
    return True

def get_job_status(args):
    """Get detailed job status"""
    result = make_api_request('get', f"{args.server}/jobs/{args.job_id}")
    if not result:
        return False
    
    job = result.get("job")
    if not job:
        print(f"Job {args.job_id} not found.")
        return False
    
    # Print job details
    print(f"Job ID: {args.job_id}")
    print(f"Name: {job['name']}")
    print(f"Status: {job['status']}")
    print(f"Command: {job['command']}")
    print(f"GPUs: {', '.join(map(str, job['assigned_gpus'] or []))}" if job['assigned_gpus'] else "GPUs: (not assigned)")
    print(f"Memory Limit: {job['memory_limit']} GB")
    
    if job['submit_time']:
        submit_time = datetime.fromtimestamp(job['submit_time']).strftime('%Y-%m-%d %H:%M:%S')
        print(f"Submit Time: {submit_time}")
    
    if job['start_time']:
        start_time = datetime.fromtimestamp(job['start_time']).strftime('%Y-%m-%d %H:%M:%S')
        print(f"Start Time: {start_time}")
        
    if job['end_time']:
        end_time = datetime.fromtimestamp(job['end_time']).strftime('%Y-%m-%d %H:%M:%S')
        print(f"End Time: {end_time}")
        
    if job['exit_code'] is not None:
        print(f"Exit Code: {job['exit_code']}")
        
    if 'recent_output' in job and job['recent_output']:
        print("\nRecent Output:")
        print("-" * 40)
        print(job['recent_output'])
    
    return True

def cancel_job(args):
    """Cancel a specific job"""
    result = make_api_request('post', f"{args.server}/jobs/{args.job_id}/cancel")
    if result:
        print(f"Job {args.job_id} cancelled successfully.")
        return True
    return False

def get_gpu_status(args):
    """Get GPU status"""
    result = make_api_request('get', f"{args.server}/gpus")
    if not result:
        return False
    
    gpus = result.get("gpus", [])
    if not gpus:
        print("No GPUs found.")
        return True
    
    # Print header
    print(f"{'GPU ID':<8} {'NAME':<20} {'MEMORY':<18} {'UTIL %':<8} {'TEMP':<6} {'JOB':<10}")
    print("-" * 76)
    
    # Print GPUs
    for gpu in gpus:
        memory_str = f"{gpu['used_memory']} / {gpu['total_memory']} MB"
        job_str = gpu['assigned_job_id'] or "Free" if gpu['is_available'] else "Busy"
        
        print(f"{gpu['id']:<8} {gpu['name'][:20]:<20} {memory_str:<18} {gpu['utilization']:<8} {gpu['temperature']:<6} {job_str:<10}")
    
    return True

def view_log(args):
    """View job logs"""
    output_dir = os.path.expanduser(f"~/gpu-scheduler/output/{args.job_id}")
    
    if not os.path.isdir(output_dir):
        print(f"Log directory for job {args.job_id} not found")
        return False
        
    stdout_file = os.path.join(output_dir, "stdout.txt")
    stderr_file = os.path.join(output_dir, "stderr.txt")
    
    print("=== STDOUT ===")
    if os.path.isfile(stdout_file):
        with open(stdout_file, 'r') as f:
            print(f.read())
    else:
        print("No stdout log found")
    
    print("")
    print("=== STDERR ===")
    if os.path.isfile(stderr_file):
        with open(stderr_file, 'r') as f:
            print(f.read())
    else:
        print("No stderr log found")
    
    return True

def main():
    # Default server URL
    default_server = "http://localhost:9090"
    
    # Main parser
    parser = argparse.ArgumentParser(description='GPU Scheduler Client')
    parser.add_argument('--server', default=default_server, help='Scheduler server URL')
    
    # Subparsers
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Submit command
    submit_parser = subparsers.add_parser('submit', help='Submit a job')
    submit_parser.add_argument('--name', help='Job name')
    submit_parser.add_argument('--gpus', type=int, default=1, help='Number of GPUs required')
    submit_parser.add_argument('--gpu-ids', type=int, nargs='+', help='Specific GPU IDs to use')
    submit_parser.add_argument('--memory', type=int, default=5, help='Memory limit in GB')
    submit_parser.add_argument('--priority', type=int, default=0, help='Job priority (higher = more priority)')
    submit_parser.add_argument('--working-dir', help='Working directory')
    submit_parser.add_argument('--env', action='append', help='Environment variables in KEY=VALUE format')
    submit_parser.add_argument('command', help='Command to run (use quotes for commands with spaces)')
    submit_parser.set_defaults(func=submit_job)
    
    # List command
    list_parser = subparsers.add_parser('list', help='List all jobs')
    list_parser.set_defaults(func=list_jobs)
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Get job status')
    status_parser.add_argument('job_id', help='Job ID')
    status_parser.set_defaults(func=get_job_status)
    
    # Cancel command
    cancel_parser = subparsers.add_parser('cancel', help='Cancel a job')
    cancel_parser.add_argument('job_id', help='Job ID')
    cancel_parser.set_defaults(func=cancel_job)
    
    # GPU status command
    gpus_parser = subparsers.add_parser('gpus', help='Get GPU status')
    gpus_parser.set_defaults(func=get_gpu_status)
    
    # Log command
    log_parser = subparsers.add_parser('log', help='View job logs')
    log_parser.add_argument('job_id', help='Job ID')
    log_parser.set_defaults(func=view_log)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Check if command is specified
    if not hasattr(args, 'func'):
        parser.print_help()
        return 1
    
    # Execute command function
    success = args.func(args)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())