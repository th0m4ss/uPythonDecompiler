#!/usr/bin/env bash
ts-node -T disassemble.ts
for f in out/*.s; do
	ts-node -T decompile.ts $f > ${f::-2}.py
done
