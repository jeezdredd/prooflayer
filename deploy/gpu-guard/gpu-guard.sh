#!/usr/bin/env bash
set -u

CONTAINER="${GPU_GUARD_CONTAINER:-deploy-ollama-1}"
HOT="${GPU_GUARD_HOT:-88}"
COOL="${GPU_GUARD_COOL:-75}"
INTERVAL="${GPU_GUARD_INTERVAL:-3}"
CURVE_TEMPS=(40 50 60 65 70 75 80 90)
CURVE_PWMS=(60 90 130 170 210 240 255 255)

hwmon_named() {
    for h in /sys/class/hwmon/hwmon*; do
        [ "$(cat "$h/name" 2>/dev/null)" = "$1" ] && echo "$h"
    done
}

set_fan_curve() {
    local fan
    fan=$(hwmon_named asus_custom_fan_curve | head -1)
    [ -n "$fan" ] || { logger -t gpu-guard "no asus_custom_fan_curve, fans left on firmware curve"; return; }
    for pwm in 1 2; do
        for i in "${!CURVE_TEMPS[@]}"; do
            echo "${CURVE_TEMPS[$i]}" > "$fan/pwm${pwm}_auto_point$((i + 1))_temp"
            echo "${CURVE_PWMS[$i]}" > "$fan/pwm${pwm}_auto_point$((i + 1))_pwm"
        done
        echo 1 > "$fan/pwm${pwm}_enable"
    done
    logger -t gpu-guard "fan curve set: full speed from ${CURVE_TEMPS[6]}C"
}

gpu_temp() {
    local hottest=0 value
    for h in $(hwmon_named amdgpu); do
        value=$(( $(cat "$h/temp1_input" 2>/dev/null || echo 0) / 1000 ))
        [ "$value" -gt "$hottest" ] && hottest=$value
    done
    echo "$hottest"
}

set_fan_curve

paused=0
while true; do
    temp=$(gpu_temp)
    if [ "$paused" = 0 ] && [ "$temp" -ge "$HOT" ]; then
        docker pause "$CONTAINER" >/dev/null 2>&1 && paused=1
        logger -t gpu-guard "GPU ${temp}C >= ${HOT}C, paused ${CONTAINER}"
    elif [ "$paused" = 1 ] && [ "$temp" -le "$COOL" ]; then
        docker unpause "$CONTAINER" >/dev/null 2>&1
        paused=0
        logger -t gpu-guard "GPU ${temp}C <= ${COOL}C, resumed ${CONTAINER}"
    fi
    sleep "$INTERVAL"
done
