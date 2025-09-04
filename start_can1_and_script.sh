#!bin/bash

#Bring up Can1 at 500 kbps with restart
ip link set can1 up type can bitrate 500000 restart-ms 100

export PYTHONPATH=/home/lns/.local/lib/python3.11/site-packages:$PYTHONPATH

#run the python script
python3 /home/lns/LnS.py

