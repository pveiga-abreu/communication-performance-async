#!/bin/bash

# Default host value
HOST="http://localhost:8000"

# Parse command-line arguments
while getopts "h:" opt; do
    case $opt in
        h) HOST="$OPTARG" ;;
        *) echo "Usage: $0 [-h host]"; exit 1 ;;
    esac
done

for i in {1..10}; do
    # Create a directory for the current execution
    output_dir="results/4_$i"
    mkdir -p "$output_dir"

    # Run the locust command and save outputs in the created directory
    locust -f locustfile.py  --headless --autostart --autoquit 90 \
        -H "$HOST" \
        -u 4000 \
        -r 400 \
        -t 1m \
        -s 60 \
        --print-stats \
        --logfile "$output_dir/logfile_u4000_r400_t2m.log" \
        --html "$output_dir/report_u4000_r400_t2m.html" \
        --csv "$output_dir/report_u4000_r400_t2m" \
        --csv-full-history

    # Wait for 2 minute before the next test
    sleep 2m
done