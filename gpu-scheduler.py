#!/usr/bin/env python3
"""
Simple GPU Job Scheduler - A lightweight alternative to SLURM for local GPU management
"""

import json
import subprocess
import threading
import time
import os
import argparse
import logging
import socket
import queue
import signal
import sys
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("gpu-scheduler")

@dataclass
class JobConfig:
    """Configuration for a job to be executed."""
    command: str
    gpu_ids: List[int] = None  # If None, any available GPU will be used
    num_gpus: int = 1  # Number of GPUs needed
    memory_limit: int = 5  # In GB
    env: Dict[str, str] = None
    working_dir: str = None
    name: str = None
    priority: int = 0  # Higher number = higher priority

@dataclass
class Job(JobConfig):
    """A job that is either queued or running."""
    job_id: str = None
    status: str = "queued"  # queued, running, completed, failed
    assigned_gpus: List[int] = None
    submit_time: float = None
    start_time: float = None
    end_time: float = None
    exit_code: Optional[int] = None
    pid: Optional[int] = None
    output_file: Optional[str] = None
    error_file: Optional[str] = None

@dataclass
class GPUInfo:
    """Information about a GPU."""
    id: int
    name: str
    total_memory: int  # In MB
    used_memory: int  # In MB
    utilization: int  # Percentage
    temperature: int  # Celsius
    power_usage: float  # Watts
    power_limit: float  # Watts
    is_available: bool = True
    assigned_job_id: Optional[str] = None

class GPUScheduler:
    """Manages GPU resources and job scheduling."""
    
    def __init__(self, poll_interval=10, min_free_memory=1000, max_gpu_util=10):
        self.jobs: Dict[str, Job] = {}
        self.job_queue = queue.PriorityQueue()
        self.next_job_id = 1
        self.poll_interval = poll_interval  # seconds
        self.min_free_memory = min_free_memory  # MB
        self.max_gpu_util = max_gpu_util  # percent
        self.lock = threading.RLock()
        self.gpus: Dict[int, GPUInfo] = {}
        self.running = True
        self.output_dir = os.path.expanduser("~/gpu-scheduler/output")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Start the monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
    def _get_job_id(self) -> str:
        """Generate a unique job ID."""
        with self.lock:
            job_id = f"job{self.next_job_id}"
            self.next_job_id += 1
            return job_id
    
    def _monitor_loop(self):
        """Main monitoring loop that periodically checks GPU status and starts jobs."""
        while self.running:
            try:
                self._update_gpu_info()
                self._check_running_jobs()
                self._start_pending_jobs()
                time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
    
    def _update_gpu_info(self):
        """Update information about available GPUs using nvidia-smi."""
        try:
            # Get GPU information using nvidia-smi
            output = subprocess.check_output([
                'nvidia-smi', 
                '--query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu,power.draw,power.limit', 
                '--format=csv,noheader,nounits'
            ]).decode('utf-8').strip()
            
            with self.lock:
                # Parse output
                for line in output.split('\n'):
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) < 8:
                        continue
                        
                    gpu_id = int(parts[0])
                    gpu_info = GPUInfo(
                        id=gpu_id,
                        name=parts[1],
                        total_memory=int(float(parts[2])),
                        used_memory=int(float(parts[3])),
                        utilization=int(float(parts[4])),
                        temperature=int(float(parts[5])),
                        power_usage=float(parts[6]),
                        power_limit=float(parts[7]),
                        is_available=True  # Will be updated below
                    )
                    
                    # Check if this GPU is assigned to a job
                    for job_id, job in self.jobs.items():
                        if job.status == "running" and job.assigned_gpus and gpu_id in job.assigned_gpus:
                            gpu_info.is_available = False
                            gpu_info.assigned_job_id = job_id
                            break
                            
                    # Also consider it unavailable if it's highly utilized or low on memory
                    free_memory = gpu_info.total_memory - gpu_info.used_memory
                    if free_memory < self.min_free_memory or gpu_info.utilization > self.max_gpu_util:
                        if gpu_info.assigned_job_id is None:  # Only mark as unavailable if not explicitly assigned
                            gpu_info.is_available = False
                            
                    # Update or add the GPU info
                    self.gpus[gpu_id] = gpu_info
            
            logger.debug(f"Updated GPU info. Available GPUs: {[gpu.id for gpu in self.gpus.values() if gpu.is_available]}")
        except Exception as e:
            logger.error(f"Error updating GPU info: {e}", exc_info=True)
    
    def _check_running_jobs(self):
        """Check the status of running jobs and update their status."""
        with self.lock:
            for job_id, job in list(self.jobs.items()):
                if job.status == "running" and job.pid:
                    try:
                        # Check if the process is still running
                        os.kill(job.pid, 0)
                    except OSError:
                        # Process is not running
                        job.status = "completed"
                        job.end_time = time.time()
                        
                        # Try to get exit code from the process if possible
                        try:
                            _, status = os.waitpid(job.pid, os.WNOHANG)
                            job.exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else -1
                        except:
                            job.exit_code = -1
                            
                        logger.info(f"Job {job_id} ({job.name}) completed with exit code {job.exit_code}")
                        
                        # Release GPU
                        if job.assigned_gpus:
                            for gpu_id in job.assigned_gpus:
                                if gpu_id in self.gpus:
                                    self.gpus[gpu_id].assigned_job_id = None
    
    def _start_pending_jobs(self):
        """Check if there are any pending jobs that can be started."""
        with self.lock:
            # Get list of available GPUs
            available_gpus = [gpu.id for gpu in self.gpus.values() if gpu.is_available]
            if not available_gpus:
                return
                
            # Check queue size
            if self.job_queue.empty():
                return
                
            # Try to start jobs from the queue
            tried_jobs = []
            while not self.job_queue.empty():
                # Get next job from the queue based on priority
                priority, timestamp, job_id = self.job_queue.get()
                job = self.jobs[job_id]
                
                # Check if job is still queued
                if job.status != "queued":
                    continue
                    
                # If job requires specific GPUs, check if they're available
                if job.gpu_ids:
                    if not all(gpu_id in available_gpus for gpu_id in job.gpu_ids):
                        # Put it back in the queue and try the next one
                        tried_jobs.append((priority, timestamp, job_id))
                        continue
                    assigned_gpus = job.gpu_ids
                else:
                    # Assign required number of GPUs
                    if len(available_gpus) < job.num_gpus:
                        # Not enough GPUs available
                        tried_jobs.append((priority, timestamp, job_id))
                        continue
                    assigned_gpus = available_gpus[:job.num_gpus]
                
                # Start the job since we have the necessary GPU(s)
                self._launch_job(job, assigned_gpus)
                
                # Update available GPUs
                for gpu_id in assigned_gpus:
                    available_gpus.remove(gpu_id)
                    
                # If no more GPUs, break
                if not available_gpus:
                    break
            
            # Put tried jobs back in the queue
            for job_item in tried_jobs:
                self.job_queue.put(job_item)
                
    def _launch_job(self, job: Job, assigned_gpus: List[int]):
        """Launch a job on the specified GPUs."""
        try:
            # Update job and GPUs
            job.status = "running"
            job.start_time = time.time()
            job.assigned_gpus = assigned_gpus
            
            # Mark GPUs as assigned
            for gpu_id in assigned_gpus:
                if gpu_id in self.gpus:
                    self.gpus[gpu_id].is_available = False
                    self.gpus[gpu_id].assigned_job_id = job.job_id
            
            # Set up output files
            job_output_dir = os.path.join(self.output_dir, job.job_id)
            os.makedirs(job_output_dir, exist_ok=True)
            job.output_file = os.path.join(job_output_dir, "stdout.txt")
            job.error_file = os.path.join(job_output_dir, "stderr.txt")
            
            # Prepare command environment
            env = os.environ.copy()
            if job.env:
                env.update(job.env)
            
            # Set CUDA_VISIBLE_DEVICES
            env['CUDA_VISIBLE_DEVICES'] = ','.join(map(str, assigned_gpus))
            
            # Prepare memory limit using cgroups or ulimit
            memory_limit_mb = job.memory_limit * 1024  # Convert GB to MB
            
            # Create command to run with memory limits using systemd-run
            if shutil.which("systemd-run"):
                # Using systemd-run which is more reliable for resource limits
                launch_cmd = [
                    "systemd-run", 
                    "--user", 
                    "--scope", 
                    f"--property=MemoryLimit={job.memory_limit}G",
                    "bash", "-c", job.command
                ]
            else:
                # Fallback to ulimit
                launch_cmd = [
                    "bash", "-c", 
                    f"ulimit -v {memory_limit_mb * 1024} && {job.command}"
                ]
            
            # Open files for stdout and stderr
            stdout_file = open(job.output_file, 'w')
            stderr_file = open(job.error_file, 'w')
            
            # Launch the process
            working_dir = job.working_dir or os.getcwd()
            process = subprocess.Popen(
                launch_cmd,
                stdout=stdout_file,
                stderr=stderr_file,
                cwd=working_dir,
                env=env,
                start_new_session=True  # Create a new process group
            )
            
            job.pid = process.pid
            logger.info(f"Started job {job.job_id} ({job.name}) on GPUs {assigned_gpus} with PID {job.pid}")
            
        except Exception as e:
            logger.error(f"Error launching job {job.job_id}: {e}", exc_info=True)
            job.status = "failed"
            job.exit_code = -1
            job.end_time = time.time()
            # Free up GPUs
            for gpu_id in assigned_gpus:
                if gpu_id in self.gpus:
                    self.gpus[gpu_id].assigned_job_id = None
    
    def submit_job(self, config: JobConfig) -> str:
        """Submit a new job to the queue."""
        with self.lock:
            job_id = self._get_job_id()
            job = Job(
                **asdict(config),
                job_id=job_id,
                status="queued",
                submit_time=time.time()
            )
            
            # Set a default name if none provided
            if not job.name:
                job.name = f"job-{job_id}"
                
            # Add to jobs dictionary
            self.jobs[job_id] = job
            
            # Add to priority queue (lower number = higher priority)
            # Use negative priority so higher numbers have higher priority
            self.job_queue.put((-job.priority, job.submit_time, job_id))
            
            logger.info(f"Submitted job {job_id} ({job.name})")
            return job_id
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job if it exists and is not already completed."""
        with self.lock:
            if job_id not in self.jobs:
                return False
                
            job = self.jobs[job_id]
            
            # If job is running, kill the process
            if job.status == "running" and job.pid:
                try:
                    # Kill the entire process group
                    os.killpg(os.getpgid(job.pid), signal.SIGTERM)
                    job.status = "cancelled"
                    job.end_time = time.time()
                    
                    # Release GPUs
                    if job.assigned_gpus:
                        for gpu_id in job.assigned_gpus:
                            if gpu_id in self.gpus:
                                self.gpus[gpu_id].assigned_job_id = None
                    
                    logger.info(f"Cancelled running job {job_id}")
                    return True
                except Exception as e:
                    logger.error(f"Error cancelling job {job_id}: {e}", exc_info=True)
                    return False
            elif job.status == "queued":
                # Job is in queue, just mark it as cancelled
                job.status = "cancelled"
                job.end_time = time.time()
                logger.info(f"Cancelled queued job {job_id}")
                return True
            
            return False
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get status information for a specific job."""
        with self.lock:
            if job_id not in self.jobs:
                return None
            
            job = self.jobs[job_id]
            result = asdict(job)
            
            # Add output content if available
            if job.output_file and os.path.exists(job.output_file):
                with open(job.output_file, 'r') as f:
                    # Get the last 50 lines
                    result['recent_output'] = ''.join(f.readlines()[-50:])
                    
            return result
    
    def get_all_jobs(self) -> Dict[str, Dict]:
        """Get information about all jobs."""
        with self.lock:
            return {job_id: asdict(job) for job_id, job in self.jobs.items()}
    
    def get_gpu_status(self) -> List[Dict]:
        """Get status information for all GPUs."""
        with self.lock:
            return [asdict(gpu) for gpu in self.gpus.values()]
    
    def shutdown(self):
        """Shut down the scheduler and stop all running jobs."""
        logger.info("Shutting down scheduler...")
        with self.lock:
            self.running = False
            
            # Cancel all running jobs
            for job_id, job in self.jobs.items():
                if job.status == "running" and job.pid:
                    try:
                        os.killpg(os.getpgid(job.pid), signal.SIGTERM)
                    except:
                        pass
        
        # Wait for monitor thread to finish
        self.monitor_thread.join(timeout=5)
        logger.info("Scheduler shutdown complete")

class HTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the job scheduler API."""
    
    def __init__(self, *args, scheduler=None, **kwargs):
        self.scheduler = scheduler
        super().__init__(*args, **kwargs)
    
    def _set_headers(self, status_code=200, content_type='application/json'):
        self.send_response(status_code)
        self.send_header('Content-type', content_type)
        self.end_headers()
    
    def _send_json_response(self, data, status_code=200):
        self._set_headers(status_code)
        self.wfile.write(json.dumps(data).encode())
    
    def _parse_json_body(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        return json.loads(post_data.decode('utf-8'))
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
        try:
            # Route handling
            if path == '/jobs':
                # Get all jobs
                jobs = self.scheduler.get_all_jobs()
                self._send_json_response({'jobs': jobs})
            elif path.startswith('/jobs/'):
                # Get specific job
                job_id = path.split('/')[-1]
                job = self.scheduler.get_job_status(job_id)
                if job:
                    self._send_json_response({'job': job})
                else:
                    self._send_json_response({'error': 'Job not found'}, 404)
            elif path == '/gpus':
                # Get GPU status
                gpus = self.scheduler.get_gpu_status()
                self._send_json_response({'gpus': gpus})
            else:
                self._send_json_response({'error': 'Not found'}, 404)
        except Exception as e:
            logger.error(f"Error handling GET request: {e}", exc_info=True)
            self._send_json_response({'error': str(e)}, 500)
    
    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
        try:
            # Route handling
            if path == '/jobs':
                # Submit a new job
                job_config = self._parse_json_body()
                job_id = self.scheduler.submit_job(JobConfig(**job_config))
                self._send_json_response({'job_id': job_id})
            elif path.startswith('/jobs/') and path.endswith('/cancel'):
                # Cancel a job
                job_id = path.split('/')[-2]
                success = self.scheduler.cancel_job(job_id)
                if success:
                    self._send_json_response({'success': True})
                else:
                    self._send_json_response({'error': 'Failed to cancel job'}, 400)
            else:
                self._send_json_response({'error': 'Not found'}, 404)
        except Exception as e:
            logger.error(f"Error handling POST request: {e}", exc_info=True)
            self._send_json_response({'error': str(e)}, 500)

def run_server(port=8000, poll_interval=30, min_free_memory=1000, max_gpu_util=10):
    """Run the HTTP server."""    
    
    # Check if required tools are available
    if not shutil.which("nvidia-smi"):
        logger.error("nvidia-smi not found. This tool requires NVIDIA GPUs.")
        return
    
    # Create scheduler
    scheduler = GPUScheduler(
        poll_interval=poll_interval,
        min_free_memory=min_free_memory,
        max_gpu_util=max_gpu_util
    )
    
    # Set up HTTP server
    def handler(*args, **kwargs):
        HTTPHandler(*args, scheduler=scheduler, **kwargs)
    
    server = HTTPServer(('localhost', port), handler)
    
    logger.info(f"Starting server on port {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server due to keyboard interrupt...")
    finally:
        scheduler.shutdown()
        server.server_close()
        logger.info("Server shutdown complete")

def main():
    parser = argparse.ArgumentParser(description='Simple GPU job scheduler')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    parser.add_argument('--poll-interval', type=int, default=30, help='Interval in seconds to poll GPU status')
    parser.add_argument('--min-free-memory', type=int, default=1000, help='Minimum free memory in MB to consider a GPU available')
    parser.add_argument('--max-gpu-util', type=int, default=10, help='Maximum GPU utilization percentage to consider a GPU available')
    
    args = parser.parse_args()
    run_server(
        port=args.port,
        poll_interval=args.poll_interval,
        min_free_memory=args.min_free_memory,
        max_gpu_util=args.max_gpu_util
    )

if __name__ == "__main__":
    main()