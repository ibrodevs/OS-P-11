CC ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Wpedantic
.PHONY: all clean
all: page_faults matrix_bench
page_faults: page_faults.c
	$(CC) $(CFLAGS) -o $@ $<
matrix_bench: matrix_bench.c
	$(CC) $(CFLAGS) -o $@ $<
clean:
	rm -f page_faults matrix_bench
