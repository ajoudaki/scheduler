# GPU Scheduler Updates

## Client Improvements

The GPU scheduler client has been completely rewritten to improve reliability and usability:

### Key Improvements

1. **Robust Command Parsing**: The new client properly handles commands with spaces and special characters.
2. **Enhanced Error Handling**: Better error messages and handling of connection issues.
3. **Port Auto-Detection**: The client will automatically try ports 9090 and 8000, using whichever is running the server.
4. **Improved Documentation**: More detailed help messages and command examples.
5. **Log Viewing Support**: View job logs directly from the client.
6. **Consistent Formatting**: Cleaner, more readable output.

### How to Use

The updated `gpujob` command now has these capabilities:

```bash
# Submit a job (commands with spaces must be quoted)
gpujob submit --name "experiment" --gpus 2 --priority 10 "python /path/to/script.py --batch-size 64"

# List all jobs
gpujob list

# Check job status
gpujob status job1

# View job logs
gpujob log job1

# Check GPU status
gpujob gpus

# Cancel a job
gpujob cancel job1
```

### Implementation Notes

- The client has been completely rewritten using a function delegation pattern for better maintainability.
- All operations now go through a common API request handler with consistent error handling.
- Default port is now 9090, but the client can automatically detect if the server is running on 8000.
- Multiple commands can run concurrently with each command as a separate invocation.

## Server Improvements

- The systemd service now runs with a faster poll interval (10 seconds instead of 30) for more responsive job scheduling.
- Default port has been standardized to 9090.

## Installation

No changes are needed to your current setup. The updated client has been installed to replace the previous version.

If you'd like to reinstall:

```bash
./install.sh
```

This will update all relevant scripts and services with the latest improvements.