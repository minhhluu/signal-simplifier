#!/bin/bash

set -e

TOP=cordic_tb
OUT=cordic_sim
VCD=cordic.vcd

echo "Cleaning old files..."
rm -f $OUT $VCD

echo "Compiling..."
iverilog -Wall -o $OUT -s $TOP ../cordic.v ../cordic_tb.v ../iter_addsub.v

echo "Opening GTKWave (will wait for VCD)..."
gtkwave $VCD &

echo "Running simulation..."
vvp $OUT
