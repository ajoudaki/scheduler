#!/usr/bin/env bash
# Installation script for GPU scheduler

set -e  # Exit on error

# Configuration
INSTALL_DIR="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/gpuscheduler"
SERVICE_DIR="$HOME/.config/systemd/user"
PYTHON_EXEC=$(which python3 || which python)

# Determine script path
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
SOURCE_SERVER="$SCRIPT_DIR/gpu-scheduler.py"
SOURCE_CLIENT="$SCRIPT_DIR/gpu-scheduler-client.py"

# Make sure install directory exists
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$SERVICE_DIR"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Installing GPU Scheduler...${NC}"

# Copy Python scripts to the config directory
cp "$SOURCE_SERVER" "$CONFIG_DIR/gpu-scheduler.py"
cp "$SOURCE_CLIENT" "$CONFIG_DIR/gpu-scheduler-client.py"

# Create wrapper script for gpu-scheduler
cat > "$INSTALL_DIR/gpuschedulerd" << 'EOF'
#!/usr/bin/env bash
# GPU Scheduler daemon control script

CONFIG_DIR="$HOME/.config/gpuscheduler"
PIDFILE="$CONFIG_DIR/scheduler.pid"
LOGFILE="$CONFIG_DIR/scheduler.log"

start() {
    if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
        echo "GPU scheduler is already running with PID $(cat "$PIDFILE")"
        return 0
    fi
    
    echo "Starting GPU scheduler..."
    mkdir -p "$CONFIG_DIR"
    nohup python3 "$CONFIG_DIR/gpu-scheduler.py" "$@" > "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    echo "GPU scheduler started with PID $!"
}

stop() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 $PID 2>/dev/null; then
            echo "Stopping GPU scheduler (PID $PID)..."
            kill $PID
            rm "$PIDFILE"
            echo "Stopped"
        else
            echo "GPU scheduler is not running (stale PID file)"
            rm "$PIDFILE"
        fi
    else
        echo "GPU scheduler is not running"
    fi
}

status() {
    if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
        echo "GPU scheduler is running with PID $(cat "$PIDFILE")"
        echo "Log file: $LOGFILE"
        
        # Try to connect to the server to verify it's responsive
        if curl -s "http://localhost:9090/gpus" > /dev/null; then
            echo "Server is responsive"
        else
            echo "Warning: Server is running but not responding to API requests"
        fi
    else
        echo "GPU scheduler is not running"
        [ -f "$PIDFILE" ] && rm "$PIDFILE"
    fi
}

restart() {
    stop
    sleep 2
    start "$@"
}

case "$1" in
    start)
        shift
        start "$@"
        ;;
    stop)
        stop
        ;;
    restart)
        shift
        restart "$@"
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status} [additional arguments]"
        exit 1
        ;;
esac
EOF

# Create client command wrapper script
cat > "$INSTALL_DIR/gpujob" << 'EOF'
#!/usr/bin/env bash
# GPU Scheduler client command wrapper

CONFIG_DIR="$HOME/.config/gpuscheduler"

# Check if server is running
check_server() {
    if ! curl -s "http://localhost:9090/gpus" > /dev/null; then
        echo "Error: GPU scheduler is not running or not accessible"
        echo "Start it with: gpuschedulerd start"
        return 1
    fi
    return 0
}

# Show help for all commands
show_help() {
    echo "GPU Job Scheduler Client"
    echo ""
    echo "Usage:"
    echo "  gpujob submit [options] <command>   Submit a new job"
    echo "  gpujob list                        List all jobs"
    echo "  gpujob status <job_id>             Show job status"
    echo "  gpujob cancel <job_id>             Cancel a job"
    echo "  gpujob gpus                        Show GPU status"
    echo "  gpujob log <job_id>                View job output log"
    echo ""
    echo "Submit options:"
    echo "  --name <name>            Job name"
    echo "  --gpus <num>             Number of GPUs required (default: 1)"
    echo "  --gpu-ids <ids>          Specific GPU IDs to use (space separated)"
    echo "  --memory <gb>            Memory limit in GB (default: 5)"
    echo "  --priority <num>         Job priority (higher = more priority)"
    echo "  --working-dir <dir>      Working directory"
    echo "  --env KEY=VALUE          Environment variable (can be repeated)"
    echo ""
    echo "Examples:"
    echo "  gpujob submit --name \"Training\" --gpus 2 \"python train.py\""
    echo "  gpujob list"
    echo "  gpujob gpus"
    echo "  gpujob status job1"
    echo "  gpujob log job1"
}

# Function to view job logs
view_log() {
    job_id="$1"
    output_dir="$HOME/gpu-scheduler/output/$job_id"
    
    if [ ! -d "$output_dir" ]; then
        echo "Log directory for job $job_id not found"
        exit 1
    fi
    
    stdout_file="$output_dir/stdout.txt"
    stderr_file="$output_dir/stderr.txt"
    
    echo "=== STDOUT ==="
    if [ -f "$stdout_file" ]; then
        cat "$stdout_file"
    else
        echo "No stdout log found"
    fi
    
    echo ""
    echo "=== STDERR ==="
    if [ -f "$stderr_file" ]; then
        cat "$stderr_file"
    else
        echo "No stderr log found"
    fi
}

# Parse command
cmd="$1"
shift || true

case "$cmd" in
    submit|list|status|cancel|gpus)
        check_server || exit 1
        python3 "$CONFIG_DIR/gpu-scheduler-client.py" "$cmd" "$@"
        ;;
    log)
        if [ -z "$1" ]; then
            echo "Error: Missing job ID"
            echo "Usage: gpujob log <job_id>"
            exit 1
        fi
        view_log "$1"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Unknown command: $cmd"
        show_help
        exit 1
        ;;
esac
EOF

# Create systemd service file
cat > "$SERVICE_DIR/gpuscheduler.service" << EOF
[Unit]
Description=GPU Job Scheduler
After=network.target

[Service]
Type=simple
ExecStart=$PYTHON_EXEC $CONFIG_DIR/gpu-scheduler.py --port 9090
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=default.target
EOF

# Make scripts executable
chmod +x "$INSTALL_DIR/gpuschedulerd"
chmod +x "$INSTALL_DIR/gpujob"
chmod +x "$CONFIG_DIR/gpu-scheduler.py"
chmod +x "$CONFIG_DIR/gpu-scheduler-client.py"

# Setup systemd service
systemctl --user daemon-reload

# Add to PATH if needed
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo -e "${BLUE}Adding $INSTALL_DIR to PATH${NC}"
    
    # Determine which shell config file to update
    SHELL_TYPE=$(basename "$SHELL")
    
    if [ "$SHELL_TYPE" = "bash" ]; then
        CONFIG_FILE="$HOME/.bashrc"
    elif [ "$SHELL_TYPE" = "zsh" ]; then
        CONFIG_FILE="$HOME/.zshrc"
    else
        CONFIG_FILE="$HOME/.profile"
    fi
    
    echo "# Added by GPU Scheduler installation" >> "$CONFIG_FILE"
    echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> "$CONFIG_FILE"
    
    echo -e "${GREEN}Added $INSTALL_DIR to PATH in $CONFIG_FILE${NC}"
    echo "Please run 'source $CONFIG_FILE' or start a new terminal for the changes to take effect."
else
    echo -e "${GREEN}$INSTALL_DIR is already in PATH${NC}"
fi

echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "Usage:"
echo "  Start the scheduler daemon:   gpuschedulerd start"
echo "  Submit a job:                 gpujob submit \"command to run\""
echo "  List all jobs:                gpujob list"
echo "  View job status:              gpujob status <job_id>"
echo "  View job logs:                gpujob log <job_id>"
echo "  Cancel a job:                 gpujob cancel <job_id>"
echo "  Show GPU status:              gpujob gpus"
echo ""
echo "To start the scheduler daemon automatically at login:"
echo "  systemctl --user enable gpuscheduler.service"
echo "  systemctl --user start gpuscheduler.service"