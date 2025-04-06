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
    output_dir="results/2_$i"
    mkdir -p "$output_dir"

    # Run the locust command and save outputs in the created directory
    locust -f locustfile.py --headless --autostart --autoquit 45 \
        -H "$HOST" \
        -u 1000 \
        -r 100 \
        -t 1m \
        -s 30 \
        --print-stats \
        --logfile "$output_dir/logfile_u1000_r100_t1m.log" \
        --html "$output_dir/report_u1000_r100_t1m.html" \
        --csv "$output_dir/report_u1000_r100_t1m" \
        --csv-full-history

    # Wait for 2 minute before the next test
    sleep 2m
done