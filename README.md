# GPU Scheduler

A lightweight GPU job scheduler for managing GPU resources and job execution across multiple NVIDIA GPUs.

## Overview

This scheduler provides a simple client-server architecture for managing GPU jobs:

- **Server**: Manages GPU resources and job execution
- **Client**: Command-line interface for job submission and management
- **REST API**: HTTP-based API for interacting with the scheduler

## Installation

```bash
# Install the scheduler
./install.sh

# Enable autostart at login (optional)
systemctl --user enable gpuscheduler.service

# Start the scheduler service
systemctl --user start gpuscheduler.service
```

## Server

The server monitors GPU resources and handles job scheduling. By default, it runs on port 9090.

```bash
# Start the server manually
python gpu-scheduler.py [--port PORT] [--poll-interval SECONDS] [--min-free-memory MB] [--max-gpu-util PERCENT]

# Or use the daemon script
gpuschedulerd start [additional arguments]
gpuschedulerd status
gpuschedulerd stop
```

## Submitting Jobs

### Using the Command Line Tool

The `gpujob` command provides a user-friendly interface for job management:

```bash
# Submit a job requiring 1 GPU
gpujob submit --gpus 1 --name "test-job" python your_script.py

# Submit a job with higher priority (higher number = higher priority)
gpujob submit --priority 10 --name "high-priority" python your_script.py

# Submit a job requesting specific GPUs
gpujob submit --gpu-ids 0 1 --name "specific-gpus" python your_script.py

# Submit a job with memory limit (in GB)
gpujob submit --memory 8 --name "memory-limited" python your_script.py

# Submit with environment variables
gpujob submit --env BATCH_SIZE=64 --env LR=0.001 python train.py

# Submit with a specific working directory
gpujob submit --working-dir /path/to/project python train.py
```

### Using REST API Directly

You can also submit jobs directly to the API:

```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "command": "python your_script.py",
  "num_gpus": 1,
  "memory_limit": 5,
  "priority": 10,
  "name": "api-job"
}' http://localhost:9090/jobs
```

## Managing Jobs

```bash
# List all jobs
gpujob list

# Check job status
gpujob status JOB_ID

# Cancel a job
gpujob cancel JOB_ID

# Check GPU status
gpujob gpus

# View job logs
gpujob log JOB_ID
```

## Job Priority and Scheduling

Jobs are scheduled based on priority (higher number = higher priority) and submission time. The scheduler:

1. Assigns jobs to GPUs based on availability and job requirements
2. Manages memory limits using systemd-run or ulimit
3. Sets `CUDA_VISIBLE_DEVICES` to control which GPUs are visible to each job
4. Captures job output to `~/gpu-scheduler/output/[job_id]/`

## Environment Variables

All jobs have access to the `CUDA_VISIBLE_DEVICES` environment variable, which specifies which GPUs are assigned to the job. You can also pass additional environment variables using the `--env` option.

## Examples

```bash
# Train a model using 2 GPUs
gpujob submit --gpus 2 --name "training" --priority 10 python train.py --epochs 100

# Run a GPU performance test
gpujob submit --gpus 1 --name "benchmark" python benchmark.py

# Run an interactive notebook server (low priority)
gpujob submit --priority 1 --name "jupyter" jupyter notebook --ip=0.0.0.0

# Submit job that runs for a long time with limited memory
gpujob submit --memory 4 --name "memory-limited" python long_job.py
```

## Advanced Usage

### Direct API Usage

The scheduler exposes a REST API on port 9090 that you can use for integration with other tools:

- `GET http://localhost:9090/jobs` - List all jobs
- `POST http://localhost:9090/jobs` - Submit a new job
- `GET http://localhost:9090/jobs/{job_id}` - Get status of a specific job
- `POST http://localhost:9090/jobs/{job_id}/cancel` - Cancel a job
- `GET http://localhost:9090/gpus` - Get status of all GPUs

### Job Configuration Options

- `command` - The command to run
- `num_gpus` - Number of GPUs required (default: 1)
- `gpu_ids` - Specific GPU IDs to request (optional)
- `memory_limit` - Memory limit in GB (default: 5)
- `priority` - Job priority (default: 0, higher = more priority)
- `env` - Environment variables
- `working_dir` - Working directory
- `name` - Job name

## Troubleshooting

- Server logs: `~/.config/gpuscheduler/scheduler.log`
- Job output: `~/gpu-scheduler/output/[job_id]/stdout.txt` and `stderr.txt`
- Check server status: `gpuschedulerd status`
- Check if server is responding: `curl http://localhost:9090/gpus`