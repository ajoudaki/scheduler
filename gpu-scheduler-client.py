#!/usr/bin/env python3
"""
Client script for submitting jobs to the GPU scheduler
"""

import argparse
import json
import sys
import os
import requests

def submit_job(server_url, command, num_gpus=1, gpu_ids=None, memory_limit=5, 
               env=None, working_dir=None, name=None, priority=0):
    """Submit a job to the scheduler."""
    
    # Prepare job config
    job_config = {
        "command": command,
        "num_gpus": num_gpus,
        "memory_limit": memory_limit,
        "priority": priority
    }
    
    if gpu_ids:
        job_config["gpu_ids"] = gpu_ids
    if env:
        job_config["env"] = env
    if working_dir:
        job_config["working_dir"] = working_dir
    if name:
        job_config["name"] = name
    
    # Send request
    response = requests.post(f"{server_url}/jobs", json=job_config)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error submitting job: {response.text}", file=sys.stderr)
        return None

def list_jobs(server_url):
    """List all jobs in the scheduler."""
    response = requests.get(f"{server_url}/jobs")
    
    if response.status_code == 200:
        jobs = response.json()["jobs"]
        
        # Print header
        print(f"{'JOB ID':<10} {'NAME':<20} {'STATUS':<10} {'GPUs':<10} {'SUBMITTED':<20}")
        print("-" * 70)
        
        # Print jobs
        for job_id, job in jobs.items():
            gpus_str = ','.join(map(str, job['assigned_gpus'] or [])) if job['assigned_gpus'] else '-'
            submit_time = job['submit_time']
            # Convert timestamp to readable format if needed
            from datetime import datetime
            submit_time_str = datetime.fromtimestamp(submit_time).strftime('%Y-%m-%d %H:%M:%S') if submit_time else '-'
            
            print(f"{job_id:<10} {job['name'][:20]:<20} {job['status']:<10} {gpus_str:<10} {submit_time_str:<20}")
        
        return jobs
    else:
        print(f"Error listing jobs: {response.text}", file=sys.stderr)
        return None

def get_job_status(server_url, job_id):
    """Get detailed status for a specific job."""
    response = requests.get(f"{server_url}/jobs/{job_id}")
    
    if response.status_code == 200:
        job = response.json()["job"]
        
        # Print job details
        print(f"Job ID: {job_id}")
        print(f"Name: {job['name']}")
        print(f"Status: {job['status']}")
        print(f"Command: {job['command']}")
        print(f"GPUs: {', '.join(map(str, job['assigned_gpus'] or []))}" if job['assigned_gpus'] else "GPUs: (not assigned)")
        print(f"Memory Limit: {job['memory_limit']} GB")
        
        if job['submit_time']:
            from datetime import datetime
            submit_time = datetime.fromtimestamp(job['submit_time']).strftime('%Y-%m-%d %H:%M:%S')
            print(f"Submit Time: {submit_time}")
        
        if job['start_time']:
            from datetime import datetime
            start_time = datetime.fromtimestamp(job['start_time']).strftime('%Y-%m-%d %H:%M:%S')
            print(f"Start Time: {start_time}")
            
        if job['end_time']:
            from datetime import datetime
            end_time = datetime.fromtimestamp(job['end_time']).strftime('%Y-%m-%d %H:%M:%S')
            print(f"End Time: {end_time}")
            
        if job['exit_code'] is not None:
            print(f"Exit Code: {job['exit_code']}")
            
        if 'recent_output' in job and job['recent_output']:
            print("\nRecent Output:")
            print("-" * 40)
            print(job['recent_output'])
            
        return job
    else:
        print(f"Error getting job status: {response.text}", file=sys.stderr)
        return None

def cancel_job(server_url, job_id):
    """Cancel a job."""
    response = requests.post(f"{server_url}/jobs/{job_id}/cancel")
    
    if response.status_code == 200:
        print(f"Job {job_id} cancelled successfully.")
        return True
    else:
        print(f"Error cancelling job: {response.text}", file=sys.stderr)
        return False

def get_gpu_status(server_url):
    """Get GPU status."""
    response = requests.get(f"{server_url}/gpus")
    
    if response.status_code == 200:
        gpus = response.json()["gpus"]
        
        # Print header
        print(f"{'GPU ID':<8} {'NAME':<20} {'MEMORY':<18} {'UTIL %':<8} {'TEMP':<6} {'JOB':<10}")
        print("-" * 76)
        
        # Print GPUs
        for gpu in gpus:
            memory_str = f"{gpu['used_memory']} / {gpu['total_memory']} MB"
            job_str = gpu['assigned_job_id'] or "Free" if gpu['is_available'] else "Busy"
            
            print(f"{gpu['id']:<8} {gpu['name'][:20]:<20} {memory_str:<18} {gpu['utilization']:<8} {gpu['temperature']:<6} {job_str:<10}")
        
        return gpus
    else:
        print(f"Error getting GPU status: {response.text}", file=sys.stderr)
        return None

def main():
    # Default server URL
    default_server = "http://localhost:9090"
    
    # Main parser
    parser = argparse.ArgumentParser(description='GPU Scheduler Client')
    parser.add_argument('--server', default=default_server, help='Scheduler server URL')
    
    # Subparsers
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Submit job command
    submit_parser = subparsers.add_parser('submit', help='Submit a new job')
    submit_parser.add_argument('--name', help='Job name')
    submit_parser.add_argument('--gpus', type=int, default=1, help='Number of GPUs required')
    submit_parser.add_argument('--gpu-ids', type=int, nargs='+', help='Specific GPU IDs to use')
    submit_parser.add_argument('--memory', type=int, default=5, help='Memory limit in GB')
    submit_parser.add_argument('--priority', type=int, default=0, help='Job priority (higher = more priority)')
    submit_parser.add_argument('--working-dir', help='Working directory')
    submit_parser.add_argument('--env', action='append', help='Environment variables in KEY=VALUE format')
    submit_parser.add_argument('command', nargs='+', help='Command to run')
    
    # List jobs command
    subparsers.add_parser('list', help='List all jobs')
    
    # Job status command
    status_parser = subparsers.add_parser('status', help='Get job status')
    status_parser.add_argument('job_id', help='Job ID')
    
    # Cancel job command
    cancel_parser = subparsers.add_parser('cancel', help='Cancel a job')
    cancel_parser.add_argument('job_id', help='Job ID')
    
    # GPU status command
    subparsers.add_parser('gpus', help='Get GPU status')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Process commands
    if args.command == 'submit':
        # Parse environment variables
        env = {}
        if args.env:
            for env_var in args.env:
                key, value = env_var.split('=', 1)
                env[key] = value
        
        # Build command string from args
        command_str = ' '.join(args.command)
        
        result = submit_job(
            args.server,
            command_str,
            num_gpus=args.gpus,
            gpu_ids=args.gpu_ids,
            memory_limit=args.memory,
            env=env or None,
            working_dir=args.working_dir,
            name=args.name,
            priority=args.priority
        )
        
        if result:
            print(f"Job submitted with ID: {result['job_id']}")
            
    elif args.command == 'list':
        list_jobs(args.server)
        
    elif args.command == 'status':
        get_job_status(args.server, args.job_id)
        
    elif args.command == 'cancel':
        cancel_job(args.server, args.job_id)
        
    elif args.command == 'gpus':
        get_gpu_status(args.server)
        
    else:
        parser.print_help()

if __name__ == "__main__":
    main()