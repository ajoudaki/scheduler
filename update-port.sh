#!/usr/bin/env bash
# Script to update existing installed GPU scheduler scripts to use the new port

set -e  # Exit on error

# Configuration
INSTALL_DIR="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/gpuscheduler"
SERVICE_DIR="$HOME/.config/systemd/user"
NEW_PORT=9090
OLD_PORT=8000

echo "Updating GPU scheduler scripts to use port $NEW_PORT..."

# Update installed daemon script
if [ -f "$INSTALL_DIR/gpuschedulerd" ]; then
    echo "Updating installed daemon script..."
    sed -i "s|http://localhost:$OLD_PORT/gpus|http://localhost:$NEW_PORT/gpus|g" "$INSTALL_DIR/gpuschedulerd"
fi

# Update installed client script
if [ -f "$INSTALL_DIR/gpujob" ]; then
    echo "Updating installed client script..."
    sed -i "s|http://localhost:$OLD_PORT/gpus|http://localhost:$NEW_PORT/gpus|g" "$INSTALL_DIR/gpujob"
fi

# Update installed Python client
if [ -f "$CONFIG_DIR/gpu-scheduler-client.py" ]; then
    echo "Updating installed Python client..."
    sed -i "s|default_server = \"http://localhost:$OLD_PORT\"|default_server = \"http://localhost:$NEW_PORT\"|g" "$CONFIG_DIR/gpu-scheduler-client.py"
fi

# Update systemd service file
if [ -f "$SERVICE_DIR/gpuscheduler.service" ]; then
    echo "Updating systemd service file..."
    PYTHON_EXEC=$(which python3 || which python)
    
    # Check if port is already in the file
    if grep -q "\--port" "$SERVICE_DIR/gpuscheduler.service"; then
        sed -i "s|--port $OLD_PORT|--port $NEW_PORT|g" "$SERVICE_DIR/gpuscheduler.service"
    else
        sed -i "s|ExecStart=.*|ExecStart=$PYTHON_EXEC $CONFIG_DIR/gpu-scheduler.py --port $NEW_PORT|g" "$SERVICE_DIR/gpuscheduler.service"
    fi
    
    # Reload systemd
    systemctl --user daemon-reload
    echo "Systemd service updated. You may need to restart the service:"
    echo "  systemctl --user restart gpuscheduler.service"
fi

echo "Port update complete!"
echo "If the server is running, you should restart it:"
echo "  gpuschedulerd restart --port $NEW_PORT"