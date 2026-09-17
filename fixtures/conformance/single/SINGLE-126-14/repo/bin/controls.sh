#!/bin/sh
printf 'bad:\377\r\nlone\rtab:\tend\n'
printf 'esc:\033[31mred\033[0m\n'
printf 'c0:\001 del:\177 c1:\302\205\n'
printf 'err\r\n' >&2
