#!/bin/bash

echo "Uninstalling lyrix..."

if [ -f "/usr/bin/lyrix" ]; then
    sudo rm /usr/bin/lyrix
    echo "Removed /usr/bin/lyrix"
else
    echo "/usr/bin/lyrix not found, skipping."
fi


echo "Uninstallation complete."
